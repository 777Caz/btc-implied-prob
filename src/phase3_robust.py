"""
Phase 3 robustness (roadmap A): checks on the phase-3 machinery and an exploratory option test.

  1. Forward validation by tenor. Parity forwards (src/forwards.py) vs Deribit dated futures on
     ~3 random days per month, split into < 7d, 7-30d, 30-90d, 90d+ to expiry.
  2. Discounting test. If Deribit's BTC prices were USD values discounted at a rate r, put-call
     parity would read  c - p = DF * (1 - K/F)  with DF = exp(-rT) < 1, and forwards backed out
     with DF = 1 would be biased more at long tenors. Each live snapshot has Deribit's own forward
     per expiry, so fit DF per expiry (regression through the origin of c - p on 1 - K/F).
  3. Look-ahead. Rebuild the inputs of every historical fit (phase3_hist.month_tasks) and assert
     every trade used is in [origin - 8h, origin) and every expiry is > 1 day after the origin.
  4. Tail breaches split by origin year (and 2022 vs the rest), with moving-block bootstrap CIs:
     daily 30-day windows overlap, so plain binomial CIs would be far too narrow.
  5. EXPLORATORY: buy a ~30-day 25-delta call, and separately a 25-delta risk reversal (long call,
     short put), at 08:00 UTC every 30 days, hold to Deribit delivery. Entry prices from trades:
     median trade IV per instrument in the 8h before 08:00, repriced at 08:00 with Black-76 on the
     parity forward, then a half-spread in vol points against us, plus Deribit fees. Main result at
     HALF_SPREAD_VOL = 1.0 vol pt: above the 90th percentile of 2026 snapshot spreads for similar
     options (0.72), because spreads were likely wider in 2021-22. Sensitivity at 0 / p90 / 2.0.
     Not a strategy backtest: ~65 trades, one sample path, no position sizing.

Outputs: reports/phase3/robustness/*.csv and RESULTS.md.
Run:  python -m src.phase3_robust
"""
import glob
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

import config
from src import phase2
from src.api import deribit
from src.clean_trades import COLUMNS, clean
from src.forwards import forward_by_expiry
from src.models import smile as sm
from src.phase3_hist import WINDOW, basis_by_expiry, month_tasks

log = logging.getLogger(__name__)
OUT = config.PHASE3_DIR / "robustness"
OUT.mkdir(parents=True, exist_ok=True)

YEAR_S = 365 * 86400
TENORS = [0, 7, 30, 90, np.inf]
TENOR_LABELS = ["<7d", "7-30d", "30-90d", "90d+"]
FUT_DAYS_PER_MONTH, FUT_WINDOW = 3, pd.Timedelta("6h")
STRAT_EVERY = 30                       # days between entries
STRAT_T_RANGE = (20, 45)               # acceptable days to expiry for the "30-day" option
TARGET_DELTA = 0.25
FEE_RATE, FEE_CAP = 0.0003, 0.125      # Deribit option trade fee: 0.03% of underlying, cap 12.5% of price
DELIVERY_FEE = 0.00015                 # Deribit delivery fee: 0.015% of underlying, same 12.5% cap
HALF_SPREAD_VOL = 1.0                  # vol points against us on every leg (main result)
N_BOOT = 10_000
RNG = np.random.default_rng(7)


def tenor_bucket(days):
    return pd.cut(days, TENORS, labels=TENOR_LABELS, right=False)


