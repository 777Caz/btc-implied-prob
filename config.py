"""
Central config: paths, date ranges, currencies, API base URLs.
Import this everywhere instead of hardcoding values.
"""
from pathlib import Path
import logging

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SNAPSHOTS_DIR  = DATA_RAW / "snapshots"
RESOLUTIONS_DIR = DATA_RAW / "resolutions"
LOGS_DIR       = ROOT / "logs"
FIGURES_DIR    = ROOT / "reports" / "figures"
PHASE2_DIR     = ROOT / "reports" / "phase2"
PHASE3_DIR     = ROOT / "reports" / "phase3"

# Ensure directories exist when config is imported
for _d in [DATA_RAW, DATA_PROCESSED, SNAPSHOTS_DIR, RESOLUTIONS_DIR, LOGS_DIR, FIGURES_DIR, PHASE2_DIR, PHASE3_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Date range ───────────────────────────────────────────────────────────────
START_DATE = "2021-01-01"   # pull history from here
END_DATE   = None           # None → today

# ── Currency / instrument ─────────────────────────────────────────────────────
BASE_CURRENCY = "BTC"

# Deribit option expiry time (UTC).  All standard expirations roll at 08:00 UTC.
EXPIRY_HOUR_UTC = 8

# ── API base URLs ─────────────────────────────────────────────────────────────
# Verified against official docs on 2026-09-30. All read endpoints below are public (no API key).
DERIBIT_BASE    = "https://www.deribit.com/api/v2"
# Same API, but serves the full public trade archive. www.deribit.com only keeps the last
# 24h of public trades. Not in the current docs; verified live on 2026-09-30 (data back to 2021).
DERIBIT_HISTORY_BASE = "https://history.deribit.com/api/v2"
OPTION_TRADES_DIR = DATA_RAW / "option_trades"   # one parquet file per month
# Polymarket splits reads across two APIs:
#   Gamma = market discovery/metadata (questions, end dates, token ids)
#   CLOB  = live prices and order books for those token ids
POLYMARKET_GAMMA_BASE = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB_BASE  = "https://clob.polymarket.com"
# docs.kalshi.com/getting_started/api_environments: "external-api" is the recommended host.
# (The old trading-api.kalshi.com host now returns 401.)
KALSHI_BASE     = "https://external-api.kalshi.com/trade-api/v2"
# Coinbase Exchange: hourly BTC-USD spot candles (Deribit's own hourly index history only covers ~1 month).
COINBASE_BASE   = "https://api.exchange.coinbase.com"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
LOG_FILE   = LOGS_DIR / "pipeline.log"


def setup_logging(name: str = "btc_proj") -> logging.Logger:
    """Call once per script to get a configured logger.

    Handlers go on the root logger so messages from every module
    (e.g. src.storage, which uses logging.getLogger(__name__)) are captured too.
    """
    root = logging.getLogger()
    if not root.handlers:        # avoid duplicate handlers on re-import
        _add_handlers(root)
    return logging.getLogger(name)


def _add_handlers(logger: logging.Logger) -> None:
    logger.setLevel(LOG_LEVEL)

    fmt = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    # console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # file
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")   # utf-8 so logs work on Windows too
    fh.setFormatter(fmt)
    logger.addHandler(fh)
