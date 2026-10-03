"""
Paper-trading log for the Kalshi gap rule (no orders are ever sent).

Every day at 08:07 UTC (Task Scheduler, deploy/register_tasks.ps1):
  1. Kalshi: the 08:00 UTC live snapshot (data/raw/snapshots/<date>/predmarkets_0800xx.parquet),
     "above K" markets of today's 17:00 New York event (KXBTCD), best bid/ask and their sizes.
  2. Options: q = P(S > K) exactly as in the backtest (src/pm_kalshi_options.py): Deribit option
     trades in the 8 hours before 08:00 (history.deribit.com), cleaned, front smile SVI with the
     centre m constrained, scaled to 17:00 NY with variance time + event profile, alpha = 0.5.
     Basis BRTI / Deribit index = 1 (measured median +0.1 bp, SD 5 bp: immaterial).
  3. Gap rule for T = 2, 3, 5c (src/pm_kalshi_gap_trade.py):
       taker: buy YES at the ask if q - ask - fee > T; buy NO at 1 - bid if (1-q) - (1-bid) - fee > T
       maker: rest a YES bid at the best bid if q - bid > T; a NO bid at 1 - ask if (1-q) - (1-ask) > T
              (real books only: two-sided, spread <= 10c)
     Logged with the best-level size: for a taker the size available at that price (capacity,
     contracts = min(100, size)); for a maker the size already resting at that price (queue ahead).
Settlement (called from src/resolutions.py, daily 00:30 UTC, idempotent): Kalshi's market result,
and for maker rows the actual fills from Kalshi's public trade history after the signal time:
touch (a taker traded at our price, ignoring queue) and through (a trade beyond our price, which
fills even the back of the queue). Unfilled maker rows earn 0.

Log: data/processed/paper_trades/kalshi_gap_log.parquet (one row per signal).
Run:  python -m src.paper_trade            (today's signals, then settle anything due)
      python -m src.paper_trade 2026-10-01 (signals for a past date from its 08:00 snapshot)
"""
import glob
import logging
import sys

import numpy as np
import pandas as pd

import config
from src import pm_backfill as pb
from src import pm_kalshi_calib as kc
from src import pm_kalshi_options as ko
from src import short_horizon as sh
from src.clean_trades import COLUMNS, clean
from src.deribit_options import fetch_trades, parse_instruments
from src.storage import save_parquet

log = logging.getLogger(__name__)
LOG = config.DATA_PROCESSED / "paper_trades" / "kalshi_gap_log.parquet"
STRIKES = config.DATA_PROCESSED / "paper_trades" / "kalshi_strikes_0800.parquet"   # every strike, every day (dashboard)
THRESHOLDS = (0.02, 0.03, 0.05)
CONTRACTS = 100
NY = "America/New_York"


def snapshot_0800(day: pd.Timestamp) -> pd.DataFrame:
    files = sorted(glob.glob(str(config.SNAPSHOTS_DIR / f"{day:%Y-%m-%d}" / "predmarkets_080*.parquet")))
    if not files:
        return pd.DataFrame()
    s = pd.read_parquet(files[0])
    settle = (pd.Timestamp(f"{day:%Y-%m-%d}") + pd.Timedelta(hours=17)).tz_localize(NY).tz_convert("UTC")
    return s[(s["venue"] == "kalshi") & (s["kind"] == "above") & (s["resolution_time"] == settle)].copy()


def forward_from_snapshot(t: pd.DataFrame, origin: pd.Timestamp):
    files = sorted(glob.glob(str(config.SNAPSHOTS_DIR / f"{origin:%Y-%m-%d}" / "deribit_080*.parquet")))
    w = t[t["expiry"] > origin]
    if not files or w.empty:
        return None
    chain = pd.read_parquet(files[0])
    fwd = chain[chain["expiry"] > origin].groupby("expiry")[["forward_price", "index_price"]].first()
    front_exp = min(set(w["expiry"]) & set(fwd.index), default=None)
    if front_exp is None:
        return None
    basis = fwd.at[front_exp, "forward_price"] / fwd.at[front_exp, "index_price"]
    idx_ref = w["index_price"].iloc[-1]
    front = sh.fit_expiry(origin, w[w["expiry"] == front_exp], basis, idx_ref, constrain_m=True)
    return {"front": front, "front_expiry": front_exp, "idx_ref": idx_ref}


