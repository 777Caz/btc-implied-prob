"""
Kalshi vs options at 08:00 UTC, for 17:00 New York daily above-K markets (KXBTCD).

For every usable Kalshi quote at 08:00 UTC (two-sided, spread <= 10c; src/pm_kalshi_calib.py) the
option-implied q = P(S > K) comes from the 08:00 UTC front smile (SVI, centre m constrained) scaled
to 17:00 NY with variance time and the event-day profile, alpha = 0.5 (src/short_horizon.py, the
"vartime+events, a=0.5" variant), with no look-ahead: trades before 08:00, profiles from the
trailing year, event excess from earlier events.

Forward and basis. The smile is fitted in log-moneyness to the Deribit index forward. Kalshi settles
on CF Benchmarks' BRTI (60-second average before 17:00 NY), so the forward is multiplied by the
BRTI / Deribit-index ratio: measured each day at settlement as Kalshi's expiration value over the
median index_price of Deribit option trades in [16:58, 17:01] NY, and applied as the median of the
previous 30 measured days (no look-ahead). q with no basis adjustment is kept for comparison.

Outputs (reports/pm/kalshi_vs_options/):
  a) mid - q overall and by price bucket (cluster-bootstrap CIs), chart of mid vs q
  b) calibration of q on the same contracts: logit slope b_q, Brier
  c) encompassing: P(YES) = sigmoid(a + b1 logit(mid) + b2 logit(q)), SEs clustered by event
  d) Brier of mid, q and the 50/50 blend, with paired differences
Run:  python -m src.pm_kalshi_options
"""
import glob
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from src import intraday_vol as iv
from src import pm_kalshi_calib as kc
from src import short_horizon as sh
from src.clean_trades import COLUMNS, clean
from src.pm_kalshi_robust import logistic_multi

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "pm" / "kalshi_vs_options"
OUT.mkdir(parents=True, exist_ok=True)
NY = "America/New_York"
BASIS_WINDOW = (-2, 1)          # minutes around 17:00 NY for Deribit index_price at settlement
BASIS_LOOKBACK = 30             # previous measured days in the trailing median
BUCKETS = np.array([0, .05, .10, .20, .30, .40, .50, .60, .70, .80, .90, .95, 1.0])


def kalshi_quotes() -> pd.DataFrame:
    d = pd.read_parquet(kc.OUT / "quotes_at_leads.parquet")
    d = d[d["usable"] & (d["lead"] == kc.AT_0800) & (d["event_hour"] == "17:00 NY")].copy()
    d["mid"] = (d["bid"] + d["ask"]) / 2
    ev = pd.read_parquet(kc.CATALOG, columns=["event", "expiration_value"]).groupby("event")["expiration_value"].first()
    d["brti_settle"] = d["event"].map(ev)
    return d


def variance_models():
    d = iv.load_returns(1)
    events = sh.load_events()
    ev_by_day = {}
    for _, e in events.iterrows():
        ev_by_day.setdefault(e["date_utc"], []).append((e["event"], e["release"]))
    months = pd.date_range(pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp.now(tz="UTC").normalize(), freq="MS")
    models = {m: sh.VarianceModel(d, events, m, {}) for m in months}
    excess = sh.event_excess(d, events, models)
    models = {m: sh.VarianceModel(d, events, m, excess) for m in months}
    return models, ev_by_day


