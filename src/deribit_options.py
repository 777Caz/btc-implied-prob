"""
Step 4: historical BTC option trades from Deribit.

Output: data/raw/option_trades/YYYY-MM.parquet, one row per trade, indexed by UTC timestamp.

Endpoint: public/get_last_trades_by_currency_and_time with kind=option, served from
history.deribit.com. Behaviour verified live on 2026-09-30:
  * www.deribit.com only returns the last 24h of public trades. history.deribit.com serves the
    full archive with the same method and parameters (it is not in the current docs).
  * Max 1000 trades per call. With sorting=asc we page forward: the next call starts at the
    last timestamp we received. Several trades can share a millisecond, so that boundary can
    repeat trades, and we de-duplicate on trade_id.
  * Option `price` and `mark_price` are in BTC (Deribit BTC options are inverse: quoted and
    settled in BTC). USD value = price * index_price. We keep the original and add price_usd.
  * `iv` is in percent. The trade record has no underlying (futures) price, only index_price.

Run:  python -m src.deribit_options 2026-08-01 2026-09-01     (start inclusive, end exclusive)
Resumable: months already on disk are skipped, so re-running the same command after an
interruption (or a failed month) picks up where it stopped.
"""
import logging
import re
import sys
import time

import pandas as pd

import config
from src.api import deribit
from src.storage import save_parquet

log = logging.getLogger(__name__)

# e.g. BTC-27SEP26-80000-C  ->  expiry 27SEP26, strike 80000, call
INSTRUMENT_RE = re.compile(r"^BTC-(?P<expiry>\d{1,2}[A-Z]{3}\d{2})-(?P<strike>\d+)-(?P<type>[CP])$")

# Every monthly file gets exactly these columns. The API omits optional fields when they don't
# apply (and some didn't exist in 2021), so missing ones are filled with NaN for a stable schema.
KEEP = ["trade_id", "instrument_name", "price", "mark_price", "iv", "index_price",
        "amount", "contracts", "direction", "liquidation",
        "block_trade_id", "block_trade_leg_count", "block_rfq_id",   # block trades / RFQ fills
        "combo_id", "combo_trade_id"]                                 # legs of a combo (e.g. straddle)


def to_ms(ts: pd.Timestamp) -> int:
    return int(ts.timestamp() * 1000)


def fetch_trades(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """All BTC option trades with start <= timestamp < end."""
    trades, cursor, end_ms = [], to_ms(start), to_ms(end) - 1
    while True:
        result = deribit("get_last_trades_by_currency_and_time", base=config.DERIBIT_HISTORY_BASE,
                         currency="BTC", kind="option", start_timestamp=cursor,
                         end_timestamp=end_ms, count=1000, sorting="asc")
        batch = result["trades"]
        trades += batch
        if not result["has_more"] or not batch:
            break
        cursor = batch[-1]["timestamp"]     # may re-fetch trades at this exact ms; de-duped below
    df = pd.DataFrame(trades)
    if df.empty:
        return df
    df = df.drop_duplicates("trade_id")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index().reindex(columns=KEEP)
    # Fix dtypes explicitly: a column that is empty all month would otherwise be saved as float
    # in that file and as text in others, which breaks reading all months together.
    text_cols = ["trade_id", "instrument_name", "direction", "liquidation",
                 "block_trade_id", "combo_id", "combo_trade_id"]
    df[text_cols] = df[text_cols].astype("string")
    df = df.astype({c: "float64" for c in KEEP if c not in text_cols})
    return df


def parse_instruments(df: pd.DataFrame) -> pd.DataFrame:
    """Add expiry (08:00 UTC), strike, option_type, time to expiry, and USD prices."""
    parts = df["instrument_name"].str.extract(INSTRUMENT_RE)
    bad = parts["expiry"].isna()
    if bad.any():
        log.warning("%d trades with unparseable instrument names, e.g. %s — dropped",
                    bad.sum(), df.loc[bad, "instrument_name"].unique()[:5].tolist())
    df, parts = df[~bad].copy(), parts[~bad]
    df["expiry"] = (pd.to_datetime(parts["expiry"], format="%d%b%y").dt.tz_localize("UTC")
                    + pd.Timedelta(hours=config.EXPIRY_HOUR_UTC))
    df["strike"] = parts["strike"].astype(float)
    df["option_type"] = parts["type"].map({"C": "call", "P": "put"})
    df["days_to_expiry"] = (df["expiry"] - df.index).dt.total_seconds() / 86400
    df["price_usd"] = df["price"] * df["index_price"]
    df["mark_price_usd"] = df["mark_price"] * df["index_price"]
    df["is_block"] = df["block_trade_id"].notna()
    df["is_combo"] = df["combo_id"].notna()
    return df


def month_path(month_start: pd.Timestamp):
    return config.OPTION_TRADES_DIR / f"{month_start:%Y-%m}.parquet"


def fetch_month(month_start: pd.Timestamp) -> pd.DataFrame:
    """Fetch one calendar month day by day and save it. The file is only written once the
    whole month is fetched, so an existing file always means a complete month."""
    now = pd.Timestamp.now(tz="UTC")
    month_end = min(month_start + pd.offsets.MonthBegin(1), now)
    days = []
    for day in pd.date_range(month_start, month_end, freq="D", inclusive="left"):
        d = fetch_trades(day, min(day + pd.Timedelta(days=1), now))
        log.debug("  %s: %d trades", day.date(), len(d))
        days.append(d)
    df = parse_instruments(pd.concat(days))
    df = df[~df["trade_id"].duplicated()]      # guard against day-boundary repeats
    save_parquet(df, month_path(month_start))
    return df


def main():
    config.setup_logging()
    start = pd.Timestamp(sys.argv[1], tz="UTC") if len(sys.argv) > 1 else pd.Timestamp("2026-08-01", tz="UTC")
    end = pd.Timestamp(sys.argv[2], tz="UTC") if len(sys.argv) > 2 else start + pd.offsets.MonthBegin(1)
    current_month = pd.Timestamp.now(tz="UTC").normalize().replace(day=1)
    months = pd.date_range(start, end, freq="MS", inclusive="left")
    failed = []
    t0 = time.time()
    for i, month in enumerate(months, 1):
        tag = f"[{i}/{len(months)}] {month:%Y-%m}"
        # Resume: skip finished months. The current month is always re-fetched (it's still growing).
        if month_path(month).exists() and month < current_month:
            log.info("%s already on disk, skipping", tag)
            continue
        t = time.time()
        try:
            df = fetch_month(month)
        except Exception:
            log.exception("%s FAILED; re-run the same command later to retry it", tag)
            failed.append(f"{month:%Y-%m}")
            continue
        size_mb = month_path(month).stat().st_size / 1e6
        log.info("%s done: %d trades, %.1f MB, %.0fs  (elapsed %.0f min)",
                 tag, len(df), size_mb, time.time() - t, (time.time() - t0) / 60)
    log.info("Finished. Failed months: %s", failed or "none")


if __name__ == "__main__":
    main()