def option_q(origin: pd.Timestamp, settle: pd.Timestamp, strikes: np.ndarray) -> tuple[np.ndarray, dict]:
    raw = parse_instruments(fetch_trades(origin - sh.WINDOW, origin))
    t, _ = clean(raw[COLUMNS])
    inp = sh.day_inputs(t, origin)
    source = "parity (as backtest)"
    if inp is None or inp["front"] is None:
        # Too few call/put pairs for the parity forward (typical on weekends; the backtest skips
        # such days). Live, the 08:00 Deribit snapshot has the exchange's forward for each expiry.
        inp = forward_from_snapshot(t, origin)
        source = "Deribit snapshot forward (fallback)"
        if inp is None or inp["front"] is None:
            raise RuntimeError("no front smile fit")
    models, ev_by_day = ko.variance_models()
    model = models[sh.month_key(origin)]
    T1 = inp["front_expiry"]
    lam = sh.tau(model, origin, settle, ev_by_day, True) / sh.tau(model, origin, T1, ev_by_day, True)
    dist, gmin, cal = sh.forecast(inp["front"], T1, origin, settle, lam, 0.5, inp["idx_ref"], 1.0)
    info = {"forward_source": source, "option_trades": len(t), "front_expiry": T1, "lambda": lam, "forward": dist.forward,
            "front_rmse_vol_pts": inp["front"]["rmse_vol_pts"], "butterfly_min_g": gmin, "calendar_max_excess": cal}
    return np.clip([dist.p_above(k) for k in strikes], 0, 1), info


