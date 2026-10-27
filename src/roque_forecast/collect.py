"""Command-line data collector.

Usage (from the project folder):
    .venv/bin/python -m roque_forecast.collect live     # every 15 min (LaunchAgent)
    .venv/bin/python -m roque_forecast.collect daily    # once a day   (LaunchAgent)
    .venv/bin/python -m roque_forecast.collect weekly   # once a week  (LaunchAgent)
    .venv/bin/python -m roque_forecast.collect sample   # one-off: small samples to inspect formats

Everything is saved under data/raw/ exactly as downloaded (gzip-compressed),
so we can always rebuild the clean tables if a parser changes.
Times in file names are UTC.
"""

import argparse
import gzip
import json
import logging
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from roque_forecast import config
from roque_forecast.polite_http import PoliteSession
from roque_forecast.sources import gtc_atmosportal, ing_nights, not_mast, r2d2, tng

log = logging.getLogger("collect")


def save_gz(path: Path, content: bytes) -> None:
    """Write bytes gzip-compressed (JSON shrinks ~10x)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as f:
        f.write(content)


def collect_live(session: PoliteSession) -> None:
    """Snapshot of the GTC live panel + TNG current values, appended to a daily file.

    One JSON object per line ("JSON Lines"): easy to append, easy to read with pandas.
    Each source is tried separately, so one server being down does not lose the other.
    """
    now = datetime.now(UTC)
    record: dict = {"collected_utc": now.isoformat(timespec="seconds")}

    try:
        html = gtc_atmosportal.fetch_home_page(session)
        record["gtc_panel"] = gtc_atmosportal.parse_panel(html)
        record["gtc_panel_html"] = gtc_atmosportal.panel_html_only(html)
    except Exception as exc:  # keep going: record the error instead
        log.exception("GTC panel failed")
        record["gtc_error"] = repr(exc)

    try:
        raw = tng.fetch_current(session)
        record["tng_current"] = tng.parse_current(raw)
    except Exception as exc:
        log.exception("TNG current failed")
        record["tng_error"] = repr(exc)

    out = config.RAW_DIR / "live" / f"{now:%Y-%m}" / f"{now:%Y-%m-%d}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info("live snapshot -> %s", out)


def collect_daily(session: PoliteSession) -> None:
    """TNG last-24 h series (1-minute resolution) + TNG downtime table."""
    today = datetime.now(UTC)
    folder = config.RAW_DIR / "tng" / f"{today:%Y-%m-%d}"
    for var in tng.SERIES_VARS:
        try:
            save_gz(folder / f"{var}.json.gz", tng.fetch_series(session, var))
        except Exception:
            log.exception("TNG series %s failed", var)
    try:
        save_gz(folder / "downtime.json.gz", tng.fetch_downtime(session))
    except Exception:
        log.exception("TNG downtime failed")
    log.info("daily TNG -> %s", folder)


def collect_weekly(session: PoliteSession) -> None:
    """GTC atmosportal last-30-days series, one file per variable."""
    today = datetime.now(UTC)
    folder = config.RAW_DIR / "gtc_atmosportal" / f"{today:%Y-%m-%d}"
    for var in gtc_atmosportal.SERIES_VARS:
        try:
            save_gz(folder / f"{var}_month.json.gz", gtc_atmosportal.fetch_series(session, var))
        except Exception:
            log.exception("GTC series %s failed", var)
    log.info("weekly GTC -> %s", folder)


def collect_sample(session: PoliteSession) -> None:
    """Small samples (September 2026) to check every format before bulk downloads."""
    folder = config.RAW_DIR / "samples"
    not_mast.download_range(
        session, datetime(2026, 9, 1), datetime(2026, 10, 1), folder / "not_2026-09.tsv.gz"
    )
    # date2 is exclusive for R2D2, so pass 1 October to include 30 September
    r2d2.download_range(session, date(2026, 9, 1), date(2026, 10, 1), folder / "r2d2_2026-09.html")
    for night in [date(2026, 9, 1) + timedelta(days=i) for i in range(0, 30, 7)]:
        ing_nights.download_night(session, night, folder / "ing" / f"{night}.html")
    log.info("samples -> %s", folder)


COMMANDS = {
    "live": collect_live,
    "daily": collect_daily,
    "weekly": collect_weekly,
    "sample": collect_sample,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args(argv)

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_DIR / f"collect_{args.command}.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    COMMANDS[args.command](PoliteSession())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
