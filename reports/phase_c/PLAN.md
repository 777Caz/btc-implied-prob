# Roadmap C plan: from risk-neutral q to real-world p with an exponential-quadratic kernel

Status: plan only, nothing implemented. Written 2026-10-03.

## 1. What we are estimating, and on which data

**Inputs, one per settlement day.**
- The risk-neutral density q_t(x) of x = ln(S_s / F_t,s), from the 08:00 UTC front smile scaled
  to the settlement time s (`src/short_horizon.py`).
  - Settings: SVI centre m constrained, variance time with the event-day profile, α = 0.5.
- Two targets:
  - **noon NY:** the Binance close, as Polymarket settles; 2021-06 onward, about 1,870 days.
  - **17:00 NY:** the Binance close for the long history. BRTI (Kalshi's expiration value,
    2024-06 onward) is used when the result feeds the Kalshi comparison.
- The forward includes the basis to whichever settlement source is used.

**Why the 1-day distributions rather than 30-day:**
- Every day is a separate, non-overlapping outcome. Settlement is before the next 08:00 origin.
- That gives about 1,870 independent observations, against about 64 non-overlapping 30-day
  windows (phase 3).
- The 30-day and weekly expiries are a secondary application (section 7).

**The model.**

    p_t(x) = q_t(x) · exp(γ x + δ x²) / Z_t(γ, δ),     Z_t = ∫ q_t(x) exp(γ x + δ x²) dx

**The implied pricing kernel** (the stochastic discount factor up to a constant) is

    M_t(x) ∝ q_t(x) / p_t(x) = Z_t · exp(−γ x − δ x²)

- **With δ = 0** this is the power-utility kernel M ∝ (S/F)^−γ (roadmap item C as first
  written: p ∝ q·S^γ).
- **δ adds curvature:** a U-shaped kernel when δ < 0, i.e. investors pay extra for both tails.
  That is how a variance risk premium shows up in a kernel.

## 2. What γ and δ each correct

The cleanest intuition is a Gaussian q with mean μ and variance v. Multiplying by
exp(γx + δx²) and completing the square gives another Gaussian:

    v_p = v / (1 − 2δv)            (needs δ < 1/(2v))
    μ_p = v_p · (μ/v + γ)

- **δ corrects the width, i.e. the variance risk premium.**
  - δ < 0 gives v_p < v: real-world outcomes are less dispersed than options price.
  - Our 1-day forecasts are uniformly slightly too wide (PIT variance ratio 0.92–0.95), so we
    expect δ < 0.
  - Solving 1/(1 − 2δv) ≈ 0.93 gives δ·v ≈ −0.04.
  - **Caveat from the Kalshi comparison** (`reports/pm/kalshi_vs_options/`): on the 518 Kalshi
    days (2024-07 to 2026-09), q's strike probabilities are already well calibrated
    (logistic slope 0.985 ± 0.04). The 1-day premium may be small in that period and mostly in
    the far tails.
- **γ corrects the location, i.e. the drift or equity risk premium.**
  - γ > 0 moves mass to the upside: the real-world expected return exceeds the risk-neutral
    one, which is roughly zero over a day.
  - This is the term that could absorb the "options under-predict rallies" finding of phases 2–3.
- **What neither can fix:** an asymmetric tail miss. A quadratic tilt changes only the mean and
  variance of a Gaussian-shaped q, so for a skewed q it rescales both tails together.
  - If the miss is one-sided (upside only), the extension is a split δ (δ₊ for x > 0, δ₋ for
    x < 0), tested as a nested model in section 5.

**Parametrisation across days.** v changes a lot from day to day (vol regime, weekends, event
days), so a fixed (γ, δ) would mean a different variance ratio on every day. The primary fit
therefore uses standardised moneyness u = x / √v_t, with v_t the variance of q_t:

    p_t(u) ∝ q_t(u) · exp(γ' u + δ' u²)     ⇔     γ_t = γ'/√v_t,  δ_t = δ'/v_t  in the x form above

- **γ' is a drift in daily-SD units** (Sharpe-ratio-like).
- **δ' sets a constant variance ratio** 1/(1 − 2δ').
- This is the same exponential-quadratic family on each day. It only fixes how the coefficients
  scale across days.
- **Alternative to test:** raw x with constant (γ, δ). Choose by out-of-sample log score.

## 3. Normalisation and numerics

- **Grid:** q_t is already on a strike grid of ±16 ATM SDs, 6,001 points.
- **Prepare q:** convert to x (or u). Set the small negative Breeden-Litzenberger values to 0,
  then renormalise q to mass 1 (store the dropped mass as a diagnostic).
