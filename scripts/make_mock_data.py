"""Synthetic stand-ins for the six Task 4/5 files, with the documented columns.

Purpose: build and test the whole pipeline BEFORE Saturday. Nothing here is
real. Prices follow a known formula (suburb + building + floor + bedrooms +
parking + market index + noise) so we can check the models recover it.

Also writes data/mock_hidden/ with fake "judging" adverts and sales so
scripts/mock_judge.py can score our CSVs exactly as the judges describe.

Run:  python scripts/make_mock_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C  # noqa: E402

rng = np.random.default_rng(7)

SUBURBS = [
    "Alexandria", "Annandale", "Barangaroo", "Beaconsfield", "Camperdown",
    "Centennial Park", "Chippendale", "Darlinghurst", "Darlington", "Dawes Point",
    "Elizabeth Bay", "Erskineville", "Eveleigh", "Forest Lodge", "Glebe",
    "Haymarket", "Millers Point", "Moore Park", "Newtown", "Paddington",
    "Potts Point", "Pyrmont", "Redfern", "Rosebery", "Rushcutters Bay",
    "St Peters", "Surry Hills", "Sydney", "The Rocks", "Ultimo",
    "Waterloo", "Woolloomooloo", "Zetland",
]
STREETS = ["George", "Pitt", "Crown", "Bourke", "Harris", "Mary", "Elizabeth",
           "Riley", "Bay", "Wattle", "Jones", "Macleay", "Botany", "Regent",
           "Cleveland", "Oxford", "Powell", "Dunkerley", "Lachlan", "Sam Sing"]
STYPES = ["Street", "Road", "Place", "Lane", "Avenue"]

N_VALUE = C.N_ROWS["value_input"]          # 181,711
N_RENTS = C.N_ROWS["rents_input"]          # 65,777
N_RENTS_OUTSIDE = 4_246                    # rent rows absent from City files
N_SHOP_OFFICE = 6_700

MONTHS = pd.period_range("2003-01", "2026-11", freq="M")


def market_index(start_growth: float, bumps: list[tuple[str, float]]) -> pd.Series:
    t = np.arange(len(MONTHS)) / 12
    log_idx = start_growth * t + 0.02 * np.sin(t * 1.3)
    for when, size in bumps:
        k = MONTHS.get_loc(pd.Period(when, "M"))
        log_idx[k:] += size * (1 - np.exp(-(np.arange(len(MONTHS) - k)) / 6))
    log_idx -= log_idx[MONTHS.get_loc(pd.Period("2026-08", "M"))]
    return pd.Series(log_idx, index=MONTHS)


PRICE_IDX = market_index(0.045, [("2009-01", 0.08), ("2017-06", -0.07), ("2021-03", 0.12),
                                 ("2022-07", -0.09), ("2025-02", 0.05)])
RENT_IDX = market_index(0.025, [("2020-04", -0.18), ("2022-01", 0.22), ("2024-06", 0.05)])


def idx_at(idx: pd.Series, dates: pd.Series) -> np.ndarray:
    return idx.reindex(dates.dt.to_period("M")).to_numpy()


def make_buildings() -> pd.DataFrame:
    n_b = 4_300
    sub_i = rng.integers(0, len(SUBURBS), n_b)
    centre = {s: (-33.87 - 0.045 * rng.random(), 151.18 + 0.05 * rng.random()) for s in SUBURBS}
    lat = np.array([centre[SUBURBS[i]][0] for i in sub_i]) + rng.normal(0, 0.003, n_b)
    lon = np.array([centre[SUBURBS[i]][1] for i in sub_i]) + rng.normal(0, 0.003, n_b)
    sub_base_p = {s: np.log(rng.uniform(380_000, 650_000)) for s in SUBURBS}
    sub_base_r = {s: np.log(rng.uniform(400, 580)) for s in SUBURBS}
    size = np.clip(rng.lognormal(3.4, 0.9, n_b).astype(int), 4, 600)
    size = np.round(size * N_VALUE / size.sum()).astype(int).clip(4)
    floors = np.clip((size / rng.uniform(4, 12, n_b)).astype(int), 2, 60)
    nums = [f"{rng.integers(1, 400)}{'-' + str(rng.integers(2, 9)) if rng.random() < .15 else ''}"
            for _ in range(n_b)]
    addr = [f"{n} {STREETS[rng.integers(len(STREETS))]} {STYPES[rng.integers(len(STYPES))]}"
            for n in nums]
    block_type = rng.choice(
        ["Residential", "Commercial", "Industrial", "Education", "Hospital/Medical",
         "Parkland", "Transport"], n_b, p=[0.768, 0.207, 0.01, 0.005, 0.004, 0.003, 0.003])
    mb = rng.integers(11_200_000_000, 11_299_999_999, 2_281).astype(str)
    return pd.DataFrame({
        "b_id": np.arange(n_b), "suburb": [SUBURBS[i] + " (NSW)" for i in sub_i],
        "lat": lat, "lon": lon, "size": size, "floors": floors,
        "street_address": addr, "block_type": block_type,
        "mb": rng.choice(mb, n_b),
        "b_eff": rng.normal(0, 0.18, n_b),        # building quality, shared by price + rent
        "sub_p": [sub_base_p[SUBURBS[i]] for i in sub_i],
        "sub_r": [sub_base_r[SUBURBS[i]] for i in sub_i],
        "postcode": [str(2000 + (i * 7) % 50) for i in sub_i],
    })


def make_flats(b: pd.DataFrame) -> pd.DataFrame:
    rows = np.repeat(b.b_id.to_numpy(), b["size"].to_numpy())
    f = b.set_index("b_id").loc[rows].reset_index()
    f = f.iloc[:N_VALUE].copy() if len(f) >= N_VALUE else pd.concat(
        [f, f.sample(N_VALUE - len(f), replace=True, random_state=1)], ignore_index=True)
    n = len(f)
    f["floor"] = (rng.random(n) * f["floors"]).astype(int)
    f["pos"] = f.groupby(["b_id", "floor"]).cumcount() + 1
    f["unit_number"] = (f["floor"] * 100 + f["pos"]).astype(str)
    short = rng.random(n) < 0.12        # small buildings number units 1..n
    f.loc[short, "unit_number"] = (f.loc[short].groupby("b_id").cumcount() + 1).astype(str)
    f.loc[short, "floor"] = np.nan
    f["bedrooms_true"] = rng.choice([0, 1, 2, 3, 4], n, p=[0.08, 0.40, 0.40, 0.11, 0.01])
    f["bathrooms_true"] = np.where(f.bedrooms_true >= 2, rng.choice([1, 2], n, p=[.45, .55]), 1)
    f["car_true"] = (rng.random(n) < (0.25 + 0.18 * f.bedrooms_true)).astype(int)
    f["flat_eff"] = rng.normal(0, 0.07, n)
    fl = f["floor"].fillna(f["floors"] / 3)
    f["logp_base"] = (f.sub_p + f.b_eff + 0.30 * np.log1p(f.bedrooms_true) * 2.2
                      + 0.006 * fl + 0.085 * f.car_true + f.flat_eff
                      + 0.05 * (f.bathrooms_true - 1))
    f["logr_base"] = (f.sub_r + 0.7 * f.b_eff + 0.22 * np.log1p(f.bedrooms_true) * 2.2
                      + 0.004 * fl + 0.055 * f.car_true + 0.6 * f.flat_eff
                      + 0.04 * (f.bathrooms_true - 1))
    f["gnaf_id"] = [f"GANSW7{x:08d}" for x in rng.choice(10**8, n, replace=False)]
    f["address"] = "Unit " + f.unit_number + ", " + f.street_address
    shop = rng.choice(n, N_SHOP_OFFICE, replace=False)
    f["is_flat"] = True
    f.loc[f.index[shop], "is_flat"] = False
    f.loc[f.index[shop], "address"] = np.where(
        rng.random(N_SHOP_OFFICE) < .5, "SHOP ", "OFFICE ") + f.loc[f.index[shop], "unit_number"] \
        + ", " + f.loc[f.index[shop], "street_address"]
    return f.reset_index(drop=True)


def random_dates(n: int, start: str, end: str) -> pd.Series:
    a, z = pd.Timestamp(start).value // 10**9, pd.Timestamp(end).value // 10**9
    return pd.to_datetime(rng.integers(a, z, n), unit="s").normalize()


def make_leases(f: pd.DataFrame, rent_ids: np.ndarray):
    flats = f[f.gnaf_id.isin(rent_ids)]
    advertised = flats.sample(frac=1 - 16_094 / N_RENTS, random_state=3)
    k = rng.poisson(2.6, len(advertised)) + 1
    ev = advertised.loc[advertised.index.repeat(k)].copy()
    ev["date"] = random_dates(len(ev), "2016-01-01", "2026-11-04")
    ev["price"] = np.exp(ev.logr_base + idx_at(RENT_IDX, ev.date) + rng.normal(0, 0.075, len(ev)))
    ev["price"] = (ev.price / 5).round() * 5
    ev["car_spaces"] = np.where(rng.random(len(ev)) < 0.85, ev.car_true, np.nan)
    return ev, advertised


def main() -> None:
    C.ensure_dirs()
    C.MOCK_HIDDEN.mkdir(parents=True, exist_ok=True)
    b = make_buildings()
    f = make_flats(b)

    # ---------------- Task 5 input ----------------
    known_bed = rng.random(len(f)) < (1 - 132_217 / N_VALUE)
    vin = pd.DataFrame({
        "gnaf_id": f.gnaf_id, "address": f.address, "suburb": f.suburb,
        "postcode": f.postcode, "mb": f.mb, "block_type": f.block_type,
        "latitude": f.lat.round(8), "longitude": f.lon.round(8),
        "unit_number": np.where(rng.random(len(f)) < 12_070 / N_VALUE, "", f.unit_number),
        "bedrooms": np.where(known_bed, f.bedrooms_true, np.nan),
        "bathrooms": np.where(known_bed, f.bathrooms_true, np.nan),
        "car_spaces": np.where(known_bed, f.car_true, np.nan),
        "flats_in_building": f.groupby("b_id")["gnaf_id"].transform("size"),
    })

    # ---------------- Sales history ----------------
    k = rng.poisson(1.2, len(f))
    s = f.loc[f.index.repeat(k)].copy()
    s["date"] = random_dates(len(s), "2003-01-01", "2026-08-31")
    s["price"] = np.exp(s.logp_base + idx_at(PRICE_IDX, s.date) + rng.normal(0, 0.075, len(s)))
    s["price"] = (s.price / 1000).round() * 1000
    s["type"] = "Sold"

    # hidden judging sales: 1 Sep - 4 Nov 2026, flats under $1.2M (we keep 227)
    pool = f[f.is_flat].sample(3_000, random_state=11)
    hid = pool.copy()
    hid["date"] = random_dates(len(hid), "2026-09-01", "2026-11-04")
    hid["price"] = np.exp(hid.logp_base + idx_at(PRICE_IDX, hid.date) + rng.normal(0, 0.075, len(hid)))
    hid["price"] = (hid.price / 1000).round() * 1000
    hid = hid[hid.price < C.VALUE_SCORE_MAX_PRICE].head(227)
    vin.loc[vin.gnaf_id.isin(hid.gnaf_id), ["bedrooms", "bathrooms", "car_spaces"]] = \
        f.loc[f.gnaf_id.isin(hid.gnaf_id), ["bedrooms_true", "bathrooms_true", "car_true"]].to_numpy()

    # "For Sale" adverts: some flats were listed before their sale (incl. Aug for hidden ones)
    lst = pd.concat([s.sample(frac=0.4, random_state=5), hid.sample(frac=0.6, random_state=6)])
    lst = lst.copy()
    lst["date"] = lst["date"] - pd.to_timedelta(rng.integers(14, 60, len(lst)), unit="D")
    lst["price"] = (lst["price"] * np.exp(rng.normal(0.01, 0.04, len(lst))) / 1000).round() * 1000
    lst["type"] = "For Sale"
    lst = lst[lst.date <= C.VALUE_CUTOFF]  # the supplied file stops at the task date (GUESS)
    sales = pd.concat([s, lst], ignore_index=True).sort_values(["gnaf_id", "date"])
    sales_out = pd.DataFrame({
        "gnaf_id": sales.gnaf_id, "address": sales.address,
        "date": sales.date.dt.strftime("%Y-%m-%d"), "price": sales.price.astype(int),
        "type": sales.type, "bedrooms": sales.bedrooms_true,
        "bathrooms": sales.bathrooms_true, "car_spaces": sales.car_true,
    })
    sold = sales_out[sales_out.type == "Sold"].sort_values(["gnaf_id", "date"])
    prev = sold.groupby("gnaf_id").shift(1)
    rep = pd.DataFrame({"gnaf_id": sold.gnaf_id, "date_1": prev.date, "price_1": prev.price,
                        "date_2": sold.date, "price_2": sold.price}).dropna()
    rep["price_1"] = rep.price_1.astype(int)

    # ---------------- Task 4 input ----------------
    in_city = f[f.is_flat].sample(N_RENTS - N_RENTS_OUTSIDE, random_state=21)
    outside = f[f.is_flat].sample(N_RENTS_OUTSIDE, random_state=22).copy()
    outside["gnaf_id"] = [f"GANSW9{x:08d}" for x in rng.choice(10**8, len(outside), replace=False)]
    outside["mb"] = rng.integers(10_000_000_000, 10_999_999_999, len(outside)).astype(str)
    outside["lat"] -= 0.03
    rf = pd.concat([in_city, outside], ignore_index=True)
    leases, advertised = make_leases(rf, rf.gnaf_id.to_numpy())
    car_known = rng.random(len(rf)) > 5_793 / N_RENTS
    fl_known = rng.random(len(rf)) < 34_396 / N_RENTS
    rin = pd.DataFrame({
        "gnaf_id": rf.gnaf_id,
        "address": (rf.address.str.upper() + " " + rf.suburb.str.replace(" (NSW)", "").str.upper()
                    + " " + rf.postcode),
        "building_address": rf.street_address.str.upper(),
        "suburb": rf.suburb, "mb": rf.mb,
        "latitude": rf.lat.round(8), "longitude": rf.lon.round(8),
        "property_type": np.where(rf.bedrooms_true == 0, "studio",
                                  rng.choice(["apartment", "unit"], len(rf), p=[.7, .3])),
        "bedrooms": rf.bedrooms_true, "bathrooms": rf.bathrooms_true,
        "car_space": np.where(car_known, rf.car_true, np.nan),
        "car_spaces": np.where(car_known, rf.car_true, np.nan),
        "floor_level": np.where(fl_known, rf.floor, np.nan),
        "flats_in_building": rf.groupby("b_id")["gnaf_id"].transform("size"),
        "block_new_homes_2021_2026": np.where(rf.gnaf_id.str.startswith("GANSW9"), np.nan,
                                              rng.poisson(20, len(rf))),
        "block_homes_2026": np.where(rf.gnaf_id.str.startswith("GANSW9"), np.nan,
                                     rng.integers(50, 900, len(rf))),
        "ever_advertised_for_lease": rf.gnaf_id.isin(advertised.gnaf_id).astype(int),
        "first_ever_listed": random_dates(len(rf), "2008-01-01", "2026-06-30").strftime("%Y-%m-%d"),
        "attrs_last_seen": random_dates(len(rf), "2020-01-01", "2026-07-30").strftime("%Y-%m-%d"),
    })

    # hidden judging adverts: 1 Aug - 30 Sep 2026 (keep 1,699)
    hr = rf.sample(2_000, random_state=31).copy()
    hr["date"] = random_dates(len(hr), "2026-08-01", "2026-09-30")
    hr["price"] = np.exp(hr.logr_base + idx_at(RENT_IDX, hr.date) + rng.normal(0, 0.075, len(hr)))
    hr["price"] = (hr.price / 5).round() * 5
    hr["advert_car_space"] = np.where(rng.random(len(hr)) < 0.8, hr.car_true, np.nan)
    hr = hr.head(1_699)

    # the supplied lease file (GUESS) ends at the cut-off EXCEPT we leave a few later
    # rows in, on purpose, so the as-of filter is exercised
    leases_out = pd.DataFrame({
        "gnaf_id": leases.gnaf_id, "building_address": leases.street_address.str.upper(),
        "date": leases.date.dt.strftime("%Y-%m-%d"), "weekly_rent": leases.price,
        "bedrooms": leases.bedrooms_true, "bathrooms": leases.bathrooms_true,
        "car_spaces": leases.car_spaces,
    }).sort_values(["gnaf_id", "date"])

    blocks = pd.DataFrame({"mb": b.mb.unique()})
    blocks["homes_2021"] = rng.integers(30, 800, len(blocks))
    blocks["homes_2026"] = blocks.homes_2021 + rng.poisson(15, len(blocks))
    blocks["people_2021"] = (blocks.homes_2021 * rng.uniform(1.4, 2.4, len(blocks))).astype(int)
    blocks["people_2026"] = (blocks.homes_2026 * rng.uniform(1.4, 2.4, len(blocks))).astype(int)

    out = C.SUPPLIED
    vin.to_csv(out / C.FILES["value_input"], index=False)
    sales_out.to_csv(out / C.FILES["value_sales"], index=False)
    rep.to_csv(out / C.FILES["value_repeat"], index=False)
    rin.to_csv(out / C.FILES["rents_input"], index=False)
    leases_out.to_csv(out / C.FILES["rents_leases"], index=False)
    blocks.to_csv(out / C.FILES["blocks"], index=False)
    hid[["gnaf_id", "date", "price"]].to_csv(C.MOCK_HIDDEN / "sales.csv", index=False)
    hr[["gnaf_id", "date", "price", "advert_car_space"]].to_csv(C.MOCK_HIDDEN / "rents.csv", index=False)
    (out / "MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt").write_text(
        "Every file in this folder is synthetic. Replace with the emailed files on the day.\n")

    print(f"value input {len(vin):,} | sales {len(sales_out):,} ({(sales_out.type=='Sold').sum():,} sold) "
          f"| repeat pairs {len(rep):,}")
    print(f"rents input {len(rin):,} | leases {len(leases_out):,} | blocks {len(blocks):,}")
    print(f"mock hidden: {len(hid)} sales, {len(hr)} adverts -> {C.MOCK_HIDDEN}")


if __name__ == "__main__":
    main()