# ── 1. Forward vs futures by tenor ──────────────────────────────────────────────────────────
def futures_check_day(trades: pd.DataFrame, ref: pd.Timestamp) -> pd.DataFrame:
    w = trades.loc[ref - FUT_WINDOW:ref - pd.Timedelta("1ms")]
    if w.empty:
        return pd.DataFrame()
    fw = forward_by_expiry(w, w["index_price"].iloc[-1])
    ms = lambda t: int(t.timestamp() * 1000)
    fut = pd.DataFrame(deribit("get_last_trades_by_currency_and_time", base=config.DERIBIT_HISTORY_BASE,
                               currency="BTC", kind="future", start_timestamp=ms(ref - FUT_WINDOW),
                               end_timestamp=ms(ref), count=1000, sorting="desc")["trades"])
    if fut.empty:
        return pd.DataFrame()
    fut = fut[fut["instrument_name"].str.match(r"^BTC-\d{1,2}[A-Z]{3}\d{2}$")].copy()
    fut["expiry"] = (pd.to_datetime(fut["instrument_name"].str.split("-").str[1], format="%d%b%y")
                     .dt.tz_localize("UTC") + pd.Timedelta(hours=8))
    fb = (fut["price"] / fut["index_price"]).groupby(fut["expiry"]).agg(["median", "size"])
    j = fw.join(fb.rename(columns={"median": "futures_basis", "size": "n_futures"}), how="inner")
    j["error_bps"] = (j["basis"] / j["futures_basis"] - 1) * 1e4
    j["day"] = ref
    j["days_to_expiry"] = (j.index - ref).total_seconds() / 86400
    return j.reset_index()


def summarise_forward_errors(v: pd.DataFrame) -> pd.DataFrame:
    v = v.assign(tenor=tenor_bucket(v["days_to_expiry"]))
    g = v.groupby("tenor", observed=True)["error_bps"]
    s = pd.DataFrame({"comparisons": g.size(), "days": v.groupby("tenor", observed=True)["day"].nunique(),
                      "median_abs_bps": g.apply(lambda e: e.abs().median()),
                      "p90_abs_bps": g.apply(lambda e: e.abs().quantile(0.9)),
                      "mean_bps": g.mean(), "median_bps": g.median()})
    # signed error per year of tenor: a discounting bias would show up as a slope
    x, y = v["days_to_expiry"] / 365, v["error_bps"]
    slope = np.polyfit(x, y, 1)[0]
    s.attrs["slope_bps_per_year"] = slope
    return s


# ── 2. Discounting test on live snapshots ───────────────────────────────────────────────────
def discount_test() -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "deribit_*.parquet"))):
        s = pd.read_parquet(f)
        t0 = s["fetched_at"].iloc[0]
        for expiry, g in s.groupby("expiry"):
            T = (expiry - t0).total_seconds() / YEAR_S
            F = g["forward_price"].iloc[0]
            if T <= 1 / 365 or not F > 0:
                continue
            for price_col in ("mark_price", "mid"):
                wide = g.pivot_table(index="strike", columns="option_type", values=price_col)
                if not {"call", "put"} <= set(wide.columns):
                    continue
                wide = wide.dropna()
                wide = wide[np.abs(np.log(wide.index / F)) < 0.3]          # near the money, both legs liquid
                if len(wide) < 4:
                    continue
                x = 1 - wide.index.to_numpy() / F
                y = (wide["call"] - wide["put"]).to_numpy()
                if np.abs(x).max() < 0.02:
                    continue
                df_hat = float((x @ y) / (x @ x))                            # OLS through the origin
                resid = y - df_hat * x
                rows.append({"snapshot": t0, "expiry": expiry, "days": T * 365, "prices": price_col,
                             "n_strikes": len(wide), "DF": df_hat, "DF_minus_1_bps": (df_hat - 1) * 1e4,
                             "implied_rate_%": -np.log(df_hat) / T * 100 if df_hat > 0 else np.nan,
                             "resid_rmse_btc": float(np.sqrt(np.mean(resid ** 2))),
                             "interest_rate_field": g["interest_rate"].iloc[0]})
    return pd.DataFrame(rows)


