"""
Step 3: DVOL history (Deribit's BTC 30-day implied volatility index).

What we store:

  data/raw/dvol_hourly.parquet             DVOL hourly OHLC candles
  data/raw/dvol_daily.parquet              DVOL daily OHLC candles (UTC days)
  data/processed/btc_dvol_hourly.parquet   BTC price + DVOL on the same hourly UTC timestamps
  data/processed/btc_dvol_daily.parquet    BTC price + DVOL on the same daily UTC timestamps

Endpoint: public/get_volatility_index_data. Behaviour verified live on 2026-09-30:
  * DVOL history starts 2021-03-24 (the index launch); nothing earlier exists.
  * Values are in percentage points (e.g. 35.5 = 35.5% annualised), not fractions as the
    docs example suggests.
  * At most 1000 candles per call, and it returns the NEWEST 1000 in the window. The response
    has a `continuation` timestamp: pass it as the next `end_timestamp` to page backwards.
  * Candles are labelled with their START time, same as the Coinbase price candles, so the
    two join directly on timestamp.
  * Daily candles run 00:00-24:00 UTC: the daily close always equals the last hourly close.
    But on ~4% of days the daily OPEN differs from the first hourly open (median gap 0.8 vol
    points). We only use closes, so this doesn't matter, but don't trust the daily open.

Run:  python -m src.deribit_dvol     (after src.deribit_prices, for the merged files)
"""
import logging

import pandas as pd

import config
from src.api import deribit
from src.storage import load_parquet, save_parquet

log = logging.getLogger(__name__)


def to_ms(ts: pd.Timestamp) -> int:
    return int(ts.timestamp() * 1000)


def fetch_dvol(resolution: str, start: pd.Timestamp, end: pd.Timestamp, currency: str = "BTC") -> pd.DataFrame:
    """All DVOL candles between start and end, paging backwards with `continuation`."""
    rows, end_ms = [], to_ms(end)
    while True:
        result = deribit("get_volatility_index_data", currency=currency, resolution=resolution,
                         start_timestamp=to_ms(start), end_timestamp=end_ms)
        rows += result["data"]
        end_ms = result["continuation"]
        if not result["data"] or end_ms is None:
            break
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates("timestamp").set_index("timestamp").sort_index()
    log.info("DVOL %s: %d rows, %s -> %s", resolution, len(df), df.index[0], df.index[-1])
    return df


def merge_price_dvol(price: pd.DataFrame, dvol: pd.DataFrame) -> pd.DataFrame:
    """Close-to-close join on the shared UTC timestamps. Outer join, so gaps in either side stay visible as NaN."""
    return price[["close"]].rename(columns={"close": "btc_close"}).join(
        dvol[["close"]].rename(columns={"close": "dvol_close"}), how="outer")


def main():
    config.setup_logging()
    start = pd.Timestamp(config.START_DATE, tz="UTC")
    end = pd.Timestamp(config.END_DATE, tz="UTC") if config.END_DATE else pd.Timestamp.now(tz="UTC").floor("h")

    hourly = fetch_dvol("3600", start, end)
    daily = fetch_dvol("1D", start, end)
    save_parquet(hourly, config.DATA_RAW / "dvol_hourly.parquet")
    save_parquet(daily, config.DATA_RAW / "dvol_daily.parquet")

    for freq, dvol in [("hourly", hourly), ("daily", daily)]:
        price = load_parquet(config.DATA_RAW / f"btc_price_{freq}.parquet")
        merged = merge_price_dvol(price, dvol).loc[dvol.index[0]:]   # start where DVOL exists
        save_parquet(merged, config.DATA_PROCESSED / f"btc_dvol_{freq}.parquet")


if __name__ == "__main__":
    main()
