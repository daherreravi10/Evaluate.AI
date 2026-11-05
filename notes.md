# Notes for report.html

Edit the text under each heading. `python -m src.report` puts it in report.html.
Lead with findings (the task pages ask for insights first). Every number here
must come from outputs/metrics_*.json or pitch/numbers.md.

## Insights

- TODO (on the day): the biggest finding, in one sentence with a number. Example shape: "A car space adds a median $X a week to a City of Sydney flat, but $Y in Z."
- TODO: second finding (floor premium, building effect, or where the official baselines miss most).
- TODO: what the 227-sale test can and cannot tell anyone (see the noise section below).

## Data

- Microburbs Hackathon supplied files (used on the day only, not republished): rents-input-flats-city-of-sydney.csv, rents-past-leases-city-of-sydney.csv, blocks-homes-and-people-2021-2026.csv, flats-city-of-sydney.csv, flat-sales-city-of-sydney.csv, repeat-sales-city-of-sydney.csv.
- Microburbs Hackathon API (api-ht.microburbs.com.au), City of Sydney team key. Every API result was filtered to the task date because the endpoints have no as-of switch.
- Task 4 uses nothing dated after 31 July 2026. Task 5 uses nothing dated after 31 August 2026.

## Method

- **One pipeline for both tasks.** For each monthly snapshot date we compute every feature only from events before that date, then learn to predict the prices that appear in the next two months, the same horizon the judges test.
- **Prices moved through time with a repeat-pairs index** (same flat, two prices; smoothed monthly), rebuilt at every snapshot from earlier pairs only.
- **Anchor plus correction.** Each flat starts from its best single guess: its own For Sale advert before the task date, else its own last price moved by the index, else the median of the same building and bedroom count, else the suburb and bedroom median. LightGBM learns the correction from flat size, floor, building, block and neighbouring buildings.
- **Loss close to the median** (Huber on log price), because both scores reward typical error, not average error.
- **Parking:** the model sees the advert's parking and must price a car space at zero or more (monotone constraint). Each flat is predicted twice, with and without.
- **Our own check:** fit before the split date, score on later events up to the task date, never touching them while building.

## What did not work

- TODO (on the day): ideas tried and dropped, with the held-out number that killed them.

## Sources

- Data © Microburbs. Estimates are automated and indicative only.
- Addresses: Open G-NAF © Geoscape Australia, licensed by the Commonwealth of Australia.
- 2021 Census block counts: ABS, © Commonwealth of Australia, CC BY 4.0.
- API client behaviour follows the organisers' demo client (github.com/David-Mib/microburbs-hackathon-demos, MIT).
- Map data © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright). Snapshot as at 31 July 2026.
- ABS Census 2021 General Community Profile (G02, SA1) and ASGS Edition 3 Mesh Block allocation file: © Commonwealth of Australia, CC BY 4.0.
- Rental bond lodgement data: NSW Fair Trading (nsw.gov.au). Files published before each snapshot only.
- Contains property sales information provided under licence from the Valuer General New South Wales (CC BY-NC-ND 4.0, non-commercial, not republished).
- Delete any line above for a source the final model does not use (see outputs/exo_ablation.json).
