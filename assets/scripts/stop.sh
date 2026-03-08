#!/bin/bash
# ── Stop CLIProxy server (unified server on 8317 + backend on 8316) ──

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping CLIProxy server...${NC}"
pkill -f "$HOME/.cliproxyapi/scripts/unified-server.py" || true
pkill -f "$HOME/.cliproxyapi/bin/cliproxyapi" || true
# Backward-compatible fallback for old install paths.
pkill -f "cliproxyapi.*\.cliproxyapi/config.yaml" || true
echo -e "${GREEN}[OK] Server stopped${NC}"
