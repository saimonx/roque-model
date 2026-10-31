#!/bin/bash
# Install (or reinstall) the three data collectors as macOS LaunchAgents.
#   live   -> every 15 min : GTC live panel + TNG current values
#   daily  -> 10:07, 22:07 : TNG last-24 h series + downtime
#   weekly -> Mon 10:23    : GTC last-30-days series
#   tonight -> hourly :05  : tonight's forecast + site data (only when named: install_collectors.sh tonight)
# Uninstall: scripts/install_collectors.sh --uninstall   (or: install_collectors.sh tonight --uninstall)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"

NAMES="live daily weekly"
if [[ "${1:-}" == "tonight" ]]; then
    NAMES="tonight"
    shift
fi

for name in $NAMES; do
    label="com.jose.roque-forecast.$name"
    target="$AGENTS_DIR/$label.plist"
    # Stop the old version if it is loaded (ignore the error if it is not).
    launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
    if [[ "${1:-}" == "--uninstall" ]]; then
        rm -f "$target"
        echo "removed $label"
        continue
    fi
    mkdir -p "$PROJECT_DIR/data/logs"
    sed "s#__PROJECT_DIR__#$PROJECT_DIR#g" "$PROJECT_DIR/launchd/$label.plist" > "$target"
    plutil -lint "$target" >/dev/null
    launchctl bootstrap "$DOMAIN" "$target"
    echo "installed $label"
done
