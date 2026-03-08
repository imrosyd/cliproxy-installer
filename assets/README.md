# CLIProxy Installer Assets

This directory contains additional assets that will be installed during the CLIProxy installation process.

## Directory Structure

```
assets/
├── static/
│   └── dashboard.html      # Redesigned dashboard (factory.ai-inspired, monochrome)
└── scripts/
    ├── cp-db.sh             # Dashboard launcher with auto-start
    ├── cp-claude.sh         # Claude Code integration with model selection
    └── quota-fetcher.py     # Quota fetcher script (auto-refresh every 10 min)
```

## Files

### static/dashboard.html
Modern, professional dashboard with factory.ai-inspired monochrome design:
- **Auto dark/light theme** — follows OS preference, with manual toggle
- **4 main tabs** — Dashboard, Accounts, Quota, Settings
- **Real-time server status** — via lightweight `/health` endpoint
- **Live quota monitoring** — per-account quota bars with fallback cache
- **Responsive design** — works on desktop and mobile
- **XSS protection** — HTML escaping on all dynamic content

### scripts/cp-db.sh
Smart dashboard launcher (replaces file:// browsing):
- ✅ Opens `http://localhost:8317/dashboard.html` (not file://)
- Checks if server is running on port 8317
- Auto-starts server if needed (via `cp-start`)
- Opens dashboard in default browser (macOS/Linux)
- Portable port detection (ss → netstat → lsof fallback)
- Fetches quota data before opening
- Sets up cron job for auto-refresh (every 10 min)

### scripts/cp-claude.sh
Claude Code integration with interactive model selection:
- Auto-starts server if not running
- Fetches available models from `/v1/models`
- Interactive prompt for model selection
- Launches Claude Code with selected model

### scripts/quota-fetcher.py
Python script for quota data fetching:
- OAuth credentials can be set via env vars (`CLIPROXY_OAUTH_CLIENT_ID`, `CLIPROXY_OAUTH_CLIENT_SECRET`)
- Falls back to public Antigravity app credentials
- Fetches quota for all authenticated accounts
- Embeds quota data into dashboard.html

## Installation

These assets are automatically installed when you run the main installer:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install)"
```

The installer will:
1. Copy `dashboard.html` to `~/.cliproxyapi/static/dashboard.html`
2. Install helper scripts to `~/.cliproxyapi/scripts/`
3. Create aliases: `cp-db`, `cp-claude`, `cp-update`, etc.

## Usage

After installation, restart your terminal or source your shell config:

```bash
# Open dashboard (auto-starts server if needed)
cp-db

# Run Claude Code with proxy
cp-claude

# Or access dashboard directly
open http://localhost:8317/dashboard.html
```

## Key Features

✅ **HTTP not file://** — Dashboard opens via `http://localhost:8317` for full API access  
✅ **Portable port detection** — Works on systems without lsof by trying ss → netstat  
✅ **Modern dark/light theme** — Follows OS preference automatically  
✅ **OAuth flexibility** — Custom credentials via environment variables  
✅ **Auto-refresh** — Cron job updates quota every 10 minutes  
✅ **Error resilience** — Quota cache used when API is offline  

## Updates

To update assets to the latest version:
```bash
cp-update
```

This fetches the latest dashboard, scripts, and installer from the imrosyd fork on GitHub.
