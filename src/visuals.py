"""
Progress charts: one PNG per pipeline step, saved to reports/figures/.
Re-run after any fetch to refresh them:  python -m src.visuals

  00_data_coverage.png   what we have: each dataset's date span, gaps marked
  02_btc_price.png       BTC price, plus how closely the price sources agree
  03_btc_vs_dvol.png     BTC price and DVOL on the same time axis
  04_option_trades.png   option trades: activity, IV smile, expiries, suspect rows
  05_live_snapshot.png   latest snapshot: prediction-market P(BTC > K), Deribit smiles, forwards
"""
import glob
import logging

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

import config
from src.storage import load_parquet

log = logging.getLogger(__name__)

# Palette: validated categorical slots + neutral inks (light theme).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CRITICAL = "#d03b3b"                       # reserved for data problems, always labelled
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "text.color": INK,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "font.size": 9, "lines.linewidth": 1.2, "legend.frameon": False,
})


def save(fig, name: str, folder=None):
    path = (folder or config.FIGURES_DIR) / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart -> %s", path)


def usd_log_axis(ax):
    """Log-scale price axis with readable $ ticks (matplotlib only labels powers of 10 by default)."""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator([15e3, 20e3, 30e3, 50e3, 70e3, 100e3, 150e3]))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())


def gap_blocks(index: pd.DatetimeIndex, freq: str) -> list[tuple[pd.Timestamp, int]]:
    """Missing stretches in a regular time index, as (start, number of missing steps)."""
    missing = pd.date_range(index[0], index[-1], freq=freq).difference(index)
    if missing.empty:
        return []
    s = pd.Series(missing)
    block = (s.diff() != pd.tseries.frequencies.to_offset(freq)).cumsum()
    return [(g.iloc[0], len(g)) for _, g in s.groupby(block)]


def chart_coverage():
    """Gantt-style: one bar per dataset from first to last timestamp, gaps as red ticks."""
    R = config.DATA_RAW
    trade_files = sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet")))
    datasets = [
        ("BTC hourly (Coinbase)", R / "btc_price_hourly.parquet", "h"),
        ("BTC 6h avg index (Deribit)", R / "btc_index_6h_deribit.parquet", "6h"),
        ("08:00 settlement price (Deribit)", R / "btc_price_0800.parquet", "D"),
        ("DVOL hourly (Deribit)", R / "dvol_hourly.parquet", "h"),
    ] + [(f"Option trades {p[-15:-8]}", p, None) for p in trade_files]

    fig, ax = plt.subplots(figsize=(10, 0.55 * len(datasets) + 1.2))
    for y, (label, path, freq) in enumerate(reversed(datasets)):
        idx = pd.read_parquet(path, columns=[]).index
        ax.barh(y, idx[-1] - idx[0], left=idx[0], height=0.5, color=BLUE)
        note = f"{len(idx):,} rows"
        if freq:
            gaps = gap_blocks(idx, freq)
            for start, _ in gaps:
                ax.plot([start, start], [y - 0.35, y + 0.35], color=CRITICAL, lw=2)
            if gaps:
                note += f"  ·  {sum(n for _, n in gaps)} missing in {len(gaps)} gaps"
        ax.text(idx[-1] + pd.Timedelta(days=20), y, note, va="center", color=INK_2, fontsize=8)
    ax.set_yticks(range(len(datasets)), [d[0] for d in reversed(datasets)])
    ax.set_xlim(pd.Timestamp("2020-10-01", tz="UTC"), pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=700))
    ax.grid(axis="y", visible=False)
    ax.set_title("Data collected so far  (red ticks = gaps)")
    save(fig, "00_data_coverage.png")


