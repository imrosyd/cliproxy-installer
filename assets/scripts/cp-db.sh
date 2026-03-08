#!/bin/bash

# ── Colors ──
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── CLIProxy Dashboard Launcher ──
# Checks if server is running, starts if needed, then opens dashboard

# Add timestamp to force cache busting
TIMESTAMP=$(date +%s)
DASHBOARD_URL="http://localhost:8317/dashboard.html?v=$TIMESTAMP"
PORT=8317

echo -e "${CYAN}${BOLD}  ══  CLIProxy Dashboard  ══${NC}"
echo ""

# Portable port check: tries ss, then netstat, then lsof
check_port() {
    local port=$1
    if command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep -q ":$port "
        return $?
    fi
    if command -v netstat &>/dev/null; then
        netstat -tlnp 2>/dev/null | grep -q ":$port "
        return $?
    fi
    if command -v lsof &>/dev/null; then
        lsof -i :"$port" -sTCP:LISTEN &>/dev/null
        return $?
    fi
    return 1
}

# Check if server is already running
if check_port $PORT; then
    echo -e "${GREEN}[OK] Server already running on port $PORT${NC}"
else
    echo -e "${YELLOW}[!] Server not running, starting now...${NC}"
    
    # Determine start command
    CP_START_CMD=""
    if command -v cp-start >/dev/null 2>&1; then
        CP_START_CMD="cp-start"
    elif [ -x "$HOME/.cliproxyapi/scripts/start.sh" ]; then
        CP_START_CMD="$HOME/.cliproxyapi/scripts/start.sh"
    fi

    if [ -n "$CP_START_CMD" ]; then
        "$CP_START_CMD" >/dev/null 2>&1 &
        echo -e "${YELLOW}Waiting for server to start...${NC}"
        
        # Wait up to 10 seconds for server to start
        for i in {1..10}; do
            sleep 1
            if check_port $PORT; then
                echo -e "${GREEN}[OK] Server started successfully${NC}"
                break
            fi
            if [ $i -eq 10 ]; then
                echo -e "${RED}[ERROR] Server failed to start. Please check logs.${NC}"
                exit 1
            fi
        done
    else
        echo -e "${RED}[ERROR] cp-start command not found. Please install CLIProxy first.${NC}"
        exit 1
    fi
fi

QUOTA_FETCHER="$HOME/.cliproxyapi/scripts/quota-fetcher.py"
if [ -f "$QUOTA_FETCHER" ] && command -v python3 >/dev/null 2>&1; then
    echo -e "${YELLOW}Fetching quota data...${NC}"
    python3 "$QUOTA_FETCHER" 2>/dev/null
    echo -e "${GREEN}[OK] Quota data updated.${NC}"
fi

echo ""
echo -e "${YELLOW}Opening dashboard: ${BOLD}$DASHBOARD_URL${NC}"
echo ""

# Open dashboard in default browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$DASHBOARD_URL"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$DASHBOARD_URL"
    elif command -v gnome-open >/dev/null 2>&1; then
        gnome-open "$DASHBOARD_URL"
    else
        echo "Please open manually: $DASHBOARD_URL"
    fi
else
    echo "Please open manually: $DASHBOARD_URL"
fi

echo -e "${GREEN}[OK] Dashboard opened successfully!${NC}"
