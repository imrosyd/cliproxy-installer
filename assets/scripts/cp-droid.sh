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

# ── CLIProxy + Factory.ai Droid Launcher ──
# Auto-starts CLIProxy if not running, shows model picker, then launches Droid

PROXY_URL="http://localhost:8317"
API_KEY="sk-dummy"
PORT=8317

cp_print_header "Factory Droid" "Proxy: $PROXY_URL"

# If arguments are provided, skip interactive mode and pass directly to droid
if [ $# -gt 0 ]; then
    cp_ensure_server_running "$PORT" || exit 1
    sleep 1
    exec droid "$@"
fi

cp_ensure_server_running "$PORT" || exit 1
sleep 1

# Check droid is installed
if ! command -v droid > /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Droid is not installed.${NC}"
    echo "   Install with: curl -fsSL https://app.factory.ai/cli | sh"
    exit 1
fi

# Interactive Mode: Fetch and select models
echo -e "${YELLOW}Fetching available models...${NC}"

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

# Filter out non-chat models (embeddings, image-gen, internal tools)
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

# Classify into families
families = {}
ORDER = ['Claude', 'GPT', 'Gemini', 'Grok', 'Other']
for m in sorted(models):
    ml = m.lower()
    if ml.startswith('claude'):
        fam = 'Claude'
    elif ml.startswith('gpt-') or ml.startswith('gpt.'):
        fam = 'GPT'
    elif ml.startswith('gemini'):
        fam = 'Gemini'
    elif ml.startswith('grok'):
        fam = 'Grok'
    else:
        fam = 'Other'
    families.setdefault(fam, []).append(m)

idx = 1
lines = []
for fam in ORDER:
    group = families.get(fam, [])
    if not group:
        continue
    lines.append(f'HEADER:{fam} ({len(group)})')
    for m in group:
        lines.append(f'MODEL:{idx}:{m}')
        idx += 1
print('\n'.join(lines))
")

if [ -z "$GROUPED_OUTPUT" ]; then
    echo -e "${RED}[ERROR] No models found.${NC}"
    exit 1
fi

# Build flat model array for selection
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

# Display grouped models
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

    # Generate Droid config with selected model as default
    python3 - "$SELECTED_MODEL" <<'PYSCRIPT' 2>/dev/null
import json, urllib.request, os, sys

selected_model = sys.argv[1] if len(sys.argv) > 1 else ""

try:
    req = urllib.request.Request(
        "http://localhost:8317/v1/models",
        headers={"Authorization": "Bearer sk-dummy"}
    )
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
# Put the selected model first so Droid uses it as default
for m in models:
    model_id = m.get("id", "")
    owner = m.get("owned_by", "")
    display = " ".join(w.capitalize() for w in model_id.replace("-"," ").replace("."," ").replace("_"," ").split())
    tag = provider_tags.get(owner, f"[{owner.capitalize()}]" if owner else "")
    if tag and tag not in display:
        display = f"{display} {tag}"
    entry = {
        "model_display_name": display,
        "model": model_id,
        "base_url": "http://localhost:8317/v1",
        "api_key": "sk-dummy",
        "provider": "openai"
    }
    if model_id == selected_model:
        custom_models.insert(0, entry)
    else:
        custom_models.append(entry)

droid_file = os.path.expanduser("~/.factory/config.json")
os.makedirs(os.path.dirname(droid_file), exist_ok=True)
with open(droid_file, "w") as f:
    json.dump({"custom_models": custom_models}, f, indent=4)

print(f"[OK] Droid config written ({len(custom_models)} models, default: {selected_model})")
PYSCRIPT

    echo ""
    echo -e "${GREEN}[OK] Launching Droid with model: ${BOLD}$SELECTED_MODEL${NC}"
    echo -e "   ${DIM}Proxy: $PROXY_URL${NC}"
    echo -e "   ${DIM}Config: ~/.factory/config.json${NC}"
    echo ""
    exec droid --model "$SELECTED_MODEL"
else
    echo -e "${RED}[ERROR] Invalid selection.${NC}"
    exit 1
fi
