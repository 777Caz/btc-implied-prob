"""
Phase 3: risk-neutral distributions from the option smile.

  snapshot part   fit SVI to the latest live snapshot's quotes, build the surface, draw the charts
  historical part (after the full trade pull) daily 08:00 UTC surfaces from pooled trades,
                  arbitrage checks, 30-day distributions, and phase 2's calibration tests,
                  three ways: smile vs DVOL vs realised vol

Maths: src/models/smile.py.  Forwards: src/forwards.py.  Cleaning: src/clean_trades.py.
Outputs: reports/phase3/.
Run:  python -m src.phase3 snapshot      (charts from the latest snapshot)
      python -m src.phase3 clean         (cleaning report over all trade files)
      python -m src.phase3 forwards      (validate parity forwards vs snapshots and futures)
      python -m src.phase3 historical    (full backtest; needs all monthly trade files)
"""
import glob
import logging
import sys

import numpy as np
import pandas as pd

import config
from src import visuals
from src.api import deribit
from src.clean_trades import COLUMNS, clean, clean_all_months
from src.forwards import forward_by_expiry
from src.models import smile as sm

log = logging.getLogger(__name__)
OUT = config.PHASE3_DIR
YEAR_S = 365 * 86400


# ── Snapshot surface ─────────────────────────────────────────────────────────────────────────
MIN_T_SNAPSHOT = pd.Timedelta("6h")


def latest_snapshot() -> pd.DataFrame:
    return pd.read_parquet(sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "deribit_*.parquet")))[-1])


def snapshot_quotes(snap: pd.DataFrame) -> pd.DataFrame:
    """Out-of-the-money options with two-sided quotes, and their bid / mid / ask implied vols.
    OTM only: calls above the forward, puts below. They're the liquid side, and parity makes the
    ITM option redundant. BTC prices are converted to USD with the forward (Deribit's convention)."""
    s = snap.copy()
    s["T"] = (s["expiry"] - s["fetched_at"]).dt.total_seconds() / YEAR_S
    s = s[(s["expiry"] - s["fetched_at"]) >= MIN_T_SNAPSHOT]
    s["k"] = np.log(s["strike"] / s["forward_price"])
    s = s[((s["option_type"] == "call") & (s["k"] >= 0)) | ((s["option_type"] == "put") & (s["k"] < 0))]
    s = s.dropna(subset=["bid", "ask"])
    for side in ("bid", "ask"):
        s[f"iv_{side}"] = [sm.implied_vol(p * F, F, K, T, c == "call") for p, F, K, T, c in
                           zip(s[side], s["forward_price"], s["strike"], s["T"], s["option_type"])]
    s["mid"] = (s["bid"] + s["ask"]) / 2
    s["iv_mid"] = [sm.implied_vol(p * F, F, K, T, c == "call") for p, F, K, T, c in
                   zip(s["mid"], s["forward_price"], s["strike"], s["T"], s["option_type"])]
    return s.dropna(subset=["iv_mid"])


