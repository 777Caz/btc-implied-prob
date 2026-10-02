# Phase 3 summary: the full option smile as a forecast of BTC

**Short answer:** building the whole risk-neutral distribution from the option smile gives the
best-*shaped* 30-day forecast so far. Its PIT histogram is flat, and DVOL's "too wide in the
middle" problem is gone. But it does **not** forecast measurably better than plain DVOL, and it
does **not** fix the upper-tail misses. BTC finished above the smile's 95th percentile 8.8% of the
time (expected 5%), about the same as DVOL (7.9%). The upside miss isn't about the shape of the
distribution. Most likely the risk-neutral (option-implied) distribution systematically understates
BTC's real-world upside.

## What was built

1. **Cleaning** (22.7M Deribit BTC option trades, 2021-01 to 2026-09):

   | rule | rows removed (sequential) | share |
   |---|---|---|
   | iv = 0 | 65,322 | 0.29% |
   | iv ≥ 300 | 24,441 | 0.11% |
   | combo legs | 291,270 | 1.28% |
   | < 1 day to expiry | 4,447,007 | 19.6% |
   | **kept** | **17,895,274** | **78.8%** |

   Combo legs show iv = 0 about 2.3 times as often as other trades over the full period (0.65% vs
   0.28%), and that gap has widened as combo trading grew (5x in 2026: 1.8% vs 0.34%).
   6 trades on 15 Jul 2026 printed ~2 minutes *after* the 08:00 expiry; the < 1 day filter removes them.

2. **Forward per expiry from put-call parity.** Deribit prices options in BTC as (USD Black-76
   value) / F. Since call − put pays 1 − K/S_T BTC in every state, **c − p = 1 − K/F**, so
   **F = K / (1 − (c − p))**, with no spot price or discount factor needed. A call and put at the
   same strike traded within 5 minutes give one estimate, and the median across pairs is used.
   Validation:

   | reference | comparisons | median error | 90th pct |
   |---|---|---|---|
   | live snapshot forwards | 44 (12 snapshots) | 3.5 bp | 9 bp |
   | Deribit futures, 37 random days | 89 | 3.5 bp | 14 bp |

   Expiries with too few call/put pairs (53% of fitted expiry-days) got their forward interpolated
   from neighbouring expiries.

