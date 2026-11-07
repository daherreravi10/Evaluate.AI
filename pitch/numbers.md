# Where every pitch number comes from

| Number | Used in | Source file | Key |
|---|---|---|---|
| (example) $47/wk median miss | pitch, report | outputs/metrics_rents.json | heldout."Our model (LightGBM, snapshots)".median_abs_error |
| 65,777 flats | demo 0:20 | outputs/metrics_rents.json | rows_written |
| 181,711 addresses | demo 0:20 | outputs/metrics_valuation.json | rows_written |
| 31 July / 31 August 2026 cut-offs | demo 0:20 | outputs/metrics_*.json | cutoff |
| split 1 May 2026 | demo 0:50 | outputs/metrics_*.json | split |
| 3,866 later adverts | demo 0:50 | outputs/metrics_rents.json | test_rows |
| 547 later sales | demo 0:50 | outputs/metrics_valuation.json | test_rows |
| $43 a week median miss (42.78) | demo 0:50, 2:30 | outputs/metrics_rents.json | heldout."Our model (LightGBM, snapshots)".median_abs_error |
| 81% within $100 (0.8076) | demo 0:50 | outputs/metrics_rents.json | heldout."Our model (LightGBM, snapshots)".share_within_100 |
| 65% within 10% (0.6545) | demo 0:50 | outputs/metrics_valuation.json | heldout."Our model (LightGBM, snapshots)".share_within_10pct |
| 61% to 70% on 227 random draws | demo 0:50 | outputs/metrics_valuation.json | model_within10_227_draws (5th, 95th) |
| organisers: $86 a week; AVM 34 of 227 | demo 0:50 | task pages (CLAUDE.md), their scoring set, not ours | — |
| Unit 906, 73 Victoria St: $1,112 with car (1,112.50), $992 without | demo 1:40 | outputs/rents_evaluateai.csv | GANSW710342057 |
| car space worth about $120 a week there (1,112.50 − 992) | demo 1:40 | outputs/rents_evaluateai.csv | GANSW710342057 |
| Unit 906 value $1,797,000 (1,796,795, app shows nearest $1,000) | demo 1:40 | outputs/valuation_evaluateai.csv | GANSW710342057 |
| City median car space $76.50 a week | demo 1:40 | outputs/metrics_rents.json | parking_premium_median |
| 816 like-for-like pairs, raw median $71 (70.90) | demo 1:40 | outputs/metrics_rents.json | parking_check.pairs, parking_check.raw_median |
| without the anchor the rent miss grows to $254 (253.81) | demo 2:30 | outputs/metrics_rents.json | group_importance."Starting guess (anchor)".score_without |
| 137 of 142 test sales within 10% when the flat had a For Sale advert | demo 2:30 | outputs/metrics_valuation.json | by_anchor."had a For Sale advert" |

The app reads data/cache/app_*.parquet (local only). Before recording, its estimates were set to the hand-in CSV
values so the screen matches the submission.
