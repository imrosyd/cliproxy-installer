#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_PATH="$HOME/.cliproxyapi/scripts/cp-lib.sh"
if [ -f "$LIB_PATH" ]; then
    # shellcheck source=/dev/null
    . "$LIB_PATH"
elif [ -f "$SCRIPT_DIR/cp-lib.sh" ]; then
    # shellcheck source=/dev/null
    . "$SCRIPT_DIR/cp-lib.sh"
else
    echo "[ERROR] Missing $LIB_PATH. Please run cp-update or reinstall CLIProxy."
    exit 1
fi
cp_init_colors

# CLIProxy Dashboard Launcher: memastikan server hidup, update quota, lalu buka dashboard.

# Add timestamp to force cache busting
TIMESTAMP=$(date +%s)
DASHBOARD_URL="http://localhost:8317/dashboard.html?v=$TIMESTAMP"
PORT=8317

cp_print_header "Dashboard" "URL: http://localhost:$PORT/"

cp_ensure_server_running "$PORT" || exit 1

QUOTA_FETCHER="$HOME/.cliproxyapi/scripts/quota-fetcher.py"
PYTHON_BIN="$(cp_get_python_bin)"
if [ -f "$QUOTA_FETCHER" ] && [ -n "$PYTHON_BIN" ]; then
    cp_info "Fetching quota data..."
    "$PYTHON_BIN" "$QUOTA_FETCHER" 2>/dev/null || true
    CRON_CMD="*/10 * * * * $PYTHON_BIN $HOME/.cliproxyapi/scripts/quota-fetcher.py >/dev/null 2>&1"
    cp_ensure_cron_contains "quota-fetcher.py" "$CRON_CMD"
    cp_ok "Quota data updated."
fi

cp_info "Opening dashboard: $DASHBOARD_URL"

cp_open_url "$DASHBOARD_URL"

cp_ok "Dashboard opened."
