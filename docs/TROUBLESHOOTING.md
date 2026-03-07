# 🔧 Dashboard Troubleshooting Guide

## ✅ Quick Fixes

### Problem: Dashboard shows "0% quota" or no data

**Cause**: Quota data hasn't been fetched yet, or API is not responding

**Solution**: Manually fetch quota data

```bash
# Run the quota fetcher script
python3 ~/.cli-proxy-api/scripts/quota-fetcher.py

# Or use the Settings tab "Refresh Quota" button
```

**Advanced**: Check OAuth credentials (if using custom ones)
```bash
export CLIPROXY_OAUTH_CLIENT_ID="your-client-id"
export CLIPROXY_OAUTH_CLIENT_SECRET="your-client-secret"
python3 ~/.cli-proxy-api/scripts/quota-fetcher.py
```

---

### Problem: "Cannot connect to server" or dashboard won't load

**Cause**: Server is not running or port 8317 is blocked

**Solution**: Use `cp-db` to auto-start

```bash
# This will auto-start the server if needed
cp-db
```

**Or start manually:**
```bash
# Start the proxy server
cp-start

# Check if it's running
curl http://localhost:8317/health
# Should return: {"status":"ok"}
```

---

### Problem: Dashboard tabs don't load (blank or loading forever)

**Cause**: Server API is not responding or has issues

**Solution**: Check server status and logs

```bash
# Test the API endpoint
curl http://localhost:8317/v0/management/auth-files \
  -H "X-Management-Key: sk-dummy"

# Should return JSON with account list

# Check server logs
ps aux | grep cliproxyapi-plus
```

---

### Problem: Theme toggle not working or preferences don't save

**Cause**: Browser localStorage is disabled or full

**Solution**: Clear storage and reload

```bash
# In browser DevTools Console:
# Clear all localStorage
localStorage.clear()

# Reload the page
# F5 or Cmd+R
```

---

### Problem: "Permission denied" or "lsof not found" errors

**Cause**: Port detection method not available on your system

**Solution**: The `cp-db` and `cp-start` commands try multiple methods (ss → netstat → lsof)

**Install missing tools:**

**macOS:**
```bash
brew install lsof  # Usually pre-installed
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install net-tools  # Provides netstat
sudo apt-get install net-tools  # Provides ss
```

**Linux (RHEL/CentOS):**
```bash
sudo yum install net-tools
```

---

### Problem: Quota data is stale or not updating

**Cause**: Cron job not running or quota-fetcher failing silently

**Solution**: Check cron job and quotas

```bash
# List current cron jobs
crontab -l | grep quota-fetcher

# If empty, setup cron manually:
python3 ~/.cli-proxy-api/scripts/quota-fetcher.py
# Should trigger cron setup

# Or add manually:
crontab -e
# Add this line:
# */10 * * * * python3 ~/.cli-proxy-api/scripts/quota-fetcher.py >/dev/null 2>&1
```

---

### Problem: Dashboard shows "Server offline" but server IS running

**Cause**: `/health` endpoint not responding (network/firewall issue)

**Solution**: Check connectivity

```bash
# Test the health endpoint
curl http://localhost:8317/health -v

# Test DNS (if accessing from another machine)
curl http://[YOUR_IP]:8317/health

# Check firewall
sudo netstat -tlnp | grep 8317
```

---

### Problem: Accounts show "403 error" or "Unauthorized"

**Cause**: OAuth token expired or account disconnected

**Solution**: Re-authenticate the account

```bash
# Login again to the provider
cp-login

# Select the provider and complete OAuth flow

# Refresh the dashboard
cp-db
```

---

## 🔍 Browser Console Debugging

When facing issues, check browser DevTools for errors:

1. **Open DevTools**: 
   - Windows/Linux: `F12` or `Ctrl+Shift+I`
   - macOS: `Cmd+Option+I`

2. **Check Console tab** for red errors

3. **Check Network tab**:
   - Look for failed requests (red color)
   - Check response status codes
   - Verify `/v0/management/*` calls succeed

4. **Check Storage tab**:
   - Verify `localStorage` contains `cli-proxy-theme` and `cli-proxy-language`

---

## 📞 Server Logs

For more details, check the server logs:

```bash
# Find server process ID
ps aux | grep cliproxyapi-plus

# Check if there's a log file
ls ~/.cli-proxy-api/logs/

# View recent logs
tail -50 ~/.cli-proxy-api/logs/server.log
```

---

## 🚀 Still Having Issues?

