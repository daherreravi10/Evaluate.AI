"""Turn whatever outside files are in data/exo/raw/ into data/exo/*.parquet, and give
the pipelines one call for the static features.

python -m src.exo.build
"""
from __future__ import annotations

import pandas as pd

from . import bonds, census, enabled, osm, vg
from ..loaders import load


def build() -> dict:
    status = {}
    for name, fn in [("osm", osm.parse), ("census", census.parse), ("bonds", bonds.parse),
                     ("vg", lambda: vg.parse(load("value_input")))]:
        try:
            fn()
            status[name] = "ok"
        except FileNotFoundError as e:
            status[name] = f"skipped ({e})"
        except Exception as e:  # noqa: BLE001
            status[name] = f"FAILED: {type(e).__name__}: {e}"
        print(f"[exo] {name}: {status[name]}")
    return status


def static(flats: pd.DataFrame) -> pd.DataFrame:
    """OSM + Census features (time-invariant before the cut-off)."""
    parts = [pd.DataFrame(index=flats.index)]
    if enabled("osm"):
        parts.append(osm.features(flats))
    if enabled("census"):
        parts.append(census.features(flats))
    return pd.concat(parts, axis=1)


def snapshot(flats: pd.DataFrame, s: pd.Timestamp, task: str) -> pd.DataFrame:
    if not enabled("bonds") or task != "rents":
        return pd.DataFrame(index=flats.index)
    return bonds.snapshot_features(flats, s)


def available() -> dict:
    return {"osm": osm.OUT.exists(), "census": census.OUT.exists(),
            "bonds": bonds.OUT.exists(), "vg": vg.OUT.exists(),
            "on": [x for x in ("osm", "census", "bonds", "vg") if enabled(x)]}


if __name__ == "__main__":
    build()
