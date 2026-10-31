"""Why does the model give this percentage? A plain breakdown for each hour of tonight.

The closure model uses about 30 inputs. One by one they mean little to a reader, so
they are put into five groups that anyone can follow:

    the forecast for this hour, the forecast for the whole night, the summit station
    just before the night, what happened last night, and the time of year / hour.

For each hour the probability is split into a starting point plus one amount per
group, so that

    probability = starting point + forecast for this hour + forecast for the night
                  + station before the night + last night + time of year / hour

**Starting point:** the model's average answer over a sample of real night hours
(2021-2023): roughly how often any night hour is closed.

**Amount of each group (Shapley values, computed exactly over the groups):** the
model is asked many "what if" questions, with each group either set to tonight's
values or taken from the sample of ordinary hours. A group's amount is the average
change it makes to the probability, over every order in which the groups could be
added. The amounts always add up exactly to the probability, and a group that the
model ignores gets zero. With five groups there are only 2^5 = 32 combinations, so
the exact values are cheap to compute (no approximation).

Usage (from tonight.py):
    base, parts = explain.contributions(model, inputs, tonight_rows, explain.background(inputs))
"""

from itertools import combinations
from math import factorial

import numpy as np
import pandas as pd

from roque_forecast import config, features, hourly

# Plain-language groups of inputs, in the order they are shown on the page.
GROUPS = {
    "hour_forecast": [f for f in hourly.HOUR_FEATURES if f not in ("hour_of_night", "night_fraction")],
    "night_forecast": features.FORECAST_FEATURES,
    "station": features.OBSERVED_FEATURES,
    "last_night": features.PERSISTENCE_FEATURES,
    "calendar": features.CALENDAR_FEATURES + ["hour_of_night", "night_fraction"],
}
BACKGROUND_YEARS = (2021, 2023)  # years with every input (the 750 hPa wind starts in 2021), never the test years
BACKGROUND_SIZE = 300


def background(inputs: list[str]) -> pd.DataFrame:
    """A fixed sample of real night hours: what "an ordinary hour" looks like to the model."""
    table = pd.read_parquet(config.PROCESSED_DIR / "hour_table.parquet")
    table = table[table["year"].between(*BACKGROUND_YEARS)].dropna(subset=["closed"])
    return table.sample(n=min(BACKGROUND_SIZE, len(table)), random_state=0)[inputs].astype(float).reset_index(drop=True)


def contributions(model, inputs: list[str], rows: pd.DataFrame, sample: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Starting point and the amount of each group, for every row (all in probability, 0-1)."""
    groups = {name: [c for c in cols if c in inputs] for name, cols in GROUPS.items()}
    groups = {name: cols for name, cols in groups.items() if cols}
    names = list(groups)
    n = len(names)
    base = float(model.predict_proba(sample)[:, 1].mean())

    out = []
    for _, row in rows[inputs].astype(float).iterrows():
        # value[S]: average probability when the groups in S take tonight's values
        # and the rest come from the ordinary hours of the sample.
        value = {}
        for size in range(n + 1):
            for subset in combinations(names, size):
                frame = sample.copy()
                for name in subset:
                    frame[groups[name]] = row[groups[name]].to_numpy()
                value[frozenset(subset)] = float(model.predict_proba(frame)[:, 1].mean())
        amounts = {}
        for name in names:
            others = [g for g in names if g != name]
            total = 0.0
            for size in range(n):
                weight = factorial(size) * factorial(n - size - 1) / factorial(n)
                for subset in combinations(others, size):
                    s = frozenset(subset)
                    total += weight * (value[s | {name}] - value[s])
            amounts[name] = total
        out.append(amounts)
    parts = pd.DataFrame(out, index=rows.index)
    # The amounts add up to the probability of the full row (a property of Shapley values).
    assert np.allclose(base + parts.sum(axis=1), model.predict_proba(rows[inputs].astype(float))[:, 1], atol=1e-6)
    return base, parts
