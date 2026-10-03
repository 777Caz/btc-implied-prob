"""
Gap-conditional trade test (the main strategy test): Kalshi 17:00 NY daily above-K markets,
decided at 08:00 UTC against the option-implied fair value q (src/pm_kalshi_options.py).

Rules, fixed in advance (no tuning on 2026), threshold T in {2c, 3c, 5c}:
  taker: buy YES at the ask if  q - ask - fee(ask) > T
         buy NO  at 1 - bid if  (1 - q) - (1 - bid) - fee(1 - bid) > T
  maker (OPTIMISTIC): rest a YES bid at the best bid if q - bid > T, or a NO bid at 1 - ask if
         (1 - q) - (1 - ask) > T, and assume it fills at that price with no adverse selection
         and no fee (no maker fee on these series). Only on real books (two-sided, spread <= 10c):
         a resting order at a 1c/99c placeholder quote would not fill.
Fee = Kalshi's quadratic taker fee for a 100-contract order, ceil(0.07 * C * P * (1 - P)) / C.
Every quote at 08:00 with the needed side is eligible (spread not capped: the taker pays the
quoted price). One trade per contract and day, 100 contracts each, held to settlement.

Reported per period (pre-2026, 2026 holdout) and threshold: trades, days traded, hit rate, mean
P&L per contract with a 95% CI clustered by event (= day), total, monthly P&L and the maximum
drawdown of the cumulative daily P&L. q from the usual 8-hour smile is primary; q from the last
hour of trades is a sensitivity check. Outputs: reports/pm/kalshi_gap_trade/.
Run:  python -m src.pm_kalshi_gap_trade
"""
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from src import pm_kalshi_calib as kc
from src import pm_kalshi_options as ko

log = logging.getLogger(__name__)
OUT = config.ROOT / "reports" / "pm" / "kalshi_gap_trade"
OUT.mkdir(parents=True, exist_ok=True)
THRESHOLDS = (0.02, 0.03, 0.05)
CONTRACTS = 100
Q_SOURCES = {"q (8h smile, primary)": "q", "q_1h (last-hour smile, sensitivity)": "q_1h"}


def trades(d: pd.DataFrame, qcol: str, T: float, style: str) -> pd.DataFrame:
    d = d[d[qcol].notna()]
    q, bid, ask, y = d[qcol], d["bid"], d["ask"], d["outcome"]
    if style == "taker":
        fee_yes, fee_no = kc.kalshi_taker_fee(ask.fillna(.5), CONTRACTS), kc.kalshi_taker_fee((1 - bid).fillna(.5), CONTRACTS)
        yes = ask.notna() & (q - ask - fee_yes > T)
        no = bid.notna() & ((1 - q) - (1 - bid) - fee_no > T)
        pnl_yes, pnl_no = y - ask - fee_yes, (1 - y) - (1 - bid) - fee_no
        cost_yes, cost_no = ask, 1 - bid
    else:
        real = d["usable"]                          # resting at a 1c/99c placeholder book would not fill
        yes = real & bid.notna() & (q - bid > T)
        no = real & ask.notna() & ((1 - q) - (1 - ask) > T)
        pnl_yes, pnl_no = y - bid, (1 - y) - (1 - ask)
        cost_yes, cost_no = bid, 1 - ask
    out = []
    for side, m, pnl, cost in (("YES", yes, pnl_yes, cost_yes), ("NO", no & ~yes, pnl_no, cost_no)):
        t = d[m].assign(side=side, pnl=pnl[m], price=cost[m], win=(pnl[m] > 0).astype(float), edge=(q - cost)[m] if side == "YES" else ((1 - q) - cost)[m])
        out.append(t)
    return pd.concat(out, ignore_index=True)


def max_drawdown(daily: pd.Series) -> float:
    cum = daily.sort_index().cumsum()
    return float((cum - cum.cummax().clip(lower=0)).min()) if len(cum) else np.nan


