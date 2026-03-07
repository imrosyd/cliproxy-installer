# 🌌 CLIProxy: Ultimate Universal Proxy & Dashboard

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.0.0](https://img.shields.io/badge/Version-1.0.0-blue.svg)](https://github.com/imrosyd/cliproxy-installer)

**CLIProxy** is a high-performance, automated installer and management suite for **CLIProxyAPIPlus**. It seamlessly translates custom AI models (Claude 3.5, Gemini 1.5, GPT-5, etc.) into OpenAI-compatible endpoints for use in modern AI tools like **Droid**, **Cursor**, **Claude Code**, and **OpenCode**.

---

## ✨ Key Features

- **🚀 Instant Setup**: One-click, cross-platform installer for macOS, Linux, and Windows (Git Bash).
- **🎨 Elite Dashboard**: Stunning, glassmorphism-inspired UI for real-time monitoring and configuration.
- **🛡️ Smart Conflict Resolution**: Automatically prevents port conflicts and handles authentication errors gracefully.
- **🔌 Universal Custom Providers**: Add any OpenAI-compatible service with **Auto-Detection** and **Auto-Fetch** capabilities.
- **🔄 Live Synchronization**: Model lists are dynamically synced across all connected tools (Droid, OpenCode, etc.).
- **⚡ Supercharged Shortcuts**: Intuitive command-line aliases for total control (`cp-start`, `cp-login`, `cp-db`).

---

## 🚀 Quick Start (Universal)

Run this single command to install or update to the latest version:

```bash
curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install | bash
```

> **Note**: For Windows, run this in **Git Bash**. Ensure [Go](https://go.dev/dl/) is installed.

---

## 📖 Essential Workflow

### 1. Authenticate
Connect your favorite AI providers (Claude, Gemini, Copilot, etc.):
```bash
cp-login
```

### 2. Ignite the Proxy
Start the unified server (Backend API + Dashboard):
```bash
cp-start
```

### 3. Launch the Control Center
Open the beautiful Web Dashboard to manage accounts and settings:
```bash
cp-db
```
*Accessible at: `http://localhost:8317/dashboard.html`*

---

## 🛠️ Advanced Features

### 🧩 Adding Custom Providers (Plug-and-Play)
Our new **Interactive Add** feature makes integrating 3rd-party APIs effortless:
```bash
cp-add-provider
```
- **Auto-v1 Detection**: Automatically corrects Base URLs (e.g., adds `/v1` if needed).
- **Auto-Model Discovery**: Instantly fetches all available models from the provider.
- **Dynamic Integration**: Models appear in the Dashboard and all connected tools immediately.

### 🍱 Integrated AI Toolsets
- **`cp-claude`**: Launch Claude Code via CLIProxy.
- **`cp-droid`**: Optimized integration with [Factory.ai Droid](https://docs.factory.ai).
- **`cp-opencode`**: Fast-launch OpenCode with live-synced models.

---

## ⌨️ Command Reference

| Shortcut | Action |
| :--- | :--- |
| **`cp-login`** | Interactive menu to authenticate AI providers |
| **`cp-start`** | Cleanly start/restart the unified proxy server |
| **`cp-stop`** | Halt all background processes |
| **`cp-db`** | Launch the Premium Web Dashboard |
| **`cp-add-provider`** | Add any OpenAI-compatible API dynamically |
| **`cp-update`** | Update core binary, installer, and dashboard |
| **`cp-uninstall`** | Fully remove all components and configurations |

---

## 📂 Architecture & Paths

- **Core Binary**: `~/bin/cliproxyapi-plus`
- **Configuration**: `~/.cli-proxy-api/config.yaml` (YAML-based)
- **Static Assets**: `~/.cli-proxy-api/static/`
- **Utility Scripts**: `~/.cli-proxy-api/scripts/`

---

## 🤝 Community & Support

- **Maintained by**: [imrosyd](https://github.com/imrosyd)
- **Core Library**: [CLIProxyAPIPlus](https://github.com/router-for-me/CLIProxyAPIPlus) (by khmuhtadin)

For troubleshooting, visit our [Extended Guide](docs/TROUBLESHOOTING.md) or check the **Settings** tab in your Dashboard.

---

<p align="center">
  <i>Empowering your local AI workflow with elegance and speed.</i>
</p>
