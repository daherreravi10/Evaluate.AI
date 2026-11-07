"""Evaluate.AI — weekly rent (with and without a car space) and sale value for every flat in the
City of Sydney. The demo for demo.mp4 and pitch.mp4.

Reads data/cache/app_*.parquet (written by src/rents.py and src/valuation.py) and
outputs/metrics_*.json. Run locally only: it shows past prices from the private files.

streamlit run app/app.py
"""
from __future__ import annotations

import html
import json
import re
from urllib.parse import quote
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C  # noqa: E402
from src import neighbourhood as nb  # noqa: E402

st.set_page_config(page_title="Evaluate.AI — Sydney flats", page_icon="🅿️", layout="wide")

INK, MUTED, ASPHALT, KERB, EUCALYPT, RUST, BLUE = (
    "#1B2422", "#5E6965", "#2F3438", "#EDBB2A", "#2E6B5B", "#B4542D", "#3D6A9E")

CSS = f"""
<style>
/* Barlow, SIL Open Font License, served from app/static/fonts (works offline) */
@font-face {{ font-family: 'Barlow'; font-weight: 400; font-style: normal; font-display: swap; src: url('app/static/fonts/barlow-latin-400-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'Barlow'; font-weight: 500; font-style: normal; font-display: swap; src: url('app/static/fonts/barlow-latin-500-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'Barlow'; font-weight: 600; font-style: normal; font-display: swap; src: url('app/static/fonts/barlow-latin-600-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'Barlow Condensed'; font-weight: 500; font-style: normal; font-display: swap; src: url('app/static/fonts/barlow-condensed-latin-500-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'Barlow Condensed'; font-weight: 600; font-style: normal; font-display: swap; src: url('app/static/fonts/barlow-condensed-latin-600-normal.woff2') format('woff2'); }}

html, body, .stApp, .stMarkdown, p, li, label, input, button, textarea, h1, h2, h3, h4,
[data-testid="stTab"] p, [data-testid="stMetricValue"] {{ font-family: 'Barlow', system-ui, sans-serif !important; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: 1120px; padding-top: 1.6rem; padding-bottom: 4rem; }}
footer {{ visibility: hidden; }}
.brand {{ display: flex; align-items: center; gap: 14px; margin: 0 0 4px; }}
.brand svg {{ flex: none; }}
.brand h1 {{ font-family: 'Barlow Condensed', sans-serif !important; font-weight: 600; font-size: 46px;
            line-height: 1; margin: 0; padding: 0; color: {INK}; letter-spacing: .005em; }}
.lede {{ color: {MUTED}; font-size: 18px; margin: 2px 0 18px; max-width: 62ch; }}
.mock {{ background: #FFF6DB; border: 1px solid #EBD38A; color: #6B5310; border-radius: 8px;
        padding: 8px 12px; font-size: 14px; margin-bottom: 14px; }}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 22px; border-bottom: 1px solid #D6DCD8; }}
[data-testid="stTab"] p {{ font-size: 16px; font-weight: 600; }}
.flat-title {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 34px;
              line-height: 1.1; margin: 18px 0 2px; color: {INK}; }}
.flat-facts {{ color: {MUTED}; font-size: 16.5px; margin: 0 0 16px; }}
.bay {{ background: {ASPHALT}; border-radius: 16px; padding: 26px 28px 20px; color: #F2F3EF;
        background-image: radial-gradient(rgba(255,255,255,.035) 1px, transparent 1px);
        background-size: 5px 5px; }}
.bays {{ display: grid; grid-template-columns: 1fr 1fr; border-left: 5px solid {KERB}; }}
.slot {{ min-width: 0; }}
.slot {{ border-top: 5px solid {KERB}; border-right: 5px solid {KERB}; padding: 18px 22px 22px; }}
.slot .lbl {{ font-size: 16px; color: #C9CEC9; }}
.slot .num {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 66px;
             line-height: 1; margin-top: 6px; color: #FFFFFF; }}
.slot .num small {{ font-size: 22px; font-weight: 500; color: #C9CEC9; margin-left: 4px; }}
.slot.empty .num {{ color: #DADDD7; }}
.gap {{ margin-top: 16px; font-size: 18px; color: #E9EBE6; }}
.gap b {{ color: {KERB}; font-weight: 600; }}
.gap span {{ color: #AEB4AF; font-size: 15px; }}
.card {{ background: #FFFFFF; border: 1px solid #DCE2DE; border-radius: 12px; padding: 18px 20px; height: 100%; }}
.card h3 {{ font-size: 17px; font-weight: 600; margin: 0 0 6px; color: {INK}; padding: 0; }}
.card .big {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 48px;
             line-height: 1.05; color: {EUCALYPT}; }}
.card p {{ color: #3D4744; font-size: 15.5px; margin: 6px 0 0; }}
.card.sum .big {{ font-size: 40px; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }}
.card.tile .big {{ font-size: 34px; }}
.card.tile p {{ font-size: 14px; }}
.kv {{ display: grid; grid-template-columns: 1fr auto; gap: 0 12px; border-top: 1px solid #E6EBE8;
       padding: 9px 0 7px; margin-top: 8px; }}
.kv span {{ font-weight: 600; color: {INK}; }} .kv b {{ color: {EUCALYPT}; font-size: 18px; }}
.kv em {{ grid-column: 1 / -1; font-style: normal; color: #6B7571; font-size: 13.5px; }}
.card.sum .big small {{ font-family: Barlow, sans-serif; font-size: 15px; font-weight: 400; color: #6B7571; }}
.card.sum .tag {{ display: inline-block; font-size: 11.5px; font-weight: 600; letter-spacing: .08em;
                 border-radius: 4px; padding: 2px 7px; margin-bottom: 6px; }}
.card.rent {{ border-top: 4px solid {KERB}; }} .card.rent .tag {{ background: #FBF1D3; color: #7A5B00; }}
.card.sale {{ border-top: 4px solid {EUCALYPT}; }} .card.sale .tag {{ background: #DCEBE5; color: {EUCALYPT}; }}
.why ol {{ margin: 6px 0 0; padding-left: 20px; }}
.why li {{ font-size: 16px; margin: 6px 0; color: #2E3835; }}
.why li b {{ color: {INK}; }}
.verdict {{ font-family: 'Barlow Condensed', sans-serif; font-size: 30px; font-weight: 600; line-height: 1.1; margin: 4px 0 4px; }}
.scale {{ position: relative; height: 34px; margin: 14px 0 4px; }}
.scale .track {{ position: absolute; top: 14px; left: 0; right: 0; height: 6px; background: #E6EAE7; border-radius: 3px; }}
.scale .band {{ position: absolute; top: 10px; height: 14px; background: #CFE3DB; border-radius: 4px; }}
.scale .est {{ position: absolute; top: 4px; width: 2px; height: 26px; background: {EUCALYPT}; }}
.scale .you {{ position: absolute; top: 6px; width: 22px; height: 22px; margin-left: -11px; border-radius: 50%;
              border: 3px solid #fff; box-shadow: 0 0 0 1px #B9C2BE; }}
.scale-labels {{ display: flex; justify-content: space-between; color: {MUTED}; font-size: 13.5px; }}
.empty-state p {{ margin: 14px 0 2px; font-size: 16.5px; color: #3D4744; }}
.method {{ display: grid; grid-template-columns: 1fr 110px; gap: 4px 14px; align-items: center; margin: 10px 0 6px; }}
.method .name {{ font-size: 15.5px; color: #2E3835; }}
.method .name.ours {{ font-weight: 600; color: {INK}; }}
.method .bar {{ height: 12px; border-radius: 3px; background: #C9D1CD; }}
.method .bar.ours {{ background: {EUCALYPT}; }}
.method .val {{ font-family: 'Barlow Condensed', sans-serif; font-size: 20px; font-weight: 600; text-align: right; }}
.legend {{ display: flex; align-items: center; gap: 10px; color: {MUTED}; font-size: 14px; margin: 6px 0 10px; }}
.legend .ramp {{ width: 180px; height: 10px; border-radius: 3px;
                background: linear-gradient(90deg, #F3DE9A, {KERB}, #B5832A, {ASPHALT}); }}
@media (max-width: 640px) {{
  .bay {{ padding: 18px 16px 16px; }}
  .bays {{ grid-template-columns: 1fr; }}
  .slot {{ padding: 14px 16px 16px; }}
  .slot .num {{ font-size: 50px; }}
  .slot .num small {{ font-size: 18px; }}
  .brand h1 {{ font-size: 38px; }}
  .flat-title {{ font-size: 28px; }}
}}
.slot .num small {{ white-space: nowrap; }}
.around-title {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 28px; margin: 30px 0 2px; color: {INK}; }}
.mode {{ background: #FFFFFF; border: 1px solid #DCE2DE; border-radius: 12px; padding: 16px 18px; margin-bottom: 12px; }}
.mode h3 {{ font-size: 17px; font-weight: 600; margin: 0 0 8px; padding: 0; display: flex; align-items: center; gap: 8px; }}
.mode ul {{ list-style: none; margin: 0; padding: 0; }}
.mode li {{ display: flex; justify-content: space-between; gap: 12px; padding: 5px 0; border-top: 1px solid #EEF1EE; font-size: 15.5px; }}
.mode li:first-child {{ border-top: 0; }}
.mode li span:last-child {{ color: {MUTED}; text-align: right; white-space: nowrap; }}
.routes {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }}
.routes span {{ background: #E3EEEA; color: #1F4F43; border-radius: 4px; padding: 1px 7px; font-size: 13.5px; font-weight: 600; }}
.chip {{ font-style: normal; display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; color: #fff;
        font-size: 12.5px; font-weight: 600; flex: none; }}
.keyrow {{ display: flex; flex-wrap: wrap; gap: 6px 16px; color: {MUTED}; font-size: 14px; margin: 8px 0 4px; }}
.keyrow span {{ display: inline-flex; align-items: center; gap: 6px; }}
.trips {{ width: 100%; border-collapse: collapse; font-size: 15.5px; background: #fff; border: 1px solid #DCE2DE; border-radius: 12px; overflow: hidden; }}
.trips th {{ text-align: left; color: {MUTED}; font-weight: 600; font-size: 14px; padding: 9px 14px; border-bottom: 1px solid #DCE2DE; }}
.trips td {{ padding: 9px 14px; border-top: 1px solid #EEF1EE; }}
.trips td.n {{ font-variant-numeric: tabular-nums; }}
.trips a {{ color: {EUCALYPT}; font-weight: 600; text-decoration: none; }}
.proj li {{ display: block; }}
.proj .when {{ color: {MUTED}; font-size: 13.5px; }}
.fine {{ color: {MUTED}; font-size: 13.5px; margin-top: 28px; }}
</style>
"""

