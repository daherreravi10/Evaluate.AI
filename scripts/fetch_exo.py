"""Download the free outside data. Run on a laptop with internet, the night before
(nothing here needs the Microburbs key). Then: python -m src.exo.build

python scripts/fetch_exo.py               # all sources
python scripts/fetch_exo.py osm census    # some

Sizes: OSM ~2 MB, Census ~150 MB, bonds ~40 files x 3 MB, VG ~12 yearly zips x 30-60 MB.
Any source that fails prints where to download it by hand.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.exo import bonds, census, osm, places, vg  # noqa: E402

SOURCES = {"osm": osm.download, "places": places.download, "census": census.download,
           "bonds": bonds.download, "vg": vg.download}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(SOURCES):
        print(f"== {name}")
        try:
            SOURCES[name]()
        except Exception as e:  # noqa: BLE001
            print(f"  {name} failed: {type(e).__name__}: {e}")
