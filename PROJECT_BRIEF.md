# btc-implied-prob: project brief (state as of 2026-10-02, updated after the phase 3 robustness checks)

A self-contained description of the project: what it is for, what has been built, what the results
are, and what is still open. It's written to plan the next phases, especially how to bring in the
prediction-market comparison.

---

## 1. The question

> **Are prediction markets efficient once you account for the risk premium in options?**

Three sets of probabilities exist for the same event, e.g. "BTC above $90k on Friday":

| Source | What it gives | How |
|---|---|---|
| **Deribit options** | Risk-neutral probability q(S) | Breeden-Litzenberger: q(S_T > K) = −∂C/∂K, density = ∂²C/∂K² |
| **Options with the risk premium removed** | Real-world probability p(S) | Pricing-kernel tilt p(S) ∝ q(S)·S^γ, or empirical recalibration |
| **Polymarket / Kalshi** | Market-implied probability | YES price (bid/ask/mid) |

How to read the gaps:
- **Prediction market vs real-world p:** a gap means the prediction market is inefficient. The
  trade is unhedged: buy the cheap side and hold it to settlement.
- **Prediction market vs risk-neutral q:** a gap is a hedgeable arbitrage (buy the contract, hedge
  with a Deribit call spread). It only counts if it survives the settlement mismatch (different
  index and time, see section 4) and costs.
- **q vs p:** the gap between them is the risk premium itself. It's what phases 2-3 have been
  measuring indirectly.

Why it matters: prediction markets are often compared with option-implied probabilities as if
those were "the truth". They aren't. They're risk-neutral, and a prediction market that disagrees
with them may be *right* about real-world odds. The risk premium has to be stripped first.

---

## 2. Data inventory

All sources are free and public, with no API key. Timestamps are UTC everywhere and storage is
parquet. `data/` (1.2 GB) is git-ignored and travels as a zip.

| Dataset | Coverage | Source / notes |
|---|---|---|
| BTC price: daily, hourly, 08:00 UTC; Deribit index every 6h | 2021-01 → 2026-09-30 | Deribit + Coinbase hourly candles |
| DVOL (Deribit 30-day implied-vol index), daily and hourly | 2021-03 → 2026-09-30 | Deribit |
| **Deribit option trades** | **2021-01 → 2026-09, 69 monthly files, 22.7M trades** | `history.deribit.com` (undocumented full archive; `www` keeps only 24h). Columns include price (BTC), iv, index_price, amount, contracts, direction, block/combo ids and leg counts, is_block, is_combo |
| Deribit delivery (settlement) prices | 2,101 expiries, 2021-01-01 → 2026-10-02 | `public/get_delivery_prices` |
| **Live snapshots** (Deribit full chain + Polymarket + Kalshi, synchronised within about 2 seconds) | **2026-09-30 → now, only 31 snapshots as of 2026-10-02 20:47 UTC** (Mac was mostly asleep). Running every 10 min on a Windows PC since 2026-10-02 20:50 UTC (first scheduled run confirmed) | `src/snapshot.py`. Can't be rebuilt from history, so every missed snapshot is lost |
| Prediction-market resolutions | 3,297 resolved markets (3,140 Kalshi, 157 Polymarket), all seen in snapshots | `src/resolutions.py`, daily |
| Prediction-market history (backfill) | Kalshi 12:00/17:00 NY events since 2024 (1-minute bid/ask); Polymarket daily/weekly since 2025 (1-minute mid) | `src/pm_backfill.py` |
| Binance BTC/USDT 1-minute candles at Polymarket resolution times | daily 12:00 New York + other seen times | Polymarket settles on this, and its API doesn't publish the settlement price |

**Prediction-market history:** being backfilled (roadmap D). See section 7, question 1, for
what each venue provides.

---

## 3. Code map

Every script runs as a module from the project root: `.venv\Scripts\python -m src.<name>`.

