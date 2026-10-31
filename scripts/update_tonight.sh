#!/bin/bash
# Hourly job: tonight's forecast -> site data (-> GitHub Pages when publishing is switched on).
#   1. tonight.py      : live data + models -> site/data/tonight.json (+ FIWARE if the stack is running)
#   2. site_data.py    : evaluation and live track record -> site/data/evaluation.json
#   3. publish_site.sh : only if ROQUE_PUBLISH=1 (the repository must be public for GitHub Pages)
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$PROJECT_DIR"
.venv/bin/python -m roque_forecast.tonight
.venv/bin/python -m roque_forecast.site_data
if [[ "${ROQUE_PUBLISH:-0}" == "1" ]]; then
    scripts/publish_site.sh
fi
