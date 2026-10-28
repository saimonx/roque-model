"""Does the closure label reflect what really happens? Four independent checks.

The models learn "dome closed" from a rule rebuilt from the NOT weather station
(dome.closed: humidity, wind or ice). There is no public record of when the GTC
closes, so the label is checked against four independent public sources:

1. **GTC Public Archive** (2024 -> a year ago; data become public one year after they
   are taken): the GTC never takes science exposures with the dome closed. If the
   label is right, the GTC should almost never be exposing in minutes the label calls
   "closed", and should take no data on nights it calls fully closed. It shows when
   the GTC was certainly open, not when it closed (no data can be a technical night).
2. **Liverpool Telescope night reports** (2017 -> today): a robotic telescope on the
   same site books, every night, the hours lost to weather. Its closed hours should
   follow the label's (it is more cautious, so it loses more).
3. **TNG weather downtime** (last 365 days, from the TNG public weather page): hours
   lost to weather per night. It covers the most recent year, whose GTC data are not
   public yet.
4. **WHT nightly accounting** (ING): the same check, year by year. It also shows the
   years when the WHT log books closed nights as observed (see the EDA).

The results are also put side by side by year (`by_year`), so each year shows which
sources check it.

Usage:
    .venv/bin/python -m roque_forecast.validate   # writes reports/results/validation.json
"""

import gzip
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from roque_forecast import config, hourly
from roque_forecast.sources import gtc_archive, liverpool, tng

log = logging.getLogger("validate")
RESULTS = config.PROJECT_DIR / "reports" / "results"
FIRST_NIGHT = pd.Timestamp("2010-01-01")


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


def check_gtc_year(minutes: pd.DataFrame, year: int) -> dict | None:
    exposures = gtc_archive.load_exposures(config.RAW_DIR / "gtc_archive" / str(year))
    if exposures.empty:
        return None
    dark = minutes[(minutes["time_utc"].dt.year == year) & minutes["is_night"]].set_index("time_utc")
    exposing = pd.Series(False, index=dark.index)
    for t0, t1 in zip(exposures["t0"], exposures["t1"]):
        exposing.loc[t0.floor("min"):t1.ceil("min")] = True
    closed = dark["closed"]
    nights = pd.DataFrame({"closed": closed, "exposing": exposing, "night": dark["night"]}).groupby("night").agg(
        closed_frac=("closed", "mean"), exposing_min=("exposing", "sum"))
    fully_closed = nights[nights["closed_frac"] >= 0.99]
    months = exposures["t0"].dt.tz_convert(None).dt.to_period("M")
    months = months[months.dt.year == year]
    return {
        "year": year, "exposures": len(exposures), "first_month": str(months.min()), "last_month": str(months.max()),
        "instruments": sorted(exposures["instrument"].dropna().unique().tolist()),
        "exposing_hours": round(float(exposing.sum()) / 60, 1),
        # The key number: of the minutes the GTC was exposing, how many does the label call closed?
        "exposing_when_label_closed": round(float(closed[exposing].mean()), 4),
        "label_closed_hours": round(float(closed.sum()) / 60, 1),
        "nights_fully_closed": len(fully_closed),
        "nights_fully_closed_with_gtc_data": int((fully_closed["exposing_min"] > 0).sum()),
    }


def check_gtc(minutes: pd.DataFrame) -> list[dict]:
    folder = config.RAW_DIR / "gtc_archive"
    years = sorted(int(d.name) for d in folder.iterdir() if d.is_dir()) if folder.exists() else []
    return [r for r in (check_gtc_year(minutes, y) for y in years) if r]


def load_liverpool() -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "liverpool").glob("lt_reports_*.html"))
    parts = [liverpool.parse(f, int(f.stem.rsplit("_", 1)[1])) for f in files]
    lt = pd.concat(parts, ignore_index=True).drop_duplicates("night").set_index("night").sort_index()
    return liverpool.labels(lt[lt.index <= pd.Timestamp.now().normalize()])


