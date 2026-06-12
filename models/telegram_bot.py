"""Telegram bot @belovedpets_factory_bot status puller.

Reads TELEGRAM_BOT_TOKEN from Content Factory's .env.
Uses Bot API getMe / getChat / getChatMember to verify connection.
"""

from __future__ import annotations

from pathlib import Path

import requests
import streamlit as st


CF_ENV = Path("/Users/macbook/Databases/02 Content Factory/code/.env")


def _load_env():
    env = {}
    if CF_ENV.exists():
        for line in CF_ENV.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _token() -> str | None:
    return _load_env().get("TELEGRAM_BOT_TOKEN")


@st.cache_data(ttl=120)
def health() -> dict:
    """Check the bot is alive and respond with metadata."""
    token = _token()
    if not token:
        return {"ok": False, "message": "TELEGRAM_BOT_TOKEN missing", "bot": None}
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
        if r.status_code == 200:
            d = r.json()
            if d.get("ok"):
                bot = d["result"]
                return {
                    "ok": True,
                    "message": f"@{bot.get('username')} · {bot.get('first_name')}",
                    "bot": bot,
                }
    except Exception as e:
        return {"ok": False, "message": f"network error: {e}", "bot": None}
    return {"ok": False, "message": "auth failed", "bot": None}


@st.cache_data(ttl=60)
def get_updates(limit: int = 50) -> list[dict]:
    """Return recent updates from the bot — used to count pending/approved/rejected."""
    token = _token()
    if not token:
        return []
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"limit": limit, "timeout": 0},
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("ok"):
                return d.get("result", [])
    except Exception:
        pass
    return []


def count_approvals(updates: list[dict]) -> dict:
    """Tally approve/reject/pending callback_query events."""
    counts = {"approved": 0, "rejected": 0, "pending": 0, "messages": 0}
    for u in updates:
        if "callback_query" in u:
            data = u["callback_query"].get("data", "").lower()
            if "approve" in data:
                counts["approved"] += 1
            elif "reject" in data:
                counts["rejected"] += 1
        if "message" in u:
            text = u["message"].get("text", "").lower()
            counts["messages"] += 1
            if any(w in text for w in ["approve", "одобрено", "✅"]):
                counts["approved"] += 1
            elif any(w in text for w in ["reject", "отклонено", "❌"]):
                counts["rejected"] += 1
            elif any(w in text for w in ["pending", "wait", "ожидает"]):
                counts["pending"] += 1
    return counts