LOGO = f"""<svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">
<rect width="44" height="44" rx="9" fill="{ASPHALT}"/>
<path d="M9 36V9h26v27" fill="none" stroke="{KERB}" stroke-width="3.2"/>
<path d="M22 9v27" stroke="{KERB}" stroke-width="3.2" stroke-dasharray="4 3"/></svg>"""


# ------------------------------------------------------------------ data
@st.cache_data
def load_parquet(name: str) -> pd.DataFrame | None:
    p = C.CACHE / f"app_{name}.parquet"
    return pd.read_parquet(p) if p.exists() else None


@st.cache_data
def metrics(name: str) -> dict | None:
    p = C.OUT / f"metrics_{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def basemap() -> dict:
    """Street map behind the dots. KERBSIDE_BASEMAP=0 turns it off (no internet at the venue)."""
    import os
    if os.environ.get("KERBSIDE_BASEMAP", "1") == "0":
        blank = json.dumps({"version": 8, "sources": {}, "layers": [
            {"id": "paper", "type": "background", "paint": {"background-color": "#E6EBE8"}}]})
        return {"map_provider": "mapbox", "map_style": "data:application/json;charset=utf-8," + quote(blank)}
    osm = json.dumps({"version": 8, "sources": {"osm": {
        "type": "raster", "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], "tileSize": 256,
        "maxzoom": 19, "attribution": "\u00a9 OpenStreetMap contributors"}},
        "layers": [{"id": "osm", "type": "raster", "source": "osm",
                    "paint": {"raster-saturation": -0.75, "raster-brightness-min": 0.08}}]})
    return {"map_provider": "mapbox", "map_style": "data:application/json;charset=utf-8," + quote(osm)}


def tidy_address(a: str, suburb: str = "") -> str:
    """'UNIT 315, 2-4 POWELL STREET WATERLOO 2017' -> 'Unit 315, 2-4 Powell Street'."""
    a = str(a or "").strip()
    if a.isupper():
        a = a.title()
    a = re.sub(r"\s+\d{4}$", "", a)
    sub = str(suburb or "").replace(" (NSW)", "").strip()
    if sub and a.lower().endswith(" " + sub.lower()):
        a = a[: -len(sub)].rstrip()
    return a


@st.cache_data
def flats() -> pd.DataFrame:
    r, v = load_parquet("rents"), load_parquet("valuation")
    parts = []
    if r is not None:
        parts.append(r.add_prefix("r_").rename(columns={"r_gnaf_id": "gnaf_id"}))
    if v is not None:
        parts.append(v.add_prefix("v_").rename(columns={"v_gnaf_id": "gnaf_id"}))
    if not parts:
        return pd.DataFrame()
    df = parts[0] if len(parts) == 1 else parts[0].merge(parts[1], on="gnaf_id", how="outer")

    def pick(a, b):
        if a in df and b in df:
            return df[a].combine_first(df[b])
        return df[a] if a in df else df[b]

    df["suburb"] = pick("v_suburb", "r_suburb").fillna("").str.replace(" (NSW)", "", regex=False)
    raw = pick("v_address", "r_address").fillna("")
    df["label"] = [tidy_address(a, s) for a, s in zip(raw, df.suburb)]
    df["lat"] = pick("r_latitude", "v_latitude")
    df["lon"] = pick("r_longitude", "v_longitude")
    df["beds"] = pick("r_bedrooms", "v_bedrooms")
    df["baths"] = pick("r_bathrooms", "v_bathrooms")
    df["key"] = (df.label + " " + df.suburb).str.upper()
    if "v_is_flat" in df:
        df = df[df.v_is_flat.fillna(True).astype(bool)]
    return df.reset_index(drop=True)


