"""
Does the Kalshi favourite-longshot bias track market growth? Monthly bias measures for the 17:00 NY
daily above-K markets (KXBTCD) against monthly Kalshi BTC volume and open interest.

Bias measures (usable quotes: two-sided, spread <= 10c):
  * logit slope b of P(YES) = sigmoid(a + b logit(mid)), per month, at 08:00 UTC, 8h and 1h,
    SEs clustered by event; months with fewer than 10 events are skipped;
  * flatness gap vs options at 08:00 UTC: mean(mid - q) on mids < 30c minus mean(mid - q) on
    mids > 70c, in cents (src/pm_kalshi_options.py); positive = Kalshi flatter than options.
Activity: total contracts traded per month in the backfilled KXBTCD markets (12:00 NY hourly + 17:00 NY daily) and in the
17:00 NY daily markets, and open interest at 08:00 UTC summed over a 17:00 event's strikes
(monthly mean), from the 1-minute history.
Association: Spearman correlation across months and an OLS of the bias on log volume with a
linear time trend (months are few and both series trend, so this is descriptive).
Outputs: reports/pm/kalshi_bias_time/. Run:  python -m src.pm_kalshi_bias_time
"""
import glob
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import config
from src import pm_kalshi_calib as kc
from src import pm_kalshi_options as ko

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "pm" / "kalshi_bias_time"
OUT.mkdir(parents=True, exist_ok=True)
NY = "America/New_York"


def activity() -> pd.DataFrame:
    vol_all, vol_17, oi = [], [], []
    for f in sorted(glob.glob(str(kc.FILLED / "*.parquet"))):
        x = pd.read_parquet(f, columns=["t", "volume", "open_interest"])
        if x.empty:
            continue
        event = f.replace("\\", "/").rsplit("/", 1)[-1][:-8]
        key = x["t"].dt.year * 100 + x["t"].dt.month                         # numeric month key (strftime is slow)
        m = x.groupby(key)["volume"].sum()
        m.index = [f"{k // 100}-{k % 100:02d}" for k in m.index]
        vol_all.append(m)
        if event.endswith("17"):
            vol_17.append(m)
            close = x["t"].max()
            at8 = x[x["t"] == close.normalize() + pd.Timedelta(hours=8)]
            if len(at8):
                oi.append((close.strftime("%Y-%m"), float(at8["open_interest"].sum())))
    a = pd.DataFrame({"volume_12_17ny": pd.concat(vol_all).groupby(level=0).sum(),
                      "volume_17ny": pd.concat(vol_17).groupby(level=0).sum()})
    a["oi_0800_per_17ny_event"] = pd.DataFrame(oi, columns=["month", "oi"]).groupby("month")["oi"].mean()
    return a


def monthly_bias() -> pd.DataFrame:
    d = pd.read_parquet(kc.OUT / "quotes_at_leads.parquet")
    d = d[d["usable"] & (d["event_hour"] == "17:00 NY")].copy()
    d["mid"] = (d["bid"] + d["ask"]) / 2
    d["month"] = d["settle"].dt.tz_convert(NY).dt.strftime("%Y-%m")
    rows = []
    for (lead, month), g in d.groupby(["lead", "month"]):
        if lead == "24h" or g["event"].nunique() < 10:
            continue
        f = kc.logistic_cluster(g["outcome"].to_numpy(float), kc.logit(g["mid"].to_numpy()), g["event"].to_numpy())
        rows.append({"month": month, "measure": f"b, {lead}", "value": f["b"], "se": f["b_se"], "days": g["day"].nunique()})
    q = pd.read_parquet(ko.OUT / "quotes_with_q.parquet")
    q = q[q["usable"] & q["q"].notna()].copy()
    q["month"] = q["settle"].dt.tz_convert(NY).dt.strftime("%Y-%m")
    q["gap_c"] = (q["mid"] - q["q"]) * 100
    for month, g in q.groupby("month"):
        lo_, hi_ = g[g["mid"] < .3], g[g["mid"] > .7]
        if g["event"].nunique() < 10 or lo_.empty or hi_.empty:
            continue
        per_day = pd.DataFrame({"lo": lo_.groupby("day")["gap_c"].mean(), "hi": hi_.groupby("day")["gap_c"].mean()}).dropna()
        flat = per_day["lo"] - per_day["hi"]
        rows.append({"month": month, "measure": "flatness gap vs q, 08:00 (c)", "value": flat.mean(),
                     "se": flat.std(ddof=1) / np.sqrt(len(flat)), "days": len(flat)})
    return pd.DataFrame(rows)




