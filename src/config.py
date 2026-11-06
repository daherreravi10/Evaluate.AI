"""Single source of truth for dates, paths, file names and column names.

On the day (Sat 7 Nov, 11 am) the real files arrive by email. Their column
names for the three files the task pages do NOT document are guesses here
(marked GUESS). Fix them ONCE in SCHEMA below and every module follows.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# .env (team key, team name) is read here so every script sees it, not only the API client
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # python-dotenv missing: environment variables still work
    pass

DATA = ROOT / "data"
SUPPLIED = DATA / "supplied"      # the emailed files go here. NEVER commit.
CACHE = DATA / "cache"            # API cache + intermediate parquet. NEVER commit.
MOCK_HIDDEN = DATA / "mock_hidden"  # only exists for mock data (local judge)
OUT = ROOT / "outputs"            # CSVs, metrics, charts, report.html (committed)

# --------------------------------------------------------------------------
# Team name -> CSV slug (lower case, spaces to hyphens, letters/digits/hyphens)
# --------------------------------------------------------------------------
TEAM_NAME = os.environ.get("TEAM_NAME", "Team Name Here")


def team_slug(name: str = TEAM_NAME) -> str:
    slug = re.sub(r"\s+", "-", name.strip().lower())
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return re.sub(r"-{2,}", "-", slug).strip("-")


# --------------------------------------------------------------------------
# Task dates. These are the hard rules. Nothing after the cut-off is used.
# --------------------------------------------------------------------------
RENT_CUTOFF = "2026-07-31"        # Task 4: "as at 31 July 2026"
VALUE_CUTOFF = "2026-08-31"       # Task 5: value "on 31 August 2026"

# Our own held-out check (must be before the cut-off; the guide asks us to
# state it). Train on events < split, test on events in [split, cutoff].
RENT_SPLIT = "2026-05-01"
VALUE_SPLIT = "2026-05-01"

# Judges score ~2 months after the cut-off, so we train on the same horizon.
HORIZON_MONTHS = 2
N_SNAPSHOTS = 12                  # monthly training snapshots before the split

# Valuation judging only scores confirmed flats sold under $1.2M.
VALUE_SCORE_MAX_PRICE = 1_200_000

# --------------------------------------------------------------------------
# File names (from the task pages)
# --------------------------------------------------------------------------
FILES = {
    "rents_input": "rents-input-flats-city-of-sydney.csv",
    "rents_leases": "rents-past-leases-city-of-sydney.csv",
    "blocks": "blocks-homes-and-people-2021-2026.csv",
    "value_input": "flats-city-of-sydney.csv",
    "value_sales": "flat-sales-city-of-sydney.csv",
    "value_repeat": "repeat-sales-city-of-sydney.csv",
}

N_ROWS = {"rents_input": 65_777, "value_input": 181_711}

# --------------------------------------------------------------------------
# Column mapping: canonical name -> name in the real file.
# Documented on the task pages: rents_input, value_input (exact).
# GUESS: rents_leases, value_sales, value_repeat, blocks. Fix on the day.
# --------------------------------------------------------------------------
SCHEMA = {
    "rents_input": {c: c for c in [
        "gnaf_id", "address", "building_address", "suburb", "mb", "latitude",
        "longitude", "property_type", "bedrooms", "bathrooms", "car_space",
        "car_spaces", "floor_level", "flats_in_building",
        "block_new_homes_2021_2026", "block_homes_2026",
        "ever_advertised_for_lease", "first_ever_listed", "attrs_last_seen",
    ]},
    "value_input": {c: c for c in [
        "gnaf_id", "address", "suburb", "postcode", "mb", "block_type",
        "latitude", "longitude", "unit_number", "bedrooms", "bathrooms",
        "car_spaces", "flats_in_building",
    ]},
    # GUESS: one row per past rental advert
    "rents_leases": {
        "gnaf_id": "gnaf_id", "building_address": "building_address",
        "date": "date", "price": "weekly_rent", "bedrooms": "bedrooms",
        "bathrooms": "bathrooms", "car_spaces": "car_spaces",
    },
    # GUESS: one row per past sale (optionally also "For Sale" adverts)
    "value_sales": {
        "gnaf_id": "gnaf_id", "address": "address", "date": "date",
        "price": "price", "type": "type", "bedrooms": "bedrooms",
        "bathrooms": "bathrooms", "car_spaces": "car_spaces",
    },
    # GUESS: one row per pair of sales of the same flat
    "value_repeat": {
        "gnaf_id": "gnaf_id", "date_1": "date_1", "price_1": "price_1",
        "date_2": "date_2", "price_2": "price_2",
    },
    # GUESS
    "blocks": {
        "mb": "mb", "homes_2021": "homes_2021", "people_2021": "people_2021",
        "homes_2026": "homes_2026", "people_2026": "people_2026",
    },
}

# On the day, `python scripts/go.py check --apply` writes the real column names it found into
# schema_overrides.json (canonical name -> real name, per file). Loaded here, so no code edits.
OVERRIDES = ROOT / "schema_overrides.json"
if OVERRIDES.exists():
    import json as _json

    for _key, _cols in _json.loads(OVERRIDES.read_text()).items():
        SCHEMA.setdefault(_key, {}).update(_cols)

API_BASE = os.environ.get("MICROBURBS_API_BASE", "https://api-ht.microburbs.com.au")
API_RPS = 8  # docs say ~10 req/s per key; stay under it


def ensure_dirs() -> None:
    for d in (SUPPLIED, CACHE, OUT):
        d.mkdir(parents=True, exist_ok=True)
