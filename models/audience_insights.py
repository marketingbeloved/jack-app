"""Знания о ЦА из ресёрча — боли хозяев, что работает в соцсетях, что нет.

Первый источник — ресёрч Threads (октябрь 2026, BP-Work/04 Threads-ресёрч). Блок уходит
в промпты рядом с правилами команды: месячный план, концепты, чат. Джек берёт отсюда
углы и хуки словами самой ЦА, а не выдумывает «боли» из головы.

Где лежит: brand_data/audience_insights_<brand>.md (в git не уходит — репо публичный).
На Streamlit Cloud файла нет, поэтому текст заливается в Supabase скриптом
scripts/upload_insights.py — так же, как каталог товаров.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

BRAND_DATA = Path(__file__).resolve().parent.parent / "brand_data"


def shared_key(brand: str) -> str:
    return f"audience_insights_{(brand or '').strip().lower()}"


def local_file(brand: str) -> Path:
    return BRAND_DATA / f"{shared_key(brand)}.md"


@lru_cache(maxsize=4)
def load(brand: str) -> str:
    """Текст знаний для бренда, или "" — у Tobydic своего ресёрча пока нет."""
    f = local_file(brand)
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    try:
        from models import shared_store
        data = shared_store.get_json(shared_key(brand), None)
        if isinstance(data, dict):
            return (data.get("text") or "").strip()
    except Exception:
        pass
    return ""


def render_for_prompt(brand: str) -> str:
    text = load(brand)
    if not text:
        return ""
    return ("\n\n=== ЗНАНИЯ О ЦА ИЗ РЕСЁРЧА (реальные посты хозяев, не догадки) ===\n"
            "Опирайся на эти боли и форматы, когда выбираешь тему, хук и угол. Цифры не "
            "пересказывай в контенте — это фон для решений.\n" + text + "\n")
