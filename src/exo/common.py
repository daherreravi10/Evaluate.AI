"""Paths, address normalisation and nearest-point helpers shared by the outside sources."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from .. import config as C

EXO = C.DATA / "exo"          # processed parquet (never committed)
RAW = EXO / "raw"             # downloads (never committed)
EARTH_KM = 6371.0

# City of Sydney with a margin, (south, west, north, east)
BBOX = (-33.94, 151.155, -33.84, 151.25)

STREET_TYPES = {
    "STREET": "ST", "ROAD": "RD", "AVENUE": "AVE", "AV": "AVE", "PLACE": "PL", "LANE": "LANE",
    "LN": "LANE", "DRIVE": "DR", "PARADE": "PDE", "CRESCENT": "CRES", "CRESENT": "CRES",
    "TERRACE": "TCE", "HIGHWAY": "HWY", "BOULEVARD": "BVD", "BOULEVARDE": "BVD", "BLVD": "BVD",
    "SQUARE": "SQ", "CLOSE": "CL", "COURT": "CT", "WAY": "WAY", "CIRCUIT": "CCT", "GROVE": "GR",
    "ESPLANADE": "ESP", "WALK": "WALK", "MEWS": "MEWS", "ROW": "ROW", "QUAY": "QY",
    "PROMENADE": "PROM", "STEPS": "STPS", "ALLEY": "ALLY", "LOOP": "LOOP", "CIRCUS": "CIR",
}


def norm_street(s: pd.Series) -> pd.Series:
    """'Powell Street' / 'POWELL ST' -> 'POWELL ST'."""
    s = s.fillna("").str.upper().str.replace(r"[^A-Z0-9 ]", " ", regex=True)
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    parts = s.str.rsplit(" ", n=1, expand=True).reindex(columns=[0, 1])
    last = parts[1].map(lambda t: STREET_TYPES.get(t, t) if isinstance(t, str) else t)
    return np.where(parts[1].isna(), s, parts[0].fillna("") + " " + last.fillna(""))


def norm_num(s: pd.Series) -> pd.Series:
    return (s.fillna("").astype(str).str.upper().str.replace(r"\s+", "", regex=True)
            .str.replace(r"\.0$", "", regex=True).str.lstrip("0"))


def norm_suburb(s: pd.Series) -> pd.Series:
    return s.fillna("").str.upper().str.replace(r"\s*\(NSW\)\s*$", "", regex=True).str.strip()


def nearest(flats: pd.DataFrame, pts: pd.DataFrame, radius_counts_km: tuple = ()) -> pd.DataFrame:
    """Distance (km) from each flat to the nearest point, plus counts within radii."""
    out = pd.DataFrame(index=flats.index)
    ok = flats[["latitude", "longitude"]].notna().all(axis=1)
    if pts.empty:
        return out
    tree = BallTree(np.radians(pts[["lat", "lon"]].to_numpy()), metric="haversine")
    q = np.radians(flats.loc[ok, ["latitude", "longitude"]].to_numpy())
    d, _ = tree.query(q, k=1)
    out.loc[ok, "dist_km"] = d[:, 0] * EARTH_KM
    for r in radius_counts_km:
        out.loc[ok, f"n_{int(r * 1000)}m"] = tree.query_radius(q, r / EARTH_KM, count_only=True)
    return out


def ensure() -> None:
    for d in (EXO, RAW):
        d.mkdir(parents=True, exist_ok=True)


def parse_value_address(address: pd.Series, unit_number: pd.Series) -> pd.DataFrame:
    """Task 5 input address 'Unit 315, 2-4 Powell Street' -> unit, house, street."""
    a = address.fillna("").str.upper()
    rest = a.str.replace(r"^[^,]*,\s*", "", regex=True)          # drop 'UNIT 315, '
    m = rest.str.extract(r"^\s*([0-9]+[A-Z]?(?:\s*-\s*[0-9]+[A-Z]?)?)\s+(.*)$")
    return pd.DataFrame({"unit": norm_num(unit_number), "house": norm_num(m[0]),
                         "street": norm_street(m[1])}, index=address.index)


def addr_key(unit, house, street, suburb) -> np.ndarray:
    parts = [pd.Series(np.asarray(x, dtype=object)).fillna("").astype(str) for x in (unit, house, street, suburb)]
    return (parts[0] + "|" + parts[1] + "|" + parts[2] + "|" + parts[3]).to_numpy()


def strip(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")