# ── Spreads, taker flow, market-maker dates ─────────────────────────────────────────────────
TRADES = config.DATA_RAW / "pm_history" / "kalshi" / "trades" / "KXBTCD"
CHEAP, DEAR = 0.30, 0.70
LS = "taker longshot share (YES<30c or NO when YES>70c)"
# Public dates (Kalshi press release, news). No public start date exists for the designated
# liquidity provider on "Crypto Hourly & Daily" (help.kalshi.com lists 1 provider, no dates).
MM_EVENTS = {"2024-04-03": "SIG onboarded (first institutional MM, all markets)",
             "2026-05-29": "Wintermute confirms quoting Kalshi event contracts"}


def monthly_spreads() -> pd.DataFrame:
    d = pd.read_parquet(kc.OUT / "quotes_at_leads.parquet")
    d = d[d["two_sided"] & (d["event_hour"] == "17:00 NY") & d["lead"].isin([kc.AT_0800, "1h"])].copy()
    d["month"] = d["settle"].dt.tz_convert(NY).dt.strftime("%Y-%m")
    d["spread_c"] = (d["ask"] - d["bid"]) * 100
    near = d[((d["bid"] + d["ask"]) / 2).between(.10, .90)]                      # spreads away from the price floor
    out = d.groupby(["month", "lead"])["spread_c"].median().unstack("lead").add_prefix("median_spread_c, ")
    out = out.join(near.groupby(["month", "lead"])["spread_c"].median().unstack("lead").add_prefix("median_spread_c 10-90c, "))
    return out


def load_trades() -> pd.DataFrame:
    cat = pd.read_parquet(kc.CATALOG, columns=["event", "settle"]).groupby("event")["settle"].first()
    parts = []
    for f in sorted(glob.glob(str(TRADES / "*.parquet"))):
        t = pd.read_parquet(f)
        if t.empty:
            continue
        ev = f.replace("\\", "/").rsplit("/", 1)[-1][:-8]
        parts.append(t.assign(event=ev, settle=cat.get(ev)))
    t = pd.concat(parts, ignore_index=True)
    t = t[~t["is_block_trade"]].copy()
    t["bucket"] = np.select([t["yes_price"] < CHEAP, t["yes_price"] > DEAR], ["YES < 30c", "YES > 70c"], "YES 30-70c")
    t["taker_yes"] = (t["taker_side"] == "yes").astype(float)
    # buying the longshot: YES when YES is cheap, NO when YES is dear (NO is then cheap)
    t["longshot_buy"] = np.where(t["bucket"] == "YES < 30c", t["taker_yes"],
                                 np.where(t["bucket"] == "YES > 70c", 1 - t["taker_yes"], np.nan))
    t["month"] = t["settle"].dt.tz_convert(NY).dt.strftime("%Y-%m")
    t["day"] = t["settle"].dt.tz_convert(NY).dt.date.astype(str)
    t["before_0800"] = t["created_time"] < t["settle"].dt.normalize() + pd.Timedelta(hours=8)
    return t


def wshare(t: pd.DataFrame, col: str, by) -> pd.Series:
    """Contract-weighted mean of a 0/1 column by group."""
    w = t[col] * t["count"]
    return w.groupby([t[b] for b in by] if isinstance(by, list) else t[by]).sum() / t["count"].groupby(
        [t[b] for b in by] if isinstance(by, list) else t[by]).sum()


