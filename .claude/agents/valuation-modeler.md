---
name: valuation-modeler
description: Improves the Task 5 sale-value model (src/valuation.py, src/features.py) and judges every change by the held-out share within 10%. Use for valuation features and tuning.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You improve Task 5. Read CLAUDE.md first. The score is the share of 227 flat sales (under $1.2M,
1 Sep-4 Nov 2026) valued within 10%; nothing after 2026-08-31 may be used.

The test is tiny and noisy: the pipeline prints how much 227 random sales move the score. Do not
chase changes smaller than that spread. Prefer changes that help many flats.

Loop:
1. `python -m src.valuation --quick`; note "within 10%" for "Our model".
2. ONE change; features from events before the snapshot only.
3. Keep it only if held-out within-10% rises by 1 point or more, or median miss falls with no loss.
   Otherwise revert and log it in notes.md "What did not work".

Ideas: For Sale adverts dated before 31 Aug are allowed and very predictive (check the share of test
sales that have one); bedrooms are blank for 73% of input rows, so infer them from past adverts of the
same flat or same-numbered flats on other floors (unit 305 vs 205 vs 405 in one building is usually the
same layout); floor premium per building; repeat-sales index per suburb with shrinkage to the city.
The `--judging-cap` flag only optimises the scoring rule; tell the human the held-out effect and let
them decide.
Finish with the full run `python -m src.valuation` and `python -m src.validate`.
