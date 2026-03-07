#!/bin/bash

# Configuration
PROXY_URL="http://localhost:8317"
API_KEY="sk-dummy"
PORT=8317

# Export environment variables for Claude Code
export ANTHROPIC_BASE_URL="$PROXY_URL"
export ANTHROPIC_API_KEY="$API_KEY"

# If arguments are provided, pass them directly to claude
if [ "$#" -gt 0 ]; then
    exec claude "$@"
fi

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

# Function to check if server is running
check_server() {
    check_port $PORT
}

# Auto-start logic
if ! check_server; then
    echo "⚠️  Server not running on port $PORT. Auto-starting..."
    
    # Determine start command
    CP_START_CMD=""
    if command -v cp-start >/dev/null 2>&1; then
        CP_START_CMD="cp-start"
    elif [ -x "$HOME/.cli-proxy-api/scripts/start.sh" ]; then
        CP_START_CMD="$HOME/.cli-proxy-api/scripts/start.sh"
    fi

    if [ -n "$CP_START_CMD" ]; then
        "$CP_START_CMD" >/dev/null 2>&1 &
        echo "⏳ Waiting for server..."
        
        # Wait up to 10 seconds
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
        # Give it a small extra buffer for API readiness
        sleep 1
    else
        echo "❌ cp-start command not found. Cannot auto-start."
        exit 1
    fi
fi

# Interactive Mode: Fetch and select models
echo "🔍 Fetching available models..."

# Fetch models using curl
RESPONSE=$(curl -s -H "Authorization: Bearer $API_KEY" "$PROXY_URL/v1/models")

# Check if curl failed (even after auto-start attempt)
if [ $? -ne 0 ]; then
    echo "❌ Failed to connect to proxy at $PROXY_URL"
    exit 1
fi

# Parse models using python3 to ensure compatibility
MODELS=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'data' in data:
        for model in data['data']:
            print(model['id'])
    else:
        print('ERROR: Invalid JSON format')
except Exception as e:
    print(f'ERROR: {e}')
")

if [[ "$MODELS" == ERROR* ]]; then
    echo "❌ Failed to parse models."
    echo "Response: $RESPONSE"
    exit 1
fi

# Convert to array
MODEL_ARRAY=($MODELS)

if [ ${#MODEL_ARRAY[@]} -eq 0 ]; then
    # Fallback/Retry once if empty (sometimes happens on fresh start)
    sleep 1
    RESPONSE=$(curl -s -H "Authorization: Bearer $API_KEY" "$PROXY_URL/v1/models")
    MODELS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(' '.join([m['id'] for m in json.load(sys.stdin)['data']]))" 2>/dev/null)
    MODEL_ARRAY=($MODELS)
    
    if [ ${#MODEL_ARRAY[@]} -eq 0 ]; then
         echo "❌ No models found."
         exit 1
    fi
fi

echo "🤖 Available Models:"
i=1
for model in "${MODEL_ARRAY[@]}"; do
    echo "  $i) $model"
    ((i++))
done

echo ""
read -p "Select model (1-${#MODEL_ARRAY[@]}): " selection

if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#MODEL_ARRAY[@]}" ]; then
    SELECTED_MODEL="${MODEL_ARRAY[$((selection-1))]}"
    echo ""
    echo "🚀 Launching Claude Code with model: $SELECTED_MODEL"
    echo "   (Env: ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL)"
    echo ""
    exec claude --model "$SELECTED_MODEL"
else
    echo "❌ Invalid selection."
    exit 1
fi
