"""
Short-horizon option distributions: scale the 08:00 UTC front-expiry smile to settlement times
under one day (noon / 17:00 New York), and validate against the Binance BTC/USDT price.

Scaling
-------
At origin t (08:00 UTC) the front expiry T1 (normally 08:00 UTC the next day) has a fitted
arbitrage-penalised SVI smile w1(k), k = ln(K/F1) (total variance). For a settlement time s < T1:

    w_s(k) = lambda * w1(k / lambda^alpha),     lambda = tau(t, s) / tau(t, T1)

  * tau is VARIANCE TIME: expected variance accumulated between two clock times, from an
    intraday profile of Binance 1-minute squared returns (src/intraday_vol.py), matched to the
    day type (weekday / weekend) and the US daylight-saving regime, with weekend days at their
    own level (~0.5x a weekday). Clock time instead: lambda = (s - t) / (T1 - t).
  * alpha = 0.5 keeps the smile fixed in standardised moneyness z = k / sqrt(w) (implied vol at
    a given z is unchanged; ATM skew grows like lambda^-1/2). Alternative: alpha fitted each day
    from Deribit's ~1-day vs ~1-week smiles (w_1d(k) ~ lambda_a w_1w(k / lambda_a^alpha) with
    lambda_a = w_1d(0)/w_1w(0)), used as an expanding median of PAST days only.
  * The front smile already prices the whole period to T1 (including any scheduled event), so
    events change only how that total is allocated in time, i.e. lambda, not the total.
  * Forward: ln F_s linear in clock time between the Deribit index at the origin and F1, times
    the Binance/Deribit-index basis observed at 07:59 UTC (the target is a Binance price).

Arbitrage checks on every forecast: butterfly (Gatheral's g >= 0, numerically on w_s) and
calendar (w_s(k) <= w1(k)) on a +/- 6 standard-deviation grid. With alpha = 0.5 a butterfly-free
w1 gives a butterfly-free w_s analytically (g_s(k) >= g_1(k/sqrt(lambda))); for other alpha it is
only checked numerically.

Event days (reference/us_macro_events.csv: CPI and NFP at 08:30 ET, FOMC statement at 14:00 ET,
from bls.gov and federalreserve.gov). Event-day PROFILE rather than a day multiplier: the extra
variance arrives at a known minute, and whether it falls before or after the settlement time
(CPI/NFP 12:30/13:30 UTC is before noon NY; FOMC 18:00/19:00 UTC is after noon but before 17:00
NY) is exactly what moves lambda. A multiplier would spread it over the whole day.
  Event excess, per prior event, in units of that day's normal level:
    x_e(tau) = r^2(release + tau) / V_ref - s_normal(release + tau),  tau in [-10, 120) minutes,
    V_ref = (variance outside the window that day) / (normal share outside the window),
  averaged over earlier events of the same type (at least MIN_EVENTS). Expected variance per
  minute on an event day = level * s_normal(m) + level * x(m - release).

No look-ahead: profiles and weekend level from the trailing 365 days (refitted monthly, on
non-event days); event excess from earlier events only; alpha from earlier days only; trades
strictly before 08:00 UTC. Forecasts start once a profile has >= 90 days of history.

Outputs: reports/short_horizon/. Run:  python -m src.short_horizon
"""
import glob
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kstest

import config
from src import intraday_vol as iv
from src import visuals
from src.clean_trades import COLUMNS, clean
from src.models import smile as sm
from src.phase3_hist import MIN_SPAN_SD, MIN_STRIKES, MIN_TRADES, WINDOW, basis_by_expiry

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "short_horizon"
OUT.mkdir(parents=True, exist_ok=True)
EVENTS_CSV = config.ROOT / "reference" / "us_macro_events.csv"
NY = "America/New_York"
YEAR_S = 365 * 86400
LOOKBACK, MIN_HISTORY = pd.Timedelta(days=365), pd.Timedelta(days=90)
EV_WIN = (-10, 120)                       # event window, minutes relative to the release
MIN_EVENTS = 6
ALPHA_GRID = np.round(np.arange(0.0, 1.51, 0.05), 2)
ALPHA_MIN_DAYS = 60
TARGETS = {"noon NY": 12, "17:00 NY": 17}   # NY hour; outcome = close of the Binance 1-min candle opening then
WEEK_RANGE = (5, 9)                       # days to expiry for the "1-week" smile


