"""
Roadmap D: historical prices for settled BTC prediction markets (no hourly events).

Kalshi   KXBTCD (above/below) and KXBTC (ranges), events settling at 12:00 or 17:00 New York.
         1-minute candlesticks per market over its whole life (open_time -> close_time).
         Candles carry YES bid and ask OHLC, trade OHLC, volume and open interest, but a candle
         only exists for minutes where something changed. So two outputs:
           raw     data/raw/pm_history/kalshi/candles_1m/<series>/<event>.parquet  (as served)
           filled  data/processed/pm_history/kalshi_1m/<series>/<event>.parquet   (minute grid,
                   bid/ask/open interest forward-filled, volume 0 where no candle,
                   observed = a real candle that minute). As in the snapshots, an empty side
                   (bid 0.00 / ask 1.00) is stored as NaN in the filled file.
         Markets that settled before GET /historical/cutoff are only served by /historical/...
         Live and historical candles name fields differently (close_dollars / close, volume_fp /
         volume, open_interest_fp / open_interest); both are dollar or count strings.

Polymarket  "Bitcoin above ___ on <date>?" (Gamma series 45) and "Bitcoin price on <date>?"
         (series 10041, ranges), closed events. CLOB /prices-history at fidelity 1 = the MID
         (verified against our snapshot books; the docs don't say), per YES token, from market
         start to 1h after resolution:
           data/raw/pm_history/polymarket/mids_1m/<event slug>.parquet
         resolution_time comes from the market rules, not endDate (see
         snapshot.polymarket_resolution_time).

Catalogs (markets with strikes, resolution times, outcomes) are rebuilt on every run:
  data/raw/pm_history/{kalshi,polymarket}/markets.parquet

Resumable: an event whose output file exists is skipped; files are written atomically.
Run:  python -m src.pm_backfill kalshi | polymarket
"""
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

import config
import requests

from src.api import SESSION, get_json
from src.snapshot import parse_polymarket_strike, polymarket_resolution_time

log = logging.getLogger(__name__)

RAW = config.DATA_RAW / "pm_history"
PROC = config.DATA_PROCESSED / "pm_history"
K = config.KALSHI_BASE
G, C = config.POLYMARKET_GAMMA_BASE, config.POLYMARKET_CLOB_BASE
NY = "America/New_York"

KALSHI_SERIES = ["KXBTCD", "KXBTC"]
KALSHI_HOURS_NY = (12, 17)                     # daily-type events only; other hourly events are out of scope
KALSHI_RATE = 9.0                              # requests/s across all threads; Kalshi answers 429 above ~15/s
KALSHI_THREADS = 6                             # requests in flight (archived calls take ~1 s)
KALSHI_CHUNK = pd.Timedelta(days=3)            # candle request window (well under any per-call cap)
POLY_SERIES = {"45": "Bitcoin above", "10041": "Bitcoin price on"}
POLY_PAUSE = 0.1


class RateLimiter:
    """Shared across threads. Adaptive (AIMD): on HTTP 429 the gap between calls grows 1.25x (down
    to MIN_RATE); after each success it shrinks 2% (up to `rate`). Kalshi's /historical endpoints
    throttle harder than the live ones, so the sustainable rate is found at run time."""
    MIN_RATE = 1.0

    def __init__(self, rate: float):
        self.min_gap, self.gap = 1.0 / rate, 1.0 / rate
        self.next, self.lock = time.monotonic(), threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        time.sleep(max(0.0, t - now))

    def throttled(self):
        with self.lock:
            self.gap = min(self.gap * 1.25, 1.0 / self.MIN_RATE)

    def ok(self):
        with self.lock:
            self.gap = max(self.gap * 0.98, self.min_gap)

    @property
    def rate(self):
        return 1.0 / self.gap


KALSHI_LIMIT = RateLimiter(KALSHI_RATE)


def kget(url, params, retries: int = 8):
    for attempt in range(retries + 1):
        KALSHI_LIMIT.wait()
        try:
            r = SESSION.get(url, params=params, timeout=30)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
            time.sleep(2 ** min(attempt, 5))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            KALSHI_LIMIT.throttled()
            if attempt == retries:
                r.raise_for_status()
            time.sleep(min(2 ** attempt, 30))
            continue
        r.raise_for_status()
        KALSHI_LIMIT.ok()
        return r.json()


