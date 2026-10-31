"""ING nightly accounting — the real "hours lost to weather" for each night.

Public page: https://a.ing.iac.es/weather/archive/
Each night page shows, for the William Herschel Telescope (WHT, 4.2 m, on
the same mountain as the GTC): night length, hours lost to weather, hours
lost to technical problems, other losses and hours observed. It also shows
the Moon illumination, which strongly affects what can be observed.

The page is opened with the public "Select another night" form:
    index.php?night=YYYY-MM-DD&actionflag=showDate&submit=submit

Findings (27 Oct 2026):
- Nights with real numbers start around 2010 (2005 pages are all zeros).
- "Weather lost" can be larger than "Night" (e.g. 12:00 vs 10:10), because
  the losses are counted over a longer window than astronomical night.
  We keep the raw numbers here and decide how to cap them when modelling.
"""

import gzip
import re
from datetime import date
from pathlib import Path

from roque_forecast.polite_http import PoliteSession

NIGHT_URL = "https://a.ing.iac.es/weather/archive/index.php"


def fetch_night(session: PoliteSession, night: date) -> bytes:
    """Return the raw HTML bytes of one night (the night that starts on `night`).

    The site declares ISO-8859-1 (Latin-1); we keep raw bytes and decode when parsing.
    """
    params = {"night": night.isoformat(), "actionflag": "showDate", "submit": "submit"}
    return session.get(NIGHT_URL, params=params).content


def download_night(session: PoliteSession, night: date, dest: Path) -> Path:
    """Save the HTML page of one night, untouched, to `dest`."""
    content = fetch_night(session, night)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest


def hhmm_to_hours(text: str) -> float | None:
    """'10:30' -> 10.5 hours. Returns None for empty cells."""
    match = re.fullmatch(r"\s*(\d+):(\d{2})\s*", text)
    if not match:
        return None
    return int(match.group(1)) + int(match.group(2)) / 60


def parse_html(html: str) -> dict:
    """Extract the WHT accounting row and the Moon illumination of one night."""
    result: dict = {}

    night = re.search(r"<B>Night (\d{2})/(\d{2})/(\d{4})</B>", html)
    if night:
        day, month, year = night.groups()
        result["night"] = f"{year}-{month}-{day}"

    # Row looks like: <tr><td>WHT</td><td ...>10:10</td><td ...>10:10</td>...
    row = re.search(r"<tr><td>WHT</td>(.*?)</tr>", html, re.DOTALL)
    if row:
        cells = re.findall(r"<td[^>]*>([^<]*)", row.group(1))
        names = ["night_h", "weather_lost_h", "tech_lost_h", "other_lost_h", "observed_h"]
        for name, cell in zip(names, cells):
            result[name] = hhmm_to_hours(cell)

    moon = re.search(r"Moon illumination</th><td>\s*(\d+)%", html)
    result["moon_illumination_pct"] = int(moon.group(1)) if moon else None
    return result


def parse(path: Path) -> dict:
    """Parse a saved night page (plain `.html` or gzip-compressed `.html.gz`)."""
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return parse_html(raw.decode("latin-1"))
