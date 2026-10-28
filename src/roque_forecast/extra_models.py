"""Three more nightly forecasts, with labels from the Liverpool Telescope night reports.

1. **Hours lost to weather (LT).** Same idea as the WHT forecast, but with a label
   filled in every night by a robotic telescope, reliable in every year, so the model
   can be trained on 2017-2022 and tested on 2024-2026 like the others.
2. **Photometric sky.** On nights the LT observed, was the sky photometric (clear
   enough for precise brightness measurements)? A clear-sky forecast: cloud and
   high, thin dust spoil it even when the dome is open.
3. **Calima (desert dust).** Does the LT report mention calima/dust that night? The
   input is the CAMS dust forecast (Copernicus, through Open-Meteo), archived only
   since August 2022: the model learns how the forecast dust translates into dust
   that the telescope actually notices. With few events (about 2 % of nights) it is a
   plain logistic regression on two numbers, and it is used as a warning.

Labels are "what the LT reported", a cautious robotic telescope on the same site, not
GTC decisions. Splits as in train.py where the data allow it.

Usage:
    .venv/bin/python -m roque_forecast.extra_models
"""

import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, root_mean_squared_error

from roque_forecast import astro, config, features, hourly, train
from roque_forecast.sources import liverpool

log = logging.getLogger("extra")

DUST_FIRST_NIGHT = pd.Timestamp("2022-08-04")  # first night of the CAMS dust archive
DUST_FEATURES = ["dust_mean_log", "dust_max_log", "doy_sin", "doy_cos"]


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------
def load_liverpool() -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "liverpool").glob("lt_reports_*.html"))
    if not files:
        raise SystemExit("no Liverpool reports: run `backfill liverpool` first")
    parts = [liverpool.parse(f, int(f.stem.rsplit("_", 1)[1])) for f in files]
    table = pd.concat(parts, ignore_index=True).drop_duplicates("night").set_index("night").sort_index()
    table = table[table.index <= pd.Timestamp.now().normalize()]
    return liverpool.labels(table)


def load_dust() -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "open_meteo" / "dust").glob("cams_*.json"))
    if not files:
        raise SystemExit("no CAMS dust files: run `backfill forecasts` first")
    from roque_forecast.sources import open_meteo
    hourly_dust = pd.concat([open_meteo.parse_dust(f) for f in files], ignore_index=True)
    return hourly_dust.drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)


def nightly_dust(hourly_dust: pd.DataFrame) -> pd.DataFrame:
    """Mean and maximum forecast dust over the astronomical night (log scale: dust spans 1-800 ug/m3)."""
    dark = hourly_dust[astro.is_astronomical_night(hourly_dust["time_utc"])]
    night = pd.to_datetime(astro.night_label(dark["time_utc"])).to_numpy()
    g = dark.groupby(night)["dust"]
    out = pd.DataFrame({"dust_mean": g.mean(), "dust_max": g.max()})
    out["dust_mean_log"], out["dust_max_log"] = np.log1p(out["dust_mean"]), np.log1p(out["dust_max"])
    return out


def build_table() -> pd.DataFrame:
    lt = load_liverpool()
    table = pd.read_parquet(config.PROCESSED_DIR / "model_table.parquet")
    lt_cols = ["weather_h", "weather_frac", "photometric", "reason_dust", "observing_h", "technical_h"]
    table = table.join(lt[lt_cols].add_prefix("lt_"), how="left")
    # Last night, as for the other forecasts (shift by one calendar day, not one row).
    previous = lt[["weather_h", "photometric"]].add_prefix("prev_lt_")
    previous.index = previous.index + pd.Timedelta(days=1)
    table = table.join(previous, how="left")
    table["lt_weather_h"] = table["lt_weather_h"].clip(upper=table["night_length_h"].fillna(np.inf))
    table = table.join(nightly_dust(load_dust()), how="left")
    return table


# --------------------------------------------------------------------------
# 1. Hours lost to weather (LT)
# --------------------------------------------------------------------------
LOST_FEATURES = features.FEATURES + ["prev_lt_weather_h"]
LOST_FORECAST_ONLY = train.FORECAST_ONLY + ["prev_lt_weather_h"]


