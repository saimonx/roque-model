"""Turn the raw downloads into clean tables (Parquet files in data/processed/).

Usage:
    .venv/bin/python -m roque_forecast.build_tables

Outputs:
    not_minutes.parquet   one row per minute of NOT weather (1997 -> today), with
                          night label, "is astronomical night" and "dome closed" flags
    r2d2_points.parquet   every R2D2 seeing measurement
    ing_nights.parquet    WHT accounting per night (hours lost to weather, ...)
    nights.parquet        THE modelling table: one row per night joining all of the above

Why Parquet? It is a compressed, column-based format: much smaller and faster
than CSV, and it keeps data types (dates stay dates). It is also the standard
format of data lakes and Spark, which GRANTECAN plans to use.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from roque_forecast import astro, config, dome
from roque_forecast.sources import ing_nights, not_mast, r2d2

log = logging.getLogger("build_tables")

# Physically plausible ranges at 2,400 m on La Palma. Values outside are sensor
# errors and are set to "missing" (NaN) rather than deleted, so the row stays.
VALID_RANGES = {
    # 0 % is REAL: ~6 % of all minutes read 0, and they always follow readings of
    # 0.1-0.6 % (checked on 2024). Above the sea of clouds the air is extremely dry
    # and the sensor bottoms out at 0. Only values above 100 % are errors.
    "humidity_pct": (0.0, 100.0),
    "pressure_hpa": (740.0, 800.0),
    "temp_c": (-15.0, 35.0),
    "wind_dir_deg": (0.0, 360.0),
    "wind_speed_ms": (0.0, 70.0),
}

# A night counts for the closure statistics only if most of it has data.
MIN_NIGHT_COVERAGE = 0.8
# A night needs this many R2D2 points to get a seeing value (~25 min of data).
MIN_SEEING_POINTS = 40


def build_not_minutes() -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "not").glob("*/not_*.tsv.gz"))
    log.info("NOT: reading %d monthly files", len(files))
    df = pd.concat([not_mast.parse(f) for f in files], ignore_index=True)

    # Timestamps jitter by a few seconds (00:00:59, 00:02:01...). Rounding to the
    # nearest minute gives a regular grid; duplicates (month edges) are dropped.
    df["time_utc"] = df["time_utc"].dt.round("min")
    df = df.drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)

    for column, (low, high) in VALID_RANGES.items():
        bad = ~df[column].between(low, high)
        if bad.any():
            log.info("NOT: %s -> %d values outside [%s, %s] set to NaN", column, bad.sum(), low, high)
        df.loc[bad, column] = np.nan

    df["night"] = astro.night_label(df["time_utc"])
    df["is_night"] = astro.is_astronomical_night(df["time_utc"])
    df["dome_closed"] = dome.closed_by_humidity(df)
    return df


def circular_mean_deg(degrees: pd.Series) -> float:
    """Mean wind direction. A plain mean of 350 and 10 gives 180 (wrong); this gives 0."""
    rad = np.radians(degrees.dropna())
    if rad.empty:
        return np.nan
    return float(np.degrees(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360)


def nightly_weather(minutes: pd.DataFrame) -> pd.DataFrame:
    """Summarise the NOT minutes of each astronomical night into one row."""
    dark = minutes[minutes["is_night"]]
    grouped = dark.groupby("night")
    nights = pd.DataFrame({
        "n_samples": grouped.size(),
        # Old years are sampled every few minutes, recent ones every minute. To
        # measure completeness fairly we count 10-minute blocks that have data.
        "blocks_with_data": dark["time_utc"].dt.floor("10min").groupby(dark["night"]).nunique(),
        "humidity_mean": grouped["humidity_pct"].mean(),
        "humidity_max": grouped["humidity_pct"].max(),
        "temp_mean": grouped["temp_c"].mean(),
        # Temperature drop during the night (start minus end): strong cooling
        # often means stable air (good seeing) or approaching condensation.
        "temp_drop": grouped["temp_c"].first() - grouped["temp_c"].last(),
        "pressure_mean": grouped["pressure_hpa"].mean(),
        "wind_mean": grouped["wind_speed_ms"].mean(),
        "wind_max": grouped["wind_speed_ms"].max(),
        "wind_std": grouped["wind_speed_ms"].std(),
        "wind_dir_mean": grouped["wind_dir_deg"].agg(circular_mean_deg),
        # Share of the night's samples with the dome closed. Using the share (not
        # "count / 60") works whatever the sampling interval is.
        "dome_closed_frac": grouped["dome_closed"].mean(),
    })

    # Length of the astronomical night from the Sun itself (not from the data),
    # so we can tell how complete each night's data are.
    all_minutes = pd.date_range(
        minutes["time_utc"].min().floor("D"), minutes["time_utc"].max().ceil("D"),
        freq="min", tz="UTC",
    )
    grid = pd.DataFrame({"time_utc": all_minutes})
    grid = grid[astro.is_astronomical_night(grid["time_utc"])]
    night_length = grid.groupby(astro.night_label(grid["time_utc"])).size() / 60
    nights["night_length_h"] = night_length

    nights["coverage"] = (nights["blocks_with_data"] / (nights["night_length_h"] * 6)).clip(upper=1)
    nights["dome_closed_h"] = nights["dome_closed_frac"] * nights["night_length_h"]
    low = nights["coverage"] < MIN_NIGHT_COVERAGE
    nights.loc[low, ["dome_closed_h", "dome_closed_frac"]] = np.nan
    nights.index.name = "night"
    return nights


def build_r2d2() -> tuple[pd.DataFrame, pd.DataFrame]:
    files = sorted((config.RAW_DIR / "r2d2").glob("r2d2_*.html"))
    log.info("R2D2: reading %d monthly files", len(files))
    points = pd.concat([r2d2.parse(f) for f in files], ignore_index=True)
    points = points.drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)
    # Seeing below 0.1" or above 10" is not physical at this site.
    points = points[points["seeing_arcsec"].between(0.1, 10)]
    points["night"] = astro.night_label(points["time_utc"])

    grouped = points.groupby("night")["seeing_arcsec"]
    nightly = pd.DataFrame({
        "seeing_n": grouped.size(),
        "seeing_median": grouped.median(),
        "seeing_p25": grouped.quantile(0.25),
        "seeing_p75": grouped.quantile(0.75),
    })
    nightly.loc[nightly["seeing_n"] < MIN_SEEING_POINTS, ["seeing_median", "seeing_p25", "seeing_p75"]] = np.nan
    nightly.index.name = "night"
    return points, nightly


def build_ing() -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "ing_nights").glob("*/*.html.gz"))
    log.info("ING: reading %d night pages", len(files))
    rows = [ing_nights.parse(f) | {"file_night": f.name.removesuffix(".html.gz")} for f in files]
    df = pd.DataFrame(rows)
    df["night"] = pd.to_datetime(df["night"].fillna(df["file_night"])).dt.date
    df = df.drop(columns="file_night").set_index("night").sort_index()
    # Pages where every number is zero (including the night length) have no accounting.
    df["has_accounting"] = df["night_h"].fillna(0) > 0
    # Hours lost can exceed the night (counted over a longer window): cap them.
    df["weather_lost_frac"] = (df["weather_lost_h"] / df["night_h"]).clip(upper=1)
    df.loc[~df["has_accounting"], "weather_lost_frac"] = np.nan
    return df


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "build_tables.log"), logging.StreamHandler(sys.stdout)],
    )
    out: Path = config.PROCESSED_DIR

    minutes = build_not_minutes()
    minutes.to_parquet(out / "not_minutes.parquet", index=False)
    log.info("not_minutes: %d rows, %s -> %s", len(minutes), minutes.time_utc.min(), minutes.time_utc.max())
    weather = nightly_weather(minutes)

    points, seeing = build_r2d2()
    points.to_parquet(out / "r2d2_points.parquet", index=False)
    log.info("r2d2_points: %d rows", len(points))

    ing = build_ing()
    ing.to_parquet(out / "ing_nights.parquet")
    log.info("ing_nights: %d nights (%d with accounting)", len(ing), ing["has_accounting"].sum())

    nights = weather.join(seeing, how="outer").join(ing.add_prefix("wht_"), how="outer")
    nights.index = pd.to_datetime(nights.index)
    nights.index.name = "night"
    nights["month"] = nights.index.month
    nights["year"] = nights.index.year
    nights.to_parquet(out / "nights.parquet")
    log.info("nights: %d rows, %s -> %s", len(nights), nights.index.min().date(), nights.index.max().date())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
