"""
Phase 3, historical part: daily smile surfaces from trades, and 30-day calibration tests.

For each day d, at 08:00 UTC (same origin as phase 2):
  1. Take cleaned trades (src/clean_trades.py) in the window [08:00 - WINDOW, 08:00).
  2. Forward per expiry from put-call parity (src/forwards.py) as a basis ratio F/index. Expiries
     without enough call/put pairs get the basis interpolated from the other expiries (ln basis
     linear in T), and are flagged.
  3. Per trade: k = ln(K / (basis * index at trade time)), and implied vol from the trade. Trades
     are pooled per strike (median k and IV, weight = number of trades) so busy strikes count more
     but single prints can't dominate. Total variance at 08:00: w = iv^2 * T(08:00).
  4. Quality gates per expiry (else the expiry is skipped that day):
       >= MIN_TRADES trades, >= MIN_STRIKES distinct strikes, strikes on BOTH sides of the forward,
       and a log-moneyness span >= MIN_SPAN_SD ATM standard deviations. Without both sides and some
       spread, the smile's skew and curvature are not identified, so SVI would be extrapolating.
  5. Fit arbitrage-penalised SVI (src/models/smile.py), record butterfly / vertical / calendar checks.
  6. 30-day distribution: total-variance interpolation between the two fitted expiries that
     bracket exactly 30 days (no extrapolation allowed), then Breeden-Litzenberger.
  7. Score it against the Deribit delivery price 30 days later, like phase 2.
"""
import glob
import logging
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

import config
from src import calibration as cal
from src import phase2, visuals
from src.clean_trades import COLUMNS, clean
from src.forwards import parity_pairs, MIN_PAIRS
from src.models import dvol_lognormal as lm
from src.models import smile as sm

log = logging.getLogger(__name__)
OUT = config.PHASE3_DIR

WINDOW = pd.Timedelta("8h")       # 00:00-08:00 UTC
MIN_TRADES, MIN_STRIKES, MIN_SPAN_SD = 15, 5, 1.0
YEAR_S = 365 * 86400
HORIZON_T = lm.DAYS / lm.YEAR
STRIKES = phase2.STRIKES


def basis_by_expiry(w: pd.DataFrame) -> pd.Series:
    """Parity basis F/index per expiry; missing expiries interpolated in T (ln basis linear)."""
    pairs = parity_pairs(w)
    g = pairs.groupby("expiry")["basis"].agg(["median", "size"])
    g = g[g["size"] >= MIN_PAIRS]["median"]
    expiries = pd.Index(sorted(w["expiry"].unique()))
    if g.empty:
        return pd.Series(np.nan, index=expiries), pd.Series(False, index=expiries)
    t_have = np.array([(e - expiries[0]).total_seconds() for e in g.index])
    t_all = np.array([(e - expiries[0]).total_seconds() for e in expiries])
    b = np.exp(np.interp(t_all, t_have, np.log(g.to_numpy())))
    return pd.Series(b, index=expiries), pd.Series(expiries.isin(g.index), index=expiries)


