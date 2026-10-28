"""Checks of the closure label: TNG downtime parsing and the year-by-year table."""

import json

import pandas as pd

from roque_forecast import validate
from roque_forecast.sources import tng


def test_tng_downtime_gives_one_row_per_night():
    raw = json.dumps({"series": [
        {"name": "Weather", "data": [[1761609600000, 11.1], [1761696000000, 0.0]]},
        {"name": "Technical", "data": [[1761609600000, 0.0], [1761696000000, 0.5]]},
    ]})
    out = tng.parse_downtime(raw)
    assert list(out.columns) == ["weather_h", "technical_h"]
    assert out.index[0] == pd.Timestamp("2025-10-28")  # the day the night starts
    assert out.loc["2025-10-29", "technical_h"] == 0.5


def test_lost_vs_label_counts_fully_closed_nights():
    nights = pd.date_range("2025-01-01", periods=4)
    j = pd.DataFrame({"dark_h": 10.0, "closed_h": [10.0, 0.0, 9.5, 2.0], "lost": [9.0, 0.0, 2.0, 3.0]}, index=nights)
    out = validate.lost_vs_label(j, "lost")
    assert out["label_closed_nights"] == 2          # 10 h and 9.5 h are >= 90 % of the night
    assert out["label_closed_also_lost"] == 0.5     # the telescope lost only one of them


def test_by_year_leaves_gaps_where_a_source_has_no_data():
    result = {"gtc": [{"year": 2024, "exposing_when_label_closed": 0.01}],
              "liverpool": {"by_year": {2023: 0.8, 2024: 0.7}}, "tng": None, "wht": [{"year": 2023, "correlation": 0.6}]}
    rows = {r["year"]: r for r in validate.by_year(result)}
    assert rows[2023] == {"year": 2023, "gtc": None, "liverpool": 0.8, "tng": None, "wht": 0.6}
    assert rows[2024]["gtc"] == 0.01 and rows[2024]["wht"] is None