def summarise_discount(d: pd.DataFrame) -> pd.DataFrame:
    d = d.assign(tenor=tenor_bucket(d["days"]))
    return d.groupby(["prices", "tenor"], observed=True).agg(
        fits=("DF", "size"), median_days=("days", "median"), median_DF_minus_1_bps=("DF_minus_1_bps", "median"),
        p10_bps=("DF_minus_1_bps", lambda v: v.quantile(.1)), p90_bps=("DF_minus_1_bps", lambda v: v.quantile(.9)),
        median_implied_rate_pct=("implied_rate_%", "median"), interest_rate_field=("interest_rate_field", "median"))


# ── 3. Look-ahead audit ─────────────────────────────────────────────────────────────────────
def lookahead_audit(tasks) -> dict:
    """tasks = phase3_hist.month_tasks output: (origin, window_trades, s0, s_t)."""
    worst_after, worst_before, short_expiry, n = pd.Timedelta(-10**9, "s"), pd.Timedelta(0), 0, 0
    for origin, w, _, _ in tasks:
        if w.empty:
            continue
        n += 1
        worst_after = max(worst_after, w.index.max() - origin)        # must be < 0
        worst_before = max(worst_before, origin - w.index.min())      # must be <= 8h
        short_expiry += int((w["expiry"] <= origin + pd.Timedelta(days=1)).sum())
    return {"origins": n, "latest_trade_minus_origin": worst_after, "earliest_trade_before_origin": worst_before,
            "trades_with_expiry_within_1d": short_expiry}


# ── 5. Exploratory option strategies ────────────────────────────────────────────────────────
def snapshot_half_spread_vol(q: float = 0.9) -> tuple[float, pd.Series]:
    """Half bid-ask spread in vol points for options like the ones traded (20-45d, |delta| 0.15-0.35)."""
    out = []
    for f in sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "deribit_*.parquet"))):
        s = pd.read_parquet(f).dropna(subset=["bid", "ask"])
        t0 = s["fetched_at"].iloc[0]
        s["T"] = (s["expiry"] - t0).dt.total_seconds() / YEAR_S
        s = s[s["T"].between(STRAT_T_RANGE[0] / 365, STRAT_T_RANGE[1] / 365) & (s["bid"] > 0)]
        for _, r in s.iterrows():
            call = r["option_type"] == "call"
            F, K, T = r["forward_price"], r["strike"], r["T"]
            iv_m = r["mark_iv"] / 100
            d1 = (np.log(F / K) + iv_m**2 * T / 2) / (iv_m * np.sqrt(T))
            delta = norm.cdf(d1) if call else norm.cdf(d1) - 1
            if not 0.15 <= abs(delta) <= 0.35:
                continue
            ib = sm.implied_vol(r["bid"] * F, F, K, T, call)
            ia = sm.implied_vol(r["ask"] * F, F, K, T, call)
            if np.isfinite(ib) and np.isfinite(ia):
                out.append((ia - ib) / 2 * 100)
    hs = pd.Series(out, name="half_spread_vol_pts")
    return float(hs.quantile(q)), hs


def pick_legs(origin, w, s0):
    """Choose the ~30d expiry and 25-delta call/put from trades before 08:00 (prices come later)."""
    basis, _ = basis_by_expiry(w)
    days = pd.Series((basis.index - origin).total_seconds() / 86400, index=basis.index)
    ok = days[days.between(*STRAT_T_RANGE) & basis.notna()]
    if ok.empty:
        return None
    expiry = (ok - 30).abs().idxmin()
    T = ok[expiry] / 365
    F = basis[expiry] * s0
    g = w[w["expiry"] == expiry]
    per = g.groupby(["strike", "option_type"])["iv"].agg(iv="median", n="size").reset_index()
    per["iv"] /= 100
    per["d1"] = (np.log(F / per["strike"]) + per["iv"] ** 2 * T / 2) / (per["iv"] * np.sqrt(T))
    per["delta"] = np.where(per["option_type"] == "call", norm.cdf(per["d1"]), norm.cdf(per["d1"]) - 1)
    legs = {}
    for side, target in (("call", TARGET_DELTA), ("put", -TARGET_DELTA)):
        c = per[(per["option_type"] == side) & ((per["delta"] - target).abs() < 0.10)]
        if c.empty:
            return None
        r = c.loc[(c["delta"] - target).abs().idxmin()]
        legs[side] = {"strike": r["strike"], "iv_mid": r["iv"], "delta": r["delta"], "n_trades": int(r["n"])}
    return {"origin": origin, "expiry": expiry, "days": ok[expiry], "T": T, "F": F, "s0": s0, **{
        f"{side}_{k}": v for side, d in legs.items() for k, v in d.items()}}


