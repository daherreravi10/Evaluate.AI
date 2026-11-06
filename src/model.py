"""Shared training loop: stack monthly snapshots, fit LightGBM on log price.

Objective is Huber on log price (alpha 0.05 ~ a 5% miss): close to the median
for typical errors, which is what both judging metrics reward (median $ error
for rents, within-10% for values), and unlike L1 it allows the monotone
constraint that keeps "with car space" >= "without".
"""
from __future__ import annotations

from typing import Callable

import lightgbm as lgb
import numpy as np
import pandas as pd

from . import config as C

PARAMS = dict(objective="huber", alpha=0.05, metric="l1", learning_rate=0.05, num_leaves=31,
              min_child_samples=60, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              lambda_l2=1.0, verbose=-1, seed=7)
MAX_ROUNDS = 1200


def snapshots_before(end: str | pd.Timestamp, n: int = C.N_SNAPSHOTS,
                     horizon: int = C.HORIZON_MONTHS) -> list[pd.Timestamp]:
    """Monthly snapshots whose target window [s, s+horizon) closes by `end`."""
    last = (pd.Timestamp(end) - pd.DateOffset(months=horizon)).to_period("M").to_timestamp()
    return [last - pd.DateOffset(months=j) for j in range(n)][::-1]


def build(snapshots, make_rows: Callable, end: pd.Timestamp) -> pd.DataFrame:
    """make_rows(s, window_end) -> DataFrame of features + 'y' + 'snapshot'."""
    parts = []
    for s in snapshots:
        we = min(s + pd.DateOffset(months=C.HORIZON_MONTHS), end)
        part = make_rows(s, we)
        part["snapshot"] = s
        parts.append(part)
        print(f"  snapshot {s.date()} -> {len(part):,} training rows")
    return pd.concat(parts, ignore_index=True)


class Anchored:
    """LightGBM that starts from the anchor guess and learns the correction."""

    def __init__(self, booster, features, anchor_col):
        self.booster, self.features, self.anchor_col = booster, features, anchor_col

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(X[self.features]) + X[self.anchor_col].to_numpy()


def fit(train: pd.DataFrame, features: list[str], monotone: dict | None = None,
        anchor: str = "anchor_ladj") -> Anchored:
    """Early-stop on the latest snapshot, then refit on everything with that many rounds."""
    params = dict(PARAMS)
    if monotone:
        params["monotone_constraints"] = [monotone.get(f, 0) for f in features]
        params["monotone_constraints_method"] = "advanced"
    train = train[train[anchor].notna()]
    last = train.snapshot.max()
    tr, va = train[train.snapshot < last], train[train.snapshot == last]

    def ds(d):
        return lgb.Dataset(d[features], d.y, init_score=d[anchor].to_numpy())

    best = 300
    if len(tr) > 1000 and len(va) > 200:
        m = lgb.train(params, ds(tr), MAX_ROUNDS, valid_sets=[ds(va)],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
        best = max(50, m.best_iteration)
    booster = lgb.train(params, ds(train), best)
    print(f"  fitted {len(train):,} rows, {len(features)} features, {best} rounds")
    return Anchored(booster, features, anchor)


def importance(model: Anchored, features: list[str], top: int = 15) -> list[dict]:
    gain = model.booster.feature_importance("gain")
    order = np.argsort(gain)[::-1][:top]
    total = gain.sum() or 1
    return [{"feature": features[i], "share": float(gain[i] / total)} for i in order]


def group_importance(model: Anchored, test: pd.DataFrame, features: list[str], score,
                     key: str, higher_is_better: bool, n_rep: int = 3, seed: int = 0) -> list[dict]:
    """Held-out importance by feature group: shuffle a whole group's columns together across
    the test rows and measure how much worse the judges' metric gets. Bigger = more needed."""
    from .decisions import group_of

    rng = np.random.default_rng(seed)
    y = test.price.to_numpy()
    base = score(y, np.exp(model.predict(test)))[key]
    groups: dict[str, list[str]] = {}
    for f in features:
        groups.setdefault(group_of(f), []).append(f)
    rows = []
    for g, cols in groups.items():
        vals = []
        for _ in range(n_rep):
            T = test.copy()
            perm = rng.permutation(len(T))
            T[cols] = T[cols].to_numpy()[perm]
            vals.append(score(y, np.exp(model.predict(T)))[key])
        worse = (base - np.mean(vals)) if higher_is_better else (np.mean(vals) - base)
        rows.append({"group": g, "features": cols, "n_features": len(cols),
                     "score_without": float(np.mean(vals)), "worse_by": float(worse)})
    return sorted(rows, key=lambda r: -r["worse_by"]) + [{"group": "(all features as used)",
                                                          "score_without": float(base), "worse_by": 0.0,
                                                          "features": [], "n_features": 0}]
