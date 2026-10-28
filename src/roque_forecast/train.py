"""Train and evaluate the three night forecasts against simple reference methods.

    1. Dome closure risk: probability that the humidity rule closes the dome for
       at least 1 hour tonight (plus a second model for the number of hours).
    2. Seeing: median seeing of the night (R2D2), in arcseconds.
    3. Hours lost to weather (WHT accounting), from the predicted closure hours.

Usage:
    .venv/bin/python -m roque_forecast.train

Writes reports/results/*.csv (metrics, small, committed), the fitted models in
data/models/ and every night's predictions in data/processed/predictions.parquet.

How the evaluation stays honest
-------------------------------
- **Time split, never a random one.** Train on 2017-2022, choose settings on
  2023 (validation), and report on 2024-2026 (test), which no step has seen.
  Shuffling nights at random would leak information: consecutive nights look
  alike, so the model would be tested on near-copies of nights it trained on.
- **Reference methods ("baselines") a model must beat to be worth anything:**
  climatology (the usual value for that month), persistence (same as last
  night) and precasting (the conditions at the station right before the night).
  For closure we add a plain rule on the forecast humidity. Every baseline is
  turned into a probability using the TRAINING years only.
- **Two forecast archives** (see sources/open_meteo.py): the long, slightly
  optimistic one for training and testing, and the 24-hour-old forecasts on the
  nights where they exist, a slightly pessimistic check of the same models.
"""

import itertools
import json
import logging
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    brier_score_loss,
    mean_absolute_error,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from roque_forecast import config
from roque_forecast.features import FEATURES, OBSERVED_FEATURES

log = logging.getLogger("train")

RESULTS_DIR = config.PROJECT_DIR / "reports" / "results"
MODELS_DIR = config.DATA_DIR / "models"

TRAIN_YEARS = range(2017, 2023)  # 2017-2022
VALIDATION_YEAR = 2023
TEST_START = pd.Timestamp("2024-01-01")

# WHT accounting: years whose night logs agree with the measured weather (see EDA
# section 6). In 2019-2022 and 2024-2025 many nights with the dome closed are
# booked as fully observed, so those years are kept only for comparison.
RELIABLE_WHT_YEARS = [2017, 2018, 2023, 2026]
WHT_FIT_YEARS = [2017, 2018, 2023]  # the calibration is fitted on these...
WHT_TEST_YEARS = [2026]  # ...and tested on this one
# The monthly WHT climatology can use the long reliable history (it needs no forecast).
WHT_CLIMATOLOGY_YEARS = range(2010, 2019)

# Small grid of gradient-boosting settings, chosen on the validation year.
GRID = {
    "learning_rate": [0.03, 0.1],
    "max_leaf_nodes": [7, 15],
    "min_samples_leaf": [20, 50],
}
SEED = 2026
# Variant without the station readings before the night: what the forecast alone is
# worth (e.g. to plan tomorrow night, when tonight's station readings do not exist yet).
FORECAST_ONLY = [f for f in FEATURES if f not in OBSERVED_FEATURES]


# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------
def split(table: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "train": table[table["year"].isin(TRAIN_YEARS)],
        "validation": table[table["year"] == VALIDATION_YEAR],
        "test": table[table.index >= TEST_START],
    }


def grid_settings() -> list[dict]:
    keys = list(GRID)
    return [dict(zip(keys, values)) for values in itertools.product(*GRID.values())]


def gradient_boosting(kind: str, **settings):
    common = dict(max_iter=300, l2_regularization=1.0, random_state=SEED, **settings)
    if kind == "classifier":
        return HistGradientBoostingClassifier(**common)
    return HistGradientBoostingRegressor(**common)


def linear(kind: str):
    """Plain linear models need complete, scaled inputs: fill gaps with the median, then scale."""
    final = LogisticRegression(max_iter=2000) if kind == "classifier" else Ridge(alpha=1.0)
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), final)


