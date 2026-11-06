"""Build report.html (single file, charts embedded) from outputs/metrics_*.json
and the team's own words in notes.md.

python -m src.report
"""
from __future__ import annotations

import base64
import html
import io
import json
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import config as C  # noqa: E402

INK, MUTED, ACCENT, BASE = "#1d2433", "#6b7385", "#0f766e", "#c8ccd4"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": BASE, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "figure.dpi": 130})


def _img(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return f'<img alt="" src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}">'


def _bars(labels, values, fmt, xlabel, highlight_last=True):
    fig, ax = plt.subplots(figsize=(6.4, 0.5 + 0.42 * len(labels)))
    colors = [BASE] * len(values)
    if highlight_last:
        colors[-1] = ACCENT
    ax.barh(labels, values, color=colors, height=0.6)
    for i, v in enumerate(values):
        ax.text(v, i, " " + fmt(v), va="center", color=INK, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_xlim(0, max(values) * 1.25)
    return _img(fig)


def _md(text: str) -> str:
    """Tiny markdown: ## headings, - bullets, paragraphs, **bold**, `code`, [t](u)."""
    out, lst = [], False
    for line in text.splitlines():
        s = html.escape(line.rstrip())
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
        if s.startswith("- "):
            if not lst:
                out.append("<ul>")
                lst = True
            out.append(f"<li>{s[2:]}</li>")
            continue
        if lst:
            out.append("</ul>")
            lst = False
        if s.startswith("### "):
            out.append(f"<h3>{s[4:]}</h3>")
        elif s.strip():
            out.append(f"<p>{s}</p>")
    if lst:
        out.append("</ul>")
    return "\n".join(out)


def _notes() -> dict[str, str]:
    p = C.ROOT / "notes.md"
    secs, cur = {}, None
    for line in (p.read_text().splitlines() if p.exists() else []):
        if line.startswith("## "):
            cur = line[3:].strip().lower()
            secs[cur] = ""
        elif cur:
            secs[cur] += line + "\n"
    return secs


def _table(rows: list[list], head: list[str]) -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def rents_section(m: dict) -> str:
    h = m["heldout"]
    names = list(h)
    rows = [[k, f"${v['median_abs_error']:.0f}", f"{v['share_within_100']:.1%}", f"{v['r2']:.3f}"]
            for k, v in h.items()]
    best = h[names[-1]]
    lo, hi = m["model_median_error_ci95"]
    bars = _bars(names, [h[k]["median_abs_error"] for k in names], lambda v: f"${v:.0f}",
                 "median absolute error, $ per week (lower is better)")
    pb = m["parking_premium_by_bed"]
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    labs = [("studio" if k == "0" else "unknown" if k == "-1" else f"{k} bed") for k in pb]
    ax.bar(labs, list(pb.values()), color=ACCENT, width=0.55)
    ax.set_ylabel("$ per week")
    ax.set_title("What a car space adds to weekly rent (median)", loc="left", fontsize=10, color=INK)
    park = _img(fig)
    fe = m["floor_effect"]
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    ax.plot([int(k) for k in fe], list(fe.values()), marker="o", color=ACCENT)
    ax.set_xlabel("floor")
    ax.set_ylabel("$ per week")
    ax.set_title("Typical predicted rent if the flat sat on floor N", loc="left", fontsize=10, color=INK)
    floor = _img(fig)
    imp = _table([[i["feature"], f"{i['share']:.1%}"] for i in m["importance"][:10]], ["feature", "share of gain"])
    return f"""
<h2>Task 4 — What will this flat rent for?</h2>
<p class="kpi"><span>${best['median_abs_error']:.0f}</span> median miss per week on {m['test_rows']:,}
held-out adverts ({m['test_from']} to {m['test_to']}); {best['share_within_100']:.1%} within $100;
R² {best['r2']:.3f}. 95% interval for the median miss: ${lo:.0f} to ${hi:.0f}.</p>
<h3>Held-out check</h3>
<p>Built from adverts before <b>{m['split']}</b>; tested on adverts dated {m['split']} to {m['cutoff']},
which the model never saw. The final model is refitted on everything up to {m['cutoff']} and nothing after.</p>
{_table(rows, ["method", "median miss", "within $100", "R²"])}
{bars}
<h3>Parking</h3>
<p>Every flat gets two answers; the gap is the parking premium (median ${m['parking_premium_median']:.0f}/week).
A monotone constraint stops the model ever pricing a car space below zero.</p>
{park}
{floor}
<h3>What the model leans on</h3>
{imp}
"""


def valuation_section(m: dict) -> str:
    h = m["heldout"]
    names = list(h)
    rows = [[k, f"{v['share_within_10pct']:.1%}", f"${v['median_abs_error']:,.0f}", f"{v['r2']:.3f}"]
            for k, v in h.items()]
    best = h[names[-1]]
    lo, hi = m["model_within10_ci95"]
    d5, d50, d95 = m["model_within10_227_draws"]
    bars = _bars(names, [h[k]["share_within_10pct"] * 100 for k in names], lambda v: f"{v:.1f}%",
                 "share within 10% of sale price (higher is better)")
    ba = m.get("by_anchor", {})
    anchor = _table([[k, v["rows"], f"{v['share_within_10pct']:.1%}"] for k, v in ba.items()],
                    ["what we knew about the flat", "held-out sales", "within 10%"])
    cap = m.get("cap_scan", {})
    cap_rows = [[("no cap" if k == "none" else f"${int(k):,}"), f"{v:.1%}"] for k, v in cap.items()]
    imp = _table([[i["feature"], f"{i['share']:.1%}"] for i in m["importance"][:10]], ["feature", "share of gain"])
    return f"""
<h2>Task 5 — Value every flat</h2>
<p class="kpi"><span>{best['share_within_10pct']:.1%}</span> of {m['test_rows']:,} held-out flat sales under
$1.2M valued within 10% ({m['test_from']} to {m['test_to']}); median miss ${best['median_abs_error']:,.0f};
R² {best['r2']:.3f}. 95% interval: {lo:.1%} to {hi:.1%}.</p>
<h3>Held-out check</h3>
<p>Split date <b>{m['split']}</b>: built from sales before it, tested on {m['test_rows']:,} later sales up to
{m['cutoff']} (flats only, under $1.2M, as the judges score). No missing predictions: every one of the
{m['rows_written']:,} addresses has a value.</p>
{_table(rows, ["method", "within 10%", "median miss", "R²"])}
{bars}
<h3>Why 227 sales is a noisy test</h3>
<p>Drawing 227 of our held-out sales at random, the same model scores between {d5:.1%} and {d95:.1%}
(5th to 95th percentile). Differences of a few points between teams are mostly luck.</p>
<h3>Where it hits</h3>
{anchor}
<h3>The $1.2M rule</h3>
<p>Only sales under $1.2M are scored. Capping predictions would change the held-out score as below.
{"Applied in the submitted file." if m.get("judging_cap_applied") else "Not applied in the submitted file."}</p>
{_table(cap_rows, ["cap", "within 10%"])}
<h3>What the model leans on</h3>
{imp}
"""


def _ltable(rows: list[list], head: list[str]) -> str:
    return _table(rows, head).replace("<table>", '<table class="left">', 1)


def _pct(v) -> str:
    return "" if v is None or (isinstance(v, float) and v != v) else f"{float(v):.0%}"


def _sig(v) -> str:
    return "" if v is None or (isinstance(v, float) and v != v) else f"{float(v):.2f}"


def timeline(eda: dict) -> str:
    ck = eda.get("checks", {})
    series = [("Rental adverts per month (Task 4)", ck.get("rents_monthly_adverts"), C.RENT_SPLIT, C.RENT_CUTOFF),
              ("Sales per month (Task 5)", ck.get("value_monthly_sales"), C.VALUE_SPLIT, C.VALUE_CUTOFF)]
    series = [x for x in series if x[1]]
    if not series:
        return ""
    fig, axes = plt.subplots(len(series), 1, figsize=(6.4, 2.3 * len(series)), squeeze=False)
    for ax, (title, m, split, cut) in zip(axes[:, 0], series):
        x = pd.PeriodIndex(list(m), freq="M").to_timestamp()
        ax.plot(x, list(m.values()), color=ACCENT, lw=1.4)
        ax.axvline(pd.Timestamp(split), color=MUTED, ls="--", lw=1)
        ax.axvline(pd.Timestamp(cut), color=INK, lw=1)
        ymax = max(m.values())
        ax.text(pd.Timestamp(split), ymax, " split ", ha="right", va="top", color=MUTED, fontsize=8)
        ax.text(pd.Timestamp(cut), ymax, " cut-off", ha="left", va="top", color=INK, fontsize=8)
        ax.set_title(title, loc="left", fontsize=10, color=INK)
    fig.tight_layout()
    return _img(fig)


def decisions_section() -> str:
    p = C.OUT / "data_decisions.csv"
    if not p.exists():
        return "<h2>How we chose the data</h2><p><em>(run python -m src.eda)</em></p>"
    d = pd.read_csv(p)
    eda = json.loads((C.OUT / "eda.json").read_text()) if (C.OUT / "eda.json").exists() else {}
    ck = eda.get("checks", {})
    titles = dict(zip(d.file, d.file_title))

    summ = []
    for f, g in d.groupby("file", sort=False):
        st = g.status.value_counts()
        summ.append([titles[f], len(g), st.get("feature", 0), st.get("derived", 0),
                     st.get("key", 0) + st.get("label", 0), st.get("not used", 0), st.get("review", 0)])
    flags = d[d.flag.fillna("") != ""]
    flag_html = ""
    if len(flags):
        flag_html = '<p class="warn"><b>To review:</b> ' + "; ".join(
            f"{html.escape(r.file)}.{html.escape(r.column)}: {html.escape(r.flag)}" for r in flags.itertuples()) + "</p>"

    left = d[d.status == "not used"]
    left_rows = [[f"<code>{html.escape(r.column)}</code><br><span class=sub>{html.escape(titles[r.file])}</span>",
                  _pct(r.missing_share), _sig(r.signal), html.escape(r.reason)] for r in left.itertuples()]

    facts = []
    if "rents_car_spaces_2plus_share" in ck:
        facts.append(f"Only {ck['rents_car_spaces_2plus_share']:.1%} of flats have 2+ car spaces, so the yes/no "
                     f"<code>car_space</code> carries what the hand-in needs.")
    if "rents_attrs_last_seen_after_cutoff" in ck:
        facts.append(f"{ck['rents_attrs_last_seen_after_cutoff']:.1%} of <code>attrs_last_seen</code> dates and "
                     f"{ck['rents_first_listed_after_cutoff']:.1%} of <code>first_ever_listed</code> dates fall after "
                     f"31 July 2026.")
    if "rents_leases_after_cutoff_dropped" in ck:
        facts.append(f"{ck['rents_leases_after_cutoff_dropped']:,} past adverts dated after 31 July and "
                     f"{ck.get('value_sales_after_cutoff_dropped', 0):,} sales after 31 August were dropped.")
    if "value_floor_from_unit_share" in ck:
        facts.append(f"The floor can be read from the unit number for {ck['value_floor_from_unit_share']:.0%} of "
                     f"Task 5 rows; bedrooms are blank for {ck['value_bedrooms_blank_share']:.0%}.")
    if "value_shop_office_rows" in ck:
        facts.append(f"{ck['value_shop_office_rows']:,} Task 5 rows are shops or offices: valued (no blanks) "
                     f"but kept out of training and our test, as the judges do.")

    imp = []
    for task, label, fmt in (("rents", "Task 4: extra median miss, $ per week",
                              lambda v: f"{v:+.1f}"),
                             ("valuation", "Task 5: within-10% points lost",
                              lambda v: f"{-v * 100:+.1f}")):
        mp = C.OUT / f"metrics_{task}.json"
        if not mp.exists():
            continue
        g = json.loads(mp.read_text()).get("group_importance")
        if not g:
            continue
        rows = [[html.escape(x["group"]), x["n_features"], fmt(x["worse_by"]),
                 "<span class=sub>" + html.escape(", ".join(x["features"][:6]) +
                                                  (" ..." if len(x["features"]) > 6 else "")) + "</span>"]
                for x in g if x["features"]]
        imp.append(f"<h3>{label}</h3>" + _ltable(rows, ["feature group", "features", "change", "includes"]))

    per_file = []
    for f, g in d.groupby("file", sort=False):
        rows = [[f"<code>{html.escape(r.column)}</code>", html.escape(r.status),
                 html.escape(str(r.becomes) if isinstance(r.becomes, str) else ""),
                 _pct(r.missing_share), _sig(r.signal), html.escape(r.reason)] for r in g.itertuples()]
        per_file.append(f"<details><summary>{html.escape(titles[f])} ({len(g)} columns)</summary>" +
                        _ltable(rows, ["column", "decision", "becomes", "blank", "signal", "why"]) + "</details>")

    return f"""
<h2>How we chose the data</h2>
<p>Every column of the six supplied files is listed here with what we did with it and why. The evidence
is measured on the files by <code>python -m src.eda</code>; the reasons are kept in <code>src/decisions.py</code>,
and the whole table is in <code>outputs/data_decisions.csv</code>. <b>Signal</b> is how strongly a column moves
with each flat's latest price before the cut-off (0 to 1: rank correlation for numbers, correlation ratio for
categories). A column can be left out despite a strong signal when it would let the model see the future.</p>
{_ltable(summ, ["file", "columns", "feature", "derived", "key / label", "not used", "review"])}
{flag_html}
<h3>Left out, and why</h3>
{_ltable(left_rows, ["column", "blank", "signal", "why"])}
<h3>Checks behind the choices</h3>
{"<ul>" + "".join(f"<li>{x}</li>" for x in facts) + "</ul>" if facts else ""}
<h3>The data over time</h3>
<p>Our held-out check trains on everything before the dashed line and tests on the months between it and
the cut-off, the same shape as the judges' test.</p>
{timeline(eda)}
<h3>What the model actually needs (held-out)</h3>
<p>Each group's columns are shuffled across the held-out rows, which removes their information, and the
judges' metric is recomputed. Near zero means the group adds nothing on this test.</p>
{"".join(imp)}
<h3>Every column</h3>
{"".join(per_file)}
"""


CSS = """
:root{--ink:#1d2433;--muted:#6b7385;--line:#e3e6eb;--accent:#0f766e;--bg:#fbfbfa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:30px;line-height:1.2;margin:0 0 6px}h2{font-size:22px;margin:48px 0 8px;padding-top:24px;
border-top:1px solid var(--line)}h3{font-size:16px;margin:28px 0 6px}
.sub{color:var(--muted);margin:0 0 24px}.kpi{font-size:15px;background:#fff;border:1px solid var(--line);
border-left:4px solid var(--accent);padding:14px 16px;border-radius:6px}.kpi span{display:block;
font-size:30px;font-weight:700;color:var(--accent)}
table{border-collapse:collapse;width:100%;margin:10px 0 16px;font-size:14px;background:#fff}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}th{color:var(--muted);
font-weight:600}td:not(:first-child),th:not(:first-child){text-align:right}
img{max-width:min(100%,620px);height:auto;display:block;margin:8px 0 16px}code{background:#eef0f3;padding:1px 4px;
border-radius:3px}.warn{background:#fff4e5;border:1px solid #f3c98b;padding:10px 14px;border-radius:6px}
.left td,.left th{text-align:left!important;vertical-align:top}.left .sub{margin:0;font-size:12px}
details{margin:6px 0;background:#fff;border:1px solid var(--line);border-radius:6px;padding:8px 12px}
summary{cursor:pointer;font-weight:600}details table{margin-top:10px}
"""


def build() -> str:
    notes = _notes()
    parts = []
    mock = (C.SUPPLIED / "MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt").exists()
    for task, fn in (("rents", rents_section), ("valuation", valuation_section)):
        p = C.OUT / f"metrics_{task}.json"
        if p.exists():
            parts.append(fn(json.loads(p.read_text())))
    ab = C.OUT / "exo_ablation.json"
    if ab.exists():
        a = json.loads(ab.read_text())
        rows = []
        for task, r in a["scores"].items():
            for name, v in r.items():
                rows.append([("Task 4 rents" if task == "rents" else "Task 5 values"), name,
                             f"${v:.1f}/wk" if task == "rents" else f"{v:.1%}"])
        parts.append("<h2>Outside data: did it help?</h2><p>Same held-out sets, with and without each "
                     "free source" + (" (quick runs, 4 snapshots)" if a.get("quick") else "") +
                     ". A source stays only if it beats noise.</p>" +
                     _table(rows, ["task", "sources", "held-out score"]))
    body = "\n".join(parts)
    warn = '<p class="warn"><b>MOCK DATA.</b> These numbers come from synthetic data and mean nothing. ' \
           'Re-run on the real files.</p>' if mock else ""
    sec = lambda k: _md(notes.get(k, "")) or "<p><em>(write this in notes.md)</em></p>"  # noqa: E731
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(C.TEAM_NAME)} — report</title>
<style>{CSS}</style></head><body><main>
<h1>{html.escape(C.TEAM_NAME)}</h1>
<p class="sub">Microburbs Hackathon · Saturday 7 November 2026 · Tasks 4 and 5, City of Sydney flats</p>
{warn}
<h2 style="border:0;padding:0;margin-top:24px">What we found</h2>
{sec("insights")}
<h2>Data</h2>
{sec("data")}
{decisions_section()}
<h2>Method</h2>
{sec("method")}
{body}
<h2>What did not work</h2>
{sec("what did not work")}
<h2>Sources and credits</h2>
{sec("sources")}
<p class="sub">Generated {pd.Timestamp.now():%Y-%m-%d %H:%M} by <code>python -m src.report</code>.</p>
</main></body></html>"""
    out = C.ROOT / "report.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(page) / 1024:.0f} KB)")
    return page


if __name__ == "__main__":
    build()