def train_lost(sets: dict) -> tuple[dict, list]:
    target = "lt_weather_h"
    data = {k: v.dropna(subset=[target]) for k, v in sets.items()}

    def score(model, frame):
        return root_mean_squared_error(frame[target], model.predict(frame[LOST_FEATURES]))

    make = lambda st: train.gradient_boosting("regressor", **st)
    settings = train.choose_settings(make, data, target, score, LOST_FEATURES)
    fit_on = pd.concat([data["train"], data["validation"]])
    models = {"gradient boosting": (make(settings), LOST_FEATURES),
              "gradient boosting, forecast only": (make(settings), LOST_FORECAST_ONLY)}
    for model, inputs in models.values():
        model.fit(fit_on[inputs], fit_on[target])
    test = data["test"]
    y = test[target]
    climatology = test["month"].map(fit_on.groupby("month")[target].mean()).to_numpy()
    persistence = test["prev_lt_weather_h"].fillna(pd.Series(climatology, index=test.index)).to_numpy()
    clim_rmse = root_mean_squared_error(y, climatology)
    rows = [{"target": "lt hours lost", "method": "climatology (month)", "kind": "baseline"}
            | train.regression_metrics(y, climatology, clim_rmse),
            {"target": "lt hours lost", "method": "persistence (last night)", "kind": "baseline"}
            | train.regression_metrics(y, persistence, clim_rmse)]
    for name, (model, inputs) in models.items():
        pred = np.clip(model.predict(test[inputs]), 0, test["night_length_h"].fillna(test[target].max()))
        rows.append({"target": "lt hours lost", "method": name, "kind": "model"}
                    | train.regression_metrics(y, pred, clim_rmse))
    return {"model": models["gradient boosting"][0], "features": LOST_FEATURES,
            "model_forecast_only": models["gradient boosting, forecast only"][0],
            "forecast_only_features": LOST_FORECAST_ONLY, "settings": settings}, rows


# --------------------------------------------------------------------------
# 2. Photometric sky
# --------------------------------------------------------------------------
SKY_FEATURES = features.FEATURES + ["prev_lt_photometric"]
SKY_FORECAST_ONLY = train.FORECAST_ONLY + ["prev_lt_photometric"]
CLEAR_CLOUD_PCT = 20  # "raw forecast read literally": mean forecast cloud below 20 % -> photometric


def classification_rows(target_name: str, y: pd.Series, refs: dict, models: dict, frame: pd.DataFrame) -> list:
    clim = brier_score_loss(y, refs["climatology (month)"])
    rows = []
    for name, p in refs.items():
        rows.append({"target": target_name, "method": name, "kind": "baseline"} | hourly.event_metrics(y, p, clim))
    for name, (model, inputs) in models.items():
        rows.append({"target": target_name, "method": name, "kind": "model"}
                    | hourly.event_metrics(y, model.predict_proba(frame[inputs])[:, 1], clim))
    return rows


def train_sky(sets: dict) -> tuple[dict, list]:
    target = "lt_photometric"
    data = {k: v.dropna(subset=[target]).astype({target: float}) for k, v in sets.items()}

    def score(model, frame):
        return brier_score_loss(frame[target], model.predict_proba(frame[SKY_FEATURES])[:, 1])

    make = lambda st: train.gradient_boosting("classifier", **st)
    settings = train.choose_settings(make, data, target, score, SKY_FEATURES)
    fit_on = pd.concat([data["train"], data["validation"]])
    models = {"gradient boosting": (make(settings), SKY_FEATURES),
              "gradient boosting, forecast only": (make(settings), SKY_FORECAST_ONLY)}
    for model, inputs in models.values():
        model.fit(fit_on[inputs], fit_on[target])
    test = data["test"]
    refs = {
        "climatology (month)": test["month"].map(fit_on.groupby("month")[target].mean()).to_numpy(),
        "persistence (last night)": train.conditional_rate(fit_on, fit_on["prev_lt_photometric"] == 1,
                                                           test["prev_lt_photometric"] == 1, target),
        "raw forecast, read literally (cloud < 20 %)": train.conditional_rate(
            fit_on, fit_on["fc_cloud_mean"] < CLEAR_CLOUD_PCT, test["fc_cloud_mean"] < CLEAR_CLOUD_PCT, target),
    }
    rows = classification_rows("photometric sky", test[target], refs, models, test)
    return {"probability": models["gradient boosting"][0], "features": SKY_FEATURES,
            "probability_forecast_only": models["gradient boosting, forecast only"][0],
            "forecast_only_features": SKY_FORECAST_ONLY, "settings": settings}, rows


