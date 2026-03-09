# Quick Start

Version: `v2.0.1`

This guide focuses on fast onboarding. For architecture, failover, model alias details, and update behavior, see [`README.md`](../README.md).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install | bash
```

## Quick workflow

```bash
cp-login      # authenticate provider
cp-start      # start proxy
cp-db         # open dashboard
```

Dashboard: `http://localhost:8317/`

## Basic verification

```bash
curl http://localhost:8317/health
curl http://localhost:8317/api/system/info
```

## Need more help?

- Full troubleshooting: [`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- Command and architecture overview: [`README.md`](../README.md)

## Update note

If runtime scripts are outdated or out of sync, run the updater:

```bash
curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install | bash -- -update
```
