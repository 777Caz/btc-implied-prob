"""
The option smile -> a full risk-neutral distribution of BTC at expiry (phase 3, steps 3-5).

1. Coordinates
   Log-moneyness  k = ln(K / F)   (F = forward for that expiry)
   Total implied variance  w(k) = sigma_impl(k)^2 * T
   Working in (k, w) puts every expiry on a common footing: w grows roughly with T, and the
   no-arbitrage conditions are simple in these coordinates.

2. Smile model: SVI ("stochastic volatility inspired", Gatheral 2004)
       w(k) = a + b * ( rho*(k - m) + sqrt((k - m)^2 + s^2) )
   Five parameters: a (level), b (wing steepness), rho (skew, -1..1), m (shift), s (ATM curvature).
   Why SVI rather than a spline:
     * It's a smooth hyperbola. Its wings become straight lines in (k, w), which is exactly the
       large-strike behaviour no-arbitrage theory allows (Lee's moment formula: slope <= 2). A spline
       has no reason to extrapolate sensibly past the last traded strike, and the density lives
       partly out there.
     * Five parameters can't chase noise in individual trades the way a flexible spline can.
       Wiggles in w become NEGATIVE densities after differentiating twice.
     * Butterfly arbitrage has a closed-form test (g(k) below).
   We fit it robustly (soft-L1 loss, several starting points), parametrised so that the minimum
   total variance is >= 0 and the wings obey Lee's bound b*(1+|rho|) <= 2. A smoothing spline in
   (k, w) is kept as a fallback when SVI fails to converge or fits badly, and those cases are flagged.

3. No-arbitrage checks
   Butterfly (density >= 0): the density at k is proportional to
       g(k) = (1 - k w'/(2w))^2 - (w'^2/4) * (1/w + 1/4) + w''/2
   so g(k) < 0 anywhere <=> negative density <=> a butterfly spread with negative price.
   Calendar: at every k, total variance must not decrease with expiry: w(k, T2) >= w(k, T1).
   Otherwise a longer option would be cheaper than a shorter one.

4. Density: Breeden-Litzenberger (1978)
   Undiscounted USD call price on the forward (Black-76, zero rates, as Deribit prices):
       C(K) = F N(d1) - K N(d2),  d1 = (-k + w/2)/sqrt(w),  d2 = d1 - sqrt(w),  w = w(k)
   Because C(K) = E[(S_T - K)+], differentiating under the expectation gives
       dC/dK   = -P(S_T > K)             ->  P(S_T > K) = -dC/dK
       d2C/dK2 =  f(K)                   ->  the risk-neutral density
   We evaluate C on a fine uniform strike grid and take numerical derivatives. Checks: the density
   should integrate to ~1 and its mean should be ~F (a martingale under the forward measure).

5. Interpolation across expiries
   To get a distribution at any horizon T between two fitted expiries T1 < T < T2 we interpolate
   TOTAL VARIANCE linearly in T at fixed k:  w(k,T) = w1(k) + (T-T1)/(T2-T1) * (w2(k) - w1(k)),
   and the forward log-linearly (ln F linear in T). Linear-in-variance is what you get if the
   instantaneous variance is constant between expiries, and it preserves calendar no-arbitrage
   when the inputs are arbitrage-free. Before the first expiry we scale w1 by T/T1 (flat vol),
   and past the last we scale wn by T/Tn. Both are flagged as extrapolation.

Measure note: this is the USD risk-neutral density (C is valued in USD). Deribit settles in BTC, but
its BTC prices are USD prices / F, so the USD smile is what the quotes encode.
"""
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.optimize import brentq, least_squares
from scipy.stats import norm

YEAR = 365.0


# ── Black-76 ─────────────────────────────────────────────────────────────────────────────────
def black76(F, K, w, call=True):
    """Undiscounted Black-76 price (USD) from total variance w = sigma^2 T."""
    F, K, w = np.asarray(F, float), np.asarray(K, float), np.maximum(np.asarray(w, float), 1e-12)
    sw = np.sqrt(w)
    d1 = (np.log(F / K) + w / 2) / sw
    d2 = d1 - sw
    c = F * norm.cdf(d1) - K * norm.cdf(d2)
    return c if call else c - (F - K)


def implied_vol(price_usd, F, K, T, call=True):
    """Black-76 implied vol from an undiscounted USD price (NaN if outside no-arbitrage bounds)."""
    intrinsic = max(F - K, 0) if call else max(K - F, 0)
    upper = F if call else K
    if not (intrinsic < price_usd < upper):
        return np.nan
    f = lambda s: black76(F, K, s * s * T, call) - price_usd
    try:
        return brentq(f, 1e-4, 10.0, xtol=1e-8)
    except ValueError:
        return np.nan


