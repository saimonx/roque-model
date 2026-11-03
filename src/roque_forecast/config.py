"""Project-wide constants: site coordinates, folders and polite-download settings.

Keeping these values in one place means every script uses the same paths and
the same rules for talking to the observatories' public web servers.
"""

from pathlib import Path

# --- Site -----------------------------------------------------------------
# Roque de los Muchachos Observatory (La Palma). Coordinates of the 10.4 m
# telescope building, used later to ask a weather API for "tonight".
SITE_LAT = 28.7566
SITE_LON = -17.8919
SITE_ALT_M = 2270

# --- Folders --------------------------------------------------------------
# PROJECT_DIR is the repository root (two levels above this file:
# src/roque_forecast/config.py -> src/ -> project root).
PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # files exactly as downloaded (never edited)
PROCESSED_DIR = DATA_DIR / "processed"  # clean tables built from RAW_DIR
LOG_DIR = DATA_DIR / "logs"

# --- Polite downloading ---------------------------------------------------
# These are small public servers run by observatories, not big APIs.
# We identify ourselves honestly and wait between requests.
USER_AGENT = (
    "roque-model/0.1 "
    "(independent research project; https://github.com/saimonx/roque-model)"
)
MIN_SECONDS_BETWEEN_REQUESTS = 2.0
REQUEST_TIMEOUT_S = 120