def month_key(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(year=ts.year, month=ts.month, day=1, tz="UTC")


# ── Events ──────────────────────────────────────────────────────────────────────────────────
def load_events() -> pd.DataFrame:
    e = pd.read_csv(EVENTS_CSV)
    e["release"] = (pd.to_datetime(e["date"] + " " + e["time_et"]).dt.tz_localize(NY).dt.tz_convert("UTC"))
    e["date_utc"] = e["release"].dt.normalize()
    return e[["event", "release", "date_utc"]]


# ── Variance model (no look-ahead) ──────────────────────────────────────────────────────────
class VarianceModel:
    """Normal shares per (weekend, US DST) from trailing non-event days, weekend level, and the
    mean event excess per type from earlier events. All in units of a normal weekday's variance."""

    def __init__(self, d: pd.DataFrame, events: pd.DataFrame, month_start: pd.Timestamp, excess: dict):
        hist = d[(d.index >= month_start - LOOKBACK) & (d.index < month_start)]
        self.ok = bool(len(hist)) and hist.index.min() <= month_start - MIN_HISTORY
        if not self.ok:
            return
        ev_days = set(events["date_utc"])
        normal = hist[~hist["date"].isin(ev_days)]
        self.shares = {}
        for wk in (False, True):
            for dst in (False, True):
                g = normal[(normal["weekend"] == wk) & (normal["us_dst"] == dst)]
                if g["date"].nunique() < 20:                         # thin season: pool across DST
                    g = normal[normal["weekend"] == wk]
                self.shares[(wk, dst)] = iv.share_profile(g).to_numpy()
        day = normal.groupby("date").agg(rv=("r2", "sum"), weekend=("weekend", "first"))
        self.weekend_level = float(day.loc[day.weekend, "rv"].mean() / day.loc[~day.weekend, "rv"].mean())
        # event excess: mean over events released before this month
        self.excess = {}
        for typ, lst in excess.items():
            prior = [x for rel, x in lst if rel < month_start]
            self.excess[typ] = np.mean(prior, axis=0) if len(prior) >= MIN_EVENTS else None

    def day_density(self, date: pd.Timestamp, events_on_day: list, use_events: bool) -> np.ndarray:
        """Expected variance per minute of a UTC day, in units of a normal weekday's variance."""
        wk = date.dayofweek >= 5
        noon = date + pd.Timedelta(hours=12)
        dst = (noon.tz_convert(NY).tz_localize(None) - noon.tz_localize(None)) == pd.Timedelta(hours=-4)
        level = self.weekend_level if wk else 1.0
        dens = level * self.shares[(wk, dst)].copy()
        if use_events:
            for typ, rel in events_on_day:
                x = self.excess.get(typ)
                if x is None:
                    continue
                m0 = int((rel - date).total_seconds() // 60) + EV_WIN[0]
                idx = np.arange(m0, m0 + len(x))
                keep = (idx >= 0) & (idx < 1440)
                dens[idx[keep]] += level * x[keep]
        return np.maximum(dens, 0.1 * level * self.shares[(wk, dst)])   # never below 10% of normal


def event_excess(d: pd.DataFrame, events: pd.DataFrame, models: dict) -> dict:
    """Per event: excess variance per minute in [-10, 120) around the release, in units of that
    day's normal level (the day's own non-window variance / the normal non-window share)."""
    out = {}
    by_date = {k: g for k, g in d.groupby("date")}
    for _, e in events.iterrows():
        m = models.get(month_key(e["release"]))
        g = by_date.get(e["date_utc"])
        if m is None or not m.ok or g is None:
            continue
        wk = e["date_utc"].dayofweek >= 5
        noon = e["date_utc"] + pd.Timedelta(hours=12)
        dst = (noon.tz_convert(NY).tz_localize(None) - noon.tz_localize(None)) == pd.Timedelta(hours=-4)
        s = m.shares[(wk, dst)]
        r2 = np.zeros(1440)
        r2[g["mod"].to_numpy()] = g["r2"].to_numpy()
        m0 = int((e["release"] - e["date_utc"]).total_seconds() // 60) + EV_WIN[0]
        win = np.arange(m0, m0 + EV_WIN[1] - EV_WIN[0])
        win = win[(win >= 0) & (win < 1440)]
        if len(win) < EV_WIN[1] - EV_WIN[0]:
            continue
        outside = np.ones(1440, bool)
        outside[win] = False
        v_ref = r2[outside].sum() / s[outside].sum()
        if not v_ref > 0:
            continue
        out.setdefault(e["event"], []).append((e["release"], r2[win] / v_ref - s[win]))
    return out


def tau(model: VarianceModel, t0: pd.Timestamp, t1: pd.Timestamp, ev_by_day: dict, use_events: bool) -> float:
    """Variance time between t0 and t1 (minute resolution), in normal-weekday-day units."""
    days = pd.date_range(t0.normalize(), (t1 - pd.Timedelta("1ns")).normalize(), freq="D")
    dens = np.concatenate([model.day_density(day, ev_by_day.get(day, []), use_events) for day in days])
    a = int((t0 - days[0]).total_seconds() // 60)
    b = int(np.ceil((t1 - days[0]).total_seconds() / 60))
    return float(dens[a:b].sum())


# ── Smile fits from trades before 08:00 ─────────────────────────────────────────────────────
def fit_expiry(origin, g, basis, idx_ref):
    T = (g["expiry"].iloc[0] - origin).total_seconds() / YEAR_S
    k = np.log(g["strike"] / (basis * g["index_price"]))
    per = pd.DataFrame({"strike": g["strike"], "k": k, "iv": g["iv"] / 100}).groupby("strike").agg(
        k=("k", "median"), iv=("iv", "median"), n=("iv", "size"))
    if len(g) < MIN_TRADES or len(per) < MIN_STRIKES or not (per["k"].min() < 0 < per["k"].max()):
        return None
    ks = per["k"].sort_values()
    atm_iv = float(np.interp(0, ks, per["iv"].reindex(ks.index)))
    if (per["k"].max() - per["k"].min()) / (atm_iv * np.sqrt(T)) < MIN_SPAN_SD:
        return None
    p, _ = sm.fit_svi(per["k"], per["iv"] ** 2 * T, per["n"])
    if p is None:
        return None
    return {"svi": p, "T": T, "F": basis * idx_ref, "per": per}


def fit_alpha(front, week) -> float:
    """alpha minimising the trade-weighted IV error of lambda * w_week(k / lambda^alpha) on the front's strikes."""
    lam = front["svi"].w(0.0) / week["svi"].w(0.0)
    if not 0 < lam < 1:
        return np.nan
    k, ivs, n = front["per"]["k"].to_numpy(), front["per"]["iv"].to_numpy(), front["per"]["n"].to_numpy()
    errs = [np.sum(n * (np.sqrt(np.maximum(lam * week["svi"].w(k / lam ** a), 1e-12) / front["T"]) - ivs) ** 2)
            for a in ALPHA_GRID]
    return float(ALPHA_GRID[int(np.argmin(errs))])


def numeric_g(wfun, k):
    w = np.maximum(wfun(k), 1e-14)
    w1 = np.gradient(w, k)
    w2 = np.gradient(w1, k)
    return (1 - k * w1 / (2 * w)) ** 2 - (w1 ** 2 / 4) * (1 / w + 0.25) + w2 / 2


# ── Daily forecasts ─────────────────────────────────────────────────────────────────────────
def day_inputs(t: pd.DataFrame, origin: pd.Timestamp):
    w = t.loc[origin - WINDOW: origin - pd.Timedelta("1ms")]
    w = w[w["expiry"] > origin]
    if w.empty:
        return None
    basis, _ = basis_by_expiry(w)
    idx_ref = w["index_price"].iloc[-1]
    days = pd.Series((basis.index - origin).total_seconds() / 86400, index=basis.index)
    front_exp = days[basis.notna()].idxmin() if basis.notna().any() else None
    if front_exp is None:
        return None
    front = fit_expiry(origin, w[w["expiry"] == front_exp], basis[front_exp], idx_ref)
    week = None
    wk = days[days.between(*WEEK_RANGE) & basis.notna()]
    if len(wk):
        e = (wk - 7).abs().idxmin()
        week = fit_expiry(origin, w[w["expiry"] == e], basis[e], idx_ref)
    return {"front": front, "front_expiry": front_exp, "week": week, "idx_ref": idx_ref}


def forecast(front, front_exp, origin, s, lam, alpha, idx_ref, b0):
    p, T1, F1 = front["svi"], front["T"], front["F"]
    Ts = (s - origin).total_seconds() / YEAR_S
    F = float(np.exp(np.log(idx_ref) + Ts / T1 * np.log(F1 / idx_ref))) * b0
    w_s = lambda k: lam * p.w(np.asarray(k) / lam ** alpha)
    dist = sm.distribution_from_w(w_s, F, Ts, n=2001, width=8.0)
    kk = np.linspace(-6, 6, 241) * np.sqrt(max(w_s(0.0), 1e-12))
    g = numeric_g(w_s, kk)[5:-5]                                   # drop finite-difference edges
    cal = float(np.max(w_s(kk) - p.w(kk)) / p.w(0.0))              # relative to the front's ATM total variance
    return dist, float(g.min()), cal


VARIANTS = {   # name: (time measure, use events, alpha source)
    "clock, a=0.5": ("clock", False, "0.5"),
    "vartime, a=0.5": ("vt", False, "0.5"),
    "vartime, a=fitted": ("vt", False, "fit"),
    "vartime+events, a=0.5": ("vt", True, "0.5"),
    "vartime+events, a=fitted": ("vt", True, "fit"),
}


def run(months_only: list[str] | None = None):
    closes = pd.concat(pd.read_parquet(f, columns=["close"]) for f in sorted(glob.glob(
        str(config.DATA_RAW / "binance_1m" / "BTCUSDT-1m-*.parquet"))))["close"].sort_index()
    d = iv.load_returns(1)
    events = load_events()
    ev_by_day = {}
    for _, e in events.iterrows():
        ev_by_day.setdefault(e["date_utc"], []).append((e["event"], e["release"]))
    months = pd.date_range(pd.Timestamp("2021-01-01", tz="UTC"), closes.index.max().normalize(), freq="MS")
    models = {m: VarianceModel(d, events, m, {}) for m in months}
    excess = event_excess(d, events, models)
    for m in months:                                               # now with event excess (earlier events only)
        models[m] = VarianceModel(d, events, m, excess)
    log.info("Variance models: %d months; events with excess: %s", len(models), {k: len(v) for k, v in excess.items()})

    rows, alphas = [], []
    files = sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet")))
    if months_only:
        files = [f for f in files if any(m in f for m in months_only)]
    for f in files:
        t, _ = clean(pd.read_parquet(f, columns=COLUMNS))
        for day in t.index.normalize().unique():
            origin = day + pd.Timedelta(hours=8)
            model = models.get(month_key(day))
            if model is None or not model.ok or origin + pd.Timedelta(hours=16) > closes.index.max():
                continue
            inp = day_inputs(t, origin)
            if inp is None or inp["front"] is None:
                rows.append({"origin": origin, "status": "no front fit"})
                continue
            front = inp["front"]
            a_fit = fit_alpha(front, inp["week"]) if inp["week"] is not None else np.nan
            past = [a for o, a in alphas if o < origin and np.isfinite(a)]
            a_used = float(np.median(past)) if len(past) >= ALPHA_MIN_DAYS else np.nan
            alphas.append((origin, a_fit))
            b0 = closes.get(origin - pd.Timedelta("1min"), np.nan) / inp["idx_ref"]
            T1 = inp["front_expiry"]
            base = {"origin": origin, "status": "ok", "front_days": (T1 - origin).total_seconds() / 86400,
                    "alpha_day_fit": a_fit, "alpha_used": a_used, "basis_binance": b0,
                    "event_types": ",".join(sorted({x for x, _ in ev_by_day.get(day, [])})),
                    "front_butterfly_min_g": float(sm.butterfly_g(front["svi"], np.linspace(-6, 6, 241) * np.sqrt(front["svi"].w(0.0))).min())}
            for tname, hour in TARGETS.items():
                # settlement on the SAME calendar date as the 08:00 UTC origin, at `hour` New York time
                cand_open = (pd.Timestamp(day.strftime("%Y-%m-%d")) + pd.Timedelta(hours=hour)).tz_localize(NY).tz_convert("UTC")
                s = cand_open + pd.Timedelta("1min")                       # candle close = 1 min after its open
                y = closes.get(cand_open, np.nan)
                if not np.isfinite(y) or not np.isfinite(b0) or s >= T1:
                    continue
                lam = {"clock": (s - origin) / (T1 - origin),
                       "vt": tau(model, origin, s, ev_by_day, False) / tau(model, origin, T1, ev_by_day, False),
                       "vt_ev": tau(model, origin, s, ev_by_day, True) / tau(model, origin, T1, ev_by_day, True)}
                ev_before = [x for x, rel in ev_by_day.get(day, []) if origin <= rel < s]
                for vname, (measure, use_ev, asrc) in VARIANTS.items():
                    alpha = 0.5 if asrc == "0.5" else a_used
                    if not np.isfinite(alpha):
                        continue
                    lm = lam["vt_ev"] if use_ev else lam[measure]
                    dist, gmin, cal = forecast(front, T1, origin, s, lm, alpha, inp["idx_ref"], b0)
                    pit = dist.pit(y)
                    rows.append({**base, "target": tname, "variant": vname, "settle": s, "y": y, "lambda": lm,
                                 "alpha": alpha, "events_before_target": ",".join(ev_before),
                                 "pit": pit, "logscore": dist.log_score(y), "mass": dist.mass(),
                                 "q05": float(dist.percentile(0.05)), "q95": float(dist.percentile(0.95)),
                                 "butterfly_min_g": gmin, "calendar_max_excess": cal})
        log.info("%s done (%d rows)", f[-15:-8], len(rows))
    return pd.DataFrame(rows), excess, models


# ── Scoring ─────────────────────────────────────────────────────────────────────────────────
def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


def score(df: pd.DataFrame, base="vartime, a=0.5") -> pd.DataFrame:
    rows = []
    for (target, variant), g in df.groupby(["target", "variant"]):
        n = len(g)
        lo5, hi5 = (g["pit"] < 0.05).sum(), (g["pit"] > 0.95).sum()
        r = {"target": target, "variant": variant, "days": n,
             "pit_var_ratio": g["pit"].var() / (1 / 12), "ks_p": kstest(g["pit"], "uniform").pvalue,
             "below_5%": lo5 / n, "below_ci": "%.3f-%.3f" % wilson(lo5, n),
             "above_95%": hi5 / n, "above_ci": "%.3f-%.3f" % wilson(hi5, n),
             "inside_25_75%": g["pit"].between(0.25, 0.75).mean(), "mean_logscore": g["logscore"].mean()}
        b = df[(df["target"] == target) & (df["variant"] == base)].set_index("origin")["logscore"]
        diff = (g.set_index("origin")["logscore"] - b).dropna()
        r["logscore_vs_base"] = diff.mean()
        r["logscore_vs_base_se"] = diff.std(ddof=1) / np.sqrt(len(diff)) if len(diff) > 1 else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


def event_table(excess: dict) -> pd.DataFrame:
    rows = []
    for typ, lst in excess.items():
        x = np.mean([v for _, v in lst], axis=0)
        cum = np.cumsum(x)
        t0 = -EV_WIN[0]
        rows.append({"event": typ, "events": len(lst), "extra_variance_day_units": cum[-1],
                     "share_by_+5min": cum[t0 + 5] / cum[-1], "share_by_+30min": cum[t0 + 30] / cum[-1],
                     "share_by_+60min": cum[t0 + 60] / cum[-1],
                     "first_5min_vs_normal_x": (x[t0:t0 + 5].sum() + 5 / 1440) / (5 / 1440)})
    return pd.DataFrame(rows)


def chart_events(excess: dict):
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = {"CPI": visuals.BLUE, "NFP": visuals.ORANGE, "FOMC": visuals.AQUA}
    tt = np.arange(*EV_WIN)
    for typ, lst in sorted(excess.items()):
        cum = np.cumsum(np.mean([v for _, v in lst], axis=0))
        ax.plot(tt, cum, color=colors.get(typ, visuals.INK_2), lw=2, label=f"{typ} (n={len(lst)})")
        ax.annotate(typ, (tt[-1], cum[-1]), xytext=(4, 0), textcoords="offset points", fontsize=8.5, color=visuals.INK_2, va="center")
    ax.axvline(0, color=visuals.INK_2, lw=0.8, ls="--")
    ax.set_xlabel("minutes since release")
    ax.set_ylabel("cumulative extra variance\n(fraction of a normal day's variance)")
    ax.set_title("Extra BTC variance around US macro releases")
    ax.legend(loc="upper left")
    fig.tight_layout()
    visuals.save(fig, "event_excess.png", OUT)


def chart_pit(df: pd.DataFrame):
    vs = list(VARIANTS)
    fig, axes = plt.subplots(len(TARGETS), len(vs), figsize=(3.0 * len(vs), 2.8 * len(TARGETS)), sharey=True, squeeze=False)
    for i, tname in enumerate(TARGETS):
        for j, v in enumerate(vs):
            ax = axes[i, j]
            g = df[(df["target"] == tname) & (df["variant"] == v)]["pit"]
            ax.hist(g, bins=10, range=(0, 1), color=visuals.BLUE, edgecolor=visuals.SURFACE, linewidth=2)
            ax.axhline(len(g) / 10, color=visuals.INK_2, lw=0.8, ls="--")
            ax.set_title(f"{tname}: {v}", fontsize=8.5)
            ax.set_xticks([0, 0.5, 1])
    fig.suptitle("PIT histograms (flat = calibrated; dashed = uniform)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    visuals.save(fig, "pit_histograms.png", OUT)


def main():
    config.setup_logging()
    df, excess, models = run()
    df.to_parquet(OUT / "forecasts.parquet")
    ok = df[df["status"] == "ok"].dropna(subset=["variant"])
    # common sample: days on which every variant exists for that target
    nvar = ok.groupby(["target", "origin"])["variant"].transform("nunique")
    common = ok[nvar == len(VARIANTS)]
    ev_day = common["event_types"].fillna("") != ""
    tables = {
        "all days": score(common), "excluding event days": score(common[~ev_day]),
        "event days only": score(common[ev_day]),
    }
    status = df.drop_duplicates("origin")["status"].value_counts()
    arb = ok.groupby("variant").agg(forecasts=("pit", "size"),
                                    butterfly_violations=("butterfly_min_g", lambda g: int((g < -1e-4).sum())),
                                    calendar_violations=("calendar_max_excess", lambda c: int((c > 1e-6).sum())),
                                    worst_g=("butterfly_min_g", "min"), worst_calendar=("calendar_max_excess", "max"))
    front_bfly = int((df.drop_duplicates("origin")["front_butterfly_min_g"] < -1e-4).sum())
    lam = ok[ok["variant"].isin(["clock, a=0.5", "vartime, a=0.5", "vartime+events, a=0.5"])].pivot_table(
        index="target", columns="variant", values="lambda", aggfunc="mean")
    alpha = ok.drop_duplicates("origin")[["alpha_day_fit", "alpha_used"]].describe()
    ev = event_table(excess)
    for name, t in tables.items():
        t.to_csv(OUT / f"scores_{name.replace(' ', '_')}.csv", index=False)
    arb.to_csv(OUT / "arbitrage_checks.csv")
    ev.to_csv(OUT / "event_excess.csv", index=False)
    chart_events(excess)
    chart_pit(common)
    f = lambda t, idx=False: t.to_string(index=idx, float_format=lambda v: f"{v:.4f}")
    lines = [f"# Short-horizon scaling of the 08:00 UTC front smile (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"Days with a forecast: {common['origin'].nunique()} (common sample, all variants), "
             f"{common['origin'].min():%Y-%m-%d} to {common['origin'].max():%Y-%m-%d}; event days: {common[ev_day]['origin'].nunique()}.",
             f"Fit status by day: {status.to_dict()}", "",
             *sum([[f"## Scores: {n}", "```", f(t), "```", ""] for n, t in tables.items()], []),
             "## Mean lambda (fraction of the front expiry's variance used)", "```", f(lam, True), "```", "",
             "## alpha: daily fits from ~1-day vs ~1-week smiles, and the expanding median used", "```", f(alpha, True), "```", "",
             "## Arbitrage checks on every scaled smile (g < -1e-4 = butterfly; w_s > w1 = calendar)", "```", f(arb, True), "```",
             f"Front smiles that themselves have butterfly g < -1e-4: {front_bfly} of {df['origin'].nunique()} days.", "",
             "## Event excess (full sample, descriptive; forecasts use earlier events only)", "```", f(ev), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Short horizon done -> %s", OUT)


if __name__ == "__main__":
    main()
