"""Pure helpers for the app (no Streamlit): result ordering, similar flats, sales history.

Kept apart from app.py so they can be tested without starting the app.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Addresses in the valuation file flagged as flats that are not homes (car spaces, storage cages).
NOT_A_HOME = ("CARSPACE", "CAR SPACE", "STORE ", "STORAGE")


def is_home(address: pd.Series) -> pd.Series:
    """False for car-space and storage addresses, which the valuation file marks as flats."""
    a = address.fillna("").str.upper().str.lstrip()
    return ~a.str.startswith(NOT_A_HOME)


def unit_sort_key(label: str) -> tuple:
    """Natural order: building first, then unit number as a number ('Unit 2' before 'Unit 10')."""
    s = str(label)
    unit, _, building = s.partition(",") if "," in s else ("", "", s)
    m = re.search(r"(\d+)", unit)
    return (building.strip().lower(), int(m.group(1)) if m else -1, unit.strip().lower())


def distance_m(lat: float, lon: float, lats, lons) -> np.ndarray:
    """Metres from one point to many (equirectangular; fine at city scale)."""
    la, lo = np.radians(np.asarray(lats, float)), np.radians(np.asarray(lons, float))
    x = (lo - np.radians(lon)) * np.cos(np.radians(lat))
    return 6_371_000 * np.hypot(la - np.radians(lat), x)


def _floor(row: pd.Series) -> float:
    for c in ("r_floor_level", "v_floor"):
        v = row.get(c, np.nan)
        if pd.notna(v):
            return float(v)
    return np.nan


def _has_car(row: pd.Series, mode: str) -> float:
    v = row.get("r_car_space" if mode == "rent" else "v_car_spaces", np.nan)
    return np.nan if pd.isna(v) else float(v)


def similar_flats(df: pd.DataFrame, f: pd.Series, mode: str, radius_m: float = 400, n: int = 5,
                  max_same_building: int = 3) -> pd.DataFrame:
    """Flats with the same bedrooms within `radius_m` of `f`, compared like for like.

    mode "rent": compares with-car rents when the other flat has a car space, without-car rents when it
    has none. mode "sale": compares values. Picks a mix: the closest match, cheaper options, and other
    buildings, at most `max_same_building` from f's own building. Returns one row per pick with
    est, base (f's figure on the same footing), diff (est - base), dist_m, same_building, compare.
    """
    est_col = "r_with_car" if mode == "rent" else "v_value"
    bkey_col = "r_bkey" if mode == "rent" else "v_bkey"
    if pd.isna(f.get("beds")) or pd.isna(f.get(est_col)) or pd.isna(f.get("lat")):
        return pd.DataFrame()
    c = df[(df.gnaf_id != f.gnaf_id) & (df.beds == f.beds) & df[est_col].notna() & df.lat.notna()].copy()
    if c.empty:
        return c
    c["dist_m"] = distance_m(float(f.lat), float(f.lon), c.lat, c.lon)
    c = c[c.dist_m <= radius_m]
    if c.empty:
        return c
    same_b = c.get(bkey_col, pd.Series(index=c.index, dtype=object))
    c["same_building"] = same_b.eq(f.get(bkey_col)) & same_b.notna()
    if mode == "rent":
        no_car = c.r_car_space.fillna(1) < 1
        c["compare"] = np.where(no_car, "without", "with")
        c["est"] = np.where(no_car, c.r_without_car, c.r_with_car)
        c["base"] = np.where(no_car, float(f.r_without_car), float(f.r_with_car))
        scale = 50.0
    else:
        c["compare"] = "value"
        c["est"] = c.v_value
        c["base"] = float(f.v_value)
        scale = 100_000.0
    c["diff"] = c.est - c.base
    f_baths, f_car = f.get("baths"), _has_car(f, mode)
    mismatch = (c.baths.ne(f_baths) & c.baths.notna()).astype(int)
    car_col = "r_car_space" if mode == "rent" else "v_car_spaces"
    if pd.notna(f_car) and car_col in c:
        mismatch += (c[car_col].ne(f_car) & c[car_col].notna()).astype(int)
    c["score"] = c.dist_m / 100 + c["diff"].abs() / scale + mismatch
    c = c.sort_values("score")

    picks: list = []

    def take(rows: pd.DataFrame, k: int) -> None:
        for i in rows.index:
            if len(picks) >= n or k <= 0:
                return
            if i in picks:
                continue
            if c.at[i, "same_building"] and sum(c.at[j, "same_building"] for j in picks) >= max_same_building:
                continue
            picks.append(i)
            k -= 1

    take(c, 1)                                                     # closest match
    take(c[c["diff"] < -0.02 * c.base], 2)                         # cheaper options
    take(c[~c.same_building], 2)                                   # other buildings
    take(c, n)                                                     # fill
    out = c.loc[picks]
    return out.sort_values(["same_building", "dist_m"], ascending=[False, True])


def similar_notes(row: pd.Series, f: pd.Series, mode: str) -> dict:
    """Wording for one similar-flat card: where, the difference, what is alike and what is not."""
    step, unit = (1, " a week") if mode == "rent" else (1000, "")
    near = 5 if mode == "rent" else 5000
    d = float(row["diff"])
    amount = f"${round(abs(d) / step) * step:,.0f}"
    if abs(d) < near:
        diff_txt, tone = "About the same", "eq"
    elif d < 0:
        diff_txt, tone = f"{amount}{unit} less", "lo"
    else:
        diff_txt, tone = f"{amount}{unit} more", "hi"
    where = "Same building" if row["same_building"] else f"{max(10, int(round(row['dist_m'] / 10)) * 10)} m away"

    alike = []
    if pd.notna(row.get("beds")):
        b = int(row.beds)
        alike.append("studio" if b == 0 else f"{b} bed")
    if pd.notna(row.get("baths")):
        alike.append(f"{int(row.baths)} bath")
    car = _has_car(row, mode)
    if pd.notna(car) and car >= 1:
        alike.append("car space" if car == 1 or mode == "rent" else f"{int(car)} car spaces")

    differs = []
    fl, ffl = _floor(row), _floor(f)
    if pd.notna(fl) and pd.notna(ffl):
        k = int(fl - ffl)
        differs.append(f"Same floor ({int(fl)})" if k == 0 else
                       f"{abs(k)} floor{'s' if abs(k) != 1 else ''} {'higher' if k > 0 else 'lower'} ({int(fl)})")
    if pd.notna(row.get("baths")) and pd.notna(f.get("baths")) and row.baths != f.baths:
        k = int(row.baths - f.baths)
        differs.append(f"{int(row.baths)} bathroom{'s' if row.baths != 1 else ''} ({k:+d})")
    fcar = _has_car(f, mode)
    if pd.notna(car) and pd.notna(fcar) and car != fcar:
        if mode == "rent":
            differs.append("No car space" if car < 1 else "Has a car space")
        else:
            differs.append(f"{int(car)} car space{'s' if car != 1 else ''} ({int(car - fcar):+d})")
    if row.get("suburb") and row.get("suburb") != f.get("suburb"):
        differs.append(str(row.suburb))
    if mode == "rent" and row.get("compare") == "without":
        differs.append("compared without a car space")
    return {"where": where, "diff": diff_txt, "tone": tone, "alike": " · ".join(alike), "differs": " · ".join(differs)}


def sales_history(sales: pd.DataFrame, bkeys: pd.Series, gnaf_id: str, bkey: str | None,
                  cutoff: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """This flat's sales and its building's sales, nothing dated after `cutoff`.

    sales: gnaf_id, date, price, type ('Sold' or 'For Sale'), ... ; bkeys: gnaf_id -> building key.
    Returns (own, building): own has every event for the flat, building only 'Sold' rows, newest first,
    each building sale with its last asking price before it when the same flat was advertised.
    """
    from src.asof import until

    s = until(sales, cutoff)
    s = s[s.price.notna()].sort_values("date", ascending=False)
    own = s[s.gnaf_id == gnaf_id]
    if not isinstance(bkey, str) or not bkey.strip("|"):
        return own, s.iloc[0:0]
    in_b = s[s.gnaf_id.map(bkeys).eq(bkey)]
    sold = in_b[in_b.type.eq("Sold")].copy()
    ads = in_b[in_b.type.eq("For Sale")]
    asked = []
    for g, d in zip(sold.gnaf_id, sold.date):
        a = ads[(ads.gnaf_id == g) & (ads.date <= d)]
        asked.append(a.price.iloc[0] if len(a) else np.nan)
    sold["asked"] = asked
    return own, sold
