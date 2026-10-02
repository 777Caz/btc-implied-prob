"""
First prediction-market analysis (no options yet): are Kalshi BTC "above K" prices calibrated?

Data: the backfill (src/pm_backfill.py). KXBTCD markets with strike_type "greater" (YES pays $1
if the CF Benchmarks BRTI 60-second average at settlement is above the strike), events settling at
12:00 or 17:00 New York.

Quotes. At each lead time before settlement (24h, 8h, 1h), the forward-filled YES bid and ask at
the minute close_time - lead (the last state of the book at that moment). Only two-sided quotes
(an empty side is NaN in the filled data). mid = (bid + ask)/2. 12:00 NY events open only 1 hour
before settlement, so 24h/8h quotes exist only for 17:00 events.
Also quoted at 08:00 UTC on the settlement day (13-14h before a 17:00 NY settlement), the time of
Deribit's daily expiry and of our option surfaces, so these quotes line up with options later.
12:00 NY events can't be compared with 08:00 surfaces: they open only at 11:00 NY (15:00/16:00 UTC).

Effective N. Every strike in an event settles on the same BRTI print, and a 12:00 and a 17:00
event on the same day share most of the BTC path. So the number of independent outcomes is
roughly the number of SETTLEMENT DAYS, not markets. Every table reports it (`days`), and
standard errors / bootstrap CIs are clustered by event (= day within one lead x event-hour cell).

PRIMARY TEST: logistic recalibration  P(YES) = sigmoid(a + b * logit(mid)).
  Perfect calibration: a = 0, b = 1. b > 1: prices too compressed toward 50c, i.e. longshots
  overpriced and favourites underpriced (favourite-longshot bias). b < 1: prices too extreme.
  a != 0: YES systematically over/under-priced. Cluster-robust (sandwich) SEs.
  Holdout: estimate on events settling before 2026-01-01; re-estimate on 2026 events; and apply
  the pre-2026 (a, b) to 2026 mids out of sample, comparing Brier scores of raw vs recalibrated.

DESCRIPTIVE (no multiple-testing control; read as context, not evidence):
  reliability by mid bin, Brier score, and a per-bucket trade check (hold to settlement):
    taker        buy YES at the ask / buy NO at 1 - bid, pay the taker fee
                 ceil(0.07 * C * P * (1 - P)) to the cent per order, for C = 100 and C = 10 contracts
    maker-post   OPTIMISTIC: buy YES by resting at the bid / NO by resting at 1 - ask, no fee.
                 KXBTCD/KXBTC have fee_type "quadratic" (API, GET /series), not
                 "quadratic_with_maker_fees", so makers pay nothing. Assumes every resting order
                 fills at that minute's quote; real fills are uncertain and adversely selected
                 (you get filled when the price moves against you).
  capacity     median best-level size per mid bucket from the live snapshots (contracts and $).

Outputs: reports/pm/kalshi_calibration/
Run:  python -m src.pm_kalshi_calib
"""
import glob
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from src import visuals

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "pm" / "kalshi_calibration"
OUT.mkdir(parents=True, exist_ok=True)
CATALOG = config.DATA_RAW / "pm_history" / "kalshi" / "markets.parquet"
FILLED = config.DATA_PROCESSED / "pm_history" / "kalshi_1m" / "KXBTCD"
NY = "America/New_York"

LEADS = {"24h": pd.Timedelta("24h"), "8h": pd.Timedelta("8h"), "1h": pd.Timedelta("1h")}
AT_0800 = "08:00 UTC"                         # fixed clock time, aligned with Deribit's 08:00 surfaces
QUOTE_TIMES = [*LEADS, AT_0800]
HOLDOUT_START = pd.Timestamp("2026-01-01", tz="UTC")
BINS = np.array([0, .05, .10, .20, .30, .40, .50, .60, .70, .80, .90, .95, 1.0])
ORDER_SIZES = (100, 10)
N_BOOT = 2000
RNG = np.random.default_rng(11)
EPS = 0.005                                   # clip mids away from 0/1 before logit
CELL = ["lead", "event_hour"]                     # one analysis cell = lead time x event hour