1. **Re-run the installer**:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/imrosyd/cliproxy-installer/main/install)" -- -update
   ```

2. **Check GitHub Issues**: [imrosyd/cliproxy-installer/issues](https://github.com/imrosyd/cliproxy-installer/issues)

3. **Manual server start** (debug mode):
   ```bash
   # Get the binary location
   which cliproxyapi-plus
   
   # Run with verbose output
   cliproxyapi-plus --config ~/.cli-proxy-api/config.yaml
   ```

---

### Problem: Auto-refresh not working

**Check:**

1. Is auto-refresh checkbox checked?
2. Is countdown timer showing?
3. Any console errors?

**Fix:**

```javascript
// Open browser console and check:
console.log(autoRefreshEnabled);
console.log(refreshInterval);
console.log(countdownInterval);
```

---

### Problem: Theme toggle not working

**Check localStorage:**

```javascript
// In browser console:
localStorage.getItem('theme')
```

**Fix:**

```javascript
// Clear and retry:
localStorage.clear();
// Reload page
```

---

## 🔍 Advanced Troubleshooting

### Check Server Logs

```bash
# API server logs
tail -f /Users/khmuhtadin/.cli-proxy-api/logs/main.log

# Proxy server logs
# (visible in terminal where proxy was started)
```

### Test API Endpoints Directly

```bash
# Test auth-files
curl http://localhost:8317/v0/management/auth-files \
  -H "X-Management-Key: sk-dummy"

# Test usage
curl http://localhost:8317/v0/management/usage \
  -H "X-Management-Key: sk-dummy"

# Test quota
curl http://localhost:8317/v0/management/quota \
  -H "X-Management-Key: sk-dummy"
```

### Verify File Permissions

```bash
# Check dashboard files
ls -la /Users/khmuhtadin/.cli-proxy-api/static/dashboard*.html

# Should be readable (rw-r--r--)
```

### Reset Everything

```bash
# 1. Stop all servers
pkill -f serve-dashboards
pkill -f cliproxyapi

# 2. Clear browser cache
# (Ctrl+Shift+Del in most browsers)

# 3. Restart API server
cd /Users/khmuhtadin/bin
./cliproxyapi-plus --config /Users/khmuhtadin/.cli-proxy-api/config.yaml &

# 4. Start proxy server
python3 /Users/khmuhtadin/.cli-proxy-api/serve-dashboards-with-proxy.py &

# 5. Access dashboard
open http://localhost:8318/dashboard-v2.html
```

---

## 📊 Diagnostic Commands

### Full System Check

```bash
#!/bin/bash

echo "=== Dashboard v2 Diagnostic ==="
echo ""

echo "1. Checking Proxy Server (8318)..."
lsof -i :8318 && echo "✅ Running" || echo "❌ Not running"
echo ""

echo "2. Checking API Server (8317)..."
lsof -i :8317 && echo "✅ Running" || echo "❌ Not running"
echo ""

echo "3. Testing Proxy Endpoint..."
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  http://localhost:8318/v0/management/auth-files \
  -H "X-Management-Key: sk-dummy"
echo ""

echo "4. Checking Dashboard File..."
ls -lh /Users/khmuhtadin/.cli-proxy-api/static/dashboard-v2.html
echo ""

echo "5. Testing Dashboard Access..."
curl -s -o /dev/null -w "Status: %{http_code}\n" \
  http://localhost:8318/dashboard-v2.html
echo ""

echo "=== End Diagnostic ==="
```

---

## 🐛 Common Error Messages

### "Failed to fetch"

**Browser Console:**
```
Failed to fetch: TypeError: Failed to fetch
```

**Cause**: Proxy server not running or CORS issue

**Fix**: Restart proxy server with CORS support

---

### "NetworkError when attempting to fetch resource"

**Cause**: API server not reachable

**Fix**:
1. Check API server is running
2. Verify port 8317 is open
3. Check firewall settings

---

### "Uncaught ReferenceError: Chart is not defined"

**Cause**: Chart.js CDN failed to load

**Fix**:
1. Check internet connection
2. Try different CDN mirror
3. Download Chart.js locally

---

## 💡 Performance Issues

### Dashboard loads slowly

**Possible causes:**
1. Chart.js CDN slow
2. Large quota cache
3. Many accounts

**Optimizations:**
1. Use local Chart.js
2. Reduce auto-refresh interval
3. Optimize quota cache

---

### High CPU usage

**Check:**
```bash
# Monitor processes
top -pid $(pgrep -f serve-dashboards-with-proxy)
top -pid $(pgrep -f cliproxyapi)
```

**Fix:**
- Increase auto-refresh interval
- Reduce number of active accounts
- Check for JavaScript memory leaks

---

## 📞 Getting Help

If issues persist:

1. **Check browser console** for errors
2. **Check server logs** in `logs/main.log`
3. **Review documentation**:
   - `DASHBOARD_V2_FEATURES.md`
   - `DASHBOARD_V2_QUICKSTART.md`
   - `IMPLEMENTATION_SUMMARY.md`

4. **Test with different browser**
5. **Try incognito/private mode**

---

## ✅ Verification Checklist

Before reporting issues, verify:

- [ ] Proxy server running on port 8318
- [ ] API server running on port 8317
- [ ] Dashboard file exists and readable
- [ ] Browser cache cleared
- [ ] No console errors
- [ ] Network requests successful
- [ ] Firewall not blocking ports
- [ ] Internet connection active (for CDN)

---

**Last Updated**: December 28, 2025  
**Version**: 2.0