def money(x: float, step: int = 1) -> str:
    return f"${round(x / step) * step:,.0f}"


# ------------------------------------------------------------------ pieces
def facts_line(f: pd.Series) -> str:
    bits = []
    if pd.notna(f.beds):
        b = int(f.beds)
        bits.append("studio" if b == 0 else f"{b} bedroom{'s' if b != 1 else ''}")
    if pd.notna(f.baths):
        n = int(f.baths)
        bits.append(f"{n} bathroom{'s' if n != 1 else ''}")
    fl = f.get("r_floor_level") if pd.notna(f.get("r_floor_level", np.nan)) else f.get("v_floor", np.nan)
    if pd.notna(fl):
        bits.append(f"floor {int(fl)}")
    size = f.get("r_flats_in_building", f.get("v_flats_in_building", np.nan))
    if pd.notna(size):
        bits.append(f"in a building of {int(size)} flats")
    return ", ".join(bits).capitalize() + (f", {html.escape(f.suburb)}" if f.suburb else "")


def bay_card(f: pd.Series) -> str:
    w, wo = float(f.r_with_car), float(f.r_without_car)
    gap = w - wo
    has = f.get("r_car_space")
    tag = "" if pd.isna(has) else (" This flat is listed with a car space." if has >= 1
                                   else " This flat is listed without one.")
    return f"""<div class="bay"><div class="bays">
<div class="slot"><div class="lbl">With a car space</div><div class="num">{money(w)}<small>a week</small></div></div>
<div class="slot empty"><div class="lbl">Without a car space</div><div class="num">{money(wo)}<small>a week</small></div></div>
</div><div class="gap">The car space is worth <b>{money(gap)} a week</b> here, about {money(gap * 52, 10)} a year.
<span>{tag}</span></div></div>"""


def rent_steps(f: pd.Series, m: dict | None) -> list[str]:
    kind = f.get("r_anchor_kind")
    a = f.get("r_anchor", np.nan)
    if kind == 1:
        first = (f"<b>Started from its own last advert</b>, {f.r_own_last_age_y:.1f} years ago, "
                 f"brought to July 2026 rents: {money(f.r_own_last)} a week.")
    elif kind == 2:
        first = (f"<b>Started from its building</b>: {int(f.r_bldg_bed_n)} adverts for flats with the same "
                 f"bedrooms, median {money(f.r_bldg_bed)} a week in July 2026 terms.")
    else:
        first = f"<b>Started from similar flats in {html.escape(f.suburb)}</b>: {money(a)} a week."
    own = f.r_with_car if f.get("r_car_space", 0) >= 1 else f.r_without_car
    ch = (own / a - 1) if pd.notna(a) and a > 0 else np.nan
    second = ("<b>Adjusted for this flat</b>: floor, size, building and nearby buildings "
              + (f"moved it {ch:+.0%}." if pd.notna(ch) else "set the final figure."))
    third = "<b>Priced twice</b>, with and without a car space; a car space can only add to the rent."
    steps = [first, second, third]
    if m:
        h = m["heldout"]["Our model (LightGBM, snapshots)"]
        steps.append(f"<b>How close it usually lands</b>: on {m['test_rows']:,} adverts it never saw, half were "
                     f"within {money(h['median_abs_error'])} a week of the asking rent.")
    return steps


def value_card(f: pd.Series, m: dict | None) -> str:
    kind = f.get("v_anchor_kind")
    if kind == 0:
        why = f"Started from its own For Sale advert before 31 August ({money(f.v_ask, 1000)})."
    elif kind == 1:
        why = (f"Started from its last sale, {f.v_own_last_age_y:.1f} years ago, brought to August 2026 "
               f"prices ({money(f.v_own_last, 1000)}).")
    elif kind == 2:
        n = int(f.v_bldg_bed_n)
        why = f"Started from {n} sale{'s' if n != 1 else ''} in its building ({money(f.v_bldg_bed, 1000)} median)."
    else:
        why = f"Started from similar flats in {html.escape(f.suburb)}."
    return f"""<div class="card"><h3>Estimated value, 31 August 2026</h3>
<div class="big">{money(f.v_value, 1000)}</div><p>{why}</p></div>"""


# ------------------------------------------------------------------ buildings (rent history)
REF = pd.Timestamp(C.RENT_CUTOFF)          # the files end here: "last 12 months" and "last month" count back from it
LEASED_WORDS = {"1", "1.0", "true", "yes", "y", "t", "leased"}


@st.cache_data(show_spinner="Reading rent history")
def building_data() -> pd.DataFrame:
    """One row per flat on the rent list, with its last advert. Read from the supplied files (local only)."""
    from src.loaders import load
    ri = load("rents_input")
    ri = ri[[c for c in ["gnaf_id", "address", "building_address", "suburb", "bedrooms", "bathrooms",
                         "car_space", "attrs_last_seen"] if c in ri]].copy()
    ri["bkey"] = ri.building_address.fillna("").str.upper().str.strip() + "|" + ri.suburb.fillna("").str.upper()
    ri["building"] = [tidy_address(a, s) for a, s in zip(ri.building_address.fillna(""), ri.suburb)]
    ri["suburb_clean"] = ri.suburb.fillna("").str.replace(" (NSW)", "", regex=False)
    ri["unit"] = [tidy_address(a, s) for a, s in zip(ri.address.fillna(""), ri.suburb)]
    try:
        le = load("rents_leases")
    except FileNotFoundError:
        le = None
    if le is not None and len(le):
        le = le[le.date.notna() & le.price.notna() & (le.date <= REF)].sort_values("date")
        last = le.groupby("gnaf_id").tail(1).set_index("gnaf_id")
        ri["last_rent"] = ri.gnaf_id.map(last.price)
        ri["last_date"] = ri.gnaf_id.map(last.date)
        ri["adverts"] = ri.gnaf_id.map(le.groupby("gnaf_id").size()).fillna(0).astype(int)
        if "was_leased" in last:
            ri["leased"] = ri.gnaf_id.map(last.was_leased.astype(str).str.strip().str.lower().isin(LEASED_WORDS))
    r = load_parquet("rents")
    if r is not None:
        est = r.set_index("gnaf_id")
        ri["est_with"] = ri.gnaf_id.map(est.with_car)
        ri["est_without"] = ri.gnaf_id.map(est.without_car)
    return ri


