"""The car-space value, checked against the raw adverts and, if it helps, calibrated by them.

Raw value: compare like with like. Same building, same bedroom count, adverts with a car space
against adverts without one, all moved to the snapshot date with the rent index, from the
three years before it. The median gap over those pairs is what a car space adds.

Why calibrate: the model starts from each flat's own history, which already carries that
flat's parking, so it rarely sees a case that teaches it what a car space is worth and
shrinks the gap. The calibrated version keeps the model's rent for the flat as it is listed
and moves the other column by the raw value (suburb x bedrooms, shrunk to the city-wide
value when a suburb has few pairs). The held-out check decides which version is handed in.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .index import adjust, pairs_from_events, repeat_index

SHRINK = 20  # pairs needed before a suburb's own value counts as much as the city-wide one


def raw_pairs(flats: pd.DataFrame, lea: pd.DataFrame, asof: pd.Timestamp, years: int = 3,
              min_each: int = 2) -> pd.DataFrame:
    """One row per (building, bedrooms) with adverts both with and without a car space."""
    e = lea[(lea.date < asof) & (lea.date >= asof - pd.DateOffset(years=years)) & lea.car.notna()]
    idx = repeat_index(pairs_from_events(lea[lea.date < asof]), end=asof)
    e = e.assign(rent=np.exp(adjust(e.price, e.date, idx)))
    e = e.merge(flats[["gnaf_id", "bkey", "bed", "suburb"]], on="gnaf_id", how="inner")
    e = e[e.bed >= 0]
    g = e.groupby(["bkey", "bed", "car"]).rent.agg(["median", "size"]).unstack("car")
    g.columns = [f"{a}_{int(b)}" for a, b in g.columns]
    if not {"median_1", "median_0", "size_1", "size_0"} <= set(g.columns):
        return pd.DataFrame()
    g = g.dropna(subset=["median_1", "median_0"])
    g = g[(g.size_1 >= min_each) & (g.size_0 >= min_each)].copy()
    g["raw"] = g.median_1 - g.median_0
    g["weight"] = np.minimum(g.size_1, g.size_0)
    sub = e.groupby("bkey").suburb.first()
    g["suburb"] = sub.reindex(g.index.get_level_values("bkey")).to_numpy()
    return g


def wmed(v, w) -> float:
    v, w = np.asarray(v, float), np.asarray(w, float)
    o = np.argsort(v)
    v, w = v[o], w[o]
    return float(v[min(np.searchsorted(np.cumsum(w), w.sum() / 2), len(v) - 1)])


def premium_table(g: pd.DataFrame):
    """(suburb, bed) -> $ a week, suburb values shrunk toward the city value for that bedroom count."""
    if g.empty:
        return None
    city = g.groupby(level="bed").apply(lambda s: wmed(s.raw, s.weight))
    overall = wmed(g.raw, g.weight)
    sb = g.reset_index().groupby(["suburb", "bed"]).apply(
        lambda s: pd.Series({"v": wmed(s.raw, s.weight), "n": len(s)}), include_groups=False)

    def lookup(suburb: pd.Series, bed: pd.Series) -> np.ndarray:
        c = bed.clip(upper=4).map(city).fillna(overall).to_numpy(float)
        key = pd.MultiIndex.from_arrays([suburb, bed.clip(upper=4)])
        v = sb.v.reindex(key).to_numpy(float)
        n = sb.n.reindex(key).fillna(0).to_numpy(float)
        w = n / (n + SHRINK)
        out = np.where(np.isnan(v), c, w * v + (1 - w) * c)
        return np.clip(out, 0, None)

    return lookup


def calibrate(with_car: np.ndarray, without_car: np.ndarray, own: pd.Series, prem: np.ndarray):
    """Keep the model's rent for the flat as listed; set the other column by the raw value."""
    own = own.to_numpy(float)
    mid = (with_car + without_car) / 2
    w = np.where(own == 1, with_car, np.where(own == 0, without_car + prem, mid + prem / 2))
    wo = np.where(own == 1, with_car - prem, np.where(own == 0, without_car, mid - prem / 2))
    wo = np.clip(wo, 50, None)
    return np.maximum(w, wo), wo


def check(flats: pd.DataFrame, lea: pd.DataFrame, out: pd.DataFrame, cutoff: str, years: int = 3) -> dict:
    """Report: raw value vs the handed-in value, on the same buildings and bedrooms."""
    g = raw_pairs(flats, lea, pd.Timestamp(cutoff) + pd.Timedelta(days=1), years)
    if g.empty:
        return {"pairs": 0}
    m = out.merge(flats[["gnaf_id", "bkey", "bed"]], on="gnaf_id")
    m["prem"] = m.rent_with_car_space - m.rent_without_car_space
    g = g.join(m.groupby(["bkey", "bed"]).prem.median().rename("model"), how="inner")
    by_sub = [{"suburb": s, "pairs": int(len(x)), "raw": wmed(x.raw, x.weight), "model": float(x.model.median())}
              for s, x in g.groupby("suburb") if len(x) >= 3]
    by_sub.sort(key=lambda r: -r["pairs"])
    by_bed = [{"bed": int(b), "pairs": int(len(x)), "raw": wmed(x.raw, x.weight), "model": float(x.model.median())}
              for b, x in g.groupby(level="bed") if len(x) >= 3]
    subs = pd.DataFrame(by_sub)
    res = {
        "pairs": int(len(g)), "adverts": int(g.size_1.sum() + g.size_0.sum()), "years": years,
        "raw_median": wmed(g.raw, g.weight), "model_median": float(g.model.median()),
        "raw_share_negative": float((g.raw < 0).mean()), "by_suburb": by_sub, "by_bed": by_bed,
        "suburb_rank_corr": float(subs.raw.corr(subs.model, method="spearman")) if len(subs) >= 5 else None,
    }
    print(f"  parking check: {res['pairs']:,} building x bedroom pairs; raw adverts say "
          f"${res['raw_median']:.0f}/wk, the hand-in says ${res['model_median']:.0f}/wk")
    return res
