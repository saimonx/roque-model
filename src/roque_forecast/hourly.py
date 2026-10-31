"""Forecast 1 of the project, hour by hour: will the dome be closed?

For each night hour: the probability that the dome is closed for at least half of
that hour, for humidity, wind or ice (dome.closed: the NOT humidity rule, the INT
wind limit and an ice rule, rebuilt minute by minute from the NOT weather station).
The night's expected closed hours are the sum of the hourly probabilities, so the
table and the total always agree.

(Forecast 2, the seeing, is one number per night: see train.py. An hourly seeing
model was tried and dropped: on 2024-2026 its error was barely below the monthly
climatology, and the night's seeing derived from it was worse than the nightly
model, mean error 0.215" against 0.196".)

Inputs of each hour (all known before the night starts, as in features.py):
- the weather forecast valid at mid-hour (ECMWF: humidity, dew-point margin,
  temperature, cloud, rain, pressure; GFS: wind at 750 hPa, summit height);
- the forecast summary for the whole night, the NOT station in the 2 hours before
  the night (only in the "final" mode, see below), last night and the time of year;
- the position of the hour in the night.

Two modes, because the station readings "just before the night" only exist once the
night starts: "provisional" (forecast-only twin models, used in the afternoon) and
"final" (full models, from the start of astronomical night).

Evaluation as in train.py: train 2017-2022, choose settings on 2023, report on
2024-2026, always against simple reference methods, hour by hour and for the
night's closed hours.

Usage:
    .venv/bin/python -m roque_forecast.hourly
"""

import json
import logging
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    brier_score_loss,
    mean_absolute_error,
    roc_auc_score,
    root_mean_squared_error,
)

from roque_forecast import config, dome, features, train

log = logging.getLogger("hourly")

MIN_DARK_MINUTES = 30  # an hour belongs to the night if at least half of it is astronomical night
MIN_LABEL_MINUTES = 45  # the station must have measured most of the hour

# Inputs that describe the hour itself (the forecast valid at mid-hour).
HOUR_FEATURES = ["h_rh", "h_dew_spread", "h_temp", "h_wind", "h_wind_u", "h_wind_v", "h_cloud", "h_precip",
                 "h_pressure", "h_wind_750", "hour_of_night", "night_fraction"]
CLOSURE_FEATURES = HOUR_FEATURES + features.FEATURES
CLOSURE_FORECAST_ONLY = HOUR_FEATURES + train.FORECAST_ONLY

RESULTS_DIR = train.RESULTS_DIR
MODELS_DIR = train.MODELS_DIR


# --------------------------------------------------------------------------
# Building the hourly table
# --------------------------------------------------------------------------
def hour_forecast(hourly: pd.DataFrame, upper: pd.DataFrame | None = None) -> pd.DataFrame:
    """Forecast valid at the middle of each UTC hour: mean of the values at h and h+1.

    `hourly` is open_meteo.parse() output (one row per forecast hour), `upper` the GFS
    pressure-level winds. The result is indexed by the start of each hour (UTC).
    """
    h = hourly.set_index("time_utc").sort_index()
    mid = (h + h.shift(-1)) / 2  # value at h:30, interpolated between h and h+1
    direction = np.radians(h["wind_direction_10m"])
    u = -h["wind_speed_10m"] * np.sin(direction)
    v = -h["wind_speed_10m"] * np.cos(direction)
    out = pd.DataFrame({
        "h_rh": mid["relative_humidity_2m"],
        "h_dew_spread": mid["temperature_2m"] - mid["dew_point_2m"],
        "h_temp": mid["temperature_2m"],
        "h_wind": mid["wind_speed_10m"],
        "h_wind_u": (u + u.shift(-1)) / 2,
        "h_wind_v": (v + v.shift(-1)) / 2,
        "h_cloud": mid["cloud_cover"],
        "h_precip": h["precipitation"].shift(-1),  # rain accumulated during the hour
        "h_pressure": mid["surface_pressure"],
    })
    out["h_jet"], out["h_wind_750"] = np.nan, np.nan
    if upper is not None and len(upper):
        g = upper.set_index("time_utc").sort_index()
        for column, name in [("wind_speed_200hPa", "h_jet"), ("wind_speed_750hPa", "h_wind_750")]:
            if column in g:
                out[name] = ((g[column] + g[column].shift(-1)) / 2).reindex(out.index)
    return out