def signals(day: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    origin = day + pd.Timedelta(hours=8)
    k = snapshot_0800(day)
    if k.empty:
        log.warning("paper trade %s: no 08:00 Kalshi snapshot for today's 17:00 NY event", f"{day:%Y-%m-%d}")
        return pd.DataFrame(), pd.DataFrame()
    settle = k["resolution_time"].iloc[0]
    q, info = option_q(origin, settle, k["strike"].to_numpy())
    k = k.assign(q=q)
    bid, ask = k["yes_bid"], k["yes_ask"]
    real = bid.notna() & ask.notna() & (ask > bid) & (ask - bid <= kc.MAX_SPREAD + 1e-9)
    rows = []
    for T in THRESHOLDS:
        fy = pd.Series(kc.kalshi_taker_fee(ask.fillna(.5), CONTRACTS), index=k.index)
        fn = pd.Series(kc.kalshi_taker_fee((1 - bid).fillna(.5), CONTRACTS), index=k.index)
        rules = [("taker", "YES", ask.notna() & (k["q"] - ask - fy > T), ask, fy, k["yes_ask_size"]),
                 ("taker", "NO", bid.notna() & ((1 - k["q"]) - (1 - bid) - fn > T), 1 - bid, fn, k["yes_bid_size"]),
                 ("maker", "YES", real & (k["q"] - bid > T), bid, 0.0 * bid, k["yes_bid_size"]),
                 ("maker", "NO", real & ((1 - k["q"]) - (1 - ask) > T), 1 - ask, 0.0 * ask, k["yes_ask_size"])]
        for style, side, m, price, fee, size in rules:
            for i in np.flatnonzero(m.to_numpy()):
                r = k.iloc[i]
                edge = (r["q"] if side == "YES" else 1 - r["q"]) - price.iloc[i] - fee.iloc[i]
                rows.append({"date": f"{day:%Y-%m-%d}", "origin": origin, "snapshot_time": r["snapshot_time"],
                             "event": r["event"], "ticker": r["market_id"], "strike": r["strike"], "close_time": settle,
                             "T_c": T * 100, "style": style, "side": side, "q": r["q"], "yes_bid": r["yes_bid"],
                             "yes_ask": r["yes_ask"], "price": price.iloc[i], "fee": fee.iloc[i], "edge_c": edge * 100,
                             "best_size": size.iloc[i],
                             "contracts": min(CONTRACTS, size.iloc[i]) if style == "taker" else CONTRACTS,
                             "logged_at": pd.Timestamp.now(tz="UTC"), **info})
    out = pd.DataFrame(rows)
    table = k[["event", "market_id", "strike", "resolution_time", "yes_bid", "yes_ask", "yes_bid_size", "yes_ask_size",
               "snapshot_time", "q"]].assign(date=f"{day:%Y-%m-%d}", **{c: info[c] for c in ("forward", "lambda", "option_trades")})
    log.info("paper trade %s: %d strikes, %d signals (%s)", f"{day:%Y-%m-%d}", len(k), len(out),
             out.groupby(["T_c", "style"]).size().to_dict() if len(out) else {})
    return out, table


def kalshi_market(ticker: str) -> dict:
    try:
        return pb.kget(f"{pb.K}/markets/{ticker}", None)["market"]
    except Exception:
        return pb.kget(f"{pb.K}/historical/markets/{ticker}", None)["market"]


def kalshi_trades_after(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for url in (f"{pb.K}/markets/trades", f"{pb.K}/historical/trades"):
        cursor = None
        while True:
            p = {"ticker": ticker, "limit": 1000, "min_ts": int(start.timestamp()), "max_ts": int(end.timestamp()),
                 **({"cursor": cursor} if cursor else {})}
            r = pb.kget(url, p)
            rows += r.get("trades", [])
            cursor = r.get("cursor")
            if not cursor or not r.get("trades"):
                break
        if rows:
            break
    t = pd.DataFrame(rows)
    if not t.empty:
        t["yes_price"] = t["yes_price_dollars"].astype(float)
    return t


def settle() -> None:
    if not LOG.exists():
        return
    d = pd.read_parquet(LOG)
    due = d["outcome"].isna() & (d["close_time"] < pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=30))
    if not due.any():
        return
    cache = {}
    for i in d.index[due]:
        tk = d.at[i, "ticker"]
        if tk not in cache:
            m = kalshi_market(tk)
            if m.get("result") not in ("yes", "no"):
                cache[tk] = None
                continue
            tr = kalshi_trades_after(tk, d.at[i, "snapshot_time"], d.at[i, "close_time"])
            cache[tk] = (1.0 if m["result"] == "yes" else 0.0, m.get("expiration_value"), tr)
        if cache[tk] is None:
            continue
        y, value, tr = cache[tk]
        side, price = d.at[i, "side"], d.at[i, "price"]
        pay = y if side == "YES" else 1 - y
        if d.at[i, "style"] == "taker":
            touch = through = 1.0
        else:
            sells = tr.loc[tr["taker_side"] == "no", "yes_price"] if len(tr) else pd.Series(dtype=float)
            buys = tr.loc[tr["taker_side"] == "yes", "yes_price"] if len(tr) else pd.Series(dtype=float)
            bid, ask = d.at[i, "yes_bid"], d.at[i, "yes_ask"]
            touch = float((sells <= bid + 1e-9).any() if side == "YES" else (buys >= ask - 1e-9).any())
            through = float((sells < bid - 1e-9).any() if side == "YES" else (buys > ask + 1e-9).any())
        pnl = pay - price - d.at[i, "fee"]
        d.loc[i, ["outcome", "expiration_value", "filled_touch", "filled_through", "pnl_c_if_filled",
                  "pnl_c_touch", "pnl_c_through", "settled_at"]] = [
            y, float(value) if value not in (None, "") else np.nan, touch, through, pnl * 100,
            pnl * 100 if touch else 0.0, pnl * 100 if through else 0.0, pd.Timestamp.now(tz="UTC")]
    save_parquet(d, LOG)
    log.info("paper trade: settled %d rows", int(due.sum() - d.loc[due, "outcome"].isna().sum()))


def upsert_day(new: pd.DataFrame, path) -> None:
    old = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    if len(old):
        old = old[old["date"] != new["date"].iloc[0]]                  # re-running a day replaces it
    path.parent.mkdir(parents=True, exist_ok=True)
    save_parquet(pd.concat([old, new], ignore_index=True), path)


def append(new: pd.DataFrame, table: pd.DataFrame) -> None:
    if len(table):
        upsert_day(table, STRIKES)
    if new.empty:
        return
    for c in ("outcome", "expiration_value", "filled_touch", "filled_through", "pnl_c_if_filled", "pnl_c_touch",
              "pnl_c_through", "settled_at"):
        new[c] = np.nan
    new["settled_at"] = pd.Series(pd.NaT, index=new.index, dtype="datetime64[us, UTC]")
    upsert_day(new, LOG)


def main():
    config.setup_logging()
    day = pd.Timestamp(sys.argv[1], tz="UTC") if len(sys.argv) > 1 else pd.Timestamp.now(tz="UTC").normalize()
    done = STRIKES.exists() and (pd.read_parquet(STRIKES, columns=["date"])["date"] == f"{day:%Y-%m-%d}").any()
    if not done or len(sys.argv) > 1:
        try:
            append(*signals(day))
        except Exception:
            log.exception("paper trade signals for %s failed", f"{day:%Y-%m-%d}")
    settle()


if __name__ == "__main__":
    main()