def status_flag(row: pd.Series) -> str:
    if pd.notna(row.get("last_date")) and row.last_date >= REF - pd.DateOffset(months=1):
        return "🔵 Listed now"
    if pd.isna(row.get("last_date")):
        return "⚪ No adverts"
    if row.get("leased") is True:
        return "🟢 Leased"
    return "🟡 Advertised"


def building_table(rows: pd.DataFrame, this_gnaf: str | None = None) -> pd.DataFrame:
    rows = rows.sort_values(["last_date", "unit"], ascending=[False, True], na_position="last")
    out = pd.DataFrame({
        "Flag": [("➡️ This flat · " if g == this_gnaf else "") + status_flag(r) for g, (_, r) in
                 zip(rows.gnaf_id, rows.iterrows())],
        "Unit": rows.unit,
        "Beds": rows.bedrooms.astype("Int64"),
        "Baths": rows.bathrooms.astype("Int64"),
        "Car space": rows.car_space.map(lambda x: "" if pd.isna(x) else ("Yes" if x >= 1 else "No")),
        "Last advertised rent": rows.get("last_rent", pd.Series(np.nan, index=rows.index)),
        "Advertised on": rows.get("last_date", pd.Series(pd.NaT, index=rows.index)).dt.date,
        "Adverts": rows.get("adverts", pd.Series(0, index=rows.index)),
        "Our estimate, with car": rows.get("est_with", pd.Series(np.nan, index=rows.index)),
        "Our estimate, without car": rows.get("est_without", pd.Series(np.nan, index=rows.index)),
        "Last seen": rows.attrs_last_seen.dt.date,
    })
    return out


def show_table(tab: pd.DataFrame) -> None:
    money_col = st.column_config.NumberColumn(format="$%d")
    st.dataframe(tab, hide_index=True, width="stretch",
                 column_config={"Last advertised rent": money_col, "Our estimate, with car": money_col,
                                "Our estimate, without car": money_col})


def building_block(f: pd.Series) -> None:
    """Change 2: other flats in this building with rent history, flagged."""
    bkey = f.get("r_bkey")
    if not isinstance(bkey, str) or not bkey.strip("|"):
        return
    bd = building_data()
    rows = bd[(bd.bkey == bkey) & bd.get("last_date", pd.Series(pd.NaT, index=bd.index)).notna()]
    st.markdown(f'<div class="card"><h3>Rent history in this building</h3><p>{len(rows):,} flat'
                f'{"s" if len(rows) != 1 else ""} in this building advertised for rent up to 31 July 2026. '
                '🔵 listed in July 2026 · 🟢 leased · 🟡 advertised.</p></div>', unsafe_allow_html=True)
    if len(rows):
        show_table(building_table(rows, f.gnaf_id))


# ------------------------------------------------------------------ decision helpers
@st.cache_data
def peer_medians() -> pd.DataFrame:
    """Median of our estimates by suburb x bedrooms x bathrooms (and city-wide), for like-for-like comparisons."""
    d = flats().copy()
    d["rent"] = d.get("r_without_car")
    d["val"] = d.get("v_value")
    d["b"] = d.beds.clip(upper=4)
    d["ba"] = d.baths.clip(upper=3)
    out = []
    for keys, scope in [(["suburb", "b", "ba"], "suburb"), (["b", "ba"], "city")]:
        g = d.groupby(keys).agg(rent=("rent", "median"), rent_n=("rent", "count"),
                                val=("val", "median"), val_n=("val", "count")).reset_index()
        out.append(g.assign(scope=scope))
    return pd.concat(out, ignore_index=True)


def peer(suburb: str, beds, baths, what: str) -> tuple[float, str]:
    """Median `what` (rent or val) for flats with these rooms: suburb if >= 8 flats, else city-wide."""
    if pd.isna(beds) or pd.isna(baths):
        return np.nan, ""
    pm = peer_medians()
    b, ba = min(int(beds), 4), min(int(baths), 3)
    s = pm[(pm.scope == "suburb") & (pm.suburb == suburb) & (pm.b == b) & (pm.ba == ba)]
    if len(s) and s[f"{what}_n"].iloc[0] >= 8:
        return float(s[what].iloc[0]), suburb
    c = pm[(pm.scope == "city") & (pm.b == b) & (pm.ba == ba)]
    return (float(c[what].iloc[0]), "the City") if len(c) and c[f"{what}_n"].iloc[0] >= 3 else (np.nan, "")


def room_card(f: pd.Series, what: str) -> str:
    """What one more bedroom / bathroom is worth for a flat like this (rent a week or sale value)."""
    unit, step = (" a week", 1) if what == "rent" else ("", 1000)
    base, where = peer(f.suburb, f.beds, f.baths, what)
    rows = []
    for label, db, dba in [("One more bedroom", 1, 0), ("One more bathroom", 0, 1)]:
        if pd.isna(f.beds) or pd.isna(f.baths) or (db and f.beds >= 4) or (dba and f.baths >= 3):
            continue
        more, where2 = peer(f.suburb, f.beds + db, f.baths + dba, what)
        if pd.notna(base) and pd.notna(more):
            d = more - base
            rows.append(f'<div class="kv"><span>{label}</span><b>{"+" if d >= 0 else "−"}{money(abs(d), step)}'
                        f'{unit}</b><em>{int(f.beds) + db} bed, {int(f.baths) + dba} bath: {money(more, step)}'
                        f'{unit} in {html.escape(where2)}</em></div>')
    if not rows:
        return ""
    head = "What one more room adds to the rent" if what == "rent" else "What one more room adds to the value"
    return (f'<div class="card"><h3>{head}</h3><p>Typical {int(f.beds)} bed, {int(f.baths)} bath flat in '
            f'{html.escape(where)}: {money(base, step)}{unit}. Medians of our estimates for flats like this one.</p>'
            + "".join(rows) + "</div>")


def sale_insights(f: pd.Series) -> str:
    v = float(f.v_value)
    tiles = [("Likely price range", f"{money(v * 0.9, 1000)} – {money(v * 1.1, 1000)}",
              "Within 10% either way: where two in three of our checked estimates landed.")]
    med, where = peer(f.suburb, f.beds, f.baths, "val")
    if pd.notna(med):
        d = v / med - 1
        tiles.append(("Against similar flats", f"{d:+.0%}",
                      f"Than the typical {int(f.beds)} bed, {int(f.baths)} bath flat in {html.escape(where)} "
                      f"({money(med, 1000)})."))
    if pd.notna(f.get("v_bldg_bed", np.nan)) and f.get("v_bldg_bed_n", 0) >= 1:
        d = v / float(f.v_bldg_bed) - 1
        tiles.append(("Against its building", f"{d:+.0%}",
                      f"Than the median sale for the same bedrooms in this building ({money(f.v_bldg_bed, 1000)})."))
    if "r_without_car" in f and pd.notna(f.r_without_car):
        rent = float(f.r_with_car if f.get("r_car_space", 0) >= 1 else f.r_without_car)
        y = rent * 52 / v
        d = flats()
        sy = (d.r_without_car * 52 / d.v_value)[d.suburb == f.suburb].median()
        tiles.append(("Gross rental yield", f"{y:.1%}",
                      f"{money(rent)} a week x 52 / value. Typical in {html.escape(f.suburb)}: {sy:.1%}."
                      if pd.notna(sy) else f"{money(rent)} a week x 52 / value."))
    if pd.notna(f.get("v_ask", np.nan)) and f.get("v_anchor_kind") == 0:
        d = v / float(f.v_ask) - 1
        tiles.append(("Against its asking price", f"{d:+.0%}",
                      f"It was advertised at {money(f.v_ask, 1000)} before 31 August."))
    return '<div class="tiles">' + "".join(
        f'<div class="card tile"><h3>{a}</h3><div class="big">{b}</div><p>{c}</p></div>' for a, b, c in tiles) + "</div>"


