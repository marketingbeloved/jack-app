"""Знания о бренде для Джека: позиционирование, УТП, ЦА, тон, пиллары, конкуренты.

Почему отдельный модуль (решение Марии 2026-11-13, «идеи слабые и крутятся вокруг
прошлого месяца»): brand_data/ в git не уходит (репо публичный), и на Streamlit Cloud
Джек планировал месяц, НЕ зная ни позиционирования, ни ЦА. У Tobydic не было вообще
ничего, а в системный промпт подставлялось досье Beloved Pets.

Источник правды — файлы в ~/BP-Work. scripts/upload_brand_knowledge.py собирает из них
текст и кладёт в общую базу (Supabase, ключ brand_knowledge_<brand>). Сайт читает оттуда.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

BP_WORK = Path.home() / "BP-Work"
BRAND_DATA = Path(__file__).resolve().parent.parent / "brand_data"


def shared_key(brand: str) -> str:
    return "brand_knowledge_" + ("tobydic" if "toby" in (brand or "").lower() else "belovedpets")


_GUARD = ("⛔ ЧИТАТЬ ПЕРВЫМ: ниже встречаются «vet-developed / vet-recommended / vet-formulated / "
          "Made in USA» — это про конкурентов или старые значки. НАМ ЭТО ПИСАТЬ НЕЛЬЗЯ (ложь). "
          "«Lab tested in the USA» — только для лакомств. Мы Supplement, NOT a Medicine.")


def _sections(path: Path, keep: tuple[str, ...]) -> str:
    """Вырезать из markdown только разделы ## с нужными словами в заголовке."""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^(?=## )", text)
    out = [p.strip() for p in parts if p.startswith("## ") and
           any(k.lower() in p.split("\n", 1)[0].lower() for k in keep)]
    return "\n\n".join(out)


def _strip_front(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S).strip()


def build(brand: str) -> str:
    """Собрать текст знаний из исходников на маке. "" — исходников нет (облако)."""
    if "toby" in (brand or "").lower():
        pos = _sections(BP_WORK / "01 Контент-завод" / "knowledge" / "products" / "tobydic.md",
                        ("Позиционирование",))
        pos = "\n".join(l for l in pos.splitlines() if not l.startswith("- Drive:"))
        parts = []
        if pos:
            parts.append("=== TOBYDIC — позиционирование (Контент-завод) ===\n" + pos)
        parts.append(
            "=== TOBYDIC — продукт и ЦА (из каталога, факты) ===\n"
            "Herbal-капли 2 oz для собак и кошек с 12 недель: капаешь в корм, без таблеток.\n"
            "Линейка закрывает бытовые заботы хозяина: мочевыводящая система (Urinary), кожа, "
            "ухо и зуд (Yeast & Itch), кишечник (Herbal Intestinal Cleanse, + Probiotic), "
            "горло и дыхание (Kennel Cough Herbal), ежедневные витамины (21-in-1), "
            "сезон блох и клещей (Oral Flea & Tick Support). Продажи — Amazon US, Chewy, Walmart.\n"
            "ЦА выводи из этих забот: хозяин, у которого питомец не любит таблетки, "
            "который хочет мягкую ежедневную поддержку, а не «лечение».")
        return _GUARD + "\n\n" + "\n\n".join(parts) if pos else ""

    brief = _sections(BP_WORK / "BP-Brand-Brief.md",
                      ("Идентичность", "USP", "Целевая аудитория", "Tone of Voice",
                       "контент-пиллар", "Конкуренты", "Активные приоритеты"))
    if not brief:
        return ""
    parts = [_GUARD, "=== BELOVED PETS — Brand Brief (позиционирование, ЦА, тон, пиллары) ===\n" + brief]
    for fname, title in (("bp-usp.md", "УТП"), ("bp-competitors.md", "Конкуренты"),
                         ("bp-ig-current-style.md", "Текущий стиль Instagram")):
        f = BRAND_DATA / fname
        if f.exists():
            parts.append(f"=== {title} ({fname}) ===\n" + _strip_front(f.read_text(encoding='utf-8'))[:3500])
    return "\n\n".join(parts)


@lru_cache(maxsize=4)
def load(brand: str) -> str:
    """Знания для бренда: с мака — из исходников, на сайте — из общей базы."""
    text = build(brand)
    if text:
        return text
    try:
        from models import shared_store
        data = shared_store.get_json(shared_key(brand), None)
        if isinstance(data, dict):
            return (data.get("text") or "").strip()
    except Exception:
        pass
    return ""
