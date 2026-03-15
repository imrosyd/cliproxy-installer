#!/usr/bin/env python3
"""
CLIProxy Antigravity Manager
Reads embedded quota cache from dashboard.html and prints a summary.
"""

import json
import os
import re
import sys

DASHBOARD_FILE = os.path.expanduser("~/.cliproxyapi/static/dashboard.html")
MARKER_START = "// QUOTA_CACHE_START"
MARKER_END = "// QUOTA_CACHE_END"

MODEL_LABELS = [
    ("Gemini Pro", "geminiPro"),
    ("Claude", "claude"),
    ("Gemini Flash", "geminiFlash"),
    ("Gemini Image", "geminiImage"),
]


def load_cache():
    if not os.path.exists(DASHBOARD_FILE):
        return None, f"Dashboard file not found: {DASHBOARD_FILE}"

    try:
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        return None, f"Failed to read dashboard file: {exc}"

    pattern = re.compile(
        r"// QUOTA_CACHE_START\s*const EMBEDDED_QUOTA_CACHE = (.*?);\s*// QUOTA_CACHE_END",
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return None, "Quota cache markers not found in dashboard.html"

    json_blob = match.group(1).strip()
    if json_blob in ("", "null", "undefined"):
        return None, "Quota cache is empty. Please refresh quota first."

    try:
        return json.loads(json_blob), None
    except Exception as exc:
        return None, f"Failed to parse quota cache: {exc}"


def fmt_pct(value):
    if value is None:
        return "N/A"
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "N/A"


def fmt_reset(value):
    if not value:
        return ""
    return f" reset: {value}"


def print_account(account):
    email = account.get("email") or "unknown"
    acc_type = account.get("type") or "antigravity"
    quota = account.get("quota") or {}

    print(f"Account: {email} [{acc_type}]")
    for label, key in MODEL_LABELS:
        entry = quota.get(key) or {}
        remaining = fmt_pct(entry.get("remaining"))
        reset = fmt_reset(entry.get("resetTime"))
        print(f"  {label:<13}: {remaining}{reset}")
    print("")


def main():
    cache, err = load_cache()
    if err:
        print(err)
        sys.exit(1)

    accounts = cache.get("accounts") or {}
    last_updated = cache.get("lastUpdated") or "unknown"

    if not accounts:
        print("No accounts found in quota cache.")
        return

    for account in accounts.values():
        print_account(account)

    print(f"Last updated: {last_updated}")


if __name__ == "__main__":
    main()