def summarise(t: pd.DataFrame, all_days: pd.DataFrame) -> dict:
    if t.empty:
        return {"trades": 0}
    lo, hi = kc.cluster_boot(t.assign(pc=t["pnl"] * 100), "pc")
    daily = t.groupby("day")["pnl"].sum() * CONTRACTS                       # dollars per day, 100 contracts/trade
    daily = daily.reindex(sorted(all_days), fill_value=0.0)
    return {"trades": len(t), "days_traded": t["day"].nunique(), "days_available": len(all_days),
            "yes_share": (t["side"] == "YES").mean(), "mean_price_c": t["price"].mean() * 100,
            "mean_edge_c": t["edge"].mean() * 100, "hit_rate": t["win"].mean(),
            "pnl_per_contract_c": t["pnl"].mean() * 100, "ci_lo": lo, "ci_hi": hi,
            "total_usd_100_contracts": t["pnl"].sum() * CONTRACTS, "max_drawdown_usd": max_drawdown(daily),
            "days_positive_share": (daily[daily != 0] > 0).mean()}


def main():
    config.setup_logging()
    d = pd.read_parquet(ko.OUT / "quotes_with_q.parquet")
    rows, monthly, curves = [], [], {}
    for qname, qcol in Q_SOURCES.items():
        for style in ("taker", "maker (OPTIMISTIC: assumes fills)"):
            for T in THRESHOLDS:
                t = trades(d, qcol, T, "taker" if style == "taker" else "maker")
                t["month"] = t["settle"].dt.strftime("%Y-%m")
                for period in ("pre-2026", "2026"):
                    tp, dp = t[t["period"] == period], d[(d["period"] == period) & d[qcol].notna()]
                    for side in ("both", "YES", "NO"):
                        ts = tp if side == "both" else tp[tp["side"] == side]
                        rows.append({"q_source": qname, "style": style, "T_c": T * 100, "period": period, "side": side,
                                     **summarise(ts, dp["day"].unique())})
                if qcol == "q":
                    m = t.groupby(["period", "month"]).agg(trades=("pnl", "size"), days=("day", "nunique"),
                                                           pnl_per_contract_c=("pnl", lambda x: x.mean() * 100),
                                                           total_usd=("pnl", lambda x: x.sum() * CONTRACTS)).reset_index()
                    monthly.append(m.assign(style=style, T_c=T * 100))
                    curves[(style, T)] = t.groupby("settle")["pnl"].sum().sort_index() * CONTRACTS
        log.info("%s done", qname)
    res, monthly = pd.DataFrame(rows), pd.concat(monthly, ignore_index=True)
    res.to_csv(OUT / "results.csv", index=False)
    monthly.to_csv(OUT / "monthly.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=False)
    colors = {0.02: "#2a78b5", 0.03: "#d1572c", 0.05: "#3a9a5b"}
    for ax, style in zip(axes, ("taker", "maker (OPTIMISTIC: assumes fills)")):
        for T in THRESHOLDS:
            c = curves[(style, T)]
            ax.plot(c.index, c.cumsum(), color=colors[T], lw=1.6, label=f"T = {T * 100:.0f}c")
        ax.axvline(pd.Timestamp("2026-01-01", tz="UTC"), color="#555", lw=1, ls="--")
        ax.text(pd.Timestamp("2026-01-08", tz="UTC"), 0.03, "2026 holdout", transform=ax.get_xaxis_transform(), fontsize=9, color="#555")
        ax.axhline(0, color="#999", lw=.8)
        ax.set(title=f"Cumulative P&L, {style}, 100 contracts per trade", ylabel="USD")
        ax.legend(frameon=False, loc="upper left")
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "cumulative_pnl.png", dpi=150)
    plt.close(fig)

    fmt = lambda t: t.to_string(index=False, float_format=lambda v: f"{v:.3f}")
    main_tab = res[(res["side"] == "both")].drop(columns=["side"])
    lines = [f"# Gap-conditional trade test, Kalshi 17:00 NY at 08:00 UTC vs option q (generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)", "",
             "Rules fixed in advance; thresholds T = 2c, 3c, 5c; no tuning on 2026. 100 contracts per trade, held to settlement.",
             "P&L in cents per contract after fees; CI = 95% cluster bootstrap by event (one event per day). Drawdown on cumulative daily P&L.", "",
             "## Both sides", "```", fmt(main_tab), "```",
             "## By side", "```", fmt(res[res["side"] != "both"]), "```",
             "## Monthly P&L (primary q)", "```", fmt(monthly), "```"]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Gap trade test done -> %s", OUT)


if __name__ == "__main__":
    main()
