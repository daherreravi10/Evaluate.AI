"""Score our CSVs the way the judges describe, against MOCK hidden data.

Only works with mock data (data/mock_hidden/). On the day the real hidden
adverts and sales are private, so this script just checks the plumbing.

python scripts/mock_judge.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C  # noqa: E402
from src.loaders import load  # noqa: E402
from src.metrics import rent_scores, value_scores  # noqa: E402


def judge_rents(csv: Path) -> dict:
    sub = pd.read_csv(csv, dtype={"gnaf_id": str}).set_index("gnaf_id")
    h = pd.read_csv(C.MOCK_HIDDEN / "rents.csv", dtype={"gnaf_id": str})
    inp = load("rents_input").set_index("gnaf_id")
    # "The scored rent comes from the column matching advert parking. If advert
    #  parking is blank, use parking in the input. Exclude only when both unknown."
    car = h.advert_car_space.fillna(h.gnaf_id.map(inp.car_space))
    h = h[car.notna()]
    car = car[car.notna()]
    col = np.where(car > 0, "rent_with_car_space", "rent_without_car_space")
    pred = [sub.at[g, c] if g in sub.index else np.nan for g, c in zip(h.gnaf_id, col)]
    return rent_scores(h.price.to_numpy(), np.asarray(pred, float))


def judge_values(csv: Path) -> dict:
    sub = pd.read_csv(csv, dtype={"gnaf_id": str}).set_index("gnaf_id")
    h = pd.read_csv(C.MOCK_HIDDEN / "sales.csv", dtype={"gnaf_id": str})
    pred = h.gnaf_id.map(sub["value"]).to_numpy(float)
    return value_scores(h.price.to_numpy(), pred)


def main() -> None:
    if not (C.MOCK_HIDDEN / "rents.csv").exists():
        print("no mock hidden data: this only works on mock data")
        return
    slug = C.team_slug()
    r, v = C.OUT / f"rents_{slug}.csv", C.OUT / f"valuation_{slug}.csv"
    if r.exists():
        s = judge_rents(r)
        print(f"MOCK Task 4: median miss ${s['median_abs_error']:.0f}/wk, within $100 "
              f"{s['share_within_100']:.1%} on {s['n']} adverts (Microburbs real: $86, 55.2%)")
    if v.exists():
        s = judge_values(v)
        print(f"MOCK Task 5: within 10% {s['hits_within_10pct']}/{s['n']} = {s['share_within_10pct']:.1%}, "
              f"median miss ${s['median_abs_error']:,.0f} (real baselines: 34, 86, 109 of 227)")


if __name__ == "__main__":
    main()
