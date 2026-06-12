"""GeeLark API client — phone profile state, real polling.

Replicates the working auth from Content Factory's autoposter.py:
- base URL:  https://openapi.geelark.com/open/v1
- signature: SHA256(appId + traceId + ts + nonce + apiKey).upper()
- /phone/list expects {"ids": [profile_id, ...]} (NOT pagination)
"""

from __future__ import annotations

import hashlib
import time as _t
import uuid
from pathlib import Path

import requests
import streamlit as st


CF_ENV = Path("/Users/macbook/Databases/02 Content Factory/code/.env")
API_BASE = "https://openapi.geelark.com/open/v1"

KNOWN_PHONES = {
    "vermont":     "616135880154808620",
    "newyork":     "616135949276938540",
    "pensilvania": "616136029354590511",
}


def _load_env() -> dict:
    env = {}
    if CF_ENV.exists():
        for line in CF_ENV.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _headers(env: dict) -> dict:
    app_id = env.get("GEELARK_APP_ID", "")
    api_key = env.get("GEELARK_API_KEY", "")
    ts = str(int(_t.time() * 1000))
    trace_id = uuid.uuid4().hex
    nonce = uuid.uuid4().hex[:6]
    raw = f"{app_id}{trace_id}{ts}{nonce}{api_key}"
    sign = hashlib.sha256(raw.encode()).hexdigest().upper()
    return {
        "appId": app_id,
        "traceId": trace_id,
        "ts": ts,
        "nonce": nonce,
        "sign": sign,
        "Content-Type": "application/json",
    }


@st.cache_data(ttl=300)
def list_phones() -> list[dict]:
    """Return list of our 3 known GeeLark phones."""
    env = _load_env()
    if not env.get("GEELARK_API_KEY") or not env.get("GEELARK_APP_ID"):
        return []
    try:
        r = requests.post(
            f"{API_BASE}/phone/list",
            headers=_headers(env),
            json={"ids": list(KNOWN_PHONES.values())},
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("items", [])
    except Exception:
        pass
    return []


@st.cache_data(ttl=120)
def health() -> dict:
    env = _load_env()
    has_keys = bool(env.get("GEELARK_API_KEY") and env.get("GEELARK_APP_ID"))
    if not has_keys:
        return {"ok": False, "message": "GEELARK_API_KEY/APP_ID missing in CF .env"}
    phones = list_phones()
    return {
        "ok": len(phones) > 0,
        "message": f"connected · {len(phones)} phones reachable" if phones else "auth ok · no phones returned",
    }


def get_phone(profile_id: str) -> dict | None:
    """Find single phone by profile_id."""
    for p in list_phones():
        if str(p.get("id")) == str(profile_id) or str(p.get("profileId")) == str(profile_id):
            return p
    return None
