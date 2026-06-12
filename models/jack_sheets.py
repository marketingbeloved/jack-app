"""Google Sheets bridge — push graphic tasks for Vika into Darya's КП sheet.

Credentials resolution (first hit wins):
  1. st.secrets["gcp_service_account"]  — dict, for Streamlit Cloud
  2. ~/.bp-credentials/jack-sheets-sa.json — local service-account JSON
Target sheet id:
  st.secrets["VIKA_SHEET_ID"]  →  env VIKA_SHEET_ID  →  ~/.bp-credentials/vika-sheet-id.txt

Everything fails *softly*: functions return {"error": "..."} so the UI can show a
clear "настрой Service Account" message instead of crashing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SA_LOCAL = Path.home() / ".bp-credentials" / "jack-sheets-sa.json"
VIKA_TAB = "Vika tasks"  # worksheet/tab name created on first use
HEADER = ["Date", "Brand", "Market", "Title", "Product", "Format", "Brief for Vika", "Status"]


def _sheet_id() -> str:
    try:
        import streamlit as st
        if "VIKA_SHEET_ID" in st.secrets:
            return str(st.secrets["VIKA_SHEET_ID"]).strip()
    except Exception:
        pass
    if os.environ.get("VIKA_SHEET_ID"):
        return os.environ["VIKA_SHEET_ID"].strip()
    f = Path.home() / ".bp-credentials" / "vika-sheet-id.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    return ""


def _credentials():
    """Return google service-account Credentials or None."""
    try:
        from google.oauth2.service_account import Credentials
    except Exception:
        return None
    # 1) Streamlit secrets
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass
    # 2) Local JSON
    if SA_LOCAL.exists():
        try:
            info = json.loads(SA_LOCAL.read_text(encoding="utf-8"))
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception:
            return None
    return None


def is_configured() -> bool:
    return bool(_sheet_id()) and _credentials() is not None


def _open_tab():
    """Open (or create) the Vika worksheet. Returns (worksheet, None) or (None, error)."""
    sid = _sheet_id()
    if not sid:
        return None, "Не задан ID Google-таблицы КП (VIKA_SHEET_ID)."
    creds = _credentials()
    if creds is None:
        return None, "Нет Service Account — настрой Google Sheets (см. инструкцию)."
    try:
        import gspread
    except Exception:
        return None, "Не установлен gspread (pip install gspread google-auth)."
    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sid)
        try:
            ws = sh.worksheet(VIKA_TAB)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=VIKA_TAB, rows=200, cols=len(HEADER))
            ws.append_row(HEADER)
        return ws, None
    except Exception as e:  # noqa: BLE001
        return None, f"Sheets error: {e}"


def push_vika_task(concept: dict, date_str: str = "") -> dict:
    """Append a Vika graphic task row built from an approved concept.

    Uses the concept's vika_brief if present, else hook/angle. Returns {"ok": True}
    or {"error": "..."}.
    """
    ws, err = _open_tab()
    if err:
        return {"error": err}

    vb = concept.get("vika_brief") or {}
    if vb.get("scenes"):
        brief_txt = (vb.get("title", "") + "\n" + "\n".join(vb["scenes"])).strip()
    else:
        brief_txt = " — ".join([b for b in [concept.get("hook", ""), concept.get("angle", "")] if b])

    row = [
        date_str,
        concept.get("brand", "BelovedPets"),
        concept.get("market", ""),
        concept.get("title", ""),
        concept.get("product", ""),
        concept.get("format", ""),
        brief_txt,
        "To do",
    ]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"error": f"append failed: {e}"}
