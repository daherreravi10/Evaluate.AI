"""Free outside data for Tasks 4 and 5. Every source is optional: if its file is
missing the pipelines run without it. Turn all of them off with EXO=0.

  osm      OpenStreetMap as it stood on 31 Jul 2026 (Overpass date query):
           distance to train/metro/light rail, supermarkets, parks, schools, main roads
  census   ABS Census 2021 by SA1 (G02 medians) via the Mesh Block allocation file
  bonds    NSW Fair Trading rental bond lodgements (new leases), postcode x bedrooms
  vg       NSW Valuer General bulk sales (Task 5 extra sales), contract AND settlement
           before the cut-off

Switch off: EXO=0. Pick some: EXO_SOURCES=osm,census.

Download on a laptop with internet:  python scripts/fetch_exo.py
Build features:                      python -m src.exo.build
"""
from __future__ import annotations

import os


SOURCES = ("osm", "census", "bonds", "vg")


def enabled(source: str | None = None) -> bool:
    """EXO=0 turns everything off; EXO_SOURCES=osm,census picks a subset."""
    if os.environ.get("EXO", "1") == "0":
        return False
    if source is None:
        return True
    pick = os.environ.get("EXO_SOURCES", ",".join(SOURCES))
    return source in {x.strip() for x in pick.split(",")}