def settle(trades: pd.DataFrame, delivery: pd.Series, half_spread_vol: float = HALF_SPREAD_VOL) -> pd.DataFrame:
    """Price each leg at 08:00 (buy the call at iv + h, sell the put at iv - h), then settle at delivery."""
    t = trades.copy()
    h = half_spread_vol / 100
    for side, sign in (("call", +1), ("put", -1)):
        call = side == "call"
        t[f"{side}_fair_usd"] = sm.black76(t["F"], t[f"{side}_strike"], t[f"{side}_iv_mid"] ** 2 * t["T"], call)
        iv_exec = np.maximum(t[f"{side}_iv_mid"] + sign * h, 0.01)
        t[f"{side}_price_usd"] = sm.black76(t["F"], t[f"{side}_strike"], iv_exec ** 2 * t["T"], call)
        t[f"{side}_fee_usd"] = np.minimum(FEE_RATE * t["s0"], FEE_CAP * t[f"{side}_price_usd"])
    t["s_T"] = delivery.reindex(t["expiry"]).to_numpy()
    t = t.dropna(subset=["s_T"])
    call_pay = np.maximum(t["s_T"] - t["call_strike"], 0)
    put_pay = np.maximum(t["put_strike"] - t["s_T"], 0)
    call_dfee = np.minimum(DELIVERY_FEE * t["s_T"], FEE_CAP * call_pay)
    put_dfee = np.minimum(DELIVERY_FEE * t["s_T"], FEE_CAP * put_pay)
    # long call: pay ask + fee, receive payoff - delivery fee
    t["call_pnl_usd"] = call_pay - call_dfee - t["call_price_usd"] - t["call_fee_usd"]
    t["call_pnl_fair_usd"] = call_pay - t["call_fair_usd"]
    # risk reversal: long call, short put (receive bid - fee, pay put payoff + delivery fee)
    t["rr_pnl_usd"] = t["call_pnl_usd"] + t["put_price_usd"] - t["put_fee_usd"] - put_pay - put_dfee
    t["rr_pnl_fair_usd"] = t["call_pnl_fair_usd"] + t["put_fair_usd"] - put_pay
    for c in ["call_pnl", "call_pnl_fair", "rr_pnl", "rr_pnl_fair"]:
        t[f"{c}_pct_s0"] = t[f"{c}_usd"] / t["s0"] * 100
    t["call_return_on_premium"] = t["call_pnl_usd"] / (t["call_price_usd"] + t["call_fee_usd"])
    return t


def boot_ci(x: np.ndarray, stat=np.mean, n=N_BOOT) -> tuple[float, float]:
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    s = np.array([stat(x[i]) for i in idx])
    return float(np.quantile(s, 0.025)), float(np.quantile(s, 0.975))


