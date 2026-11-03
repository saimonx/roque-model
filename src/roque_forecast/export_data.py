"""Export the exact data RoqueModel learnt from, so anyone can download and check them.

Two CSV files, plus a README with what every column means and where it comes from,
packed into one zip (data/export/roquemodel_data.zip):

- roquemodel_training_hours.csv: one row per night hour, 2017-2026, with the label
  (was the dome closed?) and the inputs the model saw. These are the 30,044 hours the
  live RoqueModel was fitted on (hourly.py drops the hours without a label).
- roquemodel_test_predictions.csv: the 2024-2026 hours the tested copy had never seen,
  with its answer, the forecast-alone answer and the truth. The accuracy on the page
  (wrong in about 9 of 100 hours) can be recomputed from this file alone.

Nothing here is new data: both files are written from the tables in data/processed
(hourly.py), which are built from public sources by backfill.py and build_tables.py.
scripts/build_runtime.sh runs this module and uploads the zip to the "training-data"
release, where the web page and the README link to it.

Usage:
    .venv/bin/python -m roque_forecast.export_data
"""

import logging
import sys
import zipfile

import pandas as pd

from roque_forecast import config, dome, hourly, train

log = logging.getLogger("export_data")

OUT_DIR = config.DATA_DIR / "export"
ZIP_PATH = OUT_DIR / "roquemodel_data.zip"
TRAINING_CSV = "roquemodel_training_hours.csv"
TEST_CSV = "roquemodel_test_predictions.csv"
README = "README.md"

NOT_SOURCE = "NOT weather station (not.iac.es/weather/archive/met)"
OM_ECMWF = "ECMWF IFS forecast archived by Open-Meteo (historical-forecast-api.open-meteo.com)"
OM_GFS = "NOAA GFS forecast archived by Open-Meteo (historical-forecast-api.open-meteo.com)"
R2D2_SOURCE = "ING R2D2 seeing monitor (astro.ing.iac.es/seeing)"

# What each column of the training file means: (unit, meaning, source). The README is
# written from this table, so the file and its description cannot drift apart.
COLUMNS = {
    "night": ("date", "Night it belongs to: the date of the evening it starts", "calendar"),
    "hour_utc": ("UTC", "Start of the hour (one row per hour with at least 30 min of astronomical night)", "calendar"),
    "split": ("", ("fit (2017-2023: the tested copy learnt from these years, and its settings were chosen "
                  "on 2021, 2022 and 2023, leaving each one out in turn) or test (2024-2026, never seen); "
                  "the live model was refitted on all of them"), "project"),
    "closed": ("0/1", ("THE LABEL: 1 if the dome counts as closed for at least half of the hour "
                      f"(humidity >= {dome.HUMIDITY_LIMIT_PCT:.0f} %, wind >= {dome.WIND_LIMIT_MS} m/s or ice), "
                      "rebuilt minute by minute"), NOT_SOURCE),
    "closed_frac": ("0-1", "Share of the hour's minutes with the dome closed (the label is closed_frac >= 0.5)", NOT_SOURCE),
    "measured_minutes": ("min", "Minutes of the hour the station measured (the label needs at least 45)", NOT_SOURCE),
    "dark_minutes": ("min", "Minutes of astronomical night in the hour", "computed (astro.py)"),
    "h_rh": ("%", "Forecast relative humidity at mid-hour", OM_ECMWF),
    "h_dew_spread": ("°C", "Forecast temperature minus dew point at mid-hour", OM_ECMWF),
    "h_temp": ("°C", "Forecast temperature at mid-hour", OM_ECMWF),
    "h_wind": ("m/s", "Forecast 10 m wind at mid-hour", OM_ECMWF),
    "h_wind_u": ("m/s", "Forecast 10 m wind, west-east component", OM_ECMWF),
    "h_wind_v": ("m/s", "Forecast 10 m wind, south-north component", OM_ECMWF),
    "h_cloud": ("%", "Forecast cloud cover at mid-hour", OM_ECMWF),
    "h_precip": ("mm", "Forecast rain during the hour", OM_ECMWF),
    "h_pressure": ("hPa", "Forecast surface pressure at mid-hour", OM_ECMWF),
    "h_wind_750": ("m/s", "Forecast wind at 750 hPa (~2.5 km, summit height); empty before March 2021", OM_GFS),
    "hour_of_night": ("", "Position of the hour in the night (0 = first)", "computed (astro.py)"),
    "night_fraction": ("0-1", "Position of the hour as a share of the night", "computed (astro.py)"),
    "fc_rh_mean": ("%", "Forecast humidity, mean over the night", OM_ECMWF),
    "fc_rh_max": ("%", "Forecast humidity, maximum over the night", OM_ECMWF),
    "fc_dew_spread_min": ("°C", "Forecast temperature minus dew point, minimum over the night", OM_ECMWF),
    "fc_temp_mean": ("°C", "Forecast temperature, mean over the night", OM_ECMWF),
    "fc_temp_drop": ("°C", "Forecast temperature at the start of the night minus at the end", OM_ECMWF),
    "fc_wind_mean": ("m/s", "Forecast 10 m wind, mean over the night", OM_ECMWF),
    "fc_wind_max": ("m/s", "Forecast 10 m wind, maximum over the night", OM_ECMWF),
    "fc_wind_u": ("m/s", "Forecast wind west-east component, mean over the night", OM_ECMWF),
    "fc_wind_v": ("m/s", "Forecast wind south-north component, mean over the night", OM_ECMWF),
    "fc_cloud_mean": ("%", "Forecast cloud cover, mean over the night", OM_ECMWF),
    "fc_cloud_max": ("%", "Forecast cloud cover, maximum over the night", OM_ECMWF),
    "fc_precip_sum": ("mm", "Forecast rain, total over the night", OM_ECMWF),
    "fc_pressure_mean": ("hPa", "Forecast pressure, mean over the night", OM_ECMWF),
    "pre_humidity_mean": ("%", "Measured humidity in the 2 h before the night, mean", NOT_SOURCE),
    "pre_humidity_max": ("%", "Measured humidity in the 2 h before the night, maximum", NOT_SOURCE),
    "pre_wind_mean": ("m/s", "Measured wind in the 2 h before the night, mean", NOT_SOURCE),
    "pre_pressure_mean": ("hPa", "Measured pressure in the 2 h before the night, mean", NOT_SOURCE),
    "prev_dome_closed_frac": ("0-1", "Last night: share of its minutes with the dome closed", NOT_SOURCE),
    "prev_seeing_median": ("arcsec", "Last night: median seeing; empty when it could not measure", R2D2_SOURCE),
    "doy_sin": ("", "Time of year: sine of the day of the year", "calendar"),
    "doy_cos": ("", "Time of year: cosine of the day of the year", "calendar"),
}

