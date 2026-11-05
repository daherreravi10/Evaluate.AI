"""Snapshot features shared by Task 4 (rents) and Task 5 (valuation).

A "snapshot" is a date s. Every feature for s is computed ONLY from events
dated before s, and prices are moved to s with an index that was also built
only from events before s. Training rows are events in [s, s + horizon), so
the model learns exactly what the judges test: predict ~2 months ahead from
what was known at the cut-off.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from .index import adjust, pairs_from_events, repeat_index

EARTH_KM = 6371.0


def _bed(x: pd.Series) -> pd.Series:
    return x.fillna(-1).clip(upper=4).astype(int)


def snapshot_features(flats: pd.DataFrame, events: pd.DataFrame, s: pd.Timestamp,
                      pairs: pd.DataFrame | None = None, asking: pd.DataFrame | None = None,
                      k_near: int = 12) -> tuple[pd.DataFrame, pd.Series]:
    """Features for every row of `flats` as known just before snapshot `s`.

    flats  : one row per flat with gnaf_id, bkey, suburb, mb, latitude, longitude, bedrooms
    events : past prices with gnaf_id, date, price (adverts for rents, Sold for sales)
    pairs  : optional repeat pairs for the index (else built from events)
    asking : optional "For Sale" adverts (gnaf_id, date, price) for Task 5
    Returns (features indexed like flats, index series).
    """
    ev = events[events.date < s]
    pr = pairs if pairs is not None else pairs_from_events(ev)
    idx = repeat_index(pr[pr.date_2 < s], end=s)
    ev = ev.assign(ladj=adjust(ev.price, ev.date, idx))
    ev = ev.merge(flats[["gnaf_id", "bkey", "suburb", "mb", "bed"]], on="gnaf_id", how="inner")
    city_bed = ev.groupby("bed").ladj.median()
    ev["lnorm"] = ev.ladj - ev.bed.map(city_bed)   # price level net of bedroom count
    recent = ev[ev.date >= s - pd.DateOffset(years=6)]

    F = pd.DataFrame(index=flats.index)
    g = flats[["gnaf_id", "bkey", "suburb", "mb", "bed"]]

    # own history: last price moved to s, and how old it is
    last = ev.sort_values("date").groupby("gnaf_id").tail(1).set_index("gnaf_id")
    F["own_last_ladj"] = g.gnaf_id.map(last.ladj)
    F["own_last_age_y"] = (s - g.gnaf_id.map(last.date)).dt.days / 365.25
    F["own_n"] = g.gnaf_id.map(ev.groupby("gnaf_id").size()).fillna(0)

    # same building, same bedrooms / any bedrooms (normalised)
    for name, keys, src in [("bldg_bed", ["bkey", "bed"], "ladj"), ("bldg", ["bkey"], "lnorm"),
                            ("mb", ["mb"], "lnorm"), ("sub_bed", ["suburb", "bed"], "ladj"),
                            ("sub", ["suburb"], "lnorm")]:
        agg = recent.groupby(keys)[src].agg(["median", "size"])
        m = g[keys].merge(agg, left_on=keys, right_index=True, how="left")
        F[f"{name}_med"] = m["median"].to_numpy()
        F[f"{name}_n"] = m["size"].fillna(0).to_numpy()

    # nearby buildings (excluding own), for flats in buildings with no history
    b = recent.groupby("bkey").agg(lnorm=("lnorm", "median"), n=("lnorm", "size"))
    pos = flats.groupby("bkey")[["latitude", "longitude"]].first()
    b = b.join(pos, how="inner").dropna()
    if len(b) > k_near:
        tree = BallTree(np.radians(b[["latitude", "longitude"]].to_numpy()), metric="haversine")
        q = np.radians(flats[["latitude", "longitude"]].fillna(0).to_numpy())
        dist, ind = tree.query(q, k=k_near + 1)
        vals = b.lnorm.to_numpy()[ind]
        same = b.index.to_numpy()[ind] == flats.bkey.to_numpy()[:, None]
        w = np.where(same, 0.0, 1.0 / (dist * EARTH_KM + 0.05))
        F["near_med"] = (vals * w).sum(1) / np.maximum(w.sum(1), 1e-9)
        F["near_dist_km"] = np.where(same, np.inf, dist * EARTH_KM).min(1)

    # a "For Sale" advert before s is information the judges allow (Task 5)
    if asking is not None and len(asking):
        a = asking[(asking.date < s) & (asking.date >= s - pd.Timedelta(days=150))]
        a = a.sort_values("date").groupby("gnaf_id").tail(1).set_index("gnaf_id")
        F["ask_ladj"] = g.gnaf_id.map(pd.Series(adjust(a.price, a.date, idx), index=a.index))
        F["ask_age_d"] = (s - g.gnaf_id.map(a.date)).dt.days

    # relative to suburb: lets the trees share strength across suburbs
    base = F["sub_bed_med"].fillna(F["sub_med"] + flats.bed.map(city_bed))
    for c in ["own_last_ladj", "bldg_bed_med", "ask_ladj"]:
        if c in F:
            F[c + "_rel"] = F[c] - base
    F["base_ladj"] = base
    # anchor = best single guess; the model learns corrections on top of it
    # (passed to LightGBM as init_score). Order: asking advert > own last price
    # > same building & bedrooms > suburb & bedrooms.
    chain = [c for c in ["ask_ladj", "own_last_ladj", "bldg_bed_med"] if c in F] + ["base_ladj"]
    anchor = pd.Series(np.nan, index=F.index)
    kind = pd.Series(np.nan, index=F.index)
    for k, c in enumerate(chain):
        fill = anchor.isna() & F[c].notna()
        anchor[fill], kind[fill] = F.loc[fill, c], k
    F["anchor_ladj"] = anchor
    F["anchor_kind"] = kind.map({i: chain[i] for i in range(len(chain))}).map(
        {"ask_ladj": 0, "own_last_ladj": 1, "bldg_bed_med": 2, "base_ladj": 3})
    F["idx_12m"] = float(idx.iloc[-1] - idx.iloc[-13]) if len(idx) > 13 else 0.0
    return F, idx


def static_features(flats: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    X = flats[cols].copy()
    for c in X.columns:
        if X[c].dtype == object:
            X[c] = X[c].astype("category")
    return X


def add_keys(flats: pd.DataFrame) -> pd.DataFrame:
    flats = flats.copy()
    flats["bed"] = _bed(flats["bedrooms"])
    return flats
