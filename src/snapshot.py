"""
Step 5: live snapshot of the Deribit BTC options chain + Polymarket/Kalshi BTC price markets.

Each run writes two zstd-compressed parquet files to data/raw/snapshots/YYYY-MM-DD/:
  deribit_HHMMSS.parquet      every BTC option: bid/ask/mark, mark IV, OI, forward, index
  predmarkets_HHMMSS.parquet  Polymarket + Kalshi "BTC above K" and "BTC in range" markets

Every row carries `snapshot_time` (shared by all sources in one run, so rows can be joined)
and `fetched_at` (the actual moment that source was queried; the three calls span ~2 seconds).

Why these endpoints (verified against the docs and live on 2026-09-30):

Deribit  public/get_book_summary_by_currency (kind=option): the whole chain (~950 options) in one
         call, so all quotes are from one moment. It includes `underlying_price`, the forward for
         each expiry, which the historical trade data lacks. It has no bid/ask IV (only mark_iv).
         Those need a per-instrument `ticker` call (~950 calls, ~2 min, no longer one moment),
         so we skip them and can compute them later from bid/ask prices + forward.
         Prices are in BTC (inverse options).

Polymarket  Gamma /events?tag_slug=bitcoin finds the markets. The CLOB POST /books gives live
         order books for all their YES tokens in one call.
         Quirks: the strike is in `groupItemTitle` ("84,000", "74,000-76,000", "<74,000"), NOT
         in `groupItemThreshold` (that's a display-order number). `clobTokenIds` is a JSON string.
         Book levels are sorted worst-to-best, so best bid = max(bids), best ask = min(asks).
         Resolves on the Binance BTC/USDT 1-minute close at 12:00 ET.
         resolution_time comes from the RULES (time in ET from the description, or "5PM ET" in
         hourly titles, on the date in the title), not from Gamma's endDate: endDate is not the
         resolution time for older events (e.g. 12:00 UTC for Jan 2025 events that resolve at
         noon ET = 17:00 UTC). See polymarket_resolution_time().
         last_price is NOT stored for Polymarket (NaN since 2026-10-02): the book's
         last_trade_price is the last fill on the market in EITHER outcome token, so after a NO
         trade it is a NO price (~ 1 - YES). Snapshots before 2026-10-02 contain that mixed value;
         don't use them.
         There are also newer hourly events ("..., 12PM ET?") which often have zero volume and
         leftover quotes. They're kept; filter on volume/spread when analysing.

Kalshi   /markets?series_ticker=KXBTCD (above/below) and KXBTC (ranges), public, no key.
         Prices come as dollar strings ("0.0100"); an empty side shows as 0.00/1.00 with size 0,
         which we store as NaN. Strikes look like 84099.99 ("above 84,099.99" = $84,100 or
         more). The KXBTC range series also has open-ended tail markets ("above"/"below").
         Settles on the 60-second average of CF
         Benchmarks' BRTI before the close time (12:00 or 17:00 ET).

Note the three settle on DIFFERENT reference prices and times: Deribit = its own index, 30-min
TWAP to 08:00 UTC; Polymarket = Binance BTC/USDT at 12:00 ET; Kalshi = BRTI at 12:00/17:00 ET.

Run:  python -m src.snapshot
"""
import json
import logging
import re

import pandas as pd

import config
from src.api import SESSION, deribit, get_json
from src.checks import SNAPSHOT_GAP_WARN, snapshot_times
from src.deribit_options import INSTRUMENT_RE
from src.storage import save_parquet

log = logging.getLogger(__name__)

POLYMARKET_TITLES = {"Bitcoin above": "above", "Bitcoin price on": "range"}
KALSHI_SERIES = ["KXBTCD", "KXBTC"]
KALSHI_KIND = {"greater": "above", "less": "below", "between": "range"}

PRED_COLUMNS = ["venue", "event", "market_id", "question", "kind", "strike", "range_low", "range_high",
                "resolution_time", "yes_bid", "yes_ask", "yes_bid_size", "yes_ask_size",
                "last_price", "volume", "open_interest", "settlement_source", "fetched_at"]


def now_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


