# Saturday 7 November runbook — Tasks 4 and 5

Goal: **both CSVs valid and pushed by 1:00 pm**, then use the rest of the time to improve them and
tell the story. A perfect CSV at 3:05 does not count.

## Friday

- [ ] Reply **ROOM** to Luke's email (otherwise the place goes to someone else).
- [ ] Join Slack and form a team (2 to 6 people, **all of whom were already offered a place**).
- [ ] Pick the team name. The CSV slug comes from it: `Data Wranglers` → `data-wranglers`.
- [ ] Create an empty **public** GitHub repo and give everyone access.
- [ ] On your laptop: `pip install -r requirements.txt`, then `python scripts/make_mock_data.py` and
      `bash scripts/run_all.sh --quick`. If it finishes cleanly on mock data, only the files change on Saturday.
- [ ] **Outside data, tonight** (needs internet, not the key): `python scripts/fetch_exo.py`, then
      `python -m src.exo.build`. Anything that fails prints where to download it by hand into
      `data/exo/raw/<source>/`. Copy the whole `data/exo/` folder to every laptop (never to the repo).
- [ ] Try `streamlit run app/app.py` and record 10 s of screen to check the recorder works.
- [ ] Email Luke (a written answer removes the risk):
  1. May we use a *For Sale* advert dated before 31 August for a flat that sold after it?
     (The rules allow it as written, but better to confirm.)
  2. Do one `pitch.mp4` and one `demo.mp4` cover two tasks, or do you expect one per task?
  3. Do the past-leases and sales files arrive already cut at the task date, or should we filter
     them? (The kit filters them either way.)

## Saturday, before 10 am

- [ ] Have breakfast. Laptop and charger. Claude Code signed in.
- [ ] **One person** registers the team on the Google form (members + Tasks 4 and 5).

## Roles (for 3–4 people; with 2, merge 1+2 and 3+4)

| Role | Does | Subagent |
|---|---|---|
| 1. Data | Checks the files, fixes `SCHEMA`, date filter | `data-engineer` |
| 2. Rents | Improves Task 4 against the held-out check | `rent-modeler` |
| 3. Valuation | Improves Task 5 against the held-out check | `valuation-modeler` |
| 4. Story | notes.md, README, scripts, videos, final review | `storyteller-qa` |

## Timeline

| Time | What | Who |
|---|---|---|
| 10:00 | Table, coffee, wifi, clone the repo, `pip install` | all |
| 10:30 | Welcome and challenge: listen for any rule change to Tasks 4 and 5 | all |
| 11:00 | Key and files arrive by email → `data/supplied/`, key in `.env` | 1 |
| 11:02 | `python -m src.client`: tests the key (ping, suburbs, one flat's history). If it fails, check `.env` | 1 |
| 11:05 | Ask Claude Code: *"use data-engineer: print the columns, dtypes, date range and 3 rows of every file in data/supplied and fix SCHEMA in src/config.py"* | 1 |
| 11:15 | `python -m src.eda`: any column marked **review** (new in the real files) gets a decision and a reason in `src/decisions.py`; any **flag** is checked | 1 |
| 11:20 | Delete `data/supplied/MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt` and `data/mock_hidden/`. Run `python -m src.rents --quick` and `python -m src.valuation --quick` | 1 |
| 11:40 | **First real version**: `bash scripts/run_all.sh`. Commit both CSVs + `report.html`. | 1 |
| 11:40–1:00 | One change at a time, measured on the held-out check. Log what did not work. | 2, 3 |
| 11:45 | `python scripts/exo_ablation.py --each` (~15 min, in parallel): keep only the outside sources that help. Switch the rest off with `EXO_SOURCES=...` | 1 |
| 11:45 | Optional, in parallel: `python scripts/api_history.py --task rents --limit 3000` (~6 min) and re-run. Keep it only if the held-out score improves | 1 |
| 11:40–1:00 | Read `outputs/metrics_*.json` and pick the 2–3 findings | 4 |
| **1:00** | **Push valid CSVs** (`python -m src.validate` green) and `report.html`. This is already a hand-in. | 1 |
| 1:00–2:00 | Last improvements; the model freezes at 1:45 | 2, 3 |
| 1:30–2:30 | Write notes.md and README, record `demo.mp4` (app + report) and `pitch.mp4` | 4 (+ all) |
| 2:30 | Final review with `storyteller-qa` (the 6 checks) | 4 |
| 2:45 | Last push. Nothing after 2:50. | 1 |
| 3:00 | Hand-ins close | |

## If something goes wrong

| Problem | Plan B |
|---|---|
| A file has different columns | Only touch `SCHEMA` in `src/config.py`; the loader says what is missing |
| The full pipeline takes too long | `--quick` (4 snapshots instead of 12) |
| The model does not beat the best baseline on the held-out check | Submit the winning baseline (the table shows it) and say so honestly in the report |
| Running out of time on Task 5 | Submit the `--quick` version; blanks count as wrong, a reasonable value does not |
| The API is slow or returns 429 | Not needed: the kit works from the supplied files alone. The client already retries |
| The API returns 403 for a `gnaf_id` | Normal: outside the City or a retired id. `client.safe()` returns None and carries on |
| Video > 95 MB | `ffmpeg -i in.mp4 -vf scale=-2:1080 -c:v libx264 -preset veryfast -crf 28 -c:a aac out.mp4` |

## If a judge asks "why these columns?"

Open `report.html` → **How we chose the data**: every column of the six files, what we did with it, why,
its blank share and signal, the columns we left out (with the look-ahead ones explained), and which
feature groups the model needs on the held-out check. Source: `src/decisions.py` + `python -m src.eda`.

## Non-negotiable rules

1. Task 4: nothing dated after **2026-07-31**. Task 5: nothing after **2026-08-31**. The API does not filter by date.
2. Never in the repo: the key, the supplied files, API output, outside data, anything in `data/`.
3. Every pitch number comes from `outputs/metrics_*.json` and is logged in `pitch/numbers.md`.
4. Task 5 is scored on 227 sales: differences of a few points are luck. Do not chase them.
