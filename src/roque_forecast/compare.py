"""Why gradient boosting, and why these settings? Two searches, with RoqueModel's own data.

1. **Settings search.** Gradient boosting has a few settings (how many trees, how
   fast each one corrects, how big each tree can grow, how many real hours a rule
   needs, how much extreme rules are held back). Every combination of a grid is
   tried on three validation years (2021, 2022 and 2023), each time learning from
   the other years of 2017-2023, and the one with the lowest mean error (Brier
   score) is kept. Three years instead of one make the choice less dependent on one
   particular year. (Learning only from earlier years is not possible for 2021: the
   summit-height wind starts that year, so 2017-2020 have none of it.) The number of trees costs
   nothing extra to search: one model with the most trees is fitted and scored
   after 150, 300 and 600 trees (`staged_predict_proba`).

2. **Model comparison.** The same data, the same validation years and the same
   rule for choosing settings, for four kinds of model:
   - gradient boosting (RoqueModel),
   - random forest (many independent trees averaged; used for Roque seeing by
     Abarzuza et al. 2025),
   - logistic regression (one weighted sum of the inputs: the simplest model),
   - a small neural network (MLP).
   Each one, with its best settings, learns from 2017-2023 and is tested on
   2024-2026, which no choice has seen.

The test years are never used to choose anything. The results go to
reports/results/model_search.json; hourly.py reads the chosen settings from there.

Usage:
    .venv/bin/python -m roque_forecast.compare     # about 15 minutes
"""

import itertools
import json
import logging
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from roque_forecast import config, hourly, train

log = logging.getLogger("compare")
RESULTS = config.PROJECT_DIR / "reports" / "results" / "model_search.json"
VALIDATION_YEARS = [2021, 2022, 2023]
TEST_FROM = 2024
TREES = [150, 300, 600]
GB_GRID = {"learning_rate": [0.03, 0.1, 0.3], "max_leaf_nodes": [7, 15, 31],
           "min_samples_leaf": [20, 50, 100], "l2_regularization": [0.0, 1.0]}
OTHER_MODELS = {
    "random_forest": {"min_samples_leaf": [5, 20, 50], "max_features": ["sqrt", 0.5]},
    "logistic_regression": {"C": [0.1, 1.0, 10.0]},
    "neural_network": {"hidden_layer_sizes": [(32,), (64, 32)], "alpha": [1e-4, 1e-2]},
}


def grid(options: dict) -> list[dict]:
    return [dict(zip(options, values)) for values in itertools.product(*options.values())]


def load() -> pd.DataFrame:
    return pd.read_parquet(config.PROCESSED_DIR / "hour_table.parquet").dropna(subset=["closed"])


def folds(table: pd.DataFrame):
    """(learn, check) pairs: each validation year, learning from the other years before the test."""
    for year in VALIDATION_YEARS:
        yield table[(table["year"] < TEST_FROM) & (table["year"] != year)], table[table["year"] == year]


def scores(y: pd.Series, p: np.ndarray) -> dict:
    return {"brier": float(brier_score_loss(y, p)), "right": float(((p >= 0.5) == (y == 1)).mean()),
            "auc": float(roc_auc_score(y, p))}


# --------------------------------------------------------------------------
# 1. Gradient boosting settings
# --------------------------------------------------------------------------
def gradient_boosting(settings: dict, trees: int) -> HistGradientBoostingClassifier:
    # early_stopping=False: scikit-learn would otherwise stop adding trees by itself on
    # tables this big, and the number of trees is one of the settings being compared.
    return HistGradientBoostingClassifier(max_iter=trees, early_stopping=False, random_state=train.SEED, **settings)


def search_gradient_boosting(table: pd.DataFrame, inputs: list[str]) -> list[dict]:
    """Mean validation scores of every grid combination and number of trees."""
    rows = []
    for settings in grid(GB_GRID):
        per_trees = {n: [] for n in TREES}
        for learn, check in folds(table):
            model = gradient_boosting(settings, max(TREES)).fit(learn[inputs], learn["closed"])
            for n, p in enumerate(model.staged_predict_proba(check[inputs]), start=1):
                if n in per_trees:
                    per_trees[n].append(scores(check["closed"], p[:, 1]))
        for n, results in per_trees.items():
            rows.append({**settings, "trees": n, **{k: float(np.mean([r[k] for r in results])) for k in results[0]}})
        log.info("%s done", settings)
    return sorted(rows, key=lambda r: r["brier"])


