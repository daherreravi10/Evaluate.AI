"""Fast checks of the rules that would cost us the task if broken.

pytest -q
"""
import numpy as np
import pandas as pd
import pytest

from src import asof, config as C
from src.features import add_keys, snapshot_features
from src.index import pairs_from_events, repeat_index
from src.loaders import building_key, floor_from_unit
from src.metrics import rent_scores, value_scores


def test_team_slug():
    assert C.team_slug("Data Wranglers") == "data-wranglers"
    assert C.team_slug("  Block  Radar 2.0! ") == "block-radar-20"


def test_value_metric_counts_exactly_10pct_and_blank_as_wrong():
    s = value_scores([100, 100, 100, 100], [110, 90.0, 111, np.nan])
    assert s["hits_within_10pct"] == 2 and s["blank"] == 1


def test_rent_metric_blank_is_worse_than_any_error():
    s = rent_scores([500, 500, 500], [500, np.nan, np.nan])
    assert s["median_abs_error"] == np.inf
    assert s["share_within_100"] == pytest.approx(1 / 3)


def test_asof_drops_later_rows():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-07-31", "2026-08-01", None])})
    out = asof.until(df, "2026-07-31")
    assert len(out) == 1 and out.date.max() == pd.Timestamp("2026-07-31")


def test_floor_from_unit():
    f = floor_from_unit(pd.Series(["315", "1204", "7", "", "G05"]))
    assert f.iloc[0] == 3 and f.iloc[1] == 12 and np.isnan(f.iloc[2]) and np.isnan(f.iloc[3])


def test_building_key():
    k = building_key(pd.Series(["Unit 315, 2-4 Powell Street", "315/2-4 POWELL STREET"]),
                     pd.Series(["Waterloo (NSW)"] * 2))
    assert k.iloc[0] == k.iloc[1] == "2-4 POWELL STREET|WATERLOO (NSW)"


def _toy():
    rng = np.random.default_rng(0)
    n = 400
    flats = pd.DataFrame({
        "gnaf_id": [f"G{i}" for i in range(n)], "bkey": [f"B{i % 20}" for i in range(n)],
        "suburb": ["S1", "S2"] * (n // 2), "mb": [f"M{i % 30}" for i in range(n)],
        "latitude": -33.9 + rng.normal(0, .01, n), "longitude": 151.2 + rng.normal(0, .01, n),
        "bedrooms": rng.integers(0, 4, n),
    })
    flats = add_keys(flats)
    ev = pd.DataFrame({"gnaf_id": rng.choice(flats.gnaf_id, 3000),
                       "date": pd.to_datetime("2018-01-01") + pd.to_timedelta(rng.integers(0, 3100, 3000), "D")})
    ev["price"] = 500 * np.exp(0.0001 * (ev.date - ev.date.min()).dt.days + rng.normal(0, .05, len(ev)))
    return flats, ev


def test_snapshot_features_never_see_the_future():
    flats, ev = _toy()
    s = pd.Timestamp("2022-01-01")
    poisoned = ev.copy()
    poisoned.loc[poisoned.date >= s, "price"] *= 100  # future prices are absurd
    F1, _ = snapshot_features(flats, ev, s)
    F2, _ = snapshot_features(flats, poisoned, s)
    pd.testing.assert_frame_equal(F1, F2)


def test_index_recovers_a_trend():
    _, ev = _toy()
    idx = repeat_index(pairs_from_events(ev), end="2026-06-30")
    # true growth 0.0001/day ~ 3.65%/yr; first-to-last over ~8 years
    assert 0.2 < idx.iloc[-1] - idx.iloc[0] < 0.4
