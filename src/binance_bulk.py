"""
Binance BTC/USDT 1-minute klines from the public bulk archive (data.binance.vision), since 2021.

URL format (github.com/binance/binance-public-data, verified 2026-10-02):
    https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-YYYY-MM.zip
    + the same name with .CHECKSUM (sha256) next to it.
CSV, no header: open_time, open, high, low, close, volume, close_time, quote_volume, trades,
taker_buy_base, taker_buy_quote, ignore. Spot timestamps are in MILLISECONDS before 2025 and
MICROSECONDS from 2025-01-01 onwards; the unit is detected per file from the magnitude.

Only complete months are downloaded (the archive publishes a month after it ends).
Writes data/raw/binance_1m/BTCUSDT-1m-YYYY-MM.parquet; resumable (existing months skipped),
every zip checked against its sha256 before use.
Run:  python -m src.binance_bulk
"""
import hashlib
import io
import logging
import zipfile

import pandas as pd

import config
from src.api import SESSION

log = logging.getLogger(__name__)
BASE = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m"
OUT = config.DATA_RAW / "binance_1m"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"]


def to_utc(ts: pd.Series) -> pd.Series:
    unit = "us" if ts.iloc[0] > 1e14 else "ms"           # 2021 in ms ~ 1.6e12; 2025 in us ~ 1.7e15
    return pd.to_datetime(ts, unit=unit, utc=True)


def fetch_month(month: pd.Period) -> pd.DataFrame:
    name = f"BTCUSDT-1m-{month.year}-{month.month:02d}.zip"
    z = SESSION.get(f"{BASE}/{name}", timeout=120)
    z.raise_for_status()
    c = SESSION.get(f"{BASE}/{name}.CHECKSUM", timeout=30)
    c.raise_for_status()
    expected = c.text.split()[0].strip().lower()
    got = hashlib.sha256(z.content).hexdigest()
    if got != expected:
        raise ValueError(f"{name}: sha256 mismatch ({got} != {expected})")
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        df = pd.read_csv(zf.open(zf.namelist()[0]), header=None, names=COLS)
    df["open_time"] = to_utc(df["open_time"])
    df = df[["open_time", "open", "high", "low", "close", "volume", "trades"]].set_index("open_time").sort_index()
    return df[~df.index.duplicated()]


def main():
    config.setup_logging()
    OUT.mkdir(parents=True, exist_ok=True)
    last_full = pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M") - 1
    for month in pd.period_range(config.START_DATE[:7], last_full, freq="M"):
        path = OUT / f"BTCUSDT-1m-{month}.parquet"
        if path.exists():
            continue
        try:
            df = fetch_month(month)
        except Exception:
            log.exception("Binance %s failed (not published yet?)", month)
            continue
        df.to_parquet(path, compression="zstd")
        expected = month.days_in_month * 1440
        log.info("Binance %s: %d minutes (%.2f%% of %d)", month, len(df), len(df) / expected * 100, expected)


if __name__ == "__main__":
    main()
