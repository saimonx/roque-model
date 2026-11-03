# Test fixtures

Small excerpts of real public files, downloaded on 27 Oct 2026, used only to test the parsers.

| File | Source |
|---|---|
| `not_sample.tsv.gz` | NOT weather archive, first 5 minutes of 1 Sep 2026 |
| `r2d2_sample.html` | ING R2D2 seeing page, first ~20 values of 1 Sep 2026 (cut mid-line on purpose) |
| `ing_night_2026-09-01.html` | ING nightly weather and observing conditions page, night of 1 Sep 2026 |
| `gtc_home.html` | GTC atmosportal home page (live panel) at 2026-10-27 18:26 UT |
| `tonight_sample.json` | a real `site/data/tonight.json` (3 Nov 2026), to check that the web page and the Grafana Cloud dashboard only read fields the forecast writes; copy it again from `site/data/` when the page data change |
