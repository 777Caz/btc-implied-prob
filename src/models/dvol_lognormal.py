"""
Lognormal 30-day BTC distribution with DVOL as the volatility.

The maths
---------
Treat DVOL (annualised, in percent) as the volatility sigma = DVOL / 100 of BTC over the next
30 days, and assume the log return is normally distributed:

    ln(S_T / S_0)  ~  N( mu, s^2 ),     s  = sigma * sqrt(t)
                                        mu = -0.5 * sigma^2 * t

with t = 30/365 years (DVOL, like VIX, annualises with a 365-day year).

Why the drift is -0.5*sigma^2*t: under the risk-neutral measure (and with zero interest rate)
the *expected price* must equal today's price, E[S_T] = S_0. For a lognormal,
E[S_T] = S_0 * exp(mu + s^2/2), so mu = -s^2/2. The median of S_T is therefore slightly BELOW
S_0 (S_0 * exp(-s^2/2)), while the mean equals S_0. With sigma = 50% that's a -1.0% median shift
over 30 days: small but not zero.

Rates are ignored for now. Strictly the drift should be (r - 0.5*sigma^2)*t using the funding
rate or futures basis. Over 30 days that's ~0.4% for a 5% annual basis, a small shift.

Everything follows from the normal CDF N() and its inverse:

    percentile q:    S_q = S_0 * exp( mu + s * N^-1(q) )
    P(S_T > K)   :   N(d2),  d2 = ( ln(S_0/K) + mu ) / s     (the Black-Scholes "N(d2)")
    PIT          :   u = N( (ln(S_T/S_0) - mu) / s )         (where the outcome fell, 0..1)
    log score    :   log of the normal density of ln(S_T/S_0), a scalar measure of how
                     well the whole distribution anticipated the outcome (higher = better)

Caveat about DVOL as sigma: DVOL is built like VIX, from a strip of out-of-the-money options
across all strikes (a model-free "variance swap" style average over the smile), not from the
at-the-money option alone. Because the smile is higher away from the money, DVOL typically sits
ABOVE at-the-money implied vol. On top of that, implied vol usually exceeds the vol that is
later realised (the variance risk premium). Both push DVOL-based distributions to be too wide
if the lognormal model were otherwise right.

All functions are vectorised: pass floats or numpy arrays / pandas Series.
"""
import numpy as np
from scipy.stats import norm

DAYS = 30
YEAR = 365.0
T = DAYS / YEAR            # horizon in years


def params(sigma, t: float = T):
    """Mean and std of ln(S_T/S_0). `sigma` is annualised vol as a decimal (0.50 = 50%)."""
    sigma = np.asarray(sigma, dtype=float)
    s = sigma * np.sqrt(t)
    mu = -0.5 * s**2
    return mu, s


def percentile(s0, sigma, q, t: float = T):
    """Price level with probability q of S_T finishing below it."""
    mu, s = params(sigma, t)
    return np.asarray(s0) * np.exp(mu + s * norm.ppf(q))


def prob_above(s0, k, sigma, t: float = T):
    """P(S_T > K): the model price of a digital call paying 1 if BTC finishes above K."""
    mu, s = params(sigma, t)
    d2 = (np.log(np.asarray(s0) / np.asarray(k)) + mu) / s
    return norm.cdf(d2)


def pit(s0, s_t, sigma, t: float = T):
    """Probability integral transform: the model's CDF evaluated at the realised price.
    If the model is right, PIT values are uniform on [0, 1]."""
    mu, s = params(sigma, t)
    z = (np.log(np.asarray(s_t) / np.asarray(s0)) - mu) / s
    return norm.cdf(z)


def log_score(s0, s_t, sigma, t: float = T):
    """Log density of the realised log return under the model (natural log; higher is better)."""
    mu, s = params(sigma, t)
    x = np.log(np.asarray(s_t) / np.asarray(s0))
    return norm.logpdf(x, loc=mu, scale=s)