# ── Quotes at lead times ────────────────────────────────────────────────────────────────────
def quotes_at_leads() -> pd.DataFrame:
    cat = pd.read_parquet(CATALOG)
    cat = cat[(cat["series"] == "KXBTCD") & (cat["strike_type"] == "greater") & cat["outcome"].notna()]
    cat = cat.set_index("ticker")
    rows = []
    for f in sorted(glob.glob(str(FILLED / "*.parquet"))):
        q = pd.read_parquet(f, columns=["t", "ticker", "bid", "ask"])
        q = q[q["ticker"].isin(cat.index)]
        if q.empty:
            continue
        q = q.set_index(["ticker", "t"]).sort_index()
        for tk in q.index.get_level_values(0).unique():
            m, qt = cat.loc[tk], q.loc[tk]
            times = {name: (m["close_time"] - lead).floor("min") for name, lead in LEADS.items()}
            times[AT_0800] = m["close_time"].normalize() + pd.Timedelta(hours=8)    # same UTC day as settlement
            for name, t in times.items():
                if t < m["open_time"].ceil("min") or t >= m["close_time"] or t not in qt.index:
                    continue
                r = qt.loc[t]
                rows.append({"ticker": tk, "event": m["event"], "settle": m["settle"], "lead": name,
                             "strike": m["floor_strike"], "bid": float(r["bid"]), "ask": float(r["ask"]),
                             "outcome": m["outcome"]})
    d = pd.DataFrame(rows)
    d["event_hour"] = d["settle"].dt.tz_convert(NY).dt.hour.map({12: "12:00 NY", 17: "17:00 NY"})
    d["day"] = d["settle"].dt.tz_convert(NY).dt.date.astype(str)
    d["period"] = np.where(d["settle"] < HOLDOUT_START, "pre-2026", "2026")
    d["two_sided"] = d["bid"].notna() & d["ask"].notna() & (d["ask"] > d["bid"])
    return d


# ── Statistics helpers ──────────────────────────────────────────────────────────────────────
def n_info(g: pd.DataFrame) -> dict:
    return {"n": len(g), "n_events": g["event"].nunique(), "days": g["day"].nunique()}


def cluster_boot(df: pd.DataFrame, values, cluster="event", n=N_BOOT) -> tuple[float, float]:
    """95% CI of the MEAN of a per-row quantity, resampling whole clusters with replacement.
    `values` is a column name or a function df -> per-row array. Vectorised: per-cluster sums and
    counts, then mean = sum(resampled sums) / sum(resampled counts)."""
    v = np.asarray(df[values] if isinstance(values, str) else values(df), float)
    codes, _ = pd.factorize(df[cluster])
    k = codes.max() + 1 if len(codes) else 0
    if k < 5:
        return np.nan, np.nan
    sums, cnts = np.bincount(codes, weights=v, minlength=k), np.bincount(codes, minlength=k).astype(float)
    idx = RNG.integers(0, k, size=(n, k))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return float(np.quantile(means, .025)), float(np.quantile(means, .975))


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def logistic_cluster(y: np.ndarray, x: np.ndarray, groups: np.ndarray) -> dict:
    """Logistic regression y ~ a + b x by Newton-Raphson, with cluster-robust (sandwich) SEs."""
    X = np.column_stack([np.ones_like(x), x])
    beta = np.array([0.0, 1.0])
    for _ in range(50):
        p = sigmoid(X @ beta)
        step = np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]), X.T @ (y - p))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    p = sigmoid(X @ beta)
    Hinv = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))
    S = pd.DataFrame(X * (y - p)[:, None]).groupby(groups).sum().to_numpy()
    G = len(S)
    V = Hinv @ (S.T @ S * G / (G - 1)) @ Hinv                    # small-sample cluster correction
    se = np.sqrt(np.diag(V))
    return {"a": beta[0], "a_se": se[0], "z_a=0": beta[0] / se[0],
            "b": beta[1], "b_se": se[1], "z_b=1": (beta[1] - 1) / se[1],
            "b_ci_lo": beta[1] - 1.96 * se[1], "b_ci_hi": beta[1] + 1.96 * se[1]}


