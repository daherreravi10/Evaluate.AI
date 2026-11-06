"""Exploratory checks that back every data decision.

For each column of each supplied file: missing share, distinct values, share of dates after
the cut-off, and how strongly it moves with price (signal). Joined with the decision log in
src/decisions.py. Also: rows per month (to justify the split date) and checks the model needs.

python -m src.eda        (~1 minute) -> outputs/data_decisions.csv, outputs/eda.json
The report (python -m src.report) turns both into "How we chose the data".
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import asof, config as C
from .decisions import FILE_TITLE, LOOKAHEAD, lookup
from .loaders import load

CUTOFF = {"rents_input": C.RENT_CUTOFF, "rents_leases": C.RENT_CUTOFF, "blocks": C.RENT_CUTOFF,
          "value_input": C.VALUE_CUTOFF, "value_sales": C.VALUE_CUTOFF, "value_repeat": C.VALUE_CUTOFF}


def signal(x: pd.Series, y: pd.Series) -> tuple[float | None, str]:
    """How much a column moves with log price, 0..1.
    Numbers: |Spearman|. Categories (and numbers with <= 12 values): correlation ratio."""
    ok = y.notna()
    x, y = x[ok], y[ok]
    if pd.api.types.is_datetime64_any_dtype(x):
        x = x.dt.year + x.dt.dayofyear / 366
    is_text = not pd.api.types.is_numeric_dtype(x) and not pd.api.types.is_bool_dtype(x)
    if is_text and x.nunique() > 0.05 * len(x):
        return None, "identifier or free text"
    if pd.api.types.is_numeric_dtype(x) and x.nunique() > 12:
        m = x.notna()
        if m.sum() < 30:
            return None, "too few values"
        return float(abs(x[m].rank().corr(y[m].rank()))), "rank correlation"
    cat = x.astype(object).where(x.notna(), "(blank)").astype(str)
    top = cat.value_counts().index[:100]
    cat = cat.where(cat.isin(top), "(other)")
    grand = y.mean()
    ss_b = y.groupby(cat).agg(lambda v: len(v) * (v.mean() - grand) ** 2).sum()
    ss_t = ((y - grand) ** 2).sum()
    return float(np.sqrt(ss_b / ss_t)) if ss_t > 0 else None, "correlation ratio"


def profile(df: pd.DataFrame, cutoff: str) -> pd.DataFrame:
    rows = []
    for c in df.columns:
        s = df[c]
        r = {"column": c, "dtype": str(s.dtype), "missing_share": float(s.isna().mean()),
             "distinct": int(s.nunique())}
        if pd.api.types.is_datetime64_any_dtype(s):
            r["date_min"] = str(s.min().date()) if s.notna().any() else ""
            r["date_max"] = str(s.max().date()) if s.notna().any() else ""
            r["after_cutoff_share"] = float((s > pd.Timestamp(cutoff)).mean())
        elif pd.api.types.is_numeric_dtype(s) and s.notna().any():
            r["min"], r["median"], r["max"] = float(s.min()), float(s.median()), float(s.max())
        rows.append(r)
    return pd.DataFrame(rows)


def recent_target(events: pd.DataFrame, cutoff: str, years: int) -> pd.Series:
    """log price of each flat's latest event in the `years` before the cut-off."""
    e = asof.until(events, cutoff)
    e = e[(e.date > pd.Timestamp(cutoff) - pd.DateOffset(years=years)) & (e.price > 0)]
    last = e.sort_values("date").groupby("gnaf_id").tail(1).set_index("gnaf_id")
    return np.log(last.price)


def monthly(df: pd.DataFrame, col: str = "date") -> dict:
    m = df[col].dropna().dt.to_period("M").value_counts().sort_index()
    m = m[m.index >= pd.Period("2015-01", "M")]
    return {str(k): int(v) for k, v in m.items()}


