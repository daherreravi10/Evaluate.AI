"""The decision log covers every planned column, and look-ahead columns never reach the model."""
import numpy as np
import pandas as pd

from src import config as C, rents, valuation
from src.decisions import D, LOOKAHEAD, group_of
from src.eda import signal


def test_every_planned_column_has_a_decision():
    missing = [(k, c) for k, cols in C.SCHEMA.items() for c in cols if (k, c) not in D]
    assert not missing, f"add these to src/decisions.py: {missing}"


def test_lookahead_columns_are_never_raw_features():
    assert not LOOKAHEAD & set(rents.STATIC)
    assert not LOOKAHEAD & set(valuation.STATIC)
    for col in LOOKAHEAD:
        assert D[("rents_input", col)][0] in ("not used", "derived")


def test_first_listed_age_is_blank_when_listing_is_after_the_snapshot():
    s = pd.Timestamp("2025-01-01")
    first = pd.Series(pd.to_datetime(["2020-01-01", "2025-06-01"]))
    age = (s - first.where(first < s)).dt.days / 365.25
    assert age.iloc[0] > 4.9 and np.isnan(age.iloc[1])


def test_groups_cover_the_main_features():
    for f in ["own_last_ladj", "bldg_bed_med", "mb_n", "sub_med", "near_med", "floor_level",
              "car", "latitude", "idx_12m", "osm_km_rail", "anchor_ladj", "years_since_first_listed"]:
        assert group_of(f) != "Other", f


def test_signal_measures():
    y = pd.Series(np.arange(200, dtype=float))
    assert signal(pd.Series(np.arange(200)), y)[0] > 0.99
    assert signal(pd.Series([f"id{i}" for i in range(200)]), y)[0] is None
    cat = pd.Series(["a"] * 100 + ["b"] * 100)
    assert signal(cat, y)[0] > 0.8
