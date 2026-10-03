"""
Robustness of the Kalshi favourite-longshot slope (17:00 NY daily above-K markets).

1. Price floor. Kalshi prices sit on a 1c grid, so the usable mid cannot go below ~1.5c or above
   ~98.5c even when the true probability is 0.1%. Near the floor logit(mid) is mismeasured, which
   alone can push the recalibration slope b above 1. Refit b excluding mids < 5c / > 95c and
   < 10c / > 90c.

2. Distance from the money instead of price. z = ln(S_t / K) / (sigma * sqrt(tau)) with S_t the
   Coinbase BTC-USD price at the quote time (a BRTI constituent), sigma = DVOL at the quote time
   (30-day implied vol, a scale only) and tau the clock time to settlement. Selecting contracts by
   |z| (not by price) avoids conditioning on the noisy quote itself:
     a) b = slope of P(YES) = sigmoid(a + b logit(mid)) within |z| <= 1, 1.5, 2;
     b) b_z = c1 / m1, the outcome's slope in z, P(YES) = sigmoid(c0 + c1 z), over the market's
        slope in z, logit(mid) = m0 + m1 z (OLS), on the same |z| band. If logit P = a + b logit(mid)
        holds then c1 = b m1, so b_z estimates b using only moneyness. 95% CI by event bootstrap.

Same sample as src/pm_kalshi_calib.py (usable = two-sided, spread <= 10c), effective N = days.
Outputs: reports/pm/kalshi_robustness/. Run:  python -m src.pm_kalshi_robust
"""
import logging

import numpy as np
import pandas as pd

import config
from src import pm_kalshi_calib as kc

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "pm" / "kalshi_robustness"
OUT.mkdir(parents=True, exist_ok=True)
TRIMS = {"none": 0.0, "5c-95c": 0.05, "10c-90c": 0.10}
Z_BANDS = (1.0, 1.5, 2.0)
N_BOOT = 400
RNG = np.random.default_rng(7)


def load_quotes() -> pd.DataFrame:
    d = pd.read_parquet(kc.OUT / "quotes_at_leads.parquet")
    d = d[d["usable"] & (d["event_hour"] == "17:00 NY")].copy()
    d["mid"] = (d["bid"] + d["ask"]) / 2
    cat = pd.read_parquet(kc.CATALOG, columns=["ticker", "close_time"]).set_index("ticker")["close_time"]
    close = d["ticker"].map(cat)
    lead = d["lead"].map({k: v for k, v in kc.LEADS.items()})
    d["t"] = np.where(d["lead"] == kc.AT_0800, close.dt.normalize() + pd.Timedelta(hours=8),
                      (close - lead.fillna(pd.Timedelta(0))).dt.floor("min"))
    d["t"] = pd.to_datetime(d["t"], utc=True)
    d["tau"] = (close - d["t"]).dt.total_seconds() / (365 * 86400)
    spot = pd.read_parquet(config.DATA_RAW / "btc_price_hourly.parquet")["open"]          # Coinbase, price at the hour
    dvol = pd.read_parquet(config.DATA_PROCESSED / "btc_dvol_hourly.parquet")["dvol_close"]
    d["spot"] = d["t"].map(spot)
    d["sigma"] = (d["t"] - pd.Timedelta("1h")).map(dvol) / 100                          # bar ending at t
    d["z"] = np.log(d["spot"] / d["strike"]) / (d["sigma"] * np.sqrt(d["tau"]))
    return d


def logistic_multi(y, X, groups) -> tuple[np.ndarray, np.ndarray]:
    """Logistic regression with intercept, Newton-Raphson, cluster-robust SEs. Returns (beta, se)."""
    X = np.column_stack([np.ones(len(y)), X])
    beta = np.zeros(X.shape[1])
    for _ in range(60):
        p = kc.sigmoid(X @ beta)
        step = np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]), X.T @ (y - p))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    p = kc.sigmoid(X @ beta)
    Hinv = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))
    S = pd.DataFrame(X * (y - p)[:, None]).groupby(np.asarray(groups)).sum().to_numpy()
    G = len(S)
    V = Hinv @ (S.T @ S * G / (G - 1)) @ Hinv
    return beta, np.sqrt(np.diag(V))


def b_fit(s: pd.DataFrame) -> dict:
    f = kc.logistic_cluster(s["outcome"].to_numpy(float), kc.logit(s["mid"].to_numpy()), s["event"].to_numpy())
    return {**kc.n_info(s), "b": f["b"], "b_se": f["b_se"], "z_b=1": f["z_b=1"]}


