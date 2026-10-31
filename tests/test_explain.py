"""The per-hour breakdown: starting point + one amount per group = the model's probability."""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from roque_forecast import explain


def test_amounts_add_up_and_an_unused_group_gets_zero():
    rng = np.random.default_rng(0)
    inputs = ["h_rh", "fc_rh_mean", "prev_dome_closed_frac", "doy_sin"]
    x = pd.DataFrame(rng.uniform(0, 1, size=(400, 4)), columns=inputs)
    y = (x["h_rh"] > 0.6).astype(int)          # only this hour's humidity matters
    model = HistGradientBoostingClassifier(max_iter=50).fit(x, y)
    rows = x.head(5)
    base, parts = explain.contributions(model, inputs, rows, x.sample(100, random_state=1))
    total = base + parts.sum(axis=1)
    assert np.allclose(total, model.predict_proba(rows)[:, 1])
    assert set(parts.columns) == {"humidity", "night_forecast", "last_night", "calendar"}  # only groups with inputs
    assert parts["humidity"].abs().mean() > 10 * parts.drop(columns="humidity").abs().to_numpy().mean()
