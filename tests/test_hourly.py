"""Hour-by-hour tables: the mid-hour forecast, the hourly labels and tonight's hours."""

import numpy as np
import pandas as pd

from roque_forecast import hourly, tonight
from roque_forecast.sources import open_meteo


def test_hour_forecast_is_the_value_at_mid_hour():
    hours = pd.date_range("2025-03-01 20:00", periods=3, freq="h", tz="UTC")
    raw = pd.DataFrame({"time_utc": hours})
    for v in open_meteo.VARIABLES:
        raw[v] = 0.0
    raw["relative_humidity_2m"] = [80.0, 90.0, 100.0]
    raw["precipitation"] = [0.0, 0.4, 0.0]  # rain accumulated in the hour ENDING at each time
    out = hourly.hour_forecast(raw)
    assert out.loc[hours[0], "h_rh"] == 85.0  # 20:00-21:00 -> mean of 20:00 and 21:00
    assert out.loc[hours[0], "h_precip"] == 0.4  # the rain reported at 21:00 fell during 20-21
    assert np.isnan(out.loc[hours[2], "h_rh"])  # no value after the last hour


def test_hour_slots_labels_closure_and_wind_per_hour():
    t = pd.date_range("2025-03-01 21:00", periods=120, freq="min", tz="UTC")
    minutes = pd.DataFrame({"time_utc": t, "is_night": True, "night": pd.Timestamp("2025-03-01").date(),
                            "dome_closed": [False] * 60 + [True] * 60, "humidity_pct": 50.0,
                            "wind_speed_ms": [5.0] * 119 + [30.0]})
    slots = hourly.hour_slots(minutes).set_index("hour")
    assert slots["closed"].tolist() == [0.0, 1.0]
    assert slots["windy"].tolist() == [0.0, 1.0]  # one minute at or above 22.2 m/s is enough
    assert slots["hour_of_night"].tolist() == [0, 1]


def test_tonight_hours_keep_only_mostly_dark_hours():
    window = {"start": pd.Timestamp("2026-10-28 19:50", tz="UTC"), "end": pd.Timestamp("2026-10-29 06:02", tz="UTC")}
    hours = tonight.tonight_hours(window)
    # 19:00 has only 10 dark minutes and 06:00 only 2: both are left out.
    assert hours["hour"].iloc[0] == pd.Timestamp("2026-10-28 20:00", tz="UTC")
    assert hours["hour"].iloc[-1] == pd.Timestamp("2026-10-29 05:00", tz="UTC")
    assert (hours["dark_minutes"] >= hourly.MIN_DARK_MINUTES).all()


def test_combined_probability_is_humidity_or_wind():
    p = hourly.combine(np.array([0.3, 0.0, 0.5]), np.array([0.0, 0.2, 0.5]))
    assert np.allclose(p, [0.3, 0.2, 0.75])  # never below either reason; 1 - 0.5 x 0.5 = 0.75
