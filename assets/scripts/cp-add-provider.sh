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

cp_print_header "Add Provider"

PYTHON_BIN="$(cp_get_python_bin)"
if [ -z "$PYTHON_BIN" ]; then
    cp_die "Python is not installed. Please install python3 to use cp-add-provider."
fi

"$PYTHON_BIN" "$HOME/.cliproxyapi/scripts/cp-add-provider.py"
