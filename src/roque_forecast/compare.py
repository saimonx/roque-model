"""Which model, and which settings? Searches with RoqueModel's own data.

1. **Settings search, as wide for each tree model.** Gradient boosting and random
   forest are the two strongest kinds of model here, so both get the same treatment:
   every combination of a wide grid of settings is tried on three validation years
   (2021, 2022 and 2023), each time learning from the other years of 2017-2023, and
   the one with the lowest mean error (Brier score) is kept. Three years instead of
   one make the choice less dependent on one particular year. (Learning only from
   earlier years is not possible for 2021: the summit-height wind starts that year,
   so 2017-2020 have none of it.) The number of trees costs nothing extra to search:
   gradient boosting is scored after 150, 300 and 600 trees of one model
   (`staged_predict_proba`); a random forest grows 150 trees, is scored, gets 150
   more, and so on (`warm_start`).

2. **Model comparison.** Two simpler kinds of model, each with its own (smaller)
   grid, the same data, the same validation years and the same rule:
   - logistic regression (one weighted sum of the inputs: the simplest model),
   - a small neural network (MLP).
   Every kind of model, with its best settings, learns from 2017-2023 and is tested
   on 2024-2026, which no choice of settings has seen.

3. **RoqueModel's model.** The tree model with the lowest validation error, added
   over both versions (final and provisional). When the two tree models are within
   2 % of each other there, the validation years cannot tell them apart, and the one
   with the lower error on the test years is chosen. That happened (gradient boosting
   0.1450, random forest 0.1464: 0.9 % apart), so RoqueModel is the random forest,
   better on the test in both versions (and the model of Abarzuza et al. 2025 for
   Roque seeing). Because this one choice looked at the test years, the random
   forest's test scores may be slightly optimistic; no setting was chosen with them.
   The forecasts logged night by night from now on (tonight.py) are a test that no
   choice has seen.

The results go to reports/results/model_search.json; hourly.py reads RoqueModel's
model and settings from there.

Usage:
    .venv/bin/python -m roque_forecast.compare     # about two and a half hours
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
# The wide grids of the two tree models (the number of trees is searched on top, see TREES).
TREE_MODELS = {
    "gradient_boosting": {
        "learning_rate": [0.03, 0.1, 0.3],        # how much each tree corrects
        "max_leaf_nodes": [7, 15, 31],            # how big each tree can grow
        "min_samples_leaf": [20, 50, 100],        # real hours each rule needs at least
        "l2_regularization": [0.0, 1.0],          # how much extreme rules are held back
    },
    "random_forest": {
        "min_samples_leaf": [1, 3, 5, 10, 20, 50],  # real hours each rule needs at least
        "max_features": ["sqrt", 0.25, 0.5, 1.0],   # share of the inputs each split may look at
        "criterion": ["gini", "log_loss"],          # how a split is judged
        "missing": ["native", "median"],            # gaps kept as gaps, or filled with the median
    },
}
# Validation errors closer than this (2 %) cannot tell two models apart.
TIE = 0.02
OTHER_MODELS = {
    "logistic_regression": {"C": [0.01, 0.1, 1.0, 10.0]},
    "neural_network": {"hidden_layer_sizes": [(32,), (64,), (64, 32)], "alpha": [1e-4, 1e-3, 1e-2]},
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
# 1. The two tree models and their wide settings search
# --------------------------------------------------------------------------
def build(name: str, settings: dict, trees: int):
    """A tree model with these settings, ready to fit (RoqueModel is built here too)."""
    if name == "gradient_boosting":
        # early_stopping=False: scikit-learn would otherwise stop adding trees by itself on
        # tables this big, and the number of trees is one of the settings being compared.
        return HistGradientBoostingClassifier(max_iter=trees, early_stopping=False, random_state=train.SEED, **settings)
    forest = RandomForestClassifier(n_estimators=trees, n_jobs=-1, random_state=train.SEED,
                                    **{k: v for k, v in settings.items() if k != "missing"})
    # "native": scikit-learn's trees send missing values down the better side of each split.
    return make_pipeline(SimpleImputer(strategy="median"), forest) if settings["missing"] == "median" else forest


def staged(name: str, settings: dict, learn: pd.DataFrame, check: pd.DataFrame, inputs: list[str]):
    """(trees, probabilities for the check hours) after each number of trees in TREES."""
    if name == "gradient_boosting":
        model = build(name, settings, max(TREES)).fit(learn[inputs], learn["closed"])
        for n, p in enumerate(model.staged_predict_proba(check[inputs]), start=1):
            if n in TREES:
                yield n, p[:, 1]
        return
    x_learn, x_check = learn[inputs], check[inputs]
    if settings["missing"] == "median":
        fill = SimpleImputer(strategy="median").fit(x_learn)
        x_learn, x_check = fill.transform(x_learn), fill.transform(x_check)
    # warm_start: each fit keeps the trees already grown and only adds the new ones, which
    # gives the same forest as growing all of them at once (same random seed).
    forest = build(name, {**settings, "missing": "native"}, TREES[0]).set_params(warm_start=True)
    for n in TREES:
        forest.set_params(n_estimators=n).fit(x_learn, learn["closed"])
        yield n, forest.predict_proba(x_check)[:, 1]


def search_tree_model(table: pd.DataFrame, inputs: list[str], name: str) -> list[dict]:
    """Mean validation scores of every grid combination and number of trees, best first."""
    rows = []
    for settings in grid(TREE_MODELS[name]):
        per_trees = {n: [] for n in TREES}
        for learn, check in folds(table):
            for n, p in staged(name, settings, learn, check, inputs):
                per_trees[n].append(scores(check["closed"], p))
        for n, results in per_trees.items():
            rows.append({**settings, "trees": n, **{k: float(np.mean([r[k] for r in results])) for k in results[0]}})
        log.info("%s %s done", name, settings)
    return sorted(rows, key=lambda r: r["brier"])


def one_at_a_time(rows: list[dict], options: dict) -> dict:
    """For each setting, the error of every value it can take, the others fixed at the chosen ones,
    in the order of the grid. This is what the page shows to justify each setting."""
    best = rows[0]
    out = {}
    for key, values in options.items():
        same = [r for r in rows if all(r[k] == best[k] for k in options if k != key)]
        out[key] = sorted(({"value": r[key], "brier": r["brier"], "right": r["right"]} for r in same),
                          key=lambda r: values.index(r["value"]))
    return out


# --------------------------------------------------------------------------
# 2. The simpler models
# --------------------------------------------------------------------------
def make_other(name: str, settings: dict):
    """They need complete inputs (missing values filled with the median of the learning
    years) on the same scale."""
    fill = SimpleImputer(strategy="median")
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
    return min(results, key=lambda r: r["brier"]) | {"combinations": len(results)}


def test(model, table: pd.DataFrame, inputs: list[str]) -> dict:
    """Learn from 2017-2023, check on 2024-2026 (never used to choose any setting)."""
    learn, check = table[table["year"] < TEST_FROM], table[table["year"] >= TEST_FROM]
    start = time.time()
    model.fit(learn[inputs], learn["closed"])
    seconds = time.time() - start
    return {**scores(check["closed"], model.predict_proba(check[inputs])[:, 1]), "fit_seconds": round(seconds, 1)}


def plain(settings: dict) -> dict:
    """JSON-friendly settings (tuples become lists)."""
    return {k: list(v) if isinstance(v, tuple) else v for k, v in settings.items()}


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOG_DIR / "compare.log"), logging.StreamHandler(sys.stdout)])
    table = load()
    out = {"validation_years": VALIDATION_YEARS, "test_years": [TEST_FROM, int(table["year"].max())],
           "grids": {name: {**g, "trees": TREES} for name, g in TREE_MODELS.items()}, "modes": {}}
    for mode, inputs in [("final", hourly.CLOSURE_FEATURES), ("provisional", hourly.CLOSURE_FORECAST_ONLY)]:
        models, searches = [], {}
        for name, options in TREE_MODELS.items():
            rows = search_tree_model(table, inputs, name)
            chosen = {k: rows[0][k] for k in options}
            searches[name] = {"combinations": len(rows), "chosen": {**chosen, "trees": rows[0]["trees"]},
                              "top": rows[:10], "one_at_a_time": one_at_a_time(rows, {**options, "trees": TREES})}
            models.append({"name": name, "settings": searches[name]["chosen"], "combinations": len(rows),
                           "validation_brier": rows[0]["brier"],
                           "test": test(build(name, chosen, rows[0]["trees"]), table, inputs)})
            log.info("%s %s: %s", mode, name, models[-1])
        for name in OTHER_MODELS:
            best = search_other(table, inputs, name)
            models.append({"name": name, "settings": plain(best["settings"]), "combinations": best["combinations"],
                           "validation_brier": best["brier"], "test": test(make_other(name, best["settings"]), table, inputs)})
            log.info("%s %s: %s", mode, name, models[-1])
        out["modes"][mode] = {"models": models, "searches": searches}
    choose_roquemodel(out)
    RESULTS.write_text(json.dumps(out, indent=1))
    log.info("RoqueModel = %s; written %s", out["roquemodel"], RESULTS.relative_to(config.PROJECT_DIR))
    return 0


def choose_roquemodel(out: dict) -> None:
    """RoqueModel's model (see the module docstring, point 3), with the numbers behind the choice."""
    def total(name, score):
        return sum(next(m for m in out["modes"][mode]["models"] if m["name"] == name)[score]
                   for mode in out["modes"])
    validation = {name: total(name, "validation_brier") for name in TREE_MODELS}
    test_error = {name: sum(next(m for m in out["modes"][mode]["models"] if m["name"] == name)["test"]["brier"]
                            for mode in out["modes"]) for name in TREE_MODELS}
    best, worst = sorted(validation.values())
    tie = (worst - best) / best < TIE
    out["choice"] = {"validation": validation, "test": test_error, "tie": tie, "tie_margin": TIE,
                     "gap_pct": round((worst - best) / best * 100, 1)}
    out["roquemodel"] = min(test_error if tie else validation, key=(test_error if tie else validation).get)


def chosen_settings(mode: str) -> tuple[str, dict, int] | None:
    """RoqueModel's model and settings from the last search (None if it has not been run)."""
    if not RESULTS.exists():
        return None
    results = json.loads(RESULTS.read_text())
    if "roquemodel" not in results:
        return None
    name = results["roquemodel"]
    chosen = dict(results["modes"][mode]["searches"][name]["chosen"])
    return name, chosen, int(chosen.pop("trees"))


if __name__ == "__main__":
    raise SystemExit(main())
