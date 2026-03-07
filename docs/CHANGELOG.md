# Changelog - CLIProxy Suite

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-03-07
### 🚀 Initial Release - The Elite AI Proxy Experience

This is the initial official release of the combined CLIProxy Installer and Management Suite, providing a seamless, automated, and professional experience for AI developers.

### ✨ Key Features
- **Universal Provider Integration**: 
  - **Auto-v1 Detection**: Automatically detects if an endpoint requires a `/v1` prefix and corrects it in the background.
  - **Model Discovery**: Automatically fetches all available models from OpenAI-compatible providers on registration.
  - **One-Click Add**: New "Add Provider" feature in the dashboard for instant, code-free expansion.
- **Elite Dashboard UI**:
  - Premium **Glassmorphism Design** with modern typography and sleek animations.
  - Real-time **Quota Monitoring** per account and per model.
  - Integrated **Raw Config Editor (YAML)** for advanced power users.
  - Instant server control (Start/Stop/Restart) directly from the browser.
- **Deep Tooling Integration**:
  - **`cp-droid`**: Optimized support for Factory.ai Droid with auto-syncing model lists.
  - **`cp-claude`**: One-command launch for Claude Code via the proxy.
  - **`cp-opencode`**: Instant OpenCode connection with live model refreshing.
- **Robustness & Performance**:
  - Smart **Port Conflict Resolution** ensures a smooth start every time.
  - Automated **Shortcuts & Aliases** (`cp-start`, `cp-login`, `cp-db`, etc.) for efficient terminal workflow.
  - Cross-distribution Linux support and enhanced macOS/Windows compatibility.

---

## [Previously in Beta]
*Historical beta/development milestones prior to the 1.0.0 release.*

### [Alpha/Beta Updates] - 2025-12-10 to 2026-03-06
- Initial Dashboard prototype with real-time status.
- Added `quota-fetcher.py` and cron-based background updates.
- Refactored `install-linux` for better Fish shell support.
- Developed `merge-config.go` for intelligent YAML merging.
- Fixed JSON syntax errors across Windows PowerShell scripts.
- Implemented `cp-uninstall` for comprehensive system cleanup.
