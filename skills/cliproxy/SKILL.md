---
name: cliproxy
description: Manage and interact with the local CLIProxy Unified Server. Use this to start the proxy, add OpenAI-compatible models, and troubleshoot API connections.
---

# CLIProxy Management Skill

This skill provides instructions on how to interact with the user's local CLIProxy Unified Server. CLIProxy is a tool that provides local OpenAI-compatible endpoints by proxying requests to various AI providers (Claude, Gemini, Copilot, etc.).

## When to Use

Use this skill when:
- The user asks you to start, stop, or restart CLIProxy.
- The user asks you to add a new custom AI provider or model to their local configuration.
- You need to troubleshoot connection issues to local AI endpoints (`http://localhost:8317/v1`).
- The user asks you to check their CLIProxy configuration.

## Core Commands

CLIProxy provides several global terminal aliases that you can run on the user's behalf:

1. **`cp-start`**: Starts the CLIProxy unified server on port `8317`. Automatically resolves port conflicts.
2. **`cp-stop`**: Completely stops all CLIProxy background processes.
3. **`cp-update`**: Securely updates the CLIProxy core binary and installer components to the latest version.
4. **`cp-login`**: Opens an interactive login menu for authenticating with official AI providers.
5. **`cp-add-provider`**: Interactively adds a custom OpenAI-Compatible endpoint dynamically to the system's `config.yaml`.
6. **`cp-db`**: Launches the local web dashboard for monitoring server status and quotas.

## Configuration File

The primary configuration file is located at: `~/.cli-proxy-api/config.yaml`
- Use this file to manually inspect registered `openai-compatibility` providers and their `models`.
- Do not manually edit the YAML structure unless absolutely necessary; prefer advising the user to use `cp-add-provider` or the interactive `cp-login`.

## Troubleshooting

- **"Address already in use" on port 8316/8317**: Run `cp-start` to cleanly restart the server. It handles killing lingering processes automatically.
- **"401 Unauthorized" connecting to endpoints**: The user may need to re-authenticate via `cp-login`.
- **Finding available models**: Read the `openai-compatibility` list in `~/.cli-proxy-api/config.yaml` to see exactly which models the user has configured.

## Steps for Adding Custom Providers

If the user wants you to add a new OpenAI-Compatible provider (e.g., local vLLM or 3rd party API):
1. Gather the **Provider Name**, **Base URL** (e.g., `http://localhost:11434/v1`), and **API Key**.
2. Instead of editing `config.yaml` manually, run `python3 ~/.cli-proxy-api/scripts/cp-add-provider.py` or use `send_command_input` to pass the credentials through `cp-add-provider`.
3. Inform the user to run `cp-start` to apply the changes.