3. **Smile fitting: SVI** on total variance vs log-moneyness, chosen over a spline because its
   wings extrapolate the way no-arbitrage theory allows and it can't chase single-trade noise.
   Unconstrained SVI turned out to be *arbitrageable* even with a perfect fit to the quotes: on
   one expiry the wing ran to the theoretical limit and P(S_T > K) exceeded 1. The fit is
   therefore penalised for butterfly arbitrage (Gatheral's g(k) < 0) and vertical-spread arbitrage
   (P(S_T > K) = N(d₂) − φ(d₂)w′/(2√w) outside [0, 1]).

   Historical: trades in the 8 hours before 08:00 UTC, pooled per strike. An expiry needs ≥ 15
   trades, ≥ 5 strikes, strikes on both sides of the forward, and a span of ≥ 1 standard deviation.
   - **15,729 of 18,568 expiry-days passed (84.7%).** Failures: few trades 10.0%, no forward
     4.5%, other < 1%.
   - Fit error: median **0.50 vol points** (90th percentile 1.4).
   - Remaining arbitrage flags, where the data itself forces them: butterfly 691 (4.4%),
     vertical 164 (1.0%), calendar 127 (0.8%).

4. **Density** by Breeden-Litzenberger: Black-76 call prices on a fine strike grid, then
   P(S_T > K) = −∂C/∂K and the density f = ∂²C/∂K². A flat smile reproduces phase 2's lognormal to
   5 digits. Densities integrate to ~1 (median 0.999) with mean ≈ forward.

5. **Any horizon:** total variance is interpolated linearly in time at fixed log-moneyness, with
   the forward log-linear. The 30-day forecast only uses days where two fitted expiries bracket
   30 days. That leaves 1,892 of the 1,987 phase-2 origins, and all models are compared on these
   same 1,892.

## Results (1,892 daily 30-day forecasts, 2021-03 to 2026-08; 64 non-overlapping)

| | smile | DVOL | realised vol | smile ATM vol, lognormal |
|---|---|---|---|---|
| PIT variance ratio (1 = right width) | **1.02** | 0.91 (too wide) | 1.08 (too narrow) | 0.98 |
| inside 25–75% band (expect 50%) | **50.5%** | 55.7% | 51.8% | 53.5% |
| **below 5th pct** (expect 5%) | 3.9% | 4.5% | 8.7% | 6.0% |
| **above 95th pct** (expect 5%) | 8.8% | 7.9% | 10.0% | 8.4% |
| P(>110%): forecast vs observed 26.2% | 23.4% | 24.7% | 21.6% | 24.6% |
| P(>120%): forecast vs observed 13.0% | 10.1% | 11.6% | 9.0% | 11.0% |
| Brier, 5 strikes (lower better) | **0.1627** | 0.1632 | 0.1664 | 0.1632 |
| log score (higher better) | **0.379** | 0.369 | 0.155 | 0.358 |

Head-to-head, smile minus other (Newey-West p-values, daily sample):
- **vs realised vol:** smile better. Log score p = 0.010, Brier p = 0.058, with both tails better.
- **vs DVOL:** no significant difference. Log score p = 0.63, Brier p = 0.74. On the upside
  (110% strike) DVOL is slightly *better*, p = 0.07.
- **vs smile-ATM lognormal:** no significant difference (log score p = 0.25). The smile's
  *shape* adds little beyond its level.

### Did the upper-tail misses improve? No.
- **The smile is worse on the upside than DVOL.** It puts *less* probability on rallies than DVOL
  does (P(>120%) 10.1% vs 11.6%), because BTC's smile usually has a put skew that thins the right
  tail. It misses above the 95th percentile a little more often (8.8% vs 7.9%).
- **Every option-based model under-predicts the upside**, and the downside is fine or even too
  cautious (smile 3.9% below the 5th percentile). Changing the width or shape of the distribution
  can't fix a one-sided miss.
- **Likely explanation:** the gap between risk-neutral and real-world probabilities. Option
  prices embed what investors pay to insure against crashes, not BTC's real expected return.
  Over 2021–2026 BTC rose substantially, and markets that price in downside protection
  understate upside frequency. A 5.5-year sample dominated by one bull cycle can't separate a
  persistent premium from luck; the error bars on all tail rates are wide (±4–5 points).

## Caveats

- **Sample:** 64 independent 30-day windows. Differences between the option-based models are
  well inside the noise.
- **Pooling window:** trades over 8 hours before 08:00, with the smile held fixed in vol terms
  across that window.
- **Wings beyond the last traded strike are extrapolation.** The arbitrage penalty picks *a* safe
  wing, not necessarily the true one. This shows up in the snapshot heatmap's far left tail.
- **Forwards:** 53% of expiry-days use an interpolated forward. Validation errors are a few basis
  points, small relative to 30-day vol.

## Files (reports/phase3/)

- `results.md`: all tables
- Fitting and data checks: `fit_status.csv`, `fit_quality.csv`, `expiry_day_fits.parquet`,
  `cleaning_report.csv`, `iv0_block_combo.csv`, `forward_validation_*.csv`
- Calibration: `breach.csv`, `pit.csv`, `digital.csv`, `compare.csv`, `forecasts.parquet`
- Charts from today's snapshot: `density_heatmap.png`, `smile_vs_dvol_cone.png`,
  `expiry_densities.png`, `smile_fits.png`
- Backtest charts: `tail_breaches.png`, `pit_histograms.png`, `reliability.png`

Reproduce: `python -m src.phase3 clean | forwards | snapshot | historical`.
