"""DIAGNOSTIC build — finds what crashes on Streamlit Cloud. Full app is in app_full.py."""

import streamlit as st

st.set_page_config(page_title="Jack — диагностика", page_icon="🐾")
st.title("🐾 Jack — диагностика")
st.success("✅ Сервер Streamlit работает (Python + Streamlit запустились).")
st.write("Проверяю модули по одному — если что-то красное, это и есть причина:")

import traceback

MODULES = [
    "utils.styles",
    "utils.auth",
    "models.plan_briefs",
    "models.products",
    "models.llm",
    "models.jack_engine",
    "views.content_plan",
    "views.jack_workspace",
    "views.dashboard",
    "views.content_factory",
]

for name in MODULES:
    try:
        __import__(name)
        st.write(f"✅ {name}")
    except Exception:
        st.error(f"❌ {name} — вот ошибка:")
        st.code(traceback.format_exc())