# ── SVI ──────────────────────────────────────────────────────────────────────────────────────
@dataclass
class SVI:
    a: float
    b: float
    rho: float
    m: float
    s: float

    def w(self, k):
        k = np.asarray(k, float) - self.m
        return self.a + self.b * (self.rho * k + np.sqrt(k * k + self.s * self.s))

    def dw(self, k):
        k = np.asarray(k, float) - self.m
        return self.b * (self.rho + k / np.sqrt(k * k + self.s * self.s))

    def d2w(self, k):
        k = np.asarray(k, float) - self.m
        return self.b * self.s**2 / (k * k + self.s * self.s) ** 1.5


def _svi_from_x(x) -> SVI:
    """Parametrisation used in fitting: x = (vmin, b, rho, m, s) with vmin = minimum total variance >= 0."""
    vmin, b, rho, m, s = x
    return SVI(a=vmin - b * s * np.sqrt(1 - rho**2), b=b, rho=rho, m=m, s=s)


def prob_above_from_smile(p, k):
    """P(S_T > K) = -dC/dK under a smile w(k), in closed form:
        -dC/dK = N(d2) - phi(d2) * w'(k) / (2 sqrt(w))
    (Black-76 with w depending on k; uses F*phi(d1) = K*phi(d2).) The second term is the skew
    contribution. Must lie in [0, 1], otherwise a vertical spread is mispriced (arbitrage)."""
    w = np.maximum(p.w(k), 1e-12)
    sw = np.sqrt(w)
    d2 = -k / sw - sw / 2
    return norm.cdf(d2) - norm.pdf(d2) * p.dw(k) / (2 * sw)


def fit_svi(k, w, weights=None, arb_width: float = 6.0, m_bounds: tuple[float, float] | None = None) -> tuple[SVI | None, float]:
    """Robust least-squares SVI fit, penalised towards no arbitrage over +/- `arb_width` ATM
    standard deviations: butterfly (g >= 0) and vertical spread (0 <= P(S_T > K) <= 1).
    m_bounds optionally narrows the centre m (default [-1, 1]); used for short-dated smiles, whose few
    strikes leave m poorly identified (see src/short_horizon.py).
    Returns (params, RMSE in total variance) or (None, inf)."""
    k, w = np.asarray(k, float), np.asarray(w, float)
    wt = np.ones_like(k) if weights is None else np.sqrt(np.asarray(weights, float))
    atm = float(np.interp(0.0, np.sort(k), w[np.argsort(k)]))
    k_check = np.linspace(-arb_width, arb_width, 61) * np.sqrt(max(atm, 1e-8))
    lam = 10 * max(atm, 1e-6)      # penalty scale: an arbitrage of 0.01 outweighs typical misfit
    lo = [0.0, 1e-4, -0.999, -1.0, 1e-3]
    hi = [max(w.max(), 1e-3) * 2, 2.0, 0.999, 1.0, 2.0]
    if m_bounds is not None:
        lo[3], hi[3] = max(lo[3], m_bounds[0]), min(hi[3], m_bounds[1])
    m0 = float(np.clip(0.0, lo[3], hi[3]))

    def resid(x):
        p = _svi_from_x(x)
        r = (p.w(k) - w) * wt
        lee = max(0.0, p.b * (1 + abs(p.rho)) - 2.0)             # Lee's wing bound
        pa = prob_above_from_smile(p, k_check)
        arb = np.concatenate([np.maximum(0, -butterfly_g(p, k_check)),
                              np.maximum(0, pa - 1), np.maximum(0, -pa)])
        return np.concatenate([r, [10 * lee], lam * arb])

    best, best_cost = None, np.inf
    for rho0 in (-0.3, 0.0, 0.3):
        for s0 in (0.05, 0.2):
            x0 = [min(max(atm * 0.9, 1e-5), hi[0] * 0.99), 0.1, rho0, m0, s0]
            try:
                r = least_squares(resid, x0, bounds=(lo, hi), loss="soft_l1", f_scale=max(atm * 0.05, 1e-5))
            except ValueError:
                continue
            if r.success and r.cost < best_cost:
                best, best_cost = r.x, r.cost
    if best is None:
        return None, np.inf
    p = _svi_from_x(best)
    return p, float(np.sqrt(np.mean((p.w(k) - w) ** 2)))


def butterfly_g(p: SVI, k):
    """Gatheral's g(k); g < 0 means negative density (butterfly arbitrage)."""
    w, dw, d2w = p.w(k), p.dw(k), p.d2w(k)
    return (1 - k * dw / (2 * w)) ** 2 - dw**2 / 4 * (1 / w + 0.25) + d2w / 2


