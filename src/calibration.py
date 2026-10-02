"""
Calibration statistics for probabilistic forecasts.

Two samples are tested throughout:
  * non-overlapping: one 30-day forecast every 30 days (~66 windows). Windows share no days, so
    outcomes are (close to) independent and textbook standard errors / p-values are valid.
    But the sample is small.
  * overlapping: a new 30-day forecast every day (~2,000 windows). Far more data, but consecutive
    windows share 29 of their 30 days, so their outcomes are strongly correlated: a crash on
    one day shows up in the next ~30 forecasts. Treating them as independent overstates the
    effective sample size ~30x and makes p-values far too small.

Newey-West (HAC) standard errors fix that for any average over the overlapping sample (breach
rates, Brier scores, score differences). The variance of a sample mean of a correlated series x
is not var(x)/n but

    Var(mean) = (1/n) * [ gamma_0 + 2 * sum_{l=1..L} w_l * gamma_l ],   w_l = 1 - l/(L+1)

where gamma_l is the autocovariance at lag l. With a 30-day horizon sampled daily, forecast
errors of a correctly specified model are correlated up to lag 29 (an MA(29) process), so the
textbook minimum is L = 29. The Bartlett weights w_l keep the variance estimate positive, but
they also shrink the long-lag terms. In a simulation of overlapping 30-day sums (2,000 days),
L = 29 gave SEs ~20% too small, while L = 60 got within ~10% (naive iid SEs were 5.6x too small).
So we use L = 60. Overlapping p-values remain slightly optimistic, so treat borderline ones with care.
"""
import numpy as np
import pandas as pd
from scipy import stats

NW_LAGS = 60


def newey_west_se(x, lags: int = NW_LAGS) -> float:
    """HAC standard error of the mean of x (Bartlett kernel)."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    e = x - x.mean()
    var = e @ e / n
    for l in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - l / (lags + 1)) * (e[l:] @ e[:-l]) / n
    return np.sqrt(var / n)


def mean_test(x, expected: float, overlapping: bool) -> dict:
    """Is mean(x) different from `expected`? Two-sided p-value.
    Non-overlapping: iid standard error. Overlapping: Newey-West standard error."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    se = newey_west_se(x) if overlapping else x.std(ddof=1) / np.sqrt(len(x))
    z = (x.mean() - expected) / se if se > 0 else np.nan
    return {"mean": x.mean(), "se": se, "z": z, "p": 2 * stats.norm.sf(abs(z)) if se > 0 else np.nan}


def binomial_p(k: int, n: int, p0: float) -> float:
    """Exact two-sided binomial test, for rare events in the small non-overlapping sample."""
    return stats.binomtest(k, n, p0).pvalue


# ── Breach table ─────────────────────────────────────────────────────────────────────────────
def breach_table(df: pd.DataFrame, model: str, overlapping: bool,
                 bands=((0.05, 0.95), (0.10, 0.90), (0.25, 0.75))) -> pd.DataFrame:
    """How often the realised price finished below / above / outside each central band,
    vs the expected rate. Uses PIT: finishing below the q-percentile <=> PIT < q."""
    u = df[f"pit_{model}"].to_numpy()
    rows = []
    for lo, hi in bands:
        for side, hit, expected in [("below", u < lo, lo), ("above", u > hi, 1 - hi),
                                    ("outside", (u < lo) | (u > hi), lo + 1 - hi)]:
            hit = hit.astype(float)
            if overlapping:
                t = mean_test(hit, expected, overlapping=True)
                p = t["p"]
                se = t["se"]
            else:
                p = binomial_p(int(hit.sum()), len(hit), expected)
                se = np.sqrt(expected * (1 - expected) / len(hit))
            rows.append({"model": model, "band": f"{int(lo*100)}-{int(hi*100)}", "side": side, "n": len(hit),
                         "expected": expected, "observed": hit.mean(), "se": se, "p_value": p})
    return pd.DataFrame(rows)


# ── PIT ──────────────────────────────────────────────────────────────────────────────────────
def pit_summary(df: pd.DataFrame, model: str, overlapping: bool) -> dict:
    """KS test for uniform PIT, plus the variance ratio that tells U-shape from hump.

    Uniform PIT has variance 1/12. var(PIT)/(1/12):
      > 1  -> U-shape: too many outcomes in both tails -> forecast distribution too NARROW
      < 1  -> hump:    too few outcomes in the tails   -> forecast distribution too WIDE
    A mean PIT away from 0.5 means a location bias (outcomes systematically above or below the median).

    KS p-values assume independent draws. For the overlapping sample we instead run the KS test
    on each of the 30 non-overlapping sub-samples (origins d, d+30, d+60, ... for offsets
    d = 0..29) and report the median p-value.
    """
    u = df[f"pit_{model}"].dropna().to_numpy()
    ks = stats.kstest(u, "uniform")
    out = {"model": model, "n": len(u), "mean_pit": u.mean(), "var_ratio": u.var() / (1 / 12),
           "ks_stat": ks.statistic}
    if overlapping:
        pvals = [stats.kstest(u[o::30], "uniform").pvalue for o in range(30)]
        out["ks_p"] = float(np.median(pvals))
        out["ks_p_note"] = "median over 30 non-overlapping sub-samples"
        out["mean_pit_p"] = mean_test(u, 0.5, overlapping=True)["p"]
    else:
        out["ks_p"] = ks.pvalue
        out["ks_p_note"] = "standard KS"
        out["mean_pit_p"] = mean_test(u, 0.5, overlapping=False)["p"]
    return out


# ── Digital probabilities ───────────────────────────────────────────────────────────────────
def reliability(p: np.ndarray, y: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Reliability diagram data: within each forecast-probability bin, the average forecast vs
    how often the event actually happened. A calibrated forecast lies on the diagonal."""
    edges = np.linspace(0, 1, bins + 1)
    b = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    g = pd.DataFrame({"bin": b, "p": p, "y": y}).groupby("bin")
    out = g.agg(mean_forecast=("p", "mean"), observed=("y", "mean"), n=("y", "size"))
    out["ci95"] = 1.96 * np.sqrt(out["observed"] * (1 - out["observed"]) / out["n"])  # iid, indicative only
    return out


def brier(p, y) -> np.ndarray:
    """Per-forecast Brier loss (p - y)^2. The Brier score is its mean: 0 = perfect, 0.25 = coin flip at 50%."""
    return (np.asarray(p) - np.asarray(y)) ** 2


def compare_losses(loss_a, loss_b, overlapping: bool) -> dict:
    """Diebold-Mariano style test: is the mean loss difference (a - b) zero?
    Negative mean = model a is better (lower loss). Uses NW standard errors when overlapping."""
    d = np.asarray(loss_a) - np.asarray(loss_b)
    t = mean_test(d, 0.0, overlapping)
    return {"mean_diff": t["mean"], "se": t["se"], "z": t["z"], "p_value": t["p"]}
