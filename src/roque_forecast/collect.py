"""Live collector: the GTC weather panel, sent to the local FIWARE stack.

Usage (from the project folder):
    .venv/bin/python -m roque_forecast.collect live     # every 15 min (LaunchAgent)

The GTC station is NOT saved anywhere: its live panel only updates the current state of
the FIWARE entity (urn:ngsi-ld:WeatherObserved:ORM-GTC). Nothing is written to disk.
"""

import argparse
import logging
import sys

from roque_forecast import config
from roque_forecast.polite_http import PoliteSession
from roque_forecast.sources import gtc_atmosportal

log = logging.getLogger("collect")


def collect_live(session: PoliteSession) -> None:
    """Read the GTC live panel and update its FIWARE entity (skipped if FIWARE is not running)."""
    try:
        panel = gtc_atmosportal.parse_panel(gtc_atmosportal.fetch_home_page(session))
    except Exception:
        log.exception("GTC panel failed")
        return
    from roque_forecast import fiware

    fiware.push_gtc_panel(panel)
    log.info("GTC panel -> FIWARE (%d rows)", len(panel["rows"]))


COMMANDS = {"live": collect_live}


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