| Module | Role |
|---|---|
| `config.py` | Paths (pathlib), dates, API URLs, logging (UTC timestamps) |
| `src/api.py`, `src/storage.py` | HTTP with retries/pacing, Deribit JSON-RPC wrapper; parquet upsert helpers |
| `src/deribit_prices.py`, `src/deribit_dvol.py` | Price and DVOL history |
| `src/deribit_options.py` | Historical option trades, one file per month, resumable (`python -m src.deribit_options 2021-01-01 2026-11-01`) |
| `src/snapshot.py` | Live snapshot: Deribit chain (bid/ask/mark, mark IV, forward, OI) + Polymarket (Gamma API to find markets, CLOB `/books` for order books) + Kalshi (`KXBTCD` above/below, `KXBTC` ranges). Warns in the log on a gap of 30+ min |
| `src/resolutions.py` | Daily: Deribit deliveries, prediction-market outcomes (Kalshi `result` + BRTI `expiration_value`; Polymarket UMA status "resolved"), Binance candles. Idempotent. Logs a snapshot staleness/gap check |
| `src/checks.py` + `notebooks/01_data_checks.ipynb` | Data quality: coverage/gaps, timezones, duplicates, bad values, snapshot gaps |
| `src/models/dvol_lognormal.py`, `src/models/realized_vol.py` | Phase 2 models |
| `src/calibration.py` | PIT, tail-breach tests, digital (P > K) Brier, log score, Newey-West comparisons |
| `src/phase2.py` | Phase 2 pipeline |
| `src/clean_trades.py` | Trade cleaning rules |
| `src/forwards.py` | Forward per expiry from put-call parity |
| `src/models/smile.py` | Black-76, implied vol, **SVI with butterfly and vertical-spread penalties**, spline alternative, Breeden-Litzenberger `Distribution`, `Surface` (total-variance interpolation) |
| `src/phase3.py`, `src/phase3_hist.py` | Phase 3: live snapshot fits, forward validation, historical daily surfaces (multiprocessing) and 30-day calibration |
| `src/visuals.py` | All charts |
| `deploy/` | `register_tasks.ps1` + `run_task.py` (Windows Task Scheduler: snapshot every 10 min, resolutions 00:30 UTC); `crontab.txt` (Mac/Linux) |

---

## 4. Key technical decisions and quirks

**Deribit options are inverse.** Prices are in BTC: BTC price = (USD Black-76 value) / F.

**Forward from put-call parity, no rates needed.** A call minus a put at the same strike pays
(S_T − K)/S_T = 1 − K/S_T BTC. Its BTC price is therefore c − p = 1 − K/F. Rearranged:
**F = K / (1 − (c − p))**. Each call/put pair traded within 5 minutes gives one estimate, and the
median across pairs is used.
- **Accuracy:** median error 3.5 bp against live snapshot forwards and against Deribit futures.
- **Gaps:** expiries with too few pairs (53% of expiry-days) get the forward interpolated in ln(basis) vs T.
- **Not discounted (checked):** fitting c − p = DF·(1 − K/F) on Deribit's own marks gives DF − 1 ≈ 0 bp at
  every tenor, out to ~1 year. Error vs futures grows only slightly with tenor (2.6 → 4.2 bp median).

**Smile = SVI on total variance w(k) = σ²T vs log-moneyness k = ln(K/F).** SVI was chosen over a
spline because its wings extrapolate the way no-arbitrage theory allows. Even with a perfect fit,
unconstrained SVI can be arbitrageable, so the fit is penalised for:
- **butterfly arbitrage:** Gatheral's g(k) < 0, i.e. a negative density;
- **vertical-spread arbitrage:** P(S_T > K) = N(d₂) − φ(d₂)·w′/(2√w) outside [0, 1].

Time interpolation is linear in total variance at fixed k (forward log-linear). Densities come from
Black-76 prices on a fine strike grid, differentiated numerically.

**Historical fits:**
- **Trades used:** the 8 hours before 08:00 UTC, pooled per strike (median k and IV, weighted by trade count).
- **Gates per expiry:** ≥ 15 trades, ≥ 5 strikes, strikes on both sides of the forward, span ≥ 1 standard deviation.
- **Cleaning removes:** iv = 0, iv ≥ 300, combo legs, and trades with < 1 day to expiry.

**Settlement differs by venue.** This is the central obstacle for any hedged trade:

| Venue | Reference price | Time |
|---|---|---|
| Deribit | Deribit BTC index, 30-min TWAP | 08:00 UTC |
| Polymarket | Binance BTC/USDT 1-minute close | 12:00 New York (16:00 or 17:00 UTC) |
| Kalshi | CF Benchmarks BRTI, 60-second average | 12:00 or 17:00 New York (also hourly events) |

So a Polymarket "BTC above K at noon NY" contract has to be compared with an options distribution
**interpolated to 12:00 NY**, not to a Deribit expiry. The basis between Binance, BRTI and the
Deribit index is a second-order risk.

