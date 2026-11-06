"""Friday night: get this laptop ready so Saturday is only "key in, files in, run".

    python scripts/setup_tonight.py

Does, in order, and prints a PASS / FAIL table at the end:
  1. Python version (3.10+) and the packages in requirements.txt (installs what is missing)
  2. the test suite
  3. a full practice run on synthetic data (proves the whole pipeline works on this machine)
  4. a headless check of the Kerbside app
  5. downloads the free outside data (needs internet; ~10-20 min the first time) and builds it
  6. packs the processed outside data into exo_for_teammates.zip (copy it to the other laptops)

Safe to run again: finished downloads are skipped. Nothing here needs the Microburbs key.
Options: --skip-downloads (steps 1-4 only), --only-downloads (step 5-6 only).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RESULTS: list[tuple[str, bool, str]] = []


def run(title: str, args: list[str], env: dict | None = None, timeout: int = 3600) -> bool:
    import os

    print(f"\n== {title}", flush=True)
    t0 = time.time()
    e = {**os.environ, **(env or {})}
    try:
        ok = subprocess.run([PY, *args], cwd=ROOT, env=e, timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    print(f"   {'ok' if ok else 'FAILED'} in {time.time() - t0:.0f} s", flush=True)
    return ok


def record(name: str, ok: bool, note: str = "") -> None:
    RESULTS.append((name, ok, note))


def python_and_packages() -> bool:
    v = sys.version_info
    if v < (3, 10):
        record("Python 3.10+", False, f"this is {v.major}.{v.minor}: install Python 3.11 or 3.12")
        return False
    record("Python 3.10+", True, f"{v.major}.{v.minor}.{v.micro}")
    ok = run("install / check packages", ["-m", "pip", "install", "-q", "-r", "requirements.txt"])
    if not ok:  # e.g. a system Python that blocks pip
        ok = run("install packages (user)", ["-m", "pip", "install", "-q", "--user", "-r", "requirements.txt"])
    record("packages (requirements.txt)", ok, "" if ok else "make a venv: python -m venv .venv, activate it, re-run")
    return ok


def practice_run() -> None:
    record("tests", run("tests", ["-m", "pytest", "-q"]))
    ok = run("practice data", ["scripts/make_mock_data.py"])
    ok = ok and run("practice run, both tasks (quick)", ["scripts/run.py", "--quick", "--skip-tests"],
                    env={"EXO": "0", "TEAM_NAME": "Practice Team"})
    record("full pipeline on practice data", ok, "" if ok else "read the error above; nothing else will work until this does")


def app_check() -> None:
    code = (
        "from streamlit.testing.v1 import AppTest\n"
        "at = AppTest.from_file('app/app.py', default_timeout=180).run()\n"
        "assert not at.exception, at.exception\n"
        "at.button[0].click().run()\n"
        "assert not at.exception, at.exception\n"
        "print('app ok')\n")
    record("Kerbside app starts", run("app check (headless)", ["-c", code]))


def downloads() -> None:
    from importlib import import_module

    sys.path.insert(0, str(ROOT))
    exo = ROOT / "data" / "exo"
    marker = exo / "raw" / "MOCK_EXO_DO_NOT_USE_FOR_PITCH.txt"
    if marker.exists():  # practice outside files must never mix with real ones
        print("removing practice outside data first")
        shutil.rmtree(exo)
    run("download outside data", ["scripts/fetch_exo.py"], timeout=5400)
    run("build outside data", ["-m", "src.exo.build"])
    build = import_module("src.exo.build")
    for name, have in build.available().items():
        if name == "on":
            continue
        hint = {"osm": "OpenStreetMap (model features)", "places": "app: what is around each flat",
                "census": "get the 2021 GCP DataPack 'SA1, NSW' + MB_2021_AUST.xlsx into data/exo/raw/census/",
                "bonds": "rental bond .xlsx files into data/exo/raw/bonds/",
                "vg": "Valuer General bulk sales zips into data/exo/raw/vg/"}[name]
        record(f"outside data: {name}", bool(have), "" if have else hint)


def pack() -> None:
    exo = ROOT / "data" / "exo"
    files = sorted(exo.glob("*.parquet"))
    if not files:
        record("exo_for_teammates.zip", False, "nothing built yet")
        return
    out = ROOT / "exo_for_teammates.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(ROOT))
    record("exo_for_teammates.zip", True, f"{out.stat().st_size / 1e6:.0f} MB: unzip in the repo folder on each laptop")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-downloads", action="store_true")
    ap.add_argument("--only-downloads", action="store_true")
    a = ap.parse_args()
    if not a.only_downloads:
        if python_and_packages():
            practice_run()
            app_check()
    if not a.skip_downloads:
        downloads()
        pack()
    if not (ROOT / ".env").exists():
        shutil.copy(ROOT / ".env.example", ROOT / ".env")
        record(".env created", True, "set TEAM_NAME now; paste the key at 11 am tomorrow")
    print("\n" + "=" * 72)
    for name, ok, note in RESULTS:
        print(f"{'PASS' if ok else 'FAIL':5s} {name:34s} {note}")
    print("=" * 72)
    must = [r for r in RESULTS if not r[1] and not r[0].startswith("outside data")]
    print("Ready for tomorrow." if not must else "Fix the FAIL lines above before tomorrow.")
    print("Outside data is optional: the pipeline runs without it.")


if __name__ == "__main__":
    main()
