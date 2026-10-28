"""Reconstruct when the dome had to be closed, from the humidity series.

NOT rule (public): close when relative humidity reaches 90 %; reopen only after
humidity has stayed below 90 % for 20 minutes in a row.

A neat way to compute this without a loop: at minute t the dome is closed if
**any** minute in the window [t-19 min, t] had humidity >= 90 %.
- While humidity is high, the window always contains a high value -> closed.
- After the last high value at t0, the window still contains it until t0+19 -> closed.
- At t0+20 the window is [t0+1, t0+20], all below 90 % -> open again.
That is exactly "20 minutes below 90 %". In pandas this is a rolling maximum.

The full closure label (`closed`) adds the two other reasons that close a dome on
the Roque and that the station can measure:
- **Wind:** gusts above 80 km/h (22.2 m/s), the INT closing limit (ING observer alert
  procedure); reopen after 20 minutes below it, like humidity.
- **Ice:** at or below 0 degC after the air was saturated (humidity >= 90 %) at any
  moment in the previous 24 hours: rime and ice on the dome mechanisms. Calibrated
  against the Liverpool Telescope reports of 2017-2022: it adds 29 nights to the
  humidity rule, and on 26 of them the LT also lost at least half the night.
"""

import pandas as pd

HUMIDITY_LIMIT_PCT = 90.0
REOPEN_AFTER = "20min"
WIND_LIMIT_MS = 22.2  # 80 km/h, INT dome-closing limit for gusts
ICE_TEMP_C = 0.0
ICE_WET_WINDOW = "24h"


def closed_by_humidity(minutes: pd.DataFrame) -> pd.Series:
    """Boolean series (indexed like `minutes`): True when the rule says "closed".

    `minutes` needs columns time_utc (rounded to whole minutes) and humidity_pct,
    sorted by time. Missing humidity counts as "not high", so gaps are handled
    with a coverage check later.
    """
    high = (minutes["humidity_pct"] >= HUMIDITY_LIMIT_PCT).astype(int)
    high.index = pd.DatetimeIndex(minutes["time_utc"])
    # Time-based window (t-20 min, t] = the current minute and the 19 before it.
    # Using time instead of "20 rows" keeps the rule right when rows are missing.
    closed = high.rolling(REOPEN_AFTER).max().astype(bool)
    closed.index = minutes.index
    return closed


def _rolling_any(flag: pd.Series, times: pd.Series, window: str) -> pd.Series:
    """True at minute t if `flag` was true at any minute in (t - window, t] (time-based)."""
    f = flag.astype(int)
    f.index = pd.DatetimeIndex(times)
    out = f.rolling(window).max().astype(bool)
    out.index = flag.index
    return out


def closed_by_wind(minutes: pd.DataFrame, wind_limit_ms: float = WIND_LIMIT_MS) -> pd.Series:
    """Closed while gusts reach the limit, and for 20 minutes after the last one."""
    return _rolling_any(minutes["wind_speed_ms"] >= wind_limit_ms, minutes["time_utc"], REOPEN_AFTER)


def closed_by_ice(minutes: pd.DataFrame) -> pd.Series:
    """Freezing (<= 0 degC) after the air was saturated in the last 24 hours."""
    wet_recently = _rolling_any(minutes["humidity_pct"] >= HUMIDITY_LIMIT_PCT, minutes["time_utc"], ICE_WET_WINDOW)
    return (minutes["temp_c"] <= ICE_TEMP_C) & wet_recently


def closed(minutes: pd.DataFrame) -> pd.Series:
    """The closure label of the project: humidity OR wind OR ice.

    `minutes` needs time_utc, humidity_pct, wind_speed_ms and temp_c, sorted by time,
    with enough history before the night (24 h) for the ice rule."""
    return closed_by_humidity(minutes) | closed_by_wind(minutes) | closed_by_ice(minutes)
