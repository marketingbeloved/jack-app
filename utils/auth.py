"""Simple shared-password gate for the Jack app.

One password for the whole team (Darya / Dina / Vika / Tanya). The password lives
ONLY in .streamlit/secrets.toml → APP_PASSWORD (or the APP_PASSWORD env var) — it is
never hardcoded here, so this file is safe even in a public repo. If APP_PASSWORD is
not configured, the app stays locked (no default password).

Usage in app.py (right after set_page_config):
    from utils.auth import require_login
    require_login()   # shows the login screen and st.stop()s until the password is right
"""

from __future__ import annotations

import hashlib
import os

import streamlit as st


def _token() -> str:
    """Non-plaintext token kept in the URL so a page refresh doesn't re-ask the password."""
    return hashlib.sha256(_expected_password().encode()).hexdigest()[:24]


def _expected_password() -> str:
    """The team password — from Streamlit secrets or env only. No hardcoded fallback."""
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"]).strip()
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD", "").strip()


def _matches(entered: str) -> bool:
    """Forgiving compare — ignore case/spaces. False if no password configured (locked)."""
    expected = _expected_password()
    return bool(expected) and (entered or "").strip().casefold() == expected.casefold()


def require_login() -> None:
    """Block the app behind a shared password. No-op once authenticated this session."""
    if st.session_state.get("_auth_ok"):
        return

    # Persist across page refresh: token kept in the URL (?k=...). Refresh keeps the
    # query string, so the password is asked once per device, not on every reload.
    try:
        if _expected_password() and st.query_params.get("k") == _token():
            st.session_state["_auth_ok"] = True
            return
    except Exception:
        pass

    # Centered login card — form so Enter AND the button both submit reliably
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
        st.markdown("# 🐾 Jack — SMM Hub")
        st.caption("Внутренний инструмент Beloved Pets. Введи пароль команды.")
        with st.form("login_form", clear_on_submit=False):
            pw = st.text_input("Пароль", type="password", placeholder="пароль команды")
            submitted = st.form_submit_button("Войти →", use_container_width=True, type="primary")
        if submitted:
            if _matches(pw):
                st.session_state["_auth_ok"] = True
                try:
                    st.query_params["k"] = _token()  # remember login across refreshes
                except Exception:
                    pass
                st.rerun()
            else:
                st.error("Неверный пароль — спроси у Дарьи.")
        st.caption("Доступ только для команды: Дарья · Дина · Вика · Таня")

    st.stop()
