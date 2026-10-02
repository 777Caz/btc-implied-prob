"""
Phase 2: DVOL-based 30-day distributions vs a trailing realised-vol baseline, and calibration tests.

Setup
  * Forecast origin: 08:00 UTC each day. Starting price S_0 = Deribit delivery price that day.
  * Horizon: exactly 30 days. Outcome S_T = Deribit delivery price 30 days later (08:00 UTC),
    the same index the options settle on.
  * Models: the same lognormal (src/models/dvol_lognormal.py), with sigma from
      - "dvol": DVOL at 08:00 (close of the 07:00-08:00 hourly candle), / 100
      - "rv":   trailing 30-day realised vol of daily delivery prices (src/models/realized_vol.py)
  * Common sample: only origins where both sigmas and the outcome exist (DVOL starts 2021-03-24).
  * Two samples: daily overlapping origins, and one origin every 30 days (non-overlapping).

Outputs in reports/phase2/: forecasts.parquet, CSV tables, results.md (all tables), figures.
Run:  python -m src.phase2
"""
import logging

import numpy as np
import pandas as pd

import config
from src import calibration as cal
from src import visuals
from src.models import dvol_lognormal as lm
from src.models.realized_vol import trailing_realized_vol

log = logging.getLogger(__name__)

OUT = config.PHASE2_DIR
MODELS = {"dvol": "DVOL (implied)", "rv": "30d realised vol"}
QUANTILES = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
STRIKES = [0.8, 0.9, 1.0, 1.1, 1.2]           # digital strikes as a fraction of S_0
HORIZON = pd.Timedelta(days=lm.DAYS)


# ── Data ─────────────────────────────────────────────────────────────────────────────────────
def load_inputs():
    delivery = pd.read_parquet(config.RESOLUTIONS_DIR / "deribit_delivery.parquet")["delivery_price"]
    dvol = pd.read_parquet(config.DATA_RAW / "dvol_hourly.parquet")["close"]
    dvol.index = dvol.index + pd.Timedelta(hours=1)          # candle 07:00-08:00 closes at 08:00
    dvol_0800 = dvol[dvol.index.hour == 8] / 100
    return delivery, dvol_0800


def build_forecasts() -> pd.DataFrame:
    delivery, dvol_0800 = load_inputs()
    df = pd.DataFrame({"s0": delivery})
    df["s_t"] = delivery.reindex(df.index + HORIZON).to_numpy()
    df["sigma_dvol"] = dvol_0800.reindex(df.index)
    df["sigma_rv"] = trailing_realized_vol(delivery)
    # what vol actually turned out to be over the forecast window (for context, not a forecast)
    df["sigma_realised_next30"] = trailing_realized_vol(delivery).shift(-lm.DAYS)
    df = df.dropna(subset=["s_t", "sigma_dvol", "sigma_rv"])
    df.index.name = "origin"

    for m in MODELS:
        sig = df[f"sigma_{m}"]
        df[f"pit_{m}"] = lm.pit(df["s0"], df["s_t"], sig)
        df[f"logscore_{m}"] = lm.log_score(df["s0"], df["s_t"], sig)
        for q in QUANTILES:
            df[f"q{int(q*100):02d}_{m}"] = lm.percentile(df["s0"], sig, q)
        for k in STRIKES:
            df[f"p{int(k*100)}_{m}"] = lm.prob_above(df["s0"], k * df["s0"], sig)
    for k in STRIKES:
        df[f"y{int(k*100)}"] = (df["s_t"] > k * df["s0"]).astype(float)
    return df


def samples(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"overlapping (daily)": df, "non-overlapping (every 30d)": df.iloc[::lm.DAYS]}


