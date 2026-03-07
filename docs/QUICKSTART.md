# 🚀 Dashboard Quick Start Guide

## ⚡ Instant Access

### 1. Open the Dashboard
```bash
cp-db
```

The dashboard will:
- ✅ Auto-detect if the server is running
- ✅ Auto-start the server if needed (via `cp-start`)
- ✅ Fetch latest quota data
- ✅ Open in your default browser

**Or access directly:**
```
http://localhost:8317/dashboard.html
```

---

## 🎯 Dashboard Tabs

### Dashboard Tab
- **Server Status** — Live connection check
- **Account Count** — Total authenticated accounts
- **Quota Overview** — Quick snapshot of all quotas
- **Auto-Refresh** — Updates every 30 seconds by default

### Accounts Tab
- Lists all authenticated AI provider accounts
- Shows per-account quota usage as bar charts
- Displays account email and provider type

### Quota Tab
- Detailed quota breakdown per account
- Model-specific quota information
- Historical usage if available

### Settings Tab
- Server configuration
- API key management
- Manual quota refresh button

---

## 🌓 Theme & Appearance

### Auto Dark/Light Mode
The dashboard automatically follows your OS preference:
- **macOS:** System Preferences → Appearance
- **Linux:** GNOME Settings / KDE Settings
- **Windows:** Settings → Colors → Choose your mode

### Manual Theme Toggle
Click the **Theme Toggle** button (☀️/🌙) in the top-right corner to override OS preference.

Your choice is saved to `localStorage` and persists across sessions.

---

## 🔄 Auto-Refresh & Quota Updates

### Dashboard Auto-Refresh
The Dashboard updates every 30 seconds to show:
- Current server status
- Latest account list
- Real-time quota cache

### Manual Quota Fetch
Run anytime to refresh quota data:
```bash
python3 ~/.cli-proxy-api/scripts/quota-fetcher.py
```

### Automatic Cron Job
After first `cp-db` run, a cron job is installed to refresh quota automatically:
```bash
# Fetches quota every 10 minutes
*/10 * * * * python3 ~/.cli-proxy-api/scripts/quota-fetcher.py >/dev/null 2>&1
```

---

## 💡 Pro Tips

1. **Bookmark the URL**: `http://localhost:8317/dashboard.html`
   - Save time next time by visiting directly
   
2. **Always use `cp-db`**: 
   - Ensures server is running before opening dashboard
   - Auto-fetches latest quota data

3. **Check Settings tab**: 
   - Verify API keys are loaded correctly
   - See which accounts are connected

4. **Server offline?**
   - Dashboard still shows cached quota data
   - Most recent quota information is preserved

---

## 🚀 Next Steps

- [Authentication Setup](https://github.com/imrosyd/cliproxy-installer#how-to-use) — Login to providers
- [Troubleshooting](TROUBLESHOOTING.md) — Solve common issues
- [Version History](CHANGELOG.md) — See what's new
