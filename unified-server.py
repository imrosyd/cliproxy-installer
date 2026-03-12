#!/usr/bin/env python3
"""
Unified server that serves static files and proxies API requests.
Runs on port 8317 as main entry point, proxies to cliproxy on port 8316.
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
import subprocess
import signal
import sys
import os
import time
import atexit
import re
import tempfile
import json
import threading
from datetime import datetime

# Configuration
PUBLIC_PORT = 8317      # Main entry point
BACKEND_PORT = 8316     # cliproxy-server runs here

# ── Logger ─────────────────────────────────────────────────────────────────────
_LOG_TAGS = {
    'INFO':     '',
    'ALIAS':    '\033[36m',   # cyan
    'PROXY':    '\033[32m',   # green
    'FAILOVER': '\033[33m',   # yellow
    'WATCHER':  '\033[35m',   # magenta
    'SYSTEM':   '\033[34m',   # blue
    'ERROR':    '\033[31m',   # red
    'WARN':     '\033[33m',   # yellow
}
_RESET = '\033[0m'

def log(tag: str, msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    color = _LOG_TAGS.get(tag.upper(), '')
    label = f'[{tag.upper()}]' if tag else ''
    print(f'{color}{ts} {label:<10}{_RESET} {msg}')

# ── Failover Engine ────────────────────────────────────────────────────────────
# HTTP status codes that indicate quota/rate-limit exhaustion for this account.
QUOTA_ERROR_CODES = {429, 402, 529}

# 502 from backend with these message fragments = "model unknown" → trigger failover
# (not a quota error on a specific account, but model routing failure)
UNKNOWN_MODEL_FRAGMENTS = [
    "unknown provider for model",
    "unknown model",
    "model not found",
    "no provider",
]

# Seconds a candidate is put in cooldown after a quota error before retrying.
COOLDOWN_SECONDS = 120

# Model fallback cache: remember which models are currently failing
# Format: {model_name: (timestamp, fallback_provider, fallback_model)}
_model_fallback_cache = {}
_fallback_cache_lock = threading.Lock()
FALLBACK_CACHE_TTL = 300  # 5 minutes

def _set_model_fallback(model: str, provider: str, fallback_model: str):
    """Cache a successful fallback for a model that's experiencing quota issues."""
    with _fallback_cache_lock:
        _model_fallback_cache[model] = (time.time(), provider, fallback_model)
        log('FAILOVER', f"Cached fallback: {model} → {fallback_model} via {provider}")

def _get_model_fallback(model: str):
    """Get cached fallback for a model if it exists and hasn't expired."""
    with _fallback_cache_lock:
        if model in _model_fallback_cache:
            cached_time, provider, fallback_model = _model_fallback_cache[model]
            if time.time() - cached_time < FALLBACK_CACHE_TTL:
                return (provider, fallback_model)
            else:
                # Expired, remove from cache
                del _model_fallback_cache[model]
    return None

def _clear_model_fallback(model: str):
    """Clear cached fallback for a model (e.g., when it succeeds again)."""
    with _fallback_cache_lock:
        _model_fallback_cache.pop(model, None)

# Model alias map: maps Anthropic canonical model names → available backend model.
# Built automatically from /v1/models at startup + extended with known variant names.
# Keys that already exist in backend are passed through unchanged.
# This map is only a fallback — _resolve_model() checks live backend first.
_model_alias_lock = threading.Lock()
_model_alias_cache: dict = {}   # populated by _build_model_alias_map()
_backend_model_set: set = set() # all model IDs the backend currently knows


