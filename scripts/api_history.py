"""Optional: pull history/all from the API for flats the supplied files say little
about, filter to the task date, and save it so the pipelines can merge it.

Only worth it if the held-out score improves. At ~8 req/s, 3,000 flats ~ 6 minutes.

python scripts/api_history.py --task rents --limit 3000
python scripts/api_history.py --task valuation --limit 3000
then re-run python -m src.rents / src.valuation (they pick up the file automatically)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import asof, client, config as C  # noqa: E402
from src.loaders import load  # noqa: E402

TASK = {
    "rents": ("rents_input", "rents_leases", C.RENT_CUTOFF),
    "valuation": ("value_input", "value_sales", C.VALUE_CUTOFF),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=TASK, required=True)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--who", choices=["no-history", "all"], default="no-history",
                    help="no-history: flats with no event in the supplied file (most to gain)")
    a = ap.parse_args()
    inp_key, ev_key, cutoff = TASK[a.task]
    flats = load(inp_key)
    if a.task == "valuation":
        flats = flats[~flats.address.fillna("").str.upper().str.contains(r"\b(?:SHOP|OFFICE)\b")]
    ev = load(ev_key)
    pool = flats.gnaf_id if a.who == "all" else flats.gnaf_id[~flats.gnaf_id.isin(ev.gnaf_id)]
    ids = pool.sample(min(a.limit, len(pool)), random_state=0).tolist()
    print(f"{a.task}: fetching history/all for {len(ids):,} of {len(pool):,} flats")
    res = client.many(lambda g: client.history(g), ids)
    df = pd.concat([v for v in res.values() if v is not None and len(v)], ignore_index=True) \
        if any(v is not None and len(v) for v in res.values()) else pd.DataFrame()
    if df.empty:
        print("no history returned")
        return
    df = asof.until(df, cutoff, name=f"API history ({a.task})")
    out = C.CACHE / f"api_events_{a.task}.parquet"
    df.to_parquet(out)
    print(df.groupby(["kind", "type"], dropna=False).size().rename("rows").to_string())
    print(f"wrote {out}: {len(df):,} rows for {df.gnaf_id.nunique():,} flats. "
          f"Check the columns above, then map them in src/loaders.merge_api_events if needed.")


if __name__ == "__main__":
    main()