**Prediction-market parsing quirks:**
- **Polymarket:** the strike is parsed from `groupItemTitle` ("84,000", "74,000-76,000",
  "<74,000"), not `groupItemThreshold`. Book levels are unsorted, so best bid = max and best ask =
  min. Hourly events often have zero volume and leftover quotes.
- **Kalshi:** an empty side comes as 0.00/1.00 with size 0. It's stored as empty (NaN), not as a
  price. Strikes look like 84,099.99, which means $84,100 or more.
- **Market counts swing a lot through the day** as events list and settle (Kalshi 260–636 markets
  per snapshot). This is normal.

---

## 5. Results so far

### Phase 2: DVOL lognormal vs trailing realised vol, 30-day forecasts
- **Sample:** 08:00 UTC daily origins 2021-03-24 → 2026-08-31. 1,987 overlapping and 67 non-overlapping windows.
- **Outcome:** Deribit delivery price. Overlapping tests use Newey-West with 60 lags.

| | DVOL | realised vol |
|---|---|---|
| mean vol level | 59.9% (realised next 30d: 51.1%), i.e. a ~9 pt variance premium | 51.4% |
| outside 5–95% band (expect 10%) | 12.8% | 19.2% |
| Brier, 5 strikes | **0.1645** | 0.1678 (p = 0.035) |
| log score | **0.36** | 0.13 (p = 0.011) |

DVOL wins, mostly in the tails. DVOL is too wide in the middle. **Both under-predict rallies:**
BTC was above the 95th percentile 8.3% of the time with DVOL (expected 5%).

### Phase 3: full smile (SVI + Breeden-Litzenberger)
- **Fits:** 15,729 of 18,568 expiry-days fitted (84.7%), with median fit error 0.50 vol points.
- **Sample:** 1,892 common 30-day origins.

| | smile | DVOL | realised vol |
|---|---|---|---|
| PIT variance ratio (1 = right) | **1.02** | 0.91 | 1.08 |
| above 95th pct (expect 5%) | 8.8% | 7.9% | 10.0% |
| below 5th pct (expect 5%) | 3.9% | 4.5% | 8.7% |
| P(>120%): forecast vs observed 13.0% | 10.1% | 11.6% | 9.0% |
| Brier | **0.1627** | 0.1632 | 0.1664 |
| log score | **0.379** | 0.369 | 0.155 |

- **Best shape:** the smile's PIT is flat and the middle-band problem is gone.
- **Not a better forecast than DVOL:** the differences aren't significant (log score p = 0.63).
- **The upside miss stays:** every option-based model under-predicts rallies, and the downside is
  fine or too cautious. Changing the shape can't fix a one-sided miss.
- **Robustness (2026-10-02, `src/phase3_robust.py`):**
  - **The upside miss is weak.** It's concentrated in **2023–24**: above the 95th percentile 14.7%
    and 16.9% of the time, against 2–6% in other years. With 30-day block-bootstrap CIs (needed
    because daily windows overlap) it's **not significant over the full sample**: 8.8%, 95% CI
    4.5–14.0%. 2026 shows the mirror image on the downside (18.4% below the 5th percentile).
  - **No look-ahead** in any of the 2,099 historical fits.
  - **No discounting** in Deribit prices (see section 4).
  - **Exploratory option test is inconclusive.** Buying a 30-day 25-delta call every 30 days:
    −0.25% of S0, CI −1.7 to +1.5. The 25-delta risk reversal: +0.47%, CI −1.7 to +2.7. Both use
    58 trades, include costs, and make their gains only in 2023–24.
- **Interpretation:** a risk-neutral vs real-world gap on the upside is plausible (options price
  crash insurance), but **30-day option history alone can't pin it down**: about 64 independent
  windows from one bull cycle. Short-dated prediction-market events, with thousands of
  independent outcomes, are the better place to measure it.

---

## 6. Roadmap and status

