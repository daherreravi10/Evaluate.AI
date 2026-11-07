# Sydney Flats: rent and value for every flat in the City of Sydney

Microburbs Hackathon, Saturday 7 November 2026. Task 4 (weekly rent, with and without parking) and
Task 5 (sale value), City of Sydney.

![How it all fits together](docs/architecture.png)

## What we built

Two estimates for every flat in the City of Sydney, from one pipeline:

- **Weekly rent** for all 65,777 flats, as at 31 July 2026, with and without a car space
  (`outputs/rents_<team>.csv`). The gap is what a car space is worth for that flat.
- **Sale value** for all 181,711 unit-style addresses on 31 August 2026 (`outputs/valuation_<team>.csv`).
- **Evaluate.AI app** (`app/app.py`), the app: type an address and get the weekly rent with and without a car space,
  the sale value and how we got them; check whether a quoted rent is fair; see what is around the flat
  (transport, shops, hospitals, bus routes, what is being built, rough travel times by car, bike and on foot);
  and a map of what a car space adds to rent across the City.

![Evaluate.AI app](docs/kerbside_1_flat.png)

## Who it helps

- Tenants checking whether an asking rent is too high, and whether a car space is worth paying for.
- Landlords setting a rent that fits similar flats.
- Buyers and everyday investors checking a price before negotiating.

## The data

Microburbs Hackathon supplied files and API (City of Sydney key), used on the day only and not
included in this repo. Free outside data, used only if our held-out check shows it helps
(`outputs/exo_ablation.json`), and never included in this repo:

- OpenStreetMap as at 31 July 2026 (© OpenStreetMap contributors, ODbL): distance to transport, shops, parks, main roads.
- ABS Census 2021 by SA1 (© Commonwealth of Australia, CC BY 4.0): local median rent, income, household size.
- NSW Fair Trading rental bond lodgements: new-lease rents by postcode and bedrooms.
- NSW Valuer General bulk sales (contains property sales information provided under licence from the Valuer General NSW).

The Valuer General files were not used (the site blocks scripted downloads). Full credits in `report.html`.

## How we chose the data

Every column of the six supplied files has a recorded decision (used, derived, key or left out) and a
reason, backed by measured evidence: see **How we chose the data** in `report.html`
(table: `outputs/data_decisions.csv`, reasons: `src/decisions.py`). Two columns that would have let the
model see the future (`attrs_last_seen`, `ever_advertised_for_lease`) are left out on purpose.

## The clever step

We train the model the way it is judged. At every monthly snapshot we rebuild every feature from what
was known on that date only, and ask the model to predict prices in the next two months. Each estimate
starts from the best thing already known about that exact flat: its own For Sale advert, its own last
price moved to today by a repeat-sales index, or its building. The model (LightGBM) only learns the
correction on top. That starting guess is the single most important input on held-out data
(scrambling it adds $211/wk to the rent error and costs 41 points of within-10%).

For parking, every flat is priced twice, with and without a car space. A monotone constraint keeps a car
space worth zero or more, and we check the result against raw like-for-like adverts (same building, same
bedrooms, one with and one without a car space): raw adverts say **$71/wk**, our hand-in says **$72/wk**.

## Results (our own held-out check)

Built only from data before each snapshot, tested on later adverts and sales up to the cut-off.
Split date, test counts and confidence intervals are in `report.html`.

| Task | Our score | R² | Same baselines, our check | Organisers' reference |
|---|---|---|---|---|
| 4 Rents | **$43/wk median miss, 80.8% within $100** | 0.89 | suburb × bedrooms $92; with parking $95 | Microburbs valuation $86/wk, 55.21% within $100 |
| 5 Values | **65.4% within 10%**, median miss $43,656 | 0.65 | suburb × bedrooms 38.0%; asking price or last sale 53.4% | best rule 109/227 (48%); Microburbs AVM 34/227 |

Our simple baselines land close to the organisers' published figures (suburb × bedrooms: $92 vs ~$100,
38.0% vs 37.9%), which suggests our check behaves like the judges' test. No data after the cut-offs is
used: the rents file ends on 31 July; two sale adverts dated after 31 August were dropped.

## How to run it

```bash
pip install -r requirements.txt
cp .env.example .env            # TEAM_NAME=Evaluate.AI; paste the team key; never commit .env
# put the six supplied CSVs in data/supplied/
python scripts/go.py check      # key, files, columns (add --apply to accept proposed column matches)
python scripts/go.py run        # tests, EDA, both tasks, validate, report
streamlit run app/app.py        # Evaluate.AI app, for the demo (local only)
```

One task at a time: `python scripts/run.py --task rents` or `--task valuation`. Free outside data:
`python scripts/fetch_exo.py` then `python -m src.exo.build` (optional; the pipeline runs without it).

## Files

`report.html` method and results · `pitch.mp4` 45 s · `demo.mp4` 3 min ·
`outputs/` hand-in CSVs and metrics · `src/` pipeline · `tests/` leakage and contract tests.
