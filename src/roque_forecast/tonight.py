"""The forecast for TONIGHT: the two models applied to today's live data.

It downloads, every run:
1. today's ECMWF and GFS forecasts for the observatory (Open-Meteo, the same
   models and variables as the archives the models were trained on);
2. the NOT weather station for the last ~36 hours (for the "2 hours before the
   night" inputs and last night's closure);
3. the R2D2 seeing monitor for the last two nights (last night's seeing).

and applies the two forecasts of the project:
- **dome closed, hour by hour** (hourly.py): for each night hour, the probability
  that the dome is closed for humidity, wind or ice. The night's expected closed
  hours are the sum of the hourly probabilities;
- **seeing of the night** (train.py): one number for the whole night.

Two modes, so the forecast never uses information it could not have:
- **provisional** (before the night starts): the station window "2 hours before
  the night" does not exist yet, so the forecast-only twin models are used;
- **final** (from the start of astronomical night): the full models.

Outputs:
- site/data/tonight.json: everything the web page shows;
- data/forecasts/issued.jsonl: one line per run, the record of what was forecast;
- data/forecasts/outcomes.jsonl: what really happened last night, so the forecasts
  can be checked against reality as the nights go by (site_data.py).

Usage:
    .venv/bin/python -m roque_forecast.tonight              # also updates FIWARE if it is running
    .venv/bin/python -m roque_forecast.tonight --no-fiware
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd

from roque_forecast import astro, config, features, hourly, train
from roque_forecast.build_tables import MIN_NIGHT_COVERAGE, MIN_SEEING_POINTS, VALID_RANGES
from roque_forecast.polite_http import PoliteSession
from roque_forecast.sources import not_mast, open_meteo, r2d2

log = logging.getLogger("tonight")

LOCAL_TZ = ZoneInfo("Atlantic/Canary")  # La Palma local time (WET/WEST)
SITE_DATA_DIR = config.PROJECT_DIR / "site" / "data"
FORECASTS_DIR = config.DATA_DIR / "forecasts"
MODELS_DIR = config.DATA_DIR / "models"

# Levels shown on the page. For one hour: the probability that the dome is closed.
# For the night: the share of the night expected closed.
HOUR_LEVELS = [(0.2, "low"), (0.5, "medium"), (1.01, "high")]
NIGHT_LEVELS = [(0.1, "low"), (0.4, "medium"), (1.01, "high")]
# Written with every issued forecast, so the track record only scores forecasts made by
# the current models (hourly closure + nightly seeing), not by earlier versions.
MODEL_VERSION = "hourly-closure-v2"
# Seeing classes (arcsec). The Roque median is ~0.75-0.8".
SEEING_CLASSES = [(0.6, "excellent"), (0.9, "good"), (1.2, "average"), (99, "poor")]


# --------------------------------------------------------------------------
# Which night is "tonight"?
# --------------------------------------------------------------------------
def tonight_window(now: pd.Timestamp) -> dict:
    """Start and end (UTC) of the astronomical night that is running now or comes next.

    Nights are labelled with the date of the evening they start (like the ING and
    the training table), so after midnight "tonight" is still the previous date.
    """
    grid = pd.DataFrame({"time_utc": pd.date_range((now - pd.Timedelta(days=1)).floor("D"),
                                                   (now + pd.Timedelta(days=2)).ceil("D"), freq="min")})
    grid = grid[astro.is_astronomical_night(grid["time_utc"])]
    grid["night"] = pd.to_datetime(astro.night_label(grid["time_utc"]))
    nights = grid.groupby("night")["time_utc"].agg(["min", "max"])
    nights = nights[nights["max"] > now]  # the first night that has not ended yet
    label = nights.index[0]
    start, end = nights.iloc[0]["min"], nights.iloc[0]["max"] + pd.Timedelta(minutes=1)
    return {"night": label, "start": start, "end": end, "length_h": (end - start).total_seconds() / 3600}


# --------------------------------------------------------------------------
# Live data
# --------------------------------------------------------------------------
def download_live(session: PoliteSession, now: pd.Timestamp, folder: Path) -> dict:
    """Fetch the three live sources and keep the raw files (as for every other source)."""
    folder.mkdir(parents=True, exist_ok=True)
    forecast = open_meteo.download_current(session, forecast_days=3)
    (folder / "open_meteo.json").write_text(json.dumps(forecast), encoding="utf-8")
    upper = open_meteo.download_current_upper(session, forecast_days=3)
    (folder / "open_meteo_upper.json").write_text(json.dumps(upper), encoding="utf-8")

    start = (now - pd.Timedelta(hours=36)).to_pydatetime().replace(tzinfo=None)
    not_file = not_mast.download_range(session, start, now.to_pydatetime().replace(tzinfo=None),
                                       folder / "not.tsv.gz")
    today = now.date()
    # date2 is exclusive: today + 1 includes this morning's data.
    r2d2_file = r2d2.download_range(session, today - timedelta(days=2), today + timedelta(days=1),
                                    folder / "r2d2.html")
    return {"forecast": open_meteo.parse(forecast), "upper": open_meteo.parse_upper(upper),
            "minutes": clean_minutes(not_mast.parse(not_file)),
            "seeing": r2d2.parse(r2d2_file)}


def clean_minutes(df: pd.DataFrame) -> pd.DataFrame:
    """Same cleaning as build_tables.build_not_minutes (one-minute grid, impossible values removed)."""
    df["time_utc"] = df["time_utc"].dt.round("min")
    df = df.drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)
    for column, (low, high) in VALID_RANGES.items():
        df.loc[~df[column].between(low, high), column] = np.nan
    return df


def last_night(minutes: pd.DataFrame, seeing: pd.DataFrame, night: pd.Timestamp) -> dict:
    """What happened on `night` (the night before tonight): closed hours (humidity, wind or
    ice, the same label as in training) and median seeing.

    These are the "last night" inputs for tonight, and the outcome used to check the
    forecast issued for that night.
    """
    window = tonight_window(night.tz_localize("UTC") + pd.Timedelta(hours=12))  # that night's start/end
    out = {"night": str(night.date()), "dome_closed_frac": None, "dome_closed_h": None, "seeing_median": None}
    labelled = hourly.label_minutes(minutes.copy())
    dark = labelled[(labelled["time_utc"] >= window["start"]) & (labelled["time_utc"] < window["end"])]
    if not dark.empty:
        coverage = dark["time_utc"].dt.floor("10min").nunique() / (window["length_h"] * 6)
        if coverage >= MIN_NIGHT_COVERAGE:
            out["dome_closed_frac"] = round(float(dark["closed"].mean()), 4)
            out["dome_closed_h"] = round(float(dark["closed"].mean()) * window["length_h"], 2)
    points = seeing[(seeing["time_utc"] >= window["start"]) & (seeing["time_utc"] < window["end"])]
    if len(points) >= MIN_SEEING_POINTS:
        out["seeing_median"] = round(float(points["seeing_arcsec"].median()), 3)
    return out


def latest_gtc_panel(max_age_h: float = 1.0) -> dict | None:
    """Most recent snapshot of the GTC live panel saved by the 15-minute collector."""
    files = sorted((config.RAW_DIR / "live").glob("*/*.jsonl"))
    if not files:
        return None
    lines = files[-1].read_text(encoding="utf-8").strip().splitlines()
    for line in reversed(lines):
        record = json.loads(line)
        if "gtc_panel" in record:
            collected = pd.Timestamp(record["collected_utc"])
            if pd.Timestamp.now(tz="UTC") - collected > pd.Timedelta(hours=max_age_h):
                return None
            panel = record["gtc_panel"]
            return {"collected_utc": record["collected_utc"], "station_time_utc": panel["station_time_utc"],
                    "rows": [{k: r[k] for k in ("section", "name", "value", "unit", "age", "status")}
                             for r in panel["rows"]]}
    return None


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------
def build_inputs(live: dict, window: dict, previous: dict, final: bool) -> pd.DataFrame:
    """One row with the night's inputs, built with the same functions as in training."""
    label = window["night"]
    forecast = features.nightly_forecast(live["forecast"])
    if label not in forecast.index:
        raise RuntimeError(f"the live forecast does not cover the night of {label.date()}")
    row = forecast.loc[[label]].copy()
    row = row.join(features.nightly_upper(live["upper"]), how="left") if len(live.get("upper", [])) else row
    for column in features.UPPER_FEATURES:
        if column not in row:
            row[column] = np.nan
    if final:
        starts = pd.Series([window["start"]], index=pd.DatetimeIndex([label], name="night"))
        row = row.join(features.pre_night_observations(live["minutes"], starts), how="left")
    for column in features.OBSERVED_FEATURES:
        if column not in row:
            row[column] = np.nan
    row["prev_dome_closed_frac"] = previous["dome_closed_frac"]
    row["prev_seeing_median"] = previous["seeing_median"]
    doy = 2 * np.pi * row.index.day_of_year / 365.25
    row["doy_sin"], row["doy_cos"] = np.sin(doy), np.cos(doy)
    row["month"] = row.index.month
    return row.astype({c: float for c in features.SEEING_FEATURES})