def write_atomic(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, compression="zstd")
    os.replace(tmp, path)


class Progress:
    def __init__(self, name: str, total: int):
        self.name, self.total, self.done, self.skipped, self.t0 = name, total, 0, 0, time.time()

    def tick(self, skipped=False, every=25):
        self.done += 1
        self.skipped += skipped
        if self.done % every == 0 or self.done == self.total:
            worked = self.done - self.skipped
            rate = worked / max(time.time() - self.t0, 1e-9)
            eta = (self.total - self.done) / rate / 3600 if rate > 0 else float("nan")
            log.info("%s: %d/%d events (%d already done), ETA %.1f h%s", self.name, self.done, self.total,
                     self.skipped, eta, f", Kalshi rate {KALSHI_LIMIT.rate:.1f}/s" if self.name == "Kalshi" else "")


# ── Kalshi ───────────────────────────────────────────────────────────────────────────────────
def kalshi_events() -> pd.DataFrame:
    rows = []
    for series in KALSHI_SERIES:
        cur = None
        while True:
            p = {"series_ticker": series, "status": "settled", "limit": 200}
            if cur:
                p["cursor"] = cur
            r = kget(f"{K}/events", p)
            rows += [{"series": series, "event": e["event_ticker"], "strike_date": e.get("strike_date")}
                     for e in r.get("events", [])]
            cur = r.get("cursor")
            if not cur or not r.get("events"):
                break
    ev = pd.DataFrame(rows)
    ev["settle"] = pd.to_datetime(ev["strike_date"], utc=True, errors="coerce")
    n_nodate = int(ev["settle"].isna().sum())
    ev = ev.dropna(subset=["settle"])
    ev = ev[ev["settle"].dt.tz_convert(NY).dt.hour.isin(KALSHI_HOURS_NY)]
    log.info("Kalshi: %d settled 12:00/17:00 NY events (%d events without a strike_date dropped)", len(ev), n_nodate)
    return ev.sort_values("settle").reset_index(drop=True)


def kalshi_markets(event: str, archived: bool) -> list[dict]:
    url = f"{K}/historical/markets" if archived else f"{K}/markets"
    out, cur = [], None
    while True:
        p = {"event_ticker": event, "limit": 1000}
        if cur:
            p["cursor"] = cur
        r = kget(url, p)
        out += r.get("markets", [])
        cur = r.get("cursor")
        if not cur or not r.get("markets"):
            break
    return out


def _num(d: dict | None, *keys):
    for k in keys:
        v = (d or {}).get(k)
        if v not in (None, ""):
            return float(v)
    return np.nan


def parse_candles(ticker: str, candles: list[dict]) -> pd.DataFrame:
    rows = []
    for c in candles:
        r = {"ticker": ticker, "t": c["end_period_ts"],
             "volume": _num(c, "volume_fp", "volume"), "open_interest": _num(c, "open_interest_fp", "open_interest")}
        for src, dst in (("yes_bid", "bid"), ("yes_ask", "ask"), ("price", "trade")):
            for f in ("open", "high", "low", "close"):
                r[f"{dst}_{f}"] = _num(c.get(src), f"{f}_dollars", f)
        r["trade_mean"] = _num(c.get("price"), "mean_dollars", "mean")
        rows.append(r)
    df = pd.DataFrame(rows)
    if len(df):
        df["t"] = pd.to_datetime(df["t"], unit="s", utc=True)      # END of the minute the candle covers
    return df


def kalshi_candles(series: str, ticker: str, start: pd.Timestamp, end: pd.Timestamp, archived: bool) -> pd.DataFrame:
    url = f"{K}/historical/markets/{ticker}/candlesticks" if archived else f"{K}/series/{series}/markets/{ticker}/candlesticks"
    parts, a = [], start
    while a < end:
        b = min(a + KALSHI_CHUNK, end)
        r = kget(url, {"start_ts": int(a.timestamp()), "end_ts": int(b.timestamp()), "period_interval": 1})
        parts.append(parse_candles(ticker, r.get("candlesticks", [])))
        a = b
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return df.drop_duplicates(["ticker", "t"]) if len(df) else df


