"""ING R2D2 DIMM seeing monitor — our label for "how sharp were the stars".

Public page: https://astro.ing.iac.es/seeing/
Coverage: since 2018-09-19, one value every 15-35 s while it is dark.

"Seeing" is the blur caused by atmospheric turbulence, measured in
arcseconds ("). Smaller is better: 0.5" is excellent, 1.5" is poor.

Format: an HTML `<pre>` block where lines are separated by `<br>`:
    Date Time (UT)      R2D2 seeing (")
    ---------------------------------------
    2026-09-01 00:00:11    0.9213

Note: `date2` is exclusive (date1=2026-09-01, date2=2026-09-30 stops at
2026-09-29 23:59). To get a whole month, pass the first day of next month.
"""

import re
from datetime import date
from pathlib import Path

import pandas as pd

from roque_forecast.polite_http import PoliteSession

DATA_URL = "https://astro.ing.iac.es/seeing/r2d2_data.php"

# One measurement line: "YYYY-MM-DD HH:MM:SS   0.9213"
LINE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+([0-9.]+)")


def download_range(session: PoliteSession, date1: date, date2: date, dest: Path) -> Path:
    """Download seeing values from `date1` (inclusive) to `date2` (exclusive)."""
    params = {"date1": date1.isoformat(), "date2": date2.isoformat(), "submit": "Submit"}
    response = session.get(DATA_URL, params=params)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(response.text, encoding="utf-8")
    return dest


def parse_text(text: str) -> pd.DataFrame:
    """Turn the raw page into a table with columns time_utc and seeing_arcsec."""
    rows = LINE.findall(text)
    df = pd.DataFrame(rows, columns=["time_utc", "seeing_arcsec"])
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    df["seeing_arcsec"] = df["seeing_arcsec"].astype(float)
    return df


def parse(path: Path) -> pd.DataFrame:
    return parse_text(path.read_text(encoding="utf-8"))