def chart_prices():
    R = config.DATA_RAW
    daily = load_parquet(R / "btc_price_daily.parquet")
    at8 = load_parquet(R / "btc_price_0800.parquet")
    hourly = load_parquet(R / "btc_price_hourly.parquet")
    idx6 = load_parquet(R / "btc_index_6h_deribit.parquet")

    # Coinbase averaged over each preceding 6h window vs Deribit's 6h average index
    mid = (hourly["open"] + hourly["close"]) / 2
    cb6 = mid.resample("6h", label="right").mean()
    src_diff = (cb6.reindex(idx6.index) / idx6["index_avg_6h"] - 1) * 100

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 1, 1]})
    ax = axes[0]
    ax.plot(daily.index, daily["close"], color=BLUE)
    usd_log_axis(ax)
    ax.set_title("BTC daily close, USD (log scale)  ·  source: Coinbase")

    ax = axes[1]
    ax.plot(at8.index, at8["diff_pct"], color=BLUE, lw=0.8)
    ax.axhline(0, color=INK_2, lw=0.8)
    ax.set_ylabel("%")
    ax.set_title("08:00 UTC: Coinbase spot vs Deribit settlement price  (median |diff| "
                 f"{at8['diff_pct'].abs().median():.2f}%)")

    ax = axes[2]
    ax.plot(src_diff.index, src_diff, color=BLUE, lw=0.6)
    ax.axhline(0, color=INK_2, lw=0.8)
    ax.set_ylabel("%")
    ax.set_title("Coinbase vs Deribit index, 6h averages  (median |diff| "
                 f"{src_diff.abs().median():.2f}%)")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    save(fig, "02_btc_price.png")


def chart_btc_dvol():
    """Two panels on a shared time axis (not a dual-axis chart: the two scales are unrelated)."""
    m = load_parquet(config.DATA_PROCESSED / "btc_dvol_daily.parquet")
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    a1.plot(m.index, m["btc_close"], color=BLUE)
    usd_log_axis(a1)
    a1.set_title("BTC daily close, USD (log scale)")
    a2.plot(m.index, m["dvol_close"], color=ORANGE)
    a2.set_ylabel("annualised vol, %")
    a2.set_title("DVOL: 30-day implied volatility, daily close")
    for when, val in [(m["dvol_close"].idxmax(), m["dvol_close"].max()),
                      (m["dvol_close"].idxmin(), m["dvol_close"].min())]:
        a2.annotate(f"{val:.0f}  ({when:%b %Y})", (when, val), textcoords="offset points",
                    xytext=(6, 0), va="center", color=INK_2, fontsize=8)
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    save(fig, "03_btc_vs_dvol.png")


