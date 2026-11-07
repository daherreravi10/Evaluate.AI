"""App helpers: result order, non-home filter, similar flats, and the sales-history cut-off."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import logic as L  # noqa: E402

LAT, LON = -33.8702, 151.2226
M = 1 / 111_000  # degrees of latitude per metre


def flat(gid, bkey="B1|X", beds=2, baths=1, car=1, w=1000.0, wo=970.0, value=1_500_000, floor=9, north_m=0,
         suburb="Potts Point"):
    return dict(gnaf_id=gid, label=f"Unit {gid}, 1 Test Street", suburb=suburb, lat=LAT + north_m * M, lon=LON,
                beds=beds, baths=baths, r_with_car=w, r_without_car=wo, r_car_space=car, r_floor_level=floor,
                r_bkey=bkey, v_bkey=bkey, v_value=value, v_car_spaces=car, v_floor=floor)


def test_unit_sort_is_numeric_within_a_building():
    labels = ["Unit 10, 1 A St", "Unit 2, 1 A St", "Unit 1, 2 B St", "Unit 9, 1 A St"]
    assert sorted(labels, key=L.unit_sort_key) == ["Unit 2, 1 A St", "Unit 9, 1 A St", "Unit 10, 1 A St",
                                                   "Unit 1, 2 B St"]


def test_car_spaces_and_storage_are_not_homes():
    a = pd.Series(["CARSPACE 180, 73 VICTORIA STREET", "Unit 906, 73 Victoria Street", "STORE 4, 1 A ST",
                   "Storage 2, 1 A St", "SHOP 4, 95 VICTORIA STREET", None])
    assert L.is_home(a).tolist() == [False, True, False, False, True, True]


def test_similar_flats_rent_mix_and_like_for_like():
    f = pd.Series(flat("me", w=1126, wo=1095))
    others = pd.DataFrame([
        flat("same1", w=1121, wo=1088, floor=10),                    # near-identical, same building
        flat("cheap", w=1025, wo=992, floor=9),                      # $100 cheaper, same building
        flat("nocar", car=0, w=1001, wo=970, floor=10),              # no car space: compare without car
        flat("other", bkey="B2|X", w=1136, wo=1100, baths=2, north_m=70),
        flat("far", bkey="B3|X", w=1120, wo=1090, north_m=900),      # outside 400 m
        flat("3bed", beds=3, w=1400, wo=1350),                       # different bedrooms
    ])
    df = pd.concat([pd.DataFrame([f]), others], ignore_index=True)
    s = L.similar_flats(df, f, "rent")
    ids = s.gnaf_id.tolist()
    assert "me" not in ids and "far" not in ids and "3bed" not in ids
    assert {"same1", "cheap", "other"} <= set(ids)
    nocar = s[s.gnaf_id == "nocar"]
    assert nocar["compare"].iloc[0] == "without" and nocar["diff"].iloc[0] == 970 - 1095
    assert s[s.gnaf_id == "cheap"]["diff"].iloc[0] == -101
    assert s.same_building.iloc[0]                                    # same building listed first


def test_similar_flats_caps_same_building():
    f = pd.Series(flat("me"))
    rows = [flat(f"s{i}", w=1000 + i) for i in range(8)] + [flat("o1", bkey="B2|X", north_m=50)]
    df = pd.concat([pd.DataFrame([f]), pd.DataFrame(rows)], ignore_index=True)
    s = L.similar_flats(df, f, "rent", n=5, max_same_building=3)
    assert s.same_building.sum() <= 3 and "o1" in s.gnaf_id.tolist()


def test_similar_flats_needs_bedrooms():
    f = pd.Series(flat("me", beds=np.nan))
    df = pd.DataFrame([flat("a")])
    assert L.similar_flats(df, f, "sale").empty


def test_similar_notes_wording():
    f = pd.Series(flat("me", w=1126, wo=1095, floor=9))
    row = pd.Series({**flat("x", w=1025, floor=17, baths=2, suburb="Woolloomooloo", bkey="B2|X"),
                     "diff": -101.0, "dist_m": 68.0, "same_building": False, "compare": "with"})
    n = L.similar_notes(row, f, "rent")
    assert n["where"] == "70 m away" and n["diff"] == "$101 a week less" and n["tone"] == "lo"
    assert "8 floors higher (17)" in n["differs"] and "2 bathrooms (+1)" in n["differs"]
    assert "Woolloomooloo" in n["differs"] and n["alike"] == "2 bed · 2 bath · car space"
    same = pd.Series({**flat("y"), "diff": 3.0, "dist_m": 0.0, "same_building": True, "compare": "with"})
    assert L.similar_notes(same, f, "rent")["diff"] == "About the same"
    sale = pd.Series({**flat("z", car=2), "diff": -230_185.0, "dist_m": 38.0, "same_building": False,
                      "compare": "value"})
    ns = L.similar_notes(sale, f, "sale")
    assert ns["diff"] == "$230,000 less" and "2 car spaces (+1)" in ns["differs"]


def test_sales_history_never_shows_events_after_the_cutoff():
    sales = pd.DataFrame({
        "gnaf_id": ["me", "me", "n1", "n1", "n2", "elsewhere"],
        "date": pd.to_datetime(["2017-04-01", "2026-09-15", "2026-02-02", "2026-02-28", "2026-08-31", "2026-03-01"]),
        "price": [1_475_000, 1_900_000, 1_770_000, 1_770_000, 2_000_000, 900_000],
        "type": ["Sold", "Sold", "For Sale", "Sold", "Sold", "Sold"],
    })
    bkeys = pd.Series({"me": "B1", "n1": "B1", "n2": "B1", "elsewhere": "B9"})
    own, bld = L.sales_history(sales, bkeys, "me", "B1", "2026-08-31")
    assert own.date.max() <= pd.Timestamp("2026-08-31") and len(own) == 1
    assert bld.date.max() <= pd.Timestamp("2026-08-31")
    assert set(bld.gnaf_id) == {"n2", "n1", "me"} and (bld.type == "Sold").all()
    assert bld.set_index("gnaf_id").loc["n1", "asked"] == 1_770_000
    assert np.isnan(bld.set_index("gnaf_id").loc["n2", "asked"])
