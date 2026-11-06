# Sydney Flats — Microburbs Hackathon, Sat 7 Nov 2026 (Tasks 4 and 5)

We enter two scored data tasks in ONE public repo:
- **Task 4 — rents.** Weekly asking rent for all 65,777 flats in `rents-input-flats-city-of-sydney.csv`,
  twice: with and without a car space. Scored on 1,699 private adverts dated 1 Aug–30 Sep 2026 by
  **median absolute $ error** (tie-break: share within $100). Organisers' own rental valuation: $86/wk, 55.21% within $100.
- **Task 5 — valuation.** Sale value on 31 Aug 2026 for all 181,711 rows in `flats-city-of-sydney.csv`.
  Scored on 227 private flat sales under $1.2M, 1 Sep–4 Nov 2026, by **share within 10%**
  (exactly 10% counts; teams within 3 points rank by median $ error).
  Baselines on that set: Microburbs AVM 34/227, suburb x bedroom median 86/227, last sale x citywide change 109/227.

Judges pick winners from task results, pitch and demo. "A clever, non-obvious step beats polish."

## THE RULE THAT CAN DISQUALIFY US
- Task 4: use NOTHING dated after **2026-07-31**. Task 5: NOTHING after **2026-08-31**. From us or anywhere.
- The API has no as-of switch. Every event table or API result goes through `src/asof.py` (`until()`).
- Our own held-out check must split by date: build before the split, test on later events up to the cut-off,
  never use the test events while building or tuning. Report the split date, test count, score and R².
- Never put in the repo: the API key, the supplied files, raw API output, anything in `data/`.

## Hand-in by 3:00 pm (public GitHub repo)
`README.md`, `report.html`, `pitch.mp4` (<=45 s), `demo.mp4` (<=3 min), each video < 95 MB,
`outputs/rents_<team-slug>.csv`, `outputs/valuation_<team-slug>.csv`. Slug: lower case, spaces -> hyphens,
only letters/digits/hyphens (`TEAM_NAME` env var -> `src.config.team_slug()`).
CSV: UTF-8, one header, one row per input gnaf_id, no blanks. Rents may end in .50; values whole dollars.

## Commands
```
python scripts/setup_tonight.py      # Friday: install, test, practice run, app check, outside data
python scripts/go.py prepare|check [--apply]|run [--quick] [--task X]   # Saturday flow
python scripts/run.py [--quick] [--task rents|valuation]                 # pipeline, any OS
python scripts/make_mock_data.py      # synthetic files with the documented columns (before the day)
python scripts/make_mock_exo.py       # synthetic outside files in the real raw formats
python scripts/fetch_exo.py           # REAL outside data (laptop with internet)
python -m src.exo.build               # parse outside data -> data/exo/*.parquet
python scripts/exo_ablation.py --each # keep only the outside sources that help
python -m src.eda                     # column profile + decision log -> outputs/data_decisions.csv
python -m src.rents [--quick]         # held-out check + outputs/rents_<team>.csv + metrics_rents.json
python -m src.valuation [--quick]     # same for Task 5 (--judging-cap: see report)
python -m src.validate                # contract check of every CSV in outputs/
python scripts/mock_judge.py          # score vs MOCK hidden data (mock only)
python -m src.report                  # report.html from metrics + notes.md
streamlit run app/app.py              # demo for demo.mp4
pytest -q                             # leakage + metric + contract tests
bash scripts/run_all.sh               # everything above in order
bash scripts/run_task.sh rents|valuation [--quick]  # one task alone (two laptops in parallel)
```

## Layout
```
src/config.py     dates, file names, SCHEMA column mapping (fix GUESSED columns here, once)
src/loaders.py    read supplied CSVs -> canonical columns; building key; floor from unit number
src/asof.py       the cut-off filter
src/index.py      repeat-pairs monthly index (moves old prices to the snapshot date)
src/features.py   snapshot features: own history, building, block, suburb, neighbours, asking advert, anchor
src/model.py      monthly snapshots -> LightGBM (Huber on log price) starting from the anchor (init_score)
src/rents.py      Task 4 pipeline      src/valuation.py  Task 5 pipeline
src/decisions.py  why each supplied column is (not) used   src/eda.py  evidence for it
src/metrics.py    judges' metrics      src/validate.py   CSV contract check
src/client.py     cached, throttled API client, same behaviour as the official one (python -m src.client = smoke test)
src/report.py     report.html          notes.md          the team's words for the report
app/app.py        Kerbside: Streamlit demo app (local only: shows private past prices). Fonts in app/static
src/exo/          outside data: osm.py census.py bonds.py vg.py places.py build.py common.py
src/parking.py    car-space value from like-for-like raw adverts; calibrated option chosen by the held-out check
src/neighbourhood.py  app only: places nearby, car vs no car, rough travel times, projects; live API layer if a key is set
```

## Facts about the data (from the task pages)
- Rents input: `car_space` blank for 5,793; `floor_level` known for 34,396; 16,094 never advertised;
  4,246 addresses outside the City files (blank block fields; the City key does not cover them).
