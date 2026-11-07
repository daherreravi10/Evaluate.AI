"""Why each supplied column is used or not: the team's decision log.

One entry per (file, column). `python -m src.eda` joins this with the evidence it measures
(missing share, dates after the cut-off, signal against price) and writes
outputs/data_decisions.csv and the "How we chose the data" section of report.html.

Statuses
  feature   goes into the model as it is
  derived   used to build features (named in `becomes`)
  key       joins files or groups rows; carries no price information itself
  label     the price we learn from, or the parking of that price
  not used  left out, with the reason

Columns the real files bring that are not listed here show up as "review" in the report.
On the day: change an entry here whenever the team changes its mind, and say why.
"""
from __future__ import annotations

# columns that would let the model see the future; tests make sure they never become features
LOOKAHEAD = {"ever_advertised_for_lease", "attrs_last_seen", "first_ever_listed"}

D = {
    # ---------------- Task 4 input: one row per flat to price ----------------
    ("rents_input", "gnaf_id"): ("key", "", "Joins past adverts and identifies the row in the hand-in CSV. An id has no price meaning."),
    ("rents_input", "address"): ("derived", "postcode", "Free text. Only the postcode at its end is used, to join rental bond data."),
    ("rents_input", "building_address"): ("derived", "bldg_* features", "Defines the building. Flats in one building rent alike, so past adverts in the same building are the strongest signal after the flat's own history."),
    ("rents_input", "suburb"): ("feature", "suburb_code, sub_* medians", "Suburb level and suburb x bedroom medians, the organisers' own baseline."),
    ("rents_input", "mb"): ("derived", "mb_* medians, block counts, Census join", "Mesh Block: finer than suburb. Groups nearby adverts and joins the blocks file and Census SA1 data."),
    ("rents_input", "latitude"): ("feature", "near_* features, OSM distances", "Location. Also finds the nearest buildings with adverts for flats with no history."),
    ("rents_input", "longitude"): ("feature", "near_* features, OSM distances", "As latitude."),
    ("rents_input", "property_type"): ("feature", "ptype_code", "Apartment, unit or studio. The page says bedrooms wins when they disagree; the model gets both."),
    ("rents_input", "bedrooms"): ("feature", "bedrooms, bed groups", "The main size measure; also splits every median by bedroom count."),
    ("rents_input", "bathrooms"): ("feature", "", "Second size measure."),
    ("rents_input", "car_space"): ("label", "car", "Fills an advert's parking when the advert says nothing, the same fallback the judges use. Prediction sets it to 1 and to 0 for the two columns."),
    ("rents_input", "car_spaces"): ("not used", "", "The hand-in prices one car space or none. The yes/no in car_space carries that; the count only differs for flats with 2+ spaces (share shown in the evidence)."),
    ("rents_input", "floor_level"): ("feature", "", "Known for about half the flats. Higher floors rent for more; trees handle the blanks."),
    ("rents_input", "flats_in_building"): ("feature", "", "Building size: towers and walk-ups rent differently."),
    ("rents_input", "block_new_homes_2021_2026"): ("feature", "", "New supply in the block. The task page allows the 2026 block estimates."),
    ("rents_input", "block_homes_2026"): ("feature", "", "Density of the block (allowed 2026 estimate)."),
    ("rents_input", "ever_advertised_for_lease"): ("not used", "", "Looks ahead: it is 1 if the flat appears anywhere in the lease file, including adverts after a training snapshot. Every training row has an advert, so the model would learn nothing true from it. The safe version, own_n (adverts before the snapshot), is used instead."),
    ("rents_input", "first_ever_listed"): ("derived", "years_since_first_listed", "Used only as years since first listed, and only when that date is before the snapshot. A later date would tell the model the flat is about to be advertised."),
    ("rents_input", "attrs_last_seen"): ("not used", "", "Date bedrooms were last confirmed by an advert. For flats advertised in August-September (the judged ones) it would reveal the advert. A bookkeeping date, not a property of the flat."),

    # ---------------- Task 4 past adverts ----------------
    ("rents_leases", "gnaf_id"): ("key", "", "Links each advert to its flat."),
    ("rents_leases", "building_address"): ("not used", "", "The building is taken from the input file through gnaf_id, so both files always agree."),
    ("rents_leases", "date"): ("key", "snapshots, as-of filter", "Nothing after 31 July 2026 is kept. Sets which snapshot an advert trains or informs."),
    ("rents_leases", "price"): ("label", "own_*, bldg_*, mb_*, sub_*, near_* and the rent index", "The weekly rent we learn to predict, and every history feature."),
    ("rents_leases", "bedrooms"): ("not used", "", "The input file's bedrooms are used for every row, so training and prediction see the same attribute."),
    ("rents_leases", "bathrooms"): ("not used", "", "As bedrooms."),
    ("rents_leases", "car_spaces"): ("label", "car", "Parking of each advert: decides whether the advert trains the with- or without-car-space price."),

    # ---------------- blocks ----------------
    ("blocks", "mb"): ("key", "", "Joins to the flat's Mesh Block."),
    ("blocks", "homes_2021"): ("derived", "block_growth", "Growth in homes 2021-2026: new supply nearby."),
    ("blocks", "homes_2026"): ("derived", "block_growth, people_per_home", "Allowed 2026 estimate."),
    ("blocks", "people_2021"): ("not used", "", "Growth in homes already captures change; people per home uses 2026."),
    ("blocks", "people_2026"): ("derived", "people_per_home", "Crowding: smaller or shared homes."),

    # ---------------- Task 5 input ----------------
    ("value_input", "gnaf_id"): ("key", "", "Joins past sales and identifies the row in the hand-in CSV."),
    ("value_input", "address"): ("derived", "building key, Valuer General match", "Street address without the unit defines the building; the full address matches Valuer General sales."),
    ("value_input", "suburb"): ("feature", "suburb_code, sub_* medians", "Suburb level and suburb x bedroom medians, the organisers' baseline."),
    ("value_input", "postcode"): ("not used", "", "Repeats the suburb for the model. Only used to pick Valuer General records for the City."),
    ("value_input", "mb"): ("derived", "mb_* medians, Census join", "Mesh Block groups nearby sales and joins Census SA1 data."),
    ("value_input", "block_type"): ("feature", "block_code", "Residential vs commercial block: flats over shops sell differently."),
    ("value_input", "latitude"): ("feature", "near_* features, OSM distances", "Location; nearest buildings with sales."),
    ("value_input", "longitude"): ("feature", "near_* features, OSM distances", "As latitude."),
    ("value_input", "unit_number"): ("derived", "floor, unit_known", "Floor is not given for Task 5. Unit 315 is on floor 3, 1204 on floor 12 (3+ digit numbers only)."),
    ("value_input", "bedrooms"): ("feature", "bedrooms, bed groups", "Blank for 73% of rows. Trees handle blanks; filling them from the flat's own past records is a candidate to test."),
    ("value_input", "bathrooms"): ("feature", "", "Second size measure (blank with bedrooms)."),
    ("value_input", "car_spaces"): ("feature", "", "Parking adds to sale value."),
    ("value_input", "flats_in_building"): ("feature", "", "Building size."),

    # ---------------- Task 5 past sales and adverts ----------------
    ("value_sales", "gnaf_id"): ("key", "", "Links each sale to its flat."),
    ("value_sales", "address"): ("not used", "", "The input file's address is used, so both files agree."),
    ("value_sales", "date"): ("key", "snapshots, as-of filter", "Nothing after 31 August 2026 is kept."),
    ("value_sales", "price"): ("label", "own_*, bldg_*, mb_*, sub_*, near_*, ask_*", "Sold prices are the target and the history; For Sale prices become asking-price features."),
    ("value_sales", "type"): ("derived", "Sold vs For Sale", "Sold rows train and inform; For Sale adverts dated before the snapshot become ask_* features (allowed by the rules: they were public before the cut-off)."),
    ("value_sales", "advertised_price"): ("derived", "ask_*", "The asking price before each sale becomes a For Sale row; only adverts dated on or before the snapshot are used, and only if the flat has not sold since."),
    ("value_sales", "advertised_date"): ("key", "as-of filter", "Some adverts are dated after 31 August 2026 (up to 30 September): dropped. 0001-01-01 means unknown: dropped."),
    ("value_sales", "suburb"): ("not used", "", "The input file's suburb is used."),
    ("value_sales", "mb"): ("not used", "", "The input file's mesh block is used."),
    ("value_repeat", "suburb"): ("not used", "", "The index is citywide; suburb comes from the input file."),
    ("value_repeat", "hold_years"): ("not used", "", "Recomputed from the two dates."),
    ("value_repeat", "growth_pct_a_year"): ("not used", "", "Recomputed from the two prices; using the supplied figure adds nothing."),
    ("value_sales", "bedrooms"): ("not used", "", "Candidate: fill the 73% blank input bedrooms from the flat's own earlier records. Only if the held-out check improves."),
    ("value_sales", "bathrooms"): ("not used", "", "As bedrooms."),
    ("value_sales", "car_spaces"): ("not used", "", "As bedrooms."),

    # ---------------- Task 5 repeat sales ----------------
    ("value_repeat", "gnaf_id"): ("key", "", "Same flat on both sides of a pair."),
    ("value_repeat", "date_1"): ("derived", "price index", "Repeat-sales index: how much City flat prices moved month by month, rebuilt at every snapshot from earlier pairs only."),
    ("value_repeat", "price_1"): ("derived", "price index", "As date_1."),
    ("value_repeat", "date_2"): ("derived", "price index", "As date_1."),
    ("value_repeat", "price_2"): ("derived", "price index", "As date_1."),
}

