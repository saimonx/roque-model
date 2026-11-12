"""Export the exact data RoqueModel learnt from, so anyone can download and check them.

Two CSV files, plus a README in Spanish and another in English with what every column means and where it comes from,
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
README_EN = "README.en.md"

def spanish(number: float) -> str:
    """A decimal number written the Spanish way: 22.2 -> 22,2."""
    return str(number).replace(".", ",")


def thousands(number: int) -> str:
    """A whole number written the Spanish way: 30044 -> 30.044."""
    return f"{number:,}".replace(",", ".")


NOT_SOURCE = "Estación meteorológica del NOT (not.iac.es/weather/archive/met)"
OM_ECMWF = "Previsión ECMWF IFS archivada por Open-Meteo (historical-forecast-api.open-meteo.com)"
OM_GFS = "Previsión NOAA GFS archivada por Open-Meteo (historical-forecast-api.open-meteo.com)"
R2D2_SOURCE = "Monitor de seeing R2D2 del ING (astro.ing.iac.es/seeing/index.php)"

# What each column of the training file means: (unit, meaning, source), in Spanish because the
# README is written from this table, so the file and its description cannot drift apart.
COLUMNS = {
    "night": ("fecha", "Noche a la que pertenece: la fecha de la tarde en que empieza", "calendario"),
    "hour_utc": ("UTC", "Inicio de la hora (una fila por cada hora con al menos 30 min de noche astronómica)", "calendario"),
    "split": ("", ("fit (2017-2023: la copia probada aprendió de estos años, y sus ajustes se eligieron con "
                  "2021, 2022 y 2023, dejando cada uno fuera por turnos) o test (2024-2026, nunca vistos); "
                  "el modelo en directo se volvió a entrenar con todos"), "proyecto"),
    "closed": ("0/1", ("LA ETIQUETA: 1 si la cúpula cuenta como cerrada al menos la mitad de la hora "
                      f"(humedad >= {dome.HUMIDITY_LIMIT_PCT:.0f} %, viento >= {spanish(dome.WIND_LIMIT_MS)} m/s o hielo), "
                      "reconstruida minuto a minuto"), NOT_SOURCE),
    "closed_frac": ("0-1", "Parte de los minutos de la hora con la cúpula cerrada (la etiqueta es closed_frac >= 0.5)", NOT_SOURCE),
    "measured_minutes": ("min", "Minutos de la hora que midió la estación (la etiqueta necesita al menos 45)", NOT_SOURCE),
    "dark_minutes": ("min", "Minutos de noche astronómica en la hora", "calculado (astro.py)"),
    "h_rh": ("%", "Humedad relativa prevista a mitad de la hora", OM_ECMWF),
    "h_dew_spread": ("°C", "Temperatura prevista menos punto de rocío a mitad de la hora", OM_ECMWF),
    "h_temp": ("°C", "Temperatura prevista a mitad de la hora", OM_ECMWF),
    "h_wind": ("m/s", "Viento previsto a 10 m a mitad de la hora", OM_ECMWF),
    "h_wind_u": ("m/s", "Viento previsto a 10 m, componente oeste-este", OM_ECMWF),
    "h_wind_v": ("m/s", "Viento previsto a 10 m, componente sur-norte", OM_ECMWF),
    "h_cloud": ("%", "Nubosidad prevista a mitad de la hora", OM_ECMWF),
    "h_precip": ("mm", "Lluvia prevista durante la hora", OM_ECMWF),
    "h_pressure": ("hPa", "Presión en superficie prevista a mitad de la hora", OM_ECMWF),
    "h_wind_750": ("m/s", "Viento previsto a 750 hPa (~2,5 km, la altura de la cumbre); vacío antes de marzo de 2021", OM_GFS),
    "hour_of_night": ("", "Posición de la hora en la noche (0 = la primera)", "calculado (astro.py)"),
    "night_fraction": ("0-1", "Posición de la hora como parte de la noche", "calculado (astro.py)"),
    "fc_rh_mean": ("%", "Humedad prevista, media de la noche", OM_ECMWF),
    "fc_rh_max": ("%", "Humedad prevista, máximo de la noche", OM_ECMWF),
    "fc_dew_spread_min": ("°C", "Temperatura prevista menos punto de rocío, mínimo de la noche", OM_ECMWF),
    "fc_temp_mean": ("°C", "Temperatura prevista, media de la noche", OM_ECMWF),
    "fc_temp_drop": ("°C", "Temperatura prevista al inicio de la noche menos la del final", OM_ECMWF),
    "fc_wind_mean": ("m/s", "Viento previsto a 10 m, media de la noche", OM_ECMWF),
    "fc_wind_max": ("m/s", "Viento previsto a 10 m, máximo de la noche", OM_ECMWF),
    "fc_wind_u": ("m/s", "Viento previsto, componente oeste-este, media de la noche", OM_ECMWF),
    "fc_wind_v": ("m/s", "Viento previsto, componente sur-norte, media de la noche", OM_ECMWF),
    "fc_cloud_mean": ("%", "Nubosidad prevista, media de la noche", OM_ECMWF),
    "fc_cloud_max": ("%", "Nubosidad prevista, máximo de la noche", OM_ECMWF),
    "fc_precip_sum": ("mm", "Lluvia prevista, total de la noche", OM_ECMWF),
    "fc_pressure_mean": ("hPa", "Presión prevista, media de la noche", OM_ECMWF),
    "pre_humidity_mean": ("%", "Humedad medida en las 2 h antes de la noche, media", NOT_SOURCE),
    "pre_humidity_max": ("%", "Humedad medida en las 2 h antes de la noche, máximo", NOT_SOURCE),
    "pre_wind_mean": ("m/s", "Viento medido en las 2 h antes de la noche, media", NOT_SOURCE),
    "pre_pressure_mean": ("hPa", "Presión medida en las 2 h antes de la noche, media", NOT_SOURCE),
    "prev_dome_closed_frac": ("0-1", "Anoche: parte de sus minutos con la cúpula cerrada", NOT_SOURCE),
    "prev_seeing_median": ("segundos de arco", "Anoche: mediana del seeing; vacío cuando no se pudo medir", R2D2_SOURCE),
    "doy_sin": ("", "Época del año: seno del día del año", "calendario"),
    "doy_cos": ("", "Época del año: coseno del día del año", "calendario"),
}

TEST_COLUMNS = {
    "night": ("fecha", "Noche a la que pertenece", "calendario"),
    "hour_utc": ("UTC", "Inicio de la hora", "calendario"),
    "closed": ("0/1", "Lo que pasó (la etiqueta, igual que en el fichero de entrenamiento)", NOT_SOURCE),
    "p_final": ("0-1", "RoqueModel definitivo (con la estación antes de la noche): probabilidad de cúpula cerrada", "RoqueModel"),
    "p_provisional": ("0-1", "RoqueModel provisional (solo previsión, el que se usa por la tarde)", "RoqueModel"),
    "forecast_alone": ("0/1", "Las reglas de cierre aplicadas a la previsión tal cual (1 = cerrar)", OM_ECMWF),
    "climatology": ("0-1", "Parte de las horas cerradas de ese mes en 2017-2023 (la referencia más sencilla)", "proyecto"),
}

NOT_SOURCE_EN = "NOT weather station (not.iac.es/weather/archive/met)"
OM_ECMWF_EN = "ECMWF IFS forecast archived by Open-Meteo (historical-forecast-api.open-meteo.com)"
OM_GFS_EN = "NOAA GFS forecast archived by Open-Meteo (historical-forecast-api.open-meteo.com)"
R2D2_SOURCE_EN = "ING R2D2 seeing monitor (astro.ing.iac.es/seeing/index.php)"

# The same tables in English, for README.en.md (tests check that they describe the same columns).
COLUMNS_EN = {
    "night": ("date", "Night it belongs to: the date of the evening it starts", "calendar"),
    "hour_utc": ("UTC", "Start of the hour (one row per hour with at least 30 min of astronomical night)", "calendar"),
    "split": ("", ("fit (2017-2023: the tested copy learnt from these years, and its settings were chosen with "
                  "2021, 2022 and 2023, leaving each one out in turn) or test (2024-2026, never seen); "
                  "the live model was retrained with all of them"), "project"),
    "closed": ("0/1", ("THE LABEL: 1 if the dome counts as closed for at least half of the hour "
                      f"(humidity >= {dome.HUMIDITY_LIMIT_PCT:.0f}%, wind >= {dome.WIND_LIMIT_MS} m/s or ice), "
                      "reconstructed minute by minute"), NOT_SOURCE_EN),
    "closed_frac": ("0-1", "Share of the hour's minutes with the dome closed (the label is closed_frac >= 0.5)", NOT_SOURCE_EN),
    "measured_minutes": ("min", "Minutes of the hour measured by the station (the label needs at least 45)", NOT_SOURCE_EN),
    "dark_minutes": ("min", "Minutes of astronomical night in the hour", "calculated (astro.py)"),
    "h_rh": ("%", "Forecast relative humidity at mid-hour", OM_ECMWF_EN),
    "h_dew_spread": ("°C", "Forecast temperature minus dew point at mid-hour", OM_ECMWF_EN),
    "h_temp": ("°C", "Forecast temperature at mid-hour", OM_ECMWF_EN),
    "h_wind": ("m/s", "Forecast 10 m wind at mid-hour", OM_ECMWF_EN),
    "h_wind_u": ("m/s", "Forecast 10 m wind, west-east component", OM_ECMWF_EN),
    "h_wind_v": ("m/s", "Forecast 10 m wind, south-north component", OM_ECMWF_EN),
    "h_cloud": ("%", "Forecast cloud cover at mid-hour", OM_ECMWF_EN),
    "h_precip": ("mm", "Forecast rain during the hour", OM_ECMWF_EN),
    "h_pressure": ("hPa", "Forecast surface pressure at mid-hour", OM_ECMWF_EN),
    "h_wind_750": ("m/s", "Forecast wind at 750 hPa (~2.5 km, the height of the summit); empty before March 2021", OM_GFS_EN),
    "hour_of_night": ("", "Position of the hour in the night (0 = the first)", "calculated (astro.py)"),
    "night_fraction": ("0-1", "Position of the hour as a share of the night", "calculated (astro.py)"),
    "fc_rh_mean": ("%", "Forecast humidity, night mean", OM_ECMWF_EN),
    "fc_rh_max": ("%", "Forecast humidity, night maximum", OM_ECMWF_EN),
    "fc_dew_spread_min": ("°C", "Forecast temperature minus dew point, night minimum", OM_ECMWF_EN),
    "fc_temp_mean": ("°C", "Forecast temperature, night mean", OM_ECMWF_EN),
    "fc_temp_drop": ("°C", "Forecast temperature at the start of the night minus that at the end", OM_ECMWF_EN),
    "fc_wind_mean": ("m/s", "Forecast 10 m wind, night mean", OM_ECMWF_EN),
    "fc_wind_max": ("m/s", "Forecast 10 m wind, night maximum", OM_ECMWF_EN),
    "fc_wind_u": ("m/s", "Forecast wind, west-east component, night mean", OM_ECMWF_EN),
    "fc_wind_v": ("m/s", "Forecast wind, south-north component, night mean", OM_ECMWF_EN),
    "fc_cloud_mean": ("%", "Forecast cloud cover, night mean", OM_ECMWF_EN),
    "fc_cloud_max": ("%", "Forecast cloud cover, night maximum", OM_ECMWF_EN),
    "fc_precip_sum": ("mm", "Forecast rain, night total", OM_ECMWF_EN),
    "fc_pressure_mean": ("hPa", "Forecast pressure, night mean", OM_ECMWF_EN),
    "pre_humidity_mean": ("%", "Humidity measured in the 2 h before the night, mean", NOT_SOURCE_EN),
    "pre_humidity_max": ("%", "Humidity measured in the 2 h before the night, maximum", NOT_SOURCE_EN),
    "pre_wind_mean": ("m/s", "Wind measured in the 2 h before the night, mean", NOT_SOURCE_EN),
    "pre_pressure_mean": ("hPa", "Pressure measured in the 2 h before the night, mean", NOT_SOURCE_EN),
    "prev_dome_closed_frac": ("0-1", "Last night: share of its minutes with the dome closed", NOT_SOURCE_EN),
    "prev_seeing_median": ("arcseconds", "Last night: median seeing; empty when it could not be measured", R2D2_SOURCE_EN),
    "doy_sin": ("", "Time of year: sine of the day of the year", "calendar"),
    "doy_cos": ("", "Time of year: cosine of the day of the year", "calendar"),
}

TEST_COLUMNS_EN = {
    "night": ("date", "Night it belongs to", "calendar"),
    "hour_utc": ("UTC", "Start of the hour", "calendar"),
    "closed": ("0/1", "What happened (the label, same as in the training file)", NOT_SOURCE_EN),
    "p_final": ("0-1", "Final RoqueModel (with the station before the night): probability of the dome being closed", "RoqueModel"),
    "p_provisional": ("0-1", "Provisional RoqueModel (forecast only, the one used in the evening)", "RoqueModel"),
    "forecast_alone": ("0/1", "The closing rules applied to the forecast as it is (1 = close)", OM_ECMWF_EN),
    "climatology": ("0-1", "Share of closed hours in that month in 2017-2023 (the simplest baseline)", "project"),
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


def column_table(columns: dict, header: str = "| Columna | Unidad | Significado | Fuente |") -> str:
    rows = [header, "|---|---|---|---|"]
    rows += [f"| `{name}` | {unit} | {meaning} | {source} |" for name, (unit, meaning, source) in columns.items()]
    return "\n".join(rows)


def readme(training: pd.DataFrame, test: pd.DataFrame) -> str:
    provisional = ", ".join(f"`{c}`" for c in hourly.CLOSURE_FORECAST_ONLY)
    scores = {c: wrong_share(test, c) for c in ("p_final", "p_provisional", "forecast_alone")}
    percent = {c: f"{share * 100:.1f}".replace(".", ",") + " %" for c, share in scores.items()}
    first, last = training["night"].min(), training["night"].max()
    return f"""# RoqueModel: los datos con los que aprendió

