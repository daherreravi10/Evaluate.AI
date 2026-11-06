"""Run the pipeline on any OS (Windows, macOS, Linux). Same steps as run_all.sh / run_task.sh.

python scripts/run.py                    # everything: tests, outside data, EDA, both tasks, validate, report
python scripts/run.py --quick            # 4 snapshots instead of 12 (about half the time)
python scripts/run.py --task rents       # one task only (two laptops in parallel)
python scripts/run.py --task valuation --quick
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def step(title: str, args: list[str], must: bool = True) -> bool:
    print(f"\n== {title}", flush=True)
    t0 = time.time()
    ok = subprocess.run([PY, *args], cwd=ROOT).returncode == 0
    print(f"   {'ok' if ok else 'FAILED'} in {time.time() - t0:.0f} s", flush=True)
    if must and not ok:
        sys.exit(f"Stopped at: {title}. Fix the error above, then run the same command again.")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--task", choices=["rents", "valuation"])
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()
    q = ["--quick"] if a.quick else []
    if not a.skip_tests:
        step("tests", ["-m", "pytest", "-q"])
    step("outside data (whatever is downloaded)", ["-m", "src.exo.build"], must=False)
    step("EDA + data decisions", ["-m", "src.eda"])
    for task in ([a.task] if a.task else ["rents", "valuation"]):
        step(f"Task {'4 rents' if task == 'rents' else '5 valuation'}", ["-m", f"src.{task}", *q])
    step("validate hand-in CSVs", ["-m", "src.validate"])
    if (ROOT / "data" / "mock_hidden").exists():
        step("mock judge (practice data only)", ["scripts/mock_judge.py"], must=False)
    step("report.html", ["-m", "src.report"])
    print("\nDone. Open report.html, then: streamlit run app/app.py")


if __name__ == "__main__":
    main()
