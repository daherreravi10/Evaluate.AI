"""Load the supplied files with canonical column names and parsed dates."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

DATE_COLS = {"date", "date_1", "date_2", "first_ever_listed", "attrs_last_seen"}


def _path(key: str) -> Path:
    p = C.SUPPLIED / C.FILES[key]
    if not p.exists():
        raise FileNotFoundError(
            f"{p} missing. Put the emailed file in data/supplied/ "
            f"(or run: python scripts/make_mock_data.py)"
        )
    return p


def load(key: str) -> pd.DataFrame:
    """Read a supplied CSV and rename real columns to canonical names.

    Missing optional columns are created as NaN and reported, so a GUESSED
    schema fails loudly but does not crash the whole pipeline.
    """
    df = pd.read_csv(_path(key), dtype={"gnaf_id": str, "mb": str}, low_memory=False)
    mapping = C.SCHEMA[key]
    inverse = {real: canon for canon, real in mapping.items()}
    df = df.rename(columns=inverse)
    missing = [c for c in mapping if c not in df.columns]
    if missing:
        print(f"[loaders] {key}: columns not found {missing} -> filled with NaN. "
              f"Fix SCHEMA['{key}'] in src/config.py. Real columns: {list(df.columns)}")
        for c in missing:
            df[c] = np.nan
    for c in DATE_COLS & set(df.columns):
        df[c] = pd.to_datetime(df[c], errors="coerce")
        # 0001-01-01 means "no known date"
        df.loc[df[c] < "1900-01-01", c] = pd.NaT
    return df


UNIT_RE = re.compile(r"^\s*(?:UNIT|APARTMENT|APT|FLAT|SUITE|SHOP|OFFICE|U)?\s*[\w/-]*\s*,\s*", re.I)


def building_key(address: pd.Series, suburb: pd.Series) -> pd.Series:
    """'Unit 315, 2-4 Powell Street' + 'Waterloo (NSW)' -> '2-4 POWELL STREET|WATERLOO (NSW)'.

    Always compute it from the INPUT file and attach it to past events by
    gnaf_id, so event files with a different address format still match.
    """
    b = address.fillna("").str.upper().str.replace(UNIT_RE, "", regex=True)
    b = b.str.replace(r"^\s*[A-Z]?\d+[A-Z]?\s*/\s*", "", regex=True)  # '315/2-4 X ST'
    b = b.str.replace(r"\s+", " ", regex=True).str.strip()
    return b + "|" + suburb.fillna("").str.upper().str.strip()


def floor_from_unit(unit_number: pd.Series) -> pd.Series:
    """Unit 315 -> floor 3; 1204 -> 12; 7 -> NaN (too short to tell)."""
    s = unit_number.astype(str).str.extract(r"(\d+)")[0]
    n = pd.to_numeric(s, errors="coerce")
    floor = np.where(n >= 100, n // 100, np.nan)
    return pd.Series(floor, index=unit_number.index).where(lambda x: x <= 80)
