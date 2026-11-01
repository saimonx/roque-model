#!/bin/bash
# Hourly job: tonight's forecast -> site data (-> GitHub Pages when publishing is switched on).
#   1. tonight.py      : live data + models -> site/data/tonight.json (+ FIWARE if the stack is running)
#   2. site_data.py    : evaluation and live track record -> site/data/evaluation.json
#   3. publish_site.sh : only if ROQUE_PUBLISH=1 (normally off: the cloud publishes)
#   4. starts the GitHub Actions forecast (.github/workflows/forecast.yml), which publishes the
#      page. GitHub's own schedule skips most runs on a quiet repository (1 of 40 on 1 Nov), while
#      a run started this way begins at once. ROQUE_TRIGGER_CLOUD=0 turns it off.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$PROJECT_DIR"
.venv/bin/python -m roque_forecast.tonight
.venv/bin/python -m roque_forecast.site_data
if [[ "${ROQUE_PUBLISH:-0}" == "1" ]]; then
    scripts/publish_site.sh
fi
if [[ "${ROQUE_TRIGGER_CLOUD:-1}" == "1" ]]; then
    GH="$(command -v gh || echo /opt/homebrew/bin/gh)"
    # perl alarm: give up after 60 s so a stuck request never blocks the next hourly run.
    perl -e 'alarm 60; exec @ARGV' "$GH" workflow run forecast.yml -R saimonx/roque-night-forecast \
        && echo "cloud forecast started" || echo "could not start the cloud forecast" >&2
fi
