**English** · [Español](DETALLES_TECNICOS.md)

# RoqueModel — technical details

Companion to the [README](../README.en.md) and the [website](https://saimonx.github.io/roque-model/?lang=en): how the
label is built, how it is checked, how the model was chosen, all the test figures and how the forecast for each hour
works.

## Contents

1. [The label: when the dome counts as closed](#1-the-label-when-the-dome-counts-as-closed)
2. [Does the label reflect reality?](#2-does-the-label-reflect-reality)
3. [The model and how it was chosen](#3-the-model-and-how-it-was-chosen)
4. [Full test results (2024–2026)](#4-full-test-results-20242026)
5. [Tried and discarded](#5-tried-and-discarded)
6. [Findings from the data](#6-findings-from-the-data)
7. [How each hour works](#7-how-each-hour-works)
8. [FIWARE](#8-fiware)
9. [All the commands](#9-all-the-commands)
10. [Code structure](#10-code-structure)

## 1. The label: when the dome counts as closed

There is no public record of when the GTC closes, so the "dome closed" label is rebuilt from the NOT weather station
at the summit (`dome.py`): its archive starts in 1997, with one measurement every 5 minutes
until 2006 and every minute since 2007, and RoqueModel uses 2017–2026. The dome counts
as closed if any of these conditions is met:

| Reason | Closes when | Reopens when | Where the value comes from |
|---|---|---|---|
| Humidity | humidity reaches **90%** | it has been below 90% for **20 minutes in a row** | Closing rule of the NOT telescope |
| Wind | wind reaches **80 km/h** (22.2 m/s) | it has been below for **20 minutes in a row** | Closing limit of the INT telescope (ING alarm procedure) |
| Ice | temperature ≤ **0 °C** and humidity reached 90% in the previous **24 h** | the temperature rises above 0 °C | This project's own rule, tuned with the Liverpool Telescope night reports from 2017–2022 (adds 29 nights; the LT lost 26 of them) |

An hour counts as closed if the dome is closed for at least 30 of its 60 minutes. Clouds and dust are not
included: there is no reliable public record of them at the summit for every year.

## 2. Does the label reflect reality?

The label is compared with **a real telescope for every year**: the **Liverpool Telescope** (a 2 m robotic
telescope on the same mountain), which has logged every night since 2007 how many hours it lost to the weather
(`validate.py`). Both are asked the same question, night by night: **was at least half of the
night lost?**

- **They agree on 87 of every 100 nights** (3,322 nights, 2017–2026).
- When the label says the night was lost (529 nights), the LT also lost it **96 times out of
  100**.
- When the label keeps the dome open all night (2,458 nights), the LT did not lose the night either
  **90 times out of 100**.
- The LT loses more nights than the label (909 versus 529): it also closes for clouds, dust or caution, and
  the label only measures humidity, wind and ice.

| Year | Nights | Agree (out of 100) | Lost according to the label | Lost by the LT | Lost by both |
|---|---|---|---|---|---|
| 2026 | 273 | 92 | 48 | 69 | 47 |
| 2025 | 317 | 87 | 52 | 94 | 52 |
| 2024 | 314 | 85 | 45 | 83 | 41 |
| 2023 | 316 | 88 | 61 | 94 | 59 |
| 2022 | 346 | 90 | 66 | 97 | 65 |
| 2021 | 357 | 72 | 51 | 148 | 50 |
| 2020 | 350 | 86 | 56 | 100 | 54 |
| 2019 | 341 | 93 | 34 | 51 | 31 |
| 2018 | 358 | 92 | 75 | 95 | 70 |
| 2017 | 350 | 87 | 41 | 78 | 37 |

Correlation between the hours lost by the LT and the closed hours according to the label: 0.74.

**Why a single source?** So that the check means the same thing every year. Not used: the
GTC public archive (exposure times show when it was open, but the data are published
a year later and only 2024–2025 was available), the TNG's time lost to weather (it only publishes the last
year) and the WHT's night accounting (some years it counts nights with the dome closed as observed).

## 3. The model and how it was chosen

- **What it receives:** 33 inputs per hour: the forecast for that hour (humidity, margin to the dew point, wind at
  750 hPa, temperature, clouds, rain, pressure), the forecast for the whole night, the NOT weather station in the 2
  hours before the night, what happened last night (closed hours and seeing) and the time of year and the hour of the
  night (`hourly.py`, `features.py`).
- **Two versions:** provisional (before the night, without the summit station, whose readings do not exist yet) and
  final (from the start of astronomical night, with all the inputs).
- **Year split:** the settings are chosen only with 2017–2023 (validation on 2021, 2022 and 2023, see
  below) and the test is 2024–2026. The tested copy learnt from 2017–2023; the live model was retrained with the same
  settings on all of 2017–2026 (30,044 hours, 5,163 closed). Checked beforehand: adding 2024 to the training improved
  the 2025–2026 figures (wrong on 9.5% → 8.8% of hours; provisional 12.0% → 11.5%;
  `reports/results/refit_check.json`).
- **Settings search** (`compare.py`, `reports/results/model_search.json`): the two strongest model types had an
  equally wide search, scored on three validation years (2021, 2022 and 2023, each
  one learning from the other years of 2017–2023): gradient boosting, 162 combinations (learning
  rate, leaves per tree, minimum hours per leaf, L2, 150/300/600 trees), and random forest, 288
  (minimum hours per leaf from 1 to 50, share of the inputs at each split, Gini or entropy, missing values left as
  they are or filled with the median, 150/300/600 trees). Logistic regression and a small neural network
  had smaller searches.

| Model (test 2024–2026) | Right (final) | Right (provisional) | Brier (final) | AUC | Brier in validation |
|---|---|---|---|---|---|
| **Random forest** | **91.1%** | **88.5%** | **0.0628** | 0.951 | 0.0595 |
| Gradient boosting | 90.7% | 88.2% | 0.0667 | 0.951 | 0.0594 |
| Neural network (MLP) | 90.3% | 87.6% | 0.0718 | 0.949 | 0.0650 |
| Logistic regression | 88.9% | 87.2% | 0.0804 | 0.930 | 0.0658 |

In validation, the two tree models tie (adding up both versions, their Brier differs by
0.9%, whereas from one year to the next it changes by more than 30%, and each one wins one of the three years). Rule:
if they are within 2% of each other in validation, the lower error on the test decides, and the random forest is
better on the test in both versions. Because this choice looked at the test years, its test figures may be somewhat
optimistic; no setting was chosen with them.

**Random forest chosen** (scikit-learn's `RandomForestClassifier`): final, 150 trees, 3 hours per
leaf, 25% of the inputs at each split, entropy and missing values left as they are; provisional, 150 trees, 10 hours
per leaf, √inputs at each split, entropy and missing values left as they are. Training it takes about one second on
an M4 Mac.

**Breakdown of each hour** (`explain.py`): exact Shapley values over ten groups of inputs, with a background
of 200 night hours from 2021–2023. The starting point is the model's mean over that background (≈ 20%), and the
starting point plus what each group contributes adds up exactly to the percentage for the hour.

## 4. Full test results (2024–2026)

Years never used for training or for choosing settings. **Hour by hour, against what really happened**
(8,577 night hours; "close" = the forecast crosses one of the label's limits, or the model's probability ≥
50%):

| | Hours with the dome closed | Right | Closes when not needed | Leaves it open when it should close |
|---|---|---|---|---|
| What really happened (measured at the summit) | 1,453 h | — | — | — |
| The weather forecast on its own | 6,111 h | 43% of hours | 4,756 h | 98 h |
| **RoqueModel (final)** | **1,390 h** | **91% of hours** | 351 h | 414 h |
| RoqueModel (provisional) | 1,237 h | 89% of hours | 385 h | 601 h |

Against other simple baselines:

| Forecast | Baselines | RoqueModel (final) |
|---|---|---|
| Dome closed, each hour | forecast as is: right on 22 of every 100 "close" calls; humidity just before the night (precasting): 67 of every 100 | **right on 75 of every 100 "close" calls and detects 72 of every 100 closed hours**; Brier 0.063, AUC 0.95 |
| Closed hours of the night (1,028 nights) | the usual for the month: off by 2.0 h; same as last night: 1.3 h; forecast as is: 4.7 h | **off by 0.9 h on average** (provisional: 1.2 h) |
| Seeing for the night (780 nights; FIWARE only, not on the website) | the usual for the month: off by 0.23″; same as last night: 0.28″ | **off by 0.20″** (RMSE 0.284″ versus 0.350″) |

**Why the forecast on its own fails so badly:** the weather model sees the mountain as lower than it is, inside
the sea of clouds that lies below the summit, so, read as is, it says "close" for most of the
night hours. RoqueModel learns to correct this from years of archived forecasts compared with what happened at the
summit.

## 5. Tried and discarded

Documented in [MODELS_01](../reports/MODELS_01.en.md):

- separate per-night models for closure and for WHT hours lost (replaced by the hourly model and its
  sum);
- Liverpool Telescope models for hours lost and for clear sky (the clear-sky one barely improves on
  "same as last night": Brier skill 0.17 versus 0.12);
- a dust alert with CAMS (too few cases);
- hour-by-hour seeing (it does not improve on the per-night model);
- isotonic recalibration of the probabilities (no improvement).

## 6. Findings from the data

- A closing rule rebuilt from humidity alone tracks the hours the WHT really lost to the
  weather (r = 0.74 in 2007–2018), but falls short in winter; adding strong wind and ice closes
  most of that gap.
- The WHT's night accounting is not equally reliable every year: since 2019, many nights with the domes
  closed because of humidity appear as fully observed. That is why those years (2019–2022, 2024–2025) were not
  used in the study of WHT hours lost (RoqueModel does not use the WHT).
- Wind has the strongest influence on seeing (Spearman +0.58 with the night's maximum wind); easterly
  winds give the worst seeing.
- For seeing, the monthly climatology (RMSE 0.34″) beats "same as last night" (0.41″): that is the bar
  a model has to clear.

Full analysis: [EDA_01](../reports/EDA_01.en.md) ([notebook](../notebooks/01_eda.ipynb)) and
[MODELS_01](../reports/MODELS_01.en.md) ([notebook](../notebooks/02_models.ipynb)).

## 7. How each hour works

1. **GitHub Actions** (`.github/workflows/forecast.yml`) installs the package from `uv.lock` and downloads the
   trained models from the `runtime` release. `scripts/build_runtime.sh` packages them and has to be run
   again after retraining.
2. `tonight.py` downloads the latest forecast (ECMWF and GFS from Open-Meteo), the NOT weather station and last
   night's seeing, decides whether the provisional or the final model applies and writes `site/data/tonight.json`.
   If a source does not respond, it uses that source's last good copy and the website shows a warning.
3. `site_data.py` writes `site/data/evaluation.json`: the accuracy figures shown on the website.
4. `scripts/publish_site.sh` pushes `site/` to the `gh-pages` branch as a single commit, so that the
   hourly updates do not pile up in the history of `main`. GitHub Pages serves it.
5. `tonight.py` also publishes the forecast to **FIWARE** (section 8), and the **public Grafana
   Cloud dashboard** reads it from there: the website and Grafana give the same figures because they come from the
   same calculation. There is a dashboard in Spanish (`/grafana/`) and another in English (`/grafana/en/`); both are
   generated by `cloud_dashboard.py`. The website has both languages at the same address (ES · EN switch, or
   `?lang=en`), with all its texts in `site/assets/i18n.js`.

Each run is logged (`forecasts/issued.jsonl`, published with the website) together with what really happened
the previous night (`outcomes.jsonl`): it is a live track record that no choice of settings has
seen. The GitHub scheduler skips many runs on repositories with little activity, so the
workflow is launched every hour by the FIWARE server (cron at :05, `infra/cloud/monitor.py --launch`: it pushes an
empty commit to the `kick` branch, with a key that can only write to this repository). It does not depend on any
personal computer; the GitHub scheduler remains as a fallback.

**Hourly monitoring** (`infra/cloud/monitor.py`, server cron at :35): it checks the website (a recent, consistent
forecast: probabilities between 0 and 1, open + closed hours = the night, the right model for the time of
day), FIWARE (Orion, QuantumLeap, that it matches the website, recent history, writes without a token rejected,
HTTPS certificate), the public Grafana dashboard (it opens and its panels have data), GitHub (latest runs
successful and workflows active) and the server itself (containers, disk, memory). It fixes only what it can
(it starts stopped containers and relaunches the forecast if it has not run for more than 3 hours) and sends email
alerts through Healthchecks.io, which also alerts if the check stops arriving (server down). Current status:
![monitoring](https://healthchecks.io/b/2/0437fc28-5880-4f5a-b616-9f2a2ea0c8bb.svg)

**Errors with Sentry** (`observability.py`): on GitHub Actions, `tonight` and `site_data` send to
[Sentry](https://sentry.io) any exception and any logged error (for example, a write to FIWARE
that fails), with the stack trace, the commit that was running and what was logged before it. Warnings (a source that
does not respond and is replaced by its last copy) are not sent on their own. Without `SENTRY_DSN` (on the Mac, in
the tests) nothing is sent. Healthchecks.io says *that* something is wrong; Sentry says *why*.

## 8. FIWARE

[FIWARE](https://www.fiware.org) is the open platform for sensor (IoT) data that the GTC uses. RoqueModel
publishes its forecast every hour as NGSI-v2 entities in the standard format of
[Smart Data Models](https://github.com/smart-data-models/dataModel.Weather) (`fiware.py`), and the public
Grafana dashboard reads from there, as on the GTC platform.

| Entity | Type | What it contains |
|---|---|---|
| `urn:ngsi-ld:WeatherForecast:ORM-tonight` | `WeatherForecast` | tonight's forecast: closed hours, probability for each hour, the forecast on its own, the hour-by-hour weather forecast and the predicted seeing |
| `urn:ngsi-ld:WeatherObserved:ORM-NOT` | `WeatherObserved` | the NOT weather station; its history (10-minute means) goes to QuantumLeap |
| `urn:ngsi-ld:WeatherObserved:ORM-GTC` | `WeatherObserved` | local only: the GTC live panel (current value; its history is not stored) |

**In production** (`infra/cloud/`): a small cloud server (Hetzner CAX11, ARM) with Orion (current
state, on MongoDB) and QuantumLeap (history, on CrateDB), behind Caddy, which provides automatic HTTPS and
controls access: anyone can read, and only the hourly forecast (GitHub Actions, with a token) can
write. Orion and QuantumLeap are only published for x86, so on that ARM server they run under emulation.

- Current state: https://178-105-253-255.sslip.io/orion/v2/entities?options=keyValues
- History: https://178-105-253-255.sslip.io/ql/v2/entities/urn:ngsi-ld:WeatherObserved:ORM-NOT?lastN=10

**Locally**, the same stack with Docker and a Grafana dashboard of its own (`infra/docker-compose.yml`, `dashboards.py`).
If it is not running, the forecast carries on and skips this step.

```bash
docker compose -f infra/docker-compose.yml up -d     # Orion :1027, QuantumLeap :8669, CrateDB :4201, Grafana :3001
.venv/bin/python -m roque_forecast.fiware provision  # Orion -> QuantumLeap subscription (once)
```

## 9. All the commands

```bash
uv sync                                                  # creates .venv and installs the dependencies
.venv/bin/python -m pytest                               # runs the tests
.venv/bin/python -m roque_forecast.backfill not          # historical download (also: r2d2, ing); resumable
.venv/bin/python -m roque_forecast.build_tables          # raw files -> data/processed/*.parquet
.venv/bin/python -m roque_forecast.backfill forecasts    # archived Open-Meteo forecasts
.venv/bin/python -m roque_forecast.features              # modelling table and labels
.venv/bin/python -m roque_forecast.train                 # per-night models (seeing) -> reports/results/
.venv/bin/python -m roque_forecast.compare               # settings search and model comparison
.venv/bin/python -m roque_forecast.hourly                # RoqueModel -> reports/results/hourly_scores.csv
.venv/bin/python -m roque_forecast.backfill liverpool    # Liverpool Telescope night reports
.venv/bin/python -m roque_forecast.validate              # label check -> reports/results/validation.json
.venv/bin/python -m roque_forecast.export_data           # downloadable training data
.venv/bin/python -m roque_forecast.tonight               # tonight's forecast -> site/data/tonight.json
.venv/bin/python -m roque_forecast.site_data             # evaluation and history -> site/data/evaluation.json
.venv/bin/python -m roque_forecast.dashboards            # local Grafana dashboard for FIWARE
.venv/bin/python -m roque_forecast.cloud_dashboard       # public Grafana Cloud dashboard
```

## 10. Code structure

```
src/roque_forecast/
  config.py          observatory coordinates, folders, polite-download settings
  polite_http.py     shared HTTP client (User-Agent, waiting, retries)
  sources/           one module per data source: download + parsing
  collect.py         collector: GTC live panel to FIWARE (stores nothing)
  backfill.py        bulk, resumable download of the historical archives
  build_tables.py    raw files -> clean Parquet tables
  astro.py           Sun altitude and astronomical night (NOAA formulas)
  dome.py            minute-by-minute closing label: humidity, strong wind, ice
  features.py        modelling table: forecast + station before the night + last night + time of year
  train.py           per-night models: seeing (live), closure and WHT hours (study only)
  compare.py         settings search and model comparison
  hourly.py          RoqueModel: hourly closure, provisional and final, against the baselines
  explain.py         breakdown of each hour (exact Shapley values)
  validate.py        label check against the Liverpool Telescope, year by year
  tonight.py         tonight's forecast with live data
  site_data.py       evaluation and live history for the website
  export_data.py     downloadable training data
  fiware.py          NGSI-v2 entities, Orion and QuantumLeap
  dashboards.py      local Grafana dashboard for FIWARE
  cloud_dashboard.py public Grafana Cloud dashboard
  plotting.py        shared figure style
site/                static website (index.html, assets/; data/ is generated)
infra/               Docker Compose (Orion, QuantumLeap, CrateDB, Grafana) and dashboards
scripts/             hourly update, publishing and model release
notebooks/           analysis notebooks (.py source + executed .ipynb)
reports/             reports, figures and metrics tables
tests/               tests with small real files (tests/fixtures/); run on every push (tests.yml)
launchd/             templates for scheduling the update on macOS
data/                downloaded data (not in git)
```
