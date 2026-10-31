"""Reconstruct when the dome had to be closed, from the humidity series.

NOT rule (public): close when relative humidity reaches 90 %; reopen only after
humidity has stayed below 90 % for 20 minutes in a row.

A neat way to compute this without a loop: at minute t the dome is closed if
**any** minute in the window [t-19 min, t] had humidity >= 90 %.
- While humidity is high, the window always contains a high value -> closed.
- After the last high value at t0, the window still contains it until t0+19 -> closed.
- At t0+20 the window is [t0+1, t0+20], all below 90 % -> open again.
That is exactly "20 minutes below 90 %". In pandas this is a rolling maximum.

Wind also closes domes, but the NOT/GTC wind limits are not published in the
archive; `wind_limit_ms` is optional and off by default.
"""

import pandas as pd

HUMIDITY_LIMIT_PCT = 90.0
REOPEN_AFTER = "20min"


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


def closed_by_wind(minutes: pd.DataFrame, wind_limit_ms: float | None) -> pd.Series:
    if wind_limit_ms is None:
        return pd.Series(False, index=minutes.index)
    return minutes["wind_speed_ms"] >= wind_limit_ms