TEST_COLUMNS = {
    "night": ("date", "Night it belongs to", "calendar"),
    "hour_utc": ("UTC", "Start of the hour", "calendar"),
    "closed": ("0/1", "What happened (the label, as in the training file)", NOT_SOURCE),
    "p_final": ("0-1", "RoqueModel final (with the station before the night): chance the dome is closed", "RoqueModel"),
    "p_provisional": ("0-1", "RoqueModel provisional (forecast only, used in the afternoon)", "RoqueModel"),
    "forecast_alone": ("0/1", "The closing rules applied to the forecast as it is (1 = close)", OM_ECMWF),
    "climatology": ("0-1", "Share of closed hours in that month in 2017-2023 (the simplest reference)", "project"),
}


def training_table() -> pd.DataFrame:
    """The labelled night hours, with the label, its details and the model inputs, in that order."""
    table = pd.read_parquet(config.PROCESSED_DIR / "hour_table.parquet").dropna(subset=["closed"])
    nights = table.index.get_level_values("night")
    table["split"] = "fit"
    table.loc[nights >= train.TEST_START, "split"] = "test"
    out = table.reset_index().rename(columns={"hour": "hour_utc"})
    out["night"] = out["night"].dt.date
    out["closed"] = out["closed"].astype(int)
    columns = list(COLUMNS)
    # Every model input must be described here: a new input without a description fails loudly.
    missing = [c for c in hourly.CLOSURE_FEATURES if c not in columns]
    if missing:
        raise KeyError(f"inputs without a description in COLUMNS: {missing}")
    return out[columns]


def test_table() -> pd.DataFrame:
    """The tested copy's answers on 2024-2026, hour by hour."""
    pred = pd.read_parquet(config.PROCESSED_DIR / "hour_predictions.parquet")
    out = pred.reset_index().rename(columns={"hour": "hour_utc", "raw": "forecast_alone"})
    out["night"] = out["night"].dt.date
    out["closed"] = out["closed"].astype(int)
    out["forecast_alone"] = out["forecast_alone"].astype(int)
    return out[list(TEST_COLUMNS)]


def wrong_share(test: pd.DataFrame, column: str) -> float:
    """Share of hours where the answer (>= 0.5 means "closed") is not what happened, as on the page."""
    return float(((test[column] >= 0.5).astype(int) != test["closed"]).mean())


