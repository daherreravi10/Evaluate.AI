"""Task 4 — What will this flat rent for? (as at 31 July 2026)

python -m src.rents            # held-out check + final CSV + metrics json
python -m src.rents --quick    # fewer snapshots, for a fast first pass on the day
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from . import asof, config as C
from .features import add_keys, snapshot_features
from .exo import build as exo
from .loaders import load, merge_api_events
from .metrics import bootstrap_ci, rent_scores
from .model import build, fit, group_importance, importance, snapshots_before

# Every column choice is explained in src/decisions.py (and in report.html).
# Not here on purpose: ever_advertised_for_lease and attrs_last_seen look ahead in time;
# first_ever_listed is used only through a snapshot-safe age (see feature_frame).
STATIC = ["bedrooms", "bathrooms", "floor_level", "flats_in_building", "block_new_homes_2021_2026",
          "block_homes_2026", "latitude", "longitude", "suburb_code", "ptype_code",
          "block_growth", "people_per_home"]


def prepare():
    flats = add_keys(load("rents_input")).reset_index(drop=True)
    flats["bkey"] = flats.building_address.fillna("").str.upper().str.strip() + "|" + \
        flats.suburb.fillna("").str.upper()
    flats["suburb_code"] = flats.suburb.astype("category").cat.codes
    flats["ptype_code"] = flats.property_type.astype("category").cat.codes
    try:
        blocks = load("blocks")
        blocks["block_growth"] = blocks.homes_2026 / blocks.homes_2021.replace(0, np.nan) - 1
        blocks["people_per_home"] = blocks.people_2026 / blocks.homes_2026.replace(0, np.nan)
        flats = flats.merge(blocks[["mb", "block_growth", "people_per_home"]], on="mb", how="left")
    except FileNotFoundError:
        flats["block_growth"] = flats["people_per_home"] = np.nan
    flats = pd.concat([flats, exo.static(flats)], axis=1)   # OSM + Census, if present

    lea = asof.until(load("rents_leases"), C.RENT_CUTOFF, name="past leases")
    lea = merge_api_events(lea, "rents", "rent", C.RENT_CUTOFF)
    lea = lea[(lea.price >= 100) & (lea.price <= 15_000)]
    lea["car"] = (lea.car_spaces > 0).astype(float).where(lea.car_spaces.notna())
    lea = lea.merge(flats[["gnaf_id", "car_space"]], on="gnaf_id", how="left")
    lea["car"] = lea.car.fillna(lea.car_space)  # same fallback the judges use
    return flats, lea


def feature_frame(flats, lea, s):
    F, idx = snapshot_features(flats, lea, s)
    # suburb x bedrooms x parking median: the organisers' "adding parking" baseline
    rec = lea[(lea.date < s) & (lea.date >= s - pd.DateOffset(years=1))]
    rec = rec.merge(flats[["gnaf_id", "suburb", "bed"]], on="gnaf_id")
    sbc = rec.groupby(["suburb", "bed", "car"]).price.median()
    B = exo.snapshot(flats, s, "rents")                     # rental bonds, if present
    if "bond_pc_bed_lmed" in B:
        B["bond_rel"] = B.bond_pc_bed_lmed - F.base_ladj
    X = pd.concat([flats[static_cols(flats)], F, B], axis=1)
    # years since first seen advertised, only if that happened before the snapshot:
    # a later date would tell the model the flat is about to be advertised
    first = flats.first_ever_listed.where(flats.first_ever_listed < s)
    X["years_since_first_listed"] = (s - first).dt.days / 365.25
    return X, sbc, idx


def static_cols(flats) -> list[str]:
    return STATIC + [c for c in flats.columns if c.startswith(("osm_", "cen_"))]


def rows_for(flats, lea, s, we):
    X, _, _ = feature_frame(flats, lea, s)
    t = lea[(lea.date >= s) & (lea.date < we)]
    pos = pd.Series(flats.index, index=flats.gnaf_id)
    t = t[t.gnaf_id.isin(pos.index)]
    R = X.loc[pos[t.gnaf_id].to_numpy()].reset_index(drop=True)
    R["car"] = t.car.to_numpy()
    R["y"] = np.log(t.price.to_numpy())
    R["price"] = t.price.to_numpy()
    R["gnaf_id"] = t.gnaf_id.to_numpy()
    R["date"] = t.date.to_numpy()
    return R


def predict_both(model, X, features):
    out = {}
    for car in (1.0, 0.0):
        Z = X.copy()
        Z["car"] = car
        out[car] = np.exp(model.predict(Z))
    return out[1.0], out[0.0]


def run(quick: bool = False, heldout_only: bool = False) -> dict:
    C.ensure_dirs()
    n = 4 if quick else C.N_SNAPSHOTS
    flats, lea = prepare()
    print(f"flats {len(flats):,} | leases <= cut-off {len(lea):,}")
    end_split, cut = pd.Timestamp(C.RENT_SPLIT), pd.Timestamp(C.RENT_CUTOFF)

    # ---------- 1. our own held-out check: train < split, test split..cut-off ----------
    print("held-out check")
    train = build(snapshots_before(end_split, n), lambda s, we: rows_for(flats, lea, s, we), end_split)
    feats = [c for c in train.columns if c not in {"y", "price", "gnaf_id", "date", "snapshot"}]
    model = fit(train, feats, monotone={"car": 1})
    test = rows_for(flats, lea, end_split, cut + pd.Timedelta(days=1))
    Xs, sbc, _ = feature_frame(flats, lea, end_split)
    p_model = np.exp(model.predict(test))
    tf = test.merge(flats[["gnaf_id", "suburb", "bed"]], on="gnaf_id", how="left")
    b_sub = np.exp(test.base_ladj.to_numpy())
    b_park = tf.set_index(["suburb", "bed", "car"]).index.map(sbc).to_numpy(float)
    b_park = np.where(np.isnan(b_park), b_sub, b_park)
    b_own = np.where(test.own_last_ladj.notna(), np.exp(test.own_last_ladj), b_sub)
    methods = {
        "Suburb x bedrooms median": b_sub,
        "Suburb x bedrooms x parking median": b_park,
        "Own last advert, indexed": b_own,
        "Our model (LightGBM, snapshots)": p_model,
    }
    y = test.price.to_numpy()
    held = {k: rent_scores(y, v) for k, v in methods.items()}
    ci = bootstrap_ci(y, p_model, rent_scores, "median_abs_error")
    groups = group_importance(model, test, feats, rent_scores, "median_abs_error", higher_is_better=False)
    print("  held-out importance (how much the median miss grows if the group is scrambled):")
    for g in groups[:-1]:
        print(f"    {g['group']:28s} {g['worse_by']:+.1f} $/wk")
    for k, v in held.items():
        print(f"  {k:38s} median miss ${v['median_abs_error']:.0f}  within $100 {v['share_within_100']:.1%}  R2 {v['r2']:.3f}")
    pd.DataFrame({"gnaf_id": test.gnaf_id, "date": test.date, "y": y, "car": test.car,
                  "suburb": tf.suburb, "bed": tf.bed, **{k: v for k, v in methods.items()}}
                 ).to_parquet(C.OUT / "rents_holdout.parquet")
    if heldout_only:
        return {"heldout": held, "features": feats, "exo": exo.available(), "group_importance": groups}

    # ---------- 2. final model: everything up to the cut-off, predict all flats ----------
    print("final model")
    s_final = cut + pd.Timedelta(days=1)
    train_f = build(snapshots_before(s_final, n), lambda s, we: rows_for(flats, lea, s, we), s_final)
    model_f = fit(train_f, feats, monotone={"car": 1})
    Xf, _, idx = feature_frame(flats, lea, s_final)
    with_car, without_car = predict_both(model_f, Xf, feats)
    fallback = np.exp(Xf.base_ladj.fillna(np.log(lea.price.median())))
    with_car = np.where(np.isfinite(with_car), with_car, fallback)
    without_car = np.where(np.isfinite(without_car), without_car, fallback)
    without_car = np.minimum(without_car, with_car)
    out = pd.DataFrame({"gnaf_id": flats.gnaf_id,
                        "rent_with_car_space": np.round(with_car * 2) / 2,
                        "rent_without_car_space": np.round(without_car * 2) / 2})
    path = C.OUT / f"rents_{C.team_slug()}.csv"
    out.to_csv(path, index=False, encoding="utf-8")
    print(f"wrote {path} ({len(out):,} rows)")
    # for the demo app only (data/cache is never committed)
    app = flats[["gnaf_id", "address", "suburb", "latitude", "longitude", "bedrooms", "bathrooms",
                 "car_space", "floor_level", "flats_in_building", "bkey"]].copy()
    app = app.assign(with_car=out.rent_with_car_space, without_car=out.rent_without_car_space,
                     anchor_kind=Xf.anchor_kind.to_numpy(), own_last=np.exp(Xf.own_last_ladj).to_numpy(),
                     own_last_age_y=Xf.own_last_age_y.to_numpy(),
                     bldg_bed=np.exp(Xf.bldg_bed_med).to_numpy(), bldg_bed_n=Xf.bldg_bed_n.to_numpy())
    app.to_parquet(C.CACHE / "app_rents.parquet")

    prem = out.rent_with_car_space - out.rent_without_car_space
    by_bed = pd.DataFrame({"bed": flats.bed, "prem": prem}).groupby("bed").prem.median()
    by_sub = pd.DataFrame({"suburb": flats.suburb, "prem": prem}).groupby("suburb").prem.median()
    floor_pd = floor_effect(model_f, Xf, feats)
    metrics = {
        "task": "rents", "cutoff": C.RENT_CUTOFF, "split": C.RENT_SPLIT,
        "horizon_months": C.HORIZON_MONTHS, "snapshots": n,
        "train_rows_holdout": len(train), "train_rows_final": len(train_f),
        "test_rows": len(test), "test_from": str(test.date.min().date()),
        "test_to": str(test.date.max().date()), "heldout": held,
        "model_median_error_ci95": ci, "importance": importance(model_f, feats),
        "group_importance": groups, "features": feats,
        "parking_premium_median": float(prem.median()),
        "parking_premium_by_bed": {str(k): float(v) for k, v in by_bed.items()},
        "parking_premium_by_suburb": {k: float(v) for k, v in by_sub.sort_values().items()},
        "floor_effect": floor_pd,
        "rent_index_12m": float(idx.iloc[-1] - idx.iloc[-13]),
        "rows_written": len(out), "csv": path.name,
        "exo": exo.available(), "exo_features": [f for f in feats if f.startswith(("osm_", "cen_", "bond_"))],
    }
    (C.OUT / "metrics_rents.json").write_text(json.dumps(metrics, indent=1))
    return metrics


def floor_effect(model, X, feats, floors=(1, 5, 10, 20, 30)) -> dict:
    """Average predicted weekly rent if every flat sat on a given floor."""
    S = X.sample(min(5000, len(X)), random_state=0).copy()
    S["car"] = 0.0
    res = {}
    for f in floors:
        S["floor_level"] = f
        res[str(f)] = float(np.median(np.exp(model.predict(S))))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--heldout-only", action="store_true", help="skip the final model and CSV")
    run(**vars(ap.parse_args()))
