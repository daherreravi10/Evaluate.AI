"""NSW Valuer General bulk Property Sales Information (PSI), for Task 5.

Files: yearly zips (each holds 52 weekly zips of .DAT files) and weekly zips.
  https://valuation.property.nsw.gov.au/embed/propertySalesInformation
  legacy pattern: https://www.valuergeneral.nsw.gov.au/__psi/yearly/<YYYY>.zip
                  https://www.valuergeneral.nsw.gov.au/__psi/weekly/<YYYYMMDD>.zip
Put whatever you download in data/exo/raw/vg/ (zips, nested zips or .DAT, any mix).

"B" records, ';'-separated, current format (2001+), 1-based positions:
 1 record type  2 district  3 property id  4 sale counter  5 download datetime
 6 property name  7 unit no  8 house no  9 street  10 locality  11 postcode
 12 area  13 area type  14 contract date  15 settlement date  16 purchase price
 17 zoning  18 nature  19 primary purpose  20 strata lot  21 component code
 22 sale code  23 % interest  24 dealing no.

As-of rule (strict): a sale is only "known" at the cut-off if BOTH its contract and its
settlement are on or before it (the VG records a sale after settlement), and the weekly
file is dated on or before it. The judges' sales (1 Sep-4 Nov 2026) are in later VG files:
this filter is what keeps them out.

Licence: CC BY-NC-ND 4.0 (non-commercial; do not republish). Never commit these files.
Credit: "Contains property sales information provided under licence from the Valuer General
New South Wales."
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config as C
from .common import EXO, RAW, addr_key, ensure, norm_num, norm_street, norm_suburb, parse_value_address

RAW_DIR = RAW / "vg"
OUT = EXO / "vg_sales.parquet"
COLS = ["record_type", "district", "property_id", "sale_counter", "download_dt", "property_name",
        "unit", "house", "street", "locality", "postcode", "area", "area_type", "contract_date",
        "settlement_date", "price", "zoning", "nature", "purpose", "strata_lot", "component",
        "sale_code", "pct_interest", "dealing_no"]
LEGACY = "https://www.valuergeneral.nsw.gov.au/__psi"
PORTAL = "https://valuation.property.nsw.gov.au/embed/propertySalesInformation"


def download(years=range(2015, 2026), cutoff: str = C.VALUE_CUTOFF) -> None:
    """Yearly files for past years, weekly files for 2026 up to the cut-off."""
    import requests

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    targets = [(f"{LEGACY}/yearly/{y}.zip", f"{y}.zip") for y in years]
    mondays = pd.date_range("2026-01-05", cutoff, freq="W-MON")
    targets += [(f"{LEGACY}/weekly/{d:%Y%m%d}.zip", f"{d:%Y%m%d}.zip") for d in mondays]
    try:  # prefer the links the official portal shows, when it lists them
        page = requests.get(PORTAL, timeout=60, headers={"User-Agent": "microburbs-hackathon-team"}).text
        found = {}
        for href in re.findall(r'href="([^"]+?(\d{4}|\d{8})\.zip)"', page):
            url, stamp = href
            full = url if url.startswith("http") else requests.compat.urljoin(PORTAL, url)
            keep = (len(stamp) == 4 and int(stamp) in years) or \
                   (len(stamp) == 8 and "20260101" <= stamp <= pd.Timestamp(cutoff).strftime("%Y%m%d"))
            if keep:
                found[f"{stamp}.zip"] = full
        if found:
            targets = [(u, n) for n, u in sorted(found.items())]
            print(f"  vg: {len(targets)} files listed on the portal")
    except Exception:  # noqa: BLE001
        pass
    got = 0
    for url, name in targets:
        dest = RAW_DIR / name
        if dest.exists():
            got += 1
            continue
        try:
            r = requests.get(url, timeout=300, headers={"User-Agent": "microburbs-hackathon-team"})
            r.raise_for_status()
            if not r.content.startswith(b"PK"):
                raise ValueError("not a zip")
            dest.write_bytes(r.content)
            got += 1
        except Exception as e:  # noqa: BLE001
            print(f"  vg: {name} failed ({type(e).__name__})")
    print(f"  vg: {got}/{len(targets)} files in {RAW_DIR}. Missing ones: download from "
          f"https://valuation.property.nsw.gov.au/embed/propertySalesInformation into that folder")


def _file_date(name: str) -> pd.Timestamp | None:
    m = re.search(r"(20\d{6})", Path(name).name)
    return pd.to_datetime(m.group(1), format="%Y%m%d", errors="coerce") if m else None


def _iter_dat(blob: bytes, name: str, cutoff: pd.Timestamp):
    """Yield (name, text) of every .DAT inside a zip, recursing into nested zips."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for n in zf.namelist():
            d = _file_date(n)
            if d is not None and d > cutoff:
                continue  # weekly file published after the cut-off
            if n.lower().endswith(".zip"):
                yield from _iter_dat(zf.read(n), n, cutoff)
            elif n.lower().endswith(".dat"):
                yield n, zf.read(n).decode("latin-1")