# ── Deribit ──────────────────────────────────────────────────────────────────────────────────
def deribit_chain() -> pd.DataFrame:
    fetched_at = now_utc()
    rows = deribit("get_book_summary_by_currency", currency="BTC", kind="option")
    index_price = deribit("get_index_price", index_name="btc_usd")["index_price"]
    df = pd.DataFrame(rows)
    parts = df["instrument_name"].str.extract(INSTRUMENT_RE)
    df["expiry"] = (pd.to_datetime(parts["expiry"], format="%d%b%y").dt.tz_localize("UTC")
                    + pd.Timedelta(hours=config.EXPIRY_HOUR_UTC))
    df["strike"] = parts["strike"].astype(float)
    df["option_type"] = parts["type"].map({"C": "call", "P": "put"})
    df["index_price"] = index_price
    df["fetched_at"] = fetched_at
    df = df.rename(columns={"bid_price": "bid", "ask_price": "ask", "mid_price": "mid",
                            "underlying_price": "forward_price", "volume": "volume_24h"})
    keep = ["instrument_name", "expiry", "strike", "option_type", "bid", "ask", "mid", "mark_price",
            "mark_iv", "open_interest", "volume_24h", "last", "forward_price", "underlying_index",
            "interest_rate", "index_price", "fetched_at"]
    log.info("Deribit: %d options, index %.2f", len(df), index_price)
    return df[keep].sort_values(["expiry", "strike", "option_type"]).reset_index(drop=True)


# ── Polymarket ───────────────────────────────────────────────────────────────────────────────
def parse_polymarket_strike(label: str, kind: str) -> tuple[float | None, float | None, float | None]:
    """'84,000' -> strike; '74,000-76,000' -> range; '<74,000' / '>92,000' -> open-ended range."""
    nums = [float(x.replace(",", "")) for x in re.findall(r"[\d,]+(?:\.\d+)?", label)]
    if kind == "above":
        return nums[0], None, None
    if label.startswith("<"):
        return None, None, nums[0]
    if label.startswith(">"):
        return None, nums[0], None
    return None, nums[0], nums[1]


MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                       "September", "October", "November", "December"], start=1)}


def polymarket_resolution_time(title: str, description: str, end_date) -> pd.Timestamp:
    """Resolution time (UTC) from the market rules: date from the title ("... on October 3?",
    "... on October 2, 5PM ET?"), time from the title ("5PM ET") or the description
    ("12:00 in the ET timezone"), in New York time. The year is the one that puts the date closest
    to Gamma's endDate (endDate is near the right day even when its time is wrong).
    Falls back to endDate if the text can't be parsed."""
    end = pd.Timestamp(end_date)
    d = re.search(r"on (" + "|".join(MONTHS) + r") (\d{1,2})\b", title)
    t_title = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM) ET", title)
    t_desc = re.search(r"(\d{1,2}):(\d{2}) in the ET timezone", description or "")
    if not d or not (t_title or t_desc):
        log.warning("Polymarket: can't parse resolution time from %r; using endDate %s", title, end)
        return end
    if t_title:
        hour = int(t_title.group(1)) % 12 + (12 if t_title.group(3) == "PM" else 0)
        minute = int(t_title.group(2) or 0)
    else:
        hour, minute = int(t_desc.group(1)), int(t_desc.group(2))
    month, day = MONTHS[d.group(1)], int(d.group(2))
    cands = [pd.Timestamp(year=y, month=month, day=day, hour=hour, minute=minute).tz_localize("America/New_York")
             for y in (end.year - 1, end.year, end.year + 1)]
    return min(cands, key=lambda c: abs(c - end)).tz_convert("UTC")


def best_levels(book: dict) -> dict:
    bids = [(float(b["price"]), float(b["size"])) for b in book.get("bids", [])]
    asks = [(float(a["price"]), float(a["size"])) for a in book.get("asks", [])]
    bid = max(bids) if bids else (None, None)          # levels are not best-first, so take max/min
    ask = min(asks) if asks else (None, None)
    # last_trade_price is deliberately dropped: it can be a NO-token price (see module docstring)
    return {"yes_bid": bid[0], "yes_bid_size": bid[1], "yes_ask": ask[0], "yes_ask_size": ask[1]}


