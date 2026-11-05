"""Outside-data parsers on tiny files in the real formats, and their as-of rules."""
import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest
from openpyxl import Workbook

from src import config as C
from src.exo import bonds, census, osm, vg
from src.exo.common import addr_key, norm_street, norm_suburb, parse_value_address


def test_street_and_address_normalisation():
    a = norm_street(pd.Series(["Powell Street", "POWELL ST", "Bay  Road", "Sam Sing Lane"]))
    assert list(a) == ["POWELL ST", "POWELL ST", "BAY RD", "SAM SING LANE"]
    p = parse_value_address(pd.Series(["Unit 315, 2-4 Powell Street"]), pd.Series(["315"]))
    assert (p.unit[0], p.house[0], p.street[0]) == ("315", "2-4", "POWELL ST")
    assert norm_suburb(pd.Series(["Waterloo (NSW)"]))[0] == "WATERLOO"


def test_osm_query_is_dated_and_parse_kinds(tmp_path, monkeypatch):
    q = osm.queries()
    assert f'[date:"{C.RENT_CUTOFF}T23:59:59Z"]' in q["poi"] and "[date:" in q["roads"]
    monkeypatch.setattr(osm, "RAW_POI", tmp_path / "p.json")
    monkeypatch.setattr(osm, "RAW_ROADS", tmp_path / "r.json")
    monkeypatch.setattr(osm, "OUT", tmp_path / "o.parquet")
    monkeypatch.setattr("src.exo.common.EXO", tmp_path)
    (tmp_path / "p.json").write_text(json.dumps({"elements": [
        {"type": "node", "lat": -33.88, "lon": 151.2, "tags": {"railway": "station", "train": "yes"}},
        {"type": "node", "lat": -33.89, "lon": 151.2, "tags": {"railway": "tram_stop"}},
        {"type": "way", "center": {"lat": -33.9, "lon": 151.21}, "tags": {"shop": "supermarket"}}]}))
    (tmp_path / "r.json").write_text(json.dumps({"elements": [
        {"type": "way", "geometry": [{"lat": -33.88, "lon": 151.19}, {"lat": -33.881, "lon": 151.191}]}]}))
    pts = osm.parse()
    assert set(pts.kind) == {"train", "light_rail", "supermarket", "main_road"}
    F = osm.features(pd.DataFrame({"latitude": [-33.88], "longitude": [151.2]}))
    assert F.osm_km_rail.iloc[0] < 0.01 and F.osm_km_light_rail.iloc[0] == pytest.approx(1.11, abs=0.05)


def _dat(records):
    head = "A;HEADER;\n"
    return head + "\n".join(";".join(r) + ";" for r in records) + "\nZ;END;\n"


def _rec(unit, house, street, loc, pc, contract, settle, price):
    f = [""] * 24
    f[0], f[2], f[3], f[6], f[7], f[8], f[9], f[10] = "B", "123", "1", unit, house, street, loc, pc
    f[13], f[14], f[15], f[22] = contract, settle, str(price), ""
    return f


def test_vg_nested_zips_strict_asof_and_matching(tmp_path, monkeypatch):
    monkeypatch.setattr(vg, "RAW_DIR", tmp_path / "vg")
    monkeypatch.setattr(vg, "OUT", tmp_path / "vg.parquet")
    monkeypatch.setattr("src.exo.vg.ensure", lambda: None)
    (tmp_path / "vg").mkdir()
    ok = _rec("315", "2-4", "POWELL ST", "WATERLOO", "2017", "20260701", "20260805", 800000)
    settles_late = _rec("316", "2-4", "POWELL ST", "WATERLOO", "2017", "20260820", "20260915", 900000)
    judged = _rec("317", "2-4", "POWELL ST", "WATERLOO", "2017", "20260905", "20261010", 700000)
    inner_ok, inner_late = io.BytesIO(), io.BytesIO()
    with zipfile.ZipFile(inner_ok, "w") as z:
        z.writestr("001_SALES_DATA_NNME_20260810.DAT", _dat([ok, settles_late]))
    with zipfile.ZipFile(inner_late, "w") as z:
        z.writestr("001_SALES_DATA_NNME_20261012.DAT", _dat([judged]))
    (tmp_path / "vg" / "20260810.zip").write_bytes(inner_ok.getvalue())
    (tmp_path / "vg" / "20261012.zip").write_bytes(inner_late.getvalue())
    flats = pd.DataFrame({"gnaf_id": ["G315", "G316", "G317"],
                          "address": ["Unit 315, 2-4 Powell Street", "Unit 316, 2-4 Powell Street",
                                      "Unit 317, 2-4 Powell Street"],
                          "unit_number": ["315", "316", "317"], "suburb": ["Waterloo (NSW)"] * 3,
                          "postcode": ["2017"] * 3})
    out = vg.parse(flats, cutoff="2026-08-31")
    assert list(out.gnaf_id) == ["G315"]          # late settlement and judging-period sale excluded
    sold = pd.DataFrame({"gnaf_id": ["G315"], "date": [pd.Timestamp("2026-07-02")],
                         "price": [801000], "type": ["Sold"]})
    assert len(vg.merge(sold)) == 1                # same sale is not added twice