def _records(cutoff: pd.Timestamp, postcodes: set[str]) -> list[list[str]]:
    rows = []
    for p in sorted(RAW_DIR.rglob("*")):
        texts = []
        d = _file_date(p.name)
        if d is not None and d > cutoff:
            continue
        if p.suffix.lower() == ".zip":
            texts = _iter_dat(p.read_bytes(), p.name, cutoff)
        elif p.suffix.lower() == ".dat":
            texts = [(p.name, p.read_text(encoding="latin-1"))]
        for _, text in texts:
            for line in text.splitlines():
                if not line.startswith("B;"):
                    continue
                f = line.split(";")
                if len(f) >= 24 and (not postcodes or f[10].strip() in postcodes):
                    rows.append([x.strip() for x in f[:24]])
    return rows


def parse(flats: pd.DataFrame, cutoff: str = C.VALUE_CUTOFF) -> pd.DataFrame:
    """Parse all VG files, keep strata sales known by the cut-off, match them to gnaf_id."""
    cut = pd.Timestamp(cutoff)
    pcs = set(flats["postcode"].dropna().astype(str).str.extract(r"(\d{4})")[0].dropna())
    v = pd.DataFrame(_records(cut, pcs), columns=COLS)
    if v.empty:
        raise FileNotFoundError(f"no VG B records in {RAW_DIR}")
    v["contract_date"] = pd.to_datetime(v.contract_date, format="%Y%m%d", errors="coerce")
    v["settlement_date"] = pd.to_datetime(v.settlement_date, format="%Y%m%d", errors="coerce")
    v["price"] = pd.to_numeric(v.price, errors="coerce")
    v["pct_interest"] = pd.to_numeric(v.pct_interest, errors="coerce").fillna(100)
    n0 = len(v)
    v = v[(v.unit != "") & (v.price >= 50_000) & (v.pct_interest >= 100)]
    v = v[(v.contract_date <= cut) & (v.settlement_date <= cut)]
    v = v.drop_duplicates(["property_id", "sale_counter", "contract_date", "price"])

    a = parse_value_address(flats["address"], flats["unit_number"])
    fk = pd.Series(flats["gnaf_id"].to_numpy(),
                   index=addr_key(a.unit, a.house, a.street, norm_suburb(flats["suburb"])))
    fk = fk[~fk.index.duplicated(keep=False)]
    vk = addr_key(norm_num(v.unit), norm_num(v.house), norm_street(v.street), norm_suburb(v.locality))
    v["gnaf_id"] = pd.Series(vk).map(fk).to_numpy()
    matched = v.gnaf_id.notna()
    print(f"  vg: {n0:,} City-postcode records -> {len(v):,} strata sales known by {cutoff}; "
          f"{matched.mean():.0%} matched to a gnaf_id")
    out = v[matched].rename(columns={"contract_date": "date"})[
        ["gnaf_id", "date", "settlement_date", "price", "property_id", "strata_lot"]]
    ensure()
    out.to_parquet(OUT)
    return out


def merge(sold: pd.DataFrame, cutoff: str = C.VALUE_CUTOFF) -> pd.DataFrame:
    """Add VG sales the supplied file lacks (same flat, price within 2%, 120 days = same sale)."""
    if not OUT.exists():
        return sold
    v = pd.read_parquet(OUT)
    v = v[(v.date <= pd.Timestamp(cutoff)) & (v.settlement_date <= pd.Timestamp(cutoff))]
    m = v.reset_index().merge(sold[["gnaf_id", "date", "price"]], on="gnaf_id", how="left",
                              suffixes=("", "_s"))
    same = ((m.date - m.date_s).abs().dt.days <= 120) & ((m.price / m.price_s - 1).abs() <= 0.02)
    dup_idx = set(m.loc[same, "index"])
    new = v[~v.index.isin(dup_idx)].assign(type="Sold")[["gnaf_id", "date", "price", "type"]]
    print(f"  vg: {len(new):,} extra sales merged ({len(dup_idx):,} already in the supplied file)")
    return pd.concat([sold, new], ignore_index=True)
