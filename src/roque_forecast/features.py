"""Build the modelling table: one row per night with what was KNOWN at sunset
(inputs) and what HAPPENED during the night (labels).

The golden rule of forecasting: an input is allowed only if it was available
before the night started. So the inputs are:

1. **The weather forecast for the night** (Open-Meteo archive, see
   sources/open_meteo.py), summarised over the hours of astronomical night.
2. **The weather measured at the NOT in the 2 hours before the night**: at
   sunset an operator can look at the station, so this is fair. It also lets
   the model correct the forecast (a model grid point 4 km away, on smoothed
   terrain, does not see the summit exactly: it is usually wetter and calmer).
3. **Last night's outcome** (closure, seeing): "persistence". Weather on La
   Palma comes in spells of several days, so yesterday says a lot about today.
4. **The time of year**, as sine/cosine of the day of the year, so that 31 Dec
   and 1 Jan are close (a plain day number would put them 364 days apart).

The labels come from data/processed/nights.parquet (build_tables.py).

Usage (writes data/processed/model_table.parquet and model_table_day1.parquet):
    .venv/bin/python -m roque_forecast.features
"""

import logging
import sys

import numpy as np
import pandas as pd

from roque_forecast import astro, config
from roque_forecast.sources import open_meteo

log = logging.getLogger("features")

PRE_NIGHT_WINDOW = pd.Timedelta(hours=2)
# First night with archived forecasts (the ECMWF IFS HRES archive starts on 1 Jan 2017).
FIRST_NIGHT = pd.Timestamp("2017-01-01")

# The inputs the models use, in a fixed order. Missing values are allowed (the
# gradient-boosting models handle them natively).
FORECAST_FEATURES = [
    "fc_rh_mean", "fc_rh_max", "fc_dew_spread_min", "fc_temp_mean", "fc_temp_drop",
    "fc_wind_mean", "fc_wind_max", "fc_wind_u", "fc_wind_v", "fc_cloud_mean",
    "fc_cloud_max", "fc_precip_sum", "fc_pressure_mean",
]
OBSERVED_FEATURES = ["pre_humidity_mean", "pre_humidity_max", "pre_wind_mean", "pre_pressure_mean"]
PERSISTENCE_FEATURES = ["prev_dome_closed_frac", "prev_seeing_median"]
CALENDAR_FEATURES = ["doy_sin", "doy_cos"]
FEATURES = FORECAST_FEATURES + OBSERVED_FEATURES + PERSISTENCE_FEATURES + CALENDAR_FEATURES


def load_forecasts(kind: str) -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "open_meteo" / kind).glob("*.json"))
    if not files:
        raise SystemExit(f"no forecast files for {kind}: run `backfill forecasts` first")
    hourly = pd.concat([open_meteo.parse(f) for f in files], ignore_index=True)
    return hourly.drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)


def nightly_forecast(hourly: pd.DataFrame) -> pd.DataFrame:
    """Summarise the forecast hours that fall in each astronomical night."""
    hourly = hourly[astro.is_astronomical_night(hourly["time_utc"])].copy()
    hourly["night"] = pd.to_datetime(astro.night_label(hourly["time_utc"]))
    # Wind direction cannot be averaged as a number (350 and 10 degrees average to 180).
    # Splitting the wind into east-west (u) and north-south (v) parts solves it.
    direction = np.radians(hourly["wind_direction_10m"])
    hourly["u"] = -hourly["wind_speed_10m"] * np.sin(direction)
    hourly["v"] = -hourly["wind_speed_10m"] * np.cos(direction)
    # Dew-point spread: how many degrees the air must cool before water condenses.
    # Close to 0 means fog, frost or condensation on the mirror.
    hourly["dew_spread"] = hourly["temperature_2m"] - hourly["dew_point_2m"]

    g = hourly.groupby("night")
    nights = pd.DataFrame({
        "fc_hours": g.size(),
        "fc_rh_mean": g["relative_humidity_2m"].mean(),
        "fc_rh_max": g["relative_humidity_2m"].max(),
        "fc_dew_spread_min": g["dew_spread"].min(),
        "fc_temp_mean": g["temperature_2m"].mean(),
        "fc_temp_drop": g["temperature_2m"].first() - g["temperature_2m"].last(),
        "fc_wind_mean": g["wind_speed_10m"].mean(),
        "fc_wind_max": g["wind_speed_10m"].max(),
        "fc_wind_u": g["u"].mean(),
        "fc_wind_v": g["v"].mean(),
        "fc_cloud_mean": g["cloud_cover"].mean(),
        "fc_cloud_max": g["cloud_cover"].max(),
        "fc_precip_sum": g["precipitation"].sum(min_count=1),
        "fc_pressure_mean": g["surface_pressure"].mean(),
    })
    # A night is usable only if the forecast covers most of it (the day-1 archive has
    # gaps). The shortest astronomical night here lasts ~7 hours.
    return nights[nights["fc_hours"] >= 5]


