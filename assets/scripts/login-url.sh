#!/bin/bash
# Login script for VPS/headless servers — prints URL only, no browser opening

# ── Colors ──
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

BINARY="$HOME/.cliproxyapi/bin/cliproxyapi"
CONFIG="$HOME/.cliproxyapi/config.yaml"

# Set BROWSER to echo to prevent browser opening
export BROWSER=echo

clear
echo -e "${CYAN}${BOLD}  ══  CLIProxy Login (URL Mode)  ══${NC}"
echo -e "  ${DIM}Prints the login URL — open it in your browser.${NC}"
echo ""
echo -e "  ${BOLD}${GREEN}1${NC}  Antigravity    ${DIM}Claude / Gemini${NC}"
echo -e "  ${BOLD}${GREEN}2${NC}  GitHub Copilot ${DIM}Copilot Models${NC}"
echo -e "  ${BOLD}${GREEN}3${NC}  Gemini CLI     ${DIM}Google Gemini${NC}"
echo -e "  ${BOLD}${GREEN}4${NC}  Codex          ${DIM}OpenAI Codex${NC}"
echo -e "  ${BOLD}${GREEN}5${NC}  Claude         ${DIM}Anthropic API${NC}"
echo -e "  ${BOLD}${GREEN}6${NC}  Qwen           ${DIM}Alibaba Qwen${NC}"
echo -e "  ${BOLD}${GREEN}7${NC}  iFlow          ${DIM}iFlow Models${NC}"
echo ""
echo -e "  ${BOLD}${RED}0${NC}  ${DIM}Exit${NC}"
echo ""
echo -ne "  ${BOLD}›${NC} Provider ${DIM}(0-7)${NC}: "
read c
case $c in
    1) "$BINARY" --config "$CONFIG" -antigravity-login ;;
    2) "$BINARY" --config "$CONFIG" -github-copilot-login ;;
    3) "$BINARY" --config "$CONFIG" -login ;;
    4) "$BINARY" --config "$CONFIG" -codex-login ;;
    5) "$BINARY" --config "$CONFIG" -claude-login ;;
    6) "$BINARY" --config "$CONFIG" -qwen-login ;;
    7) "$BINARY" --config "$CONFIG" -iflow-login ;;
    0) echo "Exiting..."; exit 0 ;;
    *) echo "Invalid choice." ;;
esac
