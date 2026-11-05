"""Check a hand-in CSV against the task contract before it goes in the repo.

python -m src.validate outputs/rents_<team>.csv
python -m src.validate outputs/valuation_<team>.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .loaders import load

CONTRACT = {
    "rents": {"input": "rents_input", "cols": ["gnaf_id", "rent_with_car_space", "rent_without_car_space"]},
    "valuation": {"input": "value_input", "cols": ["gnaf_id", "value"]},
}


def check(path: str | Path) -> list[str]:
    path = Path(path)
    task = "rents" if path.name.startswith("rents_") else "valuation"
    spec = CONTRACT[task]
    problems: list[str] = []

    if not re.fullmatch(rf"{task}_[a-z0-9-]+\.csv", path.name):
        problems.append(f"file name {path.name!r} must be {task}_<team-slug>.csv (letters, digits, hyphens)")
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        problems.append("not UTF-8")
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("has a UTF-8 BOM; write without it")

    df = pd.read_csv(path, dtype={"gnaf_id": str})
    if list(df.columns) != spec["cols"]:
        problems.append(f"columns {list(df.columns)} != {spec['cols']}")
        return problems
    ids = set(load(spec["input"]).gnaf_id)
    if len(df) != len(ids):
        problems.append(f"{len(df):,} rows, expected {len(ids):,}")
    if df.gnaf_id.duplicated().any():
        problems.append(f"{int(df.gnaf_id.duplicated().sum())} duplicate gnaf_id")
    missing, extra = ids - set(df.gnaf_id), set(df.gnaf_id) - ids
    if missing:
        problems.append(f"{len(missing):,} input ids missing")
    if extra:
        problems.append(f"{len(extra):,} ids not in the input")
    for c in spec["cols"][1:]:
        v = pd.to_numeric(df[c], errors="coerce")
        if v.isna().any():
            problems.append(f"{c}: {int(v.isna().sum()):,} blank/non-numeric (blank counts as wrong)")
        if (v <= 0).any():
            problems.append(f"{c}: {int((v <= 0).sum())} values <= 0")
        if task == "rents" and not np.allclose((v.dropna() * 2) % 1, 0):
            problems.append(f"{c}: dollars may only end in .00 or .50")
        if task == "valuation" and not np.allclose(v.dropna() % 1, 0):
            problems.append(f"{c}: whole dollars only")
    if task == "rents":
        prem = df.rent_with_car_space - df.rent_without_car_space
        if (prem < 0).any():
            problems.append(f"{int((prem < 0).sum())} flats with a negative parking premium")
    return problems


def main(paths: list[str]) -> int:
    bad = 0
    for p in paths:
        probs = check(p)
        print(("OK   " if not probs else "FAIL ") + p)
        for x in probs:
            print("   -", x)
        bad += bool(probs)
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [str(p) for p in sorted(C.OUT.glob("*_*.csv"))]))
