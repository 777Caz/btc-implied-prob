"""
Kalshi trade history (with the taker's side) for a sample of 17:00 NY daily BTC events (KXBTCD).

Every SAMPLE_EVERY-th settlement day is fetched (all strikes, the whole market life), enough for
monthly shares of taker volume by side and price bucket. Markets settled before Kalshi's
historical cutoff are served by /historical/trades, newer ones by /markets/trades. Uses the
backfill's rate-limited client (src/pm_backfill.py); finished events are skipped on rerun.

Output: data/raw/pm_history/kalshi/trades/KXBTCD/<event>.parquet
  created_time, ticker, yes_price, count, taker_side ('yes' = taker bought YES), is_block_trade
Run:  python -m src.pm_kalshi_trades
"""
import logging

import pandas as pd

import config
from src import pm_backfill as pb

log = logging.getLogger(__name__)
OUT = config.DATA_RAW / "pm_history" / "kalshi" / "trades" / "KXBTCD"
SAMPLE_EVERY = 3


def market_trades(ticker: str, archived: bool) -> list[dict]:
    url = f"{pb.K}/historical/trades" if archived else f"{pb.K}/markets/trades"
    rows, cursor = [], None
    while True:
        params = {"ticker": ticker, "limit": 1000, **({"cursor": cursor} if cursor else {})}
        r = pb.kget(url, params)
        tr = r.get("trades", [])
        rows += [{"created_time": x["created_time"], "ticker": x["ticker"], "yes_price": float(x["yes_price_dollars"]),
                  "count": float(x["count_fp"]), "taker_side": x["taker_side"], "is_block_trade": bool(x.get("is_block_trade"))}
                 for x in tr]
        cursor = r.get("cursor")
        if not cursor or not tr:
            return rows


def sample_events() -> pd.DataFrame:
    c = pd.read_parquet(config.DATA_RAW / "pm_history" / "kalshi" / "markets.parquet")
    c = c[(c["series"] == "KXBTCD") & c["event"].str.endswith("17")]
    ev = c.groupby("event").agg(settle=("settle", "first"), archived=("archived", "first")).sort_values("settle")
    return ev.iloc[::SAMPLE_EVERY]


def main():
    config.setup_logging()
    OUT.mkdir(parents=True, exist_ok=True)
    c = pd.read_parquet(config.DATA_RAW / "pm_history" / "kalshi" / "markets.parquet")
    ev = sample_events()
    prog = pb.Progress("Kalshi trades", len(ev))
    for event, e in ev.iterrows():
        path = OUT / f"{event}.parquet"
        if path.exists():
            prog.tick(skipped=True)
            continue
        try:
            tickers = c.loc[c["event"] == event, "ticker"].tolist()
            parts = list(pb.POOL.map(lambda tk: market_trades(tk, bool(e["archived"])), tickers))
            df = pd.DataFrame([r for p in parts for r in p])
            if not df.empty:
                df["created_time"] = pd.to_datetime(df["created_time"], utc=True, format="ISO8601")
            pb.write_atomic(df, path)
        except Exception:
            log.exception("trades for %s failed; will retry on the next run", event)
        prog.tick()
    log.info("Kalshi trades finished")


if __name__ == "__main__":
    main()
