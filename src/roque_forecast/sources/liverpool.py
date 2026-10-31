"""Liverpool Telescope night reports: what happened every night, by a robotic telescope on the Roque.

The Liverpool Telescope (LT, 2 m, robotic, Liverpool John Moores University)
publishes one report per night since 2004 (https://telescope.livjm.ac.uk/Reports/):
hours spent observing, hours lost to weather, hours lost to technical problems and a
short comment ("High humidity.", "Ice risk on enclosure mechanisms.", "High calima
levels.", "Photometric with good seeing.").

Why it is useful here:
- It is filled in the same way every night by a robotic system, with no years booked
  wrongly (unlike the WHT log, see the EDA).
- It runs to the present day, so models can be tested on 2024-2026.
- The comment says WHY a night was lost (it confirmed the ice closures that the
  humidity rule alone missed, see dome.py).

Here it is used only to CHECK the project's closure label (validate.py).

It is a different telescope with its own, more cautious limits (a robotic telescope
closes for cloud, dust or ice risk that a staffed one may tolerate): the labels say
"what the LT did", not "what the GTC did".

Usage (download is done by backfill.py):
    liverpool.parse(path, year) -> DataFrame
"""

import html
import re
from datetime import date
from pathlib import Path

import pandas as pd

from roque_forecast.polite_http import PoliteSession

REPORTS_URL = "https://telescope.livjm.ac.uk/Reports/"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def download_year(session: PoliteSession, year: int, today: date, dest: Path) -> Path:
    """One page per year (the current year lives at the top-level Reports page)."""
    url = REPORTS_URL if year == today.year else f"{REPORTS_URL}{year}/"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(session.get(url).text, encoding="utf-8")
    return dest


def _cells(row_html: str) -> list[str]:
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.DOTALL | re.IGNORECASE)]


def parse(path: Path, year: int) -> pd.DataFrame:
    """Rows: night (date of the evening), observing_h, weather_h, technical_h, comment.

    The page has one table per month. The date in each row ("31 Mar") is the evening
    the night starts, the same convention as the rest of the project (checked against
    the NOT closure rule: correlation 0.66 with the same date, 0.47 shifted one day).
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = []
    for block in re.split(rf"(?=(?:{MONTHS}) {year})", text):
        month = re.match(rf"({MONTHS}) {year}", block)
        if not month:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", block, flags=re.DOTALL | re.IGNORECASE):
            c = _cells(tr)
            if len(c) < 5 or not re.match(r"^\d{1,2} \w{3}$", c[0]):
                continue
            if c[0].split()[1] != month.group(1)[:3]:  # a row of another month shown in this block
                continue
            try:
                rows.append({"night": pd.to_datetime(f"{c[0]} {year}", format="%d %b %Y"),
                             "observing_h": float(c[1]), "weather_h": float(c[2]),
                             "technical_h": float(c[3]), "comment": c[4]})
            except ValueError:  # a row without numbers (e.g. a note)
                continue
    out = pd.DataFrame(rows, columns=["night", "observing_h", "weather_h", "technical_h", "comment"])
    out["night"] = pd.to_datetime(out["night"])
    return out


# Words in the comment that say why the sky or the dome was not usable.
REASONS = {
    "humidity": r"humid|wet|\bfog|rain|snow|drizzle",
    "ice": r"\bice\b|\bicing\b|ice risk|frozen|freezing",
    "wind": r"\bwind|gust",
    "cloud": r"cloud",
    "dust": r"calima|\bdust",
}


def labels(table: pd.DataFrame) -> pd.DataFrame:
    """Add the labels used by the models.

    - weather_frac: share of the usable night lost to weather (observing + weather hours);
    - photometric: 1 if the comment says photometric, 0 if non-photometric, missing otherwise
      (closed nights have no sky quality to report);
    - one column per reason (humidity, ice, wind, cloud, dust): the comment mentions it.
    """
    out = table.copy()
    usable = out["observing_h"] + out["weather_h"]
    out["weather_frac"] = out["weather_h"] / usable.where(usable > 0)
    comment = out["comment"].str.lower()
    out["photometric"] = pd.NA
    out.loc[comment.str.contains(r"\bphoto\w*metric", regex=True), "photometric"] = 1.0
    out.loc[comment.str.contains(r"non-?\s?photometric|not photometric|mostly non", regex=True), "photometric"] = 0.0
    out["photometric"] = out["photometric"].astype("Float64")
    for reason, pattern in REASONS.items():
        out[f"reason_{reason}"] = comment.str.contains(pattern, regex=True)
    return out