def one_at_a_time(rows: list[dict]) -> dict:
    """For each setting, the error of every value it can take, the others fixed at the chosen ones.
    This is what the page shows to justify each setting."""
    best = rows[0]
    keys = [*GB_GRID, "trees"]
    out = {}
    for key in keys:
        same = [r for r in rows if all(r[k] == best[k] for k in keys if k != key)]
        out[key] = sorted(({"value": r[key], "brier": r["brier"], "right": r["right"]} for r in same),
                          key=lambda r: r["value"])
    return out


# --------------------------------------------------------------------------
# 2. Other kinds of model
# --------------------------------------------------------------------------
def make_other(name: str, settings: dict):
    """The other models need complete inputs (missing values filled with the median of the
    learning years); the linear and neural ones also need them on the same scale."""
    fill = SimpleImputer(strategy="median")
    if name == "random_forest":
        return make_pipeline(fill, RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=train.SEED, **settings))
    if name == "logistic_regression":
        return make_pipeline(fill, StandardScaler(), LogisticRegression(max_iter=3000, **settings))
    return make_pipeline(fill, StandardScaler(), MLPClassifier(max_iter=500, early_stopping=True,
                                                               random_state=train.SEED, **settings))


def search_other(table: pd.DataFrame, inputs: list[str], name: str) -> dict:
    results = []
    for settings in grid(OTHER_MODELS[name]):
        fold_scores = [scores(check["closed"], make_other(name, settings).fit(learn[inputs], learn["closed"])
                              .predict_proba(check[inputs])[:, 1]) for learn, check in folds(table)]
        results.append({"settings": settings, "brier": float(np.mean([s["brier"] for s in fold_scores]))})
    return min(results, key=lambda r: r["brier"])


def test(model, table: pd.DataFrame, inputs: list[str]) -> dict:
    """Learn from 2017-2023, check on 2024-2026 (never used for any choice)."""
    learn, check = table[table["year"] < TEST_FROM], table[table["year"] >= TEST_FROM]
    start = time.time()
    model.fit(learn[inputs], learn["closed"])
    seconds = time.time() - start
    return {**scores(check["closed"], model.predict_proba(check[inputs])[:, 1]), "fit_seconds": round(seconds, 1)}


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOG_DIR / "compare.log"), logging.StreamHandler(sys.stdout)])
    table = load()
    out = {"validation_years": VALIDATION_YEARS, "test_years": [TEST_FROM, int(table["year"].max())],
           "grid": {**GB_GRID, "trees": TREES}, "modes": {}}
    for mode, inputs in [("final", hourly.CLOSURE_FEATURES), ("provisional", hourly.CLOSURE_FORECAST_ONLY)]:
        rows = search_gradient_boosting(table, inputs)
        chosen = {k: rows[0][k] for k in GB_GRID}
        models = [{"name": "gradient_boosting", "settings": {**chosen, "trees": rows[0]["trees"]}, "validation_brier": rows[0]["brier"],
                   "test": test(gradient_boosting(chosen, rows[0]["trees"]), table, inputs)}]
        for name in OTHER_MODELS:
            best = search_other(table, inputs, name)
            models.append({"name": name, "settings": {k: list(v) if isinstance(v, tuple) else v for k, v in best["settings"].items()},
                           "validation_brier": best["brier"], "test": test(make_other(name, best["settings"]), table, inputs)})
            log.info("%s %s: %s", mode, name, models[-1])
        out["modes"][mode] = {"combinations": len(rows), "chosen": {**chosen, "trees": rows[0]["trees"]},
                              "top": rows[:10], "one_at_a_time": one_at_a_time(rows), "models": models}
    RESULTS.write_text(json.dumps(out, indent=1))
    log.info("written %s", RESULTS.relative_to(config.PROJECT_DIR))
    return 0


def chosen_settings(mode: str) -> tuple[dict, int] | None:
    """The settings chosen by the last search (None if it has not been run)."""
    if not RESULTS.exists():
        return None
    chosen = dict(json.loads(RESULTS.read_text())["modes"][mode]["chosen"])
    return chosen, int(chosen.pop("trees"))


if __name__ == "__main__":
    raise SystemExit(main())