def summary_cards(f: pd.Series) -> None:
    has_rent = "r_with_car" in f and pd.notna(f.r_with_car)
    has_value = "v_value" in f and pd.notna(f.v_value)
    c1, c2, c3 = st.columns(3, gap="medium")
    c1.markdown('<div class="card sum rent"><div class="tag">RENT</div><h3>With a car space</h3>'
                f'<div class="big">{money(f.r_with_car) if has_rent else "n/a"}<small> a week</small></div>'
                '</div>', unsafe_allow_html=True)
    c2.markdown('<div class="card sum rent"><div class="tag">RENT</div><h3>Without a car space</h3>'
                f'<div class="big">{money(f.r_without_car) if has_rent else "n/a"}<small> a week</small>'
                '</div></div>', unsafe_allow_html=True)
    c3.markdown('<div class="card sum sale"><div class="tag">SALE</div><h3>Estimated value</h3>'
                f'<div class="big">{money(f.v_value, 1000) if has_value else "n/a"}</div></div>',
                unsafe_allow_html=True)


KIND_COLOR = {  # letter colour by what it is for
    "hospital": [180, 84, 45], "mall": [61, 106, 158], "supermarket": [61, 106, 158],
    "train": [46, 107, 91], "metro": [46, 107, 91], "light_rail": [46, 107, 91], "ferry": [46, 107, 91],
    "bus": [46, 107, 91], "park": [94, 140, 74], "school": [94, 105, 101], "university": [94, 105, 101],
    "construction": [237, 187, 42],
}
KEY = [("H", "hospital", "Hospital"), ("M", "mall", "Shopping centre"), ("S", "supermarket", "Supermarket"),
       ("T", "train", "Train or metro"), ("L", "light_rail", "Light rail"), ("F", "ferry", "Ferry"),
       ("E", "school", "School"), ("P", "park", "Park"), ("C", "construction", "Being built")]


def hexc(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb)


def embed_html(page: str, height: int) -> None:
    """st.iframe on new Streamlit, components.html on older ones (removed in recent releases)."""
    if hasattr(st, "iframe"):
        st.iframe(page, height=height)
    else:
        import streamlit.components.v1 as components

        components.html(page, height=height)


@st.cache_resource
def leaflet_assets() -> tuple[str, str]:
    d = Path(__file__).parent / "static" / "leaflet"
    return (d / "leaflet.js").read_text(encoding="utf-8"), (d / "leaflet.css").read_text(encoding="utf-8")


def leaflet_map(lat: float, lon: float, label: str, show: pd.DataFrame, buses: pd.DataFrame) -> str:
    """Self-contained Leaflet map (library inlined, so it works offline; street tiles need internet)."""
    js, css = leaflet_assets()
    pts = [{"lat": r.lat, "lon": r.lon, "l": r.letter, "c": hexc(KIND_COLOR.get(r.kind, [90, 90, 90])),
            "ink": "#1B2422" if r.kind == "construction" else "#FFFFFF", "tip": r.tip} for r in show.itertuples()]
    bus = [{"lat": r.lat, "lon": r.lon, "tip": r.tip} for r in buses.itertuples()]
    data = json.dumps({"lat": lat, "lon": lon, "label": label, "pts": pts, "bus": bus}).replace("</", "<\\/")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}
html,body,#m{{margin:0;height:100%;background:#E6EBE8;font-family:Barlow,Arial,sans-serif}}
#m{{border-radius:12px;overflow:hidden}}
.pin{{width:24px;height:24px;border-radius:50%;border:2.5px solid #fff;display:grid;place-items:center;
font:700 12.5px/1 Arial,Helvetica,sans-serif;box-shadow:0 1px 3px rgba(0,0,0,.35)}}
.home{{width:20px;height:20px;border-radius:50%;background:#2F3438;border:5px solid #EDBB2A;
box-shadow:0 1px 4px rgba(0,0,0,.4)}}
.leaflet-tooltip{{font:13px/1.3 Barlow,Arial,sans-serif}}
.leaflet-tile-pane{{filter:grayscale(.75) brightness(1.06) contrast(.92)}}</style></head><body><div id="m"></div>
<script>{js}</script><script>
const D={data};
const map=L.map('m',{{zoomControl:true,attributionControl:true,zoomSnap:0.25}}).setView([D.lat,D.lon],14.75);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
 {{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}}).addTo(map);
[[620,'10 min walk'],[310,'5 min walk']].forEach(([r,t])=>L.circle([D.lat,D.lon],{{radius:r,color:'#2F3438',
 weight:1.2,opacity:.45,fill:false,dashArray:'4 5'}}).bindTooltip(t).addTo(map));
D.bus.forEach(b=>L.circleMarker([b.lat,b.lon],{{radius:3.5,color:'#fff',weight:1,fillColor:'#2E6B5B',
 fillOpacity:.75}}).bindTooltip(b.tip).addTo(map));
D.pts.forEach(p=>L.marker([p.lat,p.lon],{{icon:L.divIcon({{className:'',iconSize:[24,24],iconAnchor:[12,12],
 html:`<div class="pin" style="background:${{p.c}};color:${{p.ink}}">${{p.l}}</div>`}})}}).bindTooltip(p.tip).addTo(map));
L.marker([D.lat,D.lon],{{icon:L.divIcon({{className:'',iconSize:[30,30],iconAnchor:[15,15],
 html:'<div class="home"></div>'}}),zIndexOffset:1000}}).bindTooltip(D.label).addTo(map);