def fill_kalshi(raw: pd.DataFrame, markets: pd.DataFrame) -> pd.DataFrame:
    """Minute grid per market from open to close: bid/ask/open interest forward-filled."""
    out = []
    for _, m in markets.iterrows():
        grid = pd.date_range(m["open_time"].ceil("min"), m["close_time"].floor("min"), freq="min")
        g = raw[raw["ticker"] == m["ticker"]].set_index("t").reindex(grid)
        f = pd.DataFrame(index=grid)
        f["observed"] = g["bid_close"].notna() | g["ask_close"].notna()
        f["bid"] = g["bid_close"].ffill()
        f["ask"] = g["ask_close"].ffill()
        f["open_interest"] = g["open_interest"].ffill()
        f["volume"] = g["volume"].fillna(0.0)
        f["trade_close"] = g["trade_close"]
        f.loc[f["bid"] <= 0, "bid"] = np.nan                       # empty bid side
        f.loc[f["ask"] >= 1, "ask"] = np.nan                       # empty ask side
        f = f.astype({"bid": "float32", "ask": "float32", "open_interest": "float32", "volume": "float32",
                      "trade_close": "float32"})
        f["ticker"] = m["ticker"]
        out.append(f.rename_axis("t").reset_index())
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


POOL = ThreadPoolExecutor(KALSHI_THREADS)


def kalshi_backfill() -> None:
    cutoff = pd.Timestamp(kget(f"{K}/historical/cutoff", None)["market_settled_ts"])
    ev = kalshi_events()
    cat_path = RAW / "kalshi" / "markets.parquet"
    catalog = [pd.read_parquet(cat_path)] if cat_path.exists() else []
    prog = Progress("Kalshi", len(ev))
    for _, e in ev.iterrows():
        raw_path = RAW / "kalshi" / "candles_1m" / e["series"] / f"{e['event']}.parquet"
        fill_path = PROC / "kalshi_1m" / e["series"] / f"{e['event']}.parquet"
        if raw_path.exists() and fill_path.exists():
            prog.tick(skipped=True)
            continue
        archived = e["settle"] < cutoff
        try:
            ms = kalshi_markets(e["event"], archived)
            mk = pd.DataFrame([{
                "series": e["series"], "event": e["event"], "ticker": m["ticker"], "settle": e["settle"],
                "strike_type": m.get("strike_type"), "floor_strike": m.get("floor_strike"), "cap_strike": m.get("cap_strike"),
                "open_time": pd.Timestamp(m["open_time"]), "close_time": pd.Timestamp(m["close_time"]),
                "result": m.get("result"), "outcome": {"yes": 1.0, "no": 0.0}.get(m.get("result")),
                "expiration_value": _num(m, "expiration_value"), "volume": _num(m, "volume_fp", "volume"),
                "archived": archived} for m in ms])
            if mk.empty:
                log.warning("Kalshi %s: no markets", e["event"])
                prog.tick()
                continue
            raw = pd.concat(list(POOL.map(lambda m: kalshi_candles(e["series"], m.ticker, m.open_time, m.close_time, archived),
                                          mk.itertuples())), ignore_index=True)
            write_atomic(raw, raw_path)
            write_atomic(fill_kalshi(raw, mk), fill_path)
            catalog.append(mk)
        except Exception:
            log.exception("Kalshi %s failed; will retry on the next run", e["event"])
        prog.tick()
        if prog.done % 100 == 0 and catalog:                       # checkpoint the catalog
            write_atomic(pd.concat(catalog).drop_duplicates("ticker", keep="last"), cat_path)
    if catalog:
        write_atomic(pd.concat(catalog).drop_duplicates("ticker", keep="last"), cat_path)
    log.info("Kalshi backfill finished")


