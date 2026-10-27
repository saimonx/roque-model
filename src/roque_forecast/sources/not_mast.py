"""NOT (Nordic Optical Telescope) weather archive — our main historical source.

Public page: https://www.not.iac.es/weather/archive/met/index.php
Coverage: 1997 to today, about one measurement per minute.

How the download works (found by reading the public form):
1. We send the form as a GET request with `submit=Raw Data`.
2. The server answers with an HTML page containing a link such as
   `/temp/NOTMetData1793125455.gz` (a temporary gzip file).
3. We download that gzip file. Inside there is a tab-separated text table.

Important finding (27 Oct 2026): whatever sensors we tick, "Raw Data"
always returns the same 6 columns: time, humidity, pressure, temperature,
wind direction and wind speed. Rain and dome flags are NOT included, so the
dome-closure rule has to be rebuilt from humidity (and wind) ourselves.
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from roque_forecast.polite_http import PoliteSession

BASE_URL = "https://www.not.iac.es"
FORM_URL = f"{BASE_URL}/weather/archive/met/index.php"

# The sensors offered by the form. We still send them (it is what a person
# would tick), even though the raw export currently returns a fixed set.
SENSORS = [
    "DateTimeUT", "HumidityPercent", "PressureHPA", "TempInAirDegC",
    "WindDirectionDeg", "WindSpeedMS", "WindSpeedFilteredMS",
]

# Raw column name -> tidy column name used in the rest of the project.
COLUMN_NAMES = {
    "DateTimeUT": "time_utc",
    "Humidity": "humidity_pct",
    "PressureHPA": "pressure_hpa",
    "TempInAirDegC": "temp_c",
    "WindDirectionDeg": "wind_dir_deg",
    "WindSpeedMS": "wind_speed_ms",
}


def build_form_params(start: datetime, end: datetime) -> list[tuple[str, str]]:
    """Return the form fields for a time range, exactly as the web form sends them.

    A list of pairs (not a dict) is used because `sensors[]` appears many times.
    """
    params = [
        ("actionflag", "process"),
        ("day1", f"{start.day:02d}"), ("month1", f"{start.month:02d}"),
        ("year1", str(start.year)), ("hour1", f"{start.hour:02d}"),
        ("min1", f"{start.minute:02d}"),
        ("day2", f"{end.day:02d}"), ("month2", f"{end.month:02d}"),
        ("year2", str(end.year)), ("hour2", f"{end.hour:02d}"),
        ("min2", f"{end.minute:02d}"),
    ]
    params += [("sensors[]", name) for name in SENSORS]
    params.append(("submit", "Raw Data"))
    return params


def find_download_link(html: str) -> str | None:
    """Extract the temporary gzip link from the server's answer page."""
    match = re.search(r"/temp/NOTMetData\d+\.gz", html)
    return BASE_URL + match.group(0) if match else None


def download_range(session: PoliteSession, start: datetime, end: datetime, dest: Path) -> Path:
    """Download [start, end] (UTC) and save the gzip file, untouched, to `dest`."""
    answer = session.get(FORM_URL, params=build_form_params(start, end))
    link = find_download_link(answer.text)
    if link is None:
        raise RuntimeError(f"NOT archive returned no data link for {start} - {end}")
    gz = session.get(link)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(gz.content)
    return dest


def parse(path: Path) -> pd.DataFrame:
    """Read a downloaded NOT file into a tidy table (one row per minute).

    pandas opens `.gz` files directly, no need to unzip first.
    """
    df = pd.read_csv(path, sep="\t")
    df = df.rename(columns=COLUMN_NAMES)
    # Times are UT (= UTC). Making them timezone-aware avoids mistakes later
    # when we mix them with local (Canary Islands) time.
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df