def _fetch_backend_models() -> list:
    """Fetch the live model list from the backend. Returns list of model dicts."""
    try:
        req = urllib.request.Request(
            f'http://localhost:{BACKEND_PORT}/v1/models',
            headers={'Authorization': 'Bearer sk-dummy'},
            method='GET'
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get('data', [])
    except Exception:
        return []


def _tokenize(model_id: str) -> list:
    """
    Split a model ID into comparable tokens.
    e.g. "claude-3-5-sonnet-20241022" → ["claude", "3", "5", "sonnet", "20241022"]
         "gpt-4o-mini-2024-07-18"     → ["gpt", "4o", "mini", "2024", "07", "18"]
    Normalises dots/underscores to dashes first.

    Version token normalisation: 'v3.2' → 'v3', 'v4' → 'v4'
    so deepseek-v3.2 and deepseek-v4 both emit a 'v*' token for overlap scoring.
    """
    s = model_id.lower().replace('_', '-')
    # Normalise version tokens like v3.2 → keep just vN prefix so vN.x ~ vN
    s = re.sub(r'\bv(\d+)\.\d+', r'v\1', s)
    s = s.replace('.', '-')
    return [t for t in re.split(r'[-/:\s]+', s) if t]


def _token_similarity(req_tokens: list, backend_id: str) -> float:
    """
    Score how well `backend_id` matches the requested token list.

    Rules (in priority order):
    1. Exact match → 1.0
    2. Score = (shared tokens) / (max of the two token-set sizes)
       boosted by positional bonus if shared tokens appear in same order.
    3. Subtract a small penalty for each unmatched token in backend_id
       (to prefer shorter, more focused matches over overly long ones).
    """
    b_tokens = _tokenize(backend_id)
    if req_tokens == b_tokens:
        return 1.0

    req_set = set(req_tokens)
    b_set   = set(b_tokens)
    shared  = req_set & b_set
    if not shared:
        return 0.0

    # Jaccard-like base score
    base = len(shared) / max(len(req_set), len(b_set))

    # Order bonus: count consecutive shared tokens in same relative order
    order_matches = 0
    last_b_pos = -1
    for tok in req_tokens:
        if tok in shared:
            try:
                pos = b_tokens.index(tok, last_b_pos + 1)
                order_matches += 1
                last_b_pos = pos
            except ValueError:
                pass
    order_bonus = (order_matches / max(len(req_tokens), 1)) * 0.3

    # Penalty for extra tokens in backend model not in request
    extra_penalty = len(b_set - req_set) * 0.03

    return min(1.0, base + order_bonus - extra_penalty)


# Exclude these model IDs from being used as text-chat fallback targets
_NON_CHAT_MODELS = {
    # Embedding models — not for text chat
    'text-embedding-3-small', 'text-embedding-3-small-inference',
    'text-embedding-ada-002',
    # Image generation — not for text chat
    'gemini-3.1-flash-image',
    # Models accessible only via /completions endpoint (not /messages or /chat/completions)
    'gpt-5.4',
    # Internal/tool models
    'oswe-vscode-prime', 'oswe-vscode-secondary',
}


def _build_model_alias_map(_models: list) -> dict:
    """Alias map is now fully lazy — built on-demand by _find_best_match().
    This function is kept only to avoid breaking the call-site; always returns empty."""
    return {}


def _find_best_match(requested: str) -> str | None:
    """
    Live token-similarity search: compare `requested` against every chat-capable
    model currently in the backend and return the closest match.
    Results are cached in _model_alias_cache by the caller (_resolve_model).
    """
    with _model_alias_lock:
        chat_ids = [mid for mid in _backend_model_set if mid not in _NON_CHAT_MODELS]
    if not chat_ids:
        return None

    # Special case: OpenAI reasoning model shorthand (o1, o3, o4, o1-mini, o3-mini, o4-mini)
    # These are single/short tokens with no overlap to any backend model name.
    # Map to gpt-4o (closest capability equivalent), falling back to gpt-4 variants.
    if re.match(r'^o\d(-mini|-preview)?$', requested.lower()):
        # o*-mini variants → gpt-4o-mini; full variants → gpt-4o
        is_mini = 'mini' in requested.lower()
        if is_mini:
            mini_candidates = sorted([m for m in chat_ids if 'gpt-4o-mini' in m])
            fallback = sorted([m for m in chat_ids if 'gpt-4o' in m])
            target = mini_candidates + fallback
        else:
            o_candidates = sorted([m for m in chat_ids if 'gpt-4o' in m and 'mini' not in m])
            fallback = sorted([m for m in chat_ids if 'gpt-4' in m])
            target = o_candidates + fallback
        return target[0] if target else None

    req_tok = _tokenize(requested)

    # Provider-anchor filtering: restrict search to models whose first token matches
    # the requested model's provider prefix — prevents cross-provider mismatches.
    # If no models share the prefix, pass-through unchanged (return None).
    provider_tok = req_tok[0] if req_tok else ''

    # Normalise versioned provider prefixes: "qwen" matches "qwen3", "gemini" matches "gemini3" etc.
    def _provider_match(backend_prefix: str) -> bool:
        if backend_prefix == provider_tok:
            return True
        # "qwen" matches "qwen3", "qwen2" etc.
        if backend_prefix.startswith(provider_tok) and backend_prefix[len(provider_tok):].isdigit():
            return True
        return False

    anchored = [mid for mid in chat_ids if _provider_match(_tokenize(mid)[0])] if provider_tok else []

    # If provider prefix is purely numeric, skip anchor (shouldn't happen but guard anyway)
    if provider_tok and not provider_tok[0].isdigit():
        if not anchored:
            # Provider not in backend at all — pass-through so backend handles/rejects it
            return None
        candidate_pool = anchored
    else:
        candidate_pool = chat_ids

    # If only one candidate in pool, return it directly (e.g. grok → grok-code-fast-1)
    if len(candidate_pool) == 1:
        return candidate_pool[0]

    best_id, best_score = None, 0.0
    for mid in candidate_pool:
        s = _token_similarity(req_tok, mid)
        if s > best_score:
            best_score, best_id = s, mid
    return best_id if best_score > 0.25 else None


def _resolve_model(requested: str) -> str:
    """
    Return the backend model ID to use for the requested model name.

    Priority:
    1. Already in backend → pass through unchanged.
    2. In pre-built alias map → use cached alias.
    3. Live token-similarity search → find closest backend model on the fly.
    4. No match → return original (backend will handle/error).
    """
    if not requested:
        return requested
    with _model_alias_lock:
        if requested in _backend_model_set:
            return requested
        cached = _model_alias_cache.get(requested)
    if cached:
        return cached
    # Live fallback: match by token similarity against current backend models
    matched = _find_best_match(requested)
    if matched:
        log('ALIAS', f"Resolved  '{requested}' -> '{matched}'")
        # Cache so we don't re-score on every request
        with _model_alias_lock:
            _model_alias_cache[requested] = matched
        return matched
    log('ALIAS', f"No match  '{requested}' — pass-through")
    return requested


def _refresh_model_aliases(clear_cache: bool = True):
    """
    Refresh the live backend model set.
    On startup: retries until count stabilises (backend may still be loading).
    On periodic refresh: single fast fetch, no waiting.
    Clears the alias cache so stale matches get re-evaluated against new models.
    """
    global _backend_model_set, _model_alias_cache

    fetched = _fetch_backend_models()

    # If this is startup (clear_cache=True and set is empty), wait for stabilisation
    with _model_alias_lock:
        is_startup = len(_backend_model_set) == 0
    if is_startup:
        prev_count = 0
        stable_rounds = 0
        for attempt in range(12):          # up to ~60s
            count = len(fetched)
            if count > 0 and count == prev_count:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0
            prev_count = count
            if attempt < 11:
                time.sleep(5)
                fetched = _fetch_backend_models()

    if not fetched:
        return

    new_set = {m['id'] for m in fetched}
    with _model_alias_lock:
        changed = new_set != _backend_model_set
        _backend_model_set = new_set
        if clear_cache and changed:
            _model_alias_cache = {}   # invalidate cached matches — new models may score better

    if changed:
        log('ALIAS', f"Backend updated: {len(new_set)} models (cache cleared)")

_cooldown_lock = threading.Lock()
# Maps (provider_name, api_key) -> float (epoch seconds when cooldown expires)
_cooldown_until: dict = {}

# Parsed provider list cache — reloaded on each failover sequence to pick up edits.
_config_lock = threading.Lock()


def _load_providers_from_config(config_path: str) -> list:
    """
    Parse openai-compatibility providers from config.yaml without a YAML library.
    Returns a list of dicts:
      { 'name': str, 'base_url': str, 'api_keys': [str], 'models': [str] }
    """
    providers = []
    try:
        with open(config_path, 'r') as f:
            lines = f.readlines()
    except Exception:
        return providers

    in_compat = False
    current: dict | None = None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.lstrip()

        # Detect openai-compatibility section
        if re.match(r'^openai-compatibility\s*:', line):
            in_compat = True
            continue

        # A top-level key (no indent) other than openai-compatibility ends the section
        if in_compat and line and not line[0].isspace():
            in_compat = False
            if current:
                providers.append(current)
                current = None
            continue

        if not in_compat:
            continue

        indent = len(line) - len(stripped)

        # New provider entry
        if indent == 2 and stripped.startswith('- name:'):
            if current:
                providers.append(current)
            name = stripped.split(':', 1)[1].strip().strip('"\'')
            current = {'name': name, 'base_url': '', 'api_keys': [], 'models': [], 'enabled': True}
            continue

        if current is None:
            continue

        if indent == 4:
            if stripped.startswith('base-url:'):
                current['base_url'] = stripped.split(':', 1)[1].strip().strip('"\'')
            elif stripped.startswith('- api-key:'):
                key = stripped.split(':', 1)[1].strip().strip('"\'')
                current['api_keys'].append(key)
            elif stripped.startswith('enabled:'):
                current['enabled'] = stripped.split(':', 1)[1].strip().lower() == 'true'
        elif indent == 6:
            if stripped.startswith('- api-key:'):
                key = stripped.split(':', 1)[1].strip().strip('"\'')
                current['api_keys'].append(key)
            elif stripped.startswith('- name:'):
                model_name = stripped.split(':', 1)[1].strip().strip('"\'')
                current['models'].append(model_name)
            elif stripped.startswith('alias:'):
                pass  # We track by name
        elif stripped.startswith('alias:') and indent == 8:
            pass

    if current and in_compat:
        providers.append(current)

    # Remove entries with no base_url or no api keys
    return [p for p in providers if p['base_url'] and p['api_keys']]


def _is_in_cooldown(provider_name: str, api_key: str) -> bool:
    key = (provider_name, api_key)
    with _cooldown_lock:
        until = _cooldown_until.get(key, 0)
        return time.time() < until


def _set_cooldown(provider_name: str, api_key: str):
    key = (provider_name, api_key)
    with _cooldown_lock:
        _cooldown_until[key] = time.time() + COOLDOWN_SECONDS
    log('FAILOVER', f"Cooldown {COOLDOWN_SECONDS}s for {provider_name} (key …{api_key[-4:]})")


def _smart_model_substitute(requested_model: str, available_models: list) -> str:
    """
    Universal intelligent model substitution for cross-provider failover.
    Handles all major AI models: Claude, GPT, Gemini, DeepSeek, O1/O3, Llama, Mistral, etc.
    Maps based on tier, capability, speed, and specialized features.
    """
    if not available_models:
        return None
    
    req_lower = requested_model.lower()
    available_lower = [m.lower() for m in available_models]
    
    # ============================================================================
    # TIER 1: EXACT OR SAME-FAMILY MATCH (Highest Priority)
    # ============================================================================
    
    # Try to find exact model first
    for i, model in enumerate(available_models):
        if model.lower() == req_lower:
            return model
    
    # Try to find same family with version matching
    base_model = req_lower.split('-')[0] if '-' in req_lower else req_lower.split('.')[0]
    
    # Claude same-family matching
    if 'claude' in req_lower:
        for model in available_models:
            m_lower = model.lower()
            # Same tier matching: opus→opus, sonnet→sonnet, haiku→haiku
            if 'opus' in req_lower and 'opus' in m_lower:
                return model
            if 'sonnet' in req_lower and 'sonnet' in m_lower:
                return model
            if 'haiku' in req_lower and 'haiku' in m_lower:
                return model
    
    # Gemini same-family matching
    if 'gemini' in req_lower:
        for model in available_models:
            m_lower = model.lower()
            if 'gemini' in m_lower:
                # Pro→Pro, Flash→Flash matching
                if 'pro' in req_lower and 'pro' in m_lower:
                    return model
                if 'flash' in req_lower and 'flash' in m_lower:
                    return model
    
    # GPT same-family matching (including O1/O3)
    if any(x in req_lower for x in ['gpt', 'o1', 'o3']):
        for model in available_models:
            m_lower = model.lower()
            # O1/O3 to O1/O3 matching
            if 'o1' in req_lower and 'o1' in m_lower:
                return model
            if 'o3' in req_lower and 'o3' in m_lower:
                return model
            # GPT version matching: 5.x→5.x, 4.x→4.x
            if 'gpt-5' in req_lower and 'gpt-5' in m_lower:
                # Prefer exact version match
                req_version = req_lower.split('gpt-5')[-1].split('-')[0] if 'gpt-5' in req_lower else ''
                if req_version in m_lower:
                    return model
            if 'gpt-4' in req_lower and 'gpt-4' in m_lower:
                return model
    
    # ============================================================================
    # TIER 2: INTELLIGENT CROSS-FAMILY MAPPING
    # ============================================================================
    
    # === REASONING MODELS (Highest Tier) ===
    # Claude Opus, O1, O3, GPT-5.3, DeepSeek-R1, Gemini Pro
    reasoning_indicators = ['opus-4', 'opus-3.7', 'o1-pro', 'o3-', 'deepseek-r1', 
                           'gpt-5.3', 'gemini-3-pro', 'gemini-2.5-pro-thinking']
    if any(x in req_lower for x in reasoning_indicators):
        # Priority: O3 > O1-pro > DeepSeek-R1 > GPT-5.3 > Claude Opus > Gemini Pro
        for pattern in ['o3-', 'o1-pro', 'deepseek-r1', 'gpt-5.3', 'opus-4', 'opus-3.7', 'gemini-3-pro']:
            for model in available_models:
                if pattern in model.lower() and 'mini' not in model.lower():
                    return model
        # Fallback to high-tier models
        for pattern in ['gpt-5.2', 'sonnet-4', 'gemini-2.5-pro']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # === HIGH-TIER BALANCED MODELS ===
    # Claude Sonnet, GPT-5.2, GPT-4o, Gemini 2.5 Pro, DeepSeek-V3
    balanced_indicators = ['sonnet-4', 'sonnet-3.7', 'gpt-5.2', 'gpt-4o', 'gpt-4.5',
                          'gemini-2.5-pro', 'gemini-3-pro', 'deepseek-v3']
    if any(x in req_lower for x in balanced_indicators):
        # Priority: GPT-5.2 > Claude Sonnet 4 > GPT-4.5 > DeepSeek-V3 > Gemini 2.5 Pro
        for pattern in ['gpt-5.2', 'sonnet-4', 'gpt-4.5', 'gpt-4o', 'deepseek-v3', 'gemini-2.5-pro']:
            for model in available_models:
                if pattern in model.lower() and 'mini' not in model.lower():
                    return model
        # Fallback to mid-tier
        for pattern in ['gpt-5.1', 'sonnet-3.5', 'haiku-4', 'gemini-2.0-pro']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # === MID-TIER MODELS ===
    # Claude Haiku 4.x, GPT-5.1, GPT-4, Gemini 2.0 Pro, Llama 3.3
    mid_tier_indicators = ['haiku-4', 'haiku-3.7', 'gpt-5.1', 'gpt-4-turbo', 'gemini-2.0-pro',
                          'llama-3.3', 'llama-3.1-405b', 'mistral-large']
    if any(x in req_lower for x in mid_tier_indicators):
        for pattern in ['gpt-5.1', 'haiku-4', 'gpt-4', 'llama-3.3', 'gemini-2.0-pro', 'mistral-large']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # === FAST/EFFICIENT MODELS ===
    # Claude Haiku 3.5, Gemini Flash, GPT-4o-mini, GPT-3.5, Llama 3.1 70B/8B
    fast_indicators = ['haiku-3.5', 'haiku-3', 'flash', 'mini', 'lite', 'gpt-3.5', 
                      'llama-3.1-70b', 'llama-3.1-8b', 'mistral-7b']
    if any(x in req_lower for x in fast_indicators):
        for pattern in ['flash', 'haiku-3.5', 'gpt-4o-mini', 'gpt-3.5', 'llama-3.1-70b', 'llama-3.1-8b']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # === CODING-SPECIALIZED MODELS ===
    # Codex, DeepSeek Coder, Qwen Coder, GPT-4o (good at code)
    coding_indicators = ['codex', 'coder', 'qwen', 'deepseek-coder']
    if any(x in req_lower for x in coding_indicators):
        for pattern in ['codex', 'deepseek-coder', 'qwen-coder', 'qwen']:
            for model in available_models:
                if pattern in model.lower():
                    return model
        # Fallback to general models good at coding
        for pattern in ['gpt-5', 'gpt-4o', 'sonnet', 'llama-3']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # === SPECIALIZED MODELS ===
    
    # Vision models → multimodal alternatives
    if any(x in req_lower for x in ['vision', 'image', 'multimodal']):
        for pattern in ['gpt-4o', 'gpt-4-turbo', 'gemini', 'claude-3', 'claude-4']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # Long-context models → other long-context
    if any(x in req_lower for x in ['long', 'extended', '100k', '200k', '1m']):
        for pattern in ['gemini', 'claude', 'gpt-4']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # ============================================================================
    # TIER 3: FAMILY-BASED FALLBACKS
    # ============================================================================
    
    # Claude → Claude (any version) > GPT-5 > Gemini > Others
    if 'claude' in req_lower:
        for model in available_models:
            if 'claude' in model.lower():
                return model
        for pattern in ['gpt-5', 'gpt-4', 'gemini', 'deepseek', 'llama']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # GPT/O1/O3 → GPT (any version) > Claude > Gemini > Others
    if any(x in req_lower for x in ['gpt', 'o1', 'o3']):
        for model in available_models:
            if any(x in model.lower() for x in ['gpt', 'o1', 'o3']):
                return model
        for pattern in ['claude-4', 'claude-3.5', 'gemini-2', 'deepseek', 'llama']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # Gemini → Gemini (any version) > GPT-5 > Claude > Others
    if 'gemini' in req_lower:
        for model in available_models:
            if 'gemini' in model.lower():
                return model
        for pattern in ['gpt-5', 'gpt-4', 'claude', 'deepseek', 'llama']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # DeepSeek → DeepSeek (any) > Qwen > Llama > GPT > Claude
    if 'deepseek' in req_lower:
        for model in available_models:
            if 'deepseek' in model.lower():
                return model
        for pattern in ['qwen', 'llama', 'gpt', 'claude']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # Llama → Llama (any) > Mistral > DeepSeek > Others
    if 'llama' in req_lower:
        for model in available_models:
            if 'llama' in model.lower():
                return model
        for pattern in ['mistral', 'deepseek', 'qwen', 'gpt', 'claude']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # Mistral → Mistral (any) > Llama > Others
    if 'mistral' in req_lower:
        for model in available_models:
            if 'mistral' in model.lower():
                return model
        for pattern in ['llama', 'qwen', 'gpt', 'claude']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # Qwen → Qwen (any) > DeepSeek > Llama > Others
    if 'qwen' in req_lower:
        for model in available_models:
            if 'qwen' in model.lower():
                return model
        for pattern in ['deepseek', 'llama', 'gpt', 'claude']:
            for model in available_models:
                if pattern in model.lower():
                    return model
    
    # ============================================================================
    # TIER 4: UNIVERSAL FALLBACK
    # ============================================================================
    
    # Prefer flagship models in order of general capability
    for pattern in ['gpt-5', 'claude-4', 'gemini-3', 'gemini-2.5', 'o1', 'o3', 
                   'gpt-4', 'claude-3', 'deepseek-v3', 'llama-3.3']:
        for model in available_models:
            if pattern in model.lower():
                return model
    
    # Last resort: return first available model
    return available_models[0] if available_models else None


def _build_failover_candidates(requested_model: str, config_path: str) -> list:
    """
    Return an ordered list of (provider, api_key, model) candidates to try.

    Priority:
    1. All (provider, api_key) pairs that explicitly list requested_model — sorted
       so same-provider pairs come first relative to each other.
    2. Smart model substitution: if provider doesn't have exact model, pick best alternative
    3. All (provider, api_key) pairs that list NO models (wildcard/unknown) with
       requested_model — treated as potentially supporting it.
    """
    providers = _load_providers_from_config(config_path)
    if not providers:
        return []

    exact: list = []          # has the exact model listed
    substituted: list = []    # smart substitute model
    wildcard: list = []       # no model list — try with same model name

    for p in providers:
        for key in p['api_keys']:
            if _is_in_cooldown(p['name'], key):
                continue
            if requested_model and requested_model in p['models']:
                exact.append((p['name'], p['base_url'], key, requested_model))
            elif not p['models']:
                wildcard.append((p['name'], p['base_url'], key, requested_model))
            else:
                # Try smart model substitution
                substitute = _smart_model_substitute(requested_model, p['models'])
                if substitute:
                    substituted.append((p['name'], p['base_url'], key, substitute))

    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for c in exact + substituted + wildcard:
        ident = (c[0], c[2], c[3])  # provider, key, model
        if ident not in seen:
            seen.add(ident)
            ordered.append(c)

    return ordered

    return ordered


def _direct_request(base_url: str, api_key: str, path: str,
                    method: str, headers: dict, data: bytes | None) -> tuple:
    """
    Make a request directly to provider base_url (bypass backend).
    Returns (status_code, response_headers, body_bytes).
    Raises urllib.error.HTTPError on HTTP errors.
    """
    url = base_url.rstrip('/') + path
    req_headers = dict(headers)
    req_headers['Authorization'] = f'Bearer {api_key}'
    # Remove backend-specific headers that shouldn't go to external providers
    for h in ['X-Management-Key']:
        req_headers.pop(h, None)

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, dict(resp.headers), resp.read()
# ── End Failover Engine ────────────────────────────────────────────────────────

# Auto-detect paths
HOME = os.path.expanduser("~")
CLI_PROXY_DIR = os.path.join(HOME, ".cliproxyapi")
STATIC_DIR = os.path.join(CLI_PROXY_DIR, "static")
BIN_DIR = os.path.join(CLI_PROXY_DIR, "bin")
CLIPROXY_PATH = os.path.join(BIN_DIR, "cliproxyapi")
CONFIG_PATH = os.path.join(CLI_PROXY_DIR, "config.yaml")
USAGE_STATS_PATH = os.path.join(CLI_PROXY_DIR, "usage_stats.json")

LOGIN_PROVIDERS = {
    'antigravity': '-antigravity-login',
    'github-copilot': '-github-copilot-login',
    'gemini-cli': '-login',
    'codex': '-codex-login',
    'claude': '-claude-login',
    'qwen': '-qwen-login',
    'iflow': '-iflow-login',
    'kilo': '-kilo-login',
    'kimi': '-kimi-login',
    'kiro': '-kiro-login',
}

_login_state_lock = threading.Lock()
_login_state = {}
_device_code_re = re.compile(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}\b')
_url_re = re.compile(r'https?://[^\s)\]"]+')

def _set_login_state(provider, **kwargs):
    with _login_state_lock:
        state = _login_state.get(provider, {})
        state.update(kwargs)
        _login_state[provider] = state
        return dict(state)

def _get_login_state(provider):
    with _login_state_lock:
        return dict(_login_state.get(provider, {}))

def _monitor_login_process(provider, process):
    try:
        if process.stdout is not None:
            for line in process.stdout:
                text = line.strip()
                if not text:
                    continue
                code_match = _device_code_re.search(text)
                url_match = _url_re.search(text)
                updates = {}
                if code_match:
                    updates['device_code'] = code_match.group(0)
                if url_match:
                    updates['verification_url'] = url_match.group(0)
                if updates:
                    _set_login_state(provider, **updates)
    except Exception as e:
        _set_login_state(provider, error=str(e))
    finally:
        rc = process.poll()
        _set_login_state(provider, running=False, exit_code=rc)

# ── Usage Statistics Tracking ──────────────────────────────────────────────────
_usage_stats = {
    "total_requests": 0,
    "success_count": 0,
    "failure_count": 0,
    "total_tokens": 0,
    "apis": {},
    "requests_by_day": {},
    "requests_by_hour": {},
    "tokens_by_day": {},
    "tokens_by_hour": {}
}
_usage_lock = threading.Lock()

def _load_usage_stats():
    """Load usage statistics from file."""
    global _usage_stats
    try:
        if os.path.exists(USAGE_STATS_PATH):
            with open(USAGE_STATS_PATH, 'r') as f:
                _usage_stats = json.load(f)
                log('INFO', f"Loaded usage stats: {_usage_stats['total_requests']} total requests")
    except Exception as e:
        log('WARN', f"Failed to load usage stats: {e}")
        _usage_stats = {
            "total_requests": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_tokens": 0,
            "apis": {},
            "requests_by_day": {},
            "requests_by_hour": {},
            "tokens_by_day": {},
            "tokens_by_hour": {}
        }

def _save_usage_stats():
    """Save usage statistics to file."""
    try:
        with open(USAGE_STATS_PATH, 'w') as f:
            json.dump(_usage_stats, f, indent=2)
    except Exception as e:
        log('ERROR', f"Failed to save usage stats: {e}")

def _track_request(path: str, success: bool, tokens: int = 0):
    """Track an API request in statistics."""
    with _usage_lock:
        _usage_stats["total_requests"] += 1
        if success:
            _usage_stats["success_count"] += 1
        else:
            _usage_stats["failure_count"] += 1
        
        _usage_stats["total_tokens"] += tokens
        
        # Extract API endpoint (e.g., /v1/messages -> /v1/messages)
        api_path = path.split('?')[0]  # Remove query params
        if api_path.startswith('/v1/') or api_path.startswith('/v0/'):
            _usage_stats["apis"][api_path] = _usage_stats["apis"].get(api_path, 0) + 1
        
        # Track by day and hour
        now = datetime.now()
        day_key = now.strftime('%Y-%m-%d')
        hour_key = now.strftime('%Y-%m-%d %H:00')
        
        _usage_stats["requests_by_day"][day_key] = _usage_stats["requests_by_day"].get(day_key, 0) + 1
        _usage_stats["requests_by_hour"][hour_key] = _usage_stats["requests_by_hour"].get(hour_key, 0) + 1
        
        if tokens > 0:
            _usage_stats["tokens_by_day"][day_key] = _usage_stats["tokens_by_day"].get(day_key, 0) + tokens
            _usage_stats["tokens_by_hour"][hour_key] = _usage_stats["tokens_by_hour"].get(hour_key, 0) + tokens
        
        # Save every 10 requests to avoid excessive I/O
        if _usage_stats["total_requests"] % 10 == 0:
            _save_usage_stats()

cliproxy_process = None
_temp_config = None
_backend_log_handle = None
_process_lock = threading.Lock()
_config_write_lock = threading.Lock()
_shutdown_event = threading.Event()
_cleanup_lock = threading.Lock()
_cleanup_done = False
_server_instance = None

def _create_backend_config():
    """Create a temporary config with the backend port."""
    global _temp_config
    try:
        with open(CONFIG_PATH, 'r') as f:
            config_text = f.read()
        # Replace port value in YAML
        config_text = re.sub(r'^port:\s*\d+', f'port: {BACKEND_PORT}', config_text, count=1, flags=re.MULTILINE)
        _temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', prefix='cliproxy-backend-', delete=False)
        _temp_config.write(config_text)
        _temp_config.close()
        return _temp_config.name
    except Exception as e:
        log('ERROR', f"Failed to create backend config: {e}")
        return CONFIG_PATH

def start_cliproxy():
    """Start cliproxy-server on backend port, redirect its output to a log file."""
    global cliproxy_process, _backend_log_handle

    backend_config = _create_backend_config()

    log_dir = os.path.join(os.path.expanduser('~'), '.cliproxyapi', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    backend_log_path = os.path.join(log_dir, 'backend.log')

    with _process_lock:
        try:
            if cliproxy_process and cliproxy_process.poll() is None:
                return True

            if _backend_log_handle:
                try:
                    _backend_log_handle.close()
                except Exception:
                    pass
                _backend_log_handle = None

            _backend_log_handle = open(backend_log_path, 'a')
            cliproxy_process = subprocess.Popen(
                [CLIPROXY_PATH, '-config', backend_config],
                stdout=_backend_log_handle,
                stderr=_backend_log_handle,
                cwd=os.path.expanduser('~'),
            )
            log('INFO', f"Backend started (PID: {cliproxy_process.pid}) — logs: {backend_log_path}")
            time.sleep(2)  # Wait for startup
            return True
        except Exception as e:
            if _backend_log_handle:
                try:
                    _backend_log_handle.close()
                except Exception:
                    pass
                _backend_log_handle = None
            cliproxy_process = None
            log('ERROR', f"Failed to start backend: {e}")
            return False

def stop_cliproxy():
    """Stop cliproxy-server"""
    global cliproxy_process, _temp_config, _backend_log_handle

    with _process_lock:
        proc = cliproxy_process
        cliproxy_process = None

    if proc:
        log('INFO', "Stopping backend...")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)
            except Exception:
                pass

    with _process_lock:
        if _backend_log_handle:
            try:
                _backend_log_handle.close()
            except Exception:
                pass
            _backend_log_handle = None

    if _temp_config:
        temp_name = getattr(_temp_config, 'name', '')
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except Exception:
                pass
        _temp_config = None


def _get_auth_dir() -> str:
    """Resolve auth directory from config.yaml with safe fallback."""
    auth_dir = CLI_PROXY_DIR
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                cfg = f.read()
            match = re.search(r'^auth-dir:\s*["\']?([^"\'\n]+)', cfg, re.MULTILINE)
            if match and match.group(1).strip():
                auth_dir = match.group(1).strip()
    except Exception:
        pass
    return os.path.expanduser(auth_dir)


def _extract_auth_account(file_path: str, auth_dir: str, metadata: dict) -> dict:
    """Convert auth metadata JSON into dashboard account shape."""
    rel_id = os.path.relpath(file_path, auth_dir).replace('\\', '/')
    provider = str(metadata.get('type') or metadata.get('provider') or 'unknown')
    email = str(
        metadata.get('email')
        or metadata.get('username')
        or metadata.get('user_email')
        or metadata.get('account')
        or ''
    ).strip()
    username = str(metadata.get('username') or '').strip()
    disabled = bool(metadata.get('disabled', False))
    unavailable = bool(metadata.get('unavailable', False))
    status = str(metadata.get('status') or ('disabled' if disabled else 'active'))
    status_message = str(metadata.get('status_message') or '')

    raw_models = metadata.get('models')
    models = []
    if isinstance(raw_models, list):
        for item in raw_models:
            if isinstance(item, str) and item.strip():
                models.append({'name': item.strip()})
            elif isinstance(item, dict):
                model_name = str(item.get('name') or item.get('alias') or '').strip()
                if model_name:
                    models.append({'name': model_name})

    return {
        'id': rel_id,
        'provider': provider,
        'email': email,
        'username': username,
        'status': status,
        'status_message': status_message,
        'disabled': disabled,
        'unavailable': unavailable,
        'models': models,
    }


def _list_auth_files() -> list:
    """List auth JSON files for dashboard account table."""
    auth_dir = _get_auth_dir()
    out = []
    if not os.path.isdir(auth_dir):
        return out

    for root, _, files in os.walk(auth_dir):
        for name in files:
            if not name.lower().endswith('.json'):
                continue
            file_path = os.path.join(root, name)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    continue
                # Skip unrelated JSON files (e.g., usage_stats.json).
                looks_like_auth = any(k in data for k in (
                    'type', 'provider', 'email', 'username', 'token', 'api_key', 'refresh_token'
                ))
                if not looks_like_auth:
                    continue
                out.append(_extract_auth_account(file_path, auth_dir, data))
            except Exception:
                continue

    out.sort(key=lambda x: (x.get('provider', ''), x.get('email', ''), x.get('id', '')))
    return out


def _delete_auth_file_by_id(account_id: str) -> bool:
    """Delete an auth JSON file by relative path id from auth directory."""
    account_id = urllib.parse.unquote(account_id or '').strip()
    if not account_id:
        return False

    auth_dir = os.path.abspath(_get_auth_dir())
    safe_rel = os.path.normpath(account_id)
    if os.path.isabs(safe_rel) or safe_rel.startswith('..'):
        return False

    target = os.path.abspath(os.path.join(auth_dir, safe_rel))
    if target != auth_dir and not target.startswith(auth_dir + os.sep):
        return False

    if not os.path.exists(target):
        return False

    try:
        os.remove(target)
        return True
    except Exception:
        return False


def _set_auth_file_disabled_by_id(account_id: str, disabled: bool) -> bool:
    """Update disabled/status fields in an auth JSON file by relative id."""
    account_id = urllib.parse.unquote(account_id or '').strip()
    if not account_id:
        return False

    auth_dir = os.path.abspath(_get_auth_dir())
    safe_rel = os.path.normpath(account_id)
    if os.path.isabs(safe_rel) or safe_rel.startswith('..'):
        return False

    target = os.path.abspath(os.path.join(auth_dir, safe_rel))
    if target != auth_dir and not target.startswith(auth_dir + os.sep):
        return False

    if not os.path.exists(target):
        return False

    try:
        with open(target, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False

        data['disabled'] = bool(disabled)
        data['status'] = 'disabled' if disabled else 'active'
        if disabled:
            data['status_message'] = 'Disabled from dashboard'
        else:
            data['status_message'] = ''

        with open(target, 'w') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
        return True
    except Exception:
        return False


def _remove_provider_from_config(provider_name: str) -> bool:
    """Remove a named provider from the openai-compatibility section in config.yaml."""
    provider_name = (provider_name or '').strip()
    if not provider_name:
        return False

    config_path = os.path.expanduser('~/.cliproxyapi/config.yaml')
    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, 'r') as f:
            lines = f.readlines()
    except Exception:
        return False

    # Find the provider block and remove it.
    # Strategy: scan line by line tracking which openai-compatibility provider we are inside.
    new_lines = []
    in_compat = False
    skip_block = False
    # indent of the current provider entry (the "  - name:" line)
    block_indent: int | None = None
    found = False

    for raw in lines:
        line = raw.rstrip('\n')
        stripped = line.lstrip()

        # Detect openai-compatibility section start
        if re.match(r'^openai-compatibility\s*:', line):
            in_compat = True
            if not skip_block:
                new_lines.append(raw)
            continue

        # A top-level key (no indent) other than openai-compatibility ends the section
        if in_compat and line and not line[0].isspace():
            in_compat = False
            skip_block = False
            block_indent = None

        if in_compat:
            indent = len(line) - len(stripped)

            # Detect a new provider entry line: "  - name: ..."
            if indent == 2 and stripped.startswith('- name:'):
                entry_name = stripped.split(':', 1)[1].strip().strip('"\'')
                if entry_name == provider_name:
                    skip_block = True
                    block_indent = indent
                    found = True
                    continue  # skip this line
                else:
                    # Previous skip block ended — a new provider starts
                    skip_block = False
                    block_indent = None

            if skip_block:
                # Skip all lines that belong to this provider block
                # (deeper indented lines, or empty lines within the block)
                if stripped == '' or (len(line) - len(stripped)) > (block_indent or 2):
                    continue
                else:
                    # Non-empty line at same or lower indent ends the block
                    skip_block = False
                    block_indent = None
                    # This line belongs to something else — don't skip it

        new_lines.append(raw)

    if not found:
        return False

    # Remove trailing empty lines before end of openai-compatibility section
    # (to avoid leaving a dangling empty block)
    with _config_write_lock:
        with open(config_path, 'w') as f:
            f.writelines(new_lines)

    return True


def _toggle_provider_in_config(provider_name: str, enabled: bool) -> bool:
    """Enable or disable a named provider in the openai-compatibility section in config.yaml."""
    provider_name = (provider_name or '').strip()
    if not provider_name:
        log('ERROR', "Provider name is empty")
        return False

    config_path = os.path.expanduser('~/.cliproxyapi/config.yaml')
    if not os.path.exists(config_path):
        log('ERROR', f"Config file not found: {config_path}")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()
    except Exception as e:
        log('ERROR', f"Failed to read config: {e}")
        return False

    # Find provider and update enabled field
    new_lines = []
    in_compat = False
    found_provider = None
    modified = False
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        
        # Detect openai-compatibility section
        if re.match(r'^openai-compatibility\s*:', stripped):
            in_compat = True
            new_lines.append(line)
            continue
        
        # End of openai-compatibility section
        if in_compat and stripped and not line.startswith(' ') and not line.startswith('\t'):
            in_compat = False
        
        if not in_compat:
            new_lines.append(line)
            continue
        
        # Check for provider name at indent 2
        indent = len(line) - len(stripped)
        if indent == 2 and stripped.startswith('- name:'):
            # Extract provider name
            name_part = stripped[7:].strip().strip('"').strip("'")
            if name_part == provider_name:
                found_provider = True
                new_lines.append(line)
                # Add enabled field on next line
                new_lines.append(f"    enabled: {str(enabled).lower()}")
                modified = True
                continue
            else:
                found_provider = False
        
        # If we're in the target provider, handle enabled field
        if found_provider:
            # Skip if this line is already an enabled field
            if stripped.startswith('enabled:'):
                # Replace the existing enabled field
                new_lines.append(f"    enabled: {str(enabled).lower()}")
                continue
            
            # If we hit another provider, we're done with this one
            if indent == 2 and stripped.startswith('- name:'):
                found_provider = None
        
        new_lines.append(line)
    
    if not modified:
        log('ERROR', f"Provider not found in config: {provider_name}")
        # Try alternative search - case insensitive
        log('INFO', f"Searching for provider '{provider_name}' in config...")
        for i, line in enumerate(lines):
            if f"- name:" in line and provider_name.lower() in line.lower():
                log('INFO', f"Found potential match at line {i+1}: {line}")
        return False

    try:
        with _config_write_lock:
            with open(config_path, 'w') as f:
                f.write('\n'.join(new_lines))
        log('INFO', f"Successfully toggled provider {provider_name} to enabled={enabled}")
        return True
    except Exception as e:
        log('ERROR', f"Failed to write config: {e}")
        return False


def _cleanup_once():
    """Run cleanup once, even if called by both signal and atexit handlers."""
    global _cleanup_done
    with _cleanup_lock:
        if _cleanup_done:
            return
        _cleanup_done = True

    _shutdown_event.set()
    _save_usage_stats()
    stop_cliproxy()


def _handle_shutdown_signal(signum, _frame):
    """Signal handler that gracefully stops HTTP server and backend process."""
    global _server_instance
    log('SYSTEM', f"Received signal {signum}, shutting down...")
    _shutdown_event.set()
    if _server_instance:
        threading.Thread(target=_server_instance.shutdown, daemon=True).start()
    else:
        _cleanup_once()


def wait_for_backend_ready(timeout=10):
    """Wait for backend to be ready by checking health endpoint."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(
                f'http://localhost:{BACKEND_PORT}/v1/models',
                headers={'Authorization': 'Bearer sk-dummy'},
                method='GET'
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    log('INFO', "Backend is ready")
                    return True
        except:
            pass
        time.sleep(0.5)
    log('WARN', "Backend readiness check timed out")
    return False


def launch_provider_login(provider):
    """Launch provider login using the installed CLIProxy binary."""
    login_flag = LOGIN_PROVIDERS.get(provider)
    if not login_flag:
        raise ValueError("Unsupported provider")
    if not os.path.exists(CLIPROXY_PATH):
        raise FileNotFoundError(f"Binary not found: {CLIPROXY_PATH}")
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")

    capture_output = provider == 'github-copilot'
    kwargs = {
        'stdin': subprocess.DEVNULL,
        'start_new_session': True,
    }
    if capture_output:
        kwargs.update({
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'text': True,
            'bufsize': 1,
        })
    else:
        kwargs.update({
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
        })

    process = subprocess.Popen([CLIPROXY_PATH, '-config', CONFIG_PATH, login_flag], **kwargs)
    if capture_output:
        _set_login_state(
            provider,
            pid=process.pid,
            running=True,
            started_at=int(time.time()),
            device_code='',
            verification_url='',
            exit_code=None,
            error=''
        )
        threading.Thread(target=_monitor_login_process, args=(provider, process), daemon=True).start()
    return process.pid

class UnifiedHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # Quieter logging
        if '/v0/' in str(args) or '/v1/' in str(args):
            return  # Skip API logging
        super().log_message(format, *args)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Management-Key, Authorization')
        super().end_headers()

    def _write_json(self, payload, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Lightweight health check endpoint
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        # API requests -> proxy to backend
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('GET')
        # System Management
        elif self.path.startswith('/api/system/'):
            self.handle_system_api('GET')
        # Root -> redirect to dashboard
        elif self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/dashboard.html')
            self.end_headers()
        else:
            # Static files
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('POST')
        elif self.path.startswith('/api/system/'):
            self.handle_system_api('POST')
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('DELETE')
        elif self.path.startswith('/api/system/'):
            self.handle_system_api('DELETE')
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('PUT')
        else:
            self.send_error(404)

    def do_PATCH(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('PATCH')
        else:
            self.send_error(404)

    def handle_system_api(self, method):
        # Extremely basic remote management endpoints for the UI
        if self.path == '/api/system/restart' and method == 'POST':
            log('SYSTEM', "Restarting backend...")
            stop_cliproxy()
            time.sleep(1)
            start_cliproxy()
            _refresh_model_aliases()
            # Wait for backend to be fully ready before responding
            backend_ready = wait_for_backend_ready(timeout=10)
            if backend_ready:
                self._write_json({"status": "restarted", "backend_ready": True})
            else:
                self._write_json({"status": "restarted", "backend_ready": False, "warning": "Backend may still be starting up"})
        elif self.path == '/api/system/stop' and method == 'POST':
            log('SYSTEM', "Stopping backend...")
            stop_cliproxy()
            self._write_json({"status": "stopped"})
        elif self.path == '/api/system/info' and method == 'GET':
            status = "online" if cliproxy_process else "offline"
            pid = cliproxy_process.pid if cliproxy_process else None
            with _model_alias_lock:
                n_models = len(_backend_model_set)
                n_cached = len(_model_alias_cache)
                known_list = sorted(_backend_model_set)
            self._write_json({
                "status": status, "pid": pid,
                "backend_models": n_models,
                "alias_cache_entries": n_cached,
                "models": known_list,
            })
        elif self.path == '/api/system/login-providers' and method == 'GET':
            providers = [
                {"id": "antigravity", "label": "Antigravity (Claude/Gemini)"},
                {"id": "github-copilot", "label": "GitHub Copilot"},
                {"id": "gemini-cli", "label": "Gemini CLI"},
                {"id": "codex", "label": "Codex"},
                {"id": "claude", "label": "Claude"},
                {"id": "qwen", "label": "Qwen"},
                {"id": "iflow", "label": "iFlow"},
            ]
            self._write_json({"providers": providers})
        elif self.path.startswith('/api/system/login-state') and method == 'GET':
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            provider = str((qs.get('provider') or [''])[0]).strip()
            if not provider:
                self.send_error(400, "Missing provider")
                return
            state = _get_login_state(provider)
            if not state:
                state = {"provider": provider, "running": False}
            else:
                state['provider'] = provider
            self._write_json(state)
        elif self.path == '/api/system/login' and method == 'POST':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                provider = str(data.get('provider', '')).strip()
                if not provider:
                    self.send_error(400, "Missing provider")
                    return

                pid = launch_provider_login(provider)
                self._write_json({
                    "status": "started",
                    "provider": provider,
                    "pid": pid,
                    "message": "Login flow started. Finish authentication in your browser, then refresh Accounts. This login is shared with the CLI on this machine."
                })
            except ValueError as e:
                self.send_error(400, str(e))
            except FileNotFoundError as e:
                self.send_error(404, str(e))
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path == '/api/system/add-provider' and method == 'POST':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                name = data.get('name', '').strip()
                base_url = data.get('base_url', '').strip()
                api_key = data.get('api_key', '').strip()
                
                if not name or not base_url or not api_key:
                    self.send_error(400, "Missing required fields")
                    return
                    
                config_path = os.path.expanduser('~/.cliproxyapi/config.yaml')
                
                # Check if provider already exists
                with open(config_path, 'r') as f:
                    content = f.read()
                    if f'- name: "{name}"' in content or f"- name: {name}" in content:
                        self.send_error(409, "Provider name already exists")
                        return

                # Attempt to fetch models
                models_yaml = ""
                chosen_base_url = base_url
                try:
                    m_list = []
                    # Try direct /models
                    urls_to_try = [base_url.rstrip('/') + '/models']
                    if '/v1' not in base_url:
                        urls_to_try.append(base_url.rstrip('/') + '/v1/models')
                        
                    for models_url in urls_to_try:
                        try:
                            m_req = urllib.request.Request(models_url, headers={'Authorization': f'Bearer {api_key}'})
                            with urllib.request.urlopen(m_req, timeout=5) as m_resp:
                                m_data = json.loads(m_resp.read().decode('utf-8'))
                                m_list = m_data.get('data', [])
                                if m_list: 
                                    if '/v1/models' in models_url:
                                        chosen_base_url = base_url.rstrip('/') + '/v1'
                                    break
                        except: continue

                    if m_list:
                        models_yaml = "    models:\n"
                        for m in m_list:
                            m_id = m.get('id')
                            if m_id:
                                models_yaml += f'      - name: "{m_id}"\n        alias: "{m_id}"\n'
                except Exception as me:
                    log('WARN', f"Could not fetch models for {name}: {me}")

                # Append to file
                append_str = f"""
  - name: "{name}"
    base-url: "{chosen_base_url}"
    api-key-entries:
      - api-key: "{api_key}"
{models_yaml}"""
                with open(config_path, 'a') as f:
                    if "openai-compatibility:" not in content:
                        f.write("\nopenai-compatibility:")
                    f.write(append_str)
                
                # Auto restart to apply changes
                stop_cliproxy()
                time.sleep(1)
                start_cliproxy()
                
                # Wait for backend to be fully ready
                backend_ready = wait_for_backend_ready(timeout=10)
                
                if backend_ready:
                    self._write_json({"status": "added_and_restarted", "backend_ready": True})
                else:
                    self._write_json({"status": "added_and_restarted", "backend_ready": False, "warning": "Backend may still be starting up"})
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path.startswith('/api/system/remove-provider/') and method == 'DELETE':
            try:
                provider_name = urllib.parse.unquote(self.path[len('/api/system/remove-provider/'):]).strip()
                if not provider_name:
                    self._write_json({"error": "Missing provider name"}, status=400)
                    return
                if _remove_provider_from_config(provider_name):
                    # Auto restart to apply changes
                    stop_cliproxy()
                    time.sleep(1)
                    start_cliproxy()
                    
                    backend_ready = wait_for_backend_ready(timeout=10)
                    
                    if backend_ready:
                        self._write_json({"status": "removed_and_restarted", "backend_ready": True})
                    else:
                        self._write_json({"status": "removed_and_restarted", "backend_ready": False, "warning": "Backend may still be starting up"})
                else:
                    self._write_json({"error": "Provider not found"}, status=404)
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path.startswith('/api/system/toggle-provider/') and method == 'PUT':
            try:
                # Extract provider name from path
                provider_name = urllib.parse.unquote(self.path[len('/api/system/toggle-provider/'):]).strip()
                if not provider_name:
                    self._write_json({"error": "Missing provider name"}, status=400)
                    return
                
                # Get enabled value from request body
                content_length = int(self.headers.get('Content-Length', 0))
                put_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
                payload = json.loads(put_data.decode('utf-8') or '{}')
                enabled = bool(payload.get('enabled', True))
                
                if _toggle_provider_in_config(provider_name, enabled):
                    # Auto restart to apply changes
                    stop_cliproxy()
                    time.sleep(1)
                    start_cliproxy()
                    
                    backend_ready = wait_for_backend_ready(timeout=10)
                    
                    if backend_ready:
                        self._write_json({"status": "updated_and_restarted", "backend_ready": True, "name": provider_name, "enabled": enabled})
                    else:
                        self._write_json({"status": "updated_and_restarted", "backend_ready": False, "warning": "Backend may still be starting up", "name": provider_name, "enabled": enabled})
                else:
                    self._write_json({"error": "Provider not found"}, status=404)
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path == '/api/system/raw-config' and method == 'GET':
            try:
                config_path = os.path.expanduser('~/.cliproxyapi/config.yaml')
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        content = f.read()
                    self._write_json({"yaml": content})
                else:
                    self.send_error(404, "Config not found")
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path == '/api/system/raw-config' and method == 'POST':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                yaml_content = data.get('yaml', '')
                if not yaml_content:
                    self.send_error(400, "YAML content is empty")
                    return
                    
                config_path = os.path.expanduser('~/.cliproxyapi/config.yaml')
                with _config_write_lock:
                    with open(config_path, 'w') as f:
                        f.write(yaml_content)
                
                # Auto restart to apply changes and wait for backend to be ready
                stop_cliproxy()
                time.sleep(1)
                start_cliproxy()
                
                # Wait for backend to be fully ready before responding
                backend_ready = wait_for_backend_ready(timeout=10)
                
                if backend_ready:
                    self._write_json({"status": "saved_and_restarted", "backend_ready": True})
                else:
                    self._write_json({"status": "saved_and_restarted", "backend_ready": False, "warning": "Backend may still be starting up"})
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def proxy_request(self, method):
        # ── Intercept management endpoints to return local stats ──────────────
        if self.path == '/v0/management/usage' and method == 'GET':
            # Return local usage statistics instead of forwarding to backend
            response = {
                "failed_requests": _usage_stats.get("failure_count", 0),
                "usage": _usage_stats
            }
            self._write_json(response)
            return

        if self.path == '/v0/management/config' and method == 'GET':
            # Return local config including openai-compatibility providers
            config_path = os.path.expanduser('~/.cliproxyapi/config.yaml')
            result = {'openai-compatibility': []}
            try:
                if os.path.exists(config_path):
                    providers = _load_providers_from_config(config_path)
                    result['openai-compatibility'] = providers
            except Exception as e:
                log('WARN', f"Failed to load config: {e}")
            self._write_json(result)
            return

        parsed_path = urllib.parse.urlparse(self.path)
        path_only = parsed_path.path

        if path_only == '/v0/management/auth-files' and method == 'GET':
            self._write_json({"files": _list_auth_files()})
            return

        if path_only.startswith('/v0/management/auth-files/') and method == 'DELETE':
            account_id = path_only[len('/v0/management/auth-files/'):]
            if _delete_auth_file_by_id(account_id):
                self._write_json({"status": "deleted", "id": urllib.parse.unquote(account_id)})
            else:
                self._write_json({"error": "Account not found"}, status=404)
            return

        if path_only.startswith('/v0/management/auth-files/') and method == 'PUT':
            account_id = path_only[len('/v0/management/auth-files/'):]
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                put_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
                payload = json.loads(put_data.decode('utf-8') or '{}')
                enabled = bool(payload.get('enabled', True))
            except Exception:
                self._write_json({"error": "Invalid request payload"}, status=400)
                return

            if _set_auth_file_disabled_by_id(account_id, not enabled):
                self._write_json({
                    "status": "updated",
                    "id": urllib.parse.unquote(account_id),
                    "enabled": enabled,
                    "disabled": not enabled,
                })
            else:
                self._write_json({"error": "Account not found"}, status=404)
            return
        
        # ── Collect incoming request ───────────────────────────────────────────
        headers = {}
        for key in ['Authorization', 'Content-Type', 'Accept']:
            val = self.headers.get(key)
            if val:
                headers[key] = val
        for key in ['x-api-key', 'anthropic-version', 'anthropic-beta']:
            val = self.headers.get(key)
            if val:
                headers[key] = val

        x_api_key = self.headers.get('x-api-key')
        if x_api_key:
            headers['Authorization'] = f'Bearer {x_api_key}'
        
        # For management endpoints: if X-Management-Key is sent (from dashboard),
        # convert it to Authorization header for backend
        if '/management/' in self.path:
            mgmt_key = self.headers.get('X-Management-Key')
            if mgmt_key:
                headers['Authorization'] = f'Bearer {mgmt_key}'

        data = None
        if method in ['POST', 'PUT', 'DELETE'] and self.headers.get('Content-Length'):
            content_length = int(self.headers.get('Content-Length'))
            data = self.rfile.read(content_length)

        # ── Apply model alias before hitting backend ───────────────────────────
        requested_model = self._extract_model(data)
        resolved_model = _resolve_model(requested_model)
        if resolved_model != requested_model:
            log('ALIAS', f"{requested_model} -> {resolved_model}")
            data = self._rewrite_model(data, resolved_model)

        # ── Check if resolved model is known to backend ───────────────────────
        # If model was not resolved (pass-through) and not in backend set,
        # skip backend attempt and go directly to failover to avoid wasting time.
        with _model_alias_lock:
            model_known = not resolved_model or resolved_model in _backend_model_set
        skip_backend = (not model_known and resolved_model == requested_model)

        # ── Check if we have a cached fallback for this model ─────────────────
        cached_fallback = _get_model_fallback(resolved_model)
        if cached_fallback:
            provider_name, fallback_model = cached_fallback
            log('FAILOVER', f"Using cached fallback: {resolved_model} → {fallback_model} via {provider_name}")
            # Try the cached fallback directly
            try:
                # Find the provider details from config
                candidates = _build_failover_candidates(resolved_model, CONFIG_PATH)
                for p_name, base_url, api_key, model in candidates:
                    if p_name == provider_name and model == fallback_model:
                        req_data = self._rewrite_model(data, fallback_model)
                        status, resp_headers, content = _direct_request(
                            base_url, api_key, self.path, method, headers, req_data
                        )
                        # Rewrite response model to match what client requested
                        if requested_model:
                            content = self._rewrite_response_model(content, requested_model)
                        self._send_proxy_response(status, resp_headers, content)
                        return
            except Exception as e:
                log('FAILOVER', f"Cached fallback failed: {e}, trying backend")
                # Clear the bad cache and continue to try backend
                _clear_model_fallback(resolved_model)

        # ── Try backend first (normal path) ───────────────────────────────────
        need_failover = False

        if skip_backend:
            log('FAILOVER', f"Model '{resolved_model}' unknown to backend — skipping to failover")
            need_failover = True

        if not need_failover:
            try:
                target_url = f'http://localhost:{BACKEND_PORT}{self.path}'
                log('PROXY', f"{method} {self.path} (model={resolved_model or '-'})")
                req = urllib.request.Request(target_url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=60) as response:
                    content = response.read()
                    if requested_model:
                        content = self._rewrite_response_model(content, requested_model)
                    self._send_proxy_response(response.status, dict(response.headers), content)
                    # Clear any cached fallback since backend is working now
                    _clear_model_fallback(resolved_model)
                    return
            except urllib.error.HTTPError as e:
                backend_code = e.code
                backend_body = e.read()

                # Quota error → failover
                if backend_code in QUOTA_ERROR_CODES:
                    log('FAILOVER', f"Quota error {backend_code} — starting failover")
                    need_failover = True

                # 502 with "unknown provider/model" → the model isn't wired in backend → failover
                elif backend_code == 502:
                    try:
                        err_msg = json.loads(backend_body).get('error', {}).get('message', '').lower()
                    except Exception:
                        err_msg = ''
                    if any(frag in err_msg for frag in UNKNOWN_MODEL_FRAGMENTS):
                        log('FAILOVER', f"Unknown model '{resolved_model}' — starting failover")
                        # Trigger a background refresh — backend may have new models
                        threading.Thread(target=_refresh_model_aliases, kwargs={'clear_cache': True},
                                         daemon=True).start()
                        need_failover = True

                if not need_failover:
                    self.send_response(backend_code)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(backend_body)
                    # Track failed request
                    _track_request(self.path, False, 0)
                    return

            except urllib.error.URLError as e:
                self.send_error(503, f"Backend unavailable: {str(e.reason)}")
                _track_request(self.path, False, 0)
                return
            except BrokenPipeError:
                log('WARN', f"Client disconnected (broken pipe) during {method} {self.path}")
                return
            except Exception as e:
                self.send_error(502, f"Proxy error: {str(e)}")
                _track_request(self.path, False, 0)
                return

        # ── Failover: try direct provider routing ─────────────────────────────
        candidates = _build_failover_candidates(resolved_model, CONFIG_PATH)

        if not candidates:
            log('FAILOVER', f"No candidates available for '{resolved_model}'")
            self._send_no_candidate_error(resolved_model)
            return

        last_error_body = None
        for provider_name, base_url, api_key, model in candidates:
            req_data = self._rewrite_model(data, model) if model != resolved_model else data
            try:
                if model != resolved_model:
                    log('FAILOVER', f"Trying {provider_name} …{api_key[-4:]} ({resolved_model} → {model})")
                else:
                    log('FAILOVER', f"Trying {provider_name} …{api_key[-4:]} model={model}")
                status, resp_headers, content = _direct_request(
                    base_url, api_key, self.path, method, headers, req_data
                )
                if model != resolved_model:
                    log('FAILOVER', f"✓ Success via {provider_name} ({resolved_model} → {model})")
                else:
                    log('FAILOVER', f"✓ Success via {provider_name} (model={model})")
                # Cache this successful fallback for future requests
                _set_model_fallback(resolved_model, provider_name, model)
                # Rewrite response model to match what client requested
                if requested_model:
                    content = self._rewrite_response_model(content, requested_model)
                self._send_proxy_response(status, resp_headers, content)
                return
            except urllib.error.HTTPError as e:
                err_body = e.read()
                if e.code in QUOTA_ERROR_CODES:
                    _set_cooldown(provider_name, api_key)
                    last_error_body = err_body
                    continue
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(err_body)
                return
            except Exception as e:
                log('FAILOVER', f"Error with {provider_name}: {e}")
                last_error_body = json.dumps({"error": str(e)}).encode()
                continue

        log('FAILOVER', "All candidates exhausted")
        self._send_no_candidate_error(resolved_model, last_error_body)

    def _extract_model(self, data: bytes | None) -> str:
        """Extract model name from JSON request body."""
        if not data:
            return ''
        try:
            body = json.loads(data.decode('utf-8', errors='replace'))
            return body.get('model', '')
        except Exception:
            return ''

    def _rewrite_model(self, data: bytes | None, new_model: str) -> bytes | None:
        """Return a copy of the request body with model field replaced."""
        if not data or not new_model:
            return data
        try:
            body = json.loads(data.decode('utf-8', errors='replace'))
            body['model'] = new_model
            return json.dumps(body).encode('utf-8')
        except Exception:
            return data

    @staticmethod
    def _rewrite_response_model(content: bytes, original_model: str) -> bytes:
        """Rewrite the model field in a JSON response back to the original requested model.

        This ensures the client (e.g. cp-claude) sees the model it asked for,
        even when the backend silently substituted a different one during failover.
        Without this, the CLI may reject the response or break the session."""
        if not content or not original_model:
            return content
        try:
            body = json.loads(content.decode('utf-8', errors='replace'))
            if 'model' in body:
                body['model'] = original_model
                return json.dumps(body).encode('utf-8')
        except Exception:
            pass
        return content

    def _send_proxy_response(self, status: int, resp_headers: dict, content: bytes):
        self.send_response(status)
        for k, v in resp_headers.items():
            if k.lower() not in ('transfer-encoding', 'connection',
                                  'access-control-allow-origin', 'content-length'):
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except BrokenPipeError:
            log('WARN', f"Client disconnected while sending response")
            return
        
        # Track usage statistics
        success = 200 <= status < 400
        tokens = 0
        # Try to extract token count from response
        try:
            if content:
                response_json = json.loads(content.decode('utf-8', errors='ignore'))
                usage = response_json.get('usage', {})
                tokens = usage.get('total_tokens', 0)
        except:
            pass
        _track_request(self.path, success, tokens)

    def _send_no_candidate_error(self, model: str, detail: bytes | None = None):
        msg = {
            "error": {
                "message": f"All providers exhausted for model '{model}'. No available quota.",
                "type": "quota_exhausted",
                "code": "no_candidate"
            }
        }
        if detail:
            try:
                msg["error"]["last_upstream_error"] = json.loads(detail)
            except Exception:
                pass
        body = json.dumps(msg).encode('utf-8')
        self.send_response(429)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        # Track failed request
        _track_request(self.path, False, 0)

def main():
    global _server_instance

    # Register cleanup
    atexit.register(_cleanup_once)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    print("""
\033[0;36m\033[1m
  ══  CLIProxy Unified Server  ══
\033[0m""")

    # Load usage statistics
    _load_usage_stats()

    # Start backend
    log('INFO', "Starting backend...")
    if not start_cliproxy():
        log('WARN', "Running without backend (API calls will fail)")

    # Build model alias map from live backend (runs in background, won't block startup)
    log('INFO', "Loading models from backend (background)...")
    def _initial_alias_load():
        if _shutdown_event.is_set():
            return
        _refresh_model_aliases()
    threading.Thread(target=_initial_alias_load, daemon=True).start()

    # Refresh backend model list every 30s (lightweight GET /v1/models)
    def _alias_refresh_loop():
        while not _shutdown_event.is_set():
            if _shutdown_event.wait(30):
                break
            try:
                _refresh_model_aliases(clear_cache=True)
            except Exception:
                pass
    threading.Thread(target=_alias_refresh_loop, daemon=True).start()

    # Watch config.yaml for changes → trigger immediate refresh when user edits it
    def _config_watcher():
        last_mtime = 0.0
        while not _shutdown_event.is_set():
            if _shutdown_event.wait(10):
                break
            try:
                mtime = os.path.getmtime(CONFIG_PATH)
                if mtime != last_mtime:
                    if last_mtime != 0.0:
                        log('WATCHER', "config.yaml changed — refreshing models")
                        _refresh_model_aliases(clear_cache=True)
                    last_mtime = mtime
            except Exception:
                pass
    threading.Thread(target=_config_watcher, daemon=True).start()

    # Start unified server
    log('INFO', f"Starting unified server on port {PUBLIC_PORT}...")

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PUBLIC_PORT), UnifiedHandler) as httpd:
        _server_instance = httpd
        print(f"""\033[32m
  Ready on http://localhost:{PUBLIC_PORT}
  Dashboard  : http://localhost:{PUBLIC_PORT}/
  API Proxy  : http://localhost:{PUBLIC_PORT}/v1/...

  Press Ctrl+C to stop
\033[0m""")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            _handle_shutdown_signal(signal.SIGINT, None)
        finally:
            _server_instance = None

    _cleanup_once()
    log('INFO', "Server stopped.")

if __name__ == '__main__':
    main()
