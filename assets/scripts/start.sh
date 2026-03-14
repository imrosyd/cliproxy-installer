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

cp_print_header "Start Proxy" "Endpoint: http://localhost:8317"

cp_info "Stopping any existing CLIProxy instances..."
if [ -f "$HOME/.cliproxyapi/scripts/stop.sh" ]; then
    bash "$HOME/.cliproxyapi/scripts/stop.sh" >/dev/null 2>&1
fi
cp_info "Starting CLIProxy..."
PYTHON_BIN="$(cp_get_python_bin)"
if [ -f "$HOME/.cliproxyapi/scripts/unified-server.py" ] && [ -n "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" "$HOME/.cliproxyapi/scripts/unified-server.py"
else
    cp_warn "Unified server not available, starting API-only mode"
    if [ -x "$HOME/.cliproxyapi/bin/cliproxyapi" ]; then
        "$HOME/.cliproxyapi/bin/cliproxyapi" --config "$HOME/.cliproxyapi/config.yaml"
    else
        cp_die "Backend binary not found at ~/.cliproxyapi/bin/cliproxyapi"
    fi
fi
