"""GTC weather station (atmosportal) — live data from the 10.4 m telescope itself.

Public site: https://atmosportal.gtc.iac.es/
Two kinds of data:

1. Time series (`graphics/<var>_month.php`): JSON list of {"x": epoch_ms, "y": value},
   one point every ~11 s, but ONLY the last 30 days. Not used: the GTC station is not stored.

2. Live panel (the table on the home page): current value of each sensor,
   including some that have no time series (rain flag, indoor/outdoor PM10 dust,
   external seeing monitors, water vapour). Each row is coloured by the site
   (green / yellow / ...), which tells us when the GTC considers a value a
   warning (the real alarm thresholds are not published anywhere).
"""

import json
import re

import pandas as pd
from bs4 import BeautifulSoup

from roque_forecast.polite_http import PoliteSession

BASE_URL = "https://atmosportal.gtc.iac.es"

# Variables with a downloadable time series (names as used by the site).
SERIES_VARS = [
    "humidity", "temperature", "dewpoint", "pressure", "solarrad", "winspeed", "windpeak",
]

# Row colours seen on the panel. Unknown colours are kept as their hex code.
STATUS_BY_COLOR = {"#58FA58": "ok", "#F4FA58": "warning"}


def fetch_series(session: PoliteSession, var: str, window: str = "month") -> bytes:
    """Download one variable. `window` is 'month', '7day' or '24hour'."""
    response = session.get(f"{BASE_URL}/graphics/{var}_{window}.php")
    return response.content


def parse_series(raw: bytes | str, var: str) -> pd.DataFrame:
    """JSON [{x, y}, ...] -> table with columns time_utc and <var>."""
    points = json.loads(raw)
    df = pd.DataFrame(points).rename(columns={"x": "time_utc", "y": var})
    # epoch milliseconds -> real UTC timestamps
    df["time_utc"] = pd.to_datetime(df["time_utc"], unit="ms", utc=True)
    return df


def fetch_home_page(session: PoliteSession) -> str:
    return session.get(f"{BASE_URL}/").text


def _split_value(text: str) -> tuple[float | str | None, str | None]:
    """'89.7 %' -> (89.7, '%'); ' False' -> ('False', None); '' -> (None, None)."""
    text = text.strip()
    if not text:
        return None, None
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(.*)", text)
    if match:
        return float(match.group(1)), (match.group(2) or None)
    return text, None


def parse_panel(html: str) -> dict:
    """Read the live panel into {"station_time_utc": ..., "rows": [...]}.

    Each row: name, value, unit, age (for external sensors, e.g. '0.1 h'),
    color (raw hex) and status ('ok' / 'warning' / hex if unknown / None).
    """
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.find(id="panel")
    if panel is None:
        raise ValueError("GTC home page has no #panel element (page layout changed?)")

    result: dict = {"station_time_utc": None, "rows": []}
    header = panel.find("th")
    stamp = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UT", header.get_text() if header else "")
    if stamp:
        result["station_time_utc"] = stamp.group(1)

    section = "gtc"
    for tr in panel.find_all("tr"):
        th = tr.find("th")
        if th is not None:
            # Section headers: "GTC Values ..." and "Externals"
            if "Externals" in th.get_text():
                section = "external"
            continue
        cells = tr.find_all("td")
        if len(cells) != 3:
            continue
        value, unit = _split_value(cells[2].get_text())
        color = tr.get("bgcolor")
        result["rows"].append({
            "section": section,
            "name": cells[0].get_text(strip=True),
            "value": value,
            "unit": unit,
            "age": cells[1].get_text(strip=True) or None,
            "color": color,
            "status": STATUS_BY_COLOR.get(color.upper(), color) if color else None,
        })
    return result


def panel_html_only(html: str) -> str:
    """Keep only the panel's HTML (a few KB) so we can re-parse it later if needed."""
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.find(id="panel")
    return str(panel) if panel else ""