def bz_point(s: pd.DataFrame) -> float:
    beta, _ = logistic_multi(s["outcome"].to_numpy(float), s["z"].to_numpy(), s["event"].to_numpy())
    m1 = np.polyfit(s["z"].to_numpy(), kc.logit(s["mid"].to_numpy()), 1)[0]
    return beta[1] / m1


def bz_fit(s: pd.DataFrame) -> dict:
    est = bz_point(s)
    s = s.reset_index(drop=True)
    rows = list(s.groupby("event").indices.values())
    boots = []
    for _ in range(N_BOOT):
        pick = RNG.integers(0, len(rows), len(rows))
        b = s.iloc[np.concatenate([rows[i] for i in pick])]
        boots.append(bz_point(b.assign(event=np.repeat(np.arange(len(pick)), [len(rows[i]) for i in pick]))))
    lo, hi = np.quantile(boots, [.025, .975])
    return {**kc.n_info(s), "b_z": est, "ci_lo": lo, "ci_hi": hi}


def periods(g):
    for period in ("pre-2026", "2026", "all"):
        yield period, (g if period == "all" else g[g["period"] == period])


def main():
    config.setup_logging()
    d = load_quotes()
    miss = d["z"].isna()
    log.info("quotes %d, without spot/DVOL (after 2026-09-30 14:00) %d", len(d), int(miss.sum()))
    d = d[~miss]

    trim = []
    for lead, g in d.groupby("lead"):
        for period, s in periods(g):
            for name, c in TRIMS.items():
                ss = s[s["mid"].between(c, 1 - c)] if c else s
                trim.append({"lead": lead, "period": period, "sample": f"mid {name}", **b_fit(ss)})
            for zb in Z_BANDS:
                trim.append({"lead": lead, "period": period, "sample": f"|z| <= {zb}", **b_fit(s[s["z"].abs() <= zb])})
    trim = pd.DataFrame(trim)

    bz = []
    for lead, g in d.groupby("lead"):
        for period, s in periods(g):
            for zb in Z_BANDS:
                bz.append({"lead": lead, "period": period, "band": f"|z| <= {zb}", **bz_fit(s[s["z"].abs() <= zb])})
        log.info("b_z done for %s", lead)
    bz = pd.DataFrame(bz)

    # share of the excess slope (b - 1) that the price floor explains: 1 - (b_trim - 1) / (b_all - 1)
    piv = trim.pivot_table(index=["lead", "period"], columns="sample", values="b")
    expl = pd.DataFrame({f"floor share, {c}": 1 - (piv[f"mid {c}"] - 1) / (piv["mid none"] - 1) for c in ("5c-95c", "10c-90c")})
    floor_hits = d.assign(at_floor=(d["mid"] < .05) | (d["mid"] > .95)).groupby(["lead"])["at_floor"].mean()

    trim.to_csv(OUT / "b_by_sample.csv", index=False)
    bz.to_csv(OUT / "b_z_moneyness.csv", index=False)
    expl.to_csv(OUT / "floor_share.csv")
    fmt = lambda t, idx=False: t.to_string(index=idx, float_format=lambda v: f"{v:.3f}")
    lines = [f"# Kalshi favourite-longshot slope: price-floor and moneyness robustness (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"17:00 NY daily markets, usable quotes (two-sided, spread <= {kc.MAX_SPREAD * 100:.0f}c), {d['day'].nunique()} settlement days "
             f"to {d['settle'].max():%Y-%m-%d}. z = ln(S/K) / (DVOL sqrt(tau)), S = Coinbase at the quote time. `days` = effective N.", "",
             "Share of quotes with mid < 5c or > 95c:", "```", fmt(floor_hits.to_frame("share"), True), "```",
             "## Slope b of P(YES) = sigmoid(a + b logit(mid)) by sample (price trims and |z| bands)", "```",
             fmt(trim.sort_values(["lead", "period", "sample"])), "```",
             "## Share of (b - 1) explained by the price floor = 1 - (b_trimmed - 1) / (b_untrimmed - 1)", "```", fmt(expl, True), "```",
             "## b_z = (outcome slope in z) / (market slope in z): favourite-longshot slope from moneyness only (95% event-bootstrap CI)",
             "```", fmt(bz.sort_values(["lead", "period", "band"])), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Kalshi robustness done -> %s", OUT)


if __name__ == "__main__":
    main()