English version: `{README_EN}`.

Proyecto independiente, sin afiliación con GRANTECAN ni con ningún observatorio.
Código: https://github.com/saimonx/roque-model · Web: https://saimonx.github.io/roque-model/

## Ficheros

- `{TRAINING_CSV}`: {thousands(len(training))} horas de noche del {first} al {last}, {thousands(int(training["closed"].sum()))} de ellas
  con la cúpula cerrada. Son exactamente las filas con las que se entrenó el RoqueModel en directo. El modelo
  definitivo usa las {len(hourly.CLOSURE_FEATURES)} columnas de entrada de `h_rh` a `doy_cos`; el provisional (por la tarde,
  antes de la noche) solo usa {provisional}.
- `{TEST_CSV}`: {thousands(len(test))} horas de 2024-2026 que la copia probada (entrenada solo con 2017-2023) no
  había visto nunca. Contando «cerrada» cuando el valor es 0,5 o más, se equivoca en el {percent["p_final"]} de las horas
  (provisional {percent["p_provisional"]}; solo la previsión {percent["forecast_alone"]}).

Se puede comprobar, por ejemplo en Python:

```python
import pandas as pd
t = pd.read_csv("{TEST_CSV}")
print(((t.p_final >= 0.5).astype(int) != t.closed).mean())   # {scores["p_final"]:.3f}
```