</script></body></html>"""


@st.cache_data
def places_df():
    return nb.load_places()


@st.cache_data(show_spinner=False)
def live_transport(gnaf_id: str):
    return nb.api_transport(gnaf_id)


@st.cache_data(show_spinner=False)
def live_developments(suburb: str):
    return nb.api_developments(suburb)


def around(f: pd.Series) -> None:
    pl = places_df()
    if pl is None or pd.isna(f.lat):
        st.markdown('<div class="around-title">Around this flat</div><p class="flat-facts">Run '
                    '<code>python scripts/fetch_exo.py places</code> and <code>python -m src.exo.build</code> '
                    'to see what is nearby.</p>', unsafe_allow_html=True)
        return
    lat, lon = float(f.lat), float(f.lon)
    near = nb.nearby(lat, lon, pl, radius_km=1.6)
    st.markdown('<div class="around-title">Around this flat</div><p class="flat-facts">Rent and price are not '
                'everything: how you get around, what is close, and what is being built nearby.</p>',
                unsafe_allow_html=True)
    left, right = st.columns([1.25, 1], gap="medium")

    with left:
        show = near[(near.kind != "bus") & ((near.kind != "park") | (near.dist_km <= 0.8))]
        show = show[(show.dist_km <= 1.2) | show.kind.isin(["hospital", "mall", "train", "metro", "ferry"])]
        show = show.assign(tip=show.label + ": " + show.name.where(show.name != "", show.label) +
                               " (" + show.walk.astype(str) + " min walk)")
        buses = near[(near.kind == "bus") & (near.dist_km <= 0.8)]
        buses = buses.assign(tip="Bus stop " + buses.name + ": " +
                             buses.routes.where(buses.routes != "", "routes not listed"))
        embed_html(leaflet_map(lat, lon, f.label, show, buses), height=430)
        keys = "".join(f'<span><i class="chip" style="background:{hexc(KIND_COLOR[k])};'
                       f'{"color:#1B2422" if k == "construction" else ""}">{l}</i>{t}</span>'
                       for l, k, t in KEY)
        st.markdown(f'<div class="keyrow">{keys}<span><i class="chip" style="background:#2F3438;'
                    f'box-shadow:0 0 0 3px {KERB} inset"></i>This flat</span>'
                    '<span>Rings: 5 and 10 minutes on foot</span></div>', unsafe_allow_html=True)

    with right:
        live = live_transport(f.gnaf_id)
        rows = []
        rail = nb.nearest(pl, lat, lon, ("train", "metro"))
        if live and live.get("nearest", {}).get("train"):
            t = live["nearest"]["train"]
            d = t["distance_m"] / 1000
            rows.append(("Train or metro", f"{t.get('name') or t.get('label')}, {nb.walk_min(d)} min walk"))
        elif rail is not None:
            rows.append(("Train or metro", f"{rail['name']}, {rail['walk']} min walk"))
        for kind, label in (("light_rail", "Light rail"), ("ferry", "Ferry")):
            x = nb.nearest(pl, lat, lon, (kind,))
            if x is not None and x["dist_km"] <= 1.5:
                rows.append((label, f"{x['name'] or label}, {x['walk']} min walk"))
        n_stops, routes = nb.bus_routes(near)
        shop = nb.nearest(pl, lat, lon, ("supermarket",))
        if shop is not None:
            rows.append(("Supermarket", f"{shop['walk']} min walk"))
        trips = nb.travel(lat, lon)
        cbd = trips.iloc[0]
        rows.append(("To the CBD", f"about {cbd.bike} min by bike" + (f", {int(cbd.walk)} on foot" if pd.notna(cbd.walk) else "")))
        lis = "".join(f"<li><span>{html.escape(a)}</span><span>{html.escape(b)}</span></li>" for a, b in rows)
        bus = (f'<li style="display:block"><span>Buses: {n_stops} stop{"s" if n_stops != 1 else ""} within 5 minutes'
               + (f'</span><div class="routes">{"".join(f"<span>{html.escape(r)}</span>" for r in routes[:14])}</div>'
                  if routes else " (routes not listed)</span>") + "</li>") if n_stops else ""
        st.markdown(f'<div class="mode"><h3>Without a car</h3><ul>{lis}{bus}</ul></div>', unsafe_allow_html=True)

        prem = (f.r_with_car - f.r_without_car) if "r_with_car" in f and pd.notna(f.r_with_car) else None
        car_rows = []
        if prem is not None:
            car_rows.append(("A car space here", f"{money(prem)} a week"))
        for _, t in trips.iloc[[0, 1, 4]].iterrows():
            car_rows.append((t.place.replace(" (Martin Place)", ""), f"about {t.drive} min drive"))
        lis = "".join(f"<li><span>{html.escape(a)}</span><span>{html.escape(b)}</span></li>" for a, b in car_rows)
        st.markdown(f'<div class="mode"><h3>With a car</h3><ul>{lis}</ul></div>', unsafe_allow_html=True)

        close = []
        for kind, label in (("hospital", "Hospital"), ("mall", "Shopping centre"), ("school", "School"),
                            ("park", "Park")):
            x = nb.nearest(pl, lat, lon, (kind,))
            if x is not None:
                where = f"{x['dist_km']:.1f} km" if x["dist_km"] >= 1 else f"{x['walk']} min walk"
                close.append((f"{label}" + (f": {x['name']}" if x["name"] else ""), where))
        lis = "".join(f"<li><span>{html.escape(a)}</span><span>{html.escape(b)}</span></li>" for a, b in close)
        st.markdown(f'<div class="mode"><h3>Closest</h3><ul>{lis}</ul></div>', unsafe_allow_html=True)

    # trips
    body = "".join(
        f'<tr><td>{html.escape(t.place)}</td><td class="n">{t.km:.1f} km</td><td class="n">{t.drive} min</td>'
        f'<td class="n">{t.bike} min</td><td class="n">{(str(int(t.walk)) + " min") if pd.notna(t.walk) else ""}</td>'
        f'<td><a href="{t.transit_link}" target="_blank" rel="noopener">Public transport times</a></td></tr>'
        for t in trips.itertuples())
    st.markdown(f'<p class="flat-facts" style="margin:18px 0 6px"><b>Getting to the places people ask about.</b> '
                'Rough estimates from distance, not a journey planner; the links open real trip times.</p>'
                f'<table class="trips"><thead><tr><th>To</th><th>Distance</th><th>Car</th><th>Bike</th>'
                f'<th>On foot</th><th></th></tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)

    # projects
    proj = near[(near.kind == "construction") & (near.dist_km <= 1.5)].head(6)
    das = live_developments(f.suburb)
    items = "".join(
        f'<li><b>{html.escape(p.name or p.detail.capitalize() or "Construction site")}</b>'
        f'{(" · " + html.escape(p.detail)) if p.name and p.detail else ""}'
        f'<div class="when">{p.dist_km:.1f} km away, being built now</div></li>' for p in proj.itertuples())
    if das:
        items += "".join(
            f'<li><b>{html.escape(str(d.get("category") or "Development application"))}</b>: '
            f'{html.escape(str(d["description"])[:160])}<div class="when">Lodged {html.escape(str(d.get("date", ""))[:10])}'
            f' in {html.escape(f.suburb)}</div></li>' for d in das)
    if items:
        st.markdown(f'<div class="mode proj" style="margin-top:14px"><h3>What could change the area</h3>'
                    f'<ul>{items}</ul><p class="when" style="color:{MUTED};font-size:13.5px;margin:8px 0 0">'
                    'New stations and shops tend to lift rents and prices; years of building work nearby can '
                    'hold them back. Applications are proposals: not all get built.</p></div>',
                    unsafe_allow_html=True)


def fair_rent(f: pd.Series, m: dict | None) -> None:
    st.markdown('<div class="card"><h3>Is this rent fair?</h3>'
                '<p>Type the weekly rent you were quoted for this flat.</p></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    quoted = c1.number_input("Weekly rent quoted ($)", min_value=0, max_value=20_000, value=0, step=10,
                             key=f"q_{f.gnaf_id}")
    car = c2.radio("Does it come with a car space?", ["Yes", "No"], horizontal=True,
                   index=0 if f.get("r_car_space", 0) >= 1 else 1, key=f"c_{f.gnaf_id}")
    if not quoted:
        return
    est = float(f.r_with_car if car == "Yes" else f.r_without_car)
    band = float(m["heldout"]["Our model (LightGBM, snapshots)"]["median_abs_error"]) if m else 0.1 * est
    diff = quoted - est
    if abs(diff) <= band:
        verdict, color = "In line with similar flats", EUCALYPT
        note = f"Within {money(band)} of our estimate of {money(est)}, the range half our test rents fell in."
    elif diff > 0:
        verdict, color = f"{money(diff)} a week above what we'd expect", RUST
        note = f"Our estimate is {money(est)}. That is {money(diff * 52, 10)} a year more, worth asking about."
    else:
        verdict, color = f"{money(-diff)} a week below what we'd expect", BLUE
        note = f"Our estimate is {money(est)}. A good price, or something about the flat we can't see."
    lo, hi = est - 3 * band, est + 3 * band
    pos = lambda x: 100 * (min(max(x, lo), hi) - lo) / (hi - lo)  # noqa: E731
    st.markdown(f"""<div class="card"><div class="verdict" style="color:{color}">{verdict}</div>
