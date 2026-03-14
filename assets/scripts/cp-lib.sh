#!/bin/bash

# Shared helpers for CLIProxy shell scripts.

cp_init_colors() {
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m'
}

cp_print_header() {
    local title="$1"
    local subtitle="${2:-}"
    echo -e "${CYAN}${BOLD}  ══  CLIProxy • ${title}  ══${NC}"
    if [ -n "$subtitle" ]; then
        echo -e "  ${DIM}${subtitle}${NC}"
    fi
    echo ""
}

cp_info()  { echo -e "${CYAN}[i]${NC} $*"; }
cp_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
cp_warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
cp_error() { echo -e "${RED}[ERROR]${NC} $*"; }

cp_die() {
    cp_error "$*"
    exit 1
}

cp_prompt() {
    local label="$1"
    local out_var="$2"
    local value=""
    echo -ne "  ${BOLD}›${NC} ${label}: "
    read -r value
    printf -v "$out_var" '%s' "$value"
}

cp_check_port() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -tlnp 2>/dev/null | grep -q ":$port "
        return $?
    fi
    if command -v netstat >/dev/null 2>&1; then
        netstat -tlnp 2>/dev/null | grep -q ":$port "
        return $?
    fi
    if command -v lsof >/dev/null 2>&1; then
        lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    fi
    return 1
}

cp_resolve_start_cmd() {
    if command -v cp-start >/dev/null 2>&1; then
        echo "cp-start"
        return 0
    fi
    if [ -x "$HOME/.cliproxyapi/scripts/start.sh" ]; then
        echo "$HOME/.cliproxyapi/scripts/start.sh"
        return 0
    fi
    return 1
}

cp_wait_for_port() {
    local port="$1"
    local seconds="${2:-10}"
    local i=1
    while [ "$i" -le "$seconds" ]; do
        if cp_check_port "$port"; then
            return 0
        fi
        sleep 1
        i=$((i + 1))
    done
    return 1
}

cp_ensure_server_running() {
    local port="$1"
    if cp_check_port "$port"; then
        cp_ok "Server already running on port $port"
        return 0
    fi

    cp_warn "Server not running on port $port, starting..."

    local start_cmd
    if ! start_cmd="$(cp_resolve_start_cmd)"; then
        cp_error "cp-start command not found. Please install CLIProxy first."
        return 1
    fi

    "$start_cmd" >/dev/null 2>&1 &
    cp_info "Waiting for server to start..."
    if cp_wait_for_port "$port" 10; then
        cp_ok "Server started successfully"
        return 0
    fi

    cp_error "Server failed to start. Please check logs."
    return 1
}

cp_open_url() {
    local url="$1"
    if [[ "${OSTYPE:-}" == "darwin"* ]]; then
        open "$url"
        return 0
    fi
    if [[ "${OSTYPE:-}" == "linux-gnu"* ]]; then
        if command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$url"
            return 0
        fi
        if command -v gnome-open >/dev/null 2>&1; then
            gnome-open "$url"
            return 0
        fi
    fi
    echo "Please open manually: $url"
    return 0
}

cp_get_python_bin() {
    command -v python3 2>/dev/null || command -v python 2>/dev/null || true
}

cp_ensure_cron_contains() {
    local match="$1"
    local line="$2"
    if ! command -v crontab >/dev/null 2>&1; then
        return 0
    fi
    if crontab -l 2>/dev/null | grep -q "$match"; then
        return 0
    fi
    (crontab -l 2>/dev/null; echo "$line") | crontab - 2>/dev/null || true
}
