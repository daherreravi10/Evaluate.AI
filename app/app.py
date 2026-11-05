"""Demo for demo.mp4: type an address, see the weekly rent with and without a
car space, the sale value, and why. Reads data/cache/app_*.parquet written by
src/rents.py and src/valuation.py.

streamlit run app/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as C  # noqa: E402

st.set_page_config(page_title="Sydney flats: rent and value", layout="wide")
KIND = {0: "its own For Sale advert", 1: "its own last price, moved to the task date",
        2: "flats with the same bedrooms in its building", 3: "its suburb and bedroom count"}


@st.cache_data
def load(name: str) -> pd.DataFrame | None:
    p = C.CACHE / f"app_{name}.parquet"
    return pd.read_parquet(p) if p.exists() else None


@st.cache_data
def metrics(name: str) -> dict | None:
    p = C.OUT / f"metrics_{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


rents, values = load("rents"), load("valuation")
if (C.SUPPLIED / "MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt").exists():
    st.warning("MOCK DATA: synthetic numbers for testing the app. Re-run the pipelines on the real files.")
st.title("What will this flat rent for, and what is it worth?")
st.caption("City of Sydney flats · rent as at 31 July 2026 · value as at 31 August 2026")

if rents is None and values is None:
    st.error("No results yet. Run `python -m src.rents` and `python -m src.valuation` first.")
    st.stop()

tab_flat, tab_map, tab_proof = st.tabs(["One flat", "Map", "How good is it?"])

with tab_flat:
    pool = rents if rents is not None else values
    q = st.text_input("Address", placeholder="e.g. 20 Dunkerley Place")
    hits = pool[pool.address.str.contains(q.strip(), case=False, regex=False)] if q.strip() else pool.head(0)
    if q.strip() and hits.empty:
        st.info("No flat matches that address.")
    if not hits.empty:
        label = hits.address + " · " + hits.suburb.fillna("")
        pick = st.selectbox("Pick the flat", hits.index[:200], format_func=lambda i: label[i])
        f = hits.loc[pick]
        c1, c2, c3 = st.columns(3)
        r = rents[rents.gnaf_id == f.gnaf_id] if rents is not None else pd.DataFrame()
        v = values[values.gnaf_id == f.gnaf_id] if values is not None else pd.DataFrame()
        if not r.empty:
            r = r.iloc[0]
            c1.metric("Weekly rent with a car space", f"${r.with_car:,.0f}")
            c2.metric("Without a car space", f"${r.without_car:,.0f}",
                      delta=f"car space worth ${r.with_car - r.without_car:,.0f}/wk", delta_color="off")
            st.write(f"Started from **{KIND.get(int(r.anchor_kind), 'the suburb')}**"
                     + (f" (${r.own_last:,.0f}/wk, {r.own_last_age_y:.1f} years ago, moved to July 2026)"
                        if r.anchor_kind == 1 else "")
                     + (f" ({int(r.bldg_bed_n)} adverts, median ${r.bldg_bed:,.0f}/wk)" if r.anchor_kind == 2 else "")
                     + ", then corrected for floor, size, building and neighbours.")
        if not v.empty:
            v = v.iloc[0]
            c3.metric("Sale value, 31 Aug 2026", f"${v.value:,.0f}")
            st.write(f"Value started from **{KIND.get(int(v.anchor_kind), 'the suburb')}**"
                     + (f" (${v.own_last:,.0f}, {v.own_last_age_y:.1f} years ago)" if v.anchor_kind == 1 else "")
                     + (f" (asking ${v.ask:,.0f})" if v.anchor_kind == 0 else "") + ".")
        cols = [c for c in ["bedrooms", "bathrooms", "car_space", "floor_level", "flats_in_building"] if c in f]
        st.dataframe(pd.DataFrame([f[cols]]), hide_index=True)

with tab_map:
    if rents is not None:
        b = rents.groupby("bkey").agg(lat=("latitude", "mean"), lon=("longitude", "mean"),
                                      prem=("with_car", lambda s: 0), n=("gnaf_id", "size"))
        b["prem"] = (rents.with_car - rents.without_car).groupby(rents.bkey).median()
        b = b.dropna(subset=["lat", "lon"]).reset_index()
        hi = max(float(b.prem.quantile(0.95)), 1.0)
        b["c"] = (b.prem.clip(0, hi) / hi * 255).astype(int)
        st.write("What a car space adds to weekly rent, building by building (darker = more).")
        st.pydeck_chart(pdk.Deck(
            map_style=None, initial_view_state=pdk.ViewState(latitude=-33.89, longitude=151.205, zoom=12.3),
            layers=[pdk.Layer("ScatterplotLayer", b, get_position="[lon, lat]", get_radius="20 + n * 0.6",
                              get_fill_color="[15, 118, 110, 40 + c * 0.8]", pickable=True)],
            tooltip={"text": "{bkey}\n{n} flats\n+${prem}/wk with a car space"}), width="stretch")

with tab_proof:
    for name, key, fmt in (("rents", "median_abs_error", lambda x: f"${x:,.0f}/wk median miss"),
                           ("valuation", "share_within_10pct", lambda x: f"{x:.1%} within 10%")):
        m = metrics(name)
        if not m:
            continue
        st.subheader("Task 4 · rents" if name == "rents" else "Task 5 · values")
        st.caption(f"Built before {m['split']}, tested on {m['test_rows']:,} later events up to {m['cutoff']}.")
        t = pd.DataFrame([{"method": k, "score": fmt(v[key]), "R²": round(v["r2"], 3)}
                          for k, v in m["heldout"].items()])
        st.dataframe(t, hide_index=True)
