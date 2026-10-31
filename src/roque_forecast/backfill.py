"""Bulk download of the historical archives (NOT, R2D2, ING nights).

Usage (from the project folder):
    .venv/bin/python -m roque_forecast.backfill not     # NOT weather, month by month, 1997 -> today
    .venv/bin/python -m roque_forecast.backfill r2d2    # R2D2 seeing, month by month, Sep 2018 -> today
    .venv/bin/python -m roque_forecast.backfill ing     # ING accounting, night by night, 2007 -> yesterday
    .venv/bin/python -m roque_forecast.backfill forecasts  # archived Open-Meteo forecasts, year by year
    .venv/bin/python -m roque_forecast.backfill liverpool  # Liverpool Telescope night reports (to check the label)

Design choices:
- **Resumable:** files already on disk are skipped, so the command can be stopped
  and re-run at any time. The current (unfinished) month is always downloaded again.
- **Atomic writes:** each file is first written as `*.part` and renamed when complete,
  so an interrupted download never leaves a half file that looks finished.
- **Polite:** one request at a time, 2 s apart (3 s for the ING, which has ~7,000 pages).
"""

import argparse
import gzip
import logging
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from roque_forecast import config
from roque_forecast.polite_http import PoliteSession
from roque_forecast.sources import ing_nights, liverpool, not_mast, open_meteo, r2d2

log = logging.getLogger("backfill")

NOT_FIRST_MONTH = date(1997, 1, 1)
R2D2_FIRST_MONTH = date(2018, 9, 1)  # the monitor started on 2018-09-19
ING_FIRST_NIGHT = date(2007, 1, 1)  # earlier pages are empty (checked 2005); 2007 has night lengths
# First year of each forecast archive for ECMWF IFS HRES (checked 28 Oct 2026; the
# day-1 archive is empty before late 2025, empty hours are dropped when parsing).
# "upper" is the GFS 200 hPa wind (jet stream), archived since March 2021.
FORECAST_FIRST_YEAR = {"historical": 2017, "previous_day1": 2025, "upper": 2021}


def months(first: date, last: date) -> Iterator[date]:
    """Yield the first day of every month from `first` to `last` (inclusive)."""
    current = first.replace(day=1)
    while current <= last:
        yield current
        current = (current + timedelta(days=32)).replace(day=1)


def next_month(month: date) -> date:
    return (month + timedelta(days=32)).replace(day=1)


def is_current_month(month: date, today: date) -> bool:
    return (month.year, month.month) == (today.year, today.month)


def finish(part: Path, final: Path) -> None:
    """Rename `*.part` to its final name (the download is complete)."""
    part.replace(final)


def backfill_not(session: PoliteSession, today: date) -> None:
    folder = config.RAW_DIR / "not"
    for month in months(NOT_FIRST_MONTH, today):
        final = folder / f"{month.year}" / f"not_{month:%Y-%m}.tsv.gz"
        nodata = final.with_suffix(".nodata")
        if (final.exists() or nodata.exists()) and not is_current_month(month, today):
            continue
        part = final.with_name(final.name + ".part")
        try:
            # The form works with minutes: [first day 00:00, first day of next month 00:00]
            start = datetime(month.year, month.month, 1)
            end_month = next_month(month)
            end = datetime(end_month.year, end_month.month, 1)
            not_mast.download_range(session, start, end, part)
            finish(part, final)
            log.info("NOT %s ok (%d bytes)", f"{month:%Y-%m}", final.stat().st_size)
        except RuntimeError as exc:
            # The server answered but offered no file: the month has no data.
            nodata.parent.mkdir(parents=True, exist_ok=True)
            nodata.write_text(str(exc))
            log.warning("NOT %s: no data (%s)", f"{month:%Y-%m}", exc)
        except Exception:
            log.exception("NOT %s failed (will retry on next run)", f"{month:%Y-%m}")


def backfill_r2d2(session: PoliteSession, today: date) -> None:
    folder = config.RAW_DIR / "r2d2"
    for month in months(R2D2_FIRST_MONTH, today):
        final = folder / f"r2d2_{month:%Y-%m}.html"
        if final.exists() and not is_current_month(month, today):
            continue
        part = final.with_name(final.name + ".part")
        try:
            # date2 is exclusive, so asking until the 1st of next month covers the whole month
            r2d2.download_range(session, month, next_month(month), part)
            finish(part, final)
            log.info("R2D2 %s ok (%d bytes)", f"{month:%Y-%m}", final.stat().st_size)
        except Exception:
            log.exception("R2D2 %s failed (will retry on next run)", f"{month:%Y-%m}")


def backfill_ing(session: PoliteSession, today: date) -> None:
    folder = config.RAW_DIR / "ing_nights"
    night = ING_FIRST_NIGHT
    done = 0
    # Only finished nights: a night that started yesterday ended this morning.
    while night < today:
        final = folder / f"{night.year}" / f"{night}.html.gz"
        if not final.exists():
            part = final.with_name(final.name + ".part")
            try:
                part.parent.mkdir(parents=True, exist_ok=True)
                part.write_bytes(gzip.compress(ing_nights.fetch_night(session, night)))
                finish(part, final)
                done += 1
                if done % 100 == 0:
                    log.info("ING %s ok (%d nights downloaded this run)", night, done)
            except Exception:
                log.exception("ING %s failed (will retry on next run)", night)
        night += timedelta(days=1)
    log.info("ING finished: %d nights downloaded this run", done)


def backfill_forecasts(session: PoliteSession, today: date) -> None:
    for kind, first_year in FORECAST_FIRST_YEAR.items():
        folder = config.RAW_DIR / "open_meteo" / kind
        for year in range(first_year, today.year + 1):
            model = open_meteo.UPPER_MODEL if kind == "upper" else open_meteo.MODEL
            final = folder / f"{model}_{year}.json"
            if final.exists() and year != today.year:
                continue
            part = final.with_name(final.name + ".part")
            # The archive ends yesterday; for the current year, stop there.
            end = min(date(year, 12, 31), today)
            start = max(date(year, 1, 1), open_meteo.UPPER_FIRST_DAY) if kind == "upper" else date(year, 1, 1)
            try:
                open_meteo.download_year(session, kind, start, end, part)
                finish(part, final)
                log.info("Open-Meteo %s %d ok (%d bytes)", kind, year, final.stat().st_size)
            except Exception:
                log.exception("Open-Meteo %s %d failed (will retry on next run)", kind, year)


LIVERPOOL_FIRST_YEAR = 2007  # the 2004-2006 pages have no per-night table


def backfill_liverpool(session: PoliteSession, today: date) -> None:
    folder = config.RAW_DIR / "liverpool"
    for year in range(LIVERPOOL_FIRST_YEAR, today.year + 1):
        final = folder / f"lt_reports_{year}.html"
        if final.exists() and year != today.year:
            continue
        try:
            liverpool.download_year(session, year, today, final)
            log.info("Liverpool %d ok", year)
        except Exception:
            log.exception("Liverpool %d failed (will retry on next run)", year)


SOURCES = {
    "not": (backfill_not, 2.0),
    "r2d2": (backfill_r2d2, 2.0),
    "ing": (backfill_ing, 3.0),
    "forecasts": (backfill_forecasts, 3.0),
    "liverpool": (backfill_liverpool, 3.0),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("source", choices=SOURCES)
    args = parser.parse_args(argv)

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_DIR / f"backfill_{args.source}.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    function, delay_s = SOURCES[args.source]
    function(PoliteSession(min_interval_s=delay_s), datetime.now(UTC).date())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
