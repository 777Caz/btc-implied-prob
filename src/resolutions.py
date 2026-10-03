"""
Daily resolutions job: what actually happened, for everything our snapshots quoted.

Writes to data/raw/resolutions/:

  deribit_delivery.parquet   one row per Deribit expiry: the official delivery (settlement) price
  predmarkets.parquet        one row per Polymarket/Kalshi market seen in any snapshot: status,
                             outcome (1 = YES won, 0 = NO won, NaN = not resolved yet),
                             and Kalshi's settlement value
  binance_btcusdt_1m.parquet Binance BTC/USDT 1-minute candle at 12:00 New York every day, plus at
                             every other Polymarket resolution time seen in snapshots (e.g. 1PM ET)

JOIN KEYS back to snapshot rows:
  Deribit      snapshot `expiry` (UTC, 08:00)          == deribit_delivery index `expiry`
  Pred. mkts   snapshot (`venue`, `market_id`)         == predmarkets (`venue`, `market_id`)
               (market_id = Polymarket Gamma market id, or Kalshi ticker; both are stable ids)
  Binance      Polymarket snapshot `resolution_time`   == binance index `candle_open` (UTC)

Endpoints (verified against docs + live on 2026-09-30):
  Deribit   public/get_delivery_prices. Its values equal the index_price on every per-instrument
            record from public/get_last_settlements_by_currency(type=delivery). Page size capped at 100.
  Kalshi    GET /markets?tickers=a,b,c. A settled market has status "finalized", result "yes"/"no",
            and expiration_value = the BRTI settlement value. Markets settled before
            GET /historical/cutoff are only served by GET /historical/markets/{ticker}.
  Polymarket  Gamma GET /markets?id=..; closed markets are only returned with closed=true, so we ask
            both ways. Resolution goes through UMA: umaResolutionStatus "proposed" -> "resolved",
            which can take hours. Only "resolved" counts as final. The API does not give the
            settlement price, hence the Binance fetch.
  Binance   data-api.binance.vision/api/v3/klines (the documented market-data-only host). Candles are
            identified by OPEN time. Polymarket's "12:00 ET candle close" = close of the candle
            opening at 12:00:00 ET (i.e. the price at 12:00:59).

Idempotent: re-running only fetches what is missing or not yet final. Safe to run any time.
Run:  python -m src.resolutions
"""
import glob
import json
import logging

import pandas as pd

import config
from src.api import deribit, get_json
from src.checks import SNAPSHOT_GAP_WARN, snapshot_gaps, snapshot_times
from src.storage import save_parquet

log = logging.getLogger(__name__)

OUT = config.RESOLUTIONS_DIR
BINANCE = "https://data-api.binance.vision/api/v3/klines"
NY = "America/New_York"


def upsert(new: pd.DataFrame, path, key: list[str] | None = None) -> pd.DataFrame:
    """Merge new rows into an existing parquet file, keeping the newest version of each key."""
    if path.exists():
        old = pd.read_parquet(path)
        both = pd.concat([old, new])
        if key:
            both = both.drop_duplicates(key, keep="last")
        else:
            both = both[~both.index.duplicated(keep="last")]
        new = both.sort_index()
    save_parquet(new, path)
    return new


