"""Why does the model give this percentage? A plain breakdown for each hour of tonight.

The closure model uses about 30 inputs. One by one they mean little to a reader, so
they are put into ten groups that anyone can follow. The forecast for this hour is
split by variable, so the page shows how much each one counts:

    this hour's forecast humidity, wind, temperature, cloud, rain and pressure;
    the forecast for the whole night, the summit station just before the night,
    what happened last night, and the time of year / hour.

For each hour the probability is split into a starting point plus one amount per
group, so that

    probability = starting point + humidity + wind + ... + time of year / hour

**Starting point:** the model's average answer over a sample of real night hours
(2021-2023): roughly how often any night hour is closed.

**Amount of each group (Shapley values, computed exactly over the groups):** the
model is asked many "what if" questions, with each group either set to tonight's
values or taken from the sample of ordinary hours. A group's amount is the average
change it makes to the probability, over every order in which the groups could be
added. The amounts always add up exactly to the probability, and a group that the
model ignores gets zero. With ten groups there are 2^10 = 1,024 combinations: all of
them go to the model in one batch per hour, so the exact values take a few seconds
(no approximation).

Usage (from tonight.py):
    base, parts = explain.contributions(model, inputs, tonight_rows, explain.background(inputs))
"""

from math import factorial

import numpy as np
import pandas as pd

from roque_forecast import config, features, hourly

# Plain-language groups of inputs, in the order they are shown on the page.
GROUPS = {
    # This hour's forecast, one group per variable.
    "humidity": ["h_rh", "h_dew_spread"],          # dew spread = how far the air is from saturation
    "wind": ["h_wind", "h_wind_u", "h_wind_v", "h_wind_750"],
    "temperature": ["h_temp"],
    "cloud": ["h_cloud"],
    "rain": ["h_precip"],
    "pressure": ["h_pressure"],
    # The rest.
    "night_forecast": features.FORECAST_FEATURES,
    "station": features.OBSERVED_FEATURES,
    "last_night": features.PERSISTENCE_FEATURES,
    "calendar": features.CALENDAR_FEATURES + ["hour_of_night", "night_fraction"],
}
HOUR_GROUPS = ["humidity", "wind", "temperature", "cloud", "rain", "pressure"]
assert sorted(c for g in HOUR_GROUPS for c in GROUPS[g]) == sorted(
    f for f in hourly.HOUR_FEATURES if f not in ("hour_of_night", "night_fraction"))
BACKGROUND_YEARS = (2021, 2023)  # years with every input (the 750 hPa wind starts in 2021), never the test years
BACKGROUND_SIZE = 200


def background(inputs: list[str]) -> pd.DataFrame:
    """A fixed sample of real night hours: what "an ordinary hour" looks like to the model."""
    table = pd.read_parquet(config.PROCESSED_DIR / "hour_table.parquet")
    table = table[table["year"].between(*BACKGROUND_YEARS)].dropna(subset=["closed"])
    return table.sample(n=min(BACKGROUND_SIZE, len(table)), random_state=0)[inputs].astype(float).reset_index(drop=True)


def contributions(model, inputs: list[str], rows: pd.DataFrame, sample: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Starting point and the amount of each group, for every row (all in probability, 0-1)."""
    columns = {name: [inputs.index(c) for c in cols if c in inputs] for name, cols in GROUPS.items()}
    columns = {name: idx for name, idx in columns.items() if idx}
    names = list(columns)
    n, size = len(names), len(sample)
    background = sample[inputs].to_numpy(dtype=float)
    base = float(model.predict_proba(sample[inputs].astype(float))[:, 1].mean())

    # Every combination of groups as a bit mask: bit k set = group k takes tonight's values.
    masks = np.arange(2 ** n)
    has = (masks[:, None] >> np.arange(n)) & 1                       # (combinations, groups)
    weight = np.array([factorial(k) * factorial(n - k - 1) / factorial(n) for k in range(n)])

    out = []
    for values in rows[inputs].to_numpy(dtype=float):
        # One big table: the sample repeated once per combination, with the chosen groups replaced.
        batch = np.tile(background, (len(masks), 1))
        for k, name in enumerate(names):
            chosen = np.repeat(has[:, k].astype(bool), size)
            batch[np.ix_(chosen, columns[name])] = values[columns[name]]
        # value[mask]: average probability for that combination.
        value = model.predict_proba(pd.DataFrame(batch, columns=inputs))[:, 1].reshape(len(masks), size).mean(axis=1)
        amounts = {}
        for k, name in enumerate(names):
            without = masks[has[:, k] == 0]                          # combinations without group k
            others = has[without].sum(axis=1)                        # how many groups they hold
            amounts[name] = float((weight[others] * (value[without | (1 << k)] - value[without])).sum())
        out.append(amounts)
    parts = pd.DataFrame(out, index=rows.index)
    # The amounts add up to the probability of the full row (a property of Shapley values).
    assert np.allclose(base + parts.sum(axis=1), model.predict_proba(rows[inputs].astype(float))[:, 1], atol=1e-6)
    return base, parts
