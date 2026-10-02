"""
Intraday variance profile of BTC and "variance time" (needed to scale option smiles to < 1 day).

Data: Binance BTC/USDT 1-minute closes (src/binance_bulk.py), 2021-01 onwards. Returns are
1-minute log returns between CONSECUTIVE minutes only (exchange gaps are skipped, not bridged).

Profile. v(m) = E[r^2 | minute-of-day m (UTC)], estimated as the mean squared return in that
minute across days, separately for weekdays and weekends (UTC calendar). The share
s(m) = v(m) / sum_m v(m) is the fraction of a day's expected variance that arrives in minute m.
  Robustness: (i) "mean of daily shares": each day's r^2(m) / sum_m r^2 averaged over days, so a
  few crash days can't dominate; (ii) 5-minute returns, to check that 1-minute microstructure
  noise doesn't distort the shape; (iii) by year; (iv) by US daylight-saving regime (the US equity
  open is 13:30 UTC in summer, 14:30 UTC in winter).

Variance time between clock times t1 < t2 on one day:  tau(t1, t2) = sum_{m in [t1, t2)} s(m),
the fraction of the day's expected variance. Clock time would be (t2 - t1) / 24h.

Outputs: reports/intraday/ (RESULTS.md, CSVs, charts).
Run:  python -m src.intraday_vol
"""
import glob
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from src import visuals

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "intraday"
OUT.mkdir(parents=True, exist_ok=True)
NY = "America/New_York"
GREY = "#a9a8a3"

# windows of interest, UTC minutes since midnight: (label, start, end, note)
WINDOWS = [
    ("08:00-17:00 UTC", 8 * 60, 17 * 60, "Deribit expiry -> noon New York in winter (EST)"),
    ("08:00-16:00 UTC", 8 * 60, 16 * 60, "Deribit expiry -> noon New York in summer (EDT)"),
    ("08:00-22:00 UTC", 8 * 60, 22 * 60, "Deribit expiry -> 17:00 New York in winter"),
    ("08:00-21:00 UTC", 8 * 60, 21 * 60, "Deribit expiry -> 17:00 New York in summer"),
]


def load_returns(minutes: int = 1) -> pd.DataFrame:
    close = pd.concat(pd.read_parquet(f, columns=["close"]) for f in sorted(glob.glob(
        str(config.DATA_RAW / "binance_1m" / "BTCUSDT-1m-*.parquet"))))["close"].sort_index()
    if minutes > 1:
        close = close[close.index.minute % minutes == 0]
    lr = np.log(close).diff()
    ok = close.index.to_series().diff() == pd.Timedelta(minutes=minutes)     # consecutive bars only
    r = lr[ok.to_numpy()].dropna()
    # a return is attributed to the interval it covers, i.e. it STARTS at (end - minutes)
    start = r.index - pd.Timedelta(minutes=minutes)
    d = pd.DataFrame({"r2": r.to_numpy() ** 2}, index=start)
    d["mod"] = d.index.hour * 60 + d.index.minute
    d["date"] = d.index.normalize()
    d["weekend"] = d.index.dayofweek >= 5
    d["year"] = d.index.year
    local = d.index.tz_convert(NY).tz_localize(None)
    d["us_dst"] = (local - d.index.tz_localize(None)) == pd.Timedelta(hours=-4)   # EDT = UTC-4, EST = UTC-5
    return d


def share_profile(d: pd.DataFrame, robust: bool = False, step: int = 1) -> pd.Series:
    """Fraction of expected daily variance per minute-of-day bucket (sums to 1)."""
    if robust:
        day_tot = d.groupby("date")["r2"].transform("sum")
        x = d.assign(sh=d["r2"] / day_tot)
        prof = x.groupby("mod")["sh"].mean()
    else:
        prof = d.groupby("mod")["r2"].mean()
    prof = prof.reindex(range(0, 1440, step)).interpolate(limit_direction="both")
    return prof / prof.sum()


def tau(s: pd.Series, t1: int, t2: int) -> float:
    """Variance time between minute-of-day t1 and t2 (same day): sum of shares in [t1, t2)."""
    return float(s[(s.index >= t1) & (s.index < t2)].sum())


def window_table(profiles: dict[str, pd.Series]) -> pd.DataFrame:
    rows = []
    for label, a, b, note in WINDOWS:
        r = {"window": label, "meaning": note, "clock_fraction": (b - a) / 1440}
        for name, s in profiles.items():
            r[name] = tau(s, a, b)
        rows.append(r)
    return pd.DataFrame(rows)


