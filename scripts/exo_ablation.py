"""Does each outside source earn its place? Held-out check with and without it.

python scripts/exo_ablation.py            # off vs all sources, both tasks, --quick
python scripts/exo_ablation.py --each     # also leave each source out in turn
python scripts/exo_ablation.py --full     # 12 snapshots instead of 4 (slower)

Writes outputs/exo_ablation.json and prints which sources to keep. The test sets are the
same in every run (VG sales are used for training only), so the numbers are comparable.
Rule: keep a source only if it helps by more than noise (rents: $1/wk; values: 1 point).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C  # noqa: E402
from src import rents, valuation  # noqa: E402
from src.exo import SOURCES, bonds  # noqa: E402

MODEL = "Our model (LightGBM, snapshots)"
USES = {"rents": ("osm", "census", "bonds"), "valuation": ("osm", "census", "vg")}


def score(task: str, sources: tuple[str, ...], quick: bool) -> float:
    os.environ["EXO"] = "1" if sources else "0"
    os.environ["EXO_SOURCES"] = ",".join(sources) or "none"
    bonds._cache.clear()
    r = (rents if task == "rents" else valuation).run(quick=quick, heldout_only=True)
    h = r["heldout"][MODEL]
    return h["median_abs_error"] if task == "rents" else h["share_within_10pct"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--each", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--task", choices=["rents", "valuation", "both"], default="both")
    a = ap.parse_args()
    quick = not a.full
    res: dict = {}
    for task in (["rents", "valuation"] if a.task == "both" else [a.task]):
        srcs = USES[task]
        runs = {"none": (), "all": srcs}
        if a.each:
            runs |= {f"all minus {s}": tuple(x for x in srcs if x != s) for s in srcs}
        res[task] = {name: score(task, s, quick) for name, s in runs.items()}
    os.environ.pop("EXO", None)
    os.environ.pop("EXO_SOURCES", None)

    print("\n=== outside data: held-out check ===")
    verdict = {}
    for task, r in res.items():
        better = (lambda new, old: old - new > 1.0) if task == "rents" else (lambda new, old: new - old > 0.01)
        fmt = (lambda v: f"${v:.1f}/wk") if task == "rents" else (lambda v: f"{v:.1%}")
        print(f"\n{task}  ({'median miss, lower is better' if task == 'rents' else 'within 10%, higher is better'})")
        for name, v in r.items():
            print(f"  {name:22s} {fmt(v)}")
        keep_all = better(r["all"], r["none"])
        verdict[task] = {"use_outside_data": bool(keep_all)}
        for s in USES[task]:
            k = f"all minus {s}"
            if k in r:  # the source helps if removing it makes things worse by more than noise
                verdict[task][s] = bool(better(r["all"], r[k]))
        print(f"  -> {'KEEP' if keep_all else 'DROP'} outside data for {task}"
              + "".join(f"; {s}: {'keep' if v else 'drop'}" for s, v in verdict[task].items() if s in SOURCES))
    keep = sorted({s for t, v in verdict.items() for s in USES[t]
                   if v.get("use_outside_data") and v.get(s, True)})
    print("\nrecommended for the final runs:")
    print(f"  export EXO_SOURCES={','.join(keep)}" if keep else "  export EXO=0")
    if not a.each:
        print("  (run with --each to judge every source on its own)")
    (C.OUT / "exo_ablation.json").write_text(json.dumps(
        {"quick": quick, "scores": res, "verdict": verdict, "recommended_sources": keep}, indent=1))
    print(f"\nwrote {C.OUT / 'exo_ablation.json'}")


if __name__ == "__main__":
    main()
