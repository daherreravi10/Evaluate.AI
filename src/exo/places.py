"""Places around each flat, for the app only (not a model feature, so it uses today's map).

From OpenStreetMap: hospitals, shopping centres, supermarkets, train / metro / light rail
stations, ferry wharves, bus stops with the routes that serve them, parks, schools and
universities, and things under construction (new stations, buildings, roads).

python scripts/fetch_exo.py places      (laptop with internet, ~1 min)
python -m src.exo.build                 -> data/exo/places.parquet

Credit: © OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations

import json

import pandas as pd

from .common import BBOX, EXO, RAW, ensure

OVERPASS = "https://overpass-api.de/api/interpreter"
RAW_POI = RAW / "places_poi.json"
RAW_BUS = RAW / "places_bus.json"
OUT = EXO / "places.parquet"
MARGIN = 0.02  # include stations and shops just outside the City boundary

# kind -> (map letter, label)
KINDS = {
    "hospital": ("H", "Hospital"), "mall": ("M", "Shopping centre"), "supermarket": ("S", "Supermarket"),
    "train": ("T", "Train station"), "metro": ("T", "Metro station"), "light_rail": ("L", "Light rail stop"),
    "ferry": ("F", "Ferry wharf"), "bus": ("B", "Bus stop"), "park": ("P", "Park"),
    "school": ("E", "School"), "university": ("U", "University"), "construction": ("C", "Under construction"),
}


def _bbox() -> str:
    s, w, n, e = BBOX
    return f"{s - MARGIN},{w - MARGIN},{n + MARGIN},{e + MARGIN}"


def queries() -> dict[str, str]:
    b = _bbox()
    poi = f"""[out:json][timeout:300];
(
  nwr["amenity"="hospital"]({b});
  nwr["shop"~"^(mall|department_store)$"]({b});
  nwr["shop"="supermarket"]({b});
  node["railway"~"^(station|halt)$"]({b});
  node["public_transport"="station"]({b});
  node["railway"="tram_stop"]({b});
  nwr["amenity"="ferry_terminal"]({b});
  nwr["leisure"="park"]({b});
  nwr["amenity"~"^(school|university)$"]({b});
  nwr["building"="construction"]({b});
  nwr["landuse"="construction"]({b});
  nwr["railway"="construction"]({b});
);
out center tags;"""
    bus = f"""[out:json][timeout:300];
rel["route"="bus"]({b});
out body;
node(r)["highway"="bus_stop"];
out;"""
    return {"poi": poi, "bus": bus}


def download() -> None:
    import requests

    ensure()
    for name, q in queries().items():
        r = requests.post(OVERPASS, data={"data": q}, timeout=400,
                          headers={"User-Agent": "microburbs-hackathon-team"})
        r.raise_for_status()
        (RAW_POI if name == "poi" else RAW_BUS).write_text(r.text)
        print(f"  places {name}: {len(r.json().get('elements', [])):,} elements")


def _kind(t: dict) -> str | None:
    if t.get("amenity") == "hospital":
        return "hospital"
    if t.get("shop") in ("mall", "department_store"):
        return "mall"
    if t.get("shop") == "supermarket":
        return "supermarket"
    if t.get("railway") == "tram_stop" or t.get("station") == "light_rail" or t.get("light_rail") == "yes":
        return "light_rail"
    if t.get("station") == "subway" or t.get("subway") == "yes":
        return "metro"
    if t.get("railway") in ("station", "halt") or (t.get("public_transport") == "station" and t.get("train") == "yes"):
        return "train"
    if t.get("amenity") == "ferry_terminal":
        return "ferry"
    if t.get("leisure") == "park":
        return "park"
    if t.get("amenity") == "school":
        return "school"
    if t.get("amenity") == "university":
        return "university"
    if "construction" in (t.get("building"), t.get("landuse"), t.get("railway"), t.get("highway")):
        return "construction"
    return None


def _detail(k: str, t: dict) -> str:
    if k != "construction":
        return ""
    what = t.get("construction") or t.get("building:use") or ""
    if t.get("railway") == "construction":
        what = f"new {what or 'rail'} line"
    elif t.get("building") == "construction":
        what = f"new {what or 'building'}"
    elif t.get("landuse") == "construction":
        what = "construction site"
    return what.replace("_", " ")


def parse() -> pd.DataFrame:
    rows = []
    for el in json.loads(RAW_POI.read_text()).get("elements", []):
        t = el.get("tags", {})
        k = _kind(t)
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if k and lat is not None:
            rows.append({"kind": k, "name": t.get("name") or "", "lat": lat, "lon": lon, "routes": "",
                         "detail": _detail(k, t), "osm_id": f"{el.get('type', 'n')[0]}{el.get('id')}"})
    if RAW_BUS.exists():
        els = json.loads(RAW_BUS.read_text()).get("elements", [])
        serve: dict[int, set] = {}
        for el in els:
            if el.get("type") == "relation":
                ref = el.get("tags", {}).get("ref") or el.get("tags", {}).get("name")
                for m in el.get("members", []):
                    if m.get("type") == "node" and ref:
                        serve.setdefault(m["ref"], set()).add(ref)
        for el in els:
            if el.get("type") == "node" and el.get("tags", {}).get("highway") == "bus_stop":
                refs = sorted(serve.get(el["id"], set()), key=lambda r: (len(r), r))
                rows.append({"kind": "bus", "name": el["tags"].get("name") or "", "lat": el["lat"],
                             "lon": el["lon"], "routes": ", ".join(refs), "detail": "", "osm_id": f"n{el['id']}"})
    df = pd.DataFrame(rows).drop_duplicates(["kind", "osm_id"])
    # a station mapped twice (node + area) keeps one point per name
    named = df.name != ""
    df = pd.concat([df[named].drop_duplicates(["kind", "name"]), df[~named]], ignore_index=True)
    ensure()
    df.to_parquet(OUT)
    print(f"  places: {df.kind.value_counts().to_dict()}")
    return df