def fit_expiries(q: pd.DataFrame, T_col="T", k_col="k", iv_col="iv_mid", weight_col=None,
                 min_points=5, max_rmse_vol=0.03) -> tuple[list[sm.ExpirySmile], pd.DataFrame]:
    """SVI per expiry (spline fallback). Returns fitted smiles and a per-expiry diagnostics table."""
    smiles, rows = [], []
    for expiry, g in q.groupby("expiry"):
        if len(g) < min_points:
            continue
        T, F = g[T_col].median(), g["forward"].iloc[0]
        w = g[iv_col] ** 2 * g[T_col]
        p, rmse = sm.fit_svi(g[k_col], w, g[weight_col] if weight_col else None)
        # fit quality in vol points at the median T
        rmse_vol = np.nan if p is None else float(np.sqrt(np.mean((np.sqrt(p.w(g[k_col]) / g[T_col]) - g[iv_col]) ** 2)))
        method = "svi"
        if p is None or rmse_vol > max_rmse_vol:
            p, method = sm.SplineSmile(g[k_col].to_numpy(), w.to_numpy()), "spline"
            rmse_vol = float(np.sqrt(np.mean((np.sqrt(p.w(g[k_col]) / g[T_col]) - g[iv_col]) ** 2)))
        dist = sm.distribution_from_w(p.w, F, T)
        # arbitrage checks over +/- 6 ATM standard deviations (where the probability mass is)
        kk = np.log(dist.K / F)
        kk = kk[np.abs(kk) <= 6 * np.sqrt(max(p.w(0.0), 1e-8))]
        g_min = float(sm.butterfly_g(p, kk).min()) if method == "svi" else np.nan
        p_max = float(sm.prob_above_from_smile(p, kk).max()) if method == "svi" else float((-np.gradient(
            sm.black76(F, dist.K, p.w(np.log(dist.K / F))), dist.K)).max())
        smiles.append(sm.ExpirySmile(T, F, p, float(g[k_col].min()), float(g[k_col].max())))
        rows.append({"expiry": expiry, "T_days": T * 365, "forward": F, "n": len(g),
                     "k_min": g[k_col].min(), "k_max": g[k_col].max(), "method": method,
                     "rmse_vol_pts": rmse_vol * 100, "min_g": g_min,
                     "butterfly_arb": (g_min < -1e-4) if method == "svi" else bool((dist.density < -1e-12).any()),
                     "vertical_arb": p_max > 1 + 1e-3,
                     "density_mass": dist.mass(), "mean_over_F": dist.mean() / F})
    return smiles, pd.DataFrame(rows)


def snapshot_surface(snap: pd.DataFrame):
    q = snapshot_quotes(snap).rename(columns={"forward_price": "forward"})
    smiles, diag = fit_expiries(q)
    surf = sm.Surface(smiles)
    cal_viol = surf.calendar_violations()
    diag["calendar_arb_with_next"] = [any(abs(v[0] - e.T) < 1e-9 for v in cal_viol) for e in surf.e]
    return surf, q, diag


def current_dvol(at: pd.Timestamp) -> float:
    """DVOL (decimal) at the latest 1-minute candle up to `at`."""
    ms = int(at.timestamp() * 1000)
    r = deribit("get_volatility_index_data", currency="BTC", resolution="60",
                start_timestamp=ms - 3600_000, end_timestamp=ms)["data"]
    return r[-1][4] / 100


def run_snapshot():
    snap = latest_snapshot()
    t0, spot = snap["fetched_at"].iloc[0], snap["index_price"].iloc[0]
    surf, q, diag = snapshot_surface(snap)
    diag.to_csv(OUT / "snapshot_fits.csv", index=False)
    log.info("Snapshot %s: %d expiries fitted\n%s", t0, len(diag), diag.round(4).to_string())
    dvol = current_dvol(t0)
    visuals.chart_density_heatmap(surf, t0, spot, OUT)
    visuals.chart_smile_cone(surf, t0, spot, dvol, OUT)
    visuals.chart_expiry_densities(surf, diag, t0, spot, dvol, OUT)
    visuals.chart_smile_fits(surf, q, diag, t0, OUT)
    return surf, q, diag


