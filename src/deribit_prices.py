"""
Step 2: BTC price history.

What we store (all in data/raw/, all timestamps UTC):

  btc_price_hourly.parquet      Coinbase BTC-USD hourly OHLCV candles, START_DATE -> now
  btc_price_daily.parquet       daily OHLCV built from the hourly candles (UTC calendar days)
  btc_index_6h_deribit.parquet  Deribit's own BTC index (btc_usd): average over each 6-hour
                                window, stamped at the window end (used as a cross-check)
  btc_price_0800.parquet        one row per day at 08:00 UTC:
                                  delivery_price = Deribit's official settlement price
                                  spot_close     = Coinbase close of the 07:00-08:00 candle

Why these sources (verified against the docs + live calls on 2026-09-30):
  * public/get_index_chart_data has no start/end parameters, only fixed ranges.
    range=1m gives hourly points, but only for the last month; range=all goes back to
    2016 but only one point every 6 hours. So Deribit can't give hourly index history from 2021.
  * Coinbase is one of the exchanges the Deribit index is built from. Its public candles
    endpoint gives hourly spot OHLCV back to 2015, 300 candles per request.
  * public/get_delivery_prices is exactly what options settle on: a 30-minute
    time-weighted average of the Deribit index from 07:30 to 08:00 UTC.
    Quirk: the docs say count can be up to 1000, but the server returns at most 100.

Run:  python -m src.deribit_prices
"""
import logging

import pandas as pd

import config
from src.api import deribit, get_json
from src.storage import save_parquet

log = logging.getLogger(__name__)

HOUR = pd.Timedelta(hours=1)


def fetch_delivery_prices(index_name: str = "btc_usd") -> pd.DataFrame:
    """All historical Deribit delivery (settlement) prices, newest pages first."""
    rows, offset, page = [], 0, 100      # server caps count at 100 regardless of what we ask for
    while True:
        result = deribit("get_delivery_prices", index_name=index_name, offset=offset, count=page)
        rows += result["data"]
        offset += page
        if offset >= result["records_total"]:
            break
    df = pd.DataFrame(rows)
    # Each date settles at 08:00 UTC, so we stamp it at that time.
    df["timestamp"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC") + pd.Timedelta(hours=config.EXPIRY_HOUR_UTC)
    df = df.set_index("timestamp").sort_index()[["delivery_price"]]
    log.info("Delivery prices: %d rows, %s -> %s", len(df), df.index[0], df.index[-1])
    return df


def fetch_deribit_index_6h(index_name: str = "btc_usd") -> pd.DataFrame:
    """Deribit index history at 6-hour spacing (the finest resolution available for the full history).

    Quirk (not in the docs; found by comparing with Coinbase): each value is the AVERAGE index
    over the preceding 6 hours, stamped at the END of the window. It is not a point-in-time price.
    Against that interpretation Coinbase matches it to a median of ~0.03%.
    """
    points = deribit("get_index_chart_data", index_name=index_name, range="all")
    df = pd.DataFrame(points, columns=["timestamp", "index_avg_6h"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    log.info("Deribit 6h index: %d rows, %s -> %s", len(df), df.index[0], df.index[-1])
    return df


def fetch_coinbase_hourly(start: pd.Timestamp, end: pd.Timestamp, product: str = "BTC-USD") -> pd.DataFrame:
    """Hourly candles from Coinbase Exchange, requested in 300-candle chunks (the API maximum).

    Quirks: rows come back newest-first, as [time, low, high, open, close, volume]
    (note low/high before open/close), and `time` is the candle's start in Unix seconds.
    """
    url = f"{config.COINBASE_BASE}/products/{product}/candles"
    chunks, chunk_start = [], start
    n_requests = int((end - start) / (300 * HOUR)) + 1
    log.info("Fetching Coinbase hourly candles %s -> %s (~%d requests)", start, end, n_requests)
    while chunk_start < end:
        chunk_end = min(chunk_start + 299 * HOUR, end)
        rows = get_json(url, params={
            "granularity": 3600,
            "start": chunk_start.isoformat(),
            "end": chunk_end.isoformat(),
        })
        chunks += rows
        chunk_start = chunk_end + HOUR
    df = pd.DataFrame(chunks, columns=["timestamp", "low", "high", "open", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = (df.drop_duplicates("timestamp").set_index("timestamp").sort_index()
            [["open", "high", "low", "close", "volume"]])
    log.info("Coinbase hourly: %d rows, %s -> %s", len(df), df.index[0], df.index[-1])
    return df


def hourly_to_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly candles into UTC calendar-day candles."""
    daily = hourly.resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    daily["n_hours"] = hourly["close"].resample("1D").count()   # < 24 means missing hours that day
    return daily.dropna(subset=["close"])


def build_0800(delivery: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    """One row per day at 08:00 UTC: official settlement price plus Coinbase spot for comparison."""
    # The candle starting 07:00 closes at 08:00, so its close is the spot price at 08:00.
    spot = hourly["close"].copy()
    spot.index = spot.index + HOUR
    out = delivery.join(spot.rename("spot_close"), how="left")
    out["diff_pct"] = (out["spot_close"] / out["delivery_price"] - 1) * 100
    return out


def main():
    config.setup_logging()
    start = pd.Timestamp(config.START_DATE, tz="UTC")
    end = pd.Timestamp(config.END_DATE, tz="UTC") if config.END_DATE else pd.Timestamp.now(tz="UTC").floor("h")

    hourly = fetch_coinbase_hourly(start, end)
    daily = hourly_to_daily(hourly)
    index_6h = fetch_deribit_index_6h().loc[start:end]
    delivery = fetch_delivery_prices().loc[start:end]
    at_0800 = build_0800(delivery, hourly)

    save_parquet(hourly, config.DATA_RAW / "btc_price_hourly.parquet")
    save_parquet(daily, config.DATA_RAW / "btc_price_daily.parquet")
    save_parquet(index_6h, config.DATA_RAW / "btc_index_6h_deribit.parquet")
    save_parquet(at_0800, config.DATA_RAW / "btc_price_0800.parquet")


if __name__ == "__main__":
    main()