def choose_settings(make, sets: dict, target: str, score) -> dict:
    """Try every grid point: fit on train, score on validation (lower is better).
    `make(settings)` returns a new, unfitted model."""
    results = []
    for settings in grid_settings():
        model = make(settings).fit(sets["train"][FEATURES], sets["train"][target])
        results.append((score(model, sets["validation"]), settings))
    best_score, best = min(results, key=lambda r: r[0])
    log.info("%s: best settings %s (validation score %.4f)", target, best, best_score)
    return best


def conditional_rate(train: pd.DataFrame, condition_train: pd.Series, condition_eval: pd.Series,
                     target: str) -> np.ndarray:
    """Turn a yes/no rule into a probability: how often the target happened, in the
    TRAINING years, when the rule said yes (and when it said no)."""
    rates = train[target].groupby(condition_train).mean()
    fallback = train[target].mean()
    return condition_eval.map(rates).fillna(fallback).to_numpy()


def monthly(train: pd.DataFrame, target: str, frame: pd.DataFrame, how: str = "mean") -> np.ndarray:
    per_month = train.groupby("month")[target].agg(how)
    return frame["month"].map(per_month).to_numpy()


# --------------------------------------------------------------------------
# 1. Dome closure
# --------------------------------------------------------------------------
def closure_baselines(train: pd.DataFrame, frame: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        "climatology (month)": monthly(train, "closed", frame),
        "persistence (last night)": conditional_rate(
            train, train["prev_dome_closed_frac"] >= 1 / 9, frame["prev_dome_closed_frac"] >= 1 / 9, "closed"),
        "precasting (humidity before night >= 90 %)": conditional_rate(
            train, train["pre_humidity_max"] >= 90, frame["pre_humidity_max"] >= 90, "closed"),
        "forecast rule (forecast humidity >= 95 %)": conditional_rate(
            train, train["fc_rh_max"] >= 95, frame["fc_rh_max"] >= 95, "closed"),
    }


def classification_metrics(y: pd.Series, p: np.ndarray, reference_brier: float) -> dict:
    brier = brier_score_loss(y, p)
    said_closed = p >= 0.5
    return {
        "nights": len(y),
        "brier": brier,
        # Brier skill: 1 = perfect, 0 = no better than climatology, < 0 = worse.
        "brier_skill_vs_climatology": 1 - brier / reference_brier,
        "auc": roc_auc_score(y, p),
        "hit_rate": float(said_closed[y == 1].mean()),  # closed nights we warned about
        "false_alarm_ratio": float((y[said_closed] == 0).mean()) if said_closed.any() else np.nan,
    }


