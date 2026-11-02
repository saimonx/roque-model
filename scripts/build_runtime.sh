#!/bin/bash
# Package what the hourly forecast needs to run without the full data archive, and upload it
# as the asset of the "runtime" release, where the GitHub Actions workflow downloads it from.
#   - data/models: RoqueModel (hourly.joblib) and the seeing model (seeing.joblib)
#   - data/processed: the hour table (sample of ordinary hours for the breakdown, usual values
#     per month), the nightly table (usual seeing) and the test predictions (page evaluation)
#   - data/forecasts: the forecast log, only used if the published site has none yet
# It also exports the training data (export_data.py) and uploads them as the asset of the
# "training-data" release, which the web page and the README link to for download.
# Run it again after retraining (python -m roque_forecast.hourly / train) so the cloud uses
# the new models and the download matches them.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$PROJECT_DIR"
OUT="$(mktemp -d)/runtime.tar.gz"
tar -czf "$OUT" \
    data/models/hourly.joblib data/models/seeing.joblib \
    data/processed/hour_table.parquet data/processed/model_table.parquet \
    data/processed/hour_predictions.parquet data/processed/night_predictions.parquet \
    $(ls data/forecasts/*.jsonl 2>/dev/null)
NOTES="Models and tables the hourly forecast needs (built with scripts/build_runtime.sh on $(date -u +%Y-%m-%d)).
Derived from public data: NOT weather station (not.iac.es), ING R2D2 seeing (ing.iac.es), ECMWF and GFS
forecasts archived by Open-Meteo (CC BY 4.0). Independent project, not affiliated with any observatory."
if gh release view runtime >/dev/null 2>&1; then
    gh release upload runtime "$OUT" --clobber
    gh release edit runtime --notes "$NOTES"
else
    gh release create runtime "$OUT" --title "Forecast runtime (models and tables)" --notes "$NOTES" --latest=false
fi
echo "uploaded $(du -h "$OUT" | cut -f1) to the runtime release"

# The data RoqueModel learnt from, for anyone to download and check (web page, card 3).
.venv/bin/python -m roque_forecast.export_data
DATA_ZIP=data/export/roquemodel_data.zip
DATA_NOTES="The night hours RoqueModel learnt from (2017-2026: label and every input) and the tested copy's
answers on 2024-2026, as CSV, with a README describing each column and its public source
(built with scripts/build_runtime.sh on $(date -u +%Y-%m-%d)). Derived from public data: NOT weather station
(not.iac.es), ING R2D2 seeing (ing.iac.es), ECMWF and GFS forecasts archived by Open-Meteo (CC BY 4.0).
Independent project, not affiliated with any observatory."
if gh release view training-data >/dev/null 2>&1; then
    gh release upload training-data "$DATA_ZIP" --clobber
    gh release edit training-data --notes "$DATA_NOTES"
else
    gh release create training-data "$DATA_ZIP" --title "RoqueModel training data (CSV)" --notes "$DATA_NOTES" --latest=false
fi
echo "uploaded $(du -h "$DATA_ZIP" | cut -f1) to the training-data release"
