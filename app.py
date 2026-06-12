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

from views import dashboard, content_plan, jack_workspace, content_factory, products_library  # noqa: E402

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🐾 Jack")
    st.caption("SMM Hub · Content Director")
    st.divider()

    # Brand switcher
    brand = st.selectbox(
        "Brand",
        options=["BelovedPets", "Tobydic"],
        index=0,
    )
    st.session_state["brand"] = brand

    st.divider()

    # Navigation
    page = st.radio(
        "Section",
        options=[
            "📊 Dashboard",
            "📅 Content Plan",
            "🐾 Jack Workspace",
            "🏭 Content Factory",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("Team:")
    st.markdown("- Darya · admin\n- Dina · video creator\n- Vika · graphic designer\n- Tanya · TOBYDIC lead")

    st.divider()
    st.caption("Status: 🚧 MVP in progress")

# ─── Main content ───────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    dashboard.render()
elif page == "📅 Content Plan":
    content_plan.render()
elif page == "🐾 Jack Workspace":
    jack_workspace.render()
elif page == "🏭 Content Factory":
    content_factory.render()
