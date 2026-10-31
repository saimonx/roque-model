"""Settings search helpers: the grid and the one-setting-at-a-time tables."""

from roque_forecast import compare


def test_grid_tries_every_combination():
    combos = compare.grid({"a": [1, 2], "b": ["x", "y", "z"]})
    assert len(combos) == 6 and {"a": 2, "b": "z"} in combos


def test_one_at_a_time_keeps_the_other_settings_at_the_chosen_ones():
    rows = []
    for lr in compare.GB_GRID["learning_rate"]:
        for trees in compare.TREES:
            rows.append({"learning_rate": lr, "max_leaf_nodes": 15, "min_samples_leaf": 50, "l2_regularization": 0.0,
                         "trees": trees, "brier": lr + trees / 1e4, "right": 0.9})
    rows.sort(key=lambda r: r["brier"])            # best first, as the search returns them
    table = compare.one_at_a_time(rows)
    assert [r["value"] for r in table["learning_rate"]] == compare.GB_GRID["learning_rate"]
    assert all(r["value"] in compare.TREES for r in table["trees"])
    assert len(table["max_leaf_nodes"]) == 1      # only the chosen value was tried here