def column_table(columns: dict) -> str:
    rows = ["| Column | Unit | Meaning | Source |", "|---|---|---|---|"]
    rows += [f"| `{name}` | {unit} | {meaning} | {source} |" for name, (unit, meaning, source) in columns.items()]
    return "\n".join(rows)


def readme(training: pd.DataFrame, test: pd.DataFrame) -> str:
    provisional = ", ".join(f"`{c}`" for c in hourly.CLOSURE_FORECAST_ONLY)
    scores = {c: wrong_share(test, c) for c in ("p_final", "p_provisional", "forecast_alone")}
    first, last = training["night"].min(), training["night"].max()
    return f"""# RoqueModel: the data it learnt from

Independent project, not affiliated with GRANTECAN or any observatory.
Code: https://github.com/saimonx/roque-model · Page: https://saimonx.github.io/roque-model/

## Files

- `{TRAINING_CSV}`: {len(training):,} night hours from {first} to {last}, {int(training["closed"].sum()):,} of them
  with the dome closed. These are exactly the rows the live RoqueModel was fitted on. The final model uses
  the {len(hourly.CLOSURE_FEATURES)} input columns from `h_rh` to `doy_cos`; the provisional model (afternoon,
  before the night) uses only {provisional}.
- `{TEST_CSV}`: {len(test):,} hours of 2024-2026 that the tested copy (trained on 2017-2023 only) had never
  seen. Counting "closed" when the value is 0.5 or more, it is wrong in {scores["p_final"]:.1%} of the hours
  (provisional {scores["p_provisional"]:.1%}; forecast alone {scores["forecast_alone"]:.1%}).

Check it yourself, for example in Python:

```python
import pandas as pd
t = pd.read_csv("{TEST_CSV}")
print(((t.p_final >= 0.5).astype(int) != t.closed).mean())   # {scores["p_final"]:.3f}
```

## Where the numbers come from

All inputs are things that were known before the night started. Nothing is simulated.

- **Label and station inputs:** the NOT weather station, one reading per minute
  (https://www.not.iac.es/weather/archive/met/index.php, "Raw Data"). The dome counts as closed when
  humidity is {dome.HUMIDITY_LIMIT_PCT:.0f} % or more (it reopens after 20 minutes below), when the wind
  reaches {dome.WIND_LIMIT_MS} m/s (80 km/h), or when there is ice ({dome.ICE_TEMP_C:.0f} °C or less after
  {dome.HUMIDITY_LIMIT_PCT:.0f} % humidity in the previous 24 h).
- **Forecast inputs:** what the ECMWF IFS model forecast for each hour, as archived by Open-Meteo
  (https://open-meteo.com, CC BY 4.0), at 28.7566 N, 17.8919 W, 2,270 m. The 750 hPa wind comes from the
  NOAA GFS archive (same service). Any day can be fetched again, for example:
  https://historical-forecast-api.open-meteo.com/v1/forecast?latitude=28.7566&longitude=-17.8919&elevation=2270&models=ecmwf_ifs&timezone=UTC&wind_speed_unit=ms&hourly=relative_humidity_2m,temperature_2m&start_date=2024-01-01&end_date=2024-01-02
- **Last night's seeing:** the ING R2D2 monitor (https://astro.ing.iac.es/seeing/).

The code that downloads the sources and builds these tables is in the repository (`backfill.py`,
`build_tables.py`, `features.py`, `hourly.py`; this file: `export_data.py`).

## Columns: {TRAINING_CSV}

{column_table(COLUMNS)}

## Columns: {TEST_CSV}

{column_table(TEST_COLUMNS)}

## Credits and licences

Data from the Nordic Optical Telescope (NOT), the Isaac Newton Group (ING) and Open-Meteo (CC BY 4.0;
forecasts by ECMWF and NOAA). Hourly values here are derived from their public data; please cite them.
"""


def export() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    training, test = training_table(), test_table()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(TRAINING_CSV, training.to_csv(index=False, float_format="%.6g"))
        z.writestr(TEST_CSV, test.to_csv(index=False, float_format="%.6g"))
        z.writestr(README, readme(training, test))
    info = {"hours": len(training), "closed": int(training["closed"].sum()), "test_hours": len(test),
            "wrong_final": round(wrong_share(test, "p_final"), 3), "mb": round(ZIP_PATH.stat().st_size / 1e6, 1)}
    log.info("written %s %s", ZIP_PATH.relative_to(config.PROJECT_DIR), info)
    return info


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    export()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
