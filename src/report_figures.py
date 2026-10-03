"""
The figures of reports/REPORT.md, regenerated in one style from the saved results.

  fig1  from option trades to a 1-day probability (one example day)
  fig2  validation of the short-horizon option forecasts (PIT histograms)
  fig3  Kalshi calibration and the price-floor check
  fig4  Kalshi vs options: the gap by price bucket and calibration on the same contracts
  fig5  encompassing regressions with stale and fresh option smiles
  fig6  trade tests: taker and maker P&L with confidence intervals
  fig7  markouts: what resting orders earn after a fill
  fig8  bias over time and market structure

Palette: the dataviz reference instance (blue / orange / aqua slots), light surface.
Run:  python -m src.report_figures   (fig1 refits one day's smile, ~2 minutes; the rest read reports/)
"""
import logging
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from src import pm_kalshi_calib as kc
from src import pm_kalshi_options as ko
from src import short_horizon as sh
from src.clean_trades import COLUMNS, clean

log = logging.getLogger(__name__)
R = config.ROOT / "reports"
OUT = R / "figures" / "report"
OUT.mkdir(parents=True, exist_ok=True)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
PERIOD_COLOR = {"pre-2026": BLUE, "2026": ORANGE}
EXAMPLE_EVENT = "KXBTCD-26MAR1117"                     # a midweek 2026 day with a full strike ladder

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "axes.titlecolor": INK, "axes.titlesize": 11,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.labelsize": 9.5,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5, "legend.frameon": False, "legend.fontsize": 8.5, "font.size": 9.5,
    "lines.linewidth": 2.0, "lines.markersize": 5, "figure.dpi": 100,
})


def save(fig, name: str, note: str | None = None):
    if note:
        note = "\n".join(textwrap.wrap(note, int(fig.get_figwidth() * 17)))
        fig.text(0.01, 0.005, note, fontsize=7.5, color=MUTED, ha="left", va="bottom")
    lines = note.count("\n") + 1 if note else 0
    fig.tight_layout(rect=(0, (0.012 + 0.11 / fig.get_figheight() * lines) if note else 0, 1, 1))
    fig.savefig(OUT / f"{name}.png", dpi=160)
    plt.close(fig)
    log.info("figure -> %s", OUT / f"{name}.png")


# ── fig1 ────────────────────────────────────────────────────────────────────────────────────
def fig1():
    qq = ko.kalshi_quotes()
    qq = qq[qq["event"] == EXAMPLE_EVENT]
    days = ko.option_q(qq)
    row = days[days["status"] == "ok"].iloc[0]
    origin, dist = row["origin"], row["dist_q"]
    t, _ = clean(pd.read_parquet(config.OPTION_TRADES_DIR / f"{origin:%Y-%m}.parquet", columns=COLUMNS))
    inp = sh.day_inputs(t, origin)
    front = inp["front"]
    per, p, T = front["per"], front["svi"], front["T"]
    kq = qq[qq["usable"]].assign(mid=lambda x: (x["bid"] + x["ask"]) / 2)
    settle_value = kq["brti_settle"].iloc[0]

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2))
    kk = np.linspace(per["k"].min() - .01, per["k"].max() + .01, 300)
    a.scatter(per["k"] * 100, per["iv"] * 100, s=np.clip(per["n"], 4, 60), color=BLUE, alpha=.55, lw=0,
              label="Deribit trades 00:00-08:00 (size = number of trades)")
    a.plot(kk * 100, np.sqrt(np.maximum(p.w(kk), 0) / T) * 100, color=INK, lw=1.8, label="SVI fit (arbitrage-penalised, m constrained)")
    a.set(xlabel="log-moneyness k = ln(K/F), %", ylabel="implied volatility, %",
          title=f"a) Front-expiry smile at 08:00 UTC, {origin:%d %b %Y}")
    a.legend(loc="upper center")
    K = dist.K
    lo, hi = np.searchsorted(K, kq["strike"].min() * .985), np.searchsorted(K, kq["strike"].max() * 1.015)
    b.plot(K[lo:hi] / 1e3, dist.prob_above[lo:hi], color=BLUE, lw=2, label="options: q = P(S > K) at 17:00 NY")
    b.scatter(kq["strike"] / 1e3, kq["mid"], color=ORANGE, s=22, zorder=3, label="Kalshi mid at 08:00 UTC")
    b.axvline(settle_value / 1e3, color=MUTED, lw=1, ls="--")
    b.text(settle_value / 1e3, .5, f"  settled {settle_value:,.0f}", color=INK2, fontsize=8)
    b.set(xlabel="strike K, $ thousand", ylabel="probability BTC ends above K",
          title="b) Scaled to 17:00 NY with variance time, vs Kalshi")
    b.legend(loc="upper right")
    save(fig, "fig1_option_to_probability",
         f"Event {EXAMPLE_EVENT}. Smile from {len(per)} strikes; forward from put-call parity; scaled with the variance-time fraction lambda = {row['lambda']:.2f}.")


