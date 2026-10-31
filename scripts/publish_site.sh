#!/bin/bash
# Publish site/ to the gh-pages branch as ONE fresh commit (force-pushed), so the hourly
# forecast updates never pile up in the history of main. GitHub Pages serves that branch.
# Needs: a public repository (or a paid plan) with Pages set to "Deploy from branch: gh-pages".
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -R "$PROJECT_DIR/site/." "$TMP/"
touch "$TMP/.nojekyll"   # serve files as they are (no Jekyll processing)
# The forecast log goes with the page: it is public, and the next run (in the cloud) reads it back.
if ls "$PROJECT_DIR"/data/forecasts/*.jsonl >/dev/null 2>&1; then
    mkdir -p "$TMP/forecasts"
    cp "$PROJECT_DIR"/data/forecasts/*.jsonl "$TMP/forecasts/"
fi
cd "$TMP"
git init -q -b gh-pages
git add -A
git -c user.name="roque-night-forecast bot" -c user.email="noreply@github.com" \
    commit -q -m "Forecast update $(date -u +%Y-%m-%dT%H:%MZ)"
# PUBLISH_REMOTE: set by the GitHub Actions workflow (a URL with its token); otherwise origin.
git push -q --force "${PUBLISH_REMOTE:-$(git -C "$PROJECT_DIR" remote get-url origin)}" gh-pages
echo "published site/ to gh-pages"
