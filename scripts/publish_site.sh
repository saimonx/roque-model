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
cd "$TMP"
git init -q -b gh-pages
git add -A
git -c user.name="roque-night-forecast bot" -c user.email="noreply@github.com" \
    commit -q -m "Forecast update $(date -u +%Y-%m-%dT%H:%MZ)"
git push -q --force "$(git -C "$PROJECT_DIR" remote get-url origin)" gh-pages
echo "published site/ to gh-pages"
