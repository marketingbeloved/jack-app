"""Public-page social scraper — pulls followers from open HTML, no auth needed.

Supports:
- TikTok (followerCount in SIGI_STATE)
- Instagram (og:description heuristic + edge_followed_by)
- YouTube (channel page subscriberCountText)
- Pinterest (follower_count in __NEXT_DATA__)
- Facebook → limited without auth, often blocked
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests
import streamlit as st


CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
SOCIAL_CACHE = CACHE_DIR / "socials.json"
CACHE_TTL = 3600  # 1h

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


def _read_cache() -> dict:
    if not SOCIAL_CACHE.exists():
        return {}
    try:
        data = json.loads(SOCIAL_CACHE.read_text(encoding="utf-8"))
        if time.time() - data.get("ts", 0) < CACHE_TTL:
            return data.get("data", {})
    except Exception:
        return {}
    return {}


def _write_cache(data: dict) -> None:
    SOCIAL_CACHE.write_text(
        json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def tiktok_followers(handle: str) -> int | None:
    """@handle without @"""
    handle = handle.lstrip("@")
    try:
        r = requests.get(f"https://www.tiktok.com/@{handle}", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        # SIGI_STATE script tag
        m = re.search(r'"followerCount":(\d+)', r.text)
        if m:
            return int(m.group(1))
    except Exception:
        return None
    return None


def instagram_followers(handle: str) -> int | None:
    handle = handle.lstrip("@")
    try:
        r = requests.get(f"https://www.instagram.com/{handle}/", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        # og:description ~ "12.3K Followers, 7,913 Following, 773 Posts"
        m = re.search(r'"description"\s*content="([\d,.KMB ]+)\s*Followers', r.text)
        if m:
            return _parse_human(m.group(1))
        m = re.search(r'edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', r.text)
        if m:
            return int(m.group(1))
    except Exception:
        return None
    return None


def youtube_followers(channel_id_or_handle: str) -> int | None:
    """Accepts channel ID (UC...) or @handle."""
    val = channel_id_or_handle
    if val.startswith("UC"):
        url = f"https://www.youtube.com/channel/{val}"
    else:
        url = f"https://www.youtube.com/@{val.lstrip('@')}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        m = re.search(r'"subscriberCountText"[^}]*"simpleText"\s*:\s*"([\d,.KMB ]+) subscriber', r.text)
        if m:
            return _parse_human(m.group(1))
        m = re.search(r'"subscriberCountText"[^}]*"text"\s*:\s*"([\d,.KMB ]+) subscriber', r.text)
        if m:
            return _parse_human(m.group(1))
    except Exception:
        return None
    return None


def pinterest_followers(handle: str) -> int | None:
    handle = handle.lstrip("@")
    try:
        r = requests.get(f"https://www.pinterest.com/{handle}/", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        m = re.search(r'"follower_count"\s*:\s*(\d+)', r.text)
        if m:
            return int(m.group(1))
    except Exception:
        return None
    return None


def socialblade_followers(platform: str, handle: str) -> int | None:
    """Social Blade public-stats page — works for tiktok/instagram/youtube without auth."""
    handle = handle.lstrip("@")
    if platform == "youtube":
        path = "user" if not handle.startswith("UC") else "channel"
        url = f"https://socialblade.com/youtube/{path}/{handle}"
    elif platform == "tiktok":
        url = f"https://socialblade.com/tiktok/user/{handle}"
    elif platform == "instagram":
        url = f"https://socialblade.com/instagram/user/{handle}"
    else:
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        # Social Blade exposes followers in <p>FOLLOWERS</p><p>12,345</p>
        m = re.search(r'>([\d,]+)<\s*/p>\s*<p[^>]*>FOLLOWERS', r.text, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
        m = re.search(r'FOLLOWERS[^>]*>\s*<[^>]+>\s*([\d,]+)', r.text, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
        m = re.search(r'SUBSCRIBERS[^>]*>\s*<[^>]+>\s*([\d,]+)', r.text, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
    except Exception:
        return None
    return None


def facebook_followers(page: str) -> int | None:
    """FB is hostile without auth — try og:description heuristic, often None."""
    try:
        r = requests.get(f"https://www.facebook.com/{page}/", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        m = re.search(r'([\d,.KMB ]+) people like this', r.text)
        if m:
            return _parse_human(m.group(1))
        m = re.search(r'([\d,.KMB ]+) followers', r.text, re.IGNORECASE)
        if m:
            return _parse_human(m.group(1))
    except Exception:
        return None
    return None


def _parse_human(s: str) -> int | None:
    s = s.replace(",", "").replace(" ", "").upper()
    try:
        if s.endswith("K"):
            return int(float(s[:-1]) * 1_000)
        if s.endswith("M"):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith("B"):
            return int(float(s[:-1]) * 1_000_000_000)
        return int(float(s))
    except ValueError:
        return None


@st.cache_data(ttl=CACHE_TTL)
def fetch_all(handles: dict) -> dict:
    """Fetch followers for a dict of platform → handle.

    handles example:
        {
            "tiktok":    "beloved_pets_",
            "instagram": "beloved_pets_brand",
            "youtube":   "UCSphpE0Ela9ozJN7eyyIJsA",
            "facebook":  "BelovedPetsBrand",
            "pinterest": "belovedpets",
        }
    """
    cached = _read_cache()
    if cached and all(p in cached for p in handles):
        return cached

    fetchers = {
        "tiktok":    tiktok_followers,
        "instagram": instagram_followers,
        "youtube":   youtube_followers,
        "facebook":  facebook_followers,
        "pinterest": pinterest_followers,
    }
    result = {}
    for platform, handle in handles.items():
        if not handle:
            result[platform] = None
            continue
        fetch = fetchers.get(platform)
        n = fetch(handle) if fetch else None
        # Social Blade fallback for IG/YT/TT when direct scrape gives None
        if n is None and platform in ("tiktok", "instagram", "youtube"):
            n = socialblade_followers(platform, handle)
        result[platform] = {"raw": n, "human": _human(n) if n else "—", "handle": handle}
    _write_cache(result)
    return result


# Default brand handles — from memory bp-socials
BRAND_HANDLES = {
    "tiktok":    "beloved_pets_",
    "instagram": "beloved_pets_brand",
    "youtube":   "UCSphpE0Ela9ozJN7eyyIJsA",
    "facebook":  "BelovedPetsBrand",
    "pinterest": "belovedpets",
}
