"""
Markouts and adverse selection on Kalshi's 17:00 NY daily BTC markets (KXBTCD), from the sampled
trade history (src/pm_kalshi_trades.py, every 3rd settlement day).

Every trade has a resting order (the maker) on the other side:
  * taker sold YES into the bid (taker_side 'no')  -> a resting YES bid was filled: maker buys YES
  * taker bought YES at the ask (taker_side 'yes') -> a resting YES offer was filled: maker sells YES
Everything is in the MAKER's terms, s = +1 if the maker bought YES, -1 if it sold, in cents:
  effective half-spread  s (mid_before - price)          what the maker earns against the mid
  mid move after h min   s (mid_{t+h} - mid_before)       negative = adverse selection
  markout at h           s (mid_{t+h} - price)            = half-spread + mid move
  settlement markout     s (outcome - price)              the maker's P&L to settlement
Minute quotes are the 1-minute candle closes (stamped at the END of the minute): mid_before = the
quote at the start of the trade's minute, mid_{t+h} = the quote h to h+1 minutes after the trade.
Only trades whose pre-trade book is real (two-sided, spread <= 10c) are kept. Means are
contract-weighted; 95% CIs by event-cluster bootstrap. Price buckets are the MAKER's purchase
price (YES price if it bought YES, NO price = 1 - YES price if it sold YES), so "favourite" means
the maker bought the likely side.

Maker gap strategy net of adverse selection (src/pm_kalshi_gap_trade.py, maker variant, which
assumed fills at the quote): for each side and price bucket,
  AS = E[maker P&L to settlement | quote at 08:00] - E[maker P&L to settlement | actual fill
       between 08:00 UTC and the close],
both on the sampled days, i.e. how much worse a filled resting order does than a quote taken at a
random moment. This settlement-based AS is noisy (each sampled day settles once), so the PRIMARY
adjustment is the short-horizon one: AS_30m = -E[mid move 30 minutes after a fill], measured on the
same side, price bucket and period of fills between 08:00 UTC and the close. Net P&L = gross
gap-strategy P&L - AS (both versions reported). Fill probability is not modelled.
Outputs: reports/pm/kalshi_markout/. Run:  python -m src.pm_kalshi_markout
"""
import logging

import numpy as np
import pandas as pd

import config
from src import pm_kalshi_bias_time as bt
from src import pm_kalshi_calib as kc
from src import pm_kalshi_gap_trade as gt
from src import pm_kalshi_options as ko

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "pm" / "kalshi_markout"
OUT.mkdir(parents=True, exist_ok=True)
HORIZONS = (1, 5, 30)
MAKER_BUCKETS = np.array([0, .05, .10, .20, .30, .40, .50, .60, .70, .80, .90, .95, 1.0])
FAV_BUCKETS = np.array([.5, .6, .7, .8, .9, .95, 1.0])
RNG = np.random.default_rng(5)
N_BOOT = 1000


def wboot(df: pd.DataFrame, col: str, w: str = "count", cluster: str = "event") -> tuple[float, float, float]:
    """Contract-weighted mean of `col` with a 95% event-cluster bootstrap CI."""
    df = df.dropna(subset=[col])
    if df.empty:
        return np.nan, np.nan, np.nan
    codes, _ = pd.factorize(df[cluster])
    k = codes.max() + 1
    sw = np.bincount(codes, weights=df[col] * df[w], minlength=k)
    ww = np.bincount(codes, weights=df[w], minlength=k)
    est = sw.sum() / ww.sum()
    if k < 5:
        return est, np.nan, np.nan
    idx = RNG.integers(0, k, size=(N_BOOT, k))
    means = sw[idx].sum(1) / ww[idx].sum(1)
    return est, float(np.quantile(means, .025)), float(np.quantile(means, .975))


def with_mids(t: pd.DataFrame) -> pd.DataFrame:
    """Attach the mid before the trade and h minutes after, from the event's 1-minute quotes."""
    out = []
    for event, g in t.groupby("event"):
        q = pd.read_parquet(kc.FILLED / f"{event}.parquet", columns=["t", "ticker", "bid", "ask"])
        q["mid"] = np.where((q["ask"] - q["bid"] <= kc.MAX_SPREAD + 1e-9) & (q["ask"] > q["bid"]), (q["bid"] + q["ask"]) / 2, np.nan)
        q = q.set_index(["ticker", "t"])["mid"]
        m0 = g["created_time"].dt.floor("min")
        key = lambda ts: pd.MultiIndex.from_arrays([g["ticker"], ts])
        g = g.assign(mid_before=q.reindex(key(m0)).to_numpy())
        for h in HORIZONS:
            g[f"mid_{h}m"] = q.reindex(key(m0 + pd.Timedelta(minutes=h + 1))).to_numpy()
        out.append(g)
    return pd.concat(out, ignore_index=True)