def hourly(s: pd.Series) -> pd.Series:
    """Share per clock hour (sums to 1)."""
    return s.groupby(s.index // 60).sum()


def chart_profiles(prof: dict[str, pd.Series], cum_from: int = 8 * 60):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    to_rate = lambda s, w=30: s.groupby(s.index // w).sum() * (60 / w)            # share of daily var per HOUR
    x30 = np.arange(0, 1440, 30) / 60 + 0.25

    ax = axes[0]
    for name, color, label in (("weekday", visuals.BLUE, "Weekdays"), ("weekend", visuals.ORANGE, "Weekends")):
        y = to_rate(prof[name])
        ax.plot(x30, y.to_numpy(), color=color, lw=2, label=label)
        ax.annotate(label, (x30[-1], y.iloc[-1]), xytext=(4, 0), textcoords="offset points", color=visuals.INK_2, fontsize=8.5, va="center")
    ax.axhline(1 / 24, color=visuals.INK_2, lw=0.8, ls="--")
    ax.text(0.3, 1 / 24, "flat (clock time)", color=visuals.INK_2, fontsize=8, va="bottom")
    ax.set_title("Share of daily variance per hour (UTC)")
    ax.legend(loc="upper left")

    ax = axes[1]
    for name, color, label in (("weekday_us_summer", visuals.BLUE, "Weekdays, US summer time (EDT)"),
                               ("weekday_us_winter", visuals.AQUA, "Weekdays, US winter time (EST)")):
        ax.plot(x30, to_rate(prof[name]).to_numpy(), color=color, lw=2, label=label)
    for h, txt in ((13.5, "US open\nEDT"), (14.5, "US open\nEST")):
        ax.axvline(h, color=GREY, lw=0.8)
        ax.text(h + 0.15, 0.03, txt.replace("\n", " "), rotation=90, fontsize=7.5, color=visuals.INK_2, va="bottom",
                transform=ax.get_xaxis_transform())
    ax.axhline(1 / 24, color=visuals.INK_2, lw=0.8, ls="--")
    ax.set_title("Weekdays by US daylight-saving regime")
    ax.legend(loc="upper left")

    ax = axes[2]
    hrs = np.arange(0, 24 * 60 + 1, 30)
    for name, color, label in (("weekday", visuals.BLUE, "Weekdays"), ("weekend", visuals.ORANGE, "Weekends")):
        s = prof[name]
        cum = [tau(s, cum_from, cum_from + h) if cum_from + h <= 1440 else
               tau(s, cum_from, 1440) + tau(s, 0, cum_from + h - 1440) for h in hrs]
        ax.plot(hrs / 60, cum, color=color, lw=2, label=label)
    ax.plot([0, 24], [0, 1], color=visuals.INK_2, lw=0.8, ls="--", label="clock time")
    for label, a, b, _ in WINDOWS[:2]:
        ax.axvline((b - a) / 60, color=GREY, lw=0.8)
    ax.set_title("Cumulative variance time from 08:00 UTC")
    ax.set_xlabel("hours after 08:00 UTC")
    ax.legend(loc="upper left")
    for a in axes[:2]:
        a.set_xlim(0, 24); a.set_xticks(range(0, 25, 4)); a.set_xlabel("hour of day (UTC)")
    fig.tight_layout()
    visuals.save(fig, "intraday_profile.png", OUT)


def chart_by_year(pooled: pd.Series, by_year: dict[int, pd.Series]):
    years = sorted(by_year)
    fig, axes = plt.subplots(2, int(np.ceil(len(years) / 2)), figsize=(14, 6), sharex=True, sharey=True)
    x = np.arange(24) + 0.5
    for ax, y in zip(axes.flat, years):
        ax.plot(x, hourly(pooled).to_numpy(), color=GREY, lw=2, label="all years")
        ax.plot(x, hourly(by_year[y]).to_numpy(), color=visuals.BLUE, lw=2, label=str(y))
        ax.axhline(1 / 24, color=visuals.INK_2, lw=0.8, ls="--")
        ax.set_title(f"{y} (weekdays)")
        ax.set_xticks(range(0, 25, 6))
    axes.flat[0].legend(loc="upper left", labels=["all years", "this year"])
    fig.suptitle("Share of daily variance per hour (UTC), weekdays, by year", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    visuals.save(fig, "intraday_by_year.png", OUT)


def main():
    config.setup_logging()
    d = load_returns(1)
    log.info("1-minute returns: %d, %s to %s", len(d), d.index.min(), d.index.max())
    wd, we = d[~d["weekend"]], d[d["weekend"]]
    prof = {
        "all_days": share_profile(d), "weekday": share_profile(wd), "weekend": share_profile(we),
        "weekday_robust": share_profile(wd, robust=True), "weekend_robust": share_profile(we, robust=True),
        "weekday_us_summer": share_profile(wd[wd["us_dst"]]), "weekday_us_winter": share_profile(wd[~wd["us_dst"]]),
    }
    d5 = load_returns(5)
    prof5 = {"weekday_5min": share_profile(d5[~d5["weekend"]], step=5), "weekend_5min": share_profile(d5[d5["weekend"]], step=5)}
    by_year = {y: share_profile(g) for y, g in wd.groupby("year")}
    by_year_we = {y: share_profile(g) for y, g in we.groupby("year")}

    pd.DataFrame(prof).to_csv(OUT / "profile_1min_shares.csv", index_label="minute_of_day_utc")
    hourly_tbl = pd.DataFrame({k: hourly(v) for k, v in {**prof, **prof5}.items()})
    hourly_tbl.to_csv(OUT / "profile_hourly_shares.csv", index_label="hour_utc")

    win = window_table({**prof, **prof5})
    win.to_csv(OUT / "variance_time_windows.csv", index=False)
    yr = pd.DataFrame({
        "weekday_08-17": {y: tau(s, 480, 1020) for y, s in by_year.items()},
        "weekend_08-17": {y: tau(s, 480, 1020) for y, s in by_year_we.items()},
        "weekday_corr_with_pooled (hourly)": {y: np.corrcoef(hourly(s), hourly(prof["weekday"]))[0, 1] for y, s in by_year.items()},
        "weekday_peak_hour_utc": {y: int(hourly(s).idxmax()) for y, s in by_year.items()},
        "weekday_peak/trough": {y: hourly(s).max() / hourly(s).min() for y, s in by_year.items()},
        "days": {y: g["date"].nunique() for y, g in d.groupby("year")}})
    yr.to_csv(OUT / "stability_by_year.csv", index_label="year")
    # DST-matched noon NY: 08:00 -> 16:00 UTC in summer, 08:00 -> 17:00 UTC in winter
    dst = pd.DataFrame([
        {"regime": "US summer (EDT): 08:00 UTC -> noon NY = 16:00 UTC", "variance_time": tau(prof["weekday_us_summer"], 480, 960), "clock": 8 / 24},
        {"regime": "US winter (EST): 08:00 UTC -> noon NY = 17:00 UTC", "variance_time": tau(prof["weekday_us_winter"], 480, 1020), "clock": 9 / 24}])

    # level across days: needed when a horizon crosses midnight (shares above are WITHIN a day)
    day = d.groupby("date").agg(rv=("r2", "sum"), weekend=("weekend", "first"), year=("year", "first"))
    lvl = day.groupby(["year", "weekend"])["rv"].mean().unstack()
    level = pd.DataFrame({"weekend/weekday daily variance (mean)": lvl[True] / lvl[False],
                          "weekend/weekday (median)": day.groupby(["year", "weekend"])["rv"].median().unstack().pipe(lambda t: t[True] / t[False])})
    level.loc["all"] = [day.loc[day.weekend, "rv"].mean() / day.loc[~day.weekend, "rv"].mean(),
                        day.loc[day.weekend, "rv"].median() / day.loc[~day.weekend, "rv"].median()]
    level.to_csv(OUT / "weekend_level.csv", index_label="year")

    chart_profiles(prof)
    chart_by_year(prof["weekday"], by_year)

    f = lambda t, idx=False: t.to_string(index=idx, float_format=lambda v: f"{v:.3f}")
    lines = [f"# Intraday variance profile and variance time (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             f"Binance BTC/USDT 1-minute returns, {d['date'].nunique()} days ({d.index.min():%Y-%m-%d} to {d.index.max():%Y-%m-%d}); "
             f"{wd['date'].nunique()} weekdays, {we['date'].nunique()} weekend days.", "",
             "## Variance time of key windows (fraction of a day's expected variance)", "```", f(win.drop(columns="meaning")), "```",
             "Window meanings:", *[f"- {l}: {n}" for l, _, _, n in WINDOWS], "",
             "## DST-matched: Deribit 08:00 UTC expiry -> Polymarket noon New York (weekdays)", "```", f(dst), "```", "",
             "## Stability by year", "```", f(yr, True), "```", "",
             "## Daily variance level, weekend vs weekday (for horizons crossing midnight)", "```", f(level, True), "```", "",
             "## Share of daily variance per UTC hour", "```", f(hourly_tbl, True), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Intraday analysis done -> %s", OUT)


if __name__ == "__main__":
    main()
