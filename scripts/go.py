"""Saturday: from "the email arrived" to two valid CSVs, report and app.

    python scripts/go.py prepare        # 10:00  wipe practice data and outputs (keeps outside data)
    # 11:00  save the six emailed CSVs into data/supplied/, paste the key into .env
    python scripts/go.py check          # key works? all files there? columns as expected?
    python scripts/go.py check --apply  # accept the column matches it proposes (writes schema_overrides.json)
    python scripts/go.py run --quick    # first real CSVs in ~3 min: commit and push them
    python scripts/go.py run            # full run (~5 min), then improve, then run again
    streamlit run app/app.py            # Kerbside, for the videos

`check` never changes data. It renames nothing on its own: with --apply it copies files that
arrived under a different name to the expected name and records column matches.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402

PY = sys.executable
# words that point at the canonical column, for files whose columns the pages do not document
HINTS = {
    "price": ["price", "weekly_rent", "rent", "amount", "sold_price", "sale_price", "advertised_price", "value"],
    "date": ["date", "listed_date", "list_date", "advert_date", "sold_date", "contract_date", "event_date"],
    "type": ["type", "event", "listing_type", "status", "event_type"],
    "car_spaces": ["car_spaces", "carspaces", "parking", "car_space", "cars", "parking_spaces"],
    "bedrooms": ["bedrooms", "beds", "bed", "bedroom_count"],
    "bathrooms": ["bathrooms", "baths", "bath", "bathroom_count"],
    "date_1": ["date_1", "date1", "first_date", "prev_date", "sale_date_1"],
    "date_2": ["date_2", "date2", "second_date", "next_date", "sale_date_2"],
    "price_1": ["price_1", "price1", "first_price", "prev_price", "sale_price_1"],
    "price_2": ["price_2", "price2", "second_price", "next_price", "sale_price_2"],
    "homes_2021": ["homes_2021", "dwellings_2021", "homes2021"],
    "homes_2026": ["homes_2026", "dwellings_2026", "homes2026"],
    "people_2021": ["people_2021", "persons_2021", "population_2021"],
    "people_2026": ["people_2026", "persons_2026", "population_2026"],
    "mb": ["mb", "mb_code", "mesh_block", "mb_code_2021", "meshblock"],
    "gnaf_id": ["gnaf_id", "gnaf_pid", "gnaf", "address_id"],
}
FILE_WORDS = {"rents_input": ["rents", "input"], "rents_leases": ["lease"], "blocks": ["block"],
              "value_input": ["flats", "city"], "value_sales": ["sales"], "value_repeat": ["repeat"]}


def say(ok: bool | None, msg: str) -> None:
    print(f"  {'OK  ' if ok else 'WARN' if ok is None else 'FAIL'} {msg}")


def sh(args: list[str], env: dict | None = None) -> int:
    return subprocess.run([PY, *args], cwd=ROOT, env={**os.environ, **(env or {})}).returncode


# ------------------------------------------------------------------ prepare
def prepare(_a) -> None:
    print("Removing practice data, caches and practice outputs (outside data in data/exo is kept)")
    for p in [C.SUPPLIED, C.MOCK_HIDDEN, C.CACHE]:
        if p.exists():
            shutil.rmtree(p)
            print(f"  removed {p.relative_to(ROOT)}/")
    for pat in ["rents_*.csv", "valuation_*.csv", "metrics_*.json", "eda.json", "data_decisions.csv",
                "exo_ablation.json", "*.parquet"]:
        for f in C.OUT.glob(pat):
            f.unlink()
            print(f"  removed outputs/{f.name}")
    if C.OVERRIDES.exists():
        C.OVERRIDES.unlink()
        print("  removed schema_overrides.json")
    mock_exo = C.DATA / "exo" / "raw" / "MOCK_EXO_DO_NOT_USE_FOR_PITCH.txt"
    if mock_exo.exists():
        shutil.rmtree(C.DATA / "exo")
        print("  removed practice outside data (data/exo/)")
    C.ensure_dirs()
    print(f"\nReady. At 11:00 save the six CSVs into {C.SUPPLIED.relative_to(ROOT)}/ and put the key in .env, then:"
          "\n  python scripts/go.py check")


# ------------------------------------------------------------------ check
def env_check() -> bool:
    ok = True
    key = os.environ.get("MICROBURBS_API_KEY", "")
    say(bool(key) or None, "MICROBURBS_API_KEY set in .env" if key else
        "no MICROBURBS_API_KEY in .env (the CSVs do not need it; the app's live transport and projects do)")
    if C.TEAM_NAME == "Team Name Here":
        say(False, "TEAM_NAME in .env is still 'Team Name Here': use the name you registered")
        ok = False
    else:
        say(True, f"team '{C.TEAM_NAME}' -> CSV names rents_{C.team_slug()}.csv, valuation_{C.team_slug()}.csv")
    return ok


def find_file(key: str, apply: bool) -> Path | None:
    want = C.SUPPLIED / C.FILES[key]
    if want.exists():
        return want
    cands = [p for p in C.SUPPLIED.glob("*.csv") if p.name not in C.FILES.values()]
    words = FILE_WORDS[key]
    hits = [p for p in cands if all(w in p.name.lower() for w in words)]
    if key == "value_input":
        hits = [p for p in hits if "sales" not in p.name.lower() and "rents" not in p.name.lower()]
    if len(hits) == 1:
        if apply:
            shutil.copy(hits[0], want)
            say(True, f"{hits[0].name} copied to {want.name}")
            return want
        say(None, f"{C.FILES[key]} missing; {hits[0].name} looks like it (re-run with --apply to use it)")
        return None
    say(False, f"{C.FILES[key]} missing in data/supplied/")
    return None


def match_columns(key: str, real: list[str]) -> tuple[dict, list[str]]:
    """canonical -> real column for the ones not found under the expected name."""
    expected = C.SCHEMA[key]
    low = {c.lower().strip(): c for c in real}
    found, missing = {}, []
    for canon, name in expected.items():
        if name in real:
            continue
        cand = None
        for h in [name.lower(), canon.lower()] + HINTS.get(canon, []):
            if h in low:
                cand = low[h]
                break
        if cand is None:
            close = difflib.get_close_matches(name.lower(), list(low), n=1, cutoff=0.75)
            cand = low[close[0]] if close else None
        if cand and cand not in expected.values() and cand not in found.values():
            found[canon] = cand
        else:
            missing.append(canon)
    return found, missing


def files_check(apply: bool) -> bool:
    import pandas as pd

    all_ok, overrides = True, {}
    print("\nFiles and columns")
    for key in C.FILES:
        p = find_file(key, apply)
        if p is None:
            all_ok = all_ok and key in ("blocks", "value_repeat")  # optional files
            continue
        head = pd.read_csv(p, nrows=200, low_memory=False)
        n = sum(1 for _ in open(p, "rb")) - 1
        found, missing = match_columns(key, list(head.columns))
        exp_n = C.N_ROWS.get(key)
        rows = f"{n:,} rows" + ("" if not exp_n else f" (expected {exp_n:,})")
        bad_rows = exp_n and n != exp_n
        say(not bad_rows and not missing, f"{p.name}: {rows}, {len(head.columns)} columns")
        if found:
            overrides[key] = found
            for canon, real in found.items():
                print(f"       {canon:<16s} <- '{real}'")
        if missing:
            print(f"       not found: {', '.join(missing)}. Real columns: {', '.join(map(str, head.columns))}")
            if key in ("rents_input", "value_input"):
                all_ok = False
        dates = [c for c in head.columns if re.search(r"date|listed|seen", str(c), re.I)]
        if dates:
            d = pd.read_csv(p, usecols=dates, low_memory=False)
            for c in dates:
                x = pd.to_datetime(d[c], errors="coerce")
                if x.notna().any():
                    print(f"       {c}: {x.min():%Y-%m-%d} to {x.max():%Y-%m-%d}")
    if overrides:
        if apply:
            cur = json.loads(C.OVERRIDES.read_text()) if C.OVERRIDES.exists() else {}
            for k, v in overrides.items():
                cur.setdefault(k, {}).update(v)
            C.OVERRIDES.write_text(json.dumps(cur, indent=1))
            say(True, "column matches saved to schema_overrides.json (re-run check to confirm)")
        else:
            say(None, "column matches proposed above: re-run with --apply to use them")
    return all_ok


def api_check() -> None:
    print("\nMicroburbs API")
    if not os.environ.get("MICROBURBS_API_KEY"):
        say(None, "skipped (no key yet)")
        return
    try:
        from src import client

        client.ping()
        say(True, "key accepted (ping)")
        subs = client.suburbs_list()
        n = len(subs) if isinstance(subs, list) else len((subs or {}).get("suburbs", []) if isinstance(subs, dict) else [])
        say(True, f"suburbs list: {n or 'received'}")
        t = client.prop(os.environ.get("EXAMPLE_GNAF", "GANSW708007997"), "transport/nearby")
        say(bool(t) or None, "transport/nearby works (app: live transport)" if t else "transport/nearby gave no data")
    except Exception as e:  # noqa: BLE001
        say(False, f"{type(e).__name__}: {str(e)[:160]} (check the key in .env, no quotes or spaces)")


def check(a) -> None:
    print("Settings")
    ok = env_check()
    if (C.SUPPLIED / "MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt").exists():
        say(False, "practice data is still in data/supplied: run  python scripts/go.py prepare  first")
        ok = False
    ok = files_check(a.apply) and ok
    api_check()
    exo = [p.stem for p in (C.DATA / "exo").glob("*.parquet")]
    print("\nOutside data")
    say(bool(exo) or None, f"built: {', '.join(sorted(exo))}" if exo else
        "none (optional). Copy exo_for_teammates.zip from the laptop that downloaded it and unzip here")
    print("\n" + ("Ready: python scripts/go.py run --quick" if ok else "Fix the FAIL lines, then run check again."))


# ------------------------------------------------------------------ run
def run(a) -> None:
    if (C.SUPPLIED / "MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt").exists() and not a.practice:
        sys.exit("Practice data is in data/supplied. Run  python scripts/go.py prepare  and add the real files "
                 "(or use --practice to run on practice data on purpose).")
    if C.TEAM_NAME == "Team Name Here" and not a.practice:
        sys.exit("Set TEAM_NAME in .env to the registered team name first.")
    args = ["scripts/run.py", *(["--quick"] if a.quick else []), *(["--task", a.task] if a.task else [])]
    if a.skip_tests:
        args.append("--skip-tests")
    code = sh(args)
    if code:
        sys.exit(code)
    slug = C.team_slug()
    print("\nNext:\n"
          f"  git add outputs/rents_{slug}.csv outputs/valuation_{slug}.csv outputs/*.json outputs/data_decisions.csv report.html\n"
          '  git commit -m "Hand-in: CSVs and report" && git push\n'
          "  streamlit run app/app.py")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("prepare").set_defaults(fn=prepare)
    c = sp.add_parser("check")
    c.add_argument("--apply", action="store_true")
    c.set_defaults(fn=check)
    r = sp.add_parser("run")
    r.add_argument("--quick", action="store_true")
    r.add_argument("--task", choices=["rents", "valuation"])
    r.add_argument("--skip-tests", action="store_true")
    r.add_argument("--practice", action="store_true")
    r.set_defaults(fn=run)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
