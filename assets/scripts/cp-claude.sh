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
API_KEY="sk-dummy"
PORT=8317

# Export environment variables for Claude Code
export ANTHROPIC_BASE_URL="$PROXY_URL"
export ANTHROPIC_API_KEY="$API_KEY"

# Parse cp-claude specific flags (kept internal)
FORCE_SKILL_INSTALL=0
CLAUDE_ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--force-skill-install" ]; then
        FORCE_SKILL_INSTALL=1
    else
        CLAUDE_ARGS+=("$arg")
    fi
done

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

# Ensure Superpowers plugin is installed once (best-effort)
SUPERPOWERS_MARKER="$HOME/.cliproxyapi/.superpowers_installed"
ensure_superpowers() {
    # Skip if already marked as installed
    if [ "$FORCE_SKILL_INSTALL" -ne 1 ] && [ -f "$SUPERPOWERS_MARKER" ]; then
        return 0
    fi

    # Skip silently if Claude CLI is unavailable
    if ! command -v claude >/dev/null 2>&1; then
        return 0
    fi

    echo -e "${YELLOW}Checking Superpowers plugin...${NC}"

    # Fast path: plugin already installed
    if claude -p "/plugin update superpowers" >/dev/null 2>&1; then
        mkdir -p "$(dirname "$SUPERPOWERS_MARKER")"
        touch "$SUPERPOWERS_MARKER"
        echo -e "${GREEN}[OK] Superpowers ready.${NC}"
        return 0
    fi

    echo -e "${YELLOW}Installing Superpowers plugin...${NC}"
    claude -p "/plugin marketplace add obra/superpowers-marketplace" >/dev/null 2>&1 || true

    if claude -p "/plugin install superpowers@superpowers-marketplace" >/dev/null 2>&1; then
        claude -p "/plugin update superpowers" >/dev/null 2>&1 || true
        mkdir -p "$(dirname "$SUPERPOWERS_MARKER")"
        touch "$SUPERPOWERS_MARKER"
        echo -e "${GREEN}[OK] Superpowers installed automatically.${NC}"
    else
        echo -e "${YELLOW}[!] Auto-install Superpowers failed.${NC}"
        echo "   Run manually:"
        echo "   claude -p \"/plugin marketplace add obra/superpowers-marketplace\""
        echo "   claude -p \"/plugin install superpowers@superpowers-marketplace\""
    fi
}


# Function to check if server is running
check_server() {
    check_port $PORT
}

ensure_superpowers

# If arguments are provided, pass them directly to claude
if [ ${#CLAUDE_ARGS[@]} -gt 0 ]; then
    exec claude "${CLAUDE_ARGS[@]}"
fi

# Auto-start logic
if ! check_server; then
    echo -e "${YELLOW}[!] Server not running on port $PORT. Auto-starting...${NC}"
    
    # Determine start command
    CP_START_CMD=""
    if command -v cp-start >/dev/null 2>&1; then
        CP_START_CMD="cp-start"
    elif [ -x "$HOME/.cliproxyapi/scripts/start.sh" ]; then
        CP_START_CMD="$HOME/.cliproxyapi/scripts/start.sh"
    fi

    if [ -n "$CP_START_CMD" ]; then
        "$CP_START_CMD" >/dev/null 2>&1 &
        echo -e "${YELLOW}Waiting for server...${NC}"
        
        # Wait up to 10 seconds
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
        # Give it a small extra buffer for API readiness
        sleep 1
    else
        echo -e "${RED}[ERROR] cp-start command not found. Cannot auto-start.${NC}"
        exit 1
    fi
fi

# Interactive Mode: Fetch and select models
echo -e "${YELLOW}Fetching available models...${NC}"

# Fetch models using curl
RESPONSE=$(curl -s -H "Authorization: Bearer $API_KEY" "$PROXY_URL/v1/models")

# Check if curl failed (even after auto-start attempt)
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
# Keep the dot-variant as canonical, skip the dash-variant
def normalize_key(name):
    \"\"\"Normalize model name for dedup: replace dash-separated version with dots.\"\"\"
    import re
    # Match patterns like name-4-5 or name-4-6 at end → name-4.5, name-4.6
    return re.sub(r'-(\d+)-(\d+)(?=$|-)', r'-\1.\2', name)

seen_normalized = {}
deduped = []
for m in models:
    nk = normalize_key(m)
    if nk not in seen_normalized:
        seen_normalized[nk] = m
        deduped.append(m)
    else:
        # Keep the dot-variant (shorter/canonical), skip dash-variant
        existing = seen_normalized[nk]
        if '.' in m and '-' in existing.replace(m.split('.')[0], ''):
            # Current has dots, replace existing
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
        model="${line#MODEL:*:}"
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
        # Extract index and model name
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
    echo -e "${GREEN}[OK] Launching Claude Code with model: ${BOLD}$SELECTED_MODEL${NC}"
    echo -e "   ${DIM}Env: ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL${NC}"
    echo ""
    exec claude --model "$SELECTED_MODEL"
else
    echo -e "${RED}[ERROR] Invalid selection.${NC}"
    exit 1
fi