def kalshi_taker_fee(price, contracts: int) -> np.ndarray:
    """Taker fee per contract (dollars): ceil(0.07 * C * P * (1-P)) to the cent, divided by C."""
    price = np.asarray(price, float)
    return np.ceil(np.round(0.07 * contracts * price * (1 - price) * 100, 6)) / 100 / contracts


# ── PRIMARY: logit recalibration with a 2026 holdout ────────────────────────────────────────
def primary_logit(q: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    fits, oos = [], []
    for cell, g in q.groupby(CELL):
        for period in ("pre-2026", "2026", "all"):
            s = g if period == "all" else g[g["period"] == period]
            if s["event"].nunique() < 10:
                continue
            f = logistic_cluster(s["outcome"].to_numpy(float), logit(s["mid"].to_numpy()), s["event"].to_numpy())
            fits.append({"lead": cell[0], "event_hour": cell[1], "period": period, **n_info(s), **f})
        est, hold = g[g["period"] == "pre-2026"], g[g["period"] == "2026"]
        if est["event"].nunique() >= 10 and hold["event"].nunique() >= 10:
            f = logistic_cluster(est["outcome"].to_numpy(float), logit(est["mid"].to_numpy()), est["event"].to_numpy())
            h = hold.assign(recal=sigmoid(f["a"] + f["b"] * logit(hold["mid"].to_numpy())))
            diff = lambda x: (x["recal"] - x["outcome"]) ** 2 - (x["mid"] - x["outcome"]) ** 2
            lo, hi = cluster_boot(h, diff)
            oos.append({"lead": cell[0], "event_hour": cell[1], **n_info(h), "a_pre2026": f["a"], "b_pre2026": f["b"],
                        "brier_raw_mid": ((h["mid"] - h["outcome"]) ** 2).mean(),
                        "brier_recalibrated": ((h["recal"] - h["outcome"]) ** 2).mean(),
                        "diff_recal_minus_raw": diff(h).mean(), "diff_ci_lo": lo, "diff_ci_hi": hi})
    return pd.DataFrame(fits), pd.DataFrame(oos)


# ── DESCRIPTIVE ─────────────────────────────────────────────────────────────────────────────
def reliability_and_brier(q: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rel, brier = [], []
    for (lead, hour, period), g in q.assign(p2=q["period"]).groupby(CELL + ["p2"]):
        for sample, s in ((period, g),):
            s = s.assign(bin=pd.cut(s["mid"], BINS, include_lowest=True))
            for b, gb in s.groupby("bin", observed=True):
                lo, hi = cluster_boot(gb, "outcome")
                rel.append({"lead": lead, "event_hour": hour, "period": sample, "bin": str(b), **n_info(gb),
                            "mean_mid": gb["mid"].mean(), "observed": gb["outcome"].mean(), "ci_lo": lo, "ci_hi": hi})
    for cell, g in q.groupby(CELL):
        for period in ("pre-2026", "2026", "all"):
            s = g if period == "all" else g[g["period"] == period]
            if s.empty:
                continue
            bs = ((s["mid"] - s["outcome"]) ** 2).mean()
            base = s["outcome"].mean()
            lo, hi = cluster_boot(s, lambda x: (x["mid"] - x["outcome"]) ** 2)
            brier.append({"lead": cell[0], "event_hour": cell[1], "period": period, **n_info(s), "brier": bs,
                          "ci_lo": lo, "ci_hi": hi, "base_rate": base, "skill_vs_base_rate": 1 - bs / (base * (1 - base)),
                          "median_spread_c": (s["ask"] - s["bid"]).median() * 100})
    return pd.DataFrame(rel), pd.DataFrame(brier)


def trade_variants(q: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-contract P&L of buying YES / NO, for each execution assumption."""
    y = q["outcome"]
    out = {}
    for c in ORDER_SIZES:
        no_px = 1 - q["bid"]
        out[f"taker, {c} contracts"] = pd.DataFrame({
            "yes_cost": q["ask"], "yes_pnl": y - q["ask"] - kalshi_taker_fee(q["ask"], c),
            "no_cost": no_px, "no_pnl": (1 - y) - no_px - kalshi_taker_fee(no_px, c)})
    out["maker-post (OPTIMISTIC: assumes fills)"] = pd.DataFrame({
        "yes_cost": q["bid"], "yes_pnl": y - q["bid"],
        "no_cost": 1 - q["ask"], "no_pnl": (1 - y) - (1 - q["ask"])})
    return out


def trade_check(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant, pnl in trade_variants(q).items():
        d = pd.concat([q[CELL + ["event", "day", "mid"]], pnl], axis=1)
        d["bin"] = pd.cut(d["mid"], BINS, include_lowest=True)
        for (lead, hour, b), g in d.groupby(CELL + ["bin"], observed=True):
            r = {"variant": variant, "lead": lead, "event_hour": hour, "bin": str(b), **n_info(g)}
            for side in ("yes", "no"):
                r[f"{side}_pnl_c"] = g[f"{side}_pnl"].mean() * 100
                r[f"{side}_ci_lo"], r[f"{side}_ci_hi"] = cluster_boot(g, lambda x, s=side: x[f"{s}_pnl"] * 100)
                r[f"{side}_return_per_$"] = g[f"{side}_pnl"].sum() / g[f"{side}_cost"].sum()
            rows.append(r)
    return pd.DataFrame(rows)


def capacity_from_snapshots() -> pd.DataFrame:
    files = glob.glob(str(config.SNAPSHOTS_DIR / "*" / "predmarkets_*.parquet"))
    s = pd.concat(pd.read_parquet(f) for f in files)
    k = s[(s["venue"] == "kalshi") & (s["kind"] == "above") & s["event"].str.startswith("KXBTCD")
          & s["yes_bid"].notna() & s["yes_ask"].notna()].copy()
    k["mid"] = (k["yes_bid"] + k["yes_ask"]) / 2
    k["bin"] = pd.cut(k["mid"], BINS, include_lowest=True)
    k["day"] = k["snapshot_time"].dt.date
    g = k.groupby("bin", observed=True)
    return pd.DataFrame({"quotes": g.size(), "snapshots": g["snapshot_time"].nunique(), "days": g["day"].nunique(),
                         "median_bid_size": g["yes_bid_size"].median(), "median_ask_size": g["yes_ask_size"].median(),
                         "median_$_at_ask": g.apply(lambda x: (x["yes_ask_size"] * x["yes_ask"]).median(), include_groups=False),
                         "median_$_NO_at_bid": g.apply(lambda x: (x["yes_bid_size"] * (1 - x["yes_bid"])).median(), include_groups=False)})


def chart_reliability(rel: pd.DataFrame):
    rel = rel[rel["period"].isin(["pre-2026", "2026"])]
    leads = [l for l in QUOTE_TIMES if l in set(rel["lead"])]
    hours = sorted(rel["event_hour"].unique())
    fig, axes = plt.subplots(len(hours), len(leads), figsize=(3.4 * len(leads), 3.4 * len(hours)),
                             squeeze=False, sharex=True, sharey=True)
    style = {"pre-2026": (visuals.BLUE, "o", "pre-2026 (estimation)"), "2026": (visuals.ORANGE, "s", "2026 (holdout)")}
    for i, h in enumerate(hours):
        for j, l in enumerate(leads):
            ax = axes[i, j]
            ax.plot([0, 1], [0, 1], color=visuals.INK_2, lw=0.8, ls="--")
            cell = rel[(rel["lead"] == l) & (rel["event_hour"] == h)]
            if cell.empty:
                ax.text(0.5, 0.5, "no quotes\n(market not open yet)", ha="center", va="center", color=visuals.INK_2)
            for period, r in cell.groupby("period"):
                c, mk, lab = style[period]
                ax.errorbar(r["mean_mid"], r["observed"], yerr=[r["observed"] - r["ci_lo"], r["ci_hi"] - r["observed"]],
                            fmt=mk, ms=4, color=c, ecolor=c, elinewidth=1, capsize=0, label=lab)
            ax.set_title(f"{h}, {l} before", fontsize=9.5)
            ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            if i == len(hours) - 1:
                ax.set_xlabel("Kalshi mid (YES price)")
            if j == 0:
                ax.set_ylabel("share that settled YES")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper right", ncol=2)
    fig.suptitle("Kalshi BTC above-K: reliability (95% CI, clustered by event)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    visuals.save(fig, "reliability.png", OUT)


def main():
    config.setup_logging()
    d = quotes_at_leads()
    d.to_parquet(OUT / "quotes_at_leads.parquet")
    avail = d.groupby(CELL + ["period"]).agg(markets=("ticker", "size"), n_events=("event", "nunique"),
                                            days=("day", "nunique"), two_sided_share=("two_sided", "mean"))
    q = d[d["two_sided"]].copy()
    q["mid"] = (q["bid"] + q["ask"]) / 2
    fits, oos = primary_logit(q)
    rel, brier = reliability_and_brier(q)
    trades = trade_check(q)
    cap = capacity_from_snapshots()
    for name, t, idx in [("availability", avail, True), ("primary_logit", fits, False), ("primary_holdout_oos", oos, False),
                         ("reliability", rel, False), ("brier", brier, False), ("trades", trades, False),
                         ("capacity_snapshots", cap, True)]:
        t.to_csv(OUT / f"{name}.csv", index=idx)
    chart_reliability(rel)
    fmt = lambda t, idx=False: t.to_string(index=idx, float_format=lambda v: f"{v:.4f}")
    lines = [f"# Kalshi BTC above-K calibration (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"Markets {d['ticker'].nunique()}, events {d['event'].nunique()}, settlement days {d['day'].nunique()}, "
             f"{d['settle'].min():%Y-%m-%d} to {d['settle'].max():%Y-%m-%d}. `days` = effective N (independent outcomes).", "",
             "## Quote availability (two-sided share)", "```", fmt(avail, True), "```",
             "## PRIMARY: P(YES) = sigmoid(a + b logit(mid)); calibrated = (a=0, b=1); b>1 = favourite-longshot bias",
             "SEs clustered by event. Estimation = events before 2026-01-01, holdout = 2026.", "```", fmt(fits), "```",
             "### Out of sample: pre-2026 recalibration applied to 2026 (negative diff = recalibration helps)",
             "```", fmt(oos), "```", "",
             "## DESCRIPTIVE (not tests): Brier score of the mid", "```", fmt(brier), "```",
             "## DESCRIPTIVE: trade check, P&L in cents per contract (95% cluster-bootstrap CI)",
             "maker-post is OPTIMISTIC (assumes resting orders fill at the quote, no adverse selection).",
             "```", fmt(trades), "```",
             "## Capacity note: best-level size in live snapshots (contracts; indicative, few snapshots)",
             "```", fmt(cap, True), "```",
             "## DESCRIPTIVE: reliability by mid bin", "```", fmt(rel), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Kalshi calibration done -> %s", OUT)


if __name__ == "__main__":
    main()
