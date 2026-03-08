# Troubleshooting

Use this guide to diagnose common CLIProxy runtime issues. For install/update overview and architecture context, see [`README.md`](../README.md).

## Server won't start / ECONNREFUSED

```bash
cp-start
```

`cp-start` includes a watchdog and auto-restarts after crashes. If startup still fails:

```bash
# Check if port is already used
ss -tlnp | grep 8317

# Stop CLIProxy processes and retry
cp-stop
cp-start
```

---

## "Unknown model" errors (502)

CLIProxy auto-resolves model aliases. If you still get 502:

```bash
curl http://localhost:8317/api/system/info | python3 -m json.tool | grep -E "backend_models|alias_cache"
```

If `backend_models` is still 0, backend model loading is not complete yet. Wait a bit, then retry.

---

## Quota exhausted / requests failing

When quota is exhausted, CLIProxy automatically fails over to other account/provider candidates. If all candidates are exhausted, you may see:

```json
{"error": {"message": "no_candidate: all providers exhausted"}}
```

Next actions:
- Add more accounts with `cp-login`
- Wait for cooldown expiry (120 seconds)

---

## Dashboard shows "Offline"

```bash
curl http://localhost:8317/health
cp-start
```

If health endpoint is not responding, restart runtime via `cp-start`.

---

## Dashboard blank / data not loading

1. Open browser DevTools → Console and check red errors
2. Check Network tab: `/v0/management/auth-files` should return `200`
3. Hard refresh (`Ctrl+Shift+R`)

If management endpoints fail/404, run update installer to refresh runtime scripts.

---

## Account search not finding results

Search in the Accounts tab matches email, provider, type, and status. Try keywords:
- `copilot`
- `antigravity`
- `active`
- `error`

---

## Check logs

```bash
# Proxy alias/failover events appear in terminal where cp-start runs

# Backend log
tail -50 ~/.cliproxyapi/logs/backend.log

# Per-request error details
ls -t ~/.cliproxyapi/logs/error-v1-messages-*.log | head -5 | xargs tail -20
```

---

## Re-run update installer

Use this to refresh latest binary/scripts/static without resetting core auth data:

```bash
curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install | bash -- -update
```

---

## API endpoints for debugging

```bash
# Health
curl http://localhost:8317/health

# System info (model count, alias cache)
curl http://localhost:8317/api/system/info

# Account list
curl http://localhost:8317/v0/management/auth-files

# Usage stats
curl http://localhost:8317/v0/management/usage
```

---

## Still having issues?

Open an issue: [github.com/imrosyd/cliproxy-installer/issues](https://github.com/imrosyd/cliproxy-installer/issues)

Include:

```bash
curl http://localhost:8317/api/system/info
tail -30 ~/.cliproxyapi/logs/backend.log
```