# ── fig2 ────────────────────────────────────────────────────────────────────────────────────
def fig2():
    f = pd.read_parquet(R / "short_horizon" / "forecasts.parquet")
    f = f[(f["status"] == "ok") & (f["variant"] == "vartime+events, a=0.5")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    bins = np.linspace(0, 1, 21)
    for ax, target in zip(axes, ("noon NY", "17:00 NY")):
        x = f.loc[f["target"] == target, "pit"].dropna()
        n = len(x)
        h, _ = np.histogram(x, bins)
        dens = h / n * 20
        ax.bar(bins[:-1], dens, width=.05, align="edge", color=BLUE, edgecolor=SURFACE, linewidth=2)
        band = 1.96 * np.sqrt(20 * (1 - 1 / 20) / n) * 1
        ax.axhspan(1 - band, 1 + band, color=MUTED, alpha=.15, lw=0)
        ax.axhline(1, color=INK2, lw=1)
        ratio = np.var(x) / (1 / 12)
        ax.set(title=f"{target}: {n:,} days, PIT variance ratio {ratio:.2f}", xlabel="PIT = forecast P(S <= realised)")
    axes[0].set_ylabel("density (1 = calibrated)")
    save(fig, "fig2_short_horizon_validation",
         "Option forecast made at 08:00 UTC (front smile, variance time + event profile, alpha 0.5) vs the Binance price at the target; "
         "grey band = 95% range for a calibrated forecast. A hump in the middle = slightly too wide.")


# ── fig3 ────────────────────────────────────────────────────────────────────────────────────
def fig3():
    rel = pd.read_csv(R / "pm" / "kalshi_calibration" / "reliability.csv")
    rel = rel[(rel["event_hour"] == "17:00 NY") & (rel["lead"] == "1h")]
    rob = pd.read_csv(R / "pm" / "kalshi_robustness" / "b_by_sample.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1.25]})
    a.plot([0, 1], [0, 1], color=MUTED, lw=1)
    for period in ("pre-2026", "2026"):
        g = rel[rel["period"] == period]
        a.errorbar(g["mean_mid"], g["observed"], yerr=[g["observed"] - g["ci_lo"], g["ci_hi"] - g["observed"]],
                   fmt="o-", color=PERIOD_COLOR[period], ms=4.5, lw=1.5, capsize=2, label=f"{period} ({g['days'].max()} days max per bin)")
    a.set(xlabel="Kalshi mid, 1 hour before settlement", ylabel="share that settled YES",
          title="a) Reliability, 17:00 NY daily markets, 1h before")
    a.legend(loc="upper left")
    samples = [("mid none", "all prices"), ("mid 10c-90c", "mids 10-90c"), ("|z| <= 1.5", "|z| <= 1.5 SD")]
    leads = ["1h", "8h", "08:00 UTC", "24h"]
    y0 = 0
    yt, yl = [], []
    for lead in leads:
        for j, (s, lab) in enumerate(samples):
            g = rob[(rob["lead"] == lead) & (rob["sample"] == s)]
            for period, off in (("pre-2026", -.13), ("2026", .13)):
                r = g[g["period"] == period]
                if r.empty:
                    continue
                r = r.iloc[0]
                b.errorbar(r["b"], y0 + off, xerr=1.96 * r["b_se"], fmt="o", color=PERIOD_COLOR[period], ms=4.5, capsize=2,
                           label=period if (lead == leads[0] and j == 0) else None)
            yt.append(y0)
            yl.append(f"{lead}: {lab}")
            y0 += 1
        y0 += .6
    b.axvline(1, color=INK2, lw=1)
    b.set_yticks(yt, yl, fontsize=8)
    b.invert_yaxis()
    b.set(xlabel="logit slope b (1 = calibrated, > 1 = longshots overpriced), 95% CI",
          title="b) Slope b with price-floor and moneyness checks")
    b.legend(loc="lower right")
    save(fig, "fig3_kalshi_calibration",
         "Usable quotes: two-sided, spread <= 10c. Trimming mids or selecting by distance from the money removes the 1c price floor's effect.")


# ── fig4 ────────────────────────────────────────────────────────────────────────────────────
def fig4():
    dt = pd.read_csv(R / "pm" / "kalshi_vs_options" / "mid_minus_q.csv")
    q = pd.read_parquet(R / "pm" / "kalshi_vs_options" / "quotes_with_q.parquet")
    q = q[q["usable"] & q["q"].notna()].assign(mid=lambda x: (x["bid"] + x["ask"]) / 2)
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.3))
    for period in ("pre-2026", "2026"):
        g = dt[(dt["period"] == period) & (dt["mid_bucket"] != "all")]
        a.errorbar(g["mean_mid"], g["mid_minus_q_c"], yerr=[g["mid_minus_q_c"] - g["ci_lo"], g["ci_hi"] - g["mid_minus_q_c"]],
                   fmt="o-", color=PERIOD_COLOR[period], ms=4.5, lw=1.5, capsize=2, label=f"{period} ({g['days'].max()} days max)")
    a.axhline(0, color=INK2, lw=1)
    a.set(xlabel="Kalshi mid at 08:00 UTC (bucket mean)", ylabel="Kalshi mid - option q, cents",
          title="a) Kalshi is flatter than the options")
    a.legend(loc="upper right")
    bins = np.array([0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, 1])
    b.plot([0, 1], [0, 1], color=MUTED, lw=1)
    for col, color, lab in (("q", BLUE, "option q"), ("mid", ORANGE, "Kalshi mid")):
        g = q.groupby(pd.cut(q[col], bins, include_lowest=True), observed=True).agg(x=(col, "mean"), y=("outcome", "mean"), n=("outcome", "size"))
        b.plot(g["x"], g["y"], "o-", color=color, ms=4.5, lw=1.5, label=lab)
    b.set(xlabel="forecast probability (bucket mean)", ylabel="share that settled YES",
          title="b) Same contracts: q is calibrated, the mid is too flat")
    b.legend(loc="upper left")
    save(fig, "fig4_kalshi_vs_options",
         f"{len(q):,} contracts on {q['day'].nunique()} days, 2024-07 to 2026-09. Logit slope: q 0.99 +/- 0.04, Kalshi mid 1.14 +/- 0.04.")