def summarise_strategy(t: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, col in [("long 25d call", "call_pnl_pct_s0"), ("long 25d call, no costs", "call_pnl_fair_pct_s0"),
                      ("25d risk reversal", "rr_pnl_pct_s0"), ("25d risk reversal, no costs", "rr_pnl_fair_pct_s0"),
                      ("long 25d call, return on premium", "call_return_on_premium")]:
        x = t[col].to_numpy()
        lo, hi = boot_ci(x)
        hlo, hhi = boot_ci((x > 0).astype(float))
        rows.append({"strategy": name, "trades": len(x), "mean": x.mean(), "mean_ci_lo": lo, "mean_ci_hi": hi,
                     "median": np.median(x), "hit_rate": (x > 0).mean(), "hit_ci_lo": hlo, "hit_ci_hi": hhi,
                     "total": x.sum(), "worst": x.min(), "best": x.max()})
    return pd.DataFrame(rows).set_index("strategy")


# ── 4. Tail breaches by year ────────────────────────────────────────────────────────────────
def block_boot_rate(flags: np.ndarray, block: int = 30, n: int = 5000) -> tuple[float, float]:
    """Moving-block bootstrap CI for the mean of an autocorrelated 0/1 series."""
    m = len(flags)
    if m < block:
        return np.nan, np.nan
    nb = int(np.ceil(m / block))
    starts = RNG.integers(0, m - block + 1, size=(n, nb))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n, -1)[:, :m]
    s = flags[idx].mean(axis=1)
    return float(np.quantile(s, .025)), float(np.quantile(s, .975))


def tails_by_year() -> pd.DataFrame:
    df = pd.read_parquet(config.PHASE3_DIR / "forecasts.parquet")
    year = df.index.year.astype(str)
    groups = {y: year == y for y in sorted(set(year))}
    groups["2022"] = year == "2022"
    groups["all except 2022"] = year != "2022"
    groups["all"] = np.ones(len(df), bool)
    rows = []
    for model in ("smile", "dvol", "rv"):
        pit = df[f"pit_{model}"].to_numpy()
        for tail, flag in (("below 5th pct", pit < 0.05), ("above 95th pct", pit > 0.95)):
            for gname, mask in groups.items():
                f = flag[mask].astype(float)
                lo, hi = block_boot_rate(f)
                rows.append({"model": model, "tail": tail, "period": gname, "days": int(mask.sum()),
                             "independent_windows": int(mask.sum()) // 30, "rate_%": f.mean() * 100,
                             "ci_lo_%": lo * 100, "ci_hi_%": hi * 100})
    return pd.DataFrame(rows)


# ── Run ─────────────────────────────────────────────────────────────────────────────────────
def trade_pass():
    """One pass over the monthly trade files: futures check, look-ahead audit, strategy entries."""
    delivery, _ = phase2.load_inputs()
    origins = pd.DataFrame({"s0": delivery, "s_t": delivery.reindex(delivery.index + phase2.HORIZON).to_numpy()})
    half_spread, hs = snapshot_half_spread_vol()
    log.info("Half-spread (vol pts) from %d snapshot quotes: median %.2f, p90 %.2f", len(hs), hs.median(), half_spread)
    first = origins.index[0]
    entry_days = set(pd.date_range(first, origins.index[-1], freq=f"{STRAT_EVERY}D"))
    fut_rows, audits, entries_all = [], [], []
    for f in sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet"))):
        tr, _ = clean(pd.read_parquet(f, columns=COLUMNS))
        tasks = month_tasks(f, origins)
        audits.append({"month": Path(f).stem, **lookahead_audit(tasks)})
        for origin, w, s0, _ in tasks:
            if w.empty:
                continue
            e = pick_legs(origin, w, s0)
            if e:
                e["on_30d_grid"] = origin in entry_days
                entries_all.append(e)
        days = tr.index.normalize().unique()
        for d in RNG.choice(days, size=min(FUT_DAYS_PER_MONTH, len(days)), replace=False):
            try:
                fut_rows.append(futures_check_day(tr, pd.Timestamp(d) + pd.Timedelta(hours=8)))
            except Exception:
                log.exception("futures check failed for %s", d)
        log.info("%s: %d origins audited", Path(f).stem, audits[-1]["origins"])
    return (pd.concat(fut_rows, ignore_index=True), pd.DataFrame(audits), pd.DataFrame(entries_all),
            half_spread, hs, delivery)


