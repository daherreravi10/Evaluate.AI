"""The as-of rule, in one place. Every event table passes through here.

Task 4: nothing dated after 31 July 2026. Task 5: nothing after 31 August 2026.
The API has no as-of switch, so API output must be filtered here too.
"""
from __future__ import annotations

import pandas as pd


def until(df: pd.DataFrame, cutoff: str, date_col: str = "date", name: str = "") -> pd.DataFrame:
    """Keep rows dated ON or BEFORE the cut-off. Rows with no date are dropped."""
    cut = pd.Timestamp(cutoff)
    d = pd.to_datetime(df[date_col], errors="coerce")
    keep = d.notna() & (d <= cut)
    dropped_late = int((d > cut).sum())
    dropped_nodate = int(d.isna().sum())
    if name:
        print(f"[asof] {name}: kept {int(keep.sum()):,} rows <= {cutoff}; "
              f"dropped {dropped_late:,} later and {dropped_nodate:,} undated")
    return df.loc[keep].copy()


def assert_no_leak(df: pd.DataFrame, cutoff: str, date_col: str = "date", what: str = "") -> None:
    if len(df) and pd.to_datetime(df[date_col]).max() > pd.Timestamp(cutoff):
        raise AssertionError(f"LEAK: {what} has rows after {cutoff}")