def train_closure(sets: dict, day1: pd.DataFrame) -> tuple[dict, list[dict], pd.DataFrame]:
    target = "closed"
    data = {k: v.dropna(subset=[target]) for k, v in sets.items()}

    def score(model, frame):
        return brier_score_loss(frame[target], model.predict_proba(frame[FEATURES])[:, 1])

    settings = choose_settings(lambda st: gradient_boosting("classifier", **st), data, target, score)
    fit_on = pd.concat([data["train"], data["validation"]])  # final fit uses 2017-2023
    # name -> (model, inputs it uses)
    models = {
        "gradient boosting": (gradient_boosting("classifier", **settings), FEATURES),
        "logistic regression": (linear("classifier"), FEATURES),
        "gradient boosting, forecast only": (gradient_boosting("classifier", **settings), FORECAST_ONLY),
    }
    for model, inputs in models.values():
        model.fit(fit_on[inputs], fit_on[target])

    rows = []
    for source, frame in [("forecast archive", data["test"]), ("24 h old forecast", day1.dropna(subset=[target]))]:
        frame = frame[frame.index >= TEST_START]
        y = frame[target]
        reference = closure_baselines(fit_on, frame)
        clim_brier = brier_score_loss(y, reference["climatology (month)"])
        for name, p in reference.items():
            rows.append({"inputs": source, "method": name, "kind": "baseline"} | classification_metrics(y, p, clim_brier))
        for name, (model, inputs) in models.items():
            p = model.predict_proba(frame[inputs])[:, 1]
            rows.append({"inputs": source, "method": name, "kind": "model"} | classification_metrics(y, p, clim_brier))

    # Hours closed (used by forecast 3): regression with the same inputs and settings.
    hours_target = "dome_closed_h"
    hours = gradient_boosting("regressor", **settings).fit(fit_on[FEATURES], fit_on[hours_target])
    # Forecast-only twins, used by the live forecast before the 2-hour station window is complete
    # (in the afternoon the station readings "just before the night" do not exist yet).
    hours_forecast_only = gradient_boosting("regressor", **settings).fit(fit_on[FORECAST_ONLY], fit_on[hours_target])
    classifier = models["gradient boosting"][0]
    importance = importance_table(classifier, data["test"], target, "neg_brier_score")
    joblib.dump({
        "probability": classifier, "hours": hours, "features": FEATURES,
        "probability_forecast_only": models["gradient boosting, forecast only"][0],
        "hours_forecast_only": hours_forecast_only, "forecast_only_features": FORECAST_ONLY,
    }, MODELS_DIR / "closure.joblib")
    return {"classifier": classifier, "hours": hours, "settings": settings}, rows, importance


# --------------------------------------------------------------------------
# 2. Seeing
# --------------------------------------------------------------------------
def regression_metrics(y: pd.Series, pred: np.ndarray, reference_rmse: float) -> dict:
    rmse = root_mean_squared_error(y, pred)
    return {
        "nights": len(y),
        "rmse": rmse,
        "mae": mean_absolute_error(y, pred),
        # Skill: share of the baseline's error removed. 0 = same as climatology.
        "rmse_skill_vs_climatology": 1 - rmse / reference_rmse,
    }


def seeing_baselines(train: pd.DataFrame, frame: pd.DataFrame) -> dict[str, np.ndarray]:
    climatology = monthly(train, "seeing_median", frame, how="median")
    # Persistence needs last night's value; when the monitor did not measure, fall back to climatology.
    persistence = frame["prev_seeing_median"].fillna(pd.Series(climatology, index=frame.index)).to_numpy()
    return {"climatology (month)": climatology, "persistence (last night)": persistence}


def log_target(model):
    """Fit on log(seeing) and return seeing. The error of seeing grows with its value;
    on a log scale a 0.6->0.7" miss and a 1.2->1.4" miss weigh the same."""
    return TransformedTargetRegressor(regressor=model, func=np.log, inverse_func=np.exp)


def train_seeing(sets: dict, day1: pd.DataFrame) -> tuple[TransformedTargetRegressor, list[dict], pd.DataFrame]:
    target = "seeing_median"
    data = {k: v.dropna(subset=[target]) for k, v in sets.items()}

    def score(model, frame):
        return root_mean_squared_error(frame[target], model.predict(frame[FEATURES]))

    settings = choose_settings(lambda st: log_target(gradient_boosting("regressor", **st)), data, target, score)
    fit_on = pd.concat([data["train"], data["validation"]])
    models = {
        "gradient boosting": (log_target(gradient_boosting("regressor", **settings)), FEATURES),
        "linear regression": (log_target(linear("regressor")), FEATURES),
        "gradient boosting, forecast only": (log_target(gradient_boosting("regressor", **settings)), FORECAST_ONLY),
    }
    for model, inputs in models.values():
        model.fit(fit_on[inputs], fit_on[target])

    rows = []
    for source, frame in [("forecast archive", data["test"]), ("24 h old forecast", day1.dropna(subset=[target]))]:
        frame = frame[frame.index >= TEST_START]
        y = frame[target]
        reference = seeing_baselines(fit_on, frame)
        clim_rmse = root_mean_squared_error(y, reference["climatology (month)"])
        for name, pred in reference.items():
            rows.append({"inputs": source, "method": name, "kind": "baseline"} | regression_metrics(y, pred, clim_rmse))
        for name, (model, inputs) in models.items():
            rows.append({"inputs": source, "method": name, "kind": "model"}
                        | regression_metrics(y, model.predict(frame[inputs]), clim_rmse))

    model = models["gradient boosting"][0]
    importance = importance_table(model, data["test"], target, "neg_root_mean_squared_error")
    joblib.dump({"model": model, "features": FEATURES,
                 "model_forecast_only": models["gradient boosting, forecast only"][0],
                 "forecast_only_features": FORECAST_ONLY}, MODELS_DIR / "seeing.joblib")
    return model, rows, importance


