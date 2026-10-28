"""Hour-by-hour closure forecast: the mid-hour forecast, the hourly label and tonight's hours."""

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


def test_hour_slots_label_closed_for_humidity_or_wind():
    t = pd.date_range("2025-03-01 21:00", periods=180, freq="min", tz="UTC")
    humidity = [50.0] * 60 + [95.0] * 60 + [50.0] * 60
    wind = [5.0] * 150 + [30.0] * 30
    minutes = pd.DataFrame({"time_utc": t, "is_night": True, "night": pd.Timestamp("2025-03-01").date(),
                            "humidity_pct": humidity, "wind_speed_ms": wind, "temp_c": 5.0})
    slots = hourly.hour_slots(hourly.label_minutes(minutes)).set_index("hour")
    # 21h open; 22h humid; 23h closed by wind from 23:30 (+ the 20-minute tail of humidity).
    assert slots["closed"].tolist() == [0.0, 1.0, 1.0]
    assert slots["hour_of_night"].tolist() == [0, 1, 2]


def test_raw_forecast_reads_the_three_rules():
    frame = pd.DataFrame({"h_rh": [95.0, 50.0, 50.0], "h_wind": [1.0, 1.0, 1.0], "h_wind_750": [5.0, 25.0, 5.0],
                          "h_temp": [5.0, 5.0, -2.0]})
    assert hourly.raw_literal(frame).tolist() == [True, True, False]  # freezing alone (dry) does not close


def test_tonight_hours_keep_only_mostly_dark_hours():
    window = {"start": pd.Timestamp("2026-10-28 19:50", tz="UTC"), "end": pd.Timestamp("2026-10-29 06:02", tz="UTC")}
    hours = tonight.tonight_hours(window)
    # 19:00 has only 10 dark minutes and 06:00 only 2: both are left out.
    assert hours["hour"].iloc[0] == pd.Timestamp("2026-10-28 20:00", tz="UTC")
    assert hours["hour"].iloc[-1] == pd.Timestamp("2026-10-29 05:00", tz="UTC")
    assert (hours["dark_minutes"] >= hourly.MIN_DARK_MINUTES).all()