def polymarket_btc() -> pd.DataFrame:
    events, offset = [], 0
    while True:
        page = get_json(f"{config.POLYMARKET_GAMMA_BASE}/events", params={
            "tag_slug": "bitcoin", "active": "true", "closed": "false", "limit": 100, "offset": offset})
        events += page
        offset += 100
        if len(page) < 100:
            break

    rows = []
    for e in events:
        kind = next((k for prefix, k in POLYMARKET_TITLES.items() if e["title"].startswith(prefix)), None)
        if kind is None:
            continue
        for m in e["markets"]:
            if m.get("closed") or not m.get("clobTokenIds"):
                continue
            strike, lo, hi = parse_polymarket_strike(m["groupItemTitle"], kind)
            rows.append({
                "venue": "polymarket", "event": e["title"], "market_id": m["id"],
                "question": m["question"], "kind": kind, "strike": strike, "range_low": lo, "range_high": hi,
                "resolution_time": polymarket_resolution_time(e["title"], m.get("description", ""), m["endDate"]),
                "yes_token": json.loads(m["clobTokenIds"])[0],
                "volume": float(m.get("volumeNum") or 0), "open_interest": None,
                "settlement_source": "Binance BTC/USDT 1m close, 12:00 ET",
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    fetched_at = now_utc()
    resp = SESSION.post(f"{config.POLYMARKET_CLOB_BASE}/books",
                        json=[{"token_id": t} for t in df["yes_token"]], timeout=30)
    resp.raise_for_status()
    books = {b["asset_id"]: best_levels(b) for b in resp.json()}
    df = df.join(pd.DataFrame([books.get(t, {}) for t in df["yes_token"]], index=df.index))
    df["fetched_at"] = fetched_at
    log.info("Polymarket: %d markets in %d events", len(df), df["event"].nunique())
    return df.reindex(columns=PRED_COLUMNS)


# ── Kalshi ───────────────────────────────────────────────────────────────────────────────────
def kalshi_btc() -> pd.DataFrame:
    fetched_at = now_utc()
    markets = []
    for series in KALSHI_SERIES:
        cursor = None
        while True:
            params = {"series_ticker": series, "status": "open", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            page = get_json(f"{config.KALSHI_BASE}/markets", params=params)
            markets += page["markets"]
            cursor = page.get("cursor")
            if not cursor:
                break

    num = lambda v: float(v) if v not in (None, "") else None
    # Kalshi reports an empty side as bid 0.00 / ask 1.00 with size 0. Treat those as "no quote",
    # otherwise they look like real prices (e.g. a fake 0.995 mid).
    quote = lambda price, size: num(price) if (num(size) or 0) > 0 else None
    rows = []
    for m in markets:
        kind = KALSHI_KIND.get(m["strike_type"], m["strike_type"])
        rows.append({
            "venue": "kalshi", "event": m["event_ticker"], "market_id": m["ticker"],
            "question": f'{m["title"]} {m["yes_sub_title"]}', "kind": kind,
            "strike": m.get("floor_strike") if kind == "above" else None,
            "range_low": m.get("floor_strike") if kind == "range" else None,
            "range_high": m.get("cap_strike") if kind in ("range", "below") else None,
            "resolution_time": pd.Timestamp(m["close_time"]),
            "yes_bid": quote(m.get("yes_bid_dollars"), m.get("yes_bid_size_fp")),
            "yes_ask": quote(m.get("yes_ask_dollars"), m.get("yes_ask_size_fp")),
            "yes_bid_size": num(m.get("yes_bid_size_fp")), "yes_ask_size": num(m.get("yes_ask_size_fp")),
            "last_price": num(m.get("last_price_dollars")), "volume": num(m.get("volume_fp")),
            "open_interest": num(m.get("open_interest_fp")),
            "settlement_source": "CF Benchmarks BRTI, 60s average before close",
            "fetched_at": fetched_at,
        })
    df = pd.DataFrame(rows, columns=PRED_COLUMNS)
    log.info("Kalshi: %d markets in %d events", len(df), df["event"].nunique())
    return df


# ── Run ──────────────────────────────────────────────────────────────────────────────────────
def main():
    config.setup_logging()
    snapshot_time = now_utc().floor("s")
    folder = config.SNAPSHOTS_DIR / f"{snapshot_time:%Y-%m-%d}"
    stamp = f"{snapshot_time:%H%M%S}"
    previous = snapshot_times()
    if len(previous) and snapshot_time - previous[-1] >= SNAPSHOT_GAP_WARN:
        log.warning("GAP: no snapshot for %s (previous %s). Missed snapshots can't be recovered.",
                    snapshot_time - previous[-1], previous[-1])

    # Each source is independent: one failing (API down, format change) doesn't lose the others.
    results = {}
    for name, fetch in [("deribit", deribit_chain), ("polymarket", polymarket_btc), ("kalshi", kalshi_btc)]:
        try:
            results[name] = fetch()
        except Exception:
            log.exception("Snapshot source %s failed", name)

    if "deribit" in results:
        d = results["deribit"].assign(snapshot_time=snapshot_time)
        save_parquet(d, folder / f"deribit_{stamp}.parquet", compression="zstd")
    preds = [results[k] for k in ("polymarket", "kalshi") if k in results and not results[k].empty]
    if preds:
        p = pd.concat(preds, ignore_index=True).assign(snapshot_time=snapshot_time)
        p = p.astype({c: "float64" for c in ["strike", "range_low", "range_high", "yes_bid", "yes_ask",
                                             "yes_bid_size", "yes_ask_size", "last_price", "volume",
                                             "open_interest"]})
        save_parquet(p, folder / f"predmarkets_{stamp}.parquet", compression="zstd")
    log.info("Snapshot %s done: %s", snapshot_time, ", ".join(results) or "nothing saved")


if __name__ == "__main__":
    main()