# --------------------------------------------------------------------------
# 3. Hours lost to weather (WHT)
# --------------------------------------------------------------------------
def train_lost_hours(table: pd.DataFrame, closure: dict, nights: pd.DataFrame) -> tuple[LinearRegression, list[dict]]:
    """Convert predicted closure hours into WHT hours lost with a 2-number calibration.

    Why not a model trained directly on the WHT hours? Only 3 years combine a
    forecast archive and a reliable WHT log (about 1,000 nights). A gradient
    boosting model would overfit them. Instead, forecast 1 (trained on the
    reliable, sensor-based closure label) does the hard part, and one number
    learns how the WHT books it: `lost = b * predicted_closed_hours`. The line
    goes through zero (no closure predicted, no hours lost): on the calibration
    years a free intercept added ~0.6 h to every clear night and made the
    typical error worse (MAE 1.66 h against 1.30 h).

    The predicted closure hours for the calibration years come from models that
    did NOT see that year ("out of fold"), otherwise the line would be fitted on
    over-confident predictions.
    """
    target = "wht_weather_lost_h"
    data = table.dropna(subset=[target, "dome_closed_h"]).copy()
    hours_model = closure["hours"]

    # Out-of-fold predictions for the calibration years (leave one year out, 2017-2023).
    fit_pool = data[data["year"].isin([*TRAIN_YEARS, VALIDATION_YEAR])]
    data["pred_closed_h"] = np.nan
    for year in WHT_FIT_YEARS:
        others = fit_pool[fit_pool["year"] != year]
        model = clone(hours_model).fit(others[FEATURES], others["dome_closed_h"])
        rows = data["year"] == year
        data.loc[rows, "pred_closed_h"] = model.predict(data.loc[rows, FEATURES])
    later = data.index >= TEST_START  # the final model never saw these years
    data.loc[later, "pred_closed_h"] = hours_model.predict(data.loc[later, FEATURES])
    data["pred_closed_h"] = data["pred_closed_h"].clip(lower=0)

    fit = data[data["year"].isin(WHT_FIT_YEARS)]
    line = LinearRegression(fit_intercept=False).fit(fit[["pred_closed_h"]], fit[target])
    log.info("WHT calibration: lost = %.2f * predicted closed hours", line.coef_[0])

    long_history = nights[nights.index.year.isin(WHT_CLIMATOLOGY_YEARS) & (nights["wht_has_accounting"] == True)]
    long_history = long_history.assign(
        wht_weather_lost_h=long_history["wht_weather_lost_h"].clip(upper=long_history["wht_night_h"]))

    rows = []
    for label, years in [("reliable test year (2026)", WHT_TEST_YEARS),
                         ("suspect years 2024-2025 (comparison only)", [2024, 2025])]:
        frame = data[data["year"].isin(years)]
        y = frame[target]
        climatology = monthly(long_history, target, frame)
        persistence = frame["prev_wht_weather_lost_h"].fillna(pd.Series(climatology, index=frame.index)).to_numpy()
        model = line.predict(frame[["pred_closed_h"]]).clip(0, frame["wht_night_h"])
        clim_rmse = root_mean_squared_error(y, climatology)
        for name, kind, pred in [("climatology (month, 2010-2018)", "baseline", climatology),
                                 ("persistence (last night)", "baseline", persistence),
                                 ("calibrated closure forecast", "model", model)]:
            rows.append({"inputs": label, "method": name, "kind": kind} | regression_metrics(y, pred, clim_rmse))
    joblib.dump({"line": line}, MODELS_DIR / "lost_hours.joblib")
    return line, rows