<p>{note}</p>
<div class="scale"><div class="track"></div>
<div class="band" style="left:{pos(est - band)}%;width:{pos(est + band) - pos(est - band)}%"></div>
<div class="est" style="left:{pos(est)}%"></div>
<div class="you" style="left:{pos(quoted)}%;background:{color}"></div></div>
<div class="scale-labels"><span>{money(lo)}</span><span>our estimate {money(est)}</span><span>{money(hi)}</span></div>
</div>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ page
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f'<div class="brand">{LOGO}<h1>Evaluate.AI</h1></div>'
            '<p class="lede">What every flat in the City of Sydney should rent for, with and without a car '
            'space, and what it would sell for.</p>', unsafe_allow_html=True)
if (C.SUPPLIED / "MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt").exists():
    st.markdown('<div class="mock">Practice data: these numbers are synthetic. Re-run the pipelines on the '
                'real files before recording.</div>', unsafe_allow_html=True)

df = flats()
if df.empty:
    st.error("No results yet. Run python -m src.rents and python -m src.valuation, then reload.")
    st.stop()
mr, mv = metrics("rents"), metrics("valuation")

tab_flat, tab_map, tab_proof = st.tabs(["Look up a flat", "Car spaces across the city",
                                        "How accurate it is"])

with tab_flat:
    q = st.text_input("Street address", key="q", placeholder="Start typing a street, like Powell Street",
                       label_visibility="collapsed")
    if not q.strip():
        ex = df[df.r_anchor_kind.eq(1) & df.v_value.notna()] if "v_value" in df and "r_anchor_kind" in df else df
        ex = ex.sample(min(3, len(ex)), random_state=3) if len(ex) else ex
        st.markdown('<div class="empty-state"><p>Type part of an address to find a flat, '
                    'or open one of these:</p></div>', unsafe_allow_html=True)
        cols = st.columns(len(ex) or 1)
        for c, (_, f) in zip(cols, ex.iterrows()):
            c.button(f"{f.label}, {f.suburb}", key=f"ex_{f.gnaf_id}", width="stretch",
                     on_click=lambda label=f.label: st.session_state.update(q=label))
    else:
        hits = df[df.key.str.contains(q.strip().upper(), regex=False)]
        if hits.empty:
            st.info("No flat matches that address. Try just the street name.")
        else:
            hits = hits.sort_values("label").head(300)
            if len(hits) > 1:
                pick = st.selectbox(f"{len(hits):,} flats match" + (" (first 300)" if len(hits) == 300 else ""),
                                    hits.index, format_func=lambda i: f"{hits.at[i, 'label']}, {hits.at[i, 'suburb']}")
            else:
                pick = hits.index[0]
            f = df.loc[pick]
            st.markdown(f'<div class="flat-title">{html.escape(f.label)}</div>'
                        f'<p class="flat-facts">{facts_line(f)}</p>', unsafe_allow_html=True)
            has_rent = "r_with_car" in f and pd.notna(f.r_with_car)
            has_value = "v_value" in f and pd.notna(f.v_value)

            # quick view: both purposes at a glance
            summary_cards(f)
            st.write("")

            # detail: one purpose at a time
            options = (["Rent"] if has_rent else []) + (["Sale"] if has_value else [])
            mode = st.segmented_control("Details for", options, default=options[0] if options else None,
                                        key=f"mode_{f.gnaf_id}") if options else None
            mode = mode or (options[0] if options else None)
            if mode == "Rent":
                st.markdown(bay_card(f), unsafe_allow_html=True)
                st.write("")
                st.markdown('<div class="card why"><h3>How we got the rent</h3><ol>' +
                            "".join(f"<li>{s}</li>" for s in rent_steps(f, mr)) + "</ol></div>",
                            unsafe_allow_html=True)
                rc = room_card(f, "rent")
                if rc:
                    st.write("")
                    st.markdown(rc, unsafe_allow_html=True)
                st.write("")
                fair_rent(f, mr)
                st.write("")
                building_block(f)
            elif mode == "Sale":
                st.markdown(sale_insights(f), unsafe_allow_html=True)
                st.write("")
                left, right = st.columns([1, 1], gap="medium")
                left.markdown(value_card(f, mv), unsafe_allow_html=True)
                vc = room_card(f, "val")
                if vc:
                    right.markdown(vc, unsafe_allow_html=True)
            if not has_rent:
                st.caption("This flat is not on the rent list, so it has an estimated value only.")
            if not has_value:
                st.caption("This flat is not in the City of Sydney sales list, so it has rent estimates only.")
            st.write("")
            around(f)

