"""Tonight hour by hour: one row per (night, hour) instead of one row per night.

Why a second set of models? The nightly models answer "how much of tonight is
lost?". An observer also wants to know WHEN: is the first half good and the
second half wet? Here every astronomical-night hour gets its own forecast:

1. **Dome closed by humidity** in that hour (the NOT rule, as in the nightly label).
2. **Wind above the closing limit** in that hour: the INT, also on the Roque,
   closes when gusts exceed 80 km/h (22.2 m/s) for more than 10 s (ING public
   procedure). The NOT station gives one wind value per minute, so the label is
   "at least one minute at or above 22.2 m/s".
3. **Seeing** of that hour (median of the R2D2 measurements).

For each hour we also keep what the weather forecast says ON ITS OWN, read
literally (forecast humidity >= 90 % -> "closed"; forecast wind >= 22.2 m/s ->
"too windy"). The page shows both side by side: the raw forecast is almost
always wetter and calmer than the summit (the model grid point sits inside the
cloud layer, below the real summit), which is exactly what the models learn to
correct.

Inputs of each hour (all known before the night starts, as in features.py):
- the forecast for that hour (humidity, dew-point margin, temperature, wind,
  cloud, rain, pressure; jet-stream wind for the seeing);
- the forecast summary for the whole night and the station in the 2 hours
  before the night (only in final mode, as for the nightly models);
- last night, the time of year and the position of the hour in the night.

Evaluation as in train.py: train 2017-2022, choose settings on 2023, report
2024-2026, always against reference methods.

Usage:
    .venv/bin/python -m roque_forecast.hourly
"""

import json
import logging
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score, root_mean_squared_error

from roque_forecast import config, features, train

log = logging.getLogger("hourly")

WIND_LIMIT_MS = 22.2  # 80 km/h, INT dome-closing limit for gusts (ING observer alert procedure)
HUMIDITY_LIMIT_PCT = 90.0  # same number as the NOT closing rule
MIN_DARK_MINUTES = 30  # an hour belongs to the night if at least half of it is astronomical night
MIN_SEEING_POINTS = 30  # R2D2 points needed for an hourly seeing value (~15-30 min of data)

# Inputs that describe the hour itself (the forecast valid at mid-hour).
HOUR_FEATURES = ["h_rh", "h_dew_spread", "h_temp", "h_wind", "h_wind_u", "h_wind_v", "h_cloud", "h_precip",
                 "h_pressure", "h_wind_750", "hour_of_night", "night_fraction"]
CLOSURE_FEATURES = HOUR_FEATURES + features.FEATURES
CLOSURE_FORECAST_ONLY = HOUR_FEATURES + train.FORECAST_ONLY
SEEING_FEATURES = HOUR_FEATURES + ["h_jet"] + features.SEEING_FEATURES
SEEING_FORECAST_ONLY = HOUR_FEATURES + ["h_jet"] + train.SEEING_FORECAST_ONLY

RESULTS_DIR = train.RESULTS_DIR
MODELS_DIR = train.MODELS_DIR


