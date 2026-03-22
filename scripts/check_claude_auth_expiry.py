#!/usr/bin/env python3
"""Check Claude CLI credential expiry from .credentials.json."""
import json
import pathlib
import sys
import time


def main():
    cred_file = pathlib.Path.home() / ".claude" / ".credentials.json"

    if not cred_file.exists():
        print("  No .credentials.json found")
        return

    try:
        data = json.loads(cred_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  Failed to read credentials: {exc}")
        return

    oauth = data.get("claudeAiOauth", {})
    if not isinstance(oauth, dict):
        print("  Unexpected credential format")
        return

    expires_at = oauth.get("expiresAt", 0)
    if not expires_at:
        print("  No expiresAt field - token format may differ")
        return

    remaining_s = (expires_at / 1000) - time.time()
    remaining_h = remaining_s / 3600

    if remaining_h <= 0:
        print(f"  \u274c EXPIRED ({abs(remaining_h):.1f} hours ago)")
        print("  \U0001f504 Run: make claude-agent-login")
    elif remaining_h < 1:
        print(f"  \u26a0\ufe0f  Expires in {remaining_h * 60:.0f} minutes")
        print("  \U0001f504 Run: make claude-agent-login")
    elif remaining_h < 24:
        print(f"  \u26a0\ufe0f  Expires in {remaining_h:.1f} hours")
        print("  Consider: make claude-agent-auth-seed")
    else:
        print(f"  \u2705 VALID - expires in {remaining_h:.1f} hours ({remaining_h / 24:.1f} days)")

    # Also show subscription info
    sub_type = oauth.get("subscriptionType")
    rate_tier = oauth.get("rateLimitTier")
    if sub_type:
        print(f"  Subscription: {sub_type}, rate tier: {rate_tier or 'default'}")


if __name__ == "__main__":
    main()