# ── Tests ────────────────────────────────────────────────────────────────────────────────────
def run_tests(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    breach, pit, digital, compare = [], [], [], []
    for name, s in samples(df).items():
        ov = name.startswith("overlapping")
        for m in MODELS:
            breach.append(cal.breach_table(s, m, ov).assign(sample=name))
            pit.append({**cal.pit_summary(s, m, ov), "sample": name})
            for k in STRIKES:
                p, y = s[f"p{int(k*100)}_{m}"], s[f"y{int(k*100)}"]
                digital.append({"sample": name, "model": m, "strike": f"{int(k*100)}%", "n": len(s),
                                "mean_forecast": p.mean(), "observed": y.mean(),
                                "brier": cal.brier(p, y).mean()})

        # DVOL vs RV head to head: per strike, down tail (80/90), up tail (110/120), all, and log score
        groups = {f"{int(k*100)}%": [k] for k in STRIKES}
        groups |= {"down tail (80%, 90%)": [0.8, 0.9], "up tail (110%, 120%)": [1.1, 1.2], "all strikes": STRIKES}
        for g, ks in groups.items():
            loss = {m: np.mean([cal.brier(s[f"p{int(k*100)}_{m}"], s[f"y{int(k*100)}"]) for k in ks], axis=0)
                    for m in MODELS}
            compare.append({"sample": name, "metric": f"Brier {g}", "dvol": loss["dvol"].mean(), "rv": loss["rv"].mean(),
                            **cal.compare_losses(loss["dvol"], loss["rv"], ov)})
        # log score: higher is better, so compare negative log scores as losses
        compare.append({"sample": name, "metric": "log score (higher = better)",
                        "dvol": s["logscore_dvol"].mean(), "rv": s["logscore_rv"].mean(),
                        **cal.compare_losses(-s["logscore_dvol"], -s["logscore_rv"], ov)})

    vol = pd.DataFrame({
        "mean_annualised_vol_%": [df["sigma_dvol"].mean() * 100, df["sigma_rv"].mean() * 100,
                                  df["sigma_realised_next30"].mean() * 100],
        "median_%": [df["sigma_dvol"].median() * 100, df["sigma_rv"].median() * 100,
                     df["sigma_realised_next30"].median() * 100],
    }, index=["DVOL at origin", "trailing 30d realised at origin", "realised over the NEXT 30d"])
    return {
        "breach": pd.concat(breach, ignore_index=True)[["sample", "model", "band", "side", "n", "expected", "observed", "se", "p_value"]],
        "pit": pd.DataFrame(pit)[["sample", "model", "n", "mean_pit", "mean_pit_p", "var_ratio", "ks_stat", "ks_p", "ks_p_note"]],
        "digital": pd.DataFrame(digital),
        "compare": pd.DataFrame(compare)[["sample", "metric", "dvol", "rv", "mean_diff", "se", "z", "p_value"]],
        "vol": vol,
    }


def write_results(df: pd.DataFrame, tables: dict[str, pd.DataFrame]):
    df.to_parquet(OUT / "forecasts.parquet")
    for name, t in tables.items():
        t.to_csv(OUT / f"{name}.csv", index=name == "vol")
    first, last = df.index[0], df.index[-1]
    lines = [f"# Phase 2 results (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"Forecast origins {first:%Y-%m-%d} to {last:%Y-%m-%d} 08:00 UTC; "
             f"{len(df)} overlapping, {len(df.iloc[::lm.DAYS])} non-overlapping windows. "
             "Horizon 30 days. Outcome = Deribit delivery price.", ""]
    for name, title in [("vol", "Volatility levels"), ("breach", "Breach table"), ("pit", "PIT tests"),
                        ("digital", "Digital probabilities by strike"), ("compare", "DVOL vs realised-vol baseline (loss differences)")]:
        text = tables[name].to_string(index=name == "vol", float_format=lambda v: f"{v:.4f}")
        lines += [f"## {title}", "", "```", text, "```", ""]
    lines += ["`compare`: mean_diff = loss(DVOL) - loss(RV); negative = DVOL better. For the log score the "
              "loss is minus the log score. p-values use Newey-West SEs (60 lags) in the overlapping sample."]
    (OUT / "results.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote results to %s", OUT)


def main():
    config.setup_logging()
    visuals.matplotlib.use("Agg")
    df = build_forecasts()
    log.info("Forecasts: %d daily origins %s -> %s", len(df), df.index[0].date(), df.index[-1].date())
    tables = run_tests(df)
    write_results(df, tables)

    delivery, dvol_0800 = load_inputs()
    visuals.chart_forward_cone(delivery, dvol_0800, OUT)
    visuals.chart_historical_cones(df.iloc[::lm.DAYS], delivery, OUT)
    visuals.chart_pit(df, OUT)
    visuals.chart_reliability(df, OUT)
    visuals.chart_vol_levels(df, OUT)


if __name__ == "__main__":
    main()