def chart_option_trades():
    files = sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet")))
    if not files:
        return
    df = pd.concat(pd.read_parquet(f) for f in files)
    month = f"{df.index[0]:%b %Y}" if len(files) == 1 else f"{len(files)} months"
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))

    # (a) trades per day, calls vs puts
    ax = axes[0, 0]
    per_day = df.groupby([df.index.floor("D"), "option_type"]).size().unstack(fill_value=0)
    ax.bar(per_day.index, per_day["call"], width=0.8, color=BLUE, label="calls")
    ax.bar(per_day.index, per_day["put"], width=0.8, bottom=per_day["call"], color=ORANGE,
           label="puts", edgecolor=SURFACE, linewidth=1)
    ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1, 8, 15, 22]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(loc="upper left", ncols=2)
    ax.set_title(f"Trades per day  ·  {len(df):,} total")

    # (b) IV smile for one short-dated expiry: IV vs strike/index
    ax = axes[0, 1]
    clean = df[(df["iv"] > 0) & (df["iv"] < 500)]
    exp = clean[(clean["days_to_expiry"].between(5, 10))]["expiry"].value_counts().idxmax()
    s = clean[(clean["expiry"] == exp) & clean["days_to_expiry"].between(5, 10)]
    for kind, color in [("call", BLUE), ("put", ORANGE)]:
        k = s[s["option_type"] == kind]
        ax.scatter(k["strike"] / k["index_price"], k["iv"], s=8, alpha=0.35, color=color,
                   label=f"{kind}s", linewidths=0)
    ax.set_xlabel("moneyness = strike / BTC index")
    ax.set_ylabel("trade IV, %")
    ax.legend(loc="upper center", ncols=2, markerscale=2)
    ax.set_title(f"IV smile: trades in {exp:%d %b} expiry, 5–10 days before it")

    # (c) where volume sits by time to expiry
    ax = axes[1, 0]
    bins = [0, 1, 2, 7, 14, 30, 60, 120, 400]
    labels = ["<1d", "1–2d", "2–7d", "1–2w", "2w–1m", "1–2m", "2–4m", ">4m"]
    by_dte = pd.cut(df["days_to_expiry"], bins, labels=labels).value_counts().reindex(labels)
    ax.bar(labels, by_dte.values, color=BLUE, width=0.7)
    for i, v in enumerate(by_dte.values):
        ax.text(i, v, f"{v/len(df):.0%}", ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_title("Trades by time to expiry")
    ax.grid(axis="x", visible=False)

    # (d) data-quality flags found in the raw trades
    ax = axes[1, 1]
    flags = pd.Series({
        "iv = 0": (df["iv"] <= 0).sum(),
        "iv = 999": (df["iv"] >= 999).sum(),
        "iv 300–999": df["iv"].between(300, 999, inclusive="left").sum(),
        "liquidations": df["liquidation"].notna().sum(),
        "block trades": df["block_trade_id"].notna().sum(),
    })
    colors = [CRITICAL, CRITICAL, CRITICAL, BLUE, BLUE]
    ax.barh(flags.index[::-1], flags.values[::-1], color=colors[::-1], height=0.55)
    for i, v in enumerate(flags.values[::-1]):
        ax.text(v, i, f"  {v:,}  ({v/len(df):.2%})", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, flags.max() * 1.4)
    ax.grid(axis="y", visible=False)
    ax.set_title("Rows to watch  (red = suspect IV values, kept in raw/)")

    fig.suptitle(f"Deribit BTC option trades, {month}", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "04_option_trades.png")


def chart_snapshot():
    """The latest live snapshot: prediction-market probabilities, Deribit smiles, forward curve."""
    d_files = sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "deribit_*.parquet")))
    p_files = sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "predmarkets_*.parquet")))
    if not d_files or not p_files:
        return
    d, p = pd.read_parquet(d_files[-1]), pd.read_parquet(p_files[-1])
    t = d["snapshot_time"].iloc[0]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))

    # (a) P(BTC above K): per venue, the "above" event with the most usable two-sided quotes
    ax = axes[0]
    q = p[(p["kind"] == "above") & p["yes_bid"].notna() & p["yes_ask"].notna()
          & ((p["yes_ask"] - p["yes_bid"]) <= 0.10)].copy()
    q["mid"] = (q["yes_bid"] + q["yes_ask"]) / 2
    for venue, color, marker in [("polymarket", BLUE, "o"), ("kalshi", ORANGE, "s")]:
        v = q[q["venue"] == venue]
        if v.empty:
            continue
        ev = v.groupby("event").size().idxmax()
        v = v[v["event"] == ev].sort_values("strike")
        ax.plot(v["strike"], v["mid"], color=color, marker=marker, markersize=4, lw=1.2,
                label=f"{venue}: resolves {v['resolution_time'].iloc[0]:%d %b %H:%M} UTC")
    ax.axvline(d["index_price"].iloc[0], color=INK_2, lw=0.8, ls="--")
    ax.text(d["index_price"].iloc[0], 1.02, " BTC now", color=INK_2, fontsize=8)
    ax.set_ylim(-0.02, 1.08)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    ax.set_ylabel("P(BTC above strike)  = mid price")
    ax.legend(loc="upper right", fontsize=7.5)
    ax.set_title("Prediction markets: P(BTC > K)\n(two-sided quotes, spread ≤ 10¢)")

    # (b) Deribit mark IV smile, 3 nearest expiries
    ax = axes[1]
    for exp, color in zip(sorted(d["expiry"].unique())[:3], [BLUE, ORANGE, AQUA]):
        e = d[(d["expiry"] == exp) & (d["option_type"] == "call")].sort_values("strike")
        e = e[(e["strike"] / e["forward_price"]).between(0.7, 1.3)]
        ax.plot(e["strike"] / e["forward_price"], e["mark_iv"], color=color, marker="o", markersize=3,
                label=f"{exp:%d %b} ({(exp - t).total_seconds() / 86400:.1f}d)")
    ax.set_xlabel("strike / forward")
    ax.set_ylabel("mark IV, %")
    ax.legend(loc="upper center", fontsize=8)
    ax.set_title("Deribit: mark IV smile, nearest 3 expiries")

    # (c) forward curve: each expiry's forward vs spot index
    ax = axes[2]
    fwd = d.groupby("expiry")[["forward_price", "index_price"]].first()
    prem = (fwd["forward_price"] / fwd["index_price"] - 1) * 100
    days = (fwd.index - t).total_seconds() / 86400
    ax.plot(days, prem, color=BLUE, marker="o", markersize=4)
    ax.axhline(0, color=INK_2, lw=0.8)
    ax.set_xlabel("days to expiry")
    ax.set_ylabel("forward premium over index, %")
    ax.set_title("Deribit: forward price per expiry\n(what trade data lacks)")

    fig.suptitle(f"Live snapshot {t:%Y-%m-%d %H:%M} UTC  ·  {len(d)} Deribit options, "
                 f"{(p['venue'] == 'polymarket').sum()} Polymarket + {(p['venue'] == 'kalshi').sum()} Kalshi markets",
                 x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "05_live_snapshot.png")