## De dónde salen los datos

Todas las entradas se conocían antes de empezar la noche. No hay nada simulado.

- **Etiqueta y entradas de la estación:** la estación meteorológica del NOT, una medida por minuto
  (https://www.not.iac.es/weather/archive/met/index.php, «Raw Data»). La cúpula cuenta como cerrada cuando la
  humedad llega al {dome.HUMIDITY_LIMIT_PCT:.0f} % (reabre tras 20 minutos por debajo), cuando el viento
  llega a {spanish(dome.WIND_LIMIT_MS)} m/s (80 km/h) o cuando hay hielo ({dome.ICE_TEMP_C:.0f} °C o menos tras una humedad del
  {dome.HUMIDITY_LIMIT_PCT:.0f} % en las 24 h anteriores).
- **Entradas de la previsión:** lo que el modelo ECMWF IFS previó para cada hora, archivado por Open-Meteo
  (https://open-meteo.com, CC BY 4.0), en 28,7566 N, 17,8919 O, 2.270 m. El viento a 750 hPa viene del archivo
  NOAA GFS (mismo servicio). Cualquier día se puede volver a descargar, por ejemplo:
  https://historical-forecast-api.open-meteo.com/v1/forecast?latitude=28.7566&longitude=-17.8919&elevation=2270&models=ecmwf_ifs&timezone=UTC&wind_speed_unit=ms&hourly=relative_humidity_2m,temperature_2m&start_date=2024-01-01&end_date=2024-01-02
- **Seeing de anoche:** el monitor R2D2 del ING (https://astro.ing.iac.es/seeing/index.php).

El código que descarga las fuentes y construye estas tablas está en el repositorio (`backfill.py`,
`build_tables.py`, `features.py`, `hourly.py`; este paquete lo genera `export_data.py`).

## Columnas: {TRAINING_CSV}

{column_table(COLUMNS)}

## Columnas: {TEST_CSV}

{column_table(TEST_COLUMNS)}

## Créditos y licencias

Datos del Nordic Optical Telescope (NOT), del Isaac Newton Group (ING) y de Open-Meteo (CC BY 4.0; previsiones
de ECMWF y NOAA). Los valores por hora de este paquete se derivan de sus datos públicos; se ruega citarlos.
"""


def readme_en(training: pd.DataFrame, test: pd.DataFrame) -> str:
    """README.md in English, with the same figures."""
    provisional = ", ".join(f"`{c}`" for c in hourly.CLOSURE_FORECAST_ONLY)
    scores = {c: wrong_share(test, c) for c in ("p_final", "p_provisional", "forecast_alone")}
    percent = {c: f"{share * 100:.1f}%" for c, share in scores.items()}
    first, last = training["night"].min(), training["night"].max()
    header = "| Column | Unit | Meaning | Source |"
    return f"""# RoqueModel: the data it learnt from

Versión en español: `{README}`.

Independent project, not affiliated with GRANTECAN or any observatory.
Code: https://github.com/saimonx/roque-model · Website: https://saimonx.github.io/roque-model/?lang=en

## Files

- `{TRAINING_CSV}`: {len(training):,} night hours from {first} to {last}, {int(training["closed"].sum()):,} of them
  with the dome closed. They are exactly the rows the live RoqueModel was trained on. The final model
  uses the {len(hourly.CLOSURE_FEATURES)} input columns from `h_rh` to `doy_cos`; the provisional one (in the evening,
  before the night) only uses {provisional}.
- `{TEST_CSV}`: {len(test):,} hours of 2024-2026 that the tested copy (trained only on 2017-2023) had
  never seen. Counting "closed" when the value is 0.5 or more, it is wrong in {percent["p_final"]} of hours
  (provisional {percent["p_provisional"]}; forecast alone {percent["forecast_alone"]}).

It can be checked, for example in Python:

```python
import pandas as pd
t = pd.read_csv("{TEST_CSV}")
print(((t.p_final >= 0.5).astype(int) != t.closed).mean())   # {scores["p_final"]:.3f}
```

## Where the data come from

All the inputs were known before the night started. Nothing is simulated.

- **Label and station inputs:** the NOT weather station, one measurement per minute
  (https://www.not.iac.es/weather/archive/met/index.php, "Raw Data"). The dome counts as closed when
  humidity reaches {dome.HUMIDITY_LIMIT_PCT:.0f}% (reopening after 20 minutes below), when the wind
  reaches {dome.WIND_LIMIT_MS} m/s (80 km/h) or when there is ice ({dome.ICE_TEMP_C:.0f} °C or below after humidity of
  {dome.HUMIDITY_LIMIT_PCT:.0f}% in the previous 24 h).
- **Forecast inputs:** what the ECMWF IFS model forecast for each hour, archived by Open-Meteo
  (https://open-meteo.com, CC BY 4.0), at 28.7566 N, 17.8919 W, 2,270 m. The 750 hPa wind comes from the
  NOAA GFS archive (same service). Any day can be downloaded again, for example:
  https://historical-forecast-api.open-meteo.com/v1/forecast?latitude=28.7566&longitude=-17.8919&elevation=2270&models=ecmwf_ifs&timezone=UTC&wind_speed_unit=ms&hourly=relative_humidity_2m,temperature_2m&start_date=2024-01-01&end_date=2024-01-02
- **Last night's seeing:** the ING R2D2 monitor (https://astro.ing.iac.es/seeing/index.php).

The code that downloads the sources and builds these tables is in the repository (`backfill.py`,
`build_tables.py`, `features.py`, `hourly.py`; this package is written by `export_data.py`).

## Columns: {TRAINING_CSV}

{column_table(COLUMNS_EN, header)}

## Columns: {TEST_CSV}

{column_table(TEST_COLUMNS_EN, header)}

## Credits and licences

Data from the Nordic Optical Telescope (NOT), the Isaac Newton Group (ING) and Open-Meteo (CC BY 4.0; ECMWF and
NOAA forecasts). The hourly values in this package are derived from their public data; please cite them.
"""


def export() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    training, test = training_table(), test_table()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(TRAINING_CSV, training.to_csv(index=False, float_format="%.6g"))
        z.writestr(TEST_CSV, test.to_csv(index=False, float_format="%.6g"))
        z.writestr(README, readme(training, test))
        z.writestr(README_EN, readme_en(training, test))
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