def option_q(quotes: pd.DataFrame) -> pd.DataFrame:
    models, ev_by_day = variance_models()
    days = quotes.groupby("event").agg(settle=("settle", "first"), brti=("brti_settle", "first"))
    days["origin"] = days["settle"].dt.normalize() + pd.Timedelta(hours=8)
    by_origin = days.reset_index().set_index("origin").sort_index()
    rows, ratios = [], []                                             # ratios: (settle, BRTI / Deribit index)
    months = sorted({o.strftime("%Y-%m") for o in by_origin.index})
    for mth in months:
        f = config.OPTION_TRADES_DIR / f"{mth}.parquet"
        if not f.exists():
            log.warning("no option trades for %s", mth)
            continue
        t, _ = clean(pd.read_parquet(f, columns=COLUMNS))
        for origin, e in by_origin[by_origin.index.strftime("%Y-%m") == mth].iterrows():
            s = e["settle"]
            win = t.loc[s + pd.Timedelta(minutes=BASIS_WINDOW[0]): s + pd.Timedelta(minutes=BASIS_WINDOW[1])]
            past = [r for when, r in ratios if when < origin][-BASIS_LOOKBACK:]
            b_brti = float(np.median(past)) if len(past) >= 10 else np.nan
            if len(win) and np.isfinite(e["brti"]):
                ratios.append((s, e["brti"] / win["index_price"].median()))
            row = {"event": e["event"], "origin": origin, "settle": s, "basis_brti_trailing": b_brti,
                   "basis_brti_today": ratios[-1][1] if ratios and ratios[-1][0] == s else np.nan}
            model = models.get(sh.month_key(origin))
            inp = sh.day_inputs(t, origin) if model is not None and model.ok else None
            if inp is None or inp["front"] is None:
                rows.append({**row, "status": "no front fit"})
                continue
            T1 = inp["front_expiry"]
            if s >= T1:
                rows.append({**row, "status": "settle after front expiry"})
                continue
            lam = sh.tau(model, origin, s, ev_by_day, True) / sh.tau(model, origin, T1, ev_by_day, True)
            out = {**row, "status": "ok", "front_days": (T1 - origin).total_seconds() / 86400, "lambda": lam,
                   "idx_ref": inp["idx_ref"], "front_rmse_vol_pts": inp["front"]["rmse_vol_pts"]}
            for name, b0 in (("q_raw", 1.0), ("q", b_brti if np.isfinite(b_brti) else 1.0)):
                dist, gmin, cal = sh.forecast(inp["front"], T1, origin, s, lam, 0.5, inp["idx_ref"], b0)
                out[f"dist_{name}"] = dist
                out.update({"butterfly_min_g": gmin, "calendar_max_excess": cal, f"F_{name}": dist.forward})
            rows.append(out)
        log.info("%s done (%d days)", mth, len(rows))
    return pd.DataFrame(rows)


def attach_q(quotes: pd.DataFrame, days: pd.DataFrame) -> pd.DataFrame:
    ok = days[days["status"] == "ok"].set_index("event")
    q = quotes[quotes["event"].isin(ok.index)].copy()
    for name in ("q", "q_raw"):
        q[name] = [ok.at[e, f"dist_{name}"].p_above(k) for e, k in zip(q["event"], q["strike"])]
        q[name] = q[name].clip(0, 1)
    return q


# ── Analysis ────────────────────────────────────────────────────────────────────────────────
def periods(g):
    for period in ("pre-2026", "2026", "all"):
        yield period, (g if period == "all" else g[g["period"] == period])


