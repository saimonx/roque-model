# Roque Night Forecast

Forecasting observing conditions at the **Roque de los Muchachos Observatory** (La Palma, Canary Islands):
will the dome have to close tonight, how good will the seeing be, and how many hours are likely
to be lost to weather.

> **Independent project.** This is a personal portfolio project. It is **not affiliated with,
> endorsed by or produced for** GRANTECAN, the IAC, the ING, the NOT, the TNG or any other
> institution. All data come from their public web pages and are credited below.

## Status

| Step | State |
|---|---|
| Python environment, project layout, polite downloaders for 5 public sources | done |
| Live collectors (GTC panel every 15 min, TNG 24 h series, GTC 30-day series) | running |
| Bulk historical download (NOT 1997+, R2D2 2018+, ING nights 2007+) | done |
| Clean tables (Parquet) and exploratory analysis — [report](reports/EDA_01.md), [notebook](notebooks/01_eda.ipynb) | done |
| Models: dome-closure risk, seeing, hours lost, honest baselines — [report](reports/MODELS_01.md), [notebook](notebooks/02_models.ipynb) | done |
| Tonight's forecast, live (same models, current Open-Meteo forecast + NOT station) | done |
| FIWARE entities (`WeatherObserved`, `WeatherForecast`) in Orion + QuantumLeap + Grafana (ES/EN) | done (local) |
| Bilingual (ES/EN) web page with tonight's forecast and the evaluation | done (local); GitHub Pages when public |

## Results (test years 2024–2026, never used for training or tuning)

| Forecast | Best reference method | Model |
|---|---|---|
| Dome closure (≥ 1 h closed by the humidity rule) | precasting: Brier 0.082, skill 0.45 | gradient boosting: Brier **0.067**, skill **0.55**, AUC 0.96 |
| Median seeing of the night | climatology: RMSE 0.350″ | gradient boosting: RMSE **0.286″** (−18 %) |
| WHT hours lost to weather (2026, reliable log) | climatology: RMSE 2.99 h; persistence: MAE 1.42 h | calibrated closure forecast: RMSE **2.65 h**, MAE **1.36 h** |

Skill is against monthly climatology. The models use only what is known at the start of the night:
- the ECMWF forecast, taken from forecast archives and not from the weather measured later;
- the NOT station in the 2 previous hours;
- last night's outcome;
- the season.

The results hold with forecasts issued 24 h earlier. Details and caveats are in the
[models report](reports/MODELS_01.md).

![Closure skill](reports/figures/06_closure_skill.png)

## Key findings from the data