| | Item | Status |
|---|---|---|
| **A** | **Finish phase 3.** Forward validation error by tenor, including whether Deribit prices are discounted. Confirm no look-ahead. Tails separately and split by year (2022 vs rest). Exploratory 25-delta call / risk-reversal test if the upside miss persists | **Done** (2026-10-02). See section 5 and `reports/phase3/robustness/` |
| **B** | **Extensions.** Return distribution (skew, kurtosis, Q-Q, ACF of squared returns). GARCH(1,1) Student-t baseline refitted with no look-ahead. Heatmap restyle (dark, plasma, log colour, price history on the left) plus a historical density strip with the realised price | Not started |
| **C** | **Risk premium.** Pricing-kernel tilt p(S) ∝ q(S)·S^γ with γ fitted by rolling maximum likelihood. Empirical recalibration (logistic/isotonic) as comparison. Daily and weekly expiries. γ stability across regimes | Not started. **Key for the thesis** |
| **D** | **Prediction markets.** Backfill Polymarket/Kalshi historical prices for past BTC markets. Score their calibration vs raw q and premium-adjusted p (test, don't assume, favourite-longshot bias). Cross-venue Polymarket vs Kalshi at the same settlement time, after fees | Feasibility checked (section 7). Backfill of Kalshi 12:00/17:00 NY events and Polymarket daily/weekly markets in progress |
| **E** | **Phase 4: trading test.** Options fair value at the exact settlement time. Compare with bid/ask using a liquidity filter. Costs. Backtest unhedged, hedged call-spread and cross-venue strategies | Not started |
| **F** | **Dashboards.** Research dashboard + arb monitor (static Plotly HTML) | Not started |

Out of scope: 5- and 15-minute markets. Hourly markets are optional.

---

## 7. Open questions for planning the prediction-market integration

1. **Backfill feasibility (D): answered 2026-10-02.**
   - **Kalshi:**
     - **Data:** 1-minute candles with **YES bid and ask** OHLC, plus trades.
     - **History:** `KXBTCD`/`KXBTC` from Mar/Jun 2024. 12:00 New York events: 659 per series
       since Q4 2024. 17:00 New York events: 793 per series since Jun 2024.
     - **Size:** about 214k markets (25 → 75 → 188 strikes per event over time).
     - **Archive:** markets settled before the 2026-08-03 cutoff come only from `/historical/...`.
     - **Quirks:** candles exist only in minutes where something changed (forward-fill). Candles
       match our live snapshot quotes to within 1¢ 97–99% of the time.
   - **Polymarket:**
     - **Data:** `prices-history` gives the **mid only** (matches the snapshot mid; no historical
       bid/ask), at 1-minute resolution over each market's whole life.
     - **History:** "above K" since Jan 2025 (437 events, 4.3k markets), ranges since Feb 2025
       (417 events, 4.3k markets).
     - **Resolution time:** must come from the rules (noon New York), not Gamma's `endDate`,
       which is wrong for early-2025 events.
2. **Matching time.** Compare the prediction-market price at time t with the option surface at the
   same t. That needs intraday surfaces: from live snapshots going forward, from trades historically
   (pool a window before t, like the 08:00 fits). Decide the window and staleness tolerance.
3. **Horizon interpolation.** Prediction markets settle at 12:00/17:00 New York, often < 1 day
   ahead. Phase 3 dropped expiries under 1 day and only interpolates *between* fitted expiries.
   Short-dated and same-day interpolation needs thought: daily Deribit expiries help, and Deribit
   expiry is 08:00 UTC, before the New York times.
4. **Settlement basis.** Model the Binance / BRTI vs Deribit index difference at settlement
   (resolutions already store all three), or just measure it and treat it as noise.
5. **Which contracts to score.** "Above K" maps directly to q(S_T > K). Ranges map to differences of
   two of those. Rules are needed for open-ended tails and illiquid strikes (spread, volume, size filters).
6. **Risk-premium order.** Fit γ (C) on the 30-day option history first, then check it transfers to
   1–7 day horizons where prediction markets live, or fit it directly on short expiries.
7. **Evaluation design.** Calibration (Brier/log score/reliability) of prediction-market mid vs q vs
   p on the same resolved contracts. Plus the favourite-longshot test: regress outcome on price in
   logit space, slope ≠ 1. Clustering by event matters, because markets in one event share one
   outcome path, so effective sample sizes are much smaller than market counts.
8. **Sample size.** The live sample grows by ~144 snapshots/day, and each Kalshi/Polymarket event has
   dozens of strikes but **one** underlying outcome. Weeks of live data are only a few dozen
   independent outcomes. The backfill (1) is what makes the statistics meaningful.

---

## 8. Working style

Step by step, explaining the maths and design choices, waiting for review between steps. UTC
everywhere. raw/ is never edited, and derived data goes to processed/.
