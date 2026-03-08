# Changelog - CLIProxy Suite

All notable changes to this project will be documented in this file.

---

## [2.0.0] - 2026-03-08

### Added
- Local dashboard account management endpoints in unified server:
  - `GET /v0/management/auth-files`
  - `DELETE /v0/management/auth-files/{id}`
- Auth file discovery now reads from configured `auth-dir` in `config.yaml` with safe fallback to `~/.cliproxyapi`.

### Fixed
- Graceful shutdown flow to avoid double cleanup between signal handler and `atexit`.
- Backend process lifecycle handling to reduce orphan process risk on stop/restart.
- Backend log file handle cleanup to avoid descriptor leaks during repeated restarts.
- Installer-generated `cp-db` port check using valid `lsof -i :$port` syntax.
- `cp-stop` process matching to avoid broad `pkill` collisions.
- Installer now sets executable bit for `cp-add-provider.py`.

### Changed
- Standardized v2 release baseline around `.cliproxyapi` paths with additional legacy cleanup in uninstall and Windows install flow.
- Unified server now rewrites backend success response model field to keep model identity consistent for clients.

---

## [1.3.1] - 2026-03-08

### Added
- **Install script refactored** — all embedded scripts now extract to `assets/scripts/`:
  - `start.sh` — CLIProxy server startup script
  - `stop.sh` — CLIProxy server shutdown script
  - `login.sh` — Interactive provider login menu
  - `login-url.sh` — Headless login URL printer (for VPS/headless servers)
  - `cp-add-provider.sh` — Custom provider management wrapper
  - `cp-opencode.sh` — OpenCode integration script
- **Install script copy-from-assets pattern** — all scripts check local `assets/scripts/` first, fall back to GitHub download
  - Ensures fresh installs always get latest script versions
  - Supports both offline (local) and online (GitHub) installations
- **Dashboard `/management/auth-files` endpoint** — new API endpoint exposing authenticated accounts with:
  - Account provider type and email
  - Available models for each provider
  - Auto-fetches models from backend on demand

### Fixed
- **GitHub Copilot not showing in dashboard** — `/management/auth-files` endpoint now returns all auth files
- **Dashboard showing "0 models"** — endpoint now includes model list per provider
- **Install script not updating files** — embedded heredocs replaced with asset copy pattern
- **Installer maintainability** — scripts now live in version-controlled `assets/scripts/` directory

### Changed
- **Install script structure** — reduced size by removing embedded heredocs, now references external scripts
- **Dashboard data flow** — accounts loaded from backend via new `/management/auth-files` API

---

## [1.1.0] - 2026-03-08

### Added
- **Auto-failover engine** — when an account hits quota (429/402/529), automatically tries:
  1. Another account on the same provider
  2. Same model on a different provider
  3. Best available model globally
  - 120-second cooldown per account after quota error
- **Smart model resolution** — any model ID is auto-mapped to the nearest backend model using token-similarity matching (no hardcoding)
  - Version normalization: `deepseek-v3.2 → v3` token for fuzzy matching
  - Provider-anchor filtering: `grok-*` only matches `grok-*` models, not cross-provider
  - Special case: `o1`, `o3`, `o4` → `gpt-4o`; `o1-mini`, `o3-mini`, `o4-mini` → `gpt-4o-mini`
- **Backend model refresh** — models refreshed every 30s (was 300s), with immediate refresh on 502 "unknown model" error
- **Config file watcher** — triggers model refresh automatically when `config.yaml` changes
- **Auto-restart watchdog** in `start.sh` — server restarts within 3 seconds if it crashes
- **Structured logging** — all Python logs now use `HH:MM:SS [TAG] message` format with color coding
- **Backend log separation** — Go binary output redirected to `~/.cliproxyapi/logs/backend.log`, no longer mixed in terminal
- **Dashboard: Models stat card** — shows total unique models across all accounts
- **Dashboard: Active Accounts list** — dashboard tab now shows all accounts with status badges and model counts
- **Dashboard: Search improvement** — account search now filters by email, provider, type, and status
- **Dashboard: `API_BASE` dynamic** — uses `window.location.origin` instead of hardcoded `localhost:8317`

### Changed
- Installer menu redesigned — no vertical border characters, consistent `══ title ══` style
- Login menu redesigned — provider list with descriptions, no box borders
- Success/update screens redesigned — clean format without `═══` boxes
- Optional section headers use `── Section ───` style

### Fixed
- `claude-haiku-4-5-20251001` and other canonical Anthropic model IDs no longer return 502 "unknown model"
- `grok-3` no longer incorrectly resolves to `gemini-3-flash`
- `llama-3.1-70b` no longer incorrectly resolves to a Gemini model (passes through)
- Model alias cache now cleared when backend model set changes

---

## [1.0.1] - 2026-03-07

### Fixed
- Fix 401 Missing API key error by proxying Anthropic headers and prioritizing `x-api-key`
- Dashboard: add Insights tab and improve account labeling

---

## [1.0.0] - 2026-03-07

### Initial Release

- Universal installer for macOS, Linux, Windows (Git Bash)
- Unified proxy server on port 8317, backend on port 8316
- Web Dashboard with accounts, settings, and config editor
- Supported providers: Antigravity, GitHub Copilot, Gemini CLI, Codex, Claude, Qwen, iFlow
- Commands: `cp-start`, `cp-stop`, `cp-login`, `cp-login-url`, `cp-db`, `cp-update`, `cp-claude`, `cp-opencode`, `cp-droid`, `cp-uninstall`
