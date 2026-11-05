"""ABS Census 2021, by SA1 (about 400 people), joined to each flat through its Mesh Block.

Files (put them in data/exo/raw/census/, or let scripts/fetch_exo.py try):
- MB_2021_AUST.xlsx  ASGS Ed. 3 allocation file (MB_CODE_2021 -> SA1_CODE_2021)
  https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/allocation-files/MB_2021_AUST.xlsx
- 2021Census_G02_NSW_SA1.csv  from the 2021 General Community Profile DataPack,
  SA1, New South Wales (https://www.abs.gov.au/census/find-census-data/datapacks)

Census night was 10 Aug 2021: well before both cut-offs.
Credit: Australian Bureau of Statistics, © Commonwealth of Australia, CC BY 4.0.
"""
from __future__ import annotations

import zipfile

import pandas as pd

from .common import EXO, RAW, ensure

RAW_DIR = RAW / "census"
OUT = EXO / "census_sa1.parquet"
MB_URL = ("https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/"
          "edition-3-july-2021-june-2026/access-and-downloads/allocation-files/MB_2021_AUST.xlsx")
# The DataPack link is not published as text; this is the usual pattern. If it fails,
# download "2021 GCP, SA1, New South Wales" by hand into data/exo/raw/census/.
GCP_URL = "https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SA1_for_NSW_short-header.zip"
G02 = ["Median_age_persons", "Median_mortgage_repay_monthly", "Median_tot_prsnl_inc_weekly",
       "Median_rent_weekly", "Median_tot_fam_inc_weekly", "Average_num_psns_per_bedroom",
       "Median_tot_hhd_inc_weekly", "Average_household_size"]


def download() -> None:
    import requests

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for url, name in [(MB_URL, "MB_2021_AUST.xlsx"), (GCP_URL, "GCP_SA1_NSW.zip")]:
        dest = RAW_DIR / name
        if dest.exists():
            print(f"  census: {name} already here")
            continue
        try:
            r = requests.get(url, timeout=600, headers={"User-Agent": "microburbs-hackathon-team"})
            r.raise_for_status()
            dest.write_bytes(r.content)
            print(f"  census: {name} {len(r.content) / 1e6:.0f} MB")
        except Exception as e:  # noqa: BLE001
            print(f"  census: could not download {name} ({e}). Download it by hand into {RAW_DIR}")


def _g02() -> pd.DataFrame:
    for p in sorted(RAW_DIR.glob("*G02*SA1*.csv")):
        return pd.read_csv(p, dtype={"SA1_CODE_2021": str})
    for z in sorted(RAW_DIR.glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if "G02" in n and "SA1" in n and n.endswith(".csv") and "G02A" not in n and "G02B" not in n:
                    with zf.open(n) as f:
                        return pd.read_csv(f, dtype={"SA1_CODE_2021": str})
    raise FileNotFoundError(f"no 2021Census_G02_NSW_SA1.csv in {RAW_DIR}")


def _mb() -> pd.DataFrame:
    for p in sorted(RAW_DIR.glob("MB_2021_AUST*.csv")):
        return pd.read_csv(p, dtype=str, usecols=["MB_CODE_2021", "SA1_CODE_2021", "STATE_CODE_2021"])
    p = RAW_DIR / "MB_2021_AUST.xlsx"
    if not p.exists():
        raise FileNotFoundError(f"no MB_2021_AUST.xlsx in {RAW_DIR}")
    from openpyxl import load_workbook

    ws = load_workbook(p, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    head = [str(h) for h in next(rows)]
    i_mb, i_sa1, i_st = head.index("MB_CODE_2021"), head.index("SA1_CODE_2021"), head.index("STATE_CODE_2021")
    keep = [(str(r[i_mb]), str(r[i_sa1])) for r in rows if str(r[i_st]) == "1"]  # NSW only
    return pd.DataFrame(keep, columns=["MB_CODE_2021", "SA1_CODE_2021"])


def parse() -> pd.DataFrame:
    g = _g02()
    g.columns = [c.strip() for c in g.columns]
    have = [c for c in G02 if c in g.columns]
    mb = _mb()
    out = mb.merge(g[["SA1_CODE_2021"] + have], on="SA1_CODE_2021", how="inner")
    out = out.rename(columns={"MB_CODE_2021": "mb", "SA1_CODE_2021": "sa1"})
    out = out.rename(columns={c: "cen_" + c.lower() for c in have})
    ensure()
    out.to_parquet(OUT)
    print(f"  census: {len(out):,} mesh blocks with SA1 medians ({len(have)} fields)")
    return out


def features(flats: pd.DataFrame) -> pd.DataFrame:
    if not OUT.exists():
        return pd.DataFrame(index=flats.index)
    c = pd.read_parquet(OUT)
    m = flats[["mb"]].astype(str).merge(c, on="mb", how="left")
    m.index = flats.index
    F = m.drop(columns=["mb", "sa1"])
    for col in F.columns:
        F[col] = pd.to_numeric(F[col], errors="coerce").where(lambda x: x > 0)  # 0 = suppressed
    return F
