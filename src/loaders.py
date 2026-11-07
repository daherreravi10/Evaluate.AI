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
    if key in ("rents_leases", "value_sales", "value_repeat"):
        # location columns come from the input file; an event file's own copy would clash in merges
        clash = {c: f"{c}_event" for c in ("suburb", "mb", "bkey", "bed", "car_space", "postcode")
                 if c in df.columns and c not in mapping}
        df = df.rename(columns=clash)
    if key == "value_sales" and "type" not in df.columns and "advertised_price" in df.columns:
        df = _sales_long(df)
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


def _sales_long(df: pd.DataFrame) -> pd.DataFrame:
    """Real file: one row per sale with its advert (advertised_price, advertised_date) beside it.

    -> one "Sold" row (date, price) plus one "For Sale" row (advertised_date, advertised_price)
    per sale. Adverts dated after the cut-off are later dropped by asof.until like any row.
    """
    sold = df.drop(columns=["advertised_price", "advertised_date"]).assign(type="Sold")
    ad = df.drop(columns=["date", "price"]).rename(
        columns={"advertised_date": "date", "advertised_price": "price"}).assign(type="For Sale")
    ad["price"] = pd.to_numeric(ad["price"], errors="coerce")
    ad = ad[ad["price"].notna() & ad["date"].notna()]
    out = pd.concat([sold, ad], ignore_index=True)
    print(f"[loaders] value_sales: {len(sold):,} sale rows + {len(ad):,} advert rows (from advertised_*)")
    return out


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


def merge_api_events(events: pd.DataFrame, task: str, kind: str, cutoff: str) -> pd.DataFrame:
    """Add rows from data/cache/api_events_<task>.parquet (scripts/api_history.py), if present.

    kind: "rent" for Task 4 adverts, "sale" for Task 5. Rows already in the supplied file
    (same gnaf_id, date, price) are dropped. The as-of cut-off is re-applied here.
    """
    p = C.CACHE / f"api_events_{task}.parquet"
    if not p.exists():
        return events
    api = pd.read_parquet(p)
    api = api[(api["kind"] == kind) & api.price.notna() & api.date.notna()]
    api = api[api.date <= pd.Timestamp(cutoff)]
    keep = [c for c in events.columns if c in api.columns] or ["gnaf_id", "date", "price"]
    api = api[keep].copy()
    if "type" in events.columns and "type" in api.columns:
        api["type"] = api["type"].fillna("Sold")
    key = ["gnaf_id", "date", "price"]
    seen = pd.MultiIndex.from_frame(events[key])
    api = api[~pd.MultiIndex.from_frame(api[key]).isin(seen)].drop_duplicates(key)
    print(f"[loaders] merged {len(api):,} new {kind} rows from the API cache")
    return pd.concat([events, api], ignore_index=True)
