#!/bin/bash
# ── Stop CLIProxy server (unified server on 8317 + backend on 8316) ──

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

cp_print_header "Stop Proxy"
cp_info "Stopping CLIProxy server..."
pkill -f "$HOME/.cliproxyapi/scripts/unified-server.py" || true
pkill -f "$HOME/.cliproxyapi/bin/cliproxyapi" || true
# Backward-compatible fallback for old install paths.
pkill -f "cliproxyapi.*\.cliproxyapi/config.yaml" || true
cp_ok "Server stopped."
