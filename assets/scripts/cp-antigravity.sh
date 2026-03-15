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

MANAGER_PY="$HOME/.cliproxyapi/scripts/cp-antigravity.py"
QUOTA_FETCHER="$HOME/.cliproxyapi/scripts/quota-fetcher.py"
PYTHON_BIN="$(cp_get_python_bin)"

if [ -z "$PYTHON_BIN" ]; then
    cp_error "Python tidak ditemukan. Install Python untuk menggunakan Antigravity Manager."
    exit 1
fi

if [ ! -f "$MANAGER_PY" ]; then
    cp_error "Antigravity Manager belum terpasang. Jalankan cp-update atau reinstall CLIProxy."
    exit 1
fi

refresh_quota() {
    if [ -f "$QUOTA_FETCHER" ]; then
        cp_info "Mengambil data quota terbaru..."
        "$PYTHON_BIN" "$QUOTA_FETCHER" 2>/dev/null || true
        cp_ok "Quota diperbarui."
    else
        cp_warn "quota-fetcher.py tidak ditemukan."
    fi
}

show_quota() {
    "$PYTHON_BIN" "$MANAGER_PY" || true
}

open_dashboard() {
    if command -v cp-db >/dev/null 2>&1; then
        cp-db
    else
        cp_open_url "http://localhost:8317/dashboard.html"
    fi
}

while true; do
    clear
    cp_print_header "Antigravity Manager" "Monitoring sisa quota Antigravity"
    echo -e "  ${BOLD}${GREEN}1${NC}  Refresh + Tampilkan Quota"
    echo -e "  ${BOLD}${GREEN}2${NC}  Tampilkan Cache Terakhir"
    echo -e "  ${BOLD}${GREEN}3${NC}  Buka Dashboard"
    echo ""
    echo -e "  ${BOLD}${RED}0${NC}  Kembali"
    echo ""
    echo -ne "  ${BOLD}›${NC} Select ${DIM}(0-3)${NC}: "
    read opt

    case $opt in
        1)
            refresh_quota
            show_quota
            read -p "Press Enter to continue...";
            ;;
        2)
            show_quota
            read -p "Press Enter to continue...";
            ;;
        3)
            open_dashboard
            read -p "Press Enter to continue...";
            ;;
        0) break ;;
        *) cp_warn "Pilihan tidak valid."; sleep 1 ;;
    esac
done
