"""Does the closure label reflect what really happens? Checked against one telescope.

The models learn "dome closed" from a rule rebuilt from the NOT weather station
(dome.closed: humidity, wind or ice), the same way for every year. There is no
public record of when the GTC closes, so the label is checked against the night
reports of the **Liverpool Telescope** (LT, robotic 2 m on the same site), which
book every night the hours lost to weather and are filled in the same way every year.

Only one source is used, for every year, so the check means the same thing every
year. Sources looked at and not used:
- **GTC public archive**: exposure times show when the GTC was open, but data become
  public one year later and only 2024-2025 were available: not every year.
- **TNG weather downtime**: only the last 365 days are published.
- **WHT nightly accounting**: some years book nights with the dome closed as observed
  (see the EDA), so it is not filled in the same way every year.

Usage:
    .venv/bin/python -m roque_forecast.validate   # writes reports/results/validation.json
"""

import json
import logging
import sys
from pathlib import Path

import pandas as pd

from roque_forecast import config, hourly
from roque_forecast.sources import liverpool

log = logging.getLogger("validate")
RESULTS = config.PROJECT_DIR / "reports" / "results"
FIRST_NIGHT = pd.Timestamp("2017-01-01")  # same years as the models (train 2017-2022)
FULLY_CLOSED = 0.9   # the label closes at least 90 % of the dark hours
LOST = 0.5           # the LT lost at least half of the night to weather


def label_by_minute(first: pd.Timestamp) -> pd.DataFrame:
    minutes = pd.read_parquet(config.PROCESSED_DIR / "not_minutes.parquet",
                              columns=["time_utc", "is_night", "night", "humidity_pct", "wind_speed_ms", "temp_c"],
                              filters=[("time_utc", ">=", first.tz_localize("UTC") - pd.Timedelta(days=2))])
    return hourly.label_minutes(minutes)


def nightly_label(minutes: pd.DataFrame) -> pd.DataFrame:
    dark = minutes[minutes["is_night"]]
    g = dark.groupby("night")
    out = pd.DataFrame({"dark_h": g.size() / 60, "closed_h": g["closed"].sum() / 60})
    out.index = pd.to_datetime(out.index)
    return out


def load_liverpool() -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "liverpool").glob("lt_reports_*.html"))
    parts = [liverpool.parse(f, int(f.stem.rsplit("_", 1)[1])) for f in files]
    lt = pd.concat(parts, ignore_index=True).drop_duplicates("night").set_index("night").sort_index()
    return liverpool.labels(lt[lt.index <= pd.Timestamp.now().normalize()])


def compare(j: pd.DataFrame) -> dict:
    """Our closed hours against the LT hours lost to weather, for a set of nights."""
    label_closed = j["closed_h"] >= FULLY_CLOSED * j["dark_h"]
    lt_lost = j["weather_h"] >= LOST * j["dark_h"]
    return {
        "nights": len(j),
        "correlation": round(float(j["closed_h"].corr(j["weather_h"])), 2),
        # Nights our label calls (almost) fully closed: did the LT lose them too?
        "label_closed_nights": int(label_closed.sum()),
        "label_closed_lt_lost": round(float(lt_lost[label_closed].mean()), 3) if label_closed.any() else None,
        "mean_closed_h_label": round(float(j["closed_h"].mean()), 2),
        "mean_lost_h_lt": round(float(j["weather_h"].mean()), 2),
    }


def check_liverpool(label: pd.DataFrame) -> dict:
    lt = load_liverpool()
    j = label.join(lt[["weather_h", "observing_h"]], how="inner")
    # Nights with a report (the LT books nothing on nights it was down for engineering).
    j = j[(j["weather_h"] + j["observing_h"]) > 0]
    return {"first": str(j.index.min().date()), "last": str(j.index.max().date()), **compare(j),
            "by_year": [{"year": int(y), **compare(g)} for y, g in j.groupby(j.index.year)]}


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOG_DIR / "validate.log"), logging.StreamHandler(sys.stdout)])
    label = nightly_label(label_by_minute(FIRST_NIGHT))
    label = label[label.index >= FIRST_NIGHT]
    result = {"liverpool": check_liverpool(label)}
    Path(RESULTS / "validation.json").write_text(json.dumps(result, indent=2))
    log.info("%s", json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
