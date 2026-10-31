"""Settings search helpers: the grid and the one-setting-at-a-time tables."""

import numpy as np
import pandas as pd

from roque_forecast import compare


def test_grid_tries_every_combination():
    combos = compare.grid({"a": [1, 2], "b": ["x", "y", "z"]})
    assert len(combos) == 6 and {"a": 2, "b": "z"} in combos


def test_one_at_a_time_keeps_the_other_settings_at_the_chosen_ones():
    rows = []
    options = {**compare.TREE_MODELS["gradient_boosting"], "trees": compare.TREES}
    for lr in options["learning_rate"]:
        for trees in compare.TREES:
            rows.append({"learning_rate": lr, "max_leaf_nodes": 15, "min_samples_leaf": 50, "l2_regularization": 0.0,
                         "trees": trees, "brier": lr + trees / 1e4, "right": 0.9})
    rows.sort(key=lambda r: r["brier"])            # best first, as the search returns them
    table = compare.one_at_a_time(rows, options)
    assert [r["value"] for r in table["learning_rate"]] == options["learning_rate"]
    assert all(r["value"] in compare.TREES for r in table["trees"])
    assert len(table["max_leaf_nodes"]) == 1      # only the chosen value was tried here


def test_growing_a_forest_in_steps_gives_the_same_forest():
    # The search adds trees to one forest (warm_start); it must equal growing them all at once.
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(rng.normal(size=(300, 3)), columns=["a", "b", "c"])
    frame["closed"] = (frame["a"] + rng.normal(size=300) > 0).astype(int)
    frame.loc[::7, "b"] = np.nan                   # gaps, filled with the median in this variant
    learn, check, inputs = frame[:200], frame[200:], ["a", "b", "c"]
    settings = {"min_samples_leaf": 3, "max_features": "sqrt", "criterion": "gini", "missing": "median"}
    steps = dict(compare.staged("random_forest", settings, learn, check, inputs))
    direct = compare.build("random_forest", settings, compare.TREES[1]).fit(learn[inputs], learn["closed"])
    assert np.allclose(steps[compare.TREES[1]], direct.predict_proba(check[inputs])[:, 1])
