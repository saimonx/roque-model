#!/bin/bash
# Package what the hourly forecast needs to run without the full data archive, and upload it
# as the asset of the "runtime" release, where the GitHub Actions workflow downloads it from.
#   - data/models: RoqueModel (hourly.joblib) and the seeing model (seeing.joblib)
#   - data/processed: the hour table (sample of ordinary hours for the breakdown) and the
#     test predictions (page accuracy figures)
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
    data/processed/hour_table.parquet data/processed/hour_predictions.parquet \
    $(ls data/forecasts/*.jsonl 2>/dev/null)
# Release titles and notes in Spanish and English, like the README and the web page.
RUNTIME_TITLE="Modelos del pronóstico (modelos y tablas) · Forecast models (models and tables)"
NOTES="Modelos y tablas que necesita el pronóstico de cada hora (generados con scripts/build_runtime.sh el $(date -u +%Y-%m-%d)).
Derivados de datos públicos: estación meteorológica del NOT (not.iac.es), seeing R2D2 del ING (ing.iac.es) y
previsiones ECMWF y GFS archivadas por Open-Meteo (CC BY 4.0). Proyecto independiente, no afiliado a ningún observatorio.

Models and tables the hourly forecast needs (built with scripts/build_runtime.sh on $(date -u +%Y-%m-%d)).
Derived from public data: NOT weather station (not.iac.es), ING R2D2 seeing (ing.iac.es) and ECMWF and GFS
forecasts archived by Open-Meteo (CC BY 4.0). Independent project, not affiliated with any observatory."
if gh release view runtime >/dev/null 2>&1; then
    gh release upload runtime "$OUT" --clobber
    gh release edit runtime --title "$RUNTIME_TITLE" --notes "$NOTES"
else
    gh release create runtime "$OUT" --title "$RUNTIME_TITLE" --notes "$NOTES" --latest=false
fi
echo "uploaded $(du -h "$OUT" | cut -f1) to the runtime release"

# The data RoqueModel learnt from, for anyone to download and check (web page, card 3).
.venv/bin/python -m roque_forecast.export_data
DATA_ZIP=data/export/roquemodel_data.zip
DATA_TITLE="Datos de entrenamiento de RoqueModel (CSV) · RoqueModel training data (CSV)"
DATA_NOTES="Las horas de noche con las que aprendió RoqueModel (2017-2026: etiqueta y todos los datos de entrada) y las
respuestas de la copia probada en 2024-2026, en CSV, con un README que describe cada columna y su fuente pública
(generados con scripts/build_runtime.sh el $(date -u +%Y-%m-%d)). Derivados de datos públicos: estación meteorológica
del NOT (not.iac.es), seeing R2D2 del ING (ing.iac.es) y previsiones ECMWF y GFS archivadas por Open-Meteo (CC BY 4.0).
Proyecto independiente, no afiliado a ningún observatorio.

The night hours RoqueModel learnt from (2017-2026: label and all the inputs) and the answers of the copy tested on
2024-2026, as CSV, with a README (README.md in Spanish, README.en.md in English) describing each column and its public
source (built with scripts/build_runtime.sh on $(date -u +%Y-%m-%d)). Derived from public data: NOT weather station
(not.iac.es), ING R2D2 seeing (ing.iac.es) and ECMWF and GFS forecasts archived by Open-Meteo (CC BY 4.0).
Independent project, not affiliated with any observatory."
if gh release view training-data >/dev/null 2>&1; then
    gh release upload training-data "$DATA_ZIP" --clobber
    gh release edit training-data --title "$DATA_TITLE" --notes "$DATA_NOTES"
else
    gh release create training-data "$DATA_ZIP" --title "$DATA_TITLE" --notes "$DATA_NOTES" --latest=false
fi
echo "uploaded $(du -h "$DATA_ZIP" | cut -f1) to the training-data release"