# --------------------------------------------------------------------------
def importance_table(model, frame: pd.DataFrame, target: str, scoring: str) -> pd.DataFrame:
    """Permutation importance on the TEST years: shuffle one input at a time and
    measure how much worse the model gets. Bigger drop = more important input."""
    frame = frame.dropna(subset=[target])
    result = permutation_importance(model, frame[FEATURES], frame[target], scoring=scoring,
                                    n_repeats=10, random_state=SEED)
    return (pd.DataFrame({"feature": FEATURES, "importance": result.importances_mean, "std": result.importances_std})
            .sort_values("importance", ascending=False))


def predictions_table(table: pd.DataFrame, closure: dict, seeing: TransformedTargetRegressor, line: LinearRegression) -> pd.DataFrame:
    out = table[["year", "month", "closed", "dome_closed_h", "seeing_median", "wht_weather_lost_h"]].copy()
    out["p_closed"] = closure["classifier"].predict_proba(table[FEATURES])[:, 1]
    out["pred_closed_h"] = closure["hours"].predict(table[FEATURES]).clip(min=0)
    out["pred_seeing"] = seeing.predict(table[FEATURES])
    out["pred_lost_h"] = line.predict(out[["pred_closed_h"]]).clip(min=0)
    out["split"] = np.where(out.index >= TEST_START, "test",
                            np.where(out["year"] == VALIDATION_YEAR, "validation", "train"))
    return out


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "train.log"), logging.StreamHandler(sys.stdout)],
    )
    table = pd.read_parquet(config.PROCESSED_DIR / "model_table.parquet")
    day1 = pd.read_parquet(config.PROCESSED_DIR / "model_table_day1.parquet")
    nights = pd.read_parquet(config.PROCESSED_DIR / "nights.parquet")
    sets = split(table)
    log.info("nights: train %d, validation %d, test %d", *(len(v) for v in sets.values()))

    closure, closure_rows, closure_importance = train_closure(sets, day1)
    seeing, seeing_rows, seeing_importance = train_seeing(sets, day1)
    line, lost_rows = train_lost_hours(table, closure, nights)

    pd.DataFrame(closure_rows).to_csv(RESULTS_DIR / "closure_metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(seeing_rows).to_csv(RESULTS_DIR / "seeing_metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(lost_rows).to_csv(RESULTS_DIR / "lost_hours_metrics.csv", index=False, float_format="%.4f")
    closure_importance.to_csv(RESULTS_DIR / "closure_importance.csv", index=False, float_format="%.5f")
    seeing_importance.to_csv(RESULTS_DIR / "seeing_importance.csv", index=False, float_format="%.5f")
    (RESULTS_DIR / "settings.json").write_text(json.dumps({
        "closure": closure["settings"],
        "lost_hours_slope": round(float(line.coef_[0]), 3),
        "train_years": [min(TRAIN_YEARS), max(TRAIN_YEARS)], "validation_year": VALIDATION_YEAR,
        "test_from": str(TEST_START.date()),
    }, indent=2))

    predictions_table(table, closure, seeing, line).to_parquet(config.PROCESSED_DIR / "predictions.parquet")
    for name, rows in [("closure", closure_rows), ("seeing", seeing_rows), ("lost hours", lost_rows)]:
        frame = pd.DataFrame(rows)
        log.info("%s\n%s", name, frame.drop(columns="kind").to_string(index=False, float_format="%.3f"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
