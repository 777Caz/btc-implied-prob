"""
Phase 3, step 1: cleaning rules for historical option trades before smile fitting.

  iv = 0          Deribit could not compute an IV (mostly trades at or below intrinsic value)
  iv >= 300       mostly the last hours before expiry, where the IV calculation magnifies price noise
  combo legs      priced as a package, so an individual leg's price/IV can be off
  < 1 day to expiry   IV of very short options is dominated by noise and by the exact settlement
                      averaging; they also say nothing about a 30-day distribution

Each rule is reported twice: rows it would remove on its own, and rows it removes when applied
in the order above (the second adds up to the total removed).
"""
import glob

import pandas as pd

import config

RULES = {
    "iv = 0": lambda t: t["iv"] <= 0,
    "iv >= 300": lambda t: t["iv"] >= 300,
    "combo leg": lambda t: t["is_combo"],
    "< 1 day to expiry": lambda t: t["days_to_expiry"] < 1,
}
COLUMNS = ["instrument_name", "price", "iv", "index_price", "amount", "direction", "is_block", "is_combo",
           "expiry", "strike", "option_type", "days_to_expiry"]


def clean(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (kept trades, report). Report columns: alone = removed by this rule on its own,
    sequential = removed by this rule after the earlier rules were applied."""
    keep = pd.Series(True, index=trades.index)
    rows = []
    for name, rule in RULES.items():
        hit = rule(trades).fillna(False).astype(bool)
        rows.append({"rule": name, "alone": int(hit.sum()), "sequential": int((hit & keep).sum())})
        keep &= ~hit
    report = pd.DataFrame(rows).set_index("rule")
    report.loc["total removed"] = [int((~keep).sum()), int((~keep).sum())]
    report.loc["kept"] = [int(keep.sum()), int(keep.sum())]
    report["share_of_all_%"] = report["sequential"] / len(trades) * 100
    return trades[keep], report


def clean_all_months() -> pd.DataFrame:
    """Cleaning report summed over every monthly trade file (file by file, to keep memory low)."""
    total = None
    for f in sorted(glob.glob(str(config.OPTION_TRADES_DIR / "*.parquet"))):
        _, rep = clean(pd.read_parquet(f, columns=COLUMNS))
        total = rep[["alone", "sequential"]] if total is None else total + rep[["alone", "sequential"]]
    n = total.loc["total removed", "sequential"] + total.loc["kept", "sequential"]
    total["share_of_all_%"] = total["sequential"] / n * 100
    return total