- **Compute log Z by log-sum-exp:**

      log Z_t = log Σ_i q_i exp(γ x_i + δ x_i²) Δx_i

  - Trapezoid weights.
  - Log-sum-exp because exp(δx²) overflows for large x when δ > 0.
- **Integrability:**
  - When δ ≤ 0 the integral always exists.
  - When δ > 0 (p wider than q) the true integral diverges for any q with tails fatter than
    Gaussian, which SVI's linear wings imply. On the truncated grid the answer then depends on
    where the grid stops.
  - So δ' is constrained to ≤ 0.05 and we report if the bound binds. If it does, p wants to be
    wider than q, which would itself be a finding.
- **Strike probabilities under p** come from the same grid:
  P_p(S > K) = Σ_{x_i > ln(K/F)} p_i Δx_i.

## 4. Estimation: rolling maximum likelihood with no look-ahead

**Log-likelihood.** For a realised outcome x_t, the log-likelihood of day t is

    ℓ_t(γ, δ) = ln q_t(x_t) + γ x_t + δ x_t² − ln Z_t(γ, δ)

ln q_t(x_t) doesn't depend on the parameters, so the MLE maximises
Σ_t [γ x_t + δ x_t² − ln Z_t(γ, δ)].

**Why the fit is easy and the parameters interpretable:**
- ln Z_t is the cumulant-generating function of (x, x²) under q_t. It is therefore convex, the
  objective is concave, the maximum is unique, and Newton's method converges in a few steps.
- The first-order conditions are moment matching:

      Σ_t (x_t − E_p_t[x]) = 0,       Σ_t (x_t² − E_p_t[x²]) = 0

  γ makes the tilted distributions match the realised mean on average, and δ makes them match
  the realised second moment. The Hessian is minus the summed covariance matrix of (x, x²)
  under p_t.

**Standard errors:**
- Use the sandwich form H⁻¹ S H⁻¹, with S the outer product of the daily scores.
- Add a Newey-West correction with 5 lags, because vol clustering makes squared outcomes
  serially correlated even though the outcomes themselves don't overlap.

**No look-ahead:**
- At origin t, (γ, δ) is estimated only from days whose settlement is before t.
- Two windows: expanding, and rolling 365 days.
- The first forecast needs at least 180 days of history.
- q_t itself is already look-ahead-free (section 5 of the short-horizon module).

**Out-of-sample products for each day:**
- p_t
- the log-score gain over q_t, which is just γx_t + δx_t² − ln Z_t at the frozen parameters
- PIT
- strike probabilities for the Kalshi/Polymarket comparison

**Expected precision.** This is the main limitation; I'd state it upfront.
- **δ':** the score for δ' has variance of about 2 per day, so SE(δ') ≈ √(2/n)/2. That's about
  0.016 on the full sample and about 0.04 for one year.
  - In variance-ratio terms: ±0.03 overall, ±0.07 per year.
  - The full sample can detect the expected ratio of about 0.93. A single year mostly can't.
- **γ':** SE(γ') ≈ 1/√n ≈ 0.023 on the full sample.
  - With a daily SD of about 2.5%, that's ±0.06% per day, or about ±20% a year in drift.
  - So γ is weakly identified, which is the classic equity-premium problem.
  - The many Kalshi strikes per day don't help: they all settle on the same single outcome.
- **The variance premium is what this data can identify. The drift premium mostly can't.**
- We report γ with that caveat, and also fit a δ-only model (γ = 0) as the parsimonious
  alternative.

## 5. Stability tests

Fitted separately for noon NY and 17:00 NY first. Then we test whether one (γ', δ') serves both.

**By calendar year (2021–2026):**
- Fit per year.
- Wald test of equality: χ² with 2·(years − 1) degrees of freedom, robust SEs.
- Expect wide per-year intervals (section 4), so look at δ' mainly.

**By regime, each known ex ante at the origin:**
- **Vol regime:** DVOL terciles at 08:00.
- **Trend:** sign of the trailing 30-day return, and price above or below its 200-day average.
- **Weekend vs weekday:** weekend variance-time scaling is the shakiest part of q.
- **Event days vs other days** (CPI/NFP/FOMC).
- **Stress windows:** 2022-05 (LUNA) and 2022-11 (FTX).

Method: interaction model γ' = γ₀ + γ₁·D, δ' = δ₀ + δ₁·D, with a likelihood-ratio test of
γ₁ = δ₁ = 0.