with tab_map:
    if "r_with_car" not in df:
        st.info("Run python -m src.rents to see the map.")
    else:
        r = df.dropna(subset=["r_with_car", "lat", "lon"]).copy()
        r["prem"] = r.r_with_car - r.r_without_car
        b = r.groupby("r_bkey").agg(lat=("lat", "mean"), lon=("lon", "mean"), prem=("prem", "median"),
                                    flats=("gnaf_id", "size"), addr=("label", "first"),
                                    suburb=("suburb", "first")).reset_index()
        b["addr"] = b.addr.str.replace(r"^[^,]*,\s*", "", regex=True)
        lo, hi = np.percentile(b.prem, [5, 95])
        t = ((b.prem - lo) / max(hi - lo, 1)).clip(0, 1).to_numpy()
        stops = np.array([[243, 222, 154], [237, 187, 42], [181, 131, 42], [47, 52, 56]], float)
        seg = np.minimum((t * 3).astype(int), 2)
        frac = (t * 3 - seg)[:, None]
        rgb = stops[seg] * (1 - frac) + stops[seg + 1] * frac
        b["color"] = [list(map(int, c)) + [215] for c in rgb]
        b["prem_txt"] = b.prem.map(lambda x: f"${x:,.0f}")
        sub_med = r.groupby("suburb").prem.median().sort_values(ascending=False)
        st.markdown(f'<div class="flat-title" style="margin-top:6px">What a car space adds to the rent</div>'
                    f'<p class="flat-facts">Median across the City: <b>{money(r.prem.median())} a week</b>. '
                    f'Highest in {html.escape(sub_med.index[0])} ({money(sub_med.iloc[0])}), lowest in '
                    f'{html.escape(sub_med.index[-1])} ({money(sub_med.iloc[-1])}). One dot per building.</p>'
                    f'<div class="legend">{money(lo)}<div class="ramp"></div>{money(hi)} a week</div>',
                    unsafe_allow_html=True)
        pc = (mr or {}).get("parking_check") or {}
        if pc.get("pairs"):
            st.markdown(f'<div class="card" style="margin:4px 0 12px"><h3>Checked against the raw adverts</h3>'
                        f'<p>In the same building, with the same bedrooms, adverts with a car space asked a median '
                        f'<b>{money(pc["raw_median"])} a week</b> more than adverts without one '
                        f'({pc["pairs"]:,} like-for-like comparisons, last three years). The map shows our '
                        f'estimate, which is more cautious: {money(pc["model_median"])} for the same flats.</p></div>',
                        unsafe_allow_html=True)
        st.caption("Click a dot to list the flats in that building.")
        ev = st.pydeck_chart(pdk.Deck(
            **basemap(),
            initial_view_state=pdk.ViewState(latitude=float(b.lat.median()), longitude=float(b.lon.median()),
                                             zoom=12.6, pitch=0),
            layers=[pdk.Layer("ScatterplotLayer", b, id="buildings", get_position="[lon, lat]",
                              get_fill_color="color",
                              get_radius="18 + flats * 0.35", radius_min_pixels=2.5, pickable=True,
                              stroked=True, get_line_color=[255, 255, 255, 160], line_width_min_pixels=0.5)],
            tooltip={"html": "<b>{addr}</b><br/>{suburb}<br/>{flats} flats<br/>car space adds {prem_txt} a week",
                     "style": {"fontFamily": "Barlow, sans-serif", "fontSize": "13px"}}), height=560,
            on_select="rerun", selection_mode="single-object", key="carmap")
        try:
            objs = (ev.selection.get("objects") or {}).get("buildings") or []
        except Exception:  # noqa: BLE001
            objs = []
        if objs:
            bk = objs[0].get("r_bkey")
            rows = r[r.r_bkey == bk].sort_values("label")
            st.markdown(f'<div class="flat-title">{html.escape(str(objs[0].get("addr", "")))}</div>'
                        f'<p class="flat-facts">{len(rows)} flats · {html.escape(str(objs[0].get("suburb", "")))} · '
                        'click a flat to open it in <b>Look up a flat</b></p>', unsafe_allow_html=True)
            tab = pd.DataFrame({
                "Flat": rows.label, "Beds": rows.beds.astype("Int64"), "Baths": rows.baths.astype("Int64"),
                "Car space": rows.r_car_space.map(lambda x: "" if pd.isna(x) else ("Yes" if x >= 1 else "No")),
                "With car": rows.r_with_car, "Without car": rows.r_without_car,
                "Car space adds": rows.prem}).reset_index(drop=True)
            labels = rows.label.tolist()

            def open_flat(labels=labels):
                sel = st.session_state.get("carlist")
                try:
                    picked = sel["selection"]["rows"]
                except Exception:  # noqa: BLE001
                    picked = getattr(getattr(sel, "selection", None), "rows", []) or []
                if picked:
                    st.session_state["q"] = labels[picked[0]]
                    st.session_state["opened_from_map"] = labels[picked[0]]

            mc = st.column_config.NumberColumn(format="$%d")
            st.dataframe(tab, hide_index=True, width="stretch", key="carlist", on_select=open_flat,
                         selection_mode="single-row",
                         column_config={"With car": mc, "Without car": mc, "Car space adds": mc})
            if st.session_state.get("opened_from_map"):
                st.success(f"Opened {st.session_state['opened_from_map']}: go to the Look up a flat tab "
                           "to see its rent and value in detail.")

with tab_proof:
    def method_rows(m: dict, key: str, fmt, higher_better: bool) -> str:
        items = list(m["heldout"].items())
        vals = [v[key] for _, v in items]
        top = max(vals) if higher_better else max(vals) * 1.05
        rows = ""
        chosen = m.get("handin", "Our model (LightGBM, snapshots)")
        for name, v in items:
            ours = name == chosen
            label = "Evaluate.AI" if ours else name
            w = 100 * v[key] / top
            rows += (f'<div class="name{" ours" if ours else ""}">{html.escape(label)}'
                     f'<div class="bar{" ours" if ours else ""}" style="width:{w:.0f}%"></div></div>'
                     f'<div class="val">{fmt(v[key])}</div>')
        return f'<div class="method">{rows}</div>'

    c1, c2 = st.columns(2, gap="large")
    if mr:
        with c1:
            st.markdown(f'<div class="card"><h3>Weekly rent: typical miss</h3><p>Built from adverts before '
                        f'{mr["split"]}, tested on {mr["test_rows"]:,} later adverts up to {mr["cutoff"]}. '
                        f'Lower is better.</p>'
                        + method_rows(mr, "median_abs_error", lambda x: f"${x:,.0f}", False) + "</div>",
                        unsafe_allow_html=True)
    if mv:
        with c2:
            d5, _, d95 = mv["model_within10_227_draws"]
            st.markdown(f'<div class="card"><h3>Sale value: within 10% of the price</h3><p>Built from sales '
                        f'before {mv["split"]}, tested on {mv["test_rows"]:,} later flat sales under $1.2M. '
                        f'Higher is better.</p>'
                        + method_rows(mv, "share_within_10pct", lambda x: f"{x:.0%}", True) +
                        f'<p>The judges score 227 sales. Drawing 227 of ours at random, the same model scores '
                        f'between {d5:.0%} and {d95:.0%}, so a few points either way is luck.</p></div>',
                        unsafe_allow_html=True)

st.markdown('<p class="fine">Estimates are automated and indicative only. Data © Microburbs; map © OpenStreetMap '
            'contributors, © CARTO. Built for the Microburbs Hackathon, 7 November 2026.</p>',
            unsafe_allow_html=True)