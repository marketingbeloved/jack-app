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

def _render_logo() -> None:
    """Beloved Pets round logo, centered in the sidebar header."""
    import base64
    from pathlib import Path
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = Path(__file__).resolve().parent / "assets" / f"logo.{ext}"
        if p.exists():
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            b64 = base64.b64encode(p.read_bytes()).decode()
            st.markdown(
                f'<div style="text-align:center; margin:10px 0 4px 0;">'
                f'<img src="data:image/{mime};base64,{b64}" '
                f'style="width:120px; height:120px; border-radius:50%; '
                f'box-shadow:0 6px 22px rgba(0,0,0,0.28);"></div>',
                unsafe_allow_html=True,
            )
            return


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
        _render_logo()
        st.divider()
        st.session_state["brand"] = st.selectbox("Brand", ["BelovedPets", "Tobydic"], index=0)
        st.divider()
        page = st.radio("Section", list(pages.keys()), index=0,
                        label_visibility="collapsed") if pages else None
        st.divider()
        st.caption("Team:")
        try:
            from models import shared_store
            team = shared_store.get_team()
            st.markdown("\n".join(f"- {m.get('name', '')} · {m.get('role', '')}" for m in team) or "—")
            with st.expander("✏️ Изменить команду"):
                st.caption("Имена/роли — общие для всех. Меняешь тут — видят все.")
                edited = st.data_editor(
                    team, num_rows="dynamic", hide_index=True, use_container_width=True,
                    key="team_editor",
                    column_config={"name": st.column_config.TextColumn("Имя"),
                                   "role": st.column_config.TextColumn("Роль")},
                )
                if st.button("💾 Сохранить команду", use_container_width=True):
                    clean = [{"name": str(r.get("name", "")).strip(), "role": str(r.get("role", "")).strip()}
                             for r in edited if str(r.get("name", "")).strip()]
                    shared_store.save_team(clean)
                    st.success("Команда обновлена — у всех.")
                    st.rerun()
        except Exception:
            # Защита от кэша Streamlit (старый модуль в памяти до ребута) — не валим всё приложение.
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
