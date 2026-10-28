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


# --------------------------------------------------------------------------
# The Moon
# --------------------------------------------------------------------------
# Moonlight brightens the sky: faint targets need "dark time" (no Moon above the
# horizon), while bright targets and spectroscopy can use "bright time". The
# Moon does not change the dome or the seeing, so the models do not use it; the
# page shows it because it is part of planning a night.
#
# Low-precision formulas from the Astronomical Almanac ("Low-precision formulae
# for the Moon", section D): about 0.3 degrees in position, plenty to say whether
# the Moon is up and how much of it is lit (checked against the PyEphem library
# over 400 times in 2024-2026: altitude within 0.26 degrees, lit fraction within 0.2 %).


def _julian_day(times_utc) -> np.ndarray:
    return pd.DatetimeIndex(times_utc).to_julian_date().to_numpy()


def _sin(deg):
    return np.sin(np.radians(deg))


def _cos(deg):
    return np.cos(np.radians(deg))


def moon_ecliptic(times_utc) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Moon's geocentric ecliptic longitude and latitude, and horizontal parallax (degrees)."""
    t = (_julian_day(times_utc) - 2451545.0) / 36525.0
    lon = (218.32 + 481267.881 * t
           + 6.29 * _sin(135.0 + 477198.87 * t) - 1.27 * _sin(259.3 - 413335.36 * t)
           + 0.66 * _sin(235.7 + 890534.22 * t) + 0.21 * _sin(269.9 + 954397.74 * t)
           - 0.19 * _sin(357.5 + 35999.05 * t) - 0.11 * _sin(186.5 + 966404.03 * t))
    lat = (5.13 * _sin(93.3 + 483202.02 * t) + 0.28 * _sin(228.2 + 960400.89 * t)
           - 0.28 * _sin(318.3 + 6003.15 * t) - 0.17 * _sin(217.6 - 407332.21 * t))
    parallax = (0.9508 + 0.0518 * _cos(135.0 + 477198.87 * t) + 0.0095 * _cos(259.3 - 413335.36 * t)
                + 0.0078 * _cos(235.7 + 890534.22 * t) + 0.0028 * _cos(269.9 + 954397.74 * t))
    return np.mod(lon, 360), lat, parallax


def sun_ecliptic_longitude(times_utc) -> np.ndarray:
    """Sun's apparent ecliptic longitude (degrees), accurate to ~0.01 degrees."""
    d = _julian_day(times_utc) - 2451545.0
    mean_long = 280.460 + 0.9856474 * d
    anomaly = 357.528 + 0.9856003 * d
    return np.mod(mean_long + 1.915 * _sin(anomaly) + 0.020 * _sin(2 * anomaly), 360)


def moon_altitude_deg(times_utc, lat_deg: float = config.SITE_LAT, lon_deg: float = config.SITE_LON) -> np.ndarray:
    """Altitude of the Moon's centre seen from the observatory (degrees, no refraction)."""
    lon, lat, parallax = moon_ecliptic(times_utc)
    t = (_julian_day(times_utc) - 2451545.0) / 36525.0
    obliquity = 23.439 - 0.013 * t
    # Ecliptic -> equatorial coordinates (right ascension, declination).
    x = _cos(lat) * _cos(lon)
    y = _cos(obliquity) * _cos(lat) * _sin(lon) - _sin(obliquity) * _sin(lat)
    z = _sin(obliquity) * _cos(lat) * _sin(lon) + _cos(obliquity) * _sin(lat)
    right_ascension = np.degrees(np.arctan2(y, x))
    declination = np.degrees(np.arcsin(z))
    # Local sidereal time -> hour angle -> altitude.
    d = _julian_day(times_utc) - 2451545.0
    sidereal = np.mod(280.46061837 + 360.98564736629 * d + lon_deg, 360)
    hour_angle = sidereal - right_ascension
    altitude = np.degrees(np.arcsin(_sin(lat_deg) * _sin(declination)
                                    + _cos(lat_deg) * _cos(declination) * _cos(hour_angle)))
    # The Moon is close enough for our position on the Earth to matter (~1 degree).
    return altitude - parallax * _cos(altitude)


def moon_illumination(times_utc) -> tuple[np.ndarray, np.ndarray]:
    """Lit fraction of the Moon (0 new - 1 full) and whether it is waxing (growing)."""
    lon, lat, _ = moon_ecliptic(times_utc)
    elongation = lon - sun_ecliptic_longitude(times_utc)  # angle Sun-Earth-Moon along the ecliptic
    cos_angle = _cos(lat) * _cos(elongation)
    return (1 - cos_angle) / 2, _sin(elongation) > 0


def moon_during(start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Moon facts for one night: lit fraction, hours above the horizon, dark hours without it."""
    minutes = pd.date_range(start, end, freq="min", inclusive="left")
    up = moon_altitude_deg(minutes) > 0
    lit, waxing = moon_illumination(pd.DatetimeIndex([start + (end - start) / 2]))
    changes = np.flatnonzero(np.diff(up.astype(int)))
    return {
        "illumination": round(float(lit[0]), 3),
        "waxing": bool(waxing[0]),
        "up_h": round(float(up.sum()) / 60, 2),
        "dark_h": round(float((~up).sum()) / 60, 2),
        "up_at_start": bool(up[0]),
        # Times the Moon rises or sets during the night (UTC), if it does.
        "rises_utc": [minutes[i + 1].isoformat().replace("+00:00", "Z") for i in changes if not up[i]],
        "sets_utc": [minutes[i + 1].isoformat().replace("+00:00", "Z") for i in changes if up[i]],
    }