FILE_TITLE = {
    "rents_input": "Task 4 input: flats to price", "rents_leases": "Task 4 past adverts",
    "blocks": "Blocks: homes and people 2021-2026", "value_input": "Task 5 input: flats to value",
    "value_sales": "Task 5 past sales and adverts", "value_repeat": "Task 5 repeat sales",
}

# Engineered feature groups, for the held-out importance table
GROUPS = [
    ("Starting guess (anchor)", ("anchor_",)),
    ("The flat's own history", ("own_", "ask_")),
    ("Same building", ("bldg_",)),
    ("Same block", ("mb_", "block_", "people_per_home")),
    ("Suburb", ("sub_", "suburb_code", "base_ladj")),
    ("Nearest buildings", ("near_",)),
    ("Flat attributes", ("bedrooms", "bathrooms", "floor", "car", "flats_in_building", "ptype_code",
                         "unit_known", "years_since_first_listed")),
    ("Location", ("latitude", "longitude")),
    ("Market trend", ("idx_",)),
    ("Outside data", ("osm_", "cen_", "bond_")),
]


def group_of(feature: str) -> str:
    for name, prefixes in GROUPS:
        if feature.startswith(prefixes):
            return name
    return "Other"


def lookup(file_key: str, col: str) -> tuple[str, str, str]:
    return D.get((file_key, col), ("review", "", "Not in our plan: a column we did not expect. Check it on the day."))