# ── fig5 ────────────────────────────────────────────────────────────────────────────────────
def fig5():
    st = pd.read_csv(R / "pm" / "kalshi_vs_options" / "staleness_encompassing.csv").drop_duplicates(["period", "options"])
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.9), sharex=True)
    order = [("q", "trades 00:00-08:00"), ("q_2h", "last 2 hours only"), ("q_1h", "last hour only")]
    for ax, period in zip(axes, ("pre-2026", "2026")):
        for i, (opt, lab) in enumerate(order):
            r = st[(st["period"] == period) & (st["options"] == opt)].iloc[0]
            ax.errorbar(r["b1_kalshi"], i - .12, xerr=1.96 * r["b1_se"], fmt="o", color=ORANGE, capsize=2, label="Kalshi mid (b1)" if i == 0 else None)
            ax.errorbar(r["b2_options"], i + .12, xerr=1.96 * r["b2_se"], fmt="s", color=BLUE, capsize=2, label="option q (b2)" if i == 0 else None)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_yticks(range(3), [lab for _, lab in order])
        ax.invert_yaxis()
        ax.set(title=f"{period}", xlabel="coefficient, 95% CI")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=2)
    save(fig, "fig5_encompassing_staleness",
         "P(YES) = sigmoid(a + b1 logit(Kalshi mid) + b2 logit(option q)) on 08:00 UTC quotes. SEs clustered by event; the two logits are 0.98-0.99 correlated, so the weights are imprecise. Fresh option data raises the options' weight in 2026.")


