"""OpenStreetMap, as it stood on the cut-off date, via an Overpass "date" query.

The [date:...] setting asks Overpass for the map as it was at that moment, so a
station or supermarket added after 31 July 2026 is never used. One snapshot at
the earlier cut-off serves both tasks.

Credit: © OpenStreetMap contributors, ODbL (https://www.openstreetmap.org/copyright).
"""
from __future__ import annotations

import json

import pandas as pd

from .. import config as C
from .common import BBOX, EXO, RAW, ensure, nearest

OVERPASS = "https://overpass-api.de/api/interpreter"
RAW_POI = RAW / "osm_poi.json"
RAW_ROADS = RAW / "osm_roads.json"
OUT = EXO / "osm_points.parquet"
SNAPSHOT = f"{C.RENT_CUTOFF}T23:59:59Z"


def _bbox() -> str:
    s, w, n, e = BBOX
    return f"{s},{w},{n},{e}"


def queries() -> dict[str, str]:
    head = f'[out:json][timeout:240][date:"{SNAPSHOT}"];'
    b = _bbox()
    poi = head + f"""
(
  node["railway"="station"]({b});
  node["public_transport"="station"]({b});
  node["railway"="tram_stop"]({b});
  node["railway"="halt"]({b});
  nwr["shop"="supermarket"]({b});
  nwr["leisure"="park"]({b});
  nwr["amenity"="school"]({b});
);
out center tags;"""
    roads = head + f"""
way["highway"~"^(motorway|trunk|primary)$"]({b});
out geom;"""
    return {"poi": poi, "roads": roads}


def download() -> None:
    """Run on a laptop with internet. ~1 minute."""
    import requests

    ensure()
    for name, q in queries().items():
        r = requests.post(OVERPASS, data={"data": q}, timeout=300,
                          headers={"User-Agent": "microburbs-hackathon-team"})
        r.raise_for_status()
        (RAW_POI if name == "poi" else RAW_ROADS).write_bytes(r.content)
        print(f"  osm {name}: {len(r.json().get('elements', [])):,} elements")


def _kind(tags: dict) -> str | None:
    if tags.get("railway") == "tram_stop" or tags.get("station") == "light_rail":
        return "light_rail"
    if tags.get("station") == "subway" or tags.get("subway") == "yes":
        return "metro"
    if tags.get("railway") in ("station", "halt") or (
            tags.get("public_transport") == "station" and tags.get("train") == "yes"):
        return "train"
    if tags.get("shop") == "supermarket":
        return "supermarket"
    if tags.get("leisure") == "park":
        return "park"
    if tags.get("amenity") == "school":
        return "school"
    return None


def parse() -> pd.DataFrame:
    rows = []
    for el in json.loads(RAW_POI.read_text(encoding="utf-8")).get("elements", []):
        k = _kind(el.get("tags", {}))
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if k and lat is not None:
            rows.append((k, lat, lon, el.get("tags", {}).get("name")))
    if RAW_ROADS.exists():
        for el in json.loads(RAW_ROADS.read_text(encoding="utf-8")).get("elements", []):
            for p in el.get("geometry", [])[::2]:  # every second vertex is plenty
                rows.append(("main_road", p["lat"], p["lon"], el.get("tags", {}).get("name")))
    pts = pd.DataFrame(rows, columns=["kind", "lat", "lon", "name"])
    ensure()
    pts.to_parquet(OUT)
    print(f"  osm points: {pts.kind.value_counts().to_dict()}")
    return pts


def features(flats: pd.DataFrame) -> pd.DataFrame:
    """Per flat: km to the nearest of each kind, and local counts."""
    if not OUT.exists():
        return pd.DataFrame(index=flats.index)
    pts = pd.read_parquet(OUT)
    F = pd.DataFrame(index=flats.index)
    rail = pts[pts.kind.isin(["train", "metro"])]
    F["osm_km_rail"] = nearest(flats, rail)["dist_km"]
    for k, radii in [("light_rail", ()), ("supermarket", (0.5,)), ("park", ()),
                     ("school", (1.0,)), ("main_road", ())]:
        nf = nearest(flats, pts[pts.kind == k], radii)
        if "dist_km" in nf:
            F[f"osm_km_{k}"] = nf["dist_km"]
            for c in nf.columns.drop("dist_km"):
                F[f"osm_{k}_{c}"] = nf[c]
    return F