def diff_table(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, s in periods(q):
        for bucket, g in [("all", s)] + list(s.groupby(pd.cut(s["mid"], BUCKETS, include_lowest=True), observed=True)):
            dlt = (g["mid"] - g["q"]) * 100
            lo, hi = kc.cluster_boot(g.assign(dc=dlt), "dc")
            rows.append({"period": period, "mid_bucket": str(bucket), **kc.n_info(g), "mean_mid": g["mid"].mean(),
                         "mean_q": g["q"].mean(), "observed": g["outcome"].mean(), "mid_minus_q_c": dlt.mean(),
                         "ci_lo": lo, "ci_hi": hi, "median_c": dlt.median(), "p10_c": dlt.quantile(.1),
                         "p90_c": dlt.quantile(.9), "mean_abs_c": dlt.abs().mean(),
                         "mean_raw_basis_c": ((g["mid"] - g["q_raw"]) * 100).mean()})
    return pd.DataFrame(rows)


def calib_table(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, s in periods(q):
        y, ev = s["outcome"].to_numpy(float), s["event"].to_numpy()
        for name in ("mid", "q"):
            f = kc.logistic_cluster(y, kc.logit(s[name].to_numpy()), ev)
            rows.append({"period": period, "price": name, **kc.n_info(s), "a": f["a"], "a_se": f["a_se"],
                         "b": f["b"], "b_se": f["b_se"], "z_b=1": f["z_b=1"]})
    return pd.DataFrame(rows)


def encompassing(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, s in periods(q):
        X = np.column_stack([kc.logit(s["mid"].to_numpy()), kc.logit(s["q"].to_numpy())])
        beta, se = logistic_multi(s["outcome"].to_numpy(float), X, s["event"].to_numpy())
        rows.append({"period": period, **kc.n_info(s), "a": beta[0], "a_se": se[0], "b1_kalshi": beta[1], "b1_se": se[1],
                     "z_b1": beta[1] / se[1], "b2_options": beta[2], "b2_se": se[2], "z_b2": beta[2] / se[2],
                     "corr_logits": np.corrcoef(X.T)[0, 1]})
    return pd.DataFrame(rows)


def brier_table(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    q = q.assign(blend=(q["mid"] + q["q"]) / 2)
    for period, s in periods(q):
        y = s["outcome"]
        r = {"period": period, **kc.n_info(s)}
        for name in ("mid", "q", "q_raw", "blend"):
            r[f"brier_{name}"] = ((s[name] - y) ** 2).mean()
        for a, b in (("q", "mid"), ("blend", "mid"), ("blend", "q")):
            lo, hi = kc.cluster_boot(s, lambda x: (x[a] - x["outcome"]) ** 2 - (x[b] - x["outcome"]) ** 2)
            r[f"{a}-{b}"], r[f"{a}-{b}_ci"] = ((s[a] - y) ** 2 - (s[b] - y) ** 2).mean(), f"[{lo:.4f}, {hi:.4f}]"
        rows.append(r)
    return pd.DataFrame(rows)


def chart(q: pd.DataFrame, dt: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    ax = axes[0]
    for period, c in (("pre-2026", "#2a78b5"), ("2026", "#d1572c")):
        s = q[q["period"] == period]
        ax.scatter(s["q"], s["mid"], s=4, alpha=.25, color=c, label=f"{period} ({s['day'].nunique()} days)", rasterized=True)
    ax.plot([0, 1], [0, 1], color="#555", lw=1)
    ax.set(xlabel="option-implied q = P(S > K)", ylabel="Kalshi mid", title="Kalshi mid vs option q, 08:00 UTC, 17:00 NY markets")
    ax.legend(loc="upper left", frameon=False)
    ax = axes[1]
    for period, c in (("pre-2026", "#2a78b5"), ("2026", "#d1572c")):
        s = dt[(dt["period"] == period) & (dt["mid_bucket"] != "all")]
        ax.errorbar(s["mean_mid"], s["mid_minus_q_c"], yerr=[s["mid_minus_q_c"] - s["ci_lo"], s["ci_hi"] - s["mid_minus_q_c"]],
                    fmt="o-", ms=4, lw=1.5, color=c, label=period, capsize=2)
    ax.axhline(0, color="#555", lw=1)
    ax.set(xlabel="Kalshi mid (bucket mean)", ylabel="mid - q (cents)", title="Mean mid - q by price bucket (95% CI, clustered by day)")
    ax.legend(frameon=False)
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "kalshi_vs_options.png", dpi=150)
    plt.close(fig)


def main():
    config.setup_logging()
    quotes = kalshi_quotes()
    days = option_q(quotes)
    keep = [c for c in days.columns if not c.startswith("dist_")]
    days[keep].to_csv(OUT / "days.csv", index=False)
    q = attach_q(quotes, days)
    q.drop(columns=[]).to_parquet(OUT / "quotes_with_q.parquet")
    ratio = days["basis_brti_today"].dropna()
    basis = pd.DataFrame({"BRTI / Deribit index - 1 (bp)": (ratio - 1) * 1e4}).describe(percentiles=[.05, .25, .5, .75, .95]).T
    status = days["status"].value_counts()
    ok = days[days["status"] == "ok"]
    dt, cb, en, br = diff_table(q), calib_table(q), encompassing(q), brier_table(q)
    for name, t in (("mid_minus_q", dt), ("calibration_mid_vs_q", cb), ("encompassing", en), ("brier", br)):
        t.to_csv(OUT / f"{name}.csv", index=False)
    chart(q, dt)
    fmt = lambda t, idx=False: t.to_string(index=idx, float_format=lambda v: f"{v:.4f}")
    lines = [f"# Kalshi vs options, 08:00 UTC quotes on 17:00 NY daily markets (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"Contracts {len(q)}, settlement days {q['day'].nunique()} ({q['settle'].min():%Y-%m-%d} to {q['settle'].max():%Y-%m-%d}); "
             f"day status {status.to_dict()}. `days` = effective N.",
             f"Front smile: median {ok['front_days'].median():.2f} days to expiry, median fit RMSE {ok['front_rmse_vol_pts'].median():.2f} vol pts; "
             f"lambda median {ok['lambda'].median():.3f}; butterfly violations {(ok['butterfly_min_g'] < -1e-4).sum()}, "
             f"calendar violations {(ok['calendar_max_excess'] > 1e-6).sum()}.", "",
             "## Basis: BRTI settlement / Deribit index at 17:00 NY (applied as a trailing 30-day median)", "```", fmt(basis, True), "```",
             "## a) Kalshi mid - option q (cents; positive = Kalshi above options), CI clustered by day", "```", fmt(dt), "```",
             "## b) Calibration on the same contracts: P(YES) = sigmoid(a + b logit(price))", "```", fmt(cb), "```",
             "## c) Encompassing: P(YES) = sigmoid(a + b1 logit(mid) + b2 logit(q)), SEs clustered by event", "```", fmt(en), "```",
             "## d) Brier: mid, q, q without basis adjustment, 50/50 blend; paired differences (negative = first is better)", "```",
             fmt(br.T, True), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Kalshi vs options done -> %s", OUT)


if __name__ == "__main__":
    main()