class SplineSmile:
    """Fallback: cubic smoothing spline in (k, w) with linear extrapolation beyond the data."""

    def __init__(self, k, w):
        order = np.argsort(k)
        k, w = np.asarray(k)[order], np.asarray(w)[order]
        self.kmin, self.kmax = k[0], k[-1]
        self.sp = UnivariateSpline(k, w, k=3, s=len(k) * np.var(w) * 0.01)

    def w(self, k):
        k = np.asarray(k, float)
        out = self.sp(np.clip(k, self.kmin, self.kmax))
        for edge in (self.kmin, self.kmax):
            side = k < edge if edge == self.kmin else k > edge
            out = np.where(side, self.sp(edge) + self.sp.derivative()(edge) * (k - edge), out)
        return np.maximum(out, 1e-8)


# ── Density via Breeden-Litzenberger ─────────────────────────────────────────────────────────
@dataclass
class Distribution:
    """Risk-neutral distribution of S_T on a strike grid."""
    K: np.ndarray            # strike grid (USD)
    density: np.ndarray      # f(K)
    prob_above: np.ndarray   # P(S_T > K)
    forward: float
    T: float

    @property
    def cdf(self):
        return 1 - self.prob_above

    def mass(self) -> float:
        return float(np.trapezoid(self.density, self.K))

    def mean(self) -> float:
        return float(np.trapezoid(self.K * self.density, self.K))

    def percentile(self, q):
        c = np.maximum.accumulate(np.clip(self.cdf, 0, 1))      # monotone for inversion
        return np.interp(q, c, self.K)

    def p_above(self, strike):
        return np.interp(strike, self.K, self.prob_above)

    def pit(self, s_t):
        return float(np.interp(s_t, self.K, self.cdf))

    def log_score(self, s_t):
        """Log density of ln(S_T), comparable with phase 2's lognormal log score: f_x = f_S(S) * S."""
        f = np.interp(s_t, self.K, self.density)
        return float(np.log(max(f, 1e-300) * s_t))


def distribution_from_w(w_of_k, F: float, T: float, n: int = 4001, width: float = 8.0) -> Distribution:
    """Black-76 call prices on a uniform strike grid, then Breeden-Litzenberger.
    The grid spans +/- `width` ATM standard deviations in log-moneyness."""
    sd = float(np.sqrt(max(w_of_k(0.0), 1e-8)))
    K = np.linspace(F * np.exp(-width * sd), F * np.exp(width * sd), n)
    C = black76(F, K, w_of_k(np.log(K / F)))
    dC = np.gradient(C, K)
    f = np.gradient(dC, K)
    return Distribution(K=K, density=f, prob_above=np.clip(-dC, 0, 1), forward=F, T=T)


# ── Interpolation across expiries ────────────────────────────────────────────────────────────
@dataclass
class ExpirySmile:
    T: float          # years from the valuation time to expiry
    forward: float
    smile: object     # SVI or SplineSmile (anything with .w(k))
    k_min: float = -np.inf    # range of log-moneyness covered by quotes/trades
    k_max: float = np.inf


class Surface:
    """Total-variance interpolation across expiries (linear in T at fixed k; ln F linear in T)."""

    def __init__(self, expiries: list[ExpirySmile]):
        self.e = sorted(expiries, key=lambda x: x.T)

    def at(self, T: float):
        """Returns (w_of_k function, forward, extrapolated?)."""
        e = self.e
        if T <= e[0].T:
            s, r = e[0], T / e[0].T
            return (lambda k: s.smile.w(k) * r), s.forward, T < e[0].T
        if T >= e[-1].T:
            s, r = e[-1], T / e[-1].T
            return (lambda k: s.smile.w(k) * r), s.forward, T > e[-1].T
        i = np.searchsorted([x.T for x in e], T)
        lo, hi = e[i - 1], e[i]
        a = (T - lo.T) / (hi.T - lo.T)
        F = float(np.exp((1 - a) * np.log(lo.forward) + a * np.log(hi.forward)))
        return (lambda k: (1 - a) * lo.smile.w(k) + a * hi.smile.w(k)), F, False

    def distribution(self, T: float, **kw) -> tuple[Distribution, bool]:
        w_of_k, F, extrap = self.at(T)
        return distribution_from_w(w_of_k, F, T, **kw), extrap

    def calendar_violations(self, tol: float = 1e-6) -> list[tuple[float, float, float]]:
        """(T1, T2, worst shortfall) for consecutive expiries where w(k,T2) < w(k,T1).
        Checked only where BOTH expiries have data (outside that, both smiles are extrapolation)."""
        out = []
        for lo, hi in zip(self.e[:-1], self.e[1:]):
            a, b = max(lo.k_min, hi.k_min, -1.0), min(lo.k_max, hi.k_max, 1.0)
            if a >= b:
                continue
            k = np.linspace(a, b, 101)
            gap = hi.smile.w(k) - lo.smile.w(k)
            if gap.min() < -tol:
                out.append((lo.T, hi.T, float(gap.min())))
        return out
