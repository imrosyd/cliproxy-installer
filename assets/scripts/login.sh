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

BINARY="$HOME/.cliproxyapi/bin/cliproxyapi"
CONFIG="$HOME/.cliproxyapi/config.yaml"

clear
cp_print_header "Login" "Pilih provider untuk autentikasi"
echo -e "  ${BOLD}${GREEN}1${NC}  Antigravity"
echo -e "  ${BOLD}${GREEN}2${NC}  GitHub Copilot"
echo -e "  ${BOLD}${GREEN}3${NC}  Gemini CLI"
echo -e "  ${BOLD}${GREEN}4${NC}  Codex"
echo -e "  ${BOLD}${GREEN}5${NC}  Claude"
echo -e "  ${BOLD}${GREEN}6${NC}  Qwen"
echo -e "  ${BOLD}${GREEN}7${NC}  iFlow"
echo ""
echo -e "  ${BOLD}${RED}0${NC}  Exit"
echo ""
cp_prompt "Provider ${DIM}(0-7)${NC}" c
case $c in
    1) "$BINARY" --config "$CONFIG" -antigravity-login ;;
    2) "$BINARY" --config "$CONFIG" -github-copilot-login ;;
    3) "$BINARY" --config "$CONFIG" -login ;;
    4) "$BINARY" --config "$CONFIG" -codex-login ;;
    5) "$BINARY" --config "$CONFIG" -claude-login ;;
    6) "$BINARY" --config "$CONFIG" -qwen-login ;;
    7) "$BINARY" --config "$CONFIG" -iflow-login ;;
    0) echo "Exiting..."; exit 0 ;;
    *) cp_warn "Invalid choice." ;;
esac