- The dome-closure rule rebuilt from humidity tracks the hours the WHT really lost to weather (r = 0.74 in 2007–2018, 90 % agreement on "most of the night lost"), but misses winter losses caused by wind, dust or ice.
- The WHT accounting is not equally reliable every year: since 2019 many nights with the domes closed by humidity are reported as fully observed with zero losses. Those years (2019–2022, 2024–2025) are kept out of model fitting and shown only for comparison.
- Wind is the strongest driver of seeing (Spearman +0.58 with the night's maximum wind); easterly winds give the worst seeing.
- For seeing, the monthly climatology (RMSE 0.34″) beats "same as last night" (0.41″): that is the bar a model must clear.

![Seeing vs weather](reports/figures/03_seeing_vs_weather.png)

## Data sources (all real, all public)

| Source | What we use | Coverage |
|---|---|---|
| [NOT weather archive](https://www.not.iac.es/weather/archive/met/index.php) (Nordic Optical Telescope) | temperature, humidity, pressure, wind (every 5 min until 2006, every minute since) | 1997 → today |
| [ING R2D2 seeing monitor](https://astro.ing.iac.es/seeing/) (Isaac Newton Group) | DIMM seeing, every 15–35 s at night | Sep 2018 → today |
| [ING nightly accounting](https://a.ing.iac.es/weather/archive/) | hours lost to weather / technical problems on the WHT, Moon illumination | 2007 → today |
| [GTC atmosportal](https://atmosportal.gtc.iac.es/) (Gran Telescopio Canarias weather station) | ~11 s series (last 30 days only) and live panel incl. rain, PM10 dust and warning colours | collected by this project from Oct 2026 |
| [TNG weather](https://tngweb.tng.iac.es/weather) (Telescopio Nazionale Galileo) | 1-min series of the last 24 h, dust counts by particle size, downtime | collected by this project from Oct 2026 |
| [Open-Meteo](https://open-meteo.com) forecasts and archives ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)) | ECMWF IFS HRES 9 km hourly forecasts at the site: today's forecast, historical-forecast archive and forecasts issued 24 h earlier | 2017 → today (24 h earlier: 2025 → today) |

Downloads identify themselves with a descriptive User-Agent, wait at least 2 s between requests and
only use pages linked from the public sites. No simulated data are used in this project; any
simulated data in future projects will be labelled as such.

### Scientific references
- Abárzuza et al. 2025, *RNAAS* 9(2), [doi:10.3847/2515-5172/adb14f](https://doi.org/10.3847/2515-5172/adb14f) — random forest predicting seeing at the Roque from weather-station data.
- de Sepibus, Masciadri et al. 2026, [arXiv:2607.12900](https://arxiv.org/abs/2607.12900) — persistence and "precasting" as minimum baselines for seeing forecasts.
- Lombardi et al. 2007, [arXiv:astro-ph/0702570](https://arxiv.org/abs/astro-ph/0702570) — wind and humidity vs. seeing at the Roque.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 if needed).

```bash
uv sync                                          # create .venv and install dependencies
.venv/bin/python -m pytest                       # run the tests
.venv/bin/python -m roque_forecast.backfill not  # historical download (also: r2d2, ing); resumable
.venv/bin/python -m roque_forecast.build_tables  # raw files -> data/processed/*.parquet
.venv/bin/python -m roque_forecast.backfill forecasts  # archived Open-Meteo forecasts (~30 s)
.venv/bin/python -m roque_forecast.features      # one row per night: inputs known at sunset + labels
.venv/bin/python -m roque_forecast.train         # fit, compare with baselines -> reports/results/
```

### Tonight's forecast and the web page

```bash
.venv/bin/python -m roque_forecast.tonight      # live data + models -> site/data/tonight.json
.venv/bin/python -m roque_forecast.site_data    # evaluation + live track record -> site/data/evaluation.json
.venv/bin/python -m http.server 8765 -d site    # open http://localhost:8765 (?lang=es or ?lang=en)
scripts/update_tonight.sh                       # both steps (hourly job); ROQUE_PUBLISH=1 also publishes
```

![Web page, Spanish version (28 Oct 2026)](reports/figures/13_web_es.jpg)

Two modes, so a forecast never uses information it could not have had:
- **provisional** (afternoon): forecast-only models (weather forecast, last night, season);
- **final** (from the start of astronomical night): the full models, adding the NOT station in the 2 h
  before the night. This is the forecast evaluated in [MODELS_01](reports/MODELS_01.md).

Every run is logged in `data/forecasts/issued.jsonl`. Each run also records what really happened the
night before (`outcomes.jsonl`), so the page builds a **live track record**, scoring the first final
forecast of each night.

`scripts/publish_site.sh` force-pushes `site/` to a `gh-pages` branch as a single commit, so hourly
updates never pile up in the history of `main`.

### FIWARE + Grafana (local, Docker)

```bash
docker compose -f infra/docker-compose.yml up -d     # Orion :1027, QuantumLeap :8669, Grafana :3001
.venv/bin/python -m roque_forecast.fiware provision  # subscription Orion -> QuantumLeap (once)
.venv/bin/python -m roque_forecast.fiware backfill   # optional: last 30 days of both stations
.venv/bin/python -m roque_forecast.dashboards        # regenerate the ES and EN dashboards
```

| Entity | Type ([Smart Data Models](https://github.com/smart-data-models/dataModel.Weather)) | Updated by |
|---|---|---|
| `urn:ngsi-ld:WeatherObserved:ORM-GTC` | `WeatherObserved` | `collect live` (every 15 min) |
| `urn:ngsi-ld:WeatherObserved:ORM-NOT` | `WeatherObserved` | `tonight` (hourly) |
| `urn:ngsi-ld:WeatherForecast:ORM-tonight` | `WeatherForecast` (+ closure probability, seeing, hours lost) | `tonight` (hourly) |

![Grafana dashboard, Spanish version (28 Oct 2026)](reports/figures/14_grafana_es.jpg)

Ports are shifted by one from the FIWARE defaults, so the stack can run next to another FIWARE stack.
If Docker is not running, the forecast and the collectors carry on and skip this step.

### Collectors (macOS)

```bash
scripts/install_collectors.sh               # install the 3 LaunchAgents
scripts/install_collectors.sh --uninstall   # remove them
```

| Agent | When | What |
|---|---|---|
| `live` | every 15 min | GTC live panel + TNG current values → `data/raw/live/YYYY-MM/YYYY-MM-DD.jsonl` |
| `daily` | 10:07 and 22:07 | TNG last-24 h series + downtime → `data/raw/tng/YYYY-MM-DD/` |
| `weekly` | Monday 10:23 | GTC last-30-days series → `data/raw/gtc_atmosportal/YYYY-MM-DD/` |
| `tonight` (optional: `install_collectors.sh tonight`) | every hour at :05 | `scripts/update_tonight.sh` |

## Layout

```
src/roque_forecast/
  config.py          site coordinates, folders, polite-download settings
  polite_http.py     shared HTTP client (User-Agent, delay, retries)
  collect.py         command-line collector (live / daily / weekly / sample)
  backfill.py        resumable bulk download of the historical archives
  build_tables.py    raw files -> clean Parquet tables (minutes, R2D2 points, ING nights, nights)
  astro.py           Sun altitude and astronomical night (NOAA formulas, checked against ING)
  dome.py            dome-closure rule rebuilt from humidity
  features.py        modelling table: forecast + pre-night station + persistence + season, and labels
  train.py           time-split training, baselines, metrics, permutation importance
  plotting.py        shared figure style (colour-blind-safe palette)
  tonight.py         tonight's forecast from live data (provisional / final modes)
  site_data.py       evaluation and live track record for the web page
  fiware.py          NGSI-v2 entities, Orion updates, QuantumLeap subscription and backfill
  dashboards.py      Grafana dashboards (Spanish and English) from one definition
site/                static bilingual web page (index.html, assets/; data/ is generated)
infra/               Docker Compose for Orion, QuantumLeap, CrateDB and Grafana
scripts/             LaunchAgent installer, hourly update and gh-pages publishing
notebooks/           analysis notebooks (.py source + executed .ipynb)
reports/             written findings, figures and metric tables (reports/results/)
  sources/           one module per data source: download + parse
tests/               parser tests on small real files (tests/fixtures/), time-window and split tests
launchd/             LaunchAgent templates
data/                downloaded data (not in git)
```
