"""Jack Web App — unified content hub for Beloved Pets.

Run locally:
    cd ~/Databases/jack-app && source .venv/bin/activate && streamlit run app.py
Cloud: deployed on Streamlit Community Cloud (read-витрина 24/7).
"""

import streamlit as st

st.set_page_config(
    page_title="Jack — SMM Hub",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _register(pages: dict, label: str, module_name: str) -> None:
    """Import a view defensively — a view that can't load in this env is skipped, not fatal."""
    try:
        mod = __import__(f"views.{module_name}", fromlist=["render"])
        pages[label] = mod.render
    except Exception:  # noqa: BLE001
        pass


def _run() -> None:
    from utils.styles import inject as inject_styles
    from utils.auth import require_login

    inject_styles()
    require_login()  # shared-password gate (st.stop() until correct)

    pages: dict = {}
    _register(pages, "📅 Content Plan", "content_plan")
    _register(pages, "🐾 Jack Workspace", "jack_workspace")
    _register(pages, "📊 Dashboard", "dashboard")
    _register(pages, "🏭 Content Factory", "content_factory")

    with st.sidebar:
        st.markdown("## 🐾 Jack")
        st.caption("SMM Hub · Content Director")
        st.divider()
        st.session_state["brand"] = st.selectbox("Brand", ["BelovedPets", "Tobydic"], index=0)
        st.divider()
        page = st.radio("Section", list(pages.keys()), index=0,
                        label_visibility="collapsed") if pages else None
        st.divider()
        st.caption("Team:")
        st.markdown("- Darya · admin\n- Dina · video\n- Vika · graphics\n- Tanya · TOBYDIC")

    if page and page in pages:
        try:
            pages[page]()
        except Exception as e:  # noqa: BLE001
            st.error("Не удалось открыть раздел. Попробуй другой или обнови страницу.")
            st.caption(f"({type(e).__name__})")
    elif not pages:
        st.error("Разделы не загрузились.")


# Show the real error ON SCREEN (instead of Streamlit's generic "Oh no") so it can be
# screenshotted and fixed. Streamlit's own control-flow exceptions are re-raised.
try:
    _run()
except Exception as e:  # noqa: BLE001
    if type(e).__name__ in ("StopException", "RerunException", "RerunData"):
        raise
    import traceback
    st.error("⚠️ Ошибка запуска приложения — пришли этот текст:")
    st.code(traceback.format_exc())