def lost_vs_label(j: pd.DataFrame, lost: str) -> dict:
    """Common check against a telescope that books hours lost to weather per night."""
    label_closed = j["closed_h"] >= 0.9 * j["dark_h"]
    lost_night = j[lost] >= 0.5 * j["dark_h"]
    return {
        "nights": len(j), "first": str(j.index.min().date()), "last": str(j.index.max().date()),
        "correlation": round(float(j["closed_h"].corr(j[lost])), 2),
        # Nights our label calls (almost) fully closed: did that telescope lose them too?
        "label_closed_nights": int(label_closed.sum()),
        "label_closed_also_lost": round(float(lost_night[label_closed].mean()), 3),
        "mean_closed_h_label": round(float(j["closed_h"].mean()), 2),
        "mean_lost_h": round(float(j[lost].mean()), 2),
        "by_year": {int(y): round(float(g["closed_h"].corr(g[lost])), 2)
                    for y, g in j.groupby(j.index.year) if len(g) >= 60},
    }


def check_liverpool(label: pd.DataFrame) -> dict:
    lt = load_liverpool()
    j = label.join(lt[["weather_h", "observing_h"]], how="inner")
    # Nights with a report (the LT books nothing on nights it was down for engineering).
    j = j[(j.index >= "2017-01-01") & ((j["weather_h"] + j["observing_h"]) > 0)]
    return lost_vs_label(j, "weather_h")


def load_tng() -> pd.DataFrame:
    """TNG downtime, one row per night (the day the night starts), from every daily download."""
    files = sorted((config.RAW_DIR / "tng").glob("*/downtime.json.gz"))
    parts = [tng.parse_downtime(gzip.decompress(f.read_bytes())) for f in files]
    if not parts:
        return pd.DataFrame(columns=["weather_h", "technical_h"])
    out = pd.concat(parts)
    return out[~out.index.duplicated(keep="last")].sort_index()


def check_tng(label: pd.DataFrame) -> dict | None:
    j = label.join(load_tng()[["weather_h"]], how="inner").dropna()
    return lost_vs_label(j, "weather_h") if len(j) else None


def check_wht(label: pd.DataFrame) -> list[dict]:
    nights = pd.read_parquet(config.PROCESSED_DIR / "nights.parquet")
    wht = nights[nights["wht_has_accounting"] == True][["wht_weather_lost_h", "wht_night_h"]]
    j = label.join(wht, how="inner")
    j["wht_lost"] = j["wht_weather_lost_h"].clip(upper=j["wht_night_h"])
    rows = []
    for year, g in j.groupby(j.index.year):
        fully_closed = g["closed_h"] >= 0.99 * g["dark_h"]
        rows.append({"year": int(year), "nights": len(g),
                     "correlation": round(float(g["closed_h"].corr(g["wht_lost"])), 2),
                     # Nights closed all night by the label that the WHT booked with no weather loss at all.
                     "closed_all_night_but_no_wht_loss": int((fully_closed & (g["wht_lost"] == 0)).sum())})
    return rows


def by_year(result: dict) -> list[dict]:
    """One row per year with every check that covers it (empty when a source has no data)."""
    gtc = {g["year"]: g["exposing_when_label_closed"] for g in result["gtc"]}
    lt = result["liverpool"]["by_year"]
    tn = result["tng"]["by_year"] if result["tng"] else {}
    wht = {w["year"]: w["correlation"] for w in result["wht"]}
    years = sorted(set(gtc) | set(lt) | set(tn) | set(wht))
    return [{"year": y, "gtc": gtc.get(y), "liverpool": lt.get(y), "tng": tn.get(y), "wht": wht.get(y)} for y in years]


def main() -> int:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOG_DIR / "validate.log"), logging.StreamHandler(sys.stdout)])
    minutes = label_by_minute(FIRST_NIGHT)
    label = nightly_label(minutes)
    label = label[label.index >= FIRST_NIGHT]
    result = {"gtc": check_gtc(minutes), "liverpool": check_liverpool(label), "tng": check_tng(label),
              "wht": check_wht(label)}
    result["by_year"] = by_year(result)
    Path(RESULTS / "validation.json").write_text(json.dumps(result, indent=2))
    log.info("%s", json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