# ── fig6 ────────────────────────────────────────────────────────────────────────────────────
def fig6():
    tr = pd.read_csv(R / "pm" / "kalshi_gap_trade" / "results.csv")
    tr = tr[(tr["q_source"].str.startswith("q (8h")) & (tr["style"] == "taker") & (tr["side"] == "both")]
    fs = pd.read_csv(R / "pm" / "kalshi_markout" / "maker_fill_simulation.csv")
    fs = fs[fs["side"] == "both"]
    rows = []
    for T in (2.0, 3.0, 5.0):
        for period in ("pre-2026", "2026"):
            r = tr[(tr["T_c"] == T) & (tr["period"] == period)].iloc[0]
            rows.append(("taker", T, period, r["pnl_per_contract_c"], r["ci_lo"], r["ci_hi"]))
            for rule, lab in (("assume always filled", "maker, fill assumed"), ("through", "maker, fills simulated")):
                r = fs[(fs["T_c"] == T) & (fs["period"] == period) & (fs["fill_rule"] == rule)].iloc[0]
                rows.append((lab, T, period, r["pnl_per_signal_c"], r["ci_lo"], r["ci_hi"]))
    d = pd.DataFrame(rows, columns=["strategy", "T", "period", "pnl", "lo", "hi"])
    fig, ax = plt.subplots(figsize=(10, 4.6))
    strategies = ["taker", "maker, fill assumed", "maker, fills simulated"]
    y, yt, yl = 0, [], []
    for s in strategies:
        for T in (2.0, 3.0, 5.0):
            for period, off in (("pre-2026", -.14), ("2026", .14)):
                r = d[(d["strategy"] == s) & (d["T"] == T) & (d["period"] == period)].iloc[0]
                ax.errorbar(r["pnl"], y + off, xerr=[[r["pnl"] - r["lo"]], [r["hi"] - r["pnl"]]], fmt="o",
                            color=PERIOD_COLOR[period], ms=5, capsize=2, label=period if (y == 0) else None)
            yt.append(y)
            yl.append(f"{s}, T = {T:.0f}c")
            y += 1
        y += .6
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(yt, yl, fontsize=8.5)
    ax.invert_yaxis()
    ax.set(xlabel="P&L, cents per contract (taker) or per signal (maker), after fees, 95% CI clustered by day",
           title="Gap-conditional trades at 08:00 UTC vs the option fair value")
    ax.legend(loc="lower right")
    save(fig, "fig6_trade_tests",
         "Taker: all days, every executable quote. Maker: real books only; 'fills simulated' = filled only if a later Kalshi trade went through "
         "our price (sampled days, unfilled = 0). 2026 is the holdout.")


