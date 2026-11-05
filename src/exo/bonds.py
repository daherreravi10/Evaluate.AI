"""NSW Fair Trading rental bond lodgements: real new leases (not adverts), by month,
postcode, dwelling type and bedrooms.

Monthly files: https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/rental-bond-data
e.g. .../sites/default/files/noindex/2026-07/rentalbond_lodgements_june_2026.xlsx
(the file for month M is published in month M+1).

As-of rule: a file is only usable if it was published before the snapshot. For a
snapshot on the 1st of month S we use lodgements dated before the 1st of S-1
(so for the final 1 Aug 2026 snapshot, lodgements up to 30 June 2026). Task 4 only.

Credit: NSW Fair Trading rental bond data (check the licence on nsw.gov.au/copyright).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import EXO, RAW, ensure

RAW_DIR = RAW / "bonds"
OUT = EXO / "bonds.parquet"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
BASE = "https://www.nsw.gov.au/sites/default/files/noindex"


def urls(first: str = "2023-01", last: str = "2026-06") -> list[tuple[str, str]]:
    """Monthly lodgement files from `first` to `last` (inclusive)."""
    out = []
    for p in pd.period_range(first, last, freq="M"):
        pub = (p + 1).strftime("%Y-%m")
        name = f"rentalbond_lodgements_{MONTHS[p.month - 1]}_{p.year}.xlsx"
        out.append((f"{BASE}/{pub}/{name}", name))
    return out


def download(first: str = "2023-01", last: str = "2026-06") -> None:
    import requests

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    for url, name in urls(first, last):
        dest = RAW_DIR / name
        if dest.exists():
            ok += 1
            continue
        try:
            r = requests.get(url, timeout=120, headers={"User-Agent": "microburbs-hackathon-team"})
            r.raise_for_status()
            dest.write_bytes(r.content)
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  bonds: {name} failed ({type(e).__name__}); get it from the rental bond data page")
    print(f"  bonds: {ok} monthly files in {RAW_DIR}")


def _canon(c: str) -> str | None:
    c = str(c).strip().lower()
    if "postcode" in c:
        return "postcode"
    if "lodg" in c and "date" in c:
        return "date"
    if "dwelling" in c:
        return "dwelling_type"
    if "bedroom" in c:
        return "bedrooms"
    if "rent" in c:
        return "weekly_rent"
    return None


def _read_one(p) -> pd.DataFrame:
    """Each file starts with a legend; the table starts at the row holding 'Postcode'."""
    raw = pd.read_excel(p, header=None, dtype=object)
    hdr = next(i for i, row in raw.head(40).iterrows()
               if any("postcode" in str(v).lower() for v in row.values))
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [_canon(c) for c in raw.iloc[hdr].values]
    df = df.loc[:, [c for c in df.columns if c]]
    return df.loc[:, ~df.columns.duplicated()]


def parse() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"no rental bond .xlsx in {RAW_DIR}")
    df = pd.concat([_read_one(p) for p in files], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["postcode"] = pd.to_numeric(df["postcode"], errors="coerce")
    df["weekly_rent"] = pd.to_numeric(df["weekly_rent"], errors="coerce")
    bed = df["bedrooms"].astype(str).str.strip().str.upper()
    df["bedrooms"] = pd.to_numeric(bed.replace({"B": "0", "BEDSITTER": "0", "U": None}), errors="coerce")
    df["is_flat"] = df["dwelling_type"].astype(str).str.strip().str.upper().isin(["F", "FLAT", "FLAT/UNIT"])
    df = df.dropna(subset=["date", "postcode", "weekly_rent"])
    df = df[(df.weekly_rent >= 100) & (df.weekly_rent <= 15_000)]
    ensure()
    df[["date", "postcode", "dwelling_type", "bedrooms", "weekly_rent", "is_flat"]].to_parquet(OUT)
    print(f"  bonds: {len(df):,} lodgements {df.date.min():%Y-%m} to {df.date.max():%Y-%m}, "
          f"{df.is_flat.mean():.0%} flats")
    return df


def postcode_of(flats: pd.DataFrame) -> pd.Series:
    """Postcode from the end of the rents address ('... WATERLOO 2017'), else the suburb's mode."""
    pc = pd.to_numeric(flats["address"].fillna("").str.extract(r"(\d{4})\s*$")[0], errors="coerce")
    mode = pc.groupby(flats["suburb"]).agg(lambda s: s.mode().iloc[0] if s.notna().any() else np.nan)
    return pc.fillna(flats["suburb"].map(mode))


_cache: dict = {}


def snapshot_features(flats: pd.DataFrame, s: pd.Timestamp, months: int = 6) -> pd.DataFrame:
    """Median new-lease rent for the flat's postcode x bedrooms, from files published before s."""
    if not OUT.exists():
        return pd.DataFrame(index=flats.index)
    if "df" not in _cache:
        b = pd.read_parquet(OUT)
        _cache["df"] = b[b.is_flat]
    b = _cache["df"]
    avail = (s - pd.DateOffset(months=1)).to_period("M").to_timestamp()   # 1st of S-1
    win = b[(b.date < avail) & (b.date >= avail - pd.DateOffset(months=months))]
    prev = b[(b.date < avail - pd.DateOffset(months=months)) &
             (b.date >= avail - pd.DateOffset(months=2 * months))]
    pc = postcode_of(flats)
    bed = flats["bedrooms"].clip(upper=4)
    F = pd.DataFrame(index=flats.index)
    g = win.assign(bed=win.bedrooms.clip(upper=4)).groupby(["postcode", "bed"]).weekly_rent.agg(["median", "size"])
    key = pd.MultiIndex.from_arrays([pc, bed])
    F["bond_pc_bed_lmed"] = np.log(g["median"].reindex(key).to_numpy())
    F["bond_pc_bed_n"] = g["size"].reindex(key).fillna(0).to_numpy()
    gp = win.groupby("postcode").weekly_rent.median()
    gq = prev.groupby("postcode").weekly_rent.median()
    F["bond_pc_lmed"] = np.log(pc.map(gp)).to_numpy()
    F["bond_pc_growth"] = (np.log(pc.map(gp)) - np.log(pc.map(gq))).to_numpy()
    return F
