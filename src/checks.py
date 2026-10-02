"""
Step 6: data-quality checks, used by notebooks/01_data_checks.ipynb.

Every check returns a DataFrame so the notebook can display it. `problems()` collects the
issues from all checks into one summary table (dataset, check, count, detail).
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

import config

R, P = config.DATA_RAW, config.DATA_PROCESSED
SNAPSHOT_GAP_WARN = pd.Timedelta("30min")   # snapshots run every 10 min; 30+ min without one is a gap

# name -> (path, expected spacing). Spacing None = irregular (no gap check).
SERIES = {
    "btc_price_hourly":     (R / "btc_price_hourly.parquet", "h"),
    "btc_price_daily":      (R / "btc_price_daily.parquet", "D"),
    "btc_price_0800":       (R / "btc_price_0800.parquet", "D"),
    "btc_index_6h_deribit": (R / "btc_index_6h_deribit.parquet", "6h"),
    "dvol_hourly":          (R / "dvol_hourly.parquet", "h"),
    "dvol_daily":           (R / "dvol_daily.parquet", "D"),
    "btc_dvol_hourly":      (P / "btc_dvol_hourly.parquet", "h"),
    "btc_dvol_daily":       (P / "btc_dvol_daily.parquet", "D"),
    "deribit_delivery":     (config.RESOLUTIONS_DIR / "deribit_delivery.parquet", "D"),
    "binance_noon_et":      (config.RESOLUTIONS_DIR / "binance_btcusdt_1m.parquet", None),  # DST shifts 16h/17h UTC
}


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(SERIES[name][0])


def snapshot_files(kind: str) -> list[str]:
    return sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / f"{kind}_*.parquet")))


def load_snapshots(kind: str) -> pd.DataFrame:
    files = snapshot_files(kind)
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True) if files else pd.DataFrame()


# ── 1. Coverage and gaps ────────────────────────────────────────────────────────────────────
def gap_blocks(index: pd.DatetimeIndex, freq: str) -> pd.DataFrame:
    missing = pd.date_range(index.min(), index.max(), freq=freq).difference(index)
    if missing.empty:
        return pd.DataFrame(columns=["gap_start", "missing_steps"])
    s = pd.Series(missing)
    block = (s.diff() != pd.tseries.frequencies.to_offset(freq)).cumsum()
    return s.groupby(block).agg(gap_start="first", missing_steps="count").reset_index(drop=True)


def coverage() -> pd.DataFrame:
    rows = []
    for name, (path, freq) in SERIES.items():
        idx = pd.read_parquet(path, columns=[]).index
        gaps = gap_blocks(idx, freq) if freq else pd.DataFrame()
        rows.append({
            "dataset": name, "rows": len(idx), "start": idx.min(), "end": idx.max(), "spacing": freq or "irregular",
            "missing_steps": int(gaps["missing_steps"].sum()) if len(gaps) else 0, "gap_blocks": len(gaps),
            "largest_gap": int(gaps["missing_steps"].max()) if len(gaps) else 0,
        })
    return pd.DataFrame(rows).set_index("dataset")


def snapshot_times() -> pd.DatetimeIndex:
    """UTC time of every Deribit snapshot, from the file names (.../YYYY-MM-DD/deribit_HHMMSS.parquet)."""
    stamps = [Path(f).parent.name + " " + Path(f).stem.split("_")[-1] for f in snapshot_files("deribit")]
    return pd.DatetimeIndex(sorted(pd.to_datetime(stamps, format="%Y-%m-%d %H%M%S", utc=True)))


def snapshot_gaps(times: pd.DatetimeIndex | None = None, min_gap: pd.Timedelta = SNAPSHOT_GAP_WARN) -> pd.DataFrame:
    """Every stretch of >= min_gap with no snapshot (PC asleep/off, logged out, network or API down)."""
    times = snapshot_times() if times is None else times
    if len(times) < 2:
        return pd.DataFrame(columns=["last_before", "next_after", "length"])
    g = pd.DataFrame({"last_before": times[:-1], "next_after": times[1:]})
    g["length"] = g["next_after"] - g["last_before"]
    return g[g["length"] >= min_gap].reset_index(drop=True)


def snapshot_coverage() -> pd.DataFrame:
    """Time between consecutive snapshots (scheduled every 10 min), and how stale the latest one is."""
    times = snapshot_times()
    if len(times) < 2:
        return pd.DataFrame({"snapshots": [len(times)]})
    gaps = pd.Series(times[1:] - times[:-1], index=times[1:])
    return pd.DataFrame({
        "snapshots": [len(times)], "first": [times[0]], "last": [times[-1]],
        "since_last": [(pd.Timestamp.now(tz="UTC") - times[-1]).floor("s")],
        "median_spacing": [gaps.median()], "gaps_over_30min": [(gaps >= SNAPSHOT_GAP_WARN).sum()],
        "longest_gap": [gaps.max()],
    })


# ── 2. Timezones and timestamp alignment ────────────────────────────────────────────────────
def timezones() -> pd.DataFrame:
    """Every datetime (index or column) in every parquet file should be tz-aware UTC."""
    files = [p for p, _ in SERIES.values()] + \
            sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet")))[:1] + \
            snapshot_files("deribit")[-1:] + snapshot_files("predmarkets")[-1:] + \
            [config.RESOLUTIONS_DIR / "predmarkets.parquet"]
    rows = []
    for f in files:
        df = pd.read_parquet(f).head(1)
        cols = {"(index)": df.index.dtype, **{c: t for c, t in df.dtypes.items()}}
        for col, dtype in cols.items():
            if "datetime" in str(dtype):
                rows.append({"file": Path(f).relative_to(config.ROOT).as_posix(), "column": col,
                             "dtype": str(dtype), "utc": str(getattr(dtype, "tz", None)) == "UTC"})
    return pd.DataFrame(rows)


def alignment() -> pd.DataFrame:
    """Do timestamps sit where they should (on the hour, at midnight, at 08:00, at 12:00 New York)?"""
    checks = {
        "btc_price_hourly on the hour": (load("btc_price_hourly").index, lambda i: (i.minute == 0) & (i.second == 0)),
        "dvol_hourly on the hour": (load("dvol_hourly").index, lambda i: (i.minute == 0) & (i.second == 0)),
        "daily files at 00:00 UTC": (load("btc_price_daily").index.append(load("dvol_daily").index), lambda i: i.hour == 0),
        "btc_price_0800 at 08:00 UTC": (load("btc_price_0800").index, lambda i: i.hour == 8),
        "deribit_delivery at 08:00 UTC": (load("deribit_delivery").index, lambda i: i.hour == 8),
        "binance noon rows at 12:00 New York": (
            load("binance_noon_et").query("is_noon_et").index,
            lambda i: (i.tz_convert("America/New_York").hour == 12) & (i.minute == 0)),
    }
    return pd.DataFrame([{"check": k, "rows": len(i), "misaligned": int((~ok(i)).sum())}
                         for k, (i, ok) in checks.items()]).set_index("check")


# ── 3. Duplicates ───────────────────────────────────────────────────────────────────────────
def duplicates() -> pd.DataFrame:
    rows = [{"dataset": n, "key": "timestamp", "rows": len(df), "duplicates": int(df.index.duplicated().sum())}
            for n in SERIES for df in [load(n)]]
    d, p = load_snapshots("deribit"), load_snapshots("predmarkets")
    if len(d):
        rows.append({"dataset": "snapshots/deribit", "key": "snapshot_time + instrument", "rows": len(d),
                     "duplicates": int(d.duplicated(["snapshot_time", "instrument_name"]).sum())})
    if len(p):
        rows.append({"dataset": "snapshots/predmarkets", "key": "snapshot_time + venue + market_id", "rows": len(p),
                     "duplicates": int(p.duplicated(["snapshot_time", "venue", "market_id"]).sum())})
    res = config.RESOLUTIONS_DIR / "predmarkets.parquet"
    if res.exists():
        r = pd.read_parquet(res)
        rows.append({"dataset": "resolutions/predmarkets", "key": "venue + market_id", "rows": len(r),
                     "duplicates": int(r.duplicated(["venue", "market_id"]).sum())})
    return pd.DataFrame(rows).set_index("dataset")


# ── 4. Bad values ───────────────────────────────────────────────────────────────────────────
def bad_values_timeseries() -> pd.DataFrame:
    h, d = load("btc_price_hourly"), load("dvol_hourly")
    at8 = load("btc_price_0800")
    ohlc_bad = lambda x: ((x["low"] > x[["open", "close"]].min(axis=1)) | (x["high"] < x[["open", "close"]].max(axis=1)))
    ret = np.log(h["close"]).diff()
    rows = [
        ("btc_price_hourly", "price <= 0", int((h[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())),
        ("btc_price_hourly", "OHLC inconsistent (low > open/close or high < open/close)", int(ohlc_bad(h).sum())),
        ("btc_price_hourly", "|hourly log return| > 10%", int((ret.abs() > 0.10).sum())),
        ("btc_price_hourly", "zero-volume hours", int((h["volume"] <= 0).sum())),
        ("dvol_hourly", "DVOL outside 10–250", int((~d["close"].between(10, 250)).sum())),
        ("dvol_hourly", "OHLC inconsistent", int(ohlc_bad(d).sum())),
        ("dvol_hourly", "|hourly change| > 20 vol points", int((d["close"].diff().abs() > 20).sum())),
        ("btc_price_0800", "|spot vs settlement| > 1%", int((at8["diff_pct"].abs() > 1).sum())),
        ("deribit_delivery", "delivery price <= 0", int((load("deribit_delivery")["delivery_price"] <= 0).sum())),
    ]
    return pd.DataFrame(rows, columns=["dataset", "check", "rows_flagged"])


def bad_values_snapshots() -> pd.DataFrame:
    d, p = load_snapshots("deribit"), load_snapshots("predmarkets")
    rows = []
    if len(d):
        rows += [
            ("snapshots/deribit", "bid > ask (crossed)", int((d["bid"] > d["ask"]).sum()), len(d)),
            ("snapshots/deribit", "no bid", int(d["bid"].isna().sum()), len(d)),
            ("snapshots/deribit", "no ask", int(d["ask"].isna().sum()), len(d)),
            ("snapshots/deribit", "mark_iv <= 0 or > 300", int((~d["mark_iv"].between(0.01, 300)).sum()), len(d)),
            ("snapshots/deribit", "forward_price <= 0", int((d["forward_price"] <= 0).sum()), len(d)),
            ("snapshots/deribit", "mark outside [bid, ask]",
             int(((d["mark_price"] < d["bid"]) | (d["mark_price"] > d["ask"])).sum()), len(d)),
        ]
    if len(p):
        q = p.assign(spread=p["yes_ask"] - p["yes_bid"])
        rows += [
            ("snapshots/predmarkets", "bid > ask (crossed)", int((q["spread"] < 0).sum()), len(q)),
            ("snapshots/predmarkets", "price outside [0, 1]",
             int(((q[["yes_bid", "yes_ask"]] < 0) | (q[["yes_bid", "yes_ask"]] > 1)).any(axis=1).sum()), len(q)),
            ("snapshots/predmarkets", "no two-sided quote", int((q["yes_bid"].isna() | q["yes_ask"].isna()).sum()), len(q)),
            ("snapshots/predmarkets", "spread > 10¢", int((q["spread"] > 0.10).sum()), len(q)),
            ("snapshots/predmarkets", "zero volume", int((q["volume"].fillna(0) <= 0).sum()), len(q)),
            ("snapshots/predmarkets", "'above' curve not decreasing in strike (pairs)", above_curve_violations(q), len(q)),
        ]
    out = pd.DataFrame(rows, columns=["dataset", "check", "rows_flagged", "rows"])
    out["share"] = (out["rows_flagged"] / out["rows"]).map("{:.1%}".format)
    return out


def above_curve_violations(q: pd.DataFrame, tol: float = 0.02) -> int:
    """P(BTC > K) must fall as K rises. Count adjacent strike pairs (two-sided quotes, spread <= 10¢)
    where the mid rises by more than `tol`. Violations = stale or illiquid quotes, or real arbitrage."""
    a = q[(q["kind"] == "above") & (q["spread"] <= 0.10)].copy()
    a["mid"] = (a["yes_bid"] + a["yes_ask"]) / 2
    a = a.sort_values(["snapshot_time", "venue", "event", "strike"])
    jump = a.groupby(["snapshot_time", "venue", "event"])["mid"].diff()
    return int((jump > tol).sum())


def bad_values_trades() -> pd.DataFrame:
    """Per-month counts over the option trade files (aggregated file by file to keep memory low)."""
    rows = []
    for f in sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet"))):
        t = pd.read_parquet(f, columns=["trade_id", "price", "iv", "days_to_expiry", "index_price", "is_block", "is_combo"])
        rows.append({
            "month": f[-15:-8], "trades": len(t),
            "dup_trade_id": int(t["trade_id"].duplicated().sum()),
            "price<=0": int((t["price"] <= 0).sum()),
            "iv=0": int((t["iv"] <= 0).sum()),
            "iv>=300": int((t["iv"] >= 300).sum()),
            "neg_dte": int((t["days_to_expiry"] < 0).sum()),
            "index<=0": int((t["index_price"] <= 0).sum()),
            "block": int(t["is_block"].sum()), "combo": int(t["is_combo"].sum()),
            "tz_utc": str(t.index.tz) == "UTC",
        })
    return pd.DataFrame(rows).set_index("month")


# ── Summary ─────────────────────────────────────────────────────────────────────────────────
def problems() -> pd.DataFrame:
    out = []
    cov = coverage()
    for name, r in cov[cov["missing_steps"] > 0].iterrows():
        out.append((name, "gaps", r["missing_steps"], f"{r['gap_blocks']} blocks, largest {r['largest_gap']} steps"))
    sc = snapshot_coverage()
    if "gaps_over_30min" in sc and sc["gaps_over_30min"].iloc[0] > 0:
        out.append(("snapshots", "gaps >= 30 min", int(sc["gaps_over_30min"].iloc[0]), f"longest {sc['longest_gap'].iloc[0]}"))
    if "since_last" in sc and sc["since_last"].iloc[0] >= SNAPSHOT_GAP_WARN:
        out.append(("snapshots", "stale: no snapshot for >= 30 min", 1, f"last {sc['last'].iloc[0]}"))
    tz = timezones()
    for _, r in tz[~tz["utc"]].iterrows():
        out.append((r["file"], "non-UTC timestamp", 1, r["column"]))
    for chk, r in alignment().query("misaligned > 0").iterrows():
        out.append(("timestamps", chk, r["misaligned"], "misaligned"))
    for name, r in duplicates().query("duplicates > 0").iterrows():
        out.append((name, "duplicates", r["duplicates"], r["key"]))
    for _, r in bad_values_timeseries().query("rows_flagged > 0").iterrows():
        out.append((r["dataset"], r["check"], r["rows_flagged"], ""))
    for _, r in bad_values_snapshots().query("rows_flagged > 0").iterrows():
        out.append((r["dataset"], r["check"], r["rows_flagged"], f"{r['share']} of rows"))
    tr = bad_values_trades()
    if len(tr):
        for col in ["dup_trade_id", "price<=0", "iv=0", "iv>=300", "neg_dte", "index<=0"]:
            if tr[col].sum():
                out.append(("option_trades", col, int(tr[col].sum()),
                            f"{tr[col].sum() / tr['trades'].sum():.2%} of {tr['trades'].sum():,} trades, {len(tr)} months"))
    return pd.DataFrame(out, columns=["dataset", "issue", "count", "detail"])
