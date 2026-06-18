"""Persistent per-cell briefs for the content plan (shared across all viewers).

Two backends, picked automatically:
  • Supabase (cloud)  — when SUPABASE_URL + SUPABASE_KEY are set (Streamlit secrets/env).
    Needed on Streamlit Cloud, where the local filesystem resets on every reboot, so a
    plain JSON file would lose the team's ТЗ. One table holds everything (see SQL below).
  • Local JSON file   — locally on Darya's Mac (no cloud creds), same as before.

Supabase table (run once in the SQL editor):
    create table if not exists plan_briefs (
      post_id text primary key,
      data    jsonb not null,
      updated text
    );

Keyed by post id (the ids in views/content_plan.py PLAN). Each entry:
    {"text": "...", "link": "...", "title": "...", "pillar": "...", "for": "vika", "updated": "DD.MM HH:MM"}
"""

from __future__ import annotations

import json
import os
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / "cache" / "plan_briefs.json"
STORE.parent.mkdir(exist_ok=True)


# ─── backend selection ───────────────────────────────────────────────────────
def _supabase():
    """Return (url, key) for Supabase, or None to use the local file."""
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


def _sb_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


# ─── public API (same signatures for both backends) ─────────────────────────
def load_all() -> dict:
    sb = _supabase()
    if sb:
        return _sb_load_all(sb)
    return _file_load_all()


def get(post_id: str) -> dict:
    return load_all().get(post_id, {})


def ensure_synced() -> int:
    """Self-heal: push any locally-saved ТЗ that are MISSING from the shared cloud.

    Guards against the Friday failure mode — a brief saved while Supabase was
    unreachable / secrets weren't loaded would otherwise live only on one Mac and
    stay invisible to the team. We only upload briefs absent in the cloud, so a
    newer shared edit is never overwritten. Returns how many were re-synced.
    """
    sb = _supabase()
    if not sb:
        return 0
    cloud = _sb_load_all(sb)
    local = _file_load_all()
    pushed = 0
    for pid, entry in local.items():
        if pid in cloud:
            continue
        if not (entry.get("text") or entry.get("link")):
            continue
        _sb_upsert(sb, pid, entry, entry.get("updated", ""))
        pushed += 1
    return pushed


def save(post_id: str, text: str, *, title: str = "", pillar: str = "",
         for_who: str = "vika", updated: str = "", link: str = "", wish: str = "") -> None:
    text = (text or "").strip()
    link = (link or "").strip()
    entry = {"text": text, "link": link, "title": title,
             "pillar": pillar, "for": for_who, "updated": updated, "wish": (wish or "").strip()}
    keep = entry if (text or link) else None
    sb = _supabase()
    if sb:
        if keep is None:
            _sb_delete(sb, post_id)
        else:
            _sb_upsert(sb, post_id, entry, updated)
    # Always mirror to the local file too — a durable backup so ТЗ never get lost
    # if Supabase is unreachable or secrets aren't loaded for some run.
    try:
        _file_save(post_id, keep)
    except Exception:
        pass


def delete(post_id: str) -> None:
    sb = _supabase()
    if sb:
        _sb_delete(sb, post_id)
    try:
        _file_save(post_id, None)
    except Exception:
        pass


# ─── Supabase backend ────────────────────────────────────────────────────────
def _sb_load_all(sb) -> dict:
    import requests
    url, key = sb
    try:
        r = requests.get(f"{url}/rest/v1/plan_briefs?select=post_id,data",
                         headers=_sb_headers(key), timeout=15)
        if r.status_code == 200:
            # Skip '__'-namespaced rows (shared_store: corpora, concepts) — they
            # live in the same table but are not content-plan cells.
            return {row["post_id"]: row["data"] for row in r.json()
                    if row.get("data") and not str(row["post_id"]).startswith("__")}
    except Exception:
        pass
    return {}


def _sb_upsert(sb, post_id: str, entry: dict, updated: str) -> None:
    import requests
    url, key = sb
    h = _sb_headers(key)
    h["Prefer"] = "resolution=merge-duplicates"
    requests.post(f"{url}/rest/v1/plan_briefs", headers=h, timeout=15,
                  data=json.dumps([{"post_id": post_id, "data": entry, "updated": updated}]))


def _sb_delete(sb, post_id: str) -> None:
    import requests
    url, key = sb
    requests.delete(f"{url}/rest/v1/plan_briefs?post_id=eq.{post_id}",
                    headers=_sb_headers(key), timeout=15)


# ─── Local file backend ──────────────────────────────────────────────────────
def _file_load_all() -> dict:
    if not STORE.exists():
        return {}
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _file_save(post_id: str, entry: dict | None) -> None:
    data = _file_load_all()
    if entry is None:
        data.pop(post_id, None)
    else:
        data[post_id] = entry
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
