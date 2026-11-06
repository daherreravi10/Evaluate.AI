# Saturday 7 November runbook — Tasks 4 and 5

Goal: **both CSVs valid and pushed by 1:00 pm**, then use the rest of the time to improve them and
tell the story. A perfect CSV at 3:05 does not count.

## Friday night (about 30 minutes, mostly waiting)

- [ ] Reply **ROOM** to Luke's email (otherwise the place goes to someone else).
- [ ] Join Slack and form a team (2 to 6 people, **all of whom were already offered a place**).
- [ ] Pick the team name. The CSV slug comes from it: `Data Wranglers` → `data-wranglers`.
- [ ] Unzip the kit, open a terminal in its folder, make a virtual environment and run the setup:

      python -m venv .venv
      source .venv/bin/activate          (Windows: .venv\Scripts\activate)
      python scripts/setup_tonight.py

  It installs the packages, runs the tests, does a full practice run, checks the app, downloads the
  free outside data and prints a PASS / FAIL table. Outside-data FAILs are optional; the rest must PASS.
  For each outside source that fails it says where to download the file by hand (then run
  `python scripts/setup_tonight.py --only-downloads` again).
- [ ] Open `.env` (created by the setup) and set `TEAM_NAME=` to the registered name.
- [ ] Teammates: same three commands on their laptops with `--skip-downloads`, then unzip
      `exo_for_teammates.zip` (made by the setup) inside their repo folder.
- [ ] GitHub: create the team repo (private for now is fine), push the kit, add teammates. Make it
      **public** before 3 pm. Never commit `.env`, `data/` or `exo_for_teammates.zip` (.gitignore does this).
- [ ] Claude Code installed and signed in on the laptop that drives the work.
- [ ] Try `streamlit run app/app.py` and record 10 s of screen to check the recorder works.
      Bad wifi at the venue? `KERBSIDE_BASEMAP=0 streamlit run app/app.py` drops the street background.
- [ ] Email Luke (a written answer removes the risk):
  1. May we bring code we prepared before the day (a starter pipeline), as long as everything that
     uses the data is run on the day?
  2. May we use a *For Sale* advert dated before 31 August for a flat that sold after it?
     (The rules allow it as written, but better to confirm.)
  3. Do one `pitch.mp4` and one `demo.mp4` cover two tasks, or do you expect one per task?
  4. Do the past-leases and sales files arrive already cut at the task date, or should we filter
     them? (The kit filters them either way.)
  5. The guide says "Choose one or more" tasks, but the form lets us pick only one. We will pick
     Task 4 on the form and also hand in Task 5 from the same repo. Is that right?

## Saturday, before 10 am

- [ ] Have breakfast. Laptop and charger. Claude Code signed in.
- [ ] **One person** registers the team on the Google form: members + **Task 4** (the form allows one).
      If the form has a notes field, add "also submitting Task 5". Say the same in Slack.
- [ ] `python scripts/go.py prepare` — wipes the practice data and practice outputs (keeps outside data).

## Saturday, 11:00: the only steps that touch the real data

    1. Save the six emailed CSVs into data/supplied/ (any file name close to the expected one is fine)
    2. Paste the key into .env:  MICROBURBS_API_KEY=...
    3. python scripts/go.py check            # key, files, rows, columns, dates
    4. python scripts/go.py check --apply    # only if it proposed column matches or a renamed file
    5. python scripts/go.py run --quick      # first real CSVs + report in ~2 min -> commit and push
    6. python scripts/go.py run              # full run, ~4 min
    7. streamlit run app/app.py

If `check` says BLOCKING for a column it could not match, write the real name into
`schema_overrides.json` (it shows the exact line) and run `check` again.

## Two tasks without risking either

The guide says "Choose one or more" and "Use the same public repo for every task your team enters",
and there is one overall ranking. So Task 5 is extra chances, as long as it never slows Task 4 down.

- **Task 4 first, always.** If time gets short, Task 5 ships whatever version is valid at that moment.
- **Two laptops in parallel**, one per task: `bash scripts/run_task.sh rents` and
  `bash scripts/run_task.sh valuation`. Each touches only its own CSV and metrics file, so pushes never
  clash. Whoever pushes last runs `python -m src.report`.
- **Run times measured on mock data of the real size** (2-core cloud machine, so a normal laptop should be as fast or faster):
  Task 4 full ~1:40 min, quick ~1:05 · Task 5 full ~1:50 min, quick ~1:05 · outside-data ablation ~8 min.
  Nothing here needs a GPU or a big machine.
- **Only one laptop?** Run the tasks one after the other: `python scripts/go.py run` (~5 min in total).
- **Windows:** use `python scripts/run.py --task rents` instead of the `.sh` scripts.
- **Fallback for Task 5:** by 1:00 pm push the `--quick` CSV even if Task 4 still needs work. A
  valid file with reasonable values beats a perfect one at 3:05.

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
| 11:00 | Key and files arrive by email → `data/supplied/`, key in `.env`, `python scripts/go.py check` (and `--apply`) | 1 |
| 11:02 | `python -m src.client`: tests the key (ping, suburbs, one flat's history). If it fails, check `.env`. With the key set, the app's "Around this flat" also shows live transport and the suburb's development applications | 1 |
| 11:05 | Ask Claude Code: *"use data-engineer: print the columns, dtypes, date range and 3 rows of every file in data/supplied and fix SCHEMA in src/config.py"* | 1 |
| 11:15 | `python -m src.eda`: any column marked **review** (new in the real files) gets a decision and a reason in `src/decisions.py`; any **flag** is checked | 1 |
| 11:20 | Delete `data/supplied/MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt` and `data/mock_hidden/`. Run `python -m src.rents --quick` and `python -m src.valuation --quick` | 1 |
| 11:40 | **First real version**: `python scripts/go.py run --quick`. Commit both CSVs + `report.html`. | 1 |
| 11:40–1:00 | One change at a time, measured on the held-out check. Log what did not work. | 2, 3 |
| 11:45 | `python scripts/exo_ablation.py --each` (~15 min, in parallel): keep only the outside sources that help. Switch the rest off with `EXO_SOURCES=...` | 1 |
| 11:45 | Optional, in parallel: `python scripts/api_history.py --task rents --limit 3000` (~6 min) and re-run. Keep it only if the held-out score improves | 1 |
| 11:40–1:00 | Read `outputs/metrics_*.json` and pick the 2–3 findings | 4 |
| **1:00** | **Push valid CSVs** (`python -m src.validate` green) and `report.html`. This is already a hand-in. | 1 |
| 1:00–2:00 | Last improvements; the model freezes at 1:45 | 2, 3 |
| 1:30–2:30 | Write notes.md and README, record `demo.mp4` (Kerbside app + report) and `pitch.mp4` | 4 (+ all) |
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