- Valuation input: `bedrooms` blank for 132,217; ~6,700 SHOP/OFFICE addresses (never scored);
  `unit_number` blank for 12,070; floor is not given -> we parse it from the unit number (315 -> 3).
- Judging parking: the column matching the advert's parking is scored; if blank, the input's parking.
- API (getting-started page + official demos github.com/David-Mib/microburbs-hackathon-demos):
  base `https://api-ht.microburbs.com.au`, header `Authorization: Bearer <key>`, ~10 req/s per key,
  "no data" = HTTP 200 `{"data": null, "available": false, "reason", "message"}`, 403 = outside the
  City of Sydney OR a retired GNAF id, 429 = wait (Retry-After) and retry. Suburb names as the API
  writes them, e.g. `Glebe (NSW)`. Docs with a try-it button: https://api-ht.microburbs.com.au/docs
- Useful property endpoints: `history/all` (sale_history + rent_history lists), `sale-history`,
  `basics/all`, `profile`, `comparables/recent-sales-nearby`. Suburb: `sales/recent?limit=&offset=`.
  There is NO `rent-history` endpoint: rent history comes from `history/all`.
- The API has NO as-of switch. `basics/all` has no as-at date: do not use it for Task 5.
  `/suburbs/{name}/listings/for-rent` and `for-sale` are live (after the cut-off): never use them.
- Optional extra data: `python scripts/api_history.py --task rents|valuation --limit N` saves filtered
  history to data/cache/; the pipelines merge it automatically. Keep it only if the held-out score improves.

## Data decisions: every column is accounted for
- `src/decisions.py` holds one entry per (file, column): feature / derived / key / label / not used, and why.
- `python -m src.eda` measures the evidence (blank share, dates after the cut-off, signal vs price) and
  writes `outputs/data_decisions.csv` + `outputs/eda.json`; `report.html` shows it as "How we chose the data",
  with held-out importance per feature group (shuffling a group and re-scoring with the judges' metric).
- LOOK-AHEAD columns never become raw features (tested): `ever_advertised_for_lease`, `attrs_last_seen`;
  `first_ever_listed` only as years since first listed when that is before the snapshot.
- On the day: real files may bring new columns. They show as "review". Decide, write the reason in
  `src/decisions.py`, re-run `python -m src.eda`. Change your mind? Change the entry and say why.

## Outside data (src/exo/, all optional, all free)
| Source | Task | What | As-of rule in code |
|---|---|---|---|
| OpenStreetMap (Overpass) | 4, 5 | km to train/metro, light rail, supermarket, park, school, main road; counts nearby | Overpass `[date:"2026-07-31T23:59:59Z"]`: the map as it was on the cut-off |
| ABS Census 2021 (G02 by SA1 + MB allocation) | 4, 5 | SA1 median rent, household income, household size, people per bedroom, age | Census night Aug 2021 |
| NSW rental bond lodgements | 4 | median new-lease rent by postcode x bedrooms, 6-month growth | only files published before each snapshot (month M is published in M+1) |
| NSW Valuer General bulk sales | 5 | extra strata sales matched to gnaf_id by address | contract AND settlement on or before the cut-off, weekly file dated on or before it |

- `python scripts/fetch_exo.py` downloads (laptop with internet; the workspace cannot reach these sites).
  Anything that fails prints where to get it by hand into `data/exo/raw/<source>/`.
- `python -m src.exo.build` parses `data/exo/raw/` into `data/exo/*.parquet`. Pipelines use whatever exists.
- Switches: `EXO=0` (none), `EXO_SOURCES=osm,census` (subset).
- `python scripts/exo_ablation.py --each` decides with the held-out check which sources stay.
  VG sales are used for training only; test sets are identical with or without outside data.
- VG data is CC BY-NC-ND: never commit it, never republish it. Credit every source in README.md.
- `places` (OSM amenities, bus routes, construction) is for the app only, never a model feature, so it uses
  today's map. The app also calls the API live when a key is set: `transport/nearby`, `development/da-list`.

## Rules for agents
1. NEVER guess a column. On the day, print `df.columns` and 3 rows of each supplied file, then fix
   `SCHEMA` in `src/config.py`. Loaders warn about any missing column; do not ignore the warning.
2. Every new feature: prove it uses only events before the snapshot. Add a test like
   `test_snapshot_features_never_see_the_future` if it touches dates.
3. Judge every change ONLY by the held-out numbers the pipeline prints. Keep a change if it improves
   the held-out score; log it (and failures) in `notes.md` under "What did not work".
4. Run `python -m src.validate` after writing any CSV. A blank answer counts as wrong.
5. No per-flat API loops over all flats (181k calls = 5+ hours). Batch by suburb or pull only what a
   held-out test proves is worth it. Always through `src/client.py` (cache + throttle).
6. Any number that goes into the pitch or report comes from `outputs/metrics_*.json`; note it in `pitch/numbers.md`.
7. Small commits. Commit CSVs and report.html as soon as a valid version exists (by 1 pm), then improve.