# ── fig7 ────────────────────────────────────────────────────────────────────────────────────
def fig7():
    by = pd.read_csv(R / "pm" / "kalshi_markout" / "markout_by_year.csv")
    bb = pd.read_csv(R / "pm" / "kalshi_markout" / "markout_by_bucket.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1, 1.2]})
    xs = [0, 1, 5, 30]
    cols = ["half_spread_c", "markout_1m_c", "markout_5m_c", "markout_30m_c"]
    for fill, color in (("resting bid filled (taker sold YES)", BLUE), ("resting offer filled (taker bought YES)", ORANGE)):
        for year, ls in ((2025, ":"), (2026, "-")):
            r = by[(by["fill"] == fill) & (by["year"] == year)].iloc[0]
            a.plot(xs, [r[c] for c in cols], ls=ls, marker="o", color=color, ms=4,
                   label=f"{fill.split(' (')[0]}, {year}")
    a.axhline(0, color=INK2, lw=1)
    a.set_xscale("symlog", linthresh=1)
    a.set_xticks(xs, ["at fill", "1 min", "5 min", "30 min"])
    a.set(ylabel="maker's gain vs fill price, cents", title="a) Markouts after a fill (maker's view)")
    a.legend(loc="lower left", fontsize=7.5)
    bb = bb.assign(x=bb["bucket"].str.extract(r"\(([-\d.]+), ([\d.]+)\]").astype(float).mean(axis=1))
    for fill, color, lab in (("resting bid filled (taker sold YES)", BLUE, "maker bought YES at this price"),
                             ("resting offer filled (taker bought YES)", ORANGE, "maker bought NO at this price")):
        g = bb[bb["fill"] == fill]
        ci = g["settle_markout_c_ci"].str.strip("[]").str.split(", ", expand=True).astype(float)
        b.errorbar(g["x"] * 100, g["settle_markout_c"], yerr=[g["settle_markout_c"] - ci[0], ci[1] - g["settle_markout_c"]],
                   fmt="o-", color=color, ms=4, lw=1.3, capsize=2, label=lab)
    b.axhline(0, color=INK2, lw=1)
    b.set(xlabel="maker's purchase price, cents", ylabel="maker's P&L to settlement, cents",
          title="b) To settlement: favourites win, longshots lose")
    b.legend(loc="upper left")
    save(fig, "fig7_markouts",
         "Kalshi trade history, every 3rd settlement day (2.4M trades with a real pre-trade book); contract-weighted, 95% CI clustered by event.")


# ── fig8 ────────────────────────────────────────────────────────────────────────────────────
def fig8():
    bias = pd.read_csv(R / "pm" / "kalshi_bias_time" / "bias_monthly.csv")
    m = pd.read_csv(R / "pm" / "kalshi_bias_time" / "monthly_activity_spread_flow.csv", index_col=0)
    months = sorted(set(m.index) | set(bias["month"]))
    months = [x for x in months if x <= "2026-09"]
    x = {mm: i for i, mm in enumerate(months)}
    fig, axes = plt.subplots(4, 1, figsize=(10, 9.5), sharex=True)
    g = bias[(bias["measure"] == "b, 8h") & bias["month"].isin(x)]
    axes[0].errorbar([x[mm] for mm in g["month"]], g["value"], yerr=1.96 * g["se"], fmt="o-", color=BLUE, ms=4, lw=1.3, capsize=2)
    axes[0].axhline(1, color=INK2, lw=1)
    axes[0].set(ylabel="logit slope b", title="a) Favourite-longshot slope, 8h before settlement (monthly, 95% CI)")
    s = m[f"median_spread_c 10-90c, {kc.AT_0800}"].dropna()
    s = s[s.index.isin(x)]
    axes[1].plot([x[mm] for mm in s.index], s, "o-", color=BLUE, ms=4, lw=1.3)
    axes[1].set_yscale("log")
    axes[1].set_yticks([1, 2, 5, 10, 20, 50, 100], ["1", "2", "5", "10", "20", "50", "100"])
    axes[1].set(ylabel="cents (log)", title="b) Median quoted spread at 08:00 UTC, mids 10-90c")
    ls = m["taker longshot share (YES<30c or NO when YES>70c)"].dropna()
    ls = ls[ls.index.isin(x)]
    axes[2].plot([x[mm] for mm in ls.index], ls * 100, "o-", color=ORANGE, ms=4, lw=1.3)
    axes[2].axhline(50, color=INK2, lw=1)
    axes[2].set(ylabel="% of taker contracts", title="c) Takers buying the cheap side (YES < 30c, or NO when YES > 70c)")
    v = m["volume_17ny"].dropna()
    v = v[v.index.isin(x)]
    axes[3].bar([x[mm] for mm in v.index], v / 1e6, color=BLUE, width=.75)
    axes[3].set(ylabel="million contracts", title="d) Monthly volume, Kalshi 17:00 NY daily BTC markets")
    ticks = [i for i, mm in enumerate(months) if mm.endswith(("-01", "-04", "-07", "-10"))]
    axes[3].set_xticks(ticks, [months[i] for i in ticks])
    wm = x["2026-05"] - .5 + 29 / 31
    for ax in axes:
        ax.axvline(x["2026-01"] - .5, color=MUTED, lw=1, ls="--")
        ax.axvline(wm, color=AQUA, lw=1.2, ls=":")
    axes[0].text(x["2026-01"] - .6, .97, "2026 holdout", transform=axes[0].get_xaxis_transform(), color=INK2, fontsize=8, va="top", ha="right")
    axes[3].text(wm - .15, .95, "Wintermute confirms\nquoting (2026-05-29)", transform=axes[3].get_xaxis_transform(), color=INK2, fontsize=8, va="top", ha="right")
    save(fig, "fig8_bias_over_time",
         "Taker flow from the sampled trade history (every 3rd day). SIG became Kalshi's first institutional market maker on 2024-04-03, before this sample.")


def main():
    config.setup_logging()
    for f in (fig2, fig3, fig4, fig5, fig6, fig7, fig8, fig1):
        try:
            f()
        except Exception:
            log.exception("%s failed", f.__name__)


if __name__ == "__main__":
    main()