def run() -> dict:
    C.ensure_dirs()
    out, summary = [], {"files": {}, "checks": {}}
    frames: dict[str, pd.DataFrame] = {}
    for key in ["rents_input", "rents_leases", "blocks", "value_input", "value_sales", "value_repeat"]:
        try:
            frames[key] = load(key)
        except FileNotFoundError:
            print(f"[eda] {key}: file missing, skipped")

    targets = {}
    if "rents_leases" in frames:
        targets["rents_input"] = recent_target(frames["rents_leases"], C.RENT_CUTOFF, 1)
    if "value_sales" in frames:
        s = frames["value_sales"]
        sold = s[s["type"].fillna("Sold").astype(str).str.lower().str.startswith("sold")]
        targets["value_input"] = recent_target(sold, C.VALUE_CUTOFF, 3)

    for key, df in frames.items():
        cut = CUTOFF[key]
        prof = profile(df, cut)
        y = None
        if key in targets:
            y = df.gnaf_id.map(targets[key])
        for _, p in prof.iterrows():
            col = p["column"]
            status, becomes, reason = lookup(key, col)
            sig, how = (None, "")
            if y is not None and col != "gnaf_id":
                sig, how = signal(df[col], y)
            flags = []
            after = p.get("after_cutoff_share", np.nan)
            is_input = key in ("rents_input", "value_input")
            if is_input and status in ("feature", "derived") and col not in LOOKAHEAD \
                    and pd.notna(after) and after > 0:
                flags.append(f"{after:.1%} of dates after the cut-off")
            if status == "feature" and p["missing_share"] > 0.9:
                flags.append("mostly blank")
            if status == "review":
                flags.append("new column")
            out.append({"file": key, "file_title": FILE_TITLE[key], "column": col, "status": status,
                        "becomes": becomes, "reason": reason,
                        "missing_share": round(p["missing_share"], 4), "distinct": p["distinct"],
                        "after_cutoff_share": None if pd.isna(after) else round(float(after), 4),
                        "signal": None if sig is None else round(sig, 3), "signal_measure": how,
                        "flag": "; ".join(flags)})
        summary["files"][key] = {"rows": len(df), "columns": len(df.columns),
                                 "signal_rows": int(y.notna().sum()) if y is not None else None}

    dec = pd.DataFrame(out)
    dec.to_csv(C.OUT / "data_decisions.csv", index=False)

    # checks that justify specific choices
    ck = summary["checks"]
    if "rents_input" in frames:
        r = frames["rents_input"]
        ck["rents_car_spaces_2plus_share"] = float((r.car_spaces >= 2).mean())
        ck["rents_car_space_blank"] = int(r.car_space.isna().sum())
        ck["rents_attrs_last_seen_after_cutoff"] = float((r.attrs_last_seen > pd.Timestamp(C.RENT_CUTOFF)).mean())
        ck["rents_first_listed_after_cutoff"] = float((r.first_ever_listed > pd.Timestamp(C.RENT_CUTOFF)).mean())
        ck["rents_outside_block_file"] = int(r.block_homes_2026.isna().sum())
    if "rents_leases" in frames:
        lea = frames["rents_leases"]
        ck["rents_leases_after_cutoff_dropped"] = int((lea.date > pd.Timestamp(C.RENT_CUTOFF)).sum())
        ck["rents_monthly_adverts"] = monthly(lea)
        ck["rents_leases_without_parking_share"] = float(lea.car_spaces.isna().mean())
    if "value_input" in frames:
        v = frames["value_input"]
        shop = v.address.fillna("").str.upper().str.contains(r"\b(?:SHOP|OFFICE)\b")
        ck["value_shop_office_rows"] = int(shop.sum())
        ck["value_bedrooms_blank_share"] = float(v.bedrooms.isna().mean())
        u = pd.to_numeric(v.unit_number.astype(str).str.extract(r"(\d+)")[0], errors="coerce")
        ck["value_floor_from_unit_share"] = float((u >= 100).mean())
    if "value_sales" in frames:
        s = frames["value_sales"]
        typ = s["type"].fillna("Sold").astype(str).str.lower()
        ck["value_sales_after_cutoff_dropped"] = int((s.date > pd.Timestamp(C.VALUE_CUTOFF)).sum())
        ck["value_monthly_sales"] = monthly(s[typ.str.startswith("sold")])
        ck["value_for_sale_adverts"] = int((~typ.str.startswith("sold")).sum())
    summary["decision_counts"] = dec.groupby(["file", "status"]).size().unstack(fill_value=0).to_dict("index")
    summary["flags"] = dec[dec.flag != ""][["file", "column", "flag"]].to_dict("records")
    (C.OUT / "eda.json").write_text(json.dumps(summary, indent=1, default=str))

    print(f"[eda] {len(dec)} columns across {len(frames)} files -> {C.OUT / 'data_decisions.csv'}")
    print(dec.groupby("status").size().to_string())
    for f in summary["flags"]:
        print(f"  FLAG {f['file']}.{f['column']}: {f['flag']}")
    return summary


if __name__ == "__main__":
    run()
