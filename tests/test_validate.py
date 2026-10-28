"""Check of the closure label against the Liverpool Telescope reports."""

import pandas as pd

from roque_forecast import validate


def test_compare_counts_fully_closed_nights():
    nights = pd.date_range("2025-01-01", periods=4)
    j = pd.DataFrame({"dark_h": 10.0, "closed_h": [10.0, 0.0, 9.5, 2.0], "weather_h": [9.0, 0.0, 2.0, 3.0]},
                     index=nights)
    out = validate.compare(j)
    assert out["label_closed_nights"] == 2       # 10 h and 9.5 h are >= 90 % of the night
    assert out["label_closed_lt_lost"] == 0.5    # the LT lost only one of them


def test_compare_without_fully_closed_nights():
    j = pd.DataFrame({"dark_h": 10.0, "closed_h": [0.0, 1.0], "weather_h": [0.0, 2.0]},
                     index=pd.date_range("2025-01-01", periods=2))
    assert validate.compare(j)["label_closed_lt_lost"] is None
