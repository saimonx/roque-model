"""TNG (Telescopio Nazionale Galileo) public weather API.

Public site: https://tngweb.tng.iac.es/weather (a web app that calls the API below).
Endpoints used by that public app (checked 27 Oct 2026):
- /api/meteo/weather          -> current value of every sensor, including dust
                                 counts by particle size (0.3 to 10 microns)
- /api/meteo/weather/<var>    -> last 24 h, one point per minute, for:
                                 dust, humidity, pressure, seeing, temperature,
                                 uv, winddir, windspeed
- /api/meteo/downtime         -> hours lost (weather / technical) per day, last year

Because the 24 h series keep one-minute resolution, downloading them once a
day gives a full-resolution history without polling every few minutes.
"""

import json

import pandas as pd

from roque_forecast.polite_http import PoliteSession

API_URL = "https://tngweb.tng.iac.es/api/meteo"

SERIES_VARS = [
    "dust", "humidity", "pressure", "seeing", "temperature", "uv", "winddir", "windspeed",
]


def fetch_current(session: PoliteSession) -> bytes:
    return session.get(f"{API_URL}/weather").content


def fetch_series(session: PoliteSession, var: str) -> bytes:
    return session.get(f"{API_URL}/weather/{var}").content


def fetch_downtime(session: PoliteSession) -> bytes:
    return session.get(f"{API_URL}/downtime").content


def parse_series(raw: bytes | str, var: str) -> pd.DataFrame:
    """{"units", "series": [{"data": [[epoch_ms, value], ...]}]} -> tidy table.

    Missing values come as null (e.g. seeing during daytime) and are dropped.
    """
    payload = json.loads(raw)
    points = [p for serie in payload["series"] for p in serie["data"]]
    df = pd.DataFrame(points, columns=["time_utc", var]).dropna()
    df["time_utc"] = pd.to_datetime(df["time_utc"], unit="ms", utc=True)
    return df


def parse_current(raw: bytes | str) -> list[dict]:
    """Current snapshot -> list of {name, value, units, level, epoch_ms, outdated}.

    We keep `epoch` (milliseconds since 1970, always UTC) rather than the
    `timestamp` text, whose time zone the API does not state.
    """
    payload = json.loads(raw)
    return [
        {
            "name": name,
            "value": item.get("value"),
            "units": item.get("units"),
            "level": item.get("level"),
            "epoch_ms": item.get("epoch"),
            "outdated": item.get("outdated"),
        }
        for name, item in payload.items()
        if isinstance(item, dict)
    ]