def level(value: float, levels: list[tuple[float, str]]) -> str:
    return next(name for limit, name in levels if value < limit)


def tonight_hours(window: dict) -> pd.DataFrame:
    """UTC hours of tonight with at least half an hour of astronomical night (as in training)."""
    minutes = pd.DataFrame({"time_utc": pd.date_range(window["start"].floor("h"), window["end"], freq="min",
                                                      inclusive="left")})
    minutes["is_night"] = astro.is_astronomical_night(minutes["time_utc"])
    dark = minutes[minutes["is_night"]]
    counts = dark.groupby(dark["time_utc"].dt.floor("h")).size()
    hours = counts[counts >= hourly.MIN_DARK_MINUTES].index
    out = pd.DataFrame({"hour": hours, "dark_minutes": counts.loc[hours].to_numpy()})
    out["hour_of_night"] = np.arange(len(out))
    out["night_fraction"] = out["hour_of_night"] / len(out)
    return out


# --------------------------------------------------------------------------
# The two forecasts
# --------------------------------------------------------------------------
def forecast_hours(live: dict, window: dict, row: pd.DataFrame, final: bool) -> pd.DataFrame:
    """Forecast 1: the probability that the dome is closed in each hour of tonight."""
    model = joblib.load(MODELS_DIR / "hourly.joblib")["closure"]
    mode = "final" if final else "provisional"
    hours = tonight_hours(window)
    table = hours.join(hourly.hour_forecast(live["forecast"], live.get("upper")), on="hour")
    night = row.reset_index(drop=True)
    table = table.join(pd.concat([night] * len(table), ignore_index=True))
    inputs = model[f"{mode}_features"]
    table["p_closed"] = model[mode].predict_proba(table[inputs].astype(float))[:, 1]
    table["raw_closed"] = hourly.raw_literal(table)
    mid = pd.DatetimeIndex(table["hour"]) + pd.Timedelta(minutes=30)
    table["moon_up"] = astro.moon_altitude_deg(mid) > 0
    return table


