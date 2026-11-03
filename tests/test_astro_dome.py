"""Tests for the astronomical night and the dome-closure rule."""

import pandas as pd

from roque_forecast import astro, dome


def test_astronomical_night_matches_ing_twilight_times():
    # ING page for the night of 1 Sep 2026: evening twilight 20:55 UT, morning 05:29 UT.
    start = pd.Timestamp("2026-09-01 12:00", tz="UTC")
    minutes = pd.Series(pd.date_range(start, periods=24 * 60, freq="min"))
    dark = minutes[astro.is_astronomical_night(minutes)]
    assert abs(dark.iloc[0] - pd.Timestamp("2026-09-01 20:55", tz="UTC")) <= pd.Timedelta("1min")
    assert abs(dark.iloc[-1] - pd.Timestamp("2026-09-02 05:29", tz="UTC")) <= pd.Timedelta("1min")


def test_night_label_uses_the_evening_date():
    times = pd.Series(pd.to_datetime(["2026-09-01 21:00", "2026-09-02 05:00"], utc=True))
    assert list(astro.night_label(times).astype(str)) == ["2026-09-01", "2026-09-01"]


def test_dome_closes_at_90_and_reopens_after_20_minutes_below():
    times = pd.date_range("2026-01-01 20:00", periods=60, freq="min", tz="UTC")
    humidity = [50] * 5 + [95] * 3 + [80] * 52  # high at minutes 5, 6, 7
    minutes = pd.DataFrame({"time_utc": times, "humidity_pct": humidity})
    closed = dome.closed_by_humidity(minutes)
    assert not closed.iloc[4]
    assert closed.iloc[5:27].all()  # closed from minute 5 until 19 min after the last high value
    assert not closed.iloc[27]  # 20 minutes below 90 % -> reopen


def test_dome_rule_works_with_5_minute_sampling():
    # Early NOT years are sampled every 5 minutes: the rule must use time, not rows.
    times = pd.date_range("2000-01-01 20:00", periods=12, freq="5min", tz="UTC")
    humidity = [50, 95] + [80] * 10
    closed = dome.closed_by_humidity(pd.DataFrame({"time_utc": times, "humidity_pct": humidity}))
    assert closed.iloc[1:5].all()  # 20:05 (high) until 20:20
    assert not closed.iloc[5]  # 20:25 = 20 min after the last high value


def test_circular_mean_of_wind_direction():
    from roque_forecast.build_tables import circular_mean_deg

    # 350 and 10 degrees are both northerly: the mean must be ~0, not 180.
    mean = circular_mean_deg(pd.Series([350.0, 10.0]))
    assert min(mean, 360 - mean) < 1e-6
    assert abs(circular_mean_deg(pd.Series([80.0, 100.0])) - 90) < 1e-6


def test_wind_closes_and_reopens_after_20_minutes():
    times = pd.date_range("2025-01-01 22:00", periods=40, freq="min", tz="UTC")
    wind = [5.0] * 5 + [25.0] + [5.0] * 34
    minutes = pd.DataFrame({"time_utc": times, "wind_speed_ms": wind})
    closed = dome.closed_by_wind(minutes)
    assert not closed.iloc[4] and closed.iloc[5] and closed.iloc[24] and not closed.iloc[25]


def test_ice_needs_freezing_after_saturated_air():
    times = pd.date_range("2025-01-01 00:00", periods=4, freq="6h", tz="UTC")
    minutes = pd.DataFrame({"time_utc": times, "humidity_pct": [95.0, 60.0, 60.0, 60.0],
                            "temp_c": [2.0, -1.0, -1.0, 3.0]})
    ice = dome.closed_by_ice(minutes)
    assert ice.tolist() == [False, True, True, False]  # frozen and wet within 24 h; then it thaws
