"""Open-Meteo: weather FORECASTS for the observatory (what was predicted, not what happened).

To train a forecast model honestly we must feed it what a forecast said at the
time, never the weather that was later measured (that would be "cheating": the
model would learn from information nobody had in the afternoon). Open-Meteo
keeps two free archives of past forecasts (https://open-meteo.com, CC BY 4.0):

- **Historical Forecast API** (`historical-forecast-api.open-meteo.com`): the first
  hours of every model run stitched into one continuous series. For ECMWF IFS
  HRES (9 km) it goes back to 2017. Lead time is short (0 to ~6 h), so it is a
  slightly OPTIMISTIC stand-in for "the forecast available in the afternoon".
- **Previous Runs API** (`previous-runs-api.open-meteo.com`): variables with the
  suffix `_previous_day1` hold the value forecast 24 h earlier. That is a
  slightly PESSIMISTIC stand-in (the afternoon forecast is 6-18 h old, not 24 h).
  For ECMWF IFS HRES it only exists since late 2025.

We train on the long historical series and check the model again with the
day-1 forecasts: the real skill lies between the two numbers.

The model is ECMWF IFS HRES (`ecmwf_ifs`), the best global model, with a grid
point 4 km from the telescope. `elevation=2270` asks Open-Meteo to correct the
temperature from the model's smooth terrain to the real summit height.

**Upper-level wind.** The ECMWF archive above has no pressure levels, so the wind
aloft comes from NOAA's GFS model (`gfs_global`), archived only since March 2021
(checked 28 Oct 2026): at 750 hPa (~2,500 m, the summit height: RoqueModel's wind
input, because the ECMWF 10 m wind of the lower, sheltered grid point is too weak)
and at 200 hPa (~12 km, the jet stream, whose shear blurs the stars: a seeing
input). Older nights simply have no value; the tree models handle missing inputs
natively. The day-1 archive has no pressure
levels either, so the 24-hour-old check also uses this short-lead archive.
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from roque_forecast import config
from roque_forecast.polite_http import PoliteSession

HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MODEL = "ecmwf_ifs"

# Only variables that exist in BOTH archives (the day-1 archive has no gusts and
# no low/mid/high cloud split), so the same model can be fed by either source.
VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "cloud_cover",
    "precipitation",
    "surface_pressure",
]

UPPER_MODEL = "gfs_global"
# 200 hPa (~12 km): jet stream, for the seeing. 750 hPa (~2.5 km): the free-air wind at
# summit height, for the hourly wind forecast (the 10 m wind of the coarse model grid is
# far too calm at the summit: mean 1.3 m/s).
UPPER_VARIABLES = ["wind_speed_200hPa", "wind_speed_750hPa"]
UPPER_FIRST_DAY = date(2021, 3, 1)

BASE_PARAMS = {
    "latitude": config.SITE_LAT,
    "longitude": config.SITE_LON,
    "elevation": config.SITE_ALT_M,
    "models": MODEL,
    "timezone": "UTC",
    "wind_speed_unit": "ms",  # same unit as the NOT anemometer
}


def download_year(session: PoliteSession, kind: str, start: date, end: date, dest: Path) -> Path:
    """Save one block of archived forecasts as JSON. `kind` is "historical" or "previous_day1";
    `kind` "upper" is the GFS jet-stream wind (see the module notes)."""
    model = MODEL
    if kind == "historical":
        url, hourly = HISTORICAL_URL, VARIABLES
    elif kind == "previous_day1":
        url, hourly = PREVIOUS_RUNS_URL, [f"{v}_previous_day1" for v in VARIABLES]
    elif kind == "upper":
        url, hourly, model = HISTORICAL_URL, UPPER_VARIABLES, UPPER_MODEL
    else:
        raise ValueError(kind)
    params = BASE_PARAMS | {
        "models": model,
        "hourly": ",".join(hourly),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    response = session.get(url, params=params)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(response.text, encoding="utf-8")
    return dest


def download_current(session: PoliteSession, forecast_days: int = 2, past_days: int = 0) -> dict:
    """Today's forecast (for "tonight"), same model and variables as the archive.

    past_days adds the hours already gone (as forecast at the time), to compare the
    forecast with what the station measured."""
    params = BASE_PARAMS | {"hourly": ",".join(VARIABLES), "forecast_days": forecast_days, "past_days": past_days}
    return session.get(FORECAST_URL, params=params).json()


def download_current_upper(session: PoliteSession, forecast_days: int = 2, past_days: int = 0) -> dict:
    """Today's GFS jet-stream wind, same model and level as the upper archive."""
    params = BASE_PARAMS | {"models": UPPER_MODEL, "hourly": ",".join(UPPER_VARIABLES),
                            "forecast_days": forecast_days, "past_days": past_days}
    return session.get(FORECAST_URL, params=params).json()


def parse_upper(payload: dict | Path) -> pd.DataFrame:
    """Hourly table: time_utc plus the upper-level wind (empty hours dropped)."""
    if isinstance(payload, Path):
        payload = json.loads(payload.read_text(encoding="utf-8"))
    hourly = pd.DataFrame(payload["hourly"])
    hourly["time_utc"] = pd.to_datetime(hourly.pop("time"), utc=True)
    columns = [c for c in UPPER_VARIABLES if c in hourly]
    hourly = hourly.dropna(subset=columns, how="all")
    return hourly[["time_utc", *columns]].reset_index(drop=True)


def parse(payload: dict | Path) -> pd.DataFrame:
    """Hourly table: time_utc plus one column per variable (suffixes removed).

    Hours the archive does not cover come back as empty values; they are dropped.
    """
    if isinstance(payload, Path):
        payload = json.loads(payload.read_text(encoding="utf-8"))
    hourly = pd.DataFrame(payload["hourly"])
    hourly.columns = [c.removesuffix("_previous_day1") for c in hourly.columns]
    hourly["time_utc"] = pd.to_datetime(hourly.pop("time"), utc=True)
    hourly = hourly.dropna(subset=VARIABLES, how="all")
    return hourly[["time_utc", *VARIABLES]].reset_index(drop=True)