def forecast_seeing(row: pd.DataFrame, final: bool) -> float:
    """Forecast 2: the median seeing of the night (train.py nightly model)."""
    seeing = joblib.load(MODELS_DIR / "seeing.joblib")
    model, inputs = (seeing["model"], seeing["features"]) if final else \
        (seeing["model_forecast_only"], seeing["forecast_only_features"])
    return float(model.predict(row[inputs])[0])


def usual_for_month(month: int) -> dict:
    """What is normal for this month (2017-2023): closed hours (full label) and seeing."""
    table = pd.read_parquet(config.PROCESSED_DIR / "hour_table.parquet")
    fitted = table[table["year"] <= train.VALIDATION_YEAR].dropna(subset=["closed"])
    nights = hourly.closed_hours_by_night(fitted, ["closed"])
    seeing = pd.read_parquet(config.PROCESSED_DIR / "model_table.parquet")
    seeing = seeing[seeing["year"] <= train.VALIDATION_YEAR]
    return {"closed_h": round(float(nights.loc[nights["month"] == month, "closed"].mean()), 2),
            "seeing": round(float(seeing.loc[seeing["month"] == month, "seeing_median"].median()), 3)}


def summarise(hours: pd.DataFrame, window: dict, seeing: float, month: int) -> dict:
    weight = hours["dark_minutes"] / 60
    closed_h = float((hours["p_closed"] * weight).sum())
    return {
        "closed_h": round(closed_h, 2),
        "open_h": round(window["length_h"] - closed_h, 2),
        "risk": level(closed_h / window["length_h"], NIGHT_LEVELS),
        "raw_closed_hours": int(hours["raw_closed"].sum()),
        "seeing_arcsec": round(seeing, 2),
        "seeing_class": level(seeing, SEEING_CLASSES),
        "usual": usual_for_month(month),
    }


def hours_for_page(hours: pd.DataFrame) -> list[dict]:
    return [{"t": iso(h.hour), "local": h.hour.tz_convert(LOCAL_TZ).strftime("%H:%M"),
             "dark_minutes": int(h.dark_minutes), "p_closed": round(float(h.p_closed), 3),
             "level": level(h.p_closed, HOUR_LEVELS), "raw_closed": bool(h.raw_closed), "moon_up": bool(h.moon_up)}
            for h in hours.itertuples()]


# --------------------------------------------------------------------------
# Page data
# --------------------------------------------------------------------------
def iso(t: pd.Timestamp) -> str:
    return t.isoformat().replace("+00:00", "Z")


def hourly_curve(forecast: pd.DataFrame, window: dict) -> list[dict]:
    """Forecast hours from 3 h before the night to its end, for the page chart."""
    hours = forecast[(forecast["time_utc"] >= window["start"] - pd.Timedelta(hours=3))
                     & (forecast["time_utc"] <= window["end"])].copy()
    hours["dark"] = astro.is_astronomical_night(hours["time_utc"])
    return [{"t": iso(h.time_utc), "dark": bool(h.dark), "rh": h.relative_humidity_2m, "wind": h.wind_speed_10m,
             "temp": h.temperature_2m, "dew": h.dew_point_2m, "cloud": h.cloud_cover, "precip": h.precipitation}
            for h in hours.itertuples()]


