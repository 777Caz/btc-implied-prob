"""
Thin wrappers around pandas read/write parquet so the rest of the code
doesn't need to know file naming conventions.
"""
from pathlib import Path
import pandas as pd
import logging

log = logging.getLogger(__name__)


def save_parquet(df: pd.DataFrame, path: Path, *, overwrite: bool = True, compression: str = "snappy") -> None:
    """compression: "snappy" (pandas default, fastest) or "zstd" (~30-50% smaller, used for the
    many small snapshot files that accumulate every 10 minutes)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        log.info("Skipping existing file: %s", path)
        return
    if isinstance(df.index, pd.DatetimeIndex):
        # One convention for every file: timezone-aware UTC, millisecond precision.
        if str(df.index.tz) != "UTC":
            raise ValueError(f"Refusing to save non-UTC timestamps (tz={df.index.tz}) to {path}")
        df = df.copy()
        df.index = df.index.as_unit("ms")
    df.to_parquet(path, index=True, compression=compression)
    log.info("Saved %d rows -> %s", len(df), path)


def load_parquet(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Parquet not found: {path}")
    df = pd.read_parquet(path)
    log.info("Loaded %d rows <- %s", len(df), path)
    return df
