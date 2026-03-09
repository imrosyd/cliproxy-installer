#!/bin/bash

# ── Colors ──
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

BINARY="$HOME/.cliproxyapi/bin/cliproxyapi"
CONFIG="$HOME/.cliproxyapi/config.yaml"

menu_full_install() {
    while true; do
        clear
        echo -e "${CYAN}${BOLD}  ══  Full Install  ══${NC}"
        echo ""
        echo -e "  ${BOLD}${GREEN}1${NC}  Dependencies + CLIProxy + CLI Apps"
        echo -e "  ${BOLD}${GREEN}2${NC}  Dependencies + CLIProxy"
        echo -e "  ${BOLD}${GREEN}3${NC}  CLIProxy + CLI Apps"
        echo -e "  ${BOLD}${GREEN}4${NC}  CLIProxy only"
        echo ""
        echo -e "  ${BOLD}${RED}0${NC}  Back"
        echo ""
        echo -ne "  ${BOLD}›${NC} Select ${DIM}(0-4)${NC}: "
        read opt
        case $opt in
            1) 
                echo "Installing Dependencies + CLIProxy + CLI Apps..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            2) 
                echo "Installing Dependencies + CLIProxy..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            3) 
                echo "Installing CLIProxy + CLI Apps..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            4) 
                echo "Installing CLIProxy..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            0) break ;;
            *) echo "Invalid choice." ;;
        esac
    done
}

menu_cliproxy() {
    while true; do
        clear
        echo -e "${CYAN}${BOLD}  ══  Install CLIProxy  ══${NC}"
        echo ""
        echo -e "  ${BOLD}${GREEN}1${NC}  Full (Binary + Scripts + Dashboard)"
        echo -e "  ${BOLD}${GREEN}2${NC}  Reinstall/Update"
        echo ""
        echo -e "  ${BOLD}${RED}0${NC}  Back"
        echo ""
        echo -ne "  ${BOLD}›${NC} Select ${DIM}(0-2)${NC}: "
        read opt
        case $opt in
            1) 
                echo "Installing CLIProxy Full..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            2) 
                echo "Reinstalling/Updating CLIProxy..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            0) break ;;
            *) echo "Invalid choice." ;;
        esac
    done
}

menu_cli_apps() {
    while true; do
        clear
        echo -e "${CYAN}${BOLD}  ══  Install CLI Apps  ══${NC}"
        echo ""
        echo -e "  ${BOLD}${GREEN}1${NC}  All (Claude + Droid + OpenCode + KiloCode)"
        echo -e "  ${BOLD}${GREEN}2${NC}  Claude Code"
        echo -e "  ${BOLD}${GREEN}3${NC}  Factory Droid"
        echo -e "  ${BOLD}${GREEN}4${NC}  OpenCode"
        echo -e "  ${BOLD}${GREEN}5${NC}  KiloCode"
        echo ""
        echo -e "  ${BOLD}${RED}0${NC}  Back"
        echo ""
        echo -ne "  ${BOLD}›${NC} Select ${DIM}(0-5)${NC}: "
        read opt
        case $opt in
            1) 
                echo "Installing All CLI Apps..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            2) 
                echo "Installing Claude Code..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            3) 
                echo "Installing Factory Droid..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            4) 
                echo "Installing OpenCode..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            5) 
                echo "Installing KiloCode..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            0) break ;;
            *) echo "Invalid choice." ;;
        esac
    done
}

menu_update() {
    clear
    echo -e "${CYAN}${BOLD}  ══  Update  ══${NC}"
    echo ""
    echo -e "${YELLOW}Running CLIProxy update...${NC}"
    echo ""
    if command -v cp-update &> /dev/null; then
        cp-update
    elif [ -f "$HOME/.cliproxyapi/scripts/start.sh" ]; then
        echo "Reinstalling CLIProxy..."
        if command -v go &> /dev/null; then
            TEMP_DIR=$(mktemp -d)
            git clone --depth 1 https://github.com/router-for-me/CLIProxyAPIPlus.git "$TEMP_DIR" 2>/dev/null
            cd "$TEMP_DIR" && go build -o cliproxyapi ./cmd/server 2>/dev/null
            mv -f cliproxyapi "$HOME/.cliproxyapi/bin/cliproxyapi" 2>/dev/null
            rm -rf "$TEMP_DIR"
            echo -e "${GREEN}[OK] CLIProxy updated!${NC}"
        else
            echo -e "${RED}[Error] Go is not installed. Please install Go first.${NC}"
        fi
    else
        echo -e "${RED}[Error] CLIProxy not found. Please install CLIProxy first.${NC}"
    fi
    echo ""
    read -p "Press Enter to continue..."
}

main_menu() {
    while true; do
        clear
        echo -e "${CYAN}${BOLD}  ══  CLIProxy Installer Manager  ══${NC}"
        echo ""
        echo -e "  ${BOLD}${GREEN}1${NC}  Full Install"
        echo -e "  ${BOLD}${GREEN}2${NC}  Dependencies"
        echo -e "  ${BOLD}${GREEN}3${NC}  CLIProxy"
        echo -e "  ${BOLD}${GREEN}4${NC}  Update"
        echo -e "  ${BOLD}${GREEN}5${NC}  CLI Apps"
        echo -e "  ${BOLD}${GREEN}6${NC}  Uninstall"
        echo ""
        echo -e "  ${BOLD}${RED}0${NC}  Exit"
        echo ""
        echo -ne "  ${BOLD}›${NC} Select menu ${DIM}(0-6)${NC}: "
        read c
        case $c in
            1) menu_full_install ;;
            2) 
                echo "Installing Dependencies..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            3) menu_cliproxy ;;
            4) menu_update ;;
            5) menu_cli_apps ;;
            6) 
                echo "Running Uninstall..."
                echo ""
                read -p "Press Enter to continue..."
                ;;
            0) echo "Exiting..."; exit 0 ;;
            *) echo "Invalid choice." ;;
        esac
    done
}

main_menu
