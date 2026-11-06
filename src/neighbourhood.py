"""What is around a flat, for the app: places nearby, living with or without a car, rough
travel times, and projects that could change the area.

Two sources, both optional:
- data/exo/places.parquet (OpenStreetMap, works offline once fetched)
- the Microburbs API, live, when MICROBURBS_API_KEY is set: transport/nearby (nearest
  train, light rail, bus, ferry) and the suburb's development applications.

Travel times are rough estimates from straight-line distance, not a journey planner; every
destination links to a real trip planner.
"""
from __future__ import annotations

import os
from urllib.parse import quote

import numpy as np
import pandas as pd

from .exo import places

EARTH_KM = 6371.0
WALK_KMH, BIKE_KMH = 4.8, 15.0
DESTINATIONS = {
    "Sydney CBD (Martin Place)": (-33.8679, 151.2111),
    "Bondi Beach": (-33.8908, 151.2743),
    "Coogee Beach": (-33.9206, 151.2588),
    "Manly Beach": (-33.7972, 151.2884),
    "Sydney Airport": (-33.9399, 151.1753),
}


def km(lat, lon, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(lat), np.radians(np.asarray(lat2, float))
    dl = np.radians(np.asarray(lon2, float) - lon)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(a))


def walk_min(d_km: float) -> int:
    return int(round(d_km * 1.3 / WALK_KMH * 60))


def load_places() -> pd.DataFrame | None:
    return pd.read_parquet(places.OUT) if places.OUT.exists() else None


def nearby(lat: float, lon: float, pl: pd.DataFrame, radius_km: float = 1.6) -> pd.DataFrame:
    d = km(lat, lon, pl.lat, pl.lon)
    out = pl.assign(dist_km=d)
    out = out[out.dist_km <= radius_km].sort_values("dist_km")
    out["walk"] = [walk_min(x) for x in out.dist_km]
    out["letter"] = out.kind.map(lambda k: places.KINDS.get(k, ("?", ""))[0])
    out["label"] = out.kind.map(lambda k: places.KINDS.get(k, ("", k))[1])
    return out


def nearest(pl: pd.DataFrame, lat: float, lon: float, kinds: tuple) -> pd.Series | None:
    s = pl[pl.kind.isin(kinds)]
    if s.empty:
        return None
    d = km(lat, lon, s.lat, s.lon)
    i = int(np.argmin(d))
    r = s.iloc[i].to_dict()
    r.update(dist_km=float(d[i]), walk=int(walk_min(d[i])))
    return pd.Series(r, dtype=object)


def bus_routes(near: pd.DataFrame, within_km: float = 0.4) -> tuple[int, list[str]]:
    b = near[(near.kind == "bus") & (near.dist_km <= within_km)]
    routes = sorted({r.strip() for x in b.routes for r in str(x).split(",") if r.strip()},
                    key=lambda r: (len(r), r))
    return len(b), routes


def drive_min(d_km: float) -> int:
    road = d_km * 1.35
    speed = 18 if road < 5 else 26 if road < 12 else 32  # inner-Sydney averages incl. lights
    return int(5 * round((road / speed * 60 + 3) / 5)) or 5


def bike_min(d_km: float) -> int:
    return int(5 * round(d_km * 1.25 / BIKE_KMH * 60 / 5)) or 5


def trip_link(lat, lon, dest: str, mode: str) -> str:
    dlat, dlon = DESTINATIONS[dest]
    return (f"https://www.google.com/maps/dir/?api=1&origin={lat:.6f},{lon:.6f}"
            f"&destination={dlat},{dlon}&travelmode={quote(mode)}")


def travel(lat: float, lon: float) -> pd.DataFrame:
    rows = []
    for name, (dlat, dlon) in DESTINATIONS.items():
        d = float(km(lat, lon, dlat, dlon))
        w = walk_min(d)
        rows.append({"place": name, "km": d, "drive": drive_min(d), "bike": bike_min(d),
                     "walk": int(5 * round(w / 5)) if w <= 75 else None,
                     "transit_link": trip_link(lat, lon, name, "transit"),
                     "drive_link": trip_link(lat, lon, name, "driving")})
    return pd.DataFrame(rows)


# ---------------- live layer (Microburbs API), never required ----------------
def api_on() -> bool:
    return bool(os.environ.get("MICROBURBS_API_KEY")) and os.environ.get("KERBSIDE_OFFLINE") != "1"


def api_transport(gnaf_id: str) -> dict | None:
    """{'counts': {'train': n, ...}, 'nearest': {'train': {'name','label','lat','lng','distance_m'}, ...}}"""
    if not api_on():
        return None
    try:
        from . import client
        d = client.prop(gnaf_id, "transport/nearby")
        return d if isinstance(d, dict) and "nearest" in d else None
    except Exception:  # noqa: BLE001 - the app must keep working offline
        return None


def api_developments(suburb: str, limit: int = 5) -> list[dict] | None:
    """Latest development applications for the suburb: [{'description','date','category'}]."""
    if not api_on():
        return None
    try:
        from . import client
        name = suburb if suburb.endswith("(NSW)") else f"{suburb} (NSW)"
        d = client.suburb(name, "development/da-list")
        if not isinstance(d, list):
            return None
        d = [x for x in d if isinstance(x, dict) and x.get("description")]
        return sorted(d, key=lambda x: str(x.get("date", "")), reverse=True)[:limit]
    except Exception:  # noqa: BLE001
        return None