def maker_terms(t: pd.DataFrame) -> pd.DataFrame:
    cat = pd.read_parquet(kc.CATALOG, columns=["ticker", "outcome", "close_time"]).set_index("ticker")
    t = t.join(cat, on="ticker")
    t["s"] = np.where(t["taker_side"] == "no", 1.0, -1.0)             # +1: resting bid filled, maker bought YES
    t["fill"] = np.where(t["s"] > 0, "resting bid filled (taker sold YES)", "resting offer filled (taker bought YES)")
    t["maker_price"] = np.where(t["s"] > 0, t["yes_price"], 1 - t["yes_price"])
    t["half_spread_c"] = t["s"] * (t["mid_before"] - t["yes_price"]) * 100
    for h in HORIZONS:
        t[f"move_{h}m_c"] = t["s"] * (t[f"mid_{h}m"] - t["mid_before"]) * 100
        t[f"markout_{h}m_c"] = t["s"] * (t[f"mid_{h}m"] - t["yes_price"]) * 100
    t["settle_markout_c"] = t["s"] * (t["outcome"] - t["yes_price"]) * 100
    t["year"] = t["settle"].dt.year
    t["bucket"] = pd.cut(t["maker_price"], MAKER_BUCKETS, include_lowest=True).astype(str)
    return t


