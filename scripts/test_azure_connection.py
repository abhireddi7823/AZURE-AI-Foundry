#!/usr/bin/env python3
"""
test_azure_connection.py
────────────────────────
Run this locally BEFORE setting up the GitHub Actions workflow.
It checks whether your Azure OpenAI endpoint, API key, and
both model deployments are reachable and responding correctly.

Usage
─────
  # Set your values here or export them as environment variables
  export AZURE_API_KEY="your_key_here"
  export AZURE_ENDPOINT="https://lre-performance-project-resource.openai.azure.com/openai/v1"
  export PRIMARY_DEPLOYMENT="gpt-4o"
  export SECONDARY_DEPLOYMENT="gpt-4o-mini"

  python test_azure_connection.py
"""

import json
import os
import sys
import time

import requests

# ── CONFIG — edit these or set as environment variables ──────────────────────

AZURE_API_KEY   = os.environ.get("AZURE_API_KEY",          "YOUR_KEY_HERE")
ENDPOINT        = os.environ.get("AZURE_ENDPOINT",         "https://lre-performance-project-resource.openai.azure.com/openai/v1")
PRIMARY         = os.environ.get("PRIMARY_DEPLOYMENT",     "gpt-4o")
SECONDARY       = os.environ.get("SECONDARY_DEPLOYMENT",   "gpt-4o-mini")

CHAT_URL        = f"{ENDPOINT}/chat/completions"

# ─────────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"

def ok(msg):    print(f"  {GREEN}✅  {msg}{RESET}")
def fail(msg):  print(f"  {RED}❌  {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠️   {msg}{RESET}")
def info(msg):  print(f"  {CYAN}ℹ️   {msg}{RESET}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}")


# ── Test 1: Config sanity check ───────────────────────────────────────────────

def check_config():
    header("[ 1 / 4 ]  Config check")
    passed = True

    if AZURE_API_KEY in ("", "YOUR_KEY_HERE"):
        fail("AZURE_API_KEY is not set — edit the script or export the env var")
        passed = False
    else:
        masked = AZURE_API_KEY[:4] + "****" + AZURE_API_KEY[-4:]
        ok(f"AZURE_API_KEY found → {masked}")

    info(f"Endpoint  : {ENDPOINT}")
    info(f"Chat URL  : {CHAT_URL}")
    info(f"Primary   : {PRIMARY}")
    info(f"Secondary : {SECONDARY}")

    return passed


# ── Test 2: Endpoint reachability (no auth) ───────────────────────────────────

def check_endpoint_reachable():
    header("[ 2 / 4 ]  Endpoint reachability")
    try:
        # Hit the base URL — expect any HTTP response (even 401 means reachable)
        r = requests.get(ENDPOINT, timeout=10)
        if r.status_code in (200, 401, 404):
            ok(f"Endpoint reachable — HTTP {r.status_code}")
            return True
        else:
            warn(f"Unexpected status {r.status_code} — endpoint may be misconfigured")
            return True   # still reachable
    except requests.exceptions.ConnectionError:
        fail(f"Cannot reach endpoint — check the URL or your network/VPN")
        return False
    except requests.exceptions.Timeout:
        fail("Connection timed out — endpoint may be down or blocked")
        return False
    except Exception as e:
        fail(f"Unexpected error: {e}")
        return False


# ── Test 3: API key authentication ────────────────────────────────────────────

def check_auth():
    header("[ 3 / 4 ]  API key authentication")
    # Send a minimal request with a non-existent model to test auth only
    headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
    body    = {"model": "__auth_check__", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
    try:
        r = requests.post(CHAT_URL, headers=headers, json=body, timeout=15)
        if r.status_code == 401:
            fail("API key rejected (401 Unauthorized) — check your AZURE_API_KEY value")
            return False
        elif r.status_code == 404:
            # 404 on a bad model name means auth passed but model not found — expected
            ok("API key accepted (authentication successful)")
            return True
        elif r.status_code == 200:
            ok("API key accepted")
            return True
        else:
            warn(f"HTTP {r.status_code} — {r.text[:200]}")
            return True
    except Exception as e:
        fail(f"Auth check error: {e}")
        return False


# ── Test 4: Model deployment test ─────────────────────────────────────────────

def check_model(model: str, label: str) -> bool:
    print(f"\n  Testing {label}: {CYAN}{model}{RESET}")
    headers = {"api-key": AZURE_API_KEY, "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user",   "content": "Reply with exactly: CONNECTION OK"},
        ],
        "max_tokens": 10,
        "temperature": 0,
    }
    start = time.time()
    try:
        r = requests.post(CHAT_URL, headers=headers, json=body, timeout=30)
        elapsed = round(time.time() - start, 2)

        if r.status_code == 200:
            data    = r.json()
            reply   = data["choices"][0]["message"]["content"].strip()
            tokens  = data.get("usage", {})
            ok(f"Model responded in {elapsed}s")
            info(f"Response  : {reply}")
            info(f"Tokens    : prompt={tokens.get('prompt_tokens','?')}  completion={tokens.get('completion_tokens','?')}")
            return True

        elif r.status_code == 404:
            fail(f"Deployment '{model}' not found (404) — check the deployment name in Azure portal")
            _print_deployment_hint(r)
            return False

        elif r.status_code == 429:
            fail(f"Rate limit hit (429) — quota exceeded or too many requests")
            return False

        else:
            fail(f"HTTP {r.status_code} after {elapsed}s")
            info(f"Response body: {r.text[:300]}")
            return False

    except requests.exceptions.Timeout:
        fail(f"Request timed out after 30s — model may be cold-starting, try again")
        return False
    except Exception as e:
        fail(f"Unexpected error: {e}")
        return False


def _print_deployment_hint(response):
    """Try to print available deployments from the error body."""
    try:
        body = response.json()
        msg  = body.get("error", {}).get("message", "")
        if msg:
            info(f"Azure error: {msg}")
    except Exception:
        pass


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(results: dict):
    header("=" * 50)
    print(f"{BOLD}  Summary{RESET}")
    print("=" * 50)
    all_passed = True
    for check, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {status}  {check}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print(f"  {GREEN}{BOLD}All checks passed — ready to add secrets to GitHub!{RESET}")
    else:
        print(f"  {RED}{BOLD}Some checks failed — fix the issues above before setting up GitHub Actions.{RESET}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}Azure OpenAI Connection Test{RESET}")
    print("=" * 50)

    results = {}

    # 1. Config
    results["Config check"] = check_config()
    if not results["Config check"]:
        print_summary(results)
        sys.exit(1)

    # 2. Reachability
    results["Endpoint reachable"] = check_endpoint_reachable()
    if not results["Endpoint reachable"]:
        print_summary(results)
        sys.exit(1)

    # 3. Auth
    results["API key valid"] = check_auth()
    if not results["API key valid"]:
        print_summary(results)
        sys.exit(1)

    # 4. Models
    header("[ 4 / 4 ]  Model deployment tests")
    results[f"Primary model ({PRIMARY})"]     = check_model(PRIMARY,   "Primary  ")
    results[f"Secondary model ({SECONDARY})"] = check_model(SECONDARY, "Secondary")

    print_summary(results)
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