def fit_day(args):
    """Everything for one origin: per-expiry fits (diagnostics rows) and the 30-day distribution."""
    origin, w, s0, s_t = args
    rows, smiles = [], []
    if w.empty:
        return rows, None
    basis, direct = basis_by_expiry(w)
    idx_ref = w["index_price"].iloc[-1]
    for expiry, g in w.groupby("expiry"):
        T = (expiry - origin).total_seconds() / YEAR_S
        row = {"origin": origin, "expiry": expiry, "T_days": T * 365, "n_trades": len(g),
               "basis": basis.get(expiry, np.nan), "basis_from_parity": bool(direct.get(expiry, False))}
        if np.isnan(row["basis"]):
            rows.append({**row, "status": "no forward"}); continue
        k = np.log(g["strike"] / (row["basis"] * g["index_price"]))
        per = pd.DataFrame({"strike": g["strike"], "k": k, "iv": g["iv"] / 100}).groupby("strike").agg(
            k=("k", "median"), iv=("iv", "median"), n=("iv", "size"))
        atm_iv = float(np.interp(0, per["k"].sort_values(), per["iv"].reindex(per["k"].sort_values().index)))
        span_sd = (per["k"].max() - per["k"].min()) / (atm_iv * np.sqrt(T))
        row.update(n_strikes=len(per), k_min=per["k"].min(), k_max=per["k"].max(), span_sd=span_sd)
        reason = ("few trades" if len(g) < MIN_TRADES else "few strikes" if len(per) < MIN_STRIKES
                  else "one-sided strikes" if not (per["k"].min() < 0 < per["k"].max())
                  else "narrow strike span" if span_sd < MIN_SPAN_SD else None)
        if reason:
            rows.append({**row, "status": reason}); continue
        p, _ = sm.fit_svi(per["k"], per["iv"] ** 2 * T, per["n"])
        if p is None:
            rows.append({**row, "status": "fit failed"}); continue
        F = row["basis"] * idx_ref
        kk = np.linspace(-6, 6, 121) * np.sqrt(max(p.w(0.0), 1e-8))
        rmse = float(np.sqrt(np.average((np.sqrt(p.w(per["k"]) / T) - per["iv"]) ** 2, weights=per["n"])))
        rows.append({**row, "status": "ok", "forward": F, "rmse_vol_pts": rmse * 100,
                     "atm_iv": float(np.sqrt(p.w(0.0) / T)),
                     "butterfly_arb": bool(sm.butterfly_g(p, kk).min() < -1e-4),
                     "vertical_arb": bool(sm.prob_above_from_smile(p, kk).max() > 1 + 1e-3)})
        smiles.append(sm.ExpirySmile(T, F, p, float(per["k"].min()), float(per["k"].max())))

    if not smiles:
        return rows, None
    surf = sm.Surface(smiles)
    viol = {round(v[0], 10) for v in surf.calendar_violations(tol=1e-5)}
    for r in rows:
        if r["status"] == "ok":
            r["calendar_arb_with_next"] = round(r["T_days"] / 365, 10) in viol

    Ts = [e.T for e in surf.e]
    if not (min(Ts) <= HORIZON_T <= max(Ts)) or np.isnan(s_t):
        return rows, None                                   # need two expiries bracketing 30 days
    dist, _ = surf.distribution(HORIZON_T)
    w_of_k, F30, _ = surf.at(HORIZON_T)
    atm30 = float(np.sqrt(w_of_k(0.0) / HORIZON_T))
    out = {"origin": origin, "forward_30d": F30, "atm_iv_30d": atm30, "mass": dist.mass(),
           "mean_over_F": dist.mean() / F30,
           "pit_smile": dist.pit(s_t), "logscore_smile": dist.log_score(s_t)}
    for q in (0.05, 0.25, 0.50, 0.75, 0.95):
        out[f"q{int(q*100):02d}_smile"] = float(dist.percentile(q))
    for x in STRIKES:
        out[f"p{int(x*100)}_smile"] = float(dist.p_above(x * s0))
    # diagnostic: lognormal with the smile's own 30d ATM vol and forward (no skew / fat tails)
    mu, s = -0.5 * atm30**2 * HORIZON_T, atm30 * np.sqrt(HORIZON_T)
    from scipy.stats import norm
    out["pit_atm"] = float(norm.cdf((np.log(s_t / F30) - mu) / s))
    out["logscore_atm"] = float(norm.logpdf(np.log(s_t / F30), mu, s))
    for x in STRIKES:
        out[f"p{int(x*100)}_atm"] = float(norm.cdf((np.log(F30 / (x * s0)) + mu) / s))
    return rows, out


def month_tasks(path: str, origins: pd.DataFrame):
    t = pd.read_parquet(path, columns=COLUMNS)
    t, _ = clean(t)
    tasks = []
    for day in t.index.normalize().unique():
        origin = day + pd.Timedelta(hours=8)
        if origin not in origins.index:
            continue
        w = t.loc[origin - WINDOW: origin - pd.Timedelta("1ms")]
        w = w[w["expiry"] > origin + pd.Timedelta(days=1)]           # >= 1 day left at 08:00
        tasks.append((origin, w, origins.at[origin, "s0"], origins.at[origin, "s_t"]))
    return tasks


def build(max_workers: int = 8):
    p2 = phase2.build_forecasts()                         # s0, s_t, DVOL + RV forecasts per origin
    delivery, _ = phase2.load_inputs()
    origins = pd.DataFrame({"s0": delivery, "s_t": delivery.reindex(delivery.index + phase2.HORIZON).to_numpy()})
    diag, dists = [], []
    files = sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet")))
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        for f in files:
            tasks = month_tasks(f, origins)
            for rows, out in ex.map(fit_day, tasks, chunksize=4):
                diag += rows
                if out:
                    dists.append(out)
            log.info("%s: %d origins fitted", f[-15:-8], len(tasks))
    diag = pd.DataFrame(diag)
    smile = pd.DataFrame(dists).set_index("origin")
    df = p2.join(smile, how="inner")                      # common sample: all three models available
    for x in STRIKES:
        df[f"y{int(x*100)}"] = (df["s_t"] > x * df["s0"]).astype(float)
    return diag, df


MODELS3 = {"smile": "option smile (SVI)", "dvol": "DVOL lognormal", "rv": "realised-vol lognormal",
           "atm": "smile ATM vol, lognormal (diagnostic)"}