# ── Polymarket ───────────────────────────────────────────────────────────────────────────────
def polymarket_events() -> list[dict]:
    evs = {}
    for sid, prefix in POLY_SERIES.items():
        for m0 in pd.date_range("2024-12-01", pd.Timestamp.now(tz="UTC").tz_localize(None) + pd.offsets.MonthBegin(1), freq="MS"):
            off = 0
            while True:
                r = get_json(f"{G}/events", params={
                    "series_id": sid, "closed": "true", "limit": 100, "offset": off,
                    "end_date_min": m0.strftime("%Y-%m-%dT00:00:00Z"),
                    "end_date_max": (m0 + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%dT00:00:00Z")}, pause=POLY_PAUSE)
                for e in r:
                    if e["title"].startswith(prefix) and "ET?" not in e["title"]:   # no hourly events
                        evs[e["id"]] = e
                off += 100
                if len(r) < 100:
                    break
    log.info("Polymarket: %d closed daily/weekly BTC events", len(evs))
    return sorted(evs.values(), key=lambda e: e.get("endDate") or "")


def polymarket_market_rows(e: dict) -> list[dict]:
    kind = "above" if e["title"].startswith("Bitcoin above") else "range"
    rows = []
    for m in e.get("markets") or []:
        end = m.get("endDate") or e.get("endDate")               # a few markets lack their own endDate
        if not m.get("clobTokenIds") or not end:
            log.warning("Polymarket %s: market %s has no token or end date; skipped", e["slug"], m.get("id"))
            continue
        label = m.get("groupItemTitle") or m.get("question", "")
        try:
            strike, lo, hi = parse_polymarket_strike(label, kind)
        except (IndexError, ValueError):
            strike = lo = hi = None
        prices = json.loads(m.get("outcomePrices") or "[]")
        resolved = m.get("umaResolutionStatus") == "resolved" and m.get("closed") and prices
        rows.append({
            "event_id": e["id"], "event_slug": e["slug"], "event": e["title"], "market_id": m["id"],
            "condition_id": m.get("conditionId"), "yes_token": json.loads(m["clobTokenIds"])[0],
            "question": m.get("question"), "kind": kind, "strike": strike, "range_low": lo, "range_high": hi,
            "start": pd.Timestamp(m.get("startDate") or e.get("startDate")),
            "end_date_gamma": pd.Timestamp(end),
            "resolution_time": polymarket_resolution_time(e["title"], m.get("description", ""), end),
            "outcome": float(round(float(prices[0]))) if resolved else np.nan,
            "uma_status": m.get("umaResolutionStatus"), "volume": float(m.get("volumeNum") or 0)})
    return rows


def polymarket_backfill() -> None:
    events = polymarket_events()
    cat_path = RAW / "polymarket" / "markets.parquet"
    catalog = []
    prog = Progress("Polymarket", len(events))
    for e in events:
        rows = polymarket_market_rows(e)
        catalog += rows
        path = RAW / "polymarket" / "mids_1m" / f"{e['slug']}.parquet"
        if path.exists() or not rows:
            prog.tick(skipped=True)
            continue
        try:
            parts = []
            for r in rows:
                h = get_json(f"{C}/prices-history", params={
                    "market": r["yes_token"], "startTs": int(r["start"].timestamp()),
                    "endTs": int((r["resolution_time"] + pd.Timedelta("1h")).timestamp()), "fidelity": 1},
                    pause=POLY_PAUSE).get("history", [])
                if h:
                    parts.append(pd.DataFrame({"market_id": r["market_id"],
                                               "t": pd.to_datetime([x["t"] for x in h], unit="s", utc=True),
                                               "mid": [float(x["p"]) for x in h]}))
            df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["market_id", "t", "mid"])
            write_atomic(df, path)
        except Exception:
            log.exception("Polymarket %s failed; will retry on the next run", e["slug"])
        prog.tick()
    write_atomic(pd.DataFrame(catalog), cat_path)
    log.info("Polymarket backfill finished")


def main():
    config.setup_logging()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("kalshi", "all"):
        kalshi_backfill()
    if which in ("polymarket", "all"):
        polymarket_backfill()


if __name__ == "__main__":
    main()
