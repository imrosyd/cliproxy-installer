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
    cp_print_header "Update"
    cp_info "Running CLIProxy update..."
    if command -v cp-update &> /dev/null; then
        cp-update
    elif [ -f "$HOME/.cliproxyapi/scripts/start.sh" ]; then
        cp_info "Reinstalling CLIProxy..."
        if command -v go &> /dev/null; then
            TEMP_DIR=$(mktemp -d)
            git clone --depth 1 https://github.com/router-for-me/CLIProxyAPIPlus.git "$TEMP_DIR" 2>/dev/null
            cd "$TEMP_DIR" && go build -o cliproxyapi ./cmd/server 2>/dev/null
            mv -f cliproxyapi "$HOME/.cliproxyapi/bin/cliproxyapi" 2>/dev/null
            rm -rf "$TEMP_DIR"
            cp_ok "CLIProxy updated."
        else
            cp_error "Go is not installed. Please install Go first."
        fi
    else
        cp_error "CLIProxy not found. Please install CLIProxy first."
    fi
    echo ""
    read -p "Press Enter to continue..."
}

main_menu() {
    while true; do
        clear
        cp_print_header "Installer Manager"
        echo -e "  ${BOLD}${GREEN}1${NC}  Full Install"
        echo -e "  ${BOLD}${GREEN}2${NC}  Dependencies"
        echo -e "  ${BOLD}${GREEN}3${NC}  CLIProxy"
        echo -e "  ${BOLD}${GREEN}4${NC}  Update"
        echo -e "  ${BOLD}${GREEN}5${NC}  CLI Apps"
        echo -e "  ${BOLD}${GREEN}6${NC}  Uninstall"
        echo -e "  ${BOLD}${GREEN}7${NC}  Antigravity Manager"
        echo ""
        echo -e "  ${BOLD}${RED}0${NC}  Exit"
        echo ""
        cp_prompt "Select menu ${DIM}(0-7)${NC}" c
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
            7)
                if command -v cp-antigravity >/dev/null 2>&1; then
                    cp-antigravity
                elif [ -f "$HOME/.cliproxyapi/scripts/cp-antigravity.sh" ]; then
                    bash "$HOME/.cliproxyapi/scripts/cp-antigravity.sh"
                else
                    cp_warn "Antigravity Manager belum terpasang."
                    read -p "Press Enter to continue..."
                fi
                ;;
            0) echo "Exiting..."; exit 0 ;;
            *) cp_warn "Invalid choice." ;;
        esac
    done
}

main_menu