**Time variation:**
- Plot rolling 365-day estimates with bands.
- Run the Nyblom (Hansen) parameter-constancy test. It uses the cumulative sum of daily scores,
  which sums to zero at the MLE, so a drifting path means unstable parameters.

**Shape check:**
- Add a split δ (δ₊, δ₋) as a nested model and run a likelihood-ratio test.
- Check upper and lower tail coverage of p separately (below 5% and above 95%), with Wilson CIs.

**Outlier sensitivity:**
- δ matches x², so a few crash days carry a lot of weight.
- Refit excluding the top 1% of |u| days, and report the change.

## 6. Comparisons

All are out of sample, on the same days and targets, refitted on the same rolling windows.

| Model | What it is | Why it's here |
|---|---|---|
| **q** | raw scaled option density | the baseline being corrected |
| **p, kernel** | exponential-quadratic tilt (γ', δ') and δ-only | the model |
| **PIT recalibration** | p_CDF(x) = G(F_q(x)), with G a smoothed empirical CDF (or beta-calibration map) of past PITs | nonparametric version of the same idea. The kernel says p/q = e^{γx+δx²}/Z; this says p/q = g(F_q(x)) for any monotone G. If it wins clearly, the quadratic form is too rigid |
| **Logistic recalibration of strike probabilities** | P = sigmoid(a + b·logit(q)) on past days' strikes, clustered by day | matches the Kalshi analysis exactly, so the slopes are directly comparable |
| **GARCH(1,1)-t** | daily 08:00→08:00 log returns, Student-t innovations, refitted monthly on a trailing 1,000 days. The next-day variance is scaled to the settlement time by the same variance-time fraction λ, so only the information set differs | a pure real-world benchmark with no option information. This is roadmap B's GARCH. It isn't built yet, so C includes building it (the `arch` package, pinned, or a ~60-line scipy MLE) |

**Scores:**
- Log score (density) and CRPS.
- PIT variance ratio, and tail coverage at 5% and 95%.
- Brier on the Kalshi/Polymarket strike sets.
- Paired Diebold-Mariano tests on daily score differences, with Newey-West SEs (5 lags).

**For the thesis:**
- Re-run the Kalshi encompassing regression with p in place of q:
  P(YES) = sigmoid(a + b1·logit(mid) + b2·logit(p)).
- Compare the Kalshi mid with q and with p by price bucket.

## 7. Secondary horizons

- **Native daily expiries:** 08:00 → 08:00 the next day, using the unscaled front smile. This
  checks that the scaling isn't driving the result.
- **Weekly Friday expiries:** about 270 non-overlapping weeks.
- **30-day (phase 3):** fit the same kernel on the 30-day densities to compare with phase 3's
  upside miss. Overlapping windows need the 30-day block bootstrap from `src/phase3_robust.py`.
- **Question for every horizon:** does δ' scale with horizon as a constant variance-risk-premium
  share would predict?

## 8. Implementation steps (when approved)

1. **Store densities:** `src/short_horizon.py` writes each day's q on a standardised grid to
   `data/processed/short_horizon/densities.parquet`, with u ∈ ±16 SDs at 801 points, plus v_t,
   F_t and the outcome under each settlement source. All fits then run without refitting smiles.
2. **`src/models/kernel.py`:** log Z by log-sum-exp, moments under p, Newton MLE, sandwich and
   Newey-West SEs, and strike probabilities.
   - Unit test: simulate outcomes from a known tilt of real q's and recover (γ', δ') with
     correct coverage.
3. **`src/models/garch_t.py`:** rolling GARCH(1,1)-t, also with a unit test on simulated data.
4. **`src/phase_c.py`:**
   - rolling fits (expanding and 365-day)
   - benchmarks and scores
   - stability tests and charts: rolling (γ', δ'), PIT histograms, implied kernel M(u)
   - results to `reports/phase_c/`
5. **Kalshi re-run:** run the Kalshi encompassing regression with p.
6. **Write-up:** update SUMMARY.md and PROJECT_BRIEF.md.

## 9. Decisions needed before starting

1. **Parametrisation:** standardised u as primary with raw x as the alternative (recommended),
   or raw x only?
2. **Long-history settlement source:** Binance for both targets, with BRTI only for the Kalshi
   comparison (recommended), or BRTI-only, which limits us to 2024-06 onward?
3. **GARCH-t:** OK to add `arch` as a pinned dependency?
4. **Model-selection rule:** choose the kernel form by out-of-sample log score on the pre-2026
   data, and keep 2026 as a final holdout, matching the Kalshi analysis?