def _bond_xlsx(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Rental Bond Lodgements Data"])
    ws.append(["Legend: F = Flat/Unit"])
    ws.append([])
    ws.append(["Lodgement Date", "Postcode", "Dwelling Type", "Bedrooms", "Weekly Rent"])
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_bonds_parse_and_publication_lag(tmp_path, monkeypatch):
    monkeypatch.setattr(bonds, "RAW_DIR", tmp_path)
    monkeypatch.setattr(bonds, "OUT", tmp_path / "b.parquet")
    monkeypatch.setattr("src.exo.bonds.ensure", lambda: None)
    bonds._cache.clear()
    _bond_xlsx(tmp_path / "rentalbond_lodgements_may_2026.xlsx",
               [["15/05/2026", 2017, "F", 1, 700], ["16/05/2026", 2017, "F", 1, 720],
                ["16/05/2026", 2017, "H", 3, 1500], ["17/05/2026", 2017, "F", "U", 650]])
    _bond_xlsx(tmp_path / "rentalbond_lodgements_july_2026.xlsx", [["15/07/2026", 2017, "F", 1, 5000]])
    df = bonds.parse()
    assert df.is_flat.sum() == 4 and df.bedrooms.isna().sum() == 1
    flats = pd.DataFrame({"address": ["UNIT 1, 2 X ST WATERLOO 2017"], "suburb": ["Waterloo (NSW)"],
                          "bedrooms": [1]})
    F = bonds.snapshot_features(flats, pd.Timestamp("2026-08-01"))
    # July lodgements are published in August: not available at the 1 Aug snapshot
    assert np.exp(F.bond_pc_bed_lmed.iloc[0]) == pytest.approx(710)
    assert bonds.urls("2026-06", "2026-06")[0][0].endswith("2026-07/rentalbond_lodgements_june_2026.xlsx")


def test_census_join_and_suppressed_cells(tmp_path, monkeypatch):
    monkeypatch.setattr(census, "RAW_DIR", tmp_path)
    monkeypatch.setattr(census, "OUT", tmp_path / "c.parquet")
    monkeypatch.setattr("src.exo.census.ensure", lambda: None)
    wb = Workbook()
    ws = wb.active
    ws.append(["MB_CODE_2021", "SA1_CODE_2021", "STATE_CODE_2021"])
    ws.append(["11205258900", "11703133401", "1"])
    ws.append(["11205258901", "11703133402", "1"])
    ws.append(["20000000000", "20000000000", "2"])
    wb.save(tmp_path / "MB_2021_AUST.xlsx")
    g02 = "SA1_CODE_2021,Median_rent_weekly,Median_tot_hhd_inc_weekly\n11703133401,650,2400\n11703133402,0,2000\n"
    with zipfile.ZipFile(tmp_path / "gcp.zip", "w") as z:
        z.writestr("x/2021Census_G02A_NSW_SA1.csv", "decoy\n")
        z.writestr("x/2021Census_G02_NSW_SA1.csv", g02)
    census.parse()
    F = census.features(pd.DataFrame({"mb": ["11205258900", "11205258901", "999"]}))
    assert F.cen_median_rent_weekly.iloc[0] == 650
    assert np.isnan(F.cen_median_rent_weekly.iloc[1]) and np.isnan(F.cen_median_tot_hhd_inc_weekly.iloc[2])


def test_addr_key_shapes():
    k = addr_key(["1"], ["2-4"], ["POWELL ST"], ["WATERLOO"])
    assert k[0] == "1|2-4|POWELL ST|WATERLOO"
