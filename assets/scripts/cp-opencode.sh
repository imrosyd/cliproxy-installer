#!/bin/bash

# ── Colors ──
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Configuration ──
PROXY_URL="http://localhost:8317"
PORT=8317
OPENCODE_CONFIG_DIR="$HOME/.config/opencode"
OPENCODE_CONFIG="$OPENCODE_CONFIG_DIR/opencode.json"

echo -e "${CYAN}${BOLD}  ══  CLIProxy + OpenCode  ══${NC}"
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

check_server() {
    check_port $PORT
}

# Auto-start proxy server if not running
if ! check_server; then
    echo -e "${YELLOW}[!] CLIProxy server not running on port $PORT. Auto-starting...${NC}"

    CP_START_CMD=""
    if command -v cp-start > /dev/null 2>&1; then
        CP_START_CMD="cp-start"
    elif [ -x "$HOME/.cliproxyapi/scripts/start.sh" ]; then
        CP_START_CMD="$HOME/.cliproxyapi/scripts/start.sh"
    fi

    if [ -n "$CP_START_CMD" ]; then
        "$CP_START_CMD" > /dev/null 2>&1 &
        echo -e "${YELLOW}Waiting for server...${NC}"

        for i in {1..10}; do
            sleep 1
            if check_server; then
                echo -e "${GREEN}[OK] Server started.${NC}"
                break
            fi
            if [ $i -eq 10 ]; then
                echo -e "${RED}[ERROR] Failed to auto-start server.${NC}"
                exit 1
            fi
        done
        sleep 1
    else
        echo -e "${RED}[ERROR] cp-start command not found. Cannot auto-start.${NC}"
        exit 1
    fi
fi

# Always refresh OpenCode config with latest models from CLIProxy
python3 - <<'PYSCRIPT' 2>/dev/null
import json, urllib.request, os

try:
    req = urllib.request.Request(
        "http://localhost:8317/v1/models",
        headers={"Authorization": "Bearer sk-dummy"}
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode())
        models = data.get("data", [])
except:
    models = []

if not models:
    exit(0)

opencode_models = {}
default_model = small_model = None

for m in models:
    model_id = m.get("id", "")
    owner = m.get("owned_by", "")
    display = model_id.replace("-", " ").title()

    # Determine context and output limits
    if any(x in model_id for x in ["claude", "opus", "sonnet"]):
        ctx, out = 200000, 16384
    elif any(x in model_id for x in ["gemini", "flash"]):
        ctx, out = 1000000, 65536
    else:
        ctx, out = 128000, 16384

    opencode_models[model_id] = {
        "name": display,
        "inputPrice": 0,
        "outputPrice": 0,
        "contextWindow": ctx,
        "maxOutput": out
    }

    # Auto-pick defaults (prefer opus/pro, then sonnet, then first available)
    if not default_model and any(x in model_id for x in ["opus", "pro"]):
        default_model = f"cliproxy/{model_id}"
    if not small_model and any(x in model_id for x in ["sonnet", "flash"]):
        small_model = f"cliproxy/{model_id}"

if not default_model and opencode_models:
    default_model = f"cliproxy/{list(opencode_models.keys())[0]}"
if not small_model and opencode_models:
    small_model = f"cliproxy/{list(opencode_models.keys())[-1]}"

config_path = os.path.expanduser("~/.config/opencode/opencode.json")
os.makedirs(os.path.dirname(config_path), exist_ok=True)

config = {
    "provider": {
        "cliproxy": {
            "name": "CLIProxy",
            "id": "cliproxy",
            "env": [],
            "options": {
                "baseURL": "http://localhost:8317/v1",
                "apiKey": "sk-dummy"
            },
            "models": opencode_models
        }
    },
    "model": default_model,
    "small_model": small_model
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"[OK] OpenCode model list refreshed ({len(opencode_models)} models available)")
PYSCRIPT

# Check if OpenCode is installed
if ! command -v opencode > /dev/null 2>&1; then
    echo "OpenCode not found. Installing..."

    if command -v bun > /dev/null 2>&1; then
        bun install -g opencode-ai@latest
    elif command -v npm > /dev/null 2>&1; then
        npm install -g opencode-ai@latest
    else
        echo "Error: Neither npm nor bun found."
        echo "Or try: curl -fsSL https://opencode.ai/install | bash"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}[OK] Launching OpenCode with CLIProxy...${NC}"
echo -e "   ${DIM}Proxy: $PROXY_URL${NC}"
echo ""

exec opencode "$@"
