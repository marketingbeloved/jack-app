"""Tiny shared key→JSON store on Supabase (reuses the plan_briefs table).

For data that must SYNC across all users (Darya, Tanya, the team) and SURVIVE
Streamlit Cloud reboots, but isn't a content-plan cell — e.g. brand corpora and
the Jack Workspace concepts/captions pipeline.

Keys are namespaced with a leading '__' in post_id (e.g. '__concepts__',
'__corpus_tobydic__'), so plan_briefs.load_all() skips them and the content plan
is unaffected. Falls back to "not configured" (returns the caller's default) when
there are no Supabase creds — i.e. a Mac with no secrets behaves exactly as before.
"""

from __future__ import annotations

import json
import os


def _supabase():
    """Return (url, key) or None — same resolution order as plan_briefs."""
    url = key = ""
    try:
        import streamlit as st
        if "SUPABASE_URL" in st.secrets:
            url = str(st.secrets["SUPABASE_URL"]).strip()
        if "SUPABASE_KEY" in st.secrets:
            key = str(st.secrets["SUPABASE_KEY"]).strip()
    except Exception:
        pass
    url = url or os.environ.get("SUPABASE_URL", "").strip()
    key = key or os.environ.get("SUPABASE_KEY", "").strip()
    return (url.rstrip("/"), key) if url and key else None


def configured() -> bool:
    return _supabase() is not None


def _headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _pid(key: str) -> str:
    return f"__{key}__"


def get_json(key: str, default=None):
    """Read the value stored under `key`, or `default` if missing / not configured."""
    sb = _supabase()
    if not sb:
        return default
    import requests
    url, k = sb
    try:
        r = requests.get(
            f"{url}/rest/v1/plan_briefs?post_id=eq.{_pid(key)}&select=data",
            headers=_headers(k), timeout=20,
        )
        if r.status_code == 200 and r.json():
            data = r.json()[0].get("data") or {}
            return data.get("v", default)
    except Exception:
        pass
    return default


DEFAULT_TEAM = [
    {"name": "Darya", "role": "admin"},
    {"name": "Dina", "role": "video"},
    {"name": "Vika", "role": "graphics"},
    {"name": "Tanya", "role": "TOBYDIC"},
]


def get_team() -> list:
    """Team roster (shared across everyone). Editable in the sidebar."""
    t = get_json("team", None)
    return t if t else [dict(x) for x in DEFAULT_TEAM]


def save_team(team: list) -> bool:
    return put_json("team", team)


def put_avatar(slug: str, b64_uri: str) -> bool:
    """Сохранить фото-аватарку члена команды в общую базу (row __avatar_<slug>__.b64),
    в том же формате, который читает content_plan._db_avatar."""
    sb = _supabase()
    if not sb:
        return False
    import requests
    url, k = sb
    h = _headers(k)
    h["Prefer"] = "resolution=merge-duplicates"
    try:
        r = requests.post(
            f"{url}/rest/v1/plan_briefs", headers=h, timeout=30,
            data=json.dumps([{"post_id": f"__avatar_{slug}__", "data": {"b64": b64_uri}, "updated": ""}]),
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False


def put_json(key: str, value) -> bool:
    """Upsert `value` under `key`. Returns True on success, False otherwise."""
    sb = _supabase()
    if not sb:
        return False
    import requests
    url, k = sb
    h = _headers(k)
    h["Prefer"] = "resolution=merge-duplicates"
    try:
        r = requests.post(
            f"{url}/rest/v1/plan_briefs", headers=h, timeout=30,
            data=json.dumps([{"post_id": _pid(key), "data": {"v": value}, "updated": ""}]),
        )
        return r.status_code in (200, 201, 204)
    except Exception:
        return False
