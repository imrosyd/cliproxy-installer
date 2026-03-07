#!/bin/bash

# CLIProxy + Factory.ai Droid Launcher
# Auto-starts CLIProxy if not running, then launches Droid

PROXY_URL="http://localhost:8317"
PORT=8317

echo "🤖 CLIProxy + Factory.ai Droid"
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
    echo "⚠️  CLIProxy server not running on port $PORT. Auto-starting..."

    CP_START_CMD=""
    if command -v cp-start > /dev/null 2>&1; then
        CP_START_CMD="cp-start"
    elif [ -x "$HOME/.cli-proxy-api/scripts/start.sh" ]; then
        CP_START_CMD="$HOME/.cli-proxy-api/scripts/start.sh"
    fi

    if [ -n "$CP_START_CMD" ]; then
        "$CP_START_CMD" > /dev/null 2>&1 &
        echo "⏳ Waiting for server..."

        for i in {1..10}; do
            sleep 1
            if check_server; then
                echo "✅ Server started."
                break
            fi
            if [ $i -eq 10 ]; then
                echo "❌ Failed to auto-start server."
                exit 1
            fi
        done
        sleep 1
    else
        echo "❌ cp-start command not found. Cannot auto-start."
        exit 1
    fi
fi

# Check droid is installed
if ! command -v droid > /dev/null 2>&1; then
    echo "❌ Droid is not installed."
    echo "   Install with: curl -fsSL https://app.factory.ai/cli | sh"
    exit 1
fi

echo "✅ CLIProxy is running at $PROXY_URL"
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

print(f"🔄 Droid model list refreshed ({len(custom_models)} models available)")
PYSCRIPT

echo ""
echo "🚀 Launching Droid..."
echo "   Proxy: $PROXY_URL"
echo "   Config: ~/.factory/config.json"
echo ""

exec droid "$@"