def markout_table(t: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    cols = ["half_spread_c"] + [f"move_{h}m_c" for h in HORIZONS] + [f"markout_{h}m_c" for h in HORIZONS] + ["settle_markout_c"]
    rows = []
    for key, g in t.groupby(by):
        r = dict(zip(by, key if isinstance(key, tuple) else (key,)))
        r.update({"trades": len(g), "contracts": g["count"].sum(), "events": g["event"].nunique()})
        for c in cols:
            est, lo, hi = wboot(g, c)
            r[c] = est
            if c in ("move_5m_c", "settle_markout_c"):
                r[f"{c}_ci"] = f"[{lo:.2f}, {hi:.2f}]"
        rows.append(r)
    return pd.DataFrame(rows)


def representativeness(t: pd.DataFrame) -> pd.DataFrame:
    act = pd.read_csv(bt.OUT / "monthly_activity_spread_flow.csv", index_col=0) if (bt.OUT / "monthly_activity_spread_flow.csv").exists() else None
    cat = pd.read_parquet(kc.CATALOG, columns=["event", "settle"])
    cat = cat[cat["event"].str.startswith("KXBTCD") & cat["event"].str.endswith("17")].groupby("event")["settle"].first()
    sampled = set(t["event"])
    rows = []
    for year, s in cat.groupby(cat.dt.year):
        smp = s[s.index.isin(sampled)]
        rows.append({"year": year, "events": len(s), "sampled": len(smp), "share": len(smp) / len(s),
                     "weekend share, all": (s.dt.tz_convert("America/New_York").dt.dayofweek >= 5).mean(),
                     "weekend share, sampled": (smp.dt.tz_convert("America/New_York").dt.dayofweek >= 5).mean(),
                     "sampled contracts (M)": t.loc[t["year"] == year, "count"].sum() / 1e6,
                     "all 17:00 contracts (M)": act.loc[act.index.str.startswith(str(year)), "volume_17ny"].sum() / 1e6 if act is not None else np.nan})
    r = pd.DataFrame(rows)
    r["sampled volume share"] = r["sampled contracts (M)"] / r["all 17:00 contracts (M)"]
    return r


def maker_net(t: pd.DataFrame) -> pd.DataFrame:
    """Gap-strategy maker P&L net of the adverse selection measured on actual fills."""
    q = pd.read_parquet(ko.OUT / "quotes_with_q.parquet")
    sampled = set(t["event"])
    # fills while a 08:00 resting order would be live: 08:00 UTC on the settlement day to the close
    live = t[(t["created_time"] >= t["settle"].dt.normalize() + pd.Timedelta(hours=8)) & (t["created_time"] < t["close_time"])]
    rows = []
    for T in gt.THRESHOLDS:
        g = gt.trades(q, "q", T, "maker")
        for (period, side), gs in g.groupby(["period", "side"]):
            gs = gs.assign(fb=pd.cut(gs["price"], FAV_BUCKETS, include_lowest=True).astype(str))
            for fb, gb in gs.groupby("fb"):
                if len(gb) < 20:
                    continue
                lo_, hi_ = map(float, fb.strip("([]").split(", "))
                # same side: a YES buy at the bid = resting bid filled; a NO buy at 1 - ask = resting offer filled
                s = 1.0 if side == "YES" else -1.0
                yrs = range(2024, 2026) if period == "pre-2026" else [2026]
                f = live[(live["s"] == s) & live["maker_price"].between(lo_, hi_, inclusive="right") & live["year"].isin(yrs)]
                qq = q[q["event"].isin(sampled) & q["usable"] & (q["period"] == period)]
                qp = qq["bid"] if side == "YES" else 1 - qq["ask"]
                qq = qq.assign(mp=qp, pnl=np.where(side == "YES", qq["outcome"] - qq["bid"], (1 - qq["outcome"]) - (1 - qq["ask"])) * 100)
                qq = qq[qq["mp"].between(lo_, hi_, inclusive="right")].assign(count=1.0)
                fill_m, fl, fh = wboot(f, "settle_markout_c")
                mv, ml, mh = wboot(f, "move_30m_c")
                as30, as30_se = -mv, (mh - ml) / 3.92
                quote_m, ql, qh = wboot(qq, "pnl")
                gross = gb["pnl"].mean() * 100
                glo, ghi = kc.cluster_boot(gb.assign(pc=gb["pnl"] * 100), "pc")
                AS = quote_m - fill_m
                se = np.sqrt(((ghi - glo) / 3.92) ** 2 + ((fh - fl) / 3.92) ** 2 + ((qh - ql) / 3.92) ** 2)
                gse = (ghi - glo) / 3.92
                rows.append({"T_c": T * 100, "period": period, "side": side, "maker_price_bucket": fb, "gap_trades": len(gb),
                             "gross_pnl_c": gross, "fills_measured": len(f), "fill_contracts": f["count"].sum(),
                             "AS_30m_c": as30, "net_pnl_30m_c": gross - as30,
                             "net_30m_ci_lo": gross - as30 - 1.96 * np.hypot(gse, as30_se),
                             "net_30m_ci_hi": gross - as30 + 1.96 * np.hypot(gse, as30_se),
                             "pnl_at_quote_c": quote_m, "pnl_at_fill_c": fill_m, "AS_settlement_c": AS,
                             "net_pnl_settlement_c": gross - AS, "net_settle_ci_lo": gross - AS - 1.96 * se,
                             "net_settle_ci_hi": gross - AS + 1.96 * se})
    r = pd.DataFrame(rows)
    # trade-weighted totals per threshold, period and side
    tot = []
    for (T, period, side), g in r.groupby(["T_c", "period", "side"]):
        w = g["gap_trades"]
        tot.append({"T_c": T, "period": period, "side": side, "gap_trades": w.sum(),
                     "gross_pnl_c": np.average(g["gross_pnl_c"], weights=w),
                     "AS_30m_c": np.average(g["AS_30m_c"], weights=w), "net_pnl_30m_c": np.average(g["net_pnl_30m_c"], weights=w),
                     "AS_settlement_c": np.average(g["AS_settlement_c"], weights=w),
                     "net_pnl_settlement_c": np.average(g["net_pnl_settlement_c"], weights=w)})
    return r, pd.DataFrame(tot)


def fill_simulation(t: pd.DataFrame) -> pd.DataFrame:
    """Maker gap signals at 08:00 on the SAMPLED days, filled only if the trade history shows a
    taker trading against that price after 08:00 and before the close:
      touch:   any taker sale at YES price <= our bid (YES side) / taker purchase at >= our ask (NO side)
               (optimistic: ignores queue position)
      through: a taker trade strictly beyond our price, which fills even the back of the queue.
    Unfilled signals earn 0. This captures the fill selection the quote-based maker P&L ignores."""
    q = pd.read_parquet(ko.OUT / "quotes_with_q.parquet")
    q = q[q["event"].isin(set(t["event"]))]
    live = t[(t["created_time"] >= t["settle"].dt.normalize() + pd.Timedelta(hours=8)) & (t["created_time"] < t["close_time"])]
    sells = live[live["taker_side"] == "no"].groupby("ticker")["yes_price"].agg(["min"])        # lowest YES price sold into
    buys = live[live["taker_side"] == "yes"].groupby("ticker")["yes_price"].agg(["max"])        # highest YES price bought
    rows = []
    for T in gt.THRESHOLDS:
        g = gt.trades(q, "q", T, "maker")
        lo_sold = g["ticker"].map(sells["min"])
        hi_bought = g["ticker"].map(buys["max"])
        yes = g["side"] == "YES"
        touch = np.where(yes, lo_sold <= g["bid"] + 1e-9, hi_bought >= g["ask"] - 1e-9)
        through = np.where(yes, lo_sold < g["bid"] - 1e-9, hi_bought > g["ask"] + 1e-9)
        for rule, filled in (("assume always filled", np.ones(len(g), bool)), ("touch", touch), ("through", through)):
            x = g.assign(filled=filled.astype(float), pnl_c=np.where(filled, g["pnl"] * 100, 0.0))
            for (period, side), s in [((p, "both"), s) for p, s in x.groupby("period")] + list(x.groupby(["period", "side"])):
                lo, hi = kc.cluster_boot(s, "pnl_c")
                f = s[s["filled"] > 0]
                rows.append({"T_c": T * 100, "fill_rule": rule, "period": period, "side": side, "signals": len(s),
                             "days": s["day"].nunique(), "fill_rate": s["filled"].mean(),
                             "pnl_per_signal_c": s["pnl_c"].mean(), "ci_lo": lo, "ci_hi": hi,
                             "pnl_per_filled_contract_c": f["pnl"].mean() * 100 if len(f) else np.nan,
                             "hit_rate_filled": (f["pnl"] > 0).mean() if len(f) else np.nan})
    return pd.DataFrame(rows)


def main():
    config.setup_logging()
    t = bt.load_trades()
    t = maker_terms(with_mids(t))
    n0 = len(t)
    t = t[t["mid_before"].notna()]
    log.info("trades %d, with a real pre-trade book %d (%.0f%%)", n0, len(t), 100 * len(t) / n0)
    rep = representativeness(t)
    by_year = markout_table(t, ["fill", "year"])
    by_bucket = markout_table(t, ["fill", "bucket"])
    by_both = markout_table(t, ["fill", "year", "bucket"])
    detail, totals = maker_net(t)
    fills = fill_simulation(t)
    for name, x in (("representativeness", rep), ("markout_by_year", by_year), ("markout_by_bucket", by_bucket),
                    ("markout_by_year_bucket", by_both), ("maker_net_detail", detail), ("maker_net_totals", totals), ("maker_fill_simulation", fills)):
        x.to_csv(OUT / f"{name}.csv", index=False)
    fmt = lambda x: x.to_string(index=False, float_format=lambda v: f"{v:.3f}")
    lines = [f"# Kalshi markouts and adverse selection, 17:00 NY daily markets (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"Sampled trade history (every 3rd settlement day). Trades {n0}, kept {len(t)} with a real pre-trade book "
             f"(two-sided, spread <= {kc.MAX_SPREAD * 100:.0f}c). All numbers in the MAKER's terms, cents per contract, "
             "contract-weighted; CIs = 95% event-cluster bootstrap. Bucket = the maker's purchase price.", "",
             "## Representativeness of the sampled events", "```", fmt(rep), "```",
             "## Markouts by year", "```", fmt(by_year), "```",
             "## Markouts by maker price bucket (all years)", "```", fmt(by_bucket), "```",
             "## Maker gap strategy with fills simulated from the trade history (sampled days; unfilled = 0)", "```", fmt(fills), "```",
             "## Maker gap strategy net of measured adverse selection (trade-weighted totals)", "```", fmt(totals), "```",
             "### Detail by maker price bucket", "```", fmt(detail), "```",
             "## Markouts by year and bucket", "```", fmt(by_both), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Markout analysis done -> %s", OUT)


if __name__ == "__main__":
    main()