# ── Phase 2: lognormal cones and calibration ────────────────────────────────────────────────
# One-hue blue ramp for nested probability bands (outer = lighter), orange for the RV baseline.
BAND_OUTER, BAND_INNER, BAND_LINE = "#b7d3f6", "#6da7ec", "#1c5cab"


def _cone(s0, sigma, days):
    """Percentile paths of the lognormal model at each day 0..days (t in years)."""
    from src.models import dvol_lognormal as lm
    t = np.arange(0, days + 1) / lm.YEAR
    t[0] = 1e-9                                   # avoid sigma*sqrt(0) division issues at t=0
    return {q: lm.percentile(s0, sigma, q, t) for q in (0.05, 0.25, 0.50, 0.75, 0.95)}


def chart_forward_cone(delivery: pd.Series, dvol_0800: pd.Series, folder):
    """Where BTC could be over the next 30 days, from the latest 08:00 UTC origin."""
    from src.models.realized_vol import trailing_realized_vol
    origin = dvol_0800.index.intersection(delivery.index).max()
    s0, sig = delivery[origin], dvol_0800[origin]
    sig_rv = trailing_realized_vol(delivery)[origin]
    days = np.arange(0, 31)
    x = origin + pd.to_timedelta(days, unit="D")
    c, c_rv = _cone(s0, sig, 30), _cone(s0, sig_rv, 30)

    fig, ax = plt.subplots(figsize=(10, 5))
    hist = delivery.loc[origin - pd.Timedelta(days=60):origin]
    ax.plot(hist.index, hist, color=INK, lw=1.2, label="BTC (Deribit 08:00 delivery price)")
    ax.fill_between(x, c[0.05], c[0.95], color=BAND_OUTER, lw=0, label="DVOL 5–95%")
    ax.fill_between(x, c[0.25], c[0.75], color=BAND_INNER, lw=0, label="DVOL 25–75%")
    ax.plot(x, c[0.50], color=BAND_LINE, lw=1.5, label="DVOL median")
    ax.plot(x, c_rv[0.05], color=ORANGE, lw=1.2, ls="--", label="realised-vol 5% / 95%")
    ax.plot(x, c_rv[0.95], color=ORANGE, lw=1.2, ls="--")
    for q in (0.05, 0.25, 0.50, 0.75, 0.95):
        ax.annotate(f"{int(q*100)}%  ${c[q][-1]:,.0f}", (x[-1], c[q][-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(hist.index[0], x[-1] + pd.Timedelta(days=12))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(f"30-day forward cone from {origin:%d %b %Y} 08:00 UTC  ·  S₀ ${s0:,.0f}  ·  "
                 f"DVOL {sig*100:.1f}%  vs  trailing realised vol {sig_rv*100:.1f}%")
    save(fig, "forward_cone.png", folder)


def chart_historical_cones(nonoverlap: pd.DataFrame, delivery: pd.Series, folder):
    """Every non-overlapping 30-day forecast since 2021, DVOL (top) and realised-vol baseline
    (bottom), with the realised path. End points outside the 5–95% band are marked in red."""
    fig, axes = plt.subplots(2, 1, figsize=(15, 8.5), sharex=True, sharey=True)
    for ax, m, label in [(axes[0], "dvol", "DVOL (implied vol)"), (axes[1], "rv", "trailing 30-day realised vol")]:
        n_out = 0
        for origin, r in nonoverlap.iterrows():
            x = origin + pd.to_timedelta(np.arange(0, 31), unit="D")
            c = _cone(r["s0"], r[f"sigma_{m}"], 30)
            ax.fill_between(x, c[0.05], c[0.95], color=BAND_OUTER, lw=0)
            ax.fill_between(x, c[0.25], c[0.75], color=BAND_INNER, lw=0)
            path = delivery.reindex(x)
            ax.plot(x, path, color=INK, lw=0.9)
            outside = not (0.05 <= r[f"pit_{m}"] <= 0.95)
            n_out += outside
            ax.plot(x[-1], r["s_t"], "o", ms=8 if outside else 3.5, color=CRITICAL if outside else INK,
                    markeredgecolor=SURFACE, markeredgewidth=1, zorder=3)
        usd_log_axis(ax)
        ax.set_title(f"{label}: 5–95% (light) and 25–75% (dark) bands, realised path in black  ·  "
                     f"{n_out} of {len(nonoverlap)} finished outside 5–95% (red dots; expected {0.10*len(nonoverlap):.1f})")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("Non-overlapping 30-day lognormal cones since 2021", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "historical_cones.png", folder)


def chart_pit(df: pd.DataFrame, folder, models=None):
    """PIT histograms: flat = calibrated, U = too narrow, hump = too wide."""
    models = models or [("dvol", "DVOL", BLUE), ("rv", "Realised vol", ORANGE)]
    fig, axes = plt.subplots(len(models), 2, figsize=(11, 3.5 * len(models)), sharex=True, squeeze=False)
    samples = [("overlapping (daily)", df), ("non-overlapping (every 30d)", df.iloc[::30])]
    for row, (m, label, color) in enumerate(models):
        for col, (sname, s) in enumerate(samples):
            ax = axes[row, col]
            u = s[f"pit_{m}"]
            w = np.ones(len(u)) / len(u) * 10           # density: uniform = 1.0 in every bin
            ax.hist(u, bins=10, range=(0, 1), weights=w, color=color, edgecolor=SURFACE, linewidth=2)
            ax.axhline(1, color=INK_2, lw=1, ls="--")
            ax.text(0.99, 1.02, "uniform", color=INK_2, fontsize=8, ha="right", va="bottom",
                    transform=ax.get_yaxis_transform())
            ax.set_title(f"{label} · {sname} (n={len(u)})\nvar ratio {u.var() / (1/12):.2f}  "
                         f"(>1 U-shape: too narrow, <1 hump: too wide)", fontsize=9.5)
            ax.grid(axis="x", visible=False)
    for ax in axes[-1]:
        ax.set_xlabel("PIT = model CDF at the realised price")
    for ax in axes[:, 0]:
        ax.set_ylabel("density")
    fig.tight_layout()
    save(fig, "pit_histograms.png", folder)


def chart_reliability(df: pd.DataFrame, folder, models=None):
    """Reliability diagrams for P(S_T > k·S_0), pooled over the 5 strikes."""
    from src import calibration as cal
    models = models or [("dvol", "DVOL", BLUE, "o"), ("rv", "Realised vol", ORANGE, "s")]
    strikes = [80, 90, 100, 110, 120]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for ax, (sname, s) in zip(axes, [("overlapping (daily)", df), ("non-overlapping (every 30d)", df.iloc[::30])]):
        ax.plot([0, 1], [0, 1], color=INK_2, lw=1, ls="--")
        for m, label, color, marker in models:
            p = np.concatenate([s[f"p{k}_{m}"] for k in strikes])
            y = np.concatenate([s[f"y{k}"] for k in strikes])
            r = cal.reliability(p, y)
            br = cal.brier(p, y).mean()
            ax.errorbar(r["mean_forecast"], r["observed"], yerr=r["ci95"] if "non" in sname else None,
                        color=color, marker=marker, ms=5, lw=1.2, capsize=2, label=f"{label} (Brier {br:.4f})")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal")
        ax.set_xlabel("forecast P(BTC above strike)")
        ax.set_title(f"{sname}\n5 strikes pooled (80–120% of spot), n={len(s) * 5:,}", fontsize=9.5)
        ax.legend(loc="upper left", fontsize=8)
    axes[0].set_ylabel("observed frequency")
    fig.suptitle("Reliability of digital probabilities  (on the diagonal = calibrated; error bars: iid 95%, "
                 "non-overlapping only)", x=0.01, ha="left", fontweight="bold", fontsize=10)
    fig.tight_layout()
    save(fig, "reliability.png", folder)


def chart_vol_levels(df: pd.DataFrame, folder):
    """DVOL and trailing realised vol at each origin vs the vol that was realised over the next 30 days."""
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(df.index, df["sigma_realised_next30"] * 100, color=INK_2, lw=0.9, label="realised over the NEXT 30 days (outcome)")
    ax.plot(df.index, df["sigma_rv"] * 100, color=ORANGE, lw=1.1, label="trailing 30d realised (forecast)")
    ax.plot(df.index, df["sigma_dvol"] * 100, color=BLUE, lw=1.3, label="DVOL (forecast)")
    ax.set_ylabel("annualised vol, %")
    ax.legend(loc="upper right", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title("Vol forecasts at each 08:00 origin vs what was realised")
    save(fig, "vol_levels.png", folder)


# ── Phase 3: smile-based distributions ──────────────────────────────────────────────────────
SEQ_BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
            "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]


def _usd_k(ax, axis="y"):
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def chart_density_heatmap(surf, t0, spot, folder, max_days=60):
    """Risk-neutral density of BTC by horizon: x = days ahead, y = price, colour = density (log)."""
    from matplotlib.colors import LinearSegmentedColormap, LogNorm
    days = np.arange(0.25, max_days + 0.001, 0.25)
    F0 = surf.e[0].forward
    prices = np.linspace(F0 * 0.55, F0 * 1.6, 500)
    Z = np.zeros((len(prices), len(days)))
    pct = {q: [] for q in (0.05, 0.5, 0.95)}
    for j, d in enumerate(days):
        dist, _ = surf.distribution(d / 365, width=14)        # wide grid so the tails reach the plot edges
        Z[:, j] = np.interp(prices, dist.K, np.maximum(dist.density, 0), left=0, right=0)
        for q in pct:
            pct[q].append(dist.percentile(q))
    cmap = LinearSegmentedColormap.from_list("seq_blue", [SURFACE] + SEQ_BLUE)
    fig, ax = plt.subplots(figsize=(11, 6))
    zmax = Z.max()
    m = ax.pcolormesh(days, prices, np.maximum(Z, zmax * 1e-4), cmap=cmap, shading="auto",
                      norm=LogNorm(vmin=zmax * 1e-4, vmax=zmax))
    for q, ls in [(0.05, "--"), (0.5, "-"), (0.95, "--")]:
        ax.plot(days, pct[q], color=INK, lw=1, ls=ls)
        ax.annotate(f"{int(q*100)}%", (days[-1], pct[q][-1]), xytext=(4, 0), textcoords="offset points",
                    fontsize=8, color=INK_2, va="center")
    for e in surf.e:
        if e.T * 365 <= max_days:
            ax.axvline(e.T * 365, ymin=0.97, ymax=1.0, color=INK, lw=1.2)
    ax.axhline(spot, color=INK_2, lw=0.8, ls=":")
    cb = fig.colorbar(m, ax=ax, pad=0.06)
    cb.set_label("probability density per $ (log scale)")
    _usd_k(ax)
    ax.set_xlabel("days ahead (ticks on top = listed Deribit expiries; between them, total-variance interpolation)")
    ax.set_title(f"Risk-neutral density of BTC from the option smile  ·  snapshot {t0:%Y-%m-%d %H:%M} UTC  ·  "
                 f"index ${spot:,.0f}\n(lines: 5th, 50th, 95th percentile)")
    ax.grid(False)
    save(fig, "density_heatmap.png", folder)


def chart_smile_cone(surf, t0, spot, dvol, folder, max_days=30):
    """Smile-based percentile cone vs the phase-2 DVOL lognormal cone."""
    from src.models import dvol_lognormal as lm
    days = np.arange(0.25, max_days + 0.001, 0.25)
    qs = (0.05, 0.25, 0.50, 0.75, 0.95)
    sm_pct = {q: [] for q in qs}
    for d in days:
        dist, _ = surf.distribution(d / 365)
        for q in qs:
            sm_pct[q].append(dist.percentile(q))
    x = t0 + pd.to_timedelta(days, unit="D")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.fill_between(x, sm_pct[0.05], sm_pct[0.95], color=BAND_OUTER, lw=0, label="smile 5–95%")
    ax.fill_between(x, sm_pct[0.25], sm_pct[0.75], color=BAND_INNER, lw=0, label="smile 25–75%")
    ax.plot(x, sm_pct[0.5], color=BAND_LINE, lw=1.5, label="smile median")
    for i, q in enumerate(qs):
        ax.plot(x, lm.percentile(spot, dvol, q, days / lm.YEAR), color=ORANGE, lw=1.1, ls="--",
                label="DVOL lognormal 5/25/50/75/95%" if i == 0 else None)
        ax.annotate(f"{int(q*100)}%  smile \\${sm_pct[q][-1]:,.0f} · DVOL \\${lm.percentile(spot, dvol, q):,.0f}",
                    (x[-1], sm_pct[q][-1]), xytext=(6, 0), textcoords="offset points", fontsize=8, color=INK_2, va="center")
    ax.set_xlim(x[0], x[-1] + pd.Timedelta(days=13))
    _usd_k(ax)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(f"30-day cone: full option smile vs DVOL lognormal  ·  from {t0:%d %b %H:%M} UTC  ·  "
                 f"index ${spot:,.0f}  ·  DVOL {dvol*100:.1f}%")
    save(fig, "smile_vs_dvol_cone.png", folder)


def chart_expiry_densities(surf, diag, t0, spot, dvol, folder):
    """Each expiry's smile density vs the phase-2 lognormal (DVOL) at the same horizon."""
    from src.models import dvol_lognormal as lm
    from scipy.stats import norm
    n = len(surf.e)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(15, 3.2 * rows))
    for ax, e, (_, r) in zip(axes.flat, surf.e, diag.iterrows()):
        from src.models.smile import distribution_from_w
        dist = distribution_from_w(e.smile.w, e.forward, e.T)
        sd = np.sqrt(e.smile.w(0.0))
        lo, hi = e.forward * np.exp(-4.5 * sd), e.forward * np.exp(4 * sd)
        keep = (dist.K >= lo) & (dist.K <= hi)
        ax.fill_between(dist.K[keep], dist.density[keep], color=BAND_OUTER, lw=0)
        ax.plot(dist.K[keep], dist.density[keep], color=BLUE, lw=1.3, label="smile")
        mu, s = lm.params(dvol, e.T)
        K = dist.K[keep]
        f_ln = norm.pdf(np.log(K / spot), mu, s) / K           # lognormal density in price space
        ax.plot(K, f_ln, color=ORANGE, lw=1.1, ls="--", label="DVOL lognormal")
        p_sm, p_ln = dist.p_above(1.1 * spot), lm.prob_above(spot, 1.1 * spot, dvol, e.T)
        ax.set_title(f"{r['expiry']:%d %b %y}  ({e.T*365:.1f}d)\nP(>110% spot): smile {p_sm:.1%} · lognormal {p_ln:.1%}",
                     fontsize=9)
        ax.set_yticks([])
        _usd_k(ax, "x")
        ax.tick_params(axis="x", labelsize=7.5)
        ax.axvline(spot, color=INK_2, lw=0.7, ls=":")
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    axes.flat[0].legend(loc="upper left", fontsize=7.5)
    fig.suptitle(f"Risk-neutral density per expiry (snapshot {t0:%Y-%m-%d %H:%M} UTC): option smile vs DVOL lognormal "
                 f"(dotted = index ${spot:,.0f})", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "expiry_densities.png", folder)


def chart_smile_fits(surf, quotes, diag, t0, folder):
    """Market implied vols (bid-ask bars, mid dots) and the fitted smile, per expiry."""
    n = len(surf.e)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(15, 3.2 * rows))
    for ax, e, (_, r) in zip(axes.flat, surf.e, diag.iterrows()):
        q = quotes[quotes["expiry"] == r["expiry"]].sort_values("k")
        ax.vlines(q["k"], q["iv_bid"] * 100, q["iv_ask"] * 100, color=GRID, lw=2.2, label="bid–ask")
        ax.plot(q["k"], q["iv_mid"] * 100, "o", ms=3.5, color=INK, label="mid")
        pad = 0.15 * (q["k"].max() - q["k"].min())
        kk = np.linspace(q["k"].min() - pad, q["k"].max() + pad, 200)
        ax.plot(kk, np.sqrt(e.smile.w(kk) / e.T) * 100, color=BLUE, lw=1.5, label=f"{r['method'].upper()} fit")
        ax.set_title(f"{r['expiry']:%d %b %y} ({e.T*365:.1f}d) · n={len(q)} · RMSE {r['rmse_vol_pts']:.2f}",
                     fontsize=9)
        ax.tick_params(labelsize=7.5)
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("implied vol, %")
    for ax in axes[-1]:
        ax.set_xlabel("log-moneyness k = ln(K/F)")
    axes.flat[0].legend(loc="upper center", fontsize=7.5)
    fig.suptitle(f"Implied-vol smile per expiry with the fitted curve (snapshot {t0:%Y-%m-%d %H:%M} UTC; OTM options, "
                 "two-sided quotes; RMSE in vol points)",
                 x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "smile_fits.png", folder)


def chart_tail_breaches(breach: pd.DataFrame, folder):
    """How often BTC finished below the 5th / above the 95th percentile, per model (overlapping sample,
    Newey-West 95% error bars). Expected: 5% each."""
    b = breach[(breach["band"] == "5-95") & breach["side"].isin(["below", "above"])
               & breach["sample"].str.startswith("overlapping")]
    names = {"smile": "option smile", "dvol": "DVOL", "rv": "realised vol", "atm": "smile ATM vol\n(lognormal)"}
    colors = {"smile": AQUA, "dvol": BLUE, "rv": ORANGE, "atm": INK_2}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, side, title in [(axes[0], "below", "Down tail: finished below the 5th percentile"),
                            (axes[1], "above", "Up tail: finished above the 95th percentile")]:
        d = b[b["side"] == side].set_index("model").reindex([m for m in names if m in set(b["model"])])
        x = np.arange(len(d))
        ax.bar(x, d["observed"] * 100, color=[colors[m] for m in d.index], width=0.6,
               yerr=1.96 * d["se"] * 100, capsize=3, ecolor=INK_2)
        ax.axhline(5, color=INK, lw=1, ls="--")
        ax.text(-0.45, 5.15, "expected 5%", ha="left", va="bottom", fontsize=8, color=INK)
        ax.set_ylim(0, 17)
        for i, v in enumerate(d["observed"] * 100):
            ax.text(i, v / 2, f"{v:.1f}%", ha="center", color=SURFACE, fontsize=9, fontweight="bold")
        ax.set_xticks(x, [names[m] for m in d.index], fontsize=8.5)
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("% of 30-day windows (daily origins)")
    fig.suptitle("Tail misses by model  (error bars: Newey-West 95%)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, "tail_breaches.png", folder)


def main():
    matplotlib.use("Agg")                  # write files only, no window (notebooks keep inline plots)
    config.setup_logging()
    chart_coverage()
    chart_prices()
    chart_btc_dvol()
    chart_option_trades()
    chart_snapshot()


if __name__ == "__main__":
    main()