def label_minutes(minutes: pd.DataFrame) -> pd.DataFrame:
    """Add the full closure label (humidity, wind or ice) to the minute table."""
    minutes = minutes.sort_values("time_utc").reset_index(drop=True)
    minutes["closed"] = dome.closed(minutes)
    return minutes


def hour_slots(minutes: pd.DataFrame) -> pd.DataFrame:
    """Every UTC hour with at least MIN_DARK_MINUTES of astronomical night, and what happened in it.

    `minutes` is the NOT minute table with the full closure label (column `closed`,
    see label_minutes). Returns one row per hour with its position in the night and
    the label `closed` (missing when the station did not measure most of the hour).
    """
    dark = minutes[minutes["is_night"]].copy()
    dark["hour"] = dark["time_utc"].dt.floor("h")
    dark["measured"] = dark["humidity_pct"].notna() & dark["wind_speed_ms"].notna()
    g = dark.groupby(["night", "hour"])
    slots = pd.DataFrame({"dark_minutes": g.size(), "measured_minutes": g["measured"].sum(),
                          "closed_frac": g["closed"].mean()}).reset_index()
    slots = slots[slots["dark_minutes"] >= MIN_DARK_MINUTES]
    slots["night"] = pd.to_datetime(slots["night"])
    slots["hour_of_night"] = slots.groupby("night").cumcount()
    slots["night_fraction"] = slots["hour_of_night"] / slots.groupby("night")["hour"].transform("size")
    slots["closed"] = np.where(slots["measured_minutes"] >= MIN_LABEL_MINUTES,
                               (slots["closed_frac"] >= 0.5).astype(float), np.nan)
    return slots


def build_table() -> pd.DataFrame:
    minutes = pd.read_parquet(
        config.PROCESSED_DIR / "not_minutes.parquet",
        columns=["time_utc", "is_night", "night", "humidity_pct", "wind_speed_ms", "temp_c"],
        filters=[("time_utc", ">=", features.FIRST_NIGHT.tz_localize("UTC") - pd.Timedelta(days=2))],
    )
    slots = hour_slots(label_minutes(minutes))
    forecast = hour_forecast(features.load_forecasts("historical"), features.load_upper())
    nightly = pd.read_parquet(config.PROCESSED_DIR / "model_table.parquet")

    # Last night with the full label (the nightly table's persistence input is humidity only).
    previous = slots.groupby("night")["closed_frac"].mean()
    previous.index = previous.index + pd.Timedelta(days=1)
    nightly = nightly.drop(columns=["prev_dome_closed_frac"]).join(previous.rename("prev_dome_closed_frac"))

    table = slots.join(forecast, on="hour")
    keep = [*features.SEEING_FEATURES, "month", "year"]
    table = table.join(nightly[keep], on="night", how="inner")  # nights with a forecast archive
    table = table.dropna(subset=["h_rh"])
    return table.set_index(["night", "hour"]).sort_index()


