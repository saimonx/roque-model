"""Tests for the modelling inputs and the evaluation helpers.

The most dangerous bug in forecasting is a "leak": using information that was
not available yet. These tests pin down the time windows.
"""

import numpy as np
import pandas as pd

from roque_forecast import features, train
from roque_forecast.sources import open_meteo


def test_open_meteo_parse_removes_day1_suffix_and_empty_hours():
    payload = {"hourly": {"time": ["2025-03-01T00:00", "2025-03-01T01:00"]}}
    for v in open_meteo.VARIABLES:
        payload["hourly"][f"{v}_previous_day1"] = [1.0, None]
    df = open_meteo.parse(payload)
    assert list(df.columns) == ["time_utc", *open_meteo.VARIABLES]
    assert len(df) == 1  # the hour with no values at all is dropped
    assert str(df["time_utc"].dt.tz) == "UTC"


def test_nightly_forecast_uses_only_dark_hours_and_wind_components():
    hours = pd.date_range("2025-03-01 00:00", "2025-03-02 23:00", freq="h", tz="UTC")
    hourly = pd.DataFrame({"time_utc": hours})
    for v in open_meteo.VARIABLES:
        hourly[v] = 1.0
    hourly["wind_speed_10m"] = 2.0
    hourly["wind_direction_10m"] = 90.0  # wind FROM the east -> blows west -> u < 0
    hourly["temperature_2m"], hourly["dew_point_2m"] = 5.0, 2.0
    hourly.loc[hourly["time_utc"].dt.hour == 14, "relative_humidity_2m"] = 100.0  # daytime: ignored

    nights = features.nightly_forecast(hourly)
    night = nights.loc[pd.Timestamp("2025-03-01")]
    assert night["fc_rh_max"] == 1.0
    assert np.isclose(night["fc_wind_u"], -2.0) and np.isclose(night["fc_wind_v"], 0.0, atol=1e-9)
    assert night["fc_dew_spread_min"] == 3.0


def test_pre_night_observations_stop_at_the_start_of_the_night():
    start = pd.Timestamp("2025-03-01 20:00", tz="UTC")
    starts = pd.Series([start], index=pd.DatetimeIndex([pd.Timestamp("2025-03-01")], name="night"))
    minutes = pd.DataFrame({"time_utc": pd.date_range(start - pd.Timedelta(hours=3), start + pd.Timedelta(hours=1),
                                                      freq="min", tz="UTC")})
    # 10 % three hours before, 50 % in the last two hours, 99 % once the night has started
    minutes["humidity_pct"] = np.where(minutes["time_utc"] < start - pd.Timedelta(hours=2), 10.0,
                                       np.where(minutes["time_utc"] < start, 50.0, 99.0))
    minutes["wind_speed_ms"], minutes["pressure_hpa"] = 3.0, 772.0
    pre = features.pre_night_observations(minutes, starts).iloc[0]
    assert pre["pre_humidity_max"] == 50.0  # nothing from after the start, nothing older than 2 h
    assert pre["pre_humidity_mean"] == 50.0


def test_persistence_is_last_calendar_night_not_last_row():
    index = pd.DatetimeIndex(["2025-03-01", "2025-03-03"], name="night")  # 2 March is missing
    nights = pd.DataFrame({
        "dome_closed_frac": [1.0, 0.0], "dome_closed_h": [9.0, 0.0], "night_length_h": [9.0, 9.0],
        "seeing_median": [0.8, 0.9], "wht_weather_lost_h": [9.0, 0.0], "wht_night_h": [9.0, 9.0],
        "wht_has_accounting": [True, True],
    }, index=index)
    out = features.add_labels_and_persistence(pd.DataFrame(index=index), nights)
    assert np.isnan(out.loc["2025-03-03", "prev_dome_closed_frac"])  # not 1.0 from 1 March
    assert out.loc["2025-03-01", "closed"] == 1.0


def test_conditional_rate_turns_a_rule_into_training_frequencies():
    trained = pd.DataFrame({"closed": [1, 1, 0, 0, 0, 0]})
    rule = pd.Series([True, True, True, False, False, False])
    p = train.conditional_rate(trained, rule, pd.Series([True, False]), "closed")
    assert np.allclose(p, [2 / 3, 0.0])


def test_split_keeps_test_years_out_of_training():
    index = pd.date_range("2017-01-01", "2026-06-01", freq="30D")
    table = pd.DataFrame({"year": index.year}, index=index)
    sets = train.split(table)
    assert sets["train"].index.max() < pd.Timestamp("2023-01-01")
    assert (sets["validation"]["year"] == 2023).all()
    assert sets["test"].index.min() >= train.TEST_START
