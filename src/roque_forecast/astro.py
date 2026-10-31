"""Sun position and "observing night" for the observatory.

To say "this minute belongs to the night of 1 Sep 2026" we need to know
whether the Sun is below the horizon. Astronomers use **astronomical night**:
Sun more than 18 degrees below the horizon (sky fully dark). The ING
accounting uses exactly this window ("Eve. twilight" to "Mor. twilight").

We compute the Sun's altitude with the NOAA solar-position formulas
(https://gml.noaa.gov/grad/solcalc/calcdetails.html). They are accurate to
about 0.01 degrees, far better than we need, and run on millions of
timestamps at once thanks to numpy (no loop in Python).
"""

import numpy as np
import pandas as pd

from roque_forecast import config

ASTRONOMICAL_TWILIGHT_DEG = -18.0


def sun_altitude_deg(
    times_utc: pd.DatetimeIndex | pd.Series,
    lat_deg: float = config.SITE_LAT,
    lon_deg: float = config.SITE_LON,
) -> np.ndarray:
    """Altitude of the Sun's centre above the horizon, in degrees (no refraction)."""
    t = pd.DatetimeIndex(times_utc)
    # Julian century: time since 1 Jan 2000 12:00 UT in units of 36,525 days.
    julian_day = t.to_julian_date().to_numpy()
    jc = (julian_day - 2451545.0) / 36525.0

    # Sun's mean longitude and anomaly (degrees), orbit eccentricity.
    mean_long = np.mod(280.46646 + jc * (36000.76983 + jc * 0.0003032), 360)
    mean_anom = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    m = np.radians(mean_anom)
    centre = (
        np.sin(m) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
        + np.sin(2 * m) * (0.019993 - 0.000101 * jc)
        + np.sin(3 * m) * 0.000289
    )
    true_long = mean_long + centre
    apparent_long = true_long - 0.00569 - 0.00478 * np.sin(np.radians(125.04 - 1934.136 * jc))

    # Tilt of the Earth's axis (obliquity), corrected.
    obliq_mean = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    obliq = obliq_mean + 0.00256 * np.cos(np.radians(125.04 - 1934.136 * jc))

    # Declination: how far north/south of the equator the Sun is.
    declination = np.degrees(
        np.arcsin(np.sin(np.radians(obliq)) * np.sin(np.radians(apparent_long)))
    )

    # Equation of time (minutes): difference between clock time and solar time.
    y = np.tan(np.radians(obliq / 2)) ** 2
    l0 = np.radians(mean_long)
    eq_time = 4 * np.degrees(
        y * np.sin(2 * l0)
        - 2 * ecc * np.sin(m)
        + 4 * ecc * y * np.sin(m) * np.cos(2 * l0)
        - 0.5 * y * y * np.sin(4 * l0)
        - 1.25 * ecc * ecc * np.sin(2 * m)
    )

    # Hour angle: how far (in degrees) the Sun is from the local meridian.
    minutes_of_day = (t.hour * 60 + t.minute + t.second / 60).to_numpy()
    true_solar_time = np.mod(minutes_of_day + eq_time + 4 * lon_deg, 1440)
    hour_angle = np.where(true_solar_time < 0, true_solar_time / 4 + 180, true_solar_time / 4 - 180)

    lat = np.radians(lat_deg)
    dec = np.radians(declination)
    cos_zenith = np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.cos(np.radians(hour_angle))
    return 90 - np.degrees(np.arccos(np.clip(cos_zenith, -1, 1)))


def night_label(times_utc: pd.Series) -> pd.Series:
    """Label each timestamp with the date on which its night STARTS.

    On La Palma local midnight is around 01:00 UTC, so subtracting 12 h maps the
    whole night (evening of day D to morning of day D+1) onto day D, like the ING.
    """
    return (times_utc - pd.Timedelta(hours=12)).dt.date


def is_astronomical_night(times_utc: pd.Series) -> np.ndarray:
    return sun_altitude_deg(times_utc) < ASTRONOMICAL_TWILIGHT_DEG
