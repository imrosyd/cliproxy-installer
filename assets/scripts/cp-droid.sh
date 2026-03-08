#!/bin/bash

# ── Colors ──
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── CLIProxy + Factory.ai Droid Launcher ──
# Auto-starts CLIProxy if not running, then launches Droid

PROXY_URL="http://localhost:8317"
PORT=8317

echo -e "${CYAN}${BOLD}  ══  CLIProxy + Factory.ai Droid  ══${NC}"
echo ""

# Portable port check
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

# Check droid is installed
if ! command -v droid > /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Droid is not installed.${NC}"
    echo "   Install with: curl -fsSL https://app.factory.ai/cli | sh"
    exit 1
fi

echo -e "${GREEN}[OK] CLIProxy is running at $PROXY_URL${NC}"
echo ""

# Refresh Droid config with latest models from CLIProxy
python3 - <<'PYSCRIPT' 2>/dev/null
import json, urllib.request, os

try:
    req = urllib.request.Request("http://localhost:8317/v1/models", headers={"Authorization": "Bearer sk-dummy"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        models = data.get("data", [])
except:
    models = []

if not models:
    exit(0)

provider_tags = {
    "antigravity": "[Antigravity]", "gemini-cli": "[gemini-cli]",
    "github-copilot": "[Copilot]", "qwen": "[Qwen]",
    "iflow": "[iFlow]", "google": "[Google]",
}

custom_models = []
for m in models:
    model_id = m.get("id", "")
    owner = m.get("owned_by", "")
    display = " ".join(w.capitalize() for w in model_id.replace("-"," ").replace("."," ").replace("_"," ").split())
    tag = provider_tags.get(owner, f"[{owner.capitalize()}]" if owner else "")
    if tag and tag not in display:
        display = f"{display} {tag}"
    custom_models.append({"model_display_name": display, "model": model_id,
        "base_url": "http://localhost:8317/v1", "api_key": "sk-dummy", "provider": "openai"})

droid_file = os.path.expanduser("~/.factory/config.json")
os.makedirs(os.path.dirname(droid_file), exist_ok=True)
with open(droid_file, "w") as f:
    json.dump({"custom_models": custom_models}, f, indent=4)

print(f"[OK] Droid model list refreshed ({len(custom_models)} models available)")
PYSCRIPT

echo ""
echo -e "${GREEN}[OK] Launching Droid...${NC}"
echo -e "   ${DIM}Proxy: $PROXY_URL${NC}"
echo -e "   ${DIM}Config: ~/.factory/config.json${NC}"
echo ""

exec droid "$@"
