"""Check of the closure label against the Liverpool Telescope reports."""

import pandas as pd

from roque_forecast import validate


def test_compare_counts_lost_nights_on_both_sides():
    nights = pd.date_range("2025-01-01", periods=4)
    j = pd.DataFrame({"dark_h": 10.0, "closed_h": [10.0, 0.0, 6.0, 0.0], "weather_h": [9.0, 0.0, 2.0, 7.0]},
                     index=nights)
    out = validate.compare(j)
    assert out["label_lost_nights"] == 2 and out["lt_lost_nights"] == 2 and out["both_lost_nights"] == 1
    assert out["agree"] == 0.5                  # nights 1 and 2 agree, 3 and 4 do not
    assert out["label_lost_lt_lost"] == 0.5     # the LT lost one of the two nights the label lost
    assert out["label_open_nights"] == 2        # nights 2 and 4: no closed minute
    assert out["label_open_lt_kept"] == 0.5     # the LT lost night 4 anyway (cloud, dust...)


def test_compare_without_lost_nights():
    j = pd.DataFrame({"dark_h": 10.0, "closed_h": [0.0, 1.0], "weather_h": [0.0, 2.0]},
                     index=pd.date_range("2025-01-01", periods=2))
    assert validate.compare(j)["label_lost_lt_lost"] is None