def night_starts(first: pd.Timestamp, last: pd.Timestamp) -> pd.Series:
    """Start (UTC) of each astronomical night, from the Sun, at 1-minute resolution."""
    grid = pd.DataFrame({"time_utc": pd.date_range(first, last, freq="min", tz="UTC")})
    grid = grid[astro.is_astronomical_night(grid["time_utc"])]
    starts = grid.groupby(pd.to_datetime(astro.night_label(grid["time_utc"])))["time_utc"].min()
    starts.index.name = "night"
    return starts


def pre_night_observations(minutes: pd.DataFrame, starts: pd.Series) -> pd.DataFrame:
    """NOT weather in the 2 hours before each night starts (known at decision time)."""
    table = starts.rename("night_start").reset_index().sort_values("night_start")
    obs = minutes[["time_utc", "humidity_pct", "wind_speed_ms", "pressure_hpa"]].sort_values("time_utc")
    # merge_asof gives every minute the NEXT night start; keep minutes within 2 h of it.
    # allow_exact_matches=False: the first minute of the night is not "before" the night.
    obs = pd.merge_asof(obs, table, left_on="time_utc", right_on="night_start", direction="forward",
                        allow_exact_matches=False)
    obs = obs[(obs["night_start"] - obs["time_utc"]) <= PRE_NIGHT_WINDOW]
    g = obs.groupby("night")
    return pd.DataFrame({
        "pre_humidity_mean": g["humidity_pct"].mean(),
        "pre_humidity_max": g["humidity_pct"].max(),
        "pre_wind_mean": g["wind_speed_ms"].mean(),
        "pre_pressure_mean": g["pressure_hpa"].mean(),
    })


def add_labels_and_persistence(table: pd.DataFrame, nights: pd.DataFrame) -> pd.DataFrame:
    """Join what happened that night (labels) and what happened the night before."""
    labels = nights[[
        "dome_closed_frac", "dome_closed_h", "night_length_h", "seeing_median",
        "wht_weather_lost_h", "wht_night_h", "wht_has_accounting",
    ]].copy()
    # Hours lost can exceed the night in the ING accounting: cap them at the night length.
    labels["wht_weather_lost_h"] = labels["wht_weather_lost_h"].clip(upper=labels["wht_night_h"])
    labels.loc[labels["wht_has_accounting"] != True, "wht_weather_lost_h"] = np.nan
    # "Closed" = at least 1 hour of the night lost to the humidity rule.
    labels["closed"] = (labels["dome_closed_h"] >= 1).astype(float)
    labels.loc[labels["dome_closed_h"].isna(), "closed"] = np.nan

    # Shift by one CALENDAR day (not one row): if yesterday is missing, the value is missing.
    previous = nights[["dome_closed_frac", "seeing_median", "wht_weather_lost_h"]].copy()
    previous.index = previous.index + pd.Timedelta(days=1)
    previous = previous.add_prefix("prev_")

    out = table.join(labels, how="left").join(previous, how="left")
    doy = 2 * np.pi * out.index.day_of_year / 365.25
    out["doy_sin"], out["doy_cos"] = np.sin(doy), np.cos(doy)
    out["month"], out["year"] = out.index.month, out.index.year
    return out


def build(kind: str, nights: pd.DataFrame, observed: pd.DataFrame) -> pd.DataFrame:
    forecast = nightly_forecast(load_forecasts(kind))
    table = forecast.join(observed, how="left")
    table = add_labels_and_persistence(table, nights)
    table.index.name = "night"
    return table[table.index >= FIRST_NIGHT]


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "features.log"), logging.StreamHandler(sys.stdout)],
    )
    nights = pd.read_parquet(config.PROCESSED_DIR / "nights.parquet")
    minutes = pd.read_parquet(
        config.PROCESSED_DIR / "not_minutes.parquet",
        columns=["time_utc", "humidity_pct", "wind_speed_ms", "pressure_hpa"],
        filters=[("time_utc", ">=", FIRST_NIGHT.tz_localize("UTC") - pd.Timedelta(days=2))],
    )
    starts = night_starts(minutes["time_utc"].min().floor("D"), minutes["time_utc"].max().ceil("D"))
    observed = pre_night_observations(minutes, starts)

    for kind, name in [("historical", "model_table"), ("previous_day1", "model_table_day1")]:
        table = build(kind, nights, observed)
        table.to_parquet(config.PROCESSED_DIR / f"{name}.parquet")
        log.info("%s: %d nights, %s -> %s", name, len(table), table.index.min().date(), table.index.max().date())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
