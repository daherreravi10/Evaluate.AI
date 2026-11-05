"""The judges' metrics, exactly as the task pages describe them."""
from __future__ import annotations

import numpy as np


def r2(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2))


def rent_scores(y, p) -> dict:
    """Task 4: rank by median absolute $ error; tie-break share within $100.
    Blank answers count worse than any answered error."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    err = np.abs(p - y)
    err = np.where(np.isnan(p), np.inf, err)
    finite = np.isfinite(err)
    return {
        "n": int(len(y)),
        "median_abs_error": float(np.median(err)),
        "share_within_100": float(np.mean(err <= 100)),
        "r2": r2(y[finite], p[finite]) if finite.sum() > 2 else float("nan"),
        "blank": int((~finite).sum()),
    }


def value_scores(y, p) -> dict:
    """Task 5: main score is the share within 10% of sale price (exactly 10% is
    correct). Blank is wrong. Tie-break (within 3 points): median abs $ error."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    rel = np.abs(p - y) / y
    ok = np.where(np.isnan(p), False, rel <= 0.10 + 1e-12)
    err = np.where(np.isnan(p), np.inf, np.abs(p - y))
    finite = np.isfinite(err)
    return {
        "n": int(len(y)),
        "share_within_10pct": float(np.mean(ok)),
        "hits_within_10pct": int(ok.sum()),
        "median_abs_error": float(np.median(err)),
        "r2": r2(y[finite], p[finite]) if finite.sum() > 2 else float("nan"),
        "blank": int((~finite).sum()),
    }


def bootstrap_ci(y, p, fn, key, n=500, seed=0) -> tuple[float, float]:
    """95% interval for a metric, to show how noisy 227 sales really are."""
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y, float), np.asarray(p, float)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        vals.append(fn(y[i], p[i])[key])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))
