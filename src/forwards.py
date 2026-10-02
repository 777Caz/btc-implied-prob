"""
Phase 3, step 2: the forward price per expiry, backed out of put-call parity on historical trades.

Parity for Deribit's BTC-quoted (inverse) options
-------------------------------------------------
Deribit quotes option prices in BTC, computed as the USD Black-76 value divided by the forward F
(verified on a live snapshot: median error 0.006%; dividing by spot instead is off by ~1%).
At expiry a call pays (S_T-K)+/S_T BTC and a put (K-S_T)+/S_T BTC, so

    call - put  pays  (S_T - K)/S_T = 1 - K/S_T  BTC  in every state of the world.

Valued today in BTC (no BTC interest rate): 1 BTC at T is worth 1; K USD at T is worth K*D/S_0 BTC,
and F = S_0/D, so

    c - p = 1 - K/F        =>        F = K / (1 - (c - p))

The discount factor and spot price drop out, which makes this cleaner than the USD version
C - P = D(F - K).

Estimator
---------
For each expiry, pair every call trade with the put trade at the same strike that is closest in
time, keeping pairs less than MAX_GAP apart and near the money (|ln(K/index)| < MAX_LOGM, where
both options have real value). Each pair gives an F. Because BTC moves between pairs, we convert
each estimate to a BASIS RATIO b = F / index_price (the forward's premium over spot changes slowly),
take the median b across pairs (robust to bad prints), and set F = b * index at the reference time.
"""
import numpy as np
import pandas as pd

MAX_GAP = pd.Timedelta("5min")
MAX_LOGM = 0.15
MIN_PAIRS = 3


def parity_pairs(trades: pd.DataFrame) -> pd.DataFrame:
    """Call/put pairs at the same expiry and strike, traded within MAX_GAP. One row per call trade."""
    t = trades[np.abs(np.log(trades["strike"] / trades["index_price"])) < MAX_LOGM]
    t = t.reset_index().rename(columns={t.index.name or "index": "timestamp"})
    calls = t[t["option_type"] == "call"].sort_values("timestamp")
    puts = t[t["option_type"] == "put"].sort_values("timestamp")
    pairs = pd.merge_asof(calls, puts[["timestamp", "expiry", "strike", "price", "index_price"]],
                          on="timestamp", by=["expiry", "strike"], direction="nearest",
                          tolerance=MAX_GAP, suffixes=("_c", "_p")).dropna(subset=["price_p"])
    diff = pairs["price_c"] - pairs["price_p"]
    pairs["forward"] = pairs["strike"] / (1 - diff)
    index_mid = (pairs["index_price_c"] + pairs["index_price_p"]) / 2
    pairs["basis"] = pairs["forward"] / index_mid
    # drop impossible values (1 - (c-p) <= 0) and gross outliers (> 10% from spot)
    return pairs[(1 - diff > 0) & pairs["basis"].between(0.9, 1.1)]


def forward_by_expiry(trades: pd.DataFrame, index_at_ref: float) -> pd.DataFrame:
    """Median-basis forward per expiry. Columns: basis, forward, n_pairs."""
    pairs = parity_pairs(trades)
    g = pairs.groupby("expiry")["basis"].agg(basis="median", n_pairs="size", basis_iqr=lambda b: b.quantile(.75) - b.quantile(.25))
    g = g[g["n_pairs"] >= MIN_PAIRS]
    g["forward"] = g["basis"] * index_at_ref
    return g
