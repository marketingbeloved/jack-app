"""Jack Web App — unified content hub for Beloved Pets.

Run:
    cd ~/Databases/jack-app
    source .venv/bin/activate
    streamlit run app.py

Opens at http://localhost:8501
"""

import streamlit as st

st.set_page_config(
    page_title="Jack — SMM Hub",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.styles import inject as inject_styles  # noqa: E402
inject_styles()

from utils.auth import require_login  # noqa: E402
require_login()  # shared-password gate — blocks until the team password is entered

# Defensive imports — a view that can't load in the cloud (e.g. Content Factory needs
# local GeeLark/Telegram) must NOT crash the whole app. Broken views are skipped.
PAGES: dict = {}


def _register(label: str, module_name: str) -> None:
    try:
        mod = __import__(f"views.{module_name}", fromlist=["render"])
        PAGES[label] = mod.render
    except Exception:  # noqa: BLE001 — view unavailable in this environment, skip it
        pass


_register("📅 Content Plan", "content_plan")
_register("🐾 Jack Workspace", "jack_workspace")
_register("📊 Dashboard", "dashboard")
_register("🏭 Content Factory", "content_factory")

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🐾 Jack")
    st.caption("SMM Hub · Content Director")
    st.divider()

    brand = st.selectbox("Brand", options=["BelovedPets", "Tobydic"], index=0)
    st.session_state["brand"] = brand

    st.divider()

    page = st.radio(
        "Section",
        options=list(PAGES.keys()),
        index=0,
        label_visibility="collapsed",
    ) if PAGES else None

    st.divider()
    st.caption("Team:")
    st.markdown("- Darya · admin\n- Dina · video creator\n- Vika · graphic designer\n- Tanya · TOBYDIC lead")

# ─── Main content ───────────────────────────────────────────────────────────
if page and page in PAGES:
    try:
        PAGES[page]()
    except Exception as e:  # noqa: BLE001
        st.error("Не удалось открыть раздел. Попробуй другой раздел или обнови страницу.")
        st.caption(f"({type(e).__name__})")
elif not PAGES:
    st.error("Разделы не загрузились. Обнови страницу.")