# ── Validation of the parity forward (step 2) ────────────────────────────────────────────────
def validate_forwards_vs_snapshots(trades: pd.DataFrame, window: str = "2h") -> pd.DataFrame:
    """For every snapshot covered by `trades`, estimate forwards from trades in the preceding window
    and compare with the snapshot's own forward_price."""
    rows = []
    for f in sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "deribit_*.parquet"))):
        s = pd.read_parquet(f)
        t, spot = s["fetched_at"].iloc[0], s["index_price"].iloc[0]
        w = trades.loc[t - pd.Timedelta(window):t]
        if w.empty:
            continue
        fw = forward_by_expiry(w[w["days_to_expiry"] >= 0.5], spot)
        j = fw.join(s.groupby("expiry")["forward_price"].first().rename("snapshot_forward"), how="inner")
        j["error_bps"] = (j["forward"] / j["snapshot_forward"] - 1) * 1e4
        j["snapshot"] = t
        rows.append(j.reset_index())
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def validate_forwards_vs_futures(n_days: int = 40, seed: int = 3, window: str = "6h") -> pd.DataFrame:
    """On random historical days, compare parity forwards (trades in the `window` before 08:00 UTC)
    with the median basis of Deribit dated FUTURES traded in the same window. Where a future with the
    same expiry exists, its price is the forward, so this is an independent check."""
    rng = np.random.default_rng(seed)
    files = sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet")))
    rows = []
    for f in sorted(rng.choice(files, size=min(n_days, len(files)), replace=False)):
        tr, _ = clean(pd.read_parquet(f, columns=COLUMNS))
        days = tr.index.normalize().unique()
        ref = days[rng.integers(len(days))] + pd.Timedelta(hours=8)
        w = tr.loc[ref - pd.Timedelta(window):ref]
        if w.empty:
            continue
        fw = forward_by_expiry(w, w["index_price"].iloc[-1])
        ms = lambda t: int(t.timestamp() * 1000)
        fut = pd.DataFrame(deribit("get_last_trades_by_currency_and_time", base=config.DERIBIT_HISTORY_BASE,
                                   currency="BTC", kind="future", start_timestamp=ms(ref - pd.Timedelta(window)),
                                   end_timestamp=ms(ref), count=1000, sorting="desc")["trades"])
        if fut.empty:
            continue
        fut = fut[fut["instrument_name"].str.match(r"^BTC-\d{1,2}[A-Z]{3}\d{2}$")]
        fut["expiry"] = (pd.to_datetime(fut["instrument_name"].str.split("-").str[1], format="%d%b%y")
                         .dt.tz_localize("UTC") + pd.Timedelta(hours=8))
        fb = (fut["price"] / fut["index_price"]).groupby(fut["expiry"]).median().rename("futures_basis")
        j = fw.join(fb, how="inner")
        j["error_bps"] = (j["basis"] / j["futures_basis"] - 1) * 1e4
        j["day"] = ref
        j["days_to_expiry"] = (j.index - ref).total_seconds() / 86400
        rows.append(j.reset_index())
    return pd.concat(rows, ignore_index=True)


def run_forward_validation():
    from src.deribit_options import fetch_trades, parse_instruments
    now = pd.Timestamp.now(tz="UTC")
    first_snap = pd.read_parquet(sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "deribit_*.parquet")))[0])["fetched_at"].iloc[0]
    recent = parse_instruments(fetch_trades(max(first_snap - pd.Timedelta("2h"), now - pd.Timedelta("23h")), now))
    vs_snap = validate_forwards_vs_snapshots(recent)
    vs_fut = validate_forwards_vs_futures()
    vs_snap.to_csv(OUT / "forward_validation_snapshots.csv", index=False)
    vs_fut.to_csv(OUT / "forward_validation_futures.csv", index=False)
    summ = pd.DataFrame([
        {"reference": name, "expiry_obs": len(v), "days": v[key].nunique(),
         "median_abs_error_bps": v["error_bps"].abs().median(), "p90_abs_error_bps": v["error_bps"].abs().quantile(0.9),
         "mean_error_bps": v["error_bps"].mean()}
        for name, v, key in [("live snapshot forwards", vs_snap, "snapshot"), ("Deribit futures", vs_fut, "day")]])
    summ.to_csv(OUT / "forward_validation_summary.csv", index=False)
    log.info("Forward validation:\n%s", summ.round(2).to_string())


def main():
    config.setup_logging()
    visuals.matplotlib.use("Agg")
    mode = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if mode == "snapshot":
        run_snapshot()
    elif mode == "forwards":
        run_forward_validation()
    elif mode == "clean":
        rep = clean_all_months()
        rep.to_csv(OUT / "cleaning_report.csv")
        log.info("Cleaning report:\n%s", rep)
    elif mode == "historical":
        from src.phase3_hist import run_historical
        run_historical()


if __name__ == "__main__":
    main()