# ── Deribit ──────────────────────────────────────────────────────────────────────────────────
def deribit_deliveries() -> pd.DataFrame:
    path = OUT / "deribit_delivery.parquet"
    have = set(pd.read_parquet(path).index) if path.exists() else set()
    rows, offset = [], 0
    while True:                                   # newest first; stop once we reach known dates
        page = deribit("get_delivery_prices", index_name="btc_usd", offset=offset, count=100)
        rows += page["data"]
        offset += 100
        oldest = pd.Timestamp(page["data"][-1]["date"], tz="UTC") + pd.Timedelta(hours=config.EXPIRY_HOUR_UTC) if page["data"] else None
        if offset >= page["records_total"] or oldest is None or oldest in have \
                or oldest < pd.Timestamp(config.START_DATE, tz="UTC"):
            break
    df = pd.DataFrame(rows)
    df["expiry"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC") + pd.Timedelta(hours=config.EXPIRY_HOUR_UTC)
    df = df.set_index("expiry").sort_index()[["delivery_price"]].loc[config.START_DATE:]   # API is newest-first
    out = upsert(df, path)
    log.info("Deribit deliveries: %d expiries stored (latest %s)", len(out), out.index.max())
    return out


# ── Prediction markets seen in snapshots ────────────────────────────────────────────────────
def snapshot_markets() -> pd.DataFrame:
    files = glob.glob(str(config.SNAPSHOTS_DIR / "*" / "predmarkets_*.parquet"))
    cols = ["venue", "market_id", "event", "question", "kind", "strike", "range_low", "range_high", "resolution_time"]
    seen = pd.concat(pd.read_parquet(f, columns=cols) for f in files)
    return seen.drop_duplicates(["venue", "market_id"], keep="last")


def kalshi_lookup(tickers: list[str]) -> list[dict]:
    markets = []
    for i in range(0, len(tickers), 100):          # comma-separated list; keep URLs short
        chunk = tickers[i:i + 100]
        markets += get_json(f"{config.KALSHI_BASE}/markets",
                            params={"tickers": ",".join(chunk), "limit": 1000})["markets"]
    missing = set(tickers) - {m["ticker"] for m in markets}
    for t in missing:                              # settled before the archive cutoff
        try:
            markets.append(get_json(f"{config.KALSHI_BASE}/historical/markets/{t}")["market"])
        except Exception:
            log.warning("Kalshi market %s not found in live or historical API", t)
    return [{
        "venue": "kalshi", "market_id": m["ticker"], "status": m.get("status"),
        "outcome": {"yes": 1.0, "no": 0.0}.get(m.get("result")),
        "settlement_value": float(m["expiration_value"]) if m.get("expiration_value") else None,
        "settled_at": pd.Timestamp(m["settlement_ts"]) if m.get("settlement_ts") else pd.NaT,
    } for m in markets]


def polymarket_lookup(ids: list[str]) -> list[dict]:
    markets = []
    for i in range(0, len(ids), 50):
        chunk = [("id", x) for x in ids[i:i + 50]]
        for closed in ("false", "true"):           # Gamma hides closed markets unless closed=true
            markets += get_json(f"{config.POLYMARKET_GAMMA_BASE}/markets", params=chunk + [("closed", closed)])
    rows = []
    for m in {m["id"]: m for m in markets}.values():
        status = m.get("umaResolutionStatus") or ("closed" if m.get("closed") else "open")
        prices = json.loads(m.get("outcomePrices") or "[]")
        final = status == "resolved" and m.get("closed") and prices
        rows.append({
            "venue": "polymarket", "market_id": m["id"], "status": status,
            "outcome": float(round(float(prices[0]))) if final else None,   # outcomes are [Yes, No]
            "settlement_value": None,                                       # not published; see Binance
            "settled_at": pd.Timestamp(m["closedTime"]) if m.get("closedTime") else pd.NaT,
        })
    return rows


def predmarket_resolutions() -> pd.DataFrame:
    path = OUT / "predmarkets.parquet"
    seen = snapshot_markets()
    due = seen[seen["resolution_time"] <= pd.Timestamp.now(tz="UTC")]
    if path.exists():                              # skip markets we already have a final answer for
        done = pd.read_parquet(path)
        done = done[done["outcome"].notna()]
        due = due[~due.set_index(["venue", "market_id"]).index.isin(done.set_index(["venue", "market_id"]).index)]
    log.info("Prediction markets: %d seen in snapshots, %d past resolution time and not final",
             len(seen), len(due))
    if due.empty:
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()

    rows = kalshi_lookup(due.loc[due["venue"] == "kalshi", "market_id"].tolist()) \
        + polymarket_lookup(due.loc[due["venue"] == "polymarket", "market_id"].tolist())
    res = pd.DataFrame(rows).merge(seen, on=["venue", "market_id"], how="left")
    res["checked_at"] = pd.Timestamp.now(tz="UTC")
    res = res.astype({"outcome": "float64", "settlement_value": "float64"})
    out = upsert(res.set_index("resolution_time"), path, key=["venue", "market_id"])
    log.info("Prediction markets: %d rows stored, %d resolved", len(out), out["outcome"].notna().sum())
    return out


# ── Binance BTC/USDT 1-minute candles ────────────────────────────────────────────────────────
def binance_candles() -> pd.DataFrame:
    path = OUT / "binance_btcusdt_1m.parquet"
    now = pd.Timestamp.now(tz="UTC")
    # every day's 12:00 New York (DST-aware), converted to UTC
    days = pd.date_range(config.START_DATE, now.tz_convert(NY).normalize().tz_localize(None), freq="D")
    wanted = pd.DatetimeIndex([pd.Timestamp(f"{d:%Y-%m-%d} 12:00", tz=NY).tz_convert("UTC") for d in days])
    noon = set(wanted)
    # plus every Polymarket resolution time in the snapshots (hourly events: 1PM ET etc.)
    seen = snapshot_markets()
    extra = pd.DatetimeIndex(seen.loc[seen["venue"] == "polymarket", "resolution_time"].unique())
    wanted = wanted.union(extra)
    wanted = wanted[wanted + pd.Timedelta(minutes=1) <= now]            # candle must be complete
    have = pd.read_parquet(path).index if path.exists() else pd.DatetimeIndex([], tz="UTC")
    todo = wanted.difference(have)
    log.info("Binance: %d candles wanted, %d to fetch", len(wanted), len(todo))
    rows = []
    for t in todo:
        k = get_json(BINANCE, params={"symbol": "BTCUSDT", "interval": "1m",
                                      "startTime": int(t.timestamp() * 1000), "limit": 1}, pause=0.05)
        if k and k[0][0] == int(t.timestamp() * 1000):
            rows.append({"candle_open": t, "open": float(k[0][1]), "close": float(k[0][4]),
                         "is_noon_et": t in noon})
        else:
            log.warning("Binance: no candle at %s", t)
    if not rows:
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()
    out = upsert(pd.DataFrame(rows).set_index("candle_open"), path)
    log.info("Binance: %d candles stored", len(out))
    return out


def main():
    config.setup_logging()
    from src import paper_trade                                   # heavy imports; only needed here
    for name, job in [("deribit", deribit_deliveries), ("predmarkets", predmarket_resolutions),
                      ("binance", binance_candles), ("paper trade settle", paper_trade.settle)]:
        try:
            job()
        except Exception:
            log.exception("Resolutions job %s failed", name)
    check_snapshots()


def check_snapshots():
    """Daily health check of the live snapshots: the snapshot task can't report that it has stopped."""
    times = snapshot_times()
    now = pd.Timestamp.now(tz="UTC")
    if not len(times) or now - times[-1] >= SNAPSHOT_GAP_WARN:
        log.warning("STALE: no snapshot since %s; is the snapshot task running?", times[-1] if len(times) else "ever")
    gaps = snapshot_gaps(times)
    recent = gaps[gaps["next_after"] >= now - pd.Timedelta("1D")]
    for _, g in recent.iterrows():
        log.warning("GAP in last 24h: %s -> %s (%s)", g["last_before"], g["next_after"], g["length"])
    day = times[times >= now - pd.Timedelta("1D")]
    log.info("Snapshots in last 24h: %d of 144 expected", len(day))


if __name__ == "__main__":
    main()
