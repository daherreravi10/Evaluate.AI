"""Synthetic outside files in the REAL raw formats, so the parsers and the pipeline
wiring can be tested before Saturday. Run after scripts/make_mock_data.py.

- Overpass JSON (POIs with centers, roads with geometry)
- ABS MB_2021_AUST.xlsx + a DataPack-style zip holding 2021Census_G02_NSW_SA1.csv
- NSW rental bond monthly .xlsx files with a legend block above the table
- NSW VG yearly zip -> nested weekly zips -> .DAT files with 24-field B records,
  including sales AFTER the cut-off (and the mock judging sales) to prove the filter

python scripts/make_mock_exo.py
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C  # noqa: E402
from src.exo import bonds, census, osm, places, vg  # noqa: E402
from src.exo.common import BBOX, RAW, ensure  # noqa: E402
from src.loaders import load  # noqa: E402

rng = np.random.default_rng(42)


def mock_osm() -> None:
    s, w, n, e = BBOX
    els, i = [], 0

    def pt(tags, center=False):
        nonlocal i
        i += 1
        lat, lon = rng.uniform(s, n), rng.uniform(w, e)
        el = {"type": "way" if center else "node", "id": i, "tags": tags}
        el.update({"center": {"lat": lat, "lon": lon}} if center else {"lat": lat, "lon": lon})
        els.append(el)

    for _ in range(14):
        pt({"railway": "station", "name": "Mock Station", "train": "yes"})
    for _ in range(5):
        pt({"railway": "station", "station": "subway", "name": "Mock Metro"})
    for _ in range(20):
        pt({"railway": "tram_stop", "name": "Mock Light Rail"})
    for _ in range(60):
        pt({"shop": "supermarket", "name": "Mock Mart"}, center=rng.random() < .5)
    for _ in range(80):
        pt({"leisure": "park"}, center=True)
    for _ in range(40):
        pt({"amenity": "school"}, center=True)
    (osm.RAW_POI).write_text(json.dumps({"elements": els}), encoding="utf-8")
    roads = []
    for k in range(12):
        lat0, lon0 = rng.uniform(s, n), rng.uniform(w, e)
        ang = rng.uniform(0, np.pi)
        geom = [{"lat": lat0 + t * 0.002 * np.sin(ang), "lon": lon0 + t * 0.002 * np.cos(ang)}
                for t in range(-25, 26)]
        roads.append({"type": "way", "id": 10_000 + k, "tags": {"highway": "primary"}, "geometry": geom})
    osm.RAW_ROADS.write_text(json.dumps({"elements": roads}), encoding="utf-8")
    print(f"osm: {len(els)} POIs, {len(roads)} roads")


def mock_census() -> None:
    d = census.RAW_DIR
    d.mkdir(parents=True, exist_ok=True)
    rin, vin = load("rents_input"), load("value_input")
    lea = load("rents_leases")
    lea = lea[(lea.date >= "2021-01-01") & (lea.date < "2022-01-01")].merge(rin[["gnaf_id", "mb"]], on="gnaf_id")
    mbs = pd.Series(pd.concat([rin.mb, vin.mb]).dropna().unique())
    sa1 = {m: f"1{(int(m) // 4_000_000) % 10**10:010d}" for m in mbs}   # several MBs per SA1
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("MB_2021_AUST")
    ws.append(["MB_CODE_2021", "MB_CATEGORY_2021", "CHANGE_FLAG_2021", "CHANGE_LABEL_2021",
               "SA1_CODE_2021", "SA2_CODE_2021", "SA2_NAME_2021", "SA3_CODE_2021", "SA3_NAME_2021",
               "SA4_CODE_2021", "SA4_NAME_2021", "GCCSA_CODE_2021", "GCCSA_NAME_2021",
               "STATE_CODE_2021", "STATE_NAME_2021", "AUS_CODE_2021", "AUS_NAME_2021",
               "AREA_ALBERS_SQKM", "ASGS_LOCI_URI_2021"])
    for m, s in sa1.items():
        ws.append([m, "Residential", 0, "No change", s, s[:9], "Mock", s[:5], "Mock", s[:3], "Mock",
                   "1GSYD", "Greater Sydney", "1", "New South Wales", "AUS", "Australia", 0.01, ""])
    ws.append(["20000000000", "Residential", 0, "", "20000000000", "", "", "", "", "", "", "", "",
               "2", "Victoria", "AUS", "Australia", 0.01, ""])                     # non-NSW row
    wb.save(d / "MB_2021_AUST.xlsx")
    med = lea.assign(sa1=lea.mb.map(sa1)).groupby("sa1").price.median()
    g = pd.DataFrame({"SA1_CODE_2021": sorted(set(sa1.values()))})
    g["Median_rent_weekly"] = g.SA1_CODE_2021.map(med).fillna(med.median()) * rng.normal(1, .05, len(g))
    g["Median_rent_weekly"] = g.Median_rent_weekly.round()
    g["Median_tot_hhd_inc_weekly"] = (g.Median_rent_weekly * rng.uniform(2.6, 3.4, len(g))).round()
    g["Median_age_persons"] = rng.integers(26, 45, len(g))
    g["Median_mortgage_repay_monthly"] = rng.integers(1800, 4500, len(g))
    g["Median_tot_prsnl_inc_weekly"] = (g.Median_tot_hhd_inc_weekly / 1.8).round()
    g["Median_tot_fam_inc_weekly"] = (g.Median_tot_hhd_inc_weekly * 1.1).round()
    g["Average_num_psns_per_bedroom"] = rng.uniform(0.9, 1.4, len(g)).round(1)
    g["Average_household_size"] = rng.uniform(1.6, 2.6, len(g)).round(1)
    g.loc[g.sample(frac=0.03, random_state=1).index, "Median_rent_weekly"] = 0   # suppressed cells
    buf = io.StringIO()
    g.to_csv(buf, index=False)
    with zipfile.ZipFile(d / "GCP_SA1_NSW.zip", "w") as z:
        z.writestr("2021 Census GCP Statistical Area 1 for NSW/2021Census_G02_NSW_SA1.csv", buf.getvalue())
        z.writestr("2021 Census GCP Statistical Area 1 for NSW/2021Census_G02A_NSW_SA1.csv", "decoy\n")
    print(f"census: {len(sa1):,} mesh blocks, {len(g):,} SA1s")


def mock_bonds() -> None:
    d = bonds.RAW_DIR
    d.mkdir(parents=True, exist_ok=True)
    rin = load("rents_input")
    lea = load("rents_leases").merge(rin[["gnaf_id", "address"]], on="gnaf_id")
    lea["postcode"] = lea.address.str.extract(r"(\d{4})\s*$")[0]
    n = 0
    for p in pd.period_range("2023-01", "2026-06", freq="M"):
        m = lea[lea.date.dt.to_period("M") == p]
        m = m.sample(frac=0.7, random_state=p.month)
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("Lodgements")
        ws.append(["Rental Bond Lodgements Data"])
        ws.append(["Legend: Dwelling Type F = Flat/Unit, H = House, T = Terrace/Townhouse, O = Other, U = Unknown"])
        ws.append(["Bedrooms: U = Unknown"])
        ws.append([])
        ws.append(["Lodgement Date", "Postcode", "Dwelling Type", "Bedrooms", "Weekly Rent"])
        for r in m.itertuples():
            ws.append([r.date.strftime("%d/%m/%Y"), int(r.postcode), "F",
                       "U" if rng.random() < .03 else int(r.bedrooms),
                       float(round(r.price * rng.normal(0.97, 0.04)))])
            n += 1
        for _ in range(30):
            ws.append([f"15/{p.month:02d}/{p.year}", 2017, "H", 3, 1400.0])
        name = f"rentalbond_lodgements_{bonds.MONTHS[p.month - 1]}_{p.year}.xlsx"
        wb.save(d / name)
    print(f"bonds: {n:,} flat lodgements in 42 monthly files")


def _b_record(r, district="1", counter="1") -> str:
    f = ["B", district, str(r["pid"]), counter, "20260101 01:23", "", r["unit"], r["house"], r["street"],
         r["locality"], r["postcode"], "", "", r["contract"], r["settle"], str(int(r["price"])), "R", "3",
         "RESIDENCE", r["unit"], "", "", "", "AK123456"]
    return ";".join(f) + ";"


def mock_vg() -> None:
    d = vg.RAW_DIR
    d.mkdir(parents=True, exist_ok=True)
    vin = load("value_input").set_index("gnaf_id")
    sold = load("value_sales")
    sold = sold[sold["type"].astype(str).str.lower().str.startswith("sold") & sold.gnaf_id.isin(vin.index)]
    hidden = pd.read_csv(C.MOCK_HIDDEN / "sales.csv", dtype={"gnaf_id": str}, parse_dates=["date"])
    dup = sold.sample(frac=0.6, random_state=2)[["gnaf_id", "date", "price"]]            # already known
    extra = sold.sample(25_000, random_state=3)[["gnaf_id", "date", "price"]].copy()     # VG-only sales
    shift = rng.integers(-900, -60, len(extra))
    extra["date"] = extra.date + pd.to_timedelta(shift, "D")
    extra["price"] = (extra.price * np.exp(0.045 * shift / 365 + rng.normal(0, 0.06, len(extra)))).round(-3)
    late = sold.sample(2_000, random_state=4)[["gnaf_id", "price"]].assign(
        date=pd.to_datetime("2026-09-01") + pd.to_timedelta(rng.integers(0, 60, 2_000), "D"))
    allv = pd.concat([dup.assign(src="dup"), extra.assign(src="extra"),
                      late.assign(src="late"), hidden.assign(src="hidden")], ignore_index=True)
    allv = allv[allv.date >= "2015-01-01"]
    j = vin.loc[allv.gnaf_id]
    rest = j.address.str.replace(r"^[^,]*,\s*", "", regex=True)
    hs = rest.str.extract(r"^(\S+)\s+(.*)$")
    street = hs[1].str.upper().str.replace(r"\bSTREET$", "ST", regex=True).str.replace(r"\bROAD$", "RD", regex=True)
    rec = pd.DataFrame({
        "pid": rng.integers(1_000_000, 9_999_999, len(allv)), "unit": j.unit_number.fillna("").astype(str).str.replace(r"\.0$", "", regex=True).to_numpy(),
        "house": hs[0].to_numpy(), "street": street.to_numpy(),
        "locality": j.suburb.str.replace(" (NSW)", "", regex=False).str.upper().to_numpy(),
        "postcode": j.postcode.astype(str).to_numpy(),
        "contract": allv.date.dt.strftime("%Y%m%d").to_numpy(),
        "settle": (allv.date + pd.to_timedelta(rng.integers(30, 70, len(allv)), "D")).dt.strftime("%Y%m%d").to_numpy(),
        "price": allv.price.to_numpy(), "week": (allv.date + pd.Timedelta(days=75)).dt.to_period("W-SUN").dt.end_time.dt.normalize().to_numpy(),
    })
    rec = rec[rec.unit != ""]
    rec["year"] = pd.to_datetime(rec.week).dt.year
    for y, gy in rec.groupby("year"):
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as zo:
            for wk, gw in gy.groupby("week"):
                monday = (pd.Timestamp(wk) + pd.Timedelta(days=1)).strftime("%Y%m%d")
                inner = io.BytesIO()
                with zipfile.ZipFile(inner, "w") as zi:
                    body = "A;HEADER;\n" + "\n".join(_b_record(r) for _, r in gw.iterrows()) + "\nZ;TRAILER;\n"
                    zi.writestr(f"001_SALES_DATA_NNME_{monday}.DAT", body)
                zo.writestr(f"{monday}.zip", inner.getvalue())
        if y <= 2025:
            (d / f"{y}.zip").write_bytes(outer.getvalue())
        else:                                   # 2026: weekly files only, like the real site
            with zipfile.ZipFile(io.BytesIO(outer.getvalue())) as zo:
                for n in zo.namelist():
                    (d / n).write_bytes(zo.read(n))
    print(f"vg: {len(rec):,} B records "
          f"({(allv.src == 'extra').sum():,} VG-only, {(allv.src == 'dup').sum():,} duplicates, "
          f"{(allv.src.isin(['late', 'hidden'])).sum():,} after the cut-off)")


def mock_places() -> None:
    s, w, n, e = BBOX
    els, i = [], 0

    def add(tags, area=False):
        nonlocal i
        i += 1
        lat, lon = rng.uniform(s, n), rng.uniform(w, e)
        el = {"type": "way" if area else "node", "id": 50_000 + i, "tags": tags}
        el.update({"center": {"lat": lat, "lon": lon}} if area else {"lat": lat, "lon": lon})
        els.append(el)

    names = ["Central", "Redfern", "Town Hall", "Wynyard", "Martin Place", "Kings Cross", "Green Square",
             "Erskineville", "St Peters", "Museum", "St James", "Circular Quay", "Edgecliff", "Newtown"]
    for nm in names:
        add({"railway": "station", "train": "yes", "name": f"{nm} (practice)"})
    for nm in ["Waterloo", "Barangaroo", "Gadigal", "Crows Nest"]:
        add({"railway": "station", "station": "subway", "name": f"{nm} Metro (practice)"})
    for k in range(20):
        add({"railway": "tram_stop", "name": f"Light rail stop {k + 1} (practice)"})
    for k in range(6):
        add({"amenity": "hospital", "name": f"Hospital {k + 1} (practice)"}, area=True)
    for k in range(8):
        add({"shop": "mall", "name": f"Shopping centre {k + 1} (practice)"}, area=True)
    for k in range(50):
        add({"shop": "supermarket", "name": f"Supermarket {k + 1}"}, area=k % 2 == 0)
    for k in range(5):
        add({"amenity": "ferry_terminal", "name": f"Wharf {k + 1} (practice)"})
    for k in range(60):
        add({"leisure": "park", "name": f"Park {k + 1}"}, area=True)
    for k in range(30):
        add({"amenity": "school", "name": f"School {k + 1}"}, area=True)
    for k in range(12):
        add({"building": "construction", "construction": rng.choice(["apartments", "office", "hotel"]),
             "name": f"Project {k + 1} (practice)"}, area=True)
    add({"railway": "construction", "construction": "subway", "name": "New metro line (practice)"}, area=True)
    places.RAW_POI.write_text(json.dumps({"elements": els}), encoding="utf-8")
    stops = [{"type": "node", "id": 900_000 + k, "lat": rng.uniform(s, n), "lon": rng.uniform(w, e),
              "tags": {"highway": "bus_stop", "name": f"Stop {k + 1}"}} for k in range(500)]
    rels = []
    for k, ref in enumerate(["301", "303", "309", "310", "343", "352", "370", "380", "389", "M50", "X39", "422"]):
        mem = rng.choice(len(stops), 60, replace=False)
        rels.append({"type": "relation", "id": 7_000 + k, "tags": {"route": "bus", "ref": ref},
                     "members": [{"type": "node", "ref": stops[j]["id"], "role": "platform"} for j in mem]})
    places.RAW_BUS.write_text(json.dumps({"elements": rels + stops}), encoding="utf-8")
    print(f"places: {len(els)} places, {len(stops)} bus stops, {len(rels)} routes")


if __name__ == "__main__":
    ensure()
    RAW.mkdir(parents=True, exist_ok=True)
    mock_osm()
    mock_places()
    mock_census()
    mock_bonds()
    mock_vg()
    (RAW / "MOCK_EXO_DO_NOT_USE_FOR_PITCH.txt").write_text("synthetic outside files\n", encoding="utf-8")