def main():
    config.setup_logging()
    fut, audit, entries, half_spread, hs, delivery = trade_pass()
    fut.to_csv(OUT / "forward_vs_futures.csv", index=False)
    fwd = summarise_forward_errors(fut)
    fwd.to_csv(OUT / "forward_error_by_tenor.csv")
    disc = discount_test()
    disc.to_csv(OUT / "discount_fits.csv", index=False)
    disc_s = summarise_discount(disc)
    disc_s.to_csv(OUT / "discount_by_tenor.csv")
    audit.to_csv(OUT / "lookahead_audit.csv", index=False)
    tails = tails_by_year()
    tails.to_csv(OUT / "tails_by_year.csv", index=False)

    trades_all = settle(entries, delivery)
    trades_all.to_csv(OUT / "strategy_trades_all_origins.csv", index=False)
    grid = trades_all[trades_all["on_30d_grid"]]
    strat = summarise_strategy(grid)
    strat.to_csv(OUT / "strategy_summary.csv")
    # every possible 30-day grid (start offsets 0..29): how much does the answer depend on the start day?
    off = ((trades_all["origin"] - trades_all["origin"].min()).dt.days % STRAT_EVERY)
    by_offset = trades_all.groupby(off).agg(trades=("call_pnl_pct_s0", "size"), call_mean=("call_pnl_pct_s0", "mean"),
                                            rr_mean=("rr_pnl_pct_s0", "mean"),
                                            call_hit=("call_pnl_pct_s0", lambda v: (v > 0).mean()),
                                            rr_hit=("rr_pnl_pct_s0", lambda v: (v > 0).mean()))
    by_offset.to_csv(OUT / "strategy_by_start_offset.csv")
    sens = pd.concat({f"{h:.2f}": summarise_strategy(settle(entries[entries["on_30d_grid"]], delivery, h))
                      .loc[["long 25d call", "25d risk reversal"], ["mean", "mean_ci_lo", "mean_ci_hi", "hit_rate"]]
                      for h in (0.0, half_spread, HALF_SPREAD_VOL, 2.0)}, names=["half_spread_vol"])
    sens.to_csv(OUT / "strategy_spread_sensitivity.csv")

    fmt = lambda t: t.to_string(float_format=lambda v: f"{v:.3f}")
    lines = [f"# Phase 3 robustness (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             "## 1. Parity forward vs Deribit futures, by tenor", "```", fmt(fwd), "```",
             f"Slope of signed error vs tenor: {fwd.attrs['slope_bps_per_year']:.2f} bp per year of tenor.", "",
             "## 2. Discounting test (c - p = DF (1 - K/F)) on live snapshots", "```", fmt(disc_s), "```", "",
             "## 3. Look-ahead audit (all months)", "```", audit.agg({
                 "origins": "sum", "latest_trade_minus_origin": "max", "earliest_trade_before_origin": "max",
                 "trades_with_expiry_within_1d": "sum"}).to_string(), "```", "",
             "## 4. Tail breaches by origin year (30-day block bootstrap 95% CI)", "```",
             tails.pivot_table(index=["tail", "period"], columns="model", values="rate_%").round(1).to_string(), "```", "",
             f"## 5. EXPLORATORY option test (every {STRAT_EVERY} days, half-spread {HALF_SPREAD_VOL:.2f} vol pts; "
             f"2026 snapshot quotes ({len(hs)}): median {hs.median():.2f}, p90 {half_spread:.2f})", "",
             "P&L in % of S0 per 1 BTC notional (return on premium for the last row).", "```", fmt(strat), "```", "",
             "Spread sensitivity (mean P&L % of S0 and hit rate):", "```", fmt(sens), "```", "",
             "Across the 30 possible start days:", "```", fmt(by_offset.describe().loc[["mean", "min", "max"]]), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Robustness done -> %s", OUT)


if __name__ == "__main__":
    main()
