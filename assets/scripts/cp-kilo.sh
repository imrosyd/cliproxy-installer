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

# ── Configuration ──
PROXY_URL="http://localhost:8317"
API_KEY="sk-dummy"
PORT=8317
KILOCODE_CONFIG_DIR="$HOME/.config/kilocode"
KILOCODE_CONFIG="$KILOCODE_CONFIG_DIR/kilocode.json"

cp_print_header "KiloCode" "Proxy: $PROXY_URL"

# Pass-through to kilocode CLI if args are present
if [ $# -gt 0 ]; then
    cp_ensure_server_running "$PORT" || exit 1
    sleep 1
    exec kilocode "$@"
fi

cp_ensure_server_running "$PORT" || exit 1
sleep 1

echo -e "${YELLOW}Checking for KiloCode CLI...${NC}"
if ! command -v kilocode > /dev/null 2>&1; then
    echo -e "${YELLOW}KiloCode CLI not found. Installing...${NC}"
    if command -v npm > /dev/null 2>&1; then
        npm install -g @kilocode/cli
    else
        echo -e "${RED}[ERROR] npm not found. Cannot install kilocode CLI.${NC}"
        echo "  Or try: npm install -g @kilocode/cli"
        exit 1
    fi
fi

echo ""

echo -e "${GREEN}[OK] Launching KiloCode via CLIProxy Proxy...${NC}"
echo -e "   ${DIM}Proxy: $PROXY_URL${NC}"
echo ""

# Interactive Mode: Fetch and select models
RESPONSE=$(curl -s -H "Authorization: Bearer $API_KEY" "$PROXY_URL/v1/models")
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to connect to proxy at $PROXY_URL${NC}"
    exit 1
fi

# Parse and group models using python3
GROUPED_OUTPUT=$(echo "$RESPONSE" | python3 -c "
import sys, json

data = json.load(sys.stdin)
models = [m['id'] for m in data.get('data', [])]
HIDDEN = {'text-embedding-3-small-inference', 'text-embedding-3-small',
          'text-embedding-ada-002', 'gemini-3.1-flash-image',
          'oswe-vscode-prime', 'oswe-vscode-secondary'}
models = [m for m in models if m not in HIDDEN]
# Deduplicate: e.g. claude-sonnet-4-5 == claude-sonnet-4.5
import re
def normalize_key(name):
    return re.sub(r'-(\d+)-(\d+)(?=$|-)', r'-\1.\2', name)

seen_normalized = {}
deduped = []
for m in models:
    nk = normalize_key(m)
    if nk not in seen_normalized:
        seen_normalized[nk] = m
        deduped.append(m)
    else:
        existing = seen_normalized[nk]
        if '.' in m and '-' in existing.replace(m.split('.')[0], ''):
            deduped = [m if x == existing else x for x in deduped]
            seen_normalized[nk] = m
models = deduped
families = {}
ORDER = ['Claude', 'GPT', 'Gemini', 'Grok', 'Other']
for m in sorted(models):
    ml = m.lower()
    if ml.startswith('claude'): fam = 'Claude'
    elif ml.startswith('gpt-') or ml.startswith('gpt.'): fam = 'GPT'
    elif ml.startswith('gemini'): fam = 'Gemini'
    elif ml.startswith('grok'): fam = 'Grok'
    else: fam = 'Other'
    families.setdefault(fam, []).append(m)
idx = 1
lines = []
for fam in ORDER:
    group = families.get(fam, [])
    if not group: continue
    lines.append(f'HEADER:{fam} ({len(group)})')
    for m in group:
        lines.append(f'MODEL:{idx}:{m}')
        idx += 1
print('\\n'.join(lines))
")

if [ -z "$GROUPED_OUTPUT" ]; then
    echo -e "${RED}[ERROR] No models found.${NC}"
    exit 1
fi

MODEL_ARRAY=()
while IFS= read -r line; do
    if [[ "$line" == MODEL:* ]]; then
        model="${line##*:}"
        MODEL_ARRAY+=("$model")
    fi
done <<< "$GROUPED_OUTPUT"

if [ ${#MODEL_ARRAY[@]} -eq 0 ]; then
    echo -e "${RED}[ERROR] No models found.${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}${BOLD}Available Models${NC} ${DIM}(${#MODEL_ARRAY[@]} total)${NC}:"
echo ""
while IFS= read -r line; do
    if [[ "$line" == HEADER:* ]]; then
        header="${line#HEADER:}"
        echo "  ── $header ──"
    elif [[ "$line" == MODEL:* ]]; then
        rest="${line#MODEL:}"
        idx="${rest%%:*}"
        model="${rest#*:}"
        printf "  %3s) %s\n" "$idx" "$model"
    fi
done <<< "$GROUPED_OUTPUT"
echo ""
read -p "Select model (1-${#MODEL_ARRAY[@]}): " selection

if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#MODEL_ARRAY[@]}" ]; then
    SELECTED_MODEL="${MODEL_ARRAY[$((selection-1))]}"
    echo ""
    echo -e "${GREEN}[OK] Selected model: ${BOLD}$SELECTED_MODEL${NC}"
    # Generate KiloCode config with ALL available models
    python3 - "$SELECTED_MODEL" <<'PYSCRIPT' 2>/dev/null
import json, urllib.request, os, sys

selected_model = sys.argv[1] if len(sys.argv) > 1 else ""

# Fetch ALL models from CLIProxy
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

# Build all models config for KiloCode
kilo_models = {}

for m in models:
    model_id = m.get("id", "")
    
    display = model_id.replace("-", " ").title()
    
    # Determine context and output limits
    if any(x in model_id for x in ["claude", "opus", "sonnet"]):
        ctx, out = 200000, 16384
    elif any(x in model_id for x in ["gemini", "flash"]):
        ctx, out = 1000000, 65536
    else:
        ctx, out = 128000, 16384
    
    kilo_models[model_id] = {
        "name": display,
        "inputPrice": 0,
        "outputPrice": 0,
        "contextWindow": ctx,
        "maxOutput": out
    }

# Use the selected model as default; pick a small model as fallback
default_model = f"cliproxy/{selected_model}" if selected_model else None
small_model = None

for mid in kilo_models:
    if not default_model:
        default_model = f"cliproxy/{mid}"
    if not small_model and any(x in mid for x in ["sonnet", "flash", "haiku"]):
        small_model = f"cliproxy/{mid}"

if not small_model and kilo_models:
    small_model = f"cliproxy/{list(kilo_models.keys())[-1]}"

# KiloCode config path
config_path = os.path.expanduser("~/.config/kilo/opencode.json")
os.makedirs(os.path.dirname(config_path), exist_ok=True)

config = {
    "$schema": "https://kilo.ai/config.json",
    "provider": {
        "cliproxy": {
            "name": "CLIProxy",
            "id": "cliproxy",
            "npm": "@ai-sdk/openai-compatible",
            "env": [],
            "options": {
                "baseURL": "http://localhost:8317/v1",
                "apiKey": "sk-dummy"
            },
            "models": kilo_models
        }
    },
    "model": default_model,
    "small_model": small_model
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"[OK] KiloCode config written ({len(kilo_models)} models, default: {selected_model})")
PYSCRIPT
    echo ""
    echo -e "${GREEN}[OK] Launching KiloCode with model: ${BOLD}$SELECTED_MODEL${NC}"
    echo -e "   ${DIM}Proxy: $PROXY_URL${NC}"
    echo ""
    exec kilocode
else
    echo -e "${RED}[ERROR] Invalid selection.${NC}"
    exit 1
fi