def station_curve(minutes: pd.DataFrame, now: pd.Timestamp) -> list[dict]:
    """Last 24 h at the NOT station, as 10-minute means (small enough for the page)."""
    recent = minutes[minutes["time_utc"] > now - pd.Timedelta(hours=24)].set_index("time_utc")
    blocks = recent[["humidity_pct", "wind_speed_ms", "temp_c"]].resample("10min").mean().dropna(how="all")
    return [{"t": iso(t), "rh": round(r.humidity_pct, 1), "wind": round(r.wind_speed_ms, 1), "temp": round(r.temp_c, 1)}
            for t, r in zip(blocks.index, blocks.itertuples()) if not np.isnan(r.humidity_pct)]


def clean(value):
    """JSON has no NaN: turn missing numbers into null and numpy numbers into plain floats."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return None if np.isnan(value) else round(float(value), 4)
    return value


def run(now: pd.Timestamp, session: PoliteSession) -> dict:
    window = tonight_window(now)
    final = now >= window["start"]
    live = download_live(session, now, config.RAW_DIR / "tonight" / f"{now:%Y-%m-%d}")
    previous = last_night(live["minutes"], live["seeing"], window["night"] - pd.Timedelta(days=1))
    row = build_inputs(live, window, previous, final)
    hours = forecast_hours(live, window, row, final)
    forecast = summarise(hours, window, forecast_seeing(row, final), int(row["month"].iloc[0]))
    last_minute = live["minutes"].dropna(subset=["humidity_pct"]).iloc[-1]
    used = hourly.CLOSURE_FEATURES if final else hourly.CLOSURE_FORECAST_ONLY

    page = {
        "issued_utc": iso(now),
        "mode": "final" if final else "provisional",
        "night": {
            "date": str(window["night"].date()),
            "start_utc": iso(window["start"]), "end_utc": iso(window["end"]),
            "start_local": window["start"].tz_convert(LOCAL_TZ).strftime("%H:%M"),
            "end_local": window["end"].tz_convert(LOCAL_TZ).strftime("%H:%M"),
            "length_h": round(window["length_h"], 2),
            "final_from_utc": iso(window["start"]),
        },
        "forecast": forecast,
        "hours": hours_for_page(hours),
        "moon": astro.moon_during(window["start"], window["end"]),
        "inputs": {name: row[name].iloc[0] for name in used if name in row},
        "last_night": previous,
        "station_now": {"time_utc": iso(last_minute.time_utc), "rh": last_minute.humidity_pct,
                        "wind": last_minute.wind_speed_ms, "temp": last_minute.temp_c,
                        "pressure": last_minute.pressure_hpa},
        "gtc_panel": latest_gtc_panel(),
        "hourly": hourly_curve(live["forecast"], window),
        "station_24h": station_curve(live["minutes"], now),
    }
    return clean(page)


def save(page: dict) -> None:
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DATA_DIR / "tonight.json").write_text(json.dumps(page, ensure_ascii=False, indent=1), encoding="utf-8")
    FORECASTS_DIR.mkdir(parents=True, exist_ok=True)
    issued = {"issued_utc": page["issued_utc"], "night": page["night"]["date"], "mode": page["mode"],
              "model": MODEL_VERSION} | {
        k: page["forecast"][k] for k in ("closed_h", "seeing_arcsec")}
    with (FORECASTS_DIR / "issued.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(issued) + "\n")
    # Last night's outcome (rewritten if the same night is seen again: later runs have more data).
    outcomes_file = FORECASTS_DIR / "outcomes.jsonl"
    outcomes = {}
    if outcomes_file.exists():
        for line in outcomes_file.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            outcomes[record["night"]] = record
    outcomes[page["last_night"]["night"]] = page["last_night"]
    outcomes_file.write_text("".join(json.dumps(outcomes[k]) + "\n" for k in sorted(outcomes)), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--no-fiware", action="store_true", help="do not push the forecast to Orion")
    args = parser.parse_args(argv)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "tonight.log"), logging.StreamHandler(sys.stdout)],
    )
    now = pd.Timestamp(datetime.now(UTC)).floor("min")
    page = run(now, PoliteSession())
    save(page)
    f = page["forecast"]
    log.info("night %s (%s): %.1f of %.1f h expected closed (%s), seeing %.2f\"",
             page["night"]["date"], page["mode"], f["closed_h"], page["night"]["length_h"], f["risk"],
             f["seeing_arcsec"])
    if not args.no_fiware:
        from roque_forecast import fiware  # optional: only when the local FIWARE stack is running
        fiware.push_forecast(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
