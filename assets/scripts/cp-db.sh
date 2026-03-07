#!/bin/bash

# CLIProxy Dashboard Launcher
# Checks if server is running, starts if needed, then opens dashboard

# Add timestamp to force cache busting
TIMESTAMP=$(date +%s)
DASHBOARD_URL="http://localhost:8317/dashboard.html?v=$TIMESTAMP"
PORT=8317

echo "🔮 CLIProxy Dashboard Launcher"
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
    echo "✅ Server already running on port $PORT"
else
    echo "⚠️  Server not running, starting now..."
    
    # Determine start command
    CP_START_CMD=""
    if command -v cp-start >/dev/null 2>&1; then
        CP_START_CMD="cp-start"
    elif [ -x "$HOME/.cli-proxy-api/scripts/start.sh" ]; then
        CP_START_CMD="$HOME/.cli-proxy-api/scripts/start.sh"
    fi

    if [ -n "$CP_START_CMD" ]; then
        "$CP_START_CMD" >/dev/null 2>&1 &
        echo "⏳ Waiting for server to start..."
        
        # Wait up to 10 seconds for server to start
        for i in {1..10}; do
            sleep 1
            if check_port $PORT; then
                echo "✅ Server started successfully"
                break
            fi
            if [ $i -eq 10 ]; then
                echo "❌ Server failed to start. Please check logs."
                exit 1
            fi
        done
    else
        echo "❌ cp-start command not found. Please install CLIProxy first."
        exit 1
    fi
fi

QUOTA_FETCHER="$HOME/.cli-proxy-api/scripts/quota-fetcher.py"
if [ -f "$QUOTA_FETCHER" ] && command -v python3 >/dev/null 2>&1; then
    echo "🔄 Fetching quota data..."
    python3 "$QUOTA_FETCHER" 2>/dev/null
    echo "✅ Quota data updated."
fi

echo ""
echo "🌐 Opening dashboard: $DASHBOARD_URL"
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

echo "✨ Dashboard opened successfully!"