def run_tests(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    breach, pit, digital, compare = [], [], [], []
    for name, s in phase2.samples(df).items():
        ov = name.startswith("overlapping")
        for m in MODELS3:
            if f"pit_{m}" not in s:
                continue
            breach.append(cal.breach_table(s, m, ov).assign(sample=name))
            pit.append({**cal.pit_summary(s, m, ov), "sample": name})
            for x in STRIKES:
                p, y = s[f"p{int(x*100)}_{m}"], s[f"y{int(x*100)}"]
                digital.append({"sample": name, "model": m, "strike": f"{int(x*100)}%", "n": len(s),
                                "mean_forecast": p.mean(), "observed": y.mean(), "brier": cal.brier(p, y).mean()})
        groups = {f"{int(x*100)}%": [x] for x in STRIKES}
        groups |= {"down tail (80%, 90%)": [0.8, 0.9], "up tail (110%, 120%)": [1.1, 1.2], "all strikes": STRIKES}
        for other in ("dvol", "rv", "atm"):
            for g, xs in groups.items():
                loss = {m: np.mean([cal.brier(s[f"p{int(x*100)}_{m}"], s[f"y{int(x*100)}"]) for x in xs], axis=0)
                        for m in ("smile", other)}
                compare.append({"sample": name, "vs": other, "metric": f"Brier {g}", "smile": loss["smile"].mean(),
                                "other": loss[other].mean(), **cal.compare_losses(loss["smile"], loss[other], ov)})
            compare.append({"sample": name, "vs": other, "metric": "log score (higher = better)",
                            "smile": s["logscore_smile"].mean(), "other": s[f"logscore_{other}"].mean(),
                            **cal.compare_losses(-s["logscore_smile"], -s[f"logscore_{other}"], ov)})
    return {
        "breach": pd.concat(breach, ignore_index=True)[["sample", "model", "band", "side", "n", "expected", "observed", "se", "p_value"]],
        "pit": pd.DataFrame(pit)[["sample", "model", "n", "mean_pit", "mean_pit_p", "var_ratio", "ks_stat", "ks_p", "ks_p_note"]],
        "digital": pd.DataFrame(digital),
        "compare": pd.DataFrame(compare)[["sample", "vs", "metric", "smile", "other", "mean_diff", "se", "z", "p_value"]],
    }


def fit_summary(diag: pd.DataFrame) -> dict[str, pd.DataFrame]:
    status = diag["status"].value_counts().rename("expiry_days").to_frame()
    status["share_%"] = status["expiry_days"] / len(diag) * 100
    ok = diag[diag["status"] == "ok"]
    arb = pd.DataFrame({
        "expiry_days_fitted": [len(ok)],
        "rmse_vol_pts_median": [ok["rmse_vol_pts"].median()],
        "rmse_vol_pts_p90": [ok["rmse_vol_pts"].quantile(0.9)],
        "butterfly_arb": [int(ok["butterfly_arb"].sum())],
        "vertical_arb": [int(ok["vertical_arb"].sum())],
        "calendar_arb_with_next": [int(ok["calendar_arb_with_next"].fillna(False).sum())],
        "forward_from_parity_%": [ok["basis_from_parity"].mean() * 100],
    })
    return {"fit_status": status, "fit_quality": arb}


def run_historical():
    diag, df = build()
    diag.to_parquet(OUT / "expiry_day_fits.parquet")
    df.to_parquet(OUT / "forecasts.parquet")
    tables = {**fit_summary(diag), **run_tests(df)}
    for name, t in tables.items():
        t.to_csv(OUT / f"{name}.csv", index=name == "fit_status")
    lines = [f"# Phase 3 results (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"Origins with a smile-based 30-day distribution (and DVOL + RV): {len(df)} overlapping, "
             f"{len(df.iloc[::30])} non-overlapping, {df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}.", ""]
    for name, t in tables.items():
        lines += [f"## {name}", "", "```", t.to_string(index=name == "fit_status", float_format=lambda v: f"{v:.4f}"), "```", ""]
    (OUT / "results.md").write_text("\n".join(lines), encoding="utf-8")
    visuals.chart_pit(df, OUT, models=[("smile", "Option smile", visuals.AQUA), ("dvol", "DVOL", visuals.BLUE),
                                       ("rv", "Realised vol", visuals.ORANGE)])
    visuals.chart_reliability(df, OUT, models=[("smile", "Option smile", visuals.AQUA, "D"), ("dvol", "DVOL", visuals.BLUE, "o"),
                                               ("rv", "Realised vol", visuals.ORANGE, "s")])
    visuals.chart_tail_breaches(tables["breach"], OUT)
    log.info("Phase 3 historical done: %d origins", len(df))