def split(table: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Time split on the night, with the same years as train.py."""
    nights = table.index.get_level_values("night")
    return {"train": table[table["year"].isin(train.TRAIN_YEARS)],
            "validation": table[table["year"] == train.VALIDATION_YEAR],
            "test": table[nights >= train.TEST_START]}


# --------------------------------------------------------------------------
# Scores, in technical and in plain terms
# --------------------------------------------------------------------------
def event_scores(y: pd.Series, p: np.ndarray, reference_brier: float) -> dict:
    """Probability scores, and the plain reading of the yes/no call "closed if p >= 50 %":
    right = share of the "closed" calls that were right; caught = share of the closed
    hours that were called."""
    p = np.asarray(p, dtype=float)
    brier = brier_score_loss(y, p)
    said = p >= 0.5
    event = y.to_numpy() == 1
    return {"n": len(y), "event_rate": float(event.mean()), "brier": brier,
            "brier_skill": 1 - brier / reference_brier,
            "auc": roc_auc_score(y, p) if len(np.unique(p)) > 1 else np.nan,
            "right": float(event[said].mean()) if said.any() else np.nan,
            "caught": float(said[event].mean()) if event.any() else np.nan}


def number_scores(y: pd.Series, pred: np.ndarray, reference_mae: float) -> dict:
    mae = mean_absolute_error(y, pred)
    return {"n": len(y), "mae": mae, "rmse": root_mean_squared_error(y, pred), "mae_skill": 1 - mae / reference_mae}


# --------------------------------------------------------------------------
# 1. Dome closed
# --------------------------------------------------------------------------
def raw_literal(frame: pd.DataFrame) -> pd.Series:
    """The weather forecast read literally with the label's three rules: humidity >= 90 %,
    wind >= 22.2 m/s (750 hPa where available) or freezing with high humidity."""
    wind = frame["h_wind_750"].fillna(frame["h_wind"])
    humid = frame["h_rh"] >= dome.HUMIDITY_LIMIT_PCT
    return humid | (wind >= dome.WIND_LIMIT_MS) | ((frame["h_temp"] <= dome.ICE_TEMP_C) & humid)


def train_closure(sets: dict) -> tuple[dict, list, pd.DataFrame]:
    target = "closed"
    data = {k: v.dropna(subset=[target]) for k, v in sets.items()}

    def scorer(inputs):
        return lambda model, frame: brier_score_loss(frame[target], model.predict_proba(frame[inputs])[:, 1])

    # Model and settings: those chosen by the wide search over three validation years
    # (compare.py, reports/results/model_search.json). Without that file, gradient
    # boosting with the small grid on 2023 only.
    from roque_forecast import compare  # imported here: compare.py itself imports this module
    searched = compare.chosen_settings("final"), compare.chosen_settings("provisional")
    if all(searched):
        (kind, settings, trees), (kind_fo, settings_fo, trees_fo) = searched
        settings = {"model": kind, **settings, "trees": trees}
        settings_fo = {"model": kind_fo, **settings_fo, "trees": trees_fo}
    else:
        def gb(settings):
            return train.gradient_boosting("classifier", **settings)
        settings = {"model": "gradient_boosting", "trees": 300, **train.choose_settings(
            gb, data, target, scorer(CLOSURE_FEATURES), CLOSURE_FEATURES)}
        settings_fo = {"model": "gradient_boosting", "trees": 300, **train.choose_settings(
            gb, data, target, scorer(CLOSURE_FORECAST_ONLY), CLOSURE_FORECAST_ONLY)}

    def make(settings):
        rest = {k: v for k, v in settings.items() if k not in ("model", "trees")}
        return compare.build(settings["model"], rest, settings["trees"])

    fit_on = pd.concat([data["train"], data["validation"]])
    final = make(settings).fit(fit_on[CLOSURE_FEATURES], fit_on[target])
    provisional = make(settings_fo).fit(fit_on[CLOSURE_FORECAST_ONLY], fit_on[target])

    test = data["test"]
    y = test[target]

    def rate(condition_fit, condition_test):
        return train.conditional_rate(fit_on, condition_fit, condition_test, target)

    p = {
        "climatology": test["month"].map(fit_on.groupby("month")[target].mean()).to_numpy(),
        "raw forecast": raw_literal(test).astype(float).to_numpy(),
        "persistence": rate(fit_on["prev_dome_closed_frac"] >= 0.5, test["prev_dome_closed_frac"] >= 0.5),
        "precasting": rate(fit_on["pre_humidity_max"] >= 90, test["pre_humidity_max"] >= 90),
        "model, provisional": provisional.predict_proba(test[CLOSURE_FORECAST_ONLY])[:, 1],
        "model, final": final.predict_proba(test[CLOSURE_FEATURES])[:, 1],
    }
    clim = brier_score_loss(y, p["climatology"])
    rows = [{"forecast": "hour closed", "method": name} | event_scores(y, prob, clim) for name, prob in p.items()]
    predictions = test[["closed", "dark_minutes", "month"]].assign(
        p_final=p["model, final"], p_provisional=p["model, provisional"], raw=p["raw forecast"],
        climatology=p["climatology"])
    # The live models (RoqueModel). The test years were kept apart only to measure the
    # scores above, which stay as they are. Now that they are measured, the models that
    # forecast each night are refitted with the same settings on every labelled year
    # (2017-2026): more hours, and the most recent ones. Checked before doing it: with the
    # same settings, adding 2024 to the training improved the 2025-2026 scores
    # (final: wrong in 9.7 % -> 9.2 % of hours; provisional: 13.2 % -> 12.0 %).
    everything = pd.concat([data["train"], data["validation"], data["test"]])
    live_final = make(settings).fit(everything[CLOSURE_FEATURES], everything[target])
    live_provisional = make(settings_fo).fit(everything[CLOSURE_FORECAST_ONLY], everything[target])
    years = everything.index.get_level_values("night").year
    model = {"final": live_final, "final_features": CLOSURE_FEATURES, "provisional": live_provisional,
             "provisional_features": CLOSURE_FORECAST_ONLY, "settings": settings,
             "settings_provisional": settings_fo,
             "trained_on": {"first_year": int(years.min()), "last_year": int(years.max()),
                            "first_night": str(everything.index.get_level_values("night").min().date()),
                            "last_night": str(everything.index.get_level_values("night").max().date()),
                            "hours": len(everything), "closed_hours": int(everything[target].sum())},
             "evaluated_on": {"trained": [int(data["train"]["year"].min()), int(data["validation"]["year"].max())],
                              "tested": [int(test["year"].min()), int(test["year"].max())]}}
    return model, rows, predictions


# --------------------------------------------------------------------------
# 2. The night's closed hours, derived from the hours
# --------------------------------------------------------------------------
def closed_hours_by_night(hours: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Sum over each night of (probability or label) x (dark hours in that slot)."""
    weight = hours["dark_minutes"] / 60
    out = hours[columns].mul(weight, axis=0).groupby(level="night").sum()
    out["month"] = hours["month"].groupby(level="night").first()
    return out


def nightly_scores(closure_pred: pd.DataFrame, fit_on: pd.DataFrame) -> tuple[list, pd.DataFrame]:
    """Expected closed hours (sum of hourly probabilities), scored against what happened
    and against simple references for the whole night."""
    nights = closed_hours_by_night(closure_pred, ["closed", "p_final", "p_provisional", "raw"])
    fit_nights = closed_hours_by_night(fit_on.dropna(subset=["closed"]), ["closed"])
    nights["climatology"] = nights["month"].map(fit_nights.groupby("month")["closed"].mean())
    consecutive = nights.index.to_series().diff() == pd.Timedelta(days=1)
    nights["persistence"] = nights["closed"].shift(1).where(consecutive).fillna(nights["climatology"])
    clim = mean_absolute_error(nights["closed"], nights["climatology"])
    labels = {"climatology": "climatology", "persistence": "persistence", "raw": "raw forecast",
              "p_provisional": "model, provisional", "p_final": "model, final"}
    rows = [{"forecast": "night closed hours", "method": label} | number_scores(nights["closed"], nights[col], clim)
            for col, label in labels.items()]
    return rows, nights


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOG_DIR / "hourly.log"), logging.StreamHandler(sys.stdout)])
    table = build_table()
    table.to_parquet(config.PROCESSED_DIR / "hour_table.parquet")
    log.info("hour table: %d hours in %d nights, closed %.1f %% of measured hours", len(table),
             table.index.get_level_values("night").nunique(), 100 * table["closed"].mean())
    sets = split(table)

    closure, closure_rows, closure_pred = train_closure(sets)
    night_rows, nights = nightly_scores(closure_pred, pd.concat([sets["train"], sets["validation"]]))

    joblib.dump({"closure": closure}, MODELS_DIR / "hourly.joblib")
    scores = pd.DataFrame(closure_rows + night_rows)
    scores.to_csv(RESULTS_DIR / "hourly_scores.csv", index=False, float_format="%.4f")
    closure_pred.to_parquet(config.PROCESSED_DIR / "hour_predictions.parquet")
    nights.to_parquet(config.PROCESSED_DIR / "night_predictions.parquet")
    (RESULTS_DIR / "hourly_settings.json").write_text(json.dumps(
        {"closure": closure["settings"], "closure_provisional": closure["settings_provisional"],
         "live_models_trained_on": closure["trained_on"], "scores_from": closure["evaluated_on"]}, indent=2))
    pd.set_option("display.width", 200)
    log.info("scores (test 2024-2026)\n%s", scores.to_string(index=False, float_format="%.3f"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