def monthly_flow(t: pd.DataFrame) -> pd.DataFrame:
    by = wshare(t, "taker_yes", ["month", "bucket"]).unstack("bucket").add_prefix("taker YES share, ")
    ext = t[t["bucket"] != "YES 30-70c"]
    by[LS] = wshare(ext, "longshot_buy", "month")
    by["sampled events"] = t.groupby("month")["event"].nunique()
    by["sampled contracts"] = t.groupby("month")["count"].sum()
    return by


def daily_test(t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Day level: flatness gap at 08:00 vs taker longshot share BEFORE 08:00 and the 08:00 median spread."""
    q = pd.read_parquet(ko.OUT / "quotes_with_q.parquet")
    q = q[q["usable"] & q["q"].notna()].assign(gap_c=lambda x: (x["mid"] - x["q"]) * 100)
    lo, hi = q[q["mid"] < CHEAP].groupby("day")["gap_c"].mean(), q[q["mid"] > DEAR].groupby("day")["gap_c"].mean()
    spread = q.assign(s=(q["ask"] - q["bid"]) * 100).groupby("day")["s"].median()
    pre = t[t["before_0800"] & (t["bucket"] != "YES 30-70c")]
    d = pd.DataFrame({"flat": lo - hi, "longshot_share": wshare(pre, "longshot_buy", "day"), "spread": spread,
                      "pre_volume": pre.groupby("day")["count"].sum()}).dropna()
    d = d[d["pre_volume"] >= 100]
    d["period"] = np.where(pd.to_datetime(d.index) >= "2026-01-01", "2026", "pre-2026")
    rows = []
    for period, g in [("all", d), *d.groupby("period")]:
        if len(g) < 15:
            continue
        z = lambda s: (s - s.mean()) / s.std(ddof=0)
        for name, cols in (("flow only", ["longshot_share"]), ("spread only", ["spread"]), ("both", ["longshot_share", "spread"])):
            X = np.column_stack([np.ones(len(g))] + [z(g[c]) for c in cols])
            beta, *_ = np.linalg.lstsq(X, g["flat"].to_numpy(), rcond=None)
            e = g["flat"].to_numpy() - X @ beta
            XtXi = np.linalg.inv(X.T @ X)
            V = XtXi @ (X.T @ (X * (e ** 2)[:, None])) @ XtXi * len(g) / (len(g) - X.shape[1])   # HC1
            r = {"period": period, "model": name, "days": len(g),
                 "r2": 1 - (e ** 2).sum() / ((g["flat"] - g["flat"].mean()) ** 2).sum()}
            for j, c in enumerate(cols, 1):
                r[f"{c}: c per SD"], r[f"{c}: t"] = beta[j], beta[j] / np.sqrt(V[j, j])
            rows.append(r)
    return pd.DataFrame(rows), d


def assoc_table(bias: pd.DataFrame, monthly: pd.DataFrame, cols) -> pd.DataFrame:
    out = []
    for meas, g in bias.groupby("measure"):
        j = g.set_index("month").join(monthly, how="inner")
        for col in cols:
            jj = j.dropna(subset=["value", col])
            if len(jj) < 6:
                continue
            rho, p = stats.spearmanr(jj["value"], jj[col])
            logx = col.startswith(("volume", "oi"))
            X = np.column_stack([np.ones(len(jj)), np.log(jj[col].clip(lower=1)) if logx else jj[col], np.arange(len(jj))])
            w = 1 / jj["se"].to_numpy() ** 2                                  # precision-weighted
            beta = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (jj["value"].to_numpy() * w))
            resid = jj["value"].to_numpy() - X @ beta
            cov = np.linalg.inv(X.T @ (X * w[:, None])) * (resid ** 2 * w).sum() / max(len(jj) - 3, 1)
            out.append({"measure": meas, "explanatory": col + (" (log)" if logx else ""), "months": len(jj),
                        "spearman_rho": rho, "p": p, "slope_with_trend": beta[1], "se": np.sqrt(cov[1, 1]),
                        "t": beta[1] / np.sqrt(cov[1, 1])})
    return pd.DataFrame(out)


def chart(bias: pd.DataFrame, monthly: pd.DataFrame):
    months = sorted(set(monthly.index) | set(bias["month"]))
    x = {m: i for i, m in enumerate(months)}
    xs = lambda idx: [x[m] for m in idx]
    fig, axes = plt.subplots(6, 1, figsize=(12, 17), sharex=True)
    offs = {"b, 08:00 UTC": (-.15, "#2a78b5"), "b, 8h": (0, "#3a9a5b"), "b, 1h": (.15, "#d1572c")}
    for meas, (off, c) in offs.items():
        g = bias[bias["measure"] == meas]
        axes[0].errorbar([x[m] + off for m in g["month"]], g["value"], yerr=1.96 * g["se"], fmt="o-", ms=3.5, lw=1.2,
                         color=c, capsize=2, label=meas.replace("b, ", ""))
    axes[0].axhline(1, color="#555", lw=1)
    axes[0].set(ylabel="logit slope b", title="Monthly favourite-longshot slope (1 = calibrated), 95% CI")
    axes[0].legend(frameon=False, ncol=3, loc="upper left")
    g = bias[bias["measure"].str.startswith("flatness")]
    axes[1].errorbar(xs(g["month"]), g["value"], yerr=1.96 * g["se"], fmt="o-", ms=3.5, lw=1.2, color="#7b4fa0", capsize=2)
    axes[1].axhline(0, color="#555", lw=1)
    axes[1].set(ylabel="cents", title="Flatness gap vs options at 08:00: mean(mid - q) on mids < 30c minus on mids > 70c")
    for col, c, lab in ((f"median_spread_c, {kc.AT_0800}", "#2a78b5", "08:00 UTC, all"),
                        (f"median_spread_c 10-90c, {kc.AT_0800}", "#7fb0d8", "08:00 UTC, mids 10-90c"),
                        ("median_spread_c, 1h", "#d1572c", "1h before, all")):
        s = monthly[col].dropna()
        axes[2].plot(xs(s.index), s, "o-", ms=3.5, color=c, label=lab)
    axes[2].set(ylabel="cents", title="Median quoted spread, 17:00 NY markets (two-sided quotes)")
    axes[2].legend(frameon=False, ncol=3, loc="upper right")
    for col, c, lab in ((LS, "#7b4fa0", "buys the cheap side (YES<30c, or NO when YES>70c)"),
                        ("taker YES share, YES < 30c", "#d1572c", "buys YES, YES < 30c"),
                        ("taker YES share, YES > 70c", "#3a9a5b", "buys YES, YES > 70c")):
        s = monthly[col].dropna()
        axes[3].plot(xs(s.index), s * 100, "o-", ms=3.5, color=c, label=lab)
    axes[3].axhline(50, color="#999", lw=.8)
    axes[3].set(ylabel="% of taker contracts", title="Taker flow by side (sampled days, block trades excluded)")
    axes[3].legend(frameon=False, loc="lower left", fontsize=8)
    axes[4].bar(xs(monthly.index), monthly["volume_12_17ny"] / 1e6, color="#9db7d5", label="12:00 + 17:00 NY (backfilled)")
    axes[4].bar(xs(monthly.index), monthly["volume_17ny"] / 1e6, color="#2a78b5", label="17:00 NY daily")
    axes[4].set(ylabel="million contracts", title="Monthly Kalshi BTC volume")
    axes[4].legend(frameon=False, loc="upper left")
    s = monthly["oi_0800_per_17ny_event"].dropna()
    axes[5].plot(xs(s.index), s / 1e3, "o-", ms=3.5, color="#2a78b5")
    axes[5].set(ylabel="thousand contracts", title="Open interest at 08:00 UTC, summed over a 17:00 NY event's strikes (monthly mean)")
    ticks = [i for i, m in enumerate(months) if m.endswith(("-01", "-04", "-07", "-10"))]
    axes[5].set_xticks(ticks, [months[i] for i in ticks])
    pos = {d: x[d[:7]] - .5 + int(d[8:]) / 31 for d in MM_EVENTS if d[:7] in x}
    for ax in axes:
        ax.axvline(x.get("2026-01", 0) - .5, color="#999", lw=1, ls="--")
        for p in pos.values():
            ax.axvline(p, color="#c08a00", lw=1.2, ls=":")
        ax.spines[["top", "right"]].set_visible(False)
    for d, p in pos.items():
        axes[0].text(p - .1, .97, f"{d}: {MM_EVENTS[d]}", transform=axes[0].get_xaxis_transform(), fontsize=8,
                     color="#8a6200", va="top", ha="right")
    fig.text(.01, .002, "SIG became Kalshi's first institutional market maker on 2024-04-03, before this sample. Kalshi publishes "
             "no start date for its crypto hourly/daily liquidity provider. Dashed grey line: 2026 holdout.", fontsize=8, color="#8a6200")
    fig.tight_layout(rect=(0, .01, 1, 1))
    fig.savefig(OUT / "bias_vs_activity.png", dpi=150)
    plt.close(fig)


def main():
    config.setup_logging()
    act, bias, spr = activity(), monthly_bias(), monthly_spreads()
    trades = load_trades()
    flow = monthly_flow(trades)
    dtest, _ = daily_test(trades)
    monthly = act.join(spr, how="outer").join(flow, how="outer")
    monthly.to_csv(OUT / "monthly_activity_spread_flow.csv")
    bias.to_csv(OUT / "bias_monthly.csv", index=False)
    dtest.to_csv(OUT / "daily_flow_vs_spread_test.csv", index=False)
    assoc = assoc_table(bias, monthly, ["volume_17ny", "oi_0800_per_17ny_event", f"median_spread_c, {kc.AT_0800}",
                                        f"median_spread_c 10-90c, {kc.AT_0800}", LS])
    assoc.to_csv(OUT / "association.csv", index=False)
    chart(bias, monthly)
    fmt = lambda t, idx=False: t.to_string(index=idx, float_format=lambda v: f"{v:.3f}")
    piv = bias.pivot_table(index="month", columns="measure", values="value")
    lines = [f"# Kalshi bias over time vs activity, spreads and taker flow (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             "17:00 NY daily markets. Months with < 10 events skipped. Monthly tests are descriptive (few, trending months).",
             f"Taker flow from Kalshi trade history on every 3rd settlement day ({trades['event'].nunique()} events, "
             f"{trades['count'].sum() / 1e6:.0f}M contracts; block trades excluded).",
             "Best-level depth: not available historically (Kalshi candles carry prices, volume and open interest but no "
             "order-book sizes); only the live snapshots since 2026-09-30 have sizes (reports/pm/kalshi_calibration, capacity).",
             f"Market-maker dates marked: {MM_EVENTS}.", "",
             "## Monthly bias", "```", fmt(piv, True), "```",
             "## Monthly activity, spreads and taker flow", "```", fmt(monthly, True), "```",
             "## Association across months (Spearman; precision-weighted OLS of bias on the explanatory with a linear trend)",
             "```", fmt(assoc), "```",
             "## Day level: flatness gap at 08:00 (c) on taker longshot share before 08:00 and the 08:00 median spread",
             "Regressors standardised (coefficient = cents per 1 SD); HC1 t-stats; days with >= 100 contracts traded at <30c/>70c before 08:00.",
             "```", fmt(dtest), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Bias over time done -> %s", OUT)


if __name__ == "__main__":
    main()
