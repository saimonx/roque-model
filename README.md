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
| Models: dome-closure risk, seeing, hours lost, honest baselines | next |
| FIWARE `WeatherObserved` ingestion + Grafana panel | planned |
| Bilingual (EN/ES) local web with tonight's forecast | planned |

## Key findings so far

- The dome-closure rule rebuilt from humidity tracks the hours the WHT really lost to weather (r = 0.74 in 2007–2018, 90 % agreement on "most of the night lost"), but misses winter losses caused by wind, dust or ice.
- The WHT accounting is not equally reliable every year: since 2019 many nights with the domes closed by humidity are reported as fully observed with zero losses. Those 218 suspect nights must be handled before the losses are used as a training label.
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
```

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
  plotting.py        shared figure style (colour-blind-safe palette)
notebooks/           analysis notebooks (.py source + executed .ipynb)
reports/             written findings and figures
  sources/           one module per data source: download + parse
tests/               parser tests on small real files (tests/fixtures/)
launchd/             LaunchAgent templates
data/                downloaded data (not in git)
```
