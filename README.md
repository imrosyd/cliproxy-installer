# CLIProxy: Universal AI Proxy & Dashboard

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 2.0.1](https://img.shields.io/badge/Version-2.0.1-blue.svg)](https://github.com/imrosyd/cliproxy-installer) <!-- Dashboard v2.0.1 supported -->

**CLIProxy** is an installer and management suite for **CLIProxyAPIPlus**. Route AI model requests through a single OpenAI-compatible endpoint with automatic failover across accounts/providers when quota or routing issues happen.

---

## Why CLIProxy

- **Single local endpoint**: `http://localhost:8317/v1`
- **One-command install** (macOS, Linux, Windows Git Bash)
- **Automatic failover** for quota/rate-limit/provider-model issues
- **Local dashboard** for account status, usage, and insights

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install | bash
```

> Windows: run in **Git Bash** and make sure Go is installed.

---

## Quick Workflow (New Users)

### 1) Log in to a provider
```bash
cp-login
```

### 2) Start the proxy
```bash
cp-start
```

### 3) Open the dashboard
```bash
cp-db
```

Dashboard: `http://localhost:8317/`

---

## Command Reference

| Command | Description |
|---|---|
| `cp-login` | Interactive provider login |
| `cp-login-url` | URL/headless login |
| `cp-start` | Start/restart proxy (with watchdog) |
| `cp-stop` | Stop proxy |
| `cp-db` | Open web dashboard |
| `cp-update` | Update installer/runtime to latest |
| `cp-add-provider` | Add custom OpenAI-compatible provider |
| `cp-claude` | Launch Claude Code via CLIProxy |
| `cp-opencode` | Launch OpenCode via CLIProxy |
| `cp-kilo` | Launch KiloCode via CLIProxy (AI coding assistant, via CLIProxy endpoint) |
| `cp-droid` | Launch Factory.ai Droid via CLIProxy |
| `cp-antigravity` | Antigravity Manager (monitor quota) |
| `cp-uninstall` | Remove CLIProxy |

---

## Architecture Snapshot (Power Users)

CLIProxy runs in two layers:

1. **Unified Server (`unified-server.py`)**
   - Main OpenAI-compatible entrypoint (`/v1/...`)
   - Serves dashboard static files
   - Handles failover and model alias resolution

2. **Backend Binary (`cliproxyapi`)**
   - Handles provider routing/auth and available model inventory
   - Exposes management/metadata endpoints used by dashboard

Default local ports:
- Unified server: `8317`
- Backend: managed by runtime scripts

---

## Failover Behavior

When a request fails due to quota/rate limits or provider-model mismatch, CLIProxy tries:

1. another account on the **same provider**
2. a **different provider** with the same/equivalent model
3. the best available model candidate
4. returns error if all candidates fail

Account cooldown after quota error: **120 seconds**.

---

## Install vs Update

- **Fresh install**: cleans old installation and prepares a new runtime.
- **Update mode** (`cp-update` / `install-linux -update`): refreshes runtime binary/scripts/static without resetting core auth data.

For major changes, backing up important files under `~/.cliproxyapi/` is still recommended.

---

## File Locations

| Path | Description |
|---|---|
| `~/.cliproxyapi/config.yaml` | Main configuration |
| `~/.cliproxyapi/bin/cliproxyapi` | Backend binary |
| `~/.cliproxyapi/scripts/unified-server.py` | Unified server |
| `~/.cliproxyapi/static/dashboard.html` | Dashboard UI |
| `~/.cliproxyapi/logs/backend.log` | Backend logs |
| `~/.cliproxyapi/logs/error-v1-messages-*.log` | Per-request error logs |

---

## Debug Endpoints

```bash
curl http://localhost:8317/health
curl http://localhost:8317/api/system/info
curl http://localhost:8317/v0/management/auth-files
curl http://localhost:8317/v0/management/usage
```

---

## Quick Troubleshooting

- Full troubleshooting guide: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- If runtime scripts look outdated, run update installer:

```bash
curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install | bash -- -update
```

---

## Docs Index

- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [docs/CHANGELOG.md](docs/CHANGELOG.md)

---

## Support

- Issues: [github.com/imrosyd/cliproxy-installer/issues](https://github.com/imrosyd/cliproxy-installer/issues)
- Core library: [CLIProxyAPIPlus](https://github.com/router-for-me/CLIProxyAPIPlus)
