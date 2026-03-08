#!/bin/bash

# ── Colors ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping any existing CLIProxy instances...${NC}"
if [ -f "$HOME/.cliproxyapi/scripts/stop.sh" ]; then
    bash "$HOME/.cliproxyapi/scripts/stop.sh" >/dev/null 2>&1
fi
echo -e "${YELLOW}Starting CLIProxy on http://localhost:8317${NC}"
if [ -f "$HOME/.cliproxyapi/scripts/unified-server.py" ] && command -v python3 &>/dev/null; then
    python3 "$HOME/.cliproxyapi/scripts/unified-server.py"
else
    echo -e "${YELLOW}[!] Unified server not available, starting API-only mode${NC}"
    if [ -x "$HOME/.cliproxyapi/bin/cliproxyapi" ]; then
        "$HOME/.cliproxyapi/bin/cliproxyapi" --config "$HOME/.cliproxyapi/config.yaml"
    fi
fi