# --------------------------------------------------------------------------
# Building the hourly table
# --------------------------------------------------------------------------
def hour_forecast(hourly: pd.DataFrame, upper: pd.DataFrame | None = None) -> pd.DataFrame:
    """Forecast valid at the middle of each UTC hour: mean of the values at h and h+1.

    `hourly` is open_meteo.parse() output (one row per forecast hour). The result is
    indexed by the start of each hour (UTC).
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


def hour_slots(minutes: pd.DataFrame) -> pd.DataFrame:
    """Every UTC hour with at least MIN_DARK_MINUTES of astronomical night, and what happened in it.

    `minutes` is the NOT minute table (time_utc, is_night, night, dome_closed, humidity_pct,
    wind_speed_ms). Returns one row per hour: night, hour start, dark minutes, the
    position of the hour in the night and the labels (closed / windy) when measured.
    """
    dark = minutes[minutes["is_night"]].copy()
    dark["hour"] = dark["time_utc"].dt.floor("h")
    g = dark.groupby(["night", "hour"])
    slots = pd.DataFrame({
        "dark_minutes": g.size(),
        "humidity_minutes": g["humidity_pct"].count(),
        "wind_minutes": g["wind_speed_ms"].count(),
        "closed_frac": g["dome_closed"].mean(),
        "wind_max": g["wind_speed_ms"].max(),
    }).reset_index()
    slots = slots[slots["dark_minutes"] >= MIN_DARK_MINUTES]
    slots["night"] = pd.to_datetime(slots["night"])
    # Position in the night: 0 for the first hour, and as a fraction of the night's hours.
    slots["hour_of_night"] = slots.groupby("night").cumcount()
    slots["night_fraction"] = slots["hour_of_night"] / slots.groupby("night")["hour"].transform("size")
    # Labels only where the station measured most of the hour (otherwise missing).
    slots["closed"] = np.where(slots["humidity_minutes"] >= 45, (slots["closed_frac"] >= 0.5).astype(float), np.nan)
    slots["windy"] = np.where(slots["wind_minutes"] >= 45, (slots["wind_max"] >= WIND_LIMIT_MS).astype(float),
                              np.nan)
    return slots


def hourly_seeing(points: pd.DataFrame) -> pd.Series:
    """Median R2D2 seeing per UTC hour (hours with enough measurements only)."""
    hour = points["time_utc"].dt.floor("h")
    g = points.groupby(hour)["seeing_arcsec"]
    median = g.median()
    return median[g.size() >= MIN_SEEING_POINTS].rename("seeing")


def build_table() -> pd.DataFrame:
    minutes = pd.read_parquet(
        config.PROCESSED_DIR / "not_minutes.parquet",
        columns=["time_utc", "is_night", "night", "dome_closed", "humidity_pct", "wind_speed_ms"],
        filters=[("time_utc", ">=", features.FIRST_NIGHT.tz_localize("UTC"))],
    )
    slots = hour_slots(minutes)
    forecast = hour_forecast(features.load_forecasts("historical"), features.load_upper())
    seeing = hourly_seeing(pd.read_parquet(config.PROCESSED_DIR / "r2d2_points.parquet"))
    nightly = pd.read_parquet(config.PROCESSED_DIR / "model_table.parquet")

    table = slots.join(forecast, on="hour").join(seeing, on="hour")
    keep = [*features.SEEING_FEATURES, "month", "year"]
    table = table.join(nightly[keep], on="night", how="inner")  # nights with a forecast archive
    table = table.dropna(subset=["h_rh"])
    return table.set_index(["night", "hour"]).sort_index()


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
def split(table: pd.DataFrame) -> dict[str, pd.DataFrame]:
    nights = table.index.get_level_values("night")
    return {"train": table[table["year"].isin(train.TRAIN_YEARS)],
            "validation": table[table["year"] == train.VALIDATION_YEAR],
            "test": table[nights >= train.TEST_START]}


def rate_by(fit: pd.DataFrame, condition_fit: pd.Series, condition_eval: pd.Series, target: str) -> np.ndarray:
    """Turn a yes/no rule into a probability with the TRAINING years (as train.conditional_rate)."""
    return train.conditional_rate(fit, condition_fit, condition_eval, target)


def event_baselines(fit: pd.DataFrame, frame: pd.DataFrame, target: str, raw_rule) -> dict[str, np.ndarray]:
    month_rate = fit.groupby("month")[target].mean()
    out = {
        "climatology (month)": frame["month"].map(month_rate).to_numpy(),
        # The raw forecast turned into a probability: how often the event happened, in the
        # training years, when the forecast read literally said yes (and when it said no).
        "raw forecast, read literally": rate_by(fit, raw_rule(fit), raw_rule(frame), target),
    }
    if target == "closed":  # last night and the station before the night are about humidity
        out["persistence (last night)"] = rate_by(fit, fit["prev_dome_closed_frac"] >= 0.5,
                                                  frame["prev_dome_closed_frac"] >= 0.5, target)
        out["precasting (humidity before night >= 90 %)"] = rate_by(
            fit, fit["pre_humidity_max"] >= 90, frame["pre_humidity_max"] >= 90, target)
    return out


def train_event(sets: dict, target: str, full: list[str], forecast_only: list[str], raw_rule) -> tuple[dict, list]:
    data = {k: v.dropna(subset=[target]) for k, v in sets.items()}
    log.info("%s: %d training hours, event rate %.3f", target, len(data["train"]), data["train"][target].mean())

    def score(model, frame):
        return brier_score_loss(frame[target], model.predict_proba(frame[full])[:, 1])

    def score_forecast_only(model, frame):
        return brier_score_loss(frame[target], model.predict_proba(frame[forecast_only])[:, 1])

    make = lambda st: train.gradient_boosting("classifier", **st)
    settings = train.choose_settings(make, data, target, score, full)
    # The forecast-only twin gets its own settings: with fewer inputs it needs different
    # regularisation (with the full model's settings the wind twin was worse than climatology).
    settings_fo = train.choose_settings(make, data, target, score_forecast_only, forecast_only)
    fit_on = pd.concat([data["train"], data["validation"]])
    models = {"gradient boosting": (make(settings), full),
              "gradient boosting, forecast only": (make(settings_fo), forecast_only)}
    for model, inputs in models.values():
        model.fit(fit_on[inputs], fit_on[target])

    test = data["test"]
    y = test[target]
    refs = event_baselines(fit_on, test, target, raw_rule)
    clim = brier_score_loss(y, refs["climatology (month)"])
    rows = []
    for name, p in refs.items():
        rows.append({"target": target, "method": name, "kind": "baseline"} | event_metrics(y, p, clim))
    for name, (model, inputs) in models.items():
        rows.append({"target": target, "method": name, "kind": "model"}
                    | event_metrics(y, model.predict_proba(test[inputs])[:, 1], clim))
    # What the raw forecast says as a plain yes/no, to show how often it is right.
    literal = raw_rule(test).astype(float)
    rows.append({"target": target, "method": "raw forecast, yes/no", "kind": "baseline"}
                | event_metrics(y, literal.to_numpy(), clim))
    thresholds = {"final": warning_threshold(data, target, full, settings),
                  "provisional": warning_threshold(data, target, forecast_only, settings_fo)}
    warnings = [{"target": target, "warning": "raw forecast, read literally"} | warning_scores(y, literal.to_numpy() > 0)]
    for mode, (model, inputs) in [("final", models["gradient boosting"]),
                                  ("provisional", models["gradient boosting, forecast only"])]:
        p = model.predict_proba(test[inputs])[:, 1]
        warnings.append({"target": target, "warning": f"model, {mode} (threshold {thresholds[mode]:.2f})"}
                        | warning_scores(y, p >= thresholds[mode]))
    return {"probability": models["gradient boosting"][0], "features": full, "warning_thresholds": thresholds,
            "warning_test_scores": warnings,
            "probability_forecast_only": models["gradient boosting, forecast only"][0],
            "forecast_only_features": forecast_only, "settings": settings,
            "settings_forecast_only": settings_fo}, rows


WARNING_CANDIDATES = [0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5]


def warning_scores(y: pd.Series, warn: np.ndarray) -> dict:
    """How good a yes/no warning is: share of events warned (hits), share of warnings
    that were wrong (false alarms) and the Peirce skill score (hits minus false-alarm
    rate among non-events; 0 = no skill, 1 = perfect)."""
    event = y.to_numpy() == 1
    hits = (warn & event).sum() / max(event.sum(), 1)
    false_alarm_ratio = (warn & ~event).sum() / max(warn.sum(), 1)
    false_alarm_rate = (warn & ~event).sum() / max((~event).sum(), 1)
    return {"hit_rate": float(hits), "false_alarm_ratio": float(false_alarm_ratio),
            "peirce": float(hits - false_alarm_rate), "warned_hours": int(warn.sum()), "event_hours": int(event.sum())}


def warning_threshold(data: dict, target: str, inputs: list[str], settings: dict) -> float:
    """For rare events (strong wind) a probability is badly calibrated, but the ranking
    is good. So the model drives a yes/no WARNING: the probability threshold with the
    best Peirce score on the validation year, from a model fitted on the training years only."""
    model = train.gradient_boosting("classifier", **settings).fit(data["train"][inputs], data["train"][target])
    p = model.predict_proba(data["validation"][inputs])[:, 1]
    best = max(WARNING_CANDIDATES, key=lambda th: warning_scores(data["validation"][target], p >= th)["peirce"])
    log.info("%s warning threshold (validation, %d inputs): %.2f", target, len(inputs), best)
    return best


def event_metrics(y: pd.Series, p: np.ndarray, reference_brier: float) -> dict:
    brier = brier_score_loss(y, p)
    said = p >= 0.5
    return {"hours": len(y), "event_rate": float(y.mean()), "brier": brier,
            "brier_skill_vs_climatology": 1 - brier / reference_brier,
            "auc": roc_auc_score(y, p) if len(np.unique(p)) > 1 else np.nan,
            "hit_rate": float(said[y == 1].mean()) if (y == 1).any() else np.nan,
            "false_alarm_ratio": float((y[said] == 0).mean()) if said.any() else np.nan}


def train_seeing(sets: dict) -> tuple[dict, list]:
    target = "seeing"
    data = {k: v.dropna(subset=[target]) for k, v in sets.items()}

    def score(model, frame):
        return root_mean_squared_error(frame[target], model.predict(frame[SEEING_FEATURES]))

    settings = train.choose_settings(lambda st: train.log_target(train.gradient_boosting("regressor", **st)),
                                     data, target, score, SEEING_FEATURES)
    fit_on = pd.concat([data["train"], data["validation"]])
    models = {"gradient boosting": (train.log_target(train.gradient_boosting("regressor", **settings)),
                                    SEEING_FEATURES),
              "gradient boosting, forecast only": (train.log_target(train.gradient_boosting("regressor", **settings)),
                                                   SEEING_FORECAST_ONLY)}
    for model, inputs in models.values():
        model.fit(fit_on[inputs], fit_on[target])

    test = data["test"]
    y = test[target]
    month_median = fit_on.groupby("month")[target].median()
    climatology = test["month"].map(month_median).to_numpy()
    persistence = test["prev_seeing_median"].fillna(pd.Series(climatology, index=test.index)).to_numpy()
    clim_rmse = root_mean_squared_error(y, climatology)
    rows = []
    for name, kind, pred in [("climatology (month)", "baseline", climatology),
                             ("persistence (last night's median)", "baseline", persistence)]:
        rows.append({"target": target, "method": name, "kind": kind} | train.regression_metrics(y, pred, clim_rmse))
    for name, (model, inputs) in models.items():
        rows.append({"target": target, "method": name, "kind": "model"}
                    | train.regression_metrics(y, model.predict(test[inputs]), clim_rmse))
    return {"model": models["gradient boosting"][0], "features": SEEING_FEATURES,
            "model_forecast_only": models["gradient boosting, forecast only"][0],
            "forecast_only_features": SEEING_FORECAST_ONLY, "settings": settings}, rows


def humid_literal(frame: pd.DataFrame) -> pd.Series:
    return frame["h_rh"] >= HUMIDITY_LIMIT_PCT


def windy_literal(frame: pd.DataFrame) -> pd.Series:
    """The forecast wind read literally: the 750 hPa wind (summit height) where it exists,
    otherwise the 10 m wind of the grid point."""
    return frame["h_wind_750"].fillna(frame["h_wind"]) >= WIND_LIMIT_MS


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOG_DIR / "hourly.log"), logging.StreamHandler(sys.stdout)])
    table = build_table()
    table.to_parquet(config.PROCESSED_DIR / "hour_table.parquet")
    log.info("hour table: %d hours in %d nights", len(table), table.index.get_level_values("night").nunique())
    sets = split(table)

    closure, closure_rows = train_event(sets, "closed", CLOSURE_FEATURES, CLOSURE_FORECAST_ONLY, humid_literal)
    wind, wind_rows = train_event(sets, "windy", CLOSURE_FEATURES, CLOSURE_FORECAST_ONLY, windy_literal)
    pd.DataFrame(closure["warning_test_scores"] + wind["warning_test_scores"]).to_csv(
        RESULTS_DIR / "hourly_warnings.csv", index=False, float_format="%.3f")
    seeing, seeing_rows = train_seeing(sets)
    joblib.dump({"closure": closure, "wind": wind, "seeing": seeing, "wind_limit_ms": WIND_LIMIT_MS},
                MODELS_DIR / "hourly.joblib")

    metrics = pd.DataFrame(closure_rows + wind_rows)
    metrics.to_csv(RESULTS_DIR / "hourly_events_metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(seeing_rows).to_csv(RESULTS_DIR / "hourly_seeing_metrics.csv", index=False, float_format="%.4f")
    (RESULTS_DIR / "hourly_settings.json").write_text(json.dumps(
        {"closure": closure["settings"], "wind": wind["settings"], "seeing": seeing["settings"],
         "wind_limit_ms": WIND_LIMIT_MS}, indent=2))
    pd.set_option("display.width", 200)
    log.info("events\n%s", metrics.to_string(index=False, float_format="%.3f"))
    log.info("seeing\n%s", pd.DataFrame(seeing_rows).to_string(index=False, float_format="%.3f"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
