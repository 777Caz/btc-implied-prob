"""
Baseline volatility: trailing 30-day realised volatility, from the same Deribit 08:00 delivery
prices used as outcomes (so both models see the same index).

At origin date d we use the 30 daily log returns r_i = ln(P_i / P_{i-1}) between d-30 and d,
where P is the 08:00 UTC delivery price, and annualise:

    sigma_RV = sqrt( 365/30 * sum(r_i^2) )

We use the mean of r^2 (assuming zero mean return) rather than the sample variance. Over 30 days
the sample mean return is mostly noise, and subtracting it would understate vol after strong
trends. This is the standard convention for realised volatility.

Only information up to and including 08:00 on day d is used, so it's a genuine forecast.
Note: the delivery price is a 30-minute average, which smooths daily returns very slightly;
the effect on 30-day vol is negligible.
"""
import numpy as np
import pandas as pd

from src.models.dvol_lognormal import DAYS, YEAR


def trailing_realized_vol(prices: pd.Series, window: int = DAYS) -> pd.Series:
    """Annualised realised vol (decimal) at each date, from the previous `window` daily log returns."""
    r = np.log(prices).diff()
    return np.sqrt((r**2).rolling(window, min_periods=window).sum() * YEAR / window)
