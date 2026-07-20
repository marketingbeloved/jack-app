"""Content Factory metrics reader.

Reads the `content_factory_metrics` table on Supabase (populated from the monthly
SMM report — one row per phone × platform × metric × month) and shapes it for the
Content Factory view's phone→social leaf cards.

Table columns: phone, account, platform, metric, month, year, value_text, value_num.
"""
import os

# phone id used in the view  ->  phone name stored in the table
PHONE_MAP = {"vermont": "Vermont", "newyork": "New York", "pensilvania": "Pennsylvania"}
# social id used in the view ->  platform stored in the table
PLATFORM_MAP = {"tiktok": "TIK TOK", "pinterest": "PINTEREST", "youtube": "YOUTUBE", "instagram": "INSTAGRAM"}
# which stored metric fills each of the 3 leaf slots (followers / views / reach), per platform
LEAF_METRICS = {
    "TIK TOK":   {"followers": "followers",   "views": "video views",      "reach": "reached audience (28d)"},
    "INSTAGRAM": {"followers": "followers",   "views": "views",            "reach": "reach"},
    "PINTEREST": {"followers": "followers",   "views": "impressions",      "reach": "total audience"},
    "YOUTUBE":   {"followers": "subscribers", "views": "views (all-time)", "reach": None},
}
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _supabase():
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


def fetch_year(year: int = 2026) -> list:
    """All metric rows for a year. Empty list if Supabase is unreachable."""
    sb = _supabase()
    if not sb:
        return []
    url, key = sb
    try:
        import requests
        r = requests.get(
            f"{url}/rest/v1/content_factory_metrics",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "phone,platform,metric,value_text,value_num", "year": f"eq.{year}"},
            timeout=20,
        )
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def available_months(rows: list) -> list:
    """Months present in `rows`, in calendar order."""
    present = {r.get("month") for r in rows}
    return [m for m in MONTH_ORDER if m in present]


def _display(row: dict):
    """Prefer the raw text value ('13.3K', '10.7K'); fall back to the number."""
    t = row.get("value_text")
    if t not in (None, ""):
        return t
    n = row.get("value_num")
    return n


def build_lookup(rows: list, month: str) -> dict:
    """{(phone_id, social_id): {'followers':.., 'views':.., 'reach':..}} for one month.

    Missing metrics come back as None so the view can render an em dash.
    """
    idx = {}
    for r in rows:
        if r.get("month") != month:
            continue
        idx[(r.get("phone"), r.get("platform"), r.get("metric"))] = _display(r)

    out = {}
    for phone_id, phone_name in PHONE_MAP.items():
        for social_id, platform in PLATFORM_MAP.items():
            slots = {}
            for slot, metric in LEAF_METRICS[platform].items():
                slots[slot] = idx.get((phone_name, platform, metric)) if metric else None
            out[(phone_id, social_id)] = slots
    return out
