# Phase 2 summary: does DVOL forecast BTC's 30-day range better than recent history?

**Short answer: yes, modestly.** A lognormal distribution built from DVOL gives better-calibrated
30-day forecasts than the same distribution built from trailing 30-day realised volatility. The
gain comes almost entirely from the **tails**: realised vol badly under-predicts big moves. Neither
model is perfect. DVOL's distribution is **too wide in the middle** and slightly **too thin on the
upside**, which is what you'd expect when a lognormal is fitted to a fat-tailed asset.

## What we tested

- Every day at 08:00 UTC from 2021-03-24 to 2026-08-31, we forecast BTC's price 30 days later as a
  lognormal distribution centred so that the expected price equals today's price (risk-neutral,
  interest rates ignored).
- The volatility input was either **DVOL** (the options market's 30-day implied vol) or **trailing
  30-day realised vol** (just looking at the last month). Everything else was identical.
- The outcome is Deribit's 08:00 settlement price 30 days later, so model and outcome use the same index.
- There are 1,987 daily (overlapping) forecasts and 67 non-overlapping ones (one every 30 days). The
  overlapping sample uses Newey-West standard errors, because consecutive forecasts share 29 of their 30 days.

## Findings

**1. DVOL runs high, but that's not the whole story.** DVOL averaged **59.9%**, while vol over the
following 30 days averaged **51.1%**. Trailing realised vol averaged 51.4%, the right level on
average. So implied vol carries a premium of ~9 points (the variance risk premium, plus the fact
that DVOL averages across the smile and sits above at-the-money vol). Yet DVOL still forecasts better.

**2. Tails: realised vol is too narrow, DVOL is about right.** BTC finished outside the 5–95% band:

| | expected | DVOL | realised vol |
|---|---|---|---|
| daily windows | 10% | 12.8% (p = 0.31) | **19.2% (p = 0.003)** |
| non-overlapping | 10% | 11.9% (p = 0.54) | **19.4% (p = 0.02)** |

Realised vol produced nearly **twice** as many extreme outcomes as it should. It looks backwards,
so it's lowest just before vol spikes. DVOL rises ahead of risk and its tails held up.

**3. The middle: DVOL is too wide.** BTC stayed inside DVOL's 25–75% band 56% of the time (vs
50%), and the PIT histogram has a hump (variance ratio 0.91). DVOL's high level makes the central
part of the distribution too spread out. Realised vol is closer in the middle (52%) but, as above,
fails in the tails (U-shaped PIT, variance ratio 1.09).

**4. Up vs down tail.**
- *Downside:* DVOL is well calibrated. BTC fell below its 5th percentile 4.6% of the time (expected 5%).
  Realised vol: 8.8%.
- *Upside:* both models under-predict rallies. BTC rose above the 95th percentile 8.3% of the time for
  DVOL and 10.5% for realised vol (expected 5%). Digital probabilities tell the same story: at every
  strike, BTC finished above the strike slightly more often than predicted (e.g. 110% strike:
  forecast 24.7%, observed 26.4%). Two likely reasons are BTC's strong rise over the sample and the
  risk-neutral drift, which by construction assumes no expected return.

**5. Head to head.** Lower Brier score and higher log score are better.

| | DVOL | realised vol | p-value (daily / non-overlap) |
|---|---|---|---|
| Brier, all 5 strikes | **0.1645** | 0.1678 | 0.035 / 0.28 |
| Brier, up tail (110%, 120%) | **0.1594** | 0.1662 | 0.11 / 0.25 |
| Brier, down tail (80%, 90%) | **0.1262** | 0.1278 | 0.65 / 0.84 |
| Log score (whole distribution) | **0.36** | 0.13 | 0.011 / 0.077 |

DVOL wins on every measure. The log score, which rewards getting the whole distribution right
including the tails, shows the clearest gap. With only 67 independent windows the non-overlapping
results are borderline, so the evidence is **consistent but not overwhelming**.

## Caveats

- **Short sample.** 5.5 years, dominated by one big cycle, gives only 67 independent 30-day windows.
- **Rates ignored.** BTC futures usually trade at a premium (a positive basis). Including it would
  shift the distribution up slightly and would partly address the upside miss.
- **Lognormal is the wrong shape for BTC.** Its returns have fatter tails and a thinner middle.
  That's exactly the "too wide in the middle, too thin in the upper tail" pattern we see. Using
  the full option smile instead of a single vol number is the natural next step.
- **Newey-West still slightly optimistic.** Even with 60 lags, simulation shows its standard errors
  run ~10% small with this much overlap, so treat overlapping p-values near 0.05 with care.

Files: `results.md` (all tables), `*.csv`, `forecasts.parquet` (every forecast and outcome), and
the charts `forward_cone.png`, `historical_cones.png`, `pit_histograms.png`, `reliability.png`,
`vol_levels.png`. Reproduce with `python -m src.phase2`.
