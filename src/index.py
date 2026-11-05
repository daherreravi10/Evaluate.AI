"""Repeat-pairs market index (Bailey-Muth-Nourse), monthly, with smoothing.

Same flat, two prices: log(p2/p1) = I[m2] - I[m1] + noise. Solved by sparse
least squares with a small penalty on month-to-month jumps, so thin months
borrow from their neighbours. Built only from pairs before the snapshot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix, vstack
from scipy.sparse.linalg import lsqr


def pairs_from_events(ev: pd.DataFrame) -> pd.DataFrame:
    """Consecutive events of the same flat -> (date_1, price_1, date_2, price_2)."""
    e = ev.sort_values(["gnaf_id", "date"])[["gnaf_id", "date", "price"]]
    prev = e.groupby("gnaf_id")[["date", "price"]].shift(1)
    out = pd.DataFrame({"gnaf_id": e.gnaf_id, "date_1": prev.date, "price_1": prev.price,
                        "date_2": e.date, "price_2": e.price}).dropna()
    gap = (out.date_2 - out.date_1).dt.days
    return out[(gap >= 60)]  # same-advert re-lists add noise, not information


def repeat_index(pairs: pd.DataFrame, end: str, smooth: float = 4.0,
                 trim: float = 0.6) -> pd.Series:
    """Monthly log index up to the month of `end`, 0 at the last month."""
    p = pairs[(pairs.date_2 < pd.Timestamp(end)) & (pairs.price_1 > 0) & (pairs.price_2 > 0)]
    y = np.log(p.price_2.to_numpy() / p.price_1.to_numpy())
    p, y = p[np.abs(y) < trim * 3], y[np.abs(y) < trim * 3]
    start = p.date_1.min().to_period("M")
    months = pd.period_range(start, pd.Timestamp(end).to_period("M"), freq="M")
    s0 = start.year * 12 + start.month
    m1 = (p.date_1.dt.year * 12 + p.date_1.dt.month - s0).to_numpy()
    m2 = (p.date_2.dt.year * 12 + p.date_2.dt.month - s0).to_numpy()
    n, T = len(p), len(months)
    rows = np.r_[np.arange(n), np.arange(n)]
    X = coo_matrix((np.r_[np.ones(n), -np.ones(n)], (rows, np.r_[m2, m1])), shape=(n, T))
    # smoothness rows: smooth * (I[t] - I[t-1]) = 0, plus anchor I[0] = 0
    t = np.arange(1, T)
    D = coo_matrix((np.r_[np.full(T - 1, smooth), np.full(T - 1, -smooth)],
                    (np.r_[t - 1, t - 1], np.r_[t, t - 1])), shape=(T - 1, T))
    A = coo_matrix(([10.0], ([0], [0])), shape=(1, T))
    sol = lsqr(vstack([X, D, A]).tocsr(), np.r_[y, np.zeros(T - 1), 0.0], atol=1e-10, btol=1e-10)[0]
    idx = pd.Series(sol - sol[-1], index=months)
    return idx


def adjust(prices: pd.Series, dates: pd.Series, idx: pd.Series) -> np.ndarray:
    """Bring prices from their own date to the index's last month (log scale)."""
    m = dates.dt.to_period("M")
    lvl = idx.reindex(m).to_numpy()
    lvl = np.where(np.isnan(lvl), np.where(m < idx.index[0], idx.iloc[0], 0.0), lvl)
    return np.log(prices.to_numpy()) - lvl  # idx is 0 at the last month