# --------------------------------------------------------------------------
# 3. Calima
# --------------------------------------------------------------------------
def train_dust(table: pd.DataFrame) -> tuple[dict, list, list]:
    """Train on Aug 2022-2023, test on 2024-2026. Too few events for a validation year:
    the warning threshold is chosen on the training nights (in-sample), stated as such."""
    target = "lt_reason_dust"
    data = table[(table.index >= DUST_FIRST_NIGHT)].dropna(subset=["dust_max", "lt_observing_h"]).copy()
    data[target] = data[target].astype(float)
    fit_on, test = data[data.index < train.TEST_START], data[data.index >= train.TEST_START]
    model = LogisticRegression(max_iter=1000).fit(fit_on[DUST_FEATURES], fit_on[target])
    y = test[target]
    raw_ugm3 = 50  # the live warning threshold before this model: EU daily PM10 limit
    refs = {"climatology (month)": np.full(len(test), fit_on[target].mean()),
            f"raw forecast, read literally (dust max >= {raw_ugm3} ug/m3)": train.conditional_rate(
                fit_on, fit_on["dust_max"] >= raw_ugm3, test["dust_max"] >= raw_ugm3, target)}
    rows = classification_rows("calima", y, refs, {"logistic regression": (model, DUST_FEATURES)}, test)

    # Warning thresholds, chosen on the training nights; scored on the test nights.
    p_fit = model.predict_proba(fit_on[DUST_FEATURES])[:, 1]
    threshold = max(hourly.WARNING_CANDIDATES, key=lambda th: hourly.warning_scores(fit_on[target], p_fit >= th)["peirce"])
    raw_threshold = max([20, 30, 50, 75, 100, 150, 200],
                        key=lambda u: hourly.warning_scores(fit_on[target], (fit_on["dust_max"] >= u).to_numpy())["peirce"])
    p_test = model.predict_proba(test[DUST_FEATURES])[:, 1]
    warnings = [
        {"target": "calima", "warning": f"raw forecast, dust max >= {raw_ugm3} ug/m3"}
        | hourly.warning_scores(y, (test["dust_max"] >= raw_ugm3).to_numpy()),
        {"target": "calima", "warning": f"raw forecast, dust max >= {raw_threshold} ug/m3 (chosen on 2022-2023)"}
        | hourly.warning_scores(y, (test["dust_max"] >= raw_threshold).to_numpy()),
        {"target": "calima", "warning": f"model, probability >= {threshold:.2f} (chosen on 2022-2023)"}
        | hourly.warning_scores(y, p_test >= threshold),
    ]
    log.info("calima: %d training nights (%d with dust), %d test nights (%d with dust)",
             len(fit_on), int(fit_on[target].sum()), len(test), int(y.sum()))
    return {"model": model, "features": DUST_FEATURES, "warning_threshold": threshold,
            "raw_threshold_ugm3": raw_threshold}, rows, warnings


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOG_DIR / "extra_models.log"),
                                  logging.StreamHandler(sys.stdout)])
    table = build_table()
    table.to_parquet(config.PROCESSED_DIR / "model_table_extra.parquet")
    sets = train.split(table)
    lost, lost_rows = train_lost(sets)
    sky, sky_rows = train_sky(sets)
    dust, dust_rows, dust_warnings = train_dust(table)
    joblib.dump({"lost": lost, "sky": sky, "dust": dust}, train.MODELS_DIR / "extra.joblib")
    results = Path(train.RESULTS_DIR)
    pd.DataFrame(lost_rows).to_csv(results / "lt_lost_hours_metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(sky_rows + dust_rows).to_csv(results / "sky_dust_metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(dust_warnings).to_csv(results / "dust_warnings.csv", index=False, float_format="%.3f")
    (results / "extra_settings.json").write_text(json.dumps(
        {"lost": lost["settings"], "sky": sky["settings"], "dust_warning_threshold": dust["warning_threshold"],
         "dust_raw_threshold_ugm3": dust["raw_threshold_ugm3"]}, indent=2))
    pd.set_option("display.width", 220)
    log.info("LT hours lost\n%s", pd.DataFrame(lost_rows).to_string(index=False, float_format="%.3f"))
    log.info("sky and dust\n%s", pd.DataFrame(sky_rows + dust_rows).to_string(index=False, float_format="%.3f"))
    log.info("dust warnings\n%s", pd.DataFrame(dust_warnings).to_string(index=False, float_format="%.3f"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
