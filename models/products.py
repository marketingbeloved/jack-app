"""Products knowledge base — loads 58 BelovedPets SKUs from Content Factory products.json.

Provides:
- list_products(category=None, search=None) — filtered list
- get_product(id) — single SKU with full data
- categories() — {treats: 39, supplement: 15, spray: 4}
- global_compliance() — brand-wide compliance rules
- compliance_for(product) — per-SKU compliance (forbidden + safe phrases)
"""

from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache

PRODUCTS_JSON = Path("/Users/macbook/Databases/02 Content Factory/code/assets/products/products.json")


@lru_cache(maxsize=1)
def _load():
    if not PRODUCTS_JSON.exists():
        return {"products": [], "global_compliance": {}, "category_knowledge_base": {}}
    return json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))


def all_products() -> list[dict]:
    """Merge Content Factory's 58 SKUs + extras added by Darya via chat."""
    base = _load().get("products", [])
    try:
        from models.products_extend import load_extra
        return base + load_extra()
    except Exception:
        return base


def categories() -> dict[str, int]:
    return _load().get("categories_count", {})


def global_compliance() -> dict:
    return _load().get("global_compliance", {})


def category_kb() -> dict:
    return _load().get("category_knowledge_base", {})


def get_product(product_id: str) -> dict | None:
    for p in all_products():
        if p.get("id") == product_id:
            return p
    return None


def list_products(category: str | None = None, search: str | None = None) -> list[dict]:
    items = all_products()
    if category and category != "all":
        items = [p for p in items if p.get("category") == category]
    if search:
        q = search.lower()
        items = [
            p for p in items
            if q in (p.get("title", "") + " " + p.get("description_short", "")).lower()
        ]
    return items


def short_title(p: dict, max_len: int = 50) -> str:
    """Return a short brand-stripped title for display."""
    t = p.get("title", "")
    # Strip overly long marketing tail after the dash
    if " - " in t:
        t = t.split(" - ", 1)[0]
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return t


def safe_phrases(p: dict) -> list[str]:
    """Per-SKU + global safe phrases combined."""
    cat_rules = p.get("compliance", {}).get("category_rules", {})
    out = list(cat_rules.get("safe_claims", []))
    out.extend(global_compliance().get("always_use_safe_phrases", []))
    # de-dup preserving order
    seen = set()
    result = []
    for x in out:
        if x.lower() not in seen:
            result.append(x)
            seen.add(x.lower())
    return result


def forbidden_phrases(p: dict) -> list[str]:
    cat_rules = p.get("compliance", {}).get("category_rules", {})
    return list(cat_rules.get("forbidden_phrases", []))


# ─── Резолвер товара из описания задачи (рус/англ) ──────────────────────────
# Дарья пишет «сделай рилс про салфетки» — Джек должен сам найти товар в каталоге,
# а не переспрашивать. Ключ = стем/слово в тексте (рус или англ), значение =
# поисковый термин по каталогу (совпадает с англ. title/description_short).
_PRODUCT_HINTS = {
    "салфетк": "wipe", "вайпс": "wipe", "wipe": "wipe", "pads": "wipe",
    "капл": "eye wash", "промыв": "eye wash", "глаз": "eye", "eye wash": "eye wash", "tear stain": "tear",
    "успокоит": "calming", "калминг": "calming", "стресс": "calming", "тревог": "calming",
    "calm": "calming", "anxiet": "calming",
    "масло": "hemp", "конопл": "hemp", "гемп": "hemp", "hemp": "hemp",
    "дрожж": "yeast", "yeast": "yeast", "уши": "ear", "ушн": "ear", "ear": "ear",
    "блох": "flea", "flea": "flea", "клещ": "tick", "tick": "tick",
    "пробиотик": "probiotic", "probiotic": "probiotic", "кишеч": "intestinal",
    "жкт": "intestinal", "пищевар": "digest", "intestinal": "intestinal",
    "зуб": "dental", "dental": "dental", "полост": "dental",
    "лакомств": "treat", "вкусняшк": "treat", "джерки": "jerky", "jerky": "jerky",
    "treats": "treat", "chew": "chew",
    "сустав": "joint", "joint": "joint", "хондро": "joint",
    "витамин": "multivitamin", "мультивитамин": "multivitamin", "multivitamin": "multivitamin",
    "шерст": "skin", "кож": "skin", "skin": "skin", "coat": "coat",
    "uti": "uti", "мочев": "urinary", "цистит": "urinary", "urinary": "urinary",
    "spray": "spray", "спрей": "spray",
}


def resolve_products(text: str, limit: int = 4) -> list[dict]:
    """По описанию задачи (рус/англ) найти товары в каталоге.

    «салфетки» → Eye Wash Wipes, «успокоительное» → Calming Chews и т.п.
    Возвращает список совпавших товаров (пусто — если ничего не опознано).
    Используется, чтобы Джек НЕ переспрашивал товар, когда он однозначен.
    """
    t = (text or "").lower()
    terms = []
    for stem, term in _PRODUCT_HINTS.items():
        if stem in t and term not in terms:
            terms.append(term)
    out, seen = [], set()
    for term in terms:
        for p in list_products(search=term):
            pid = p.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                out.append(p)
                if len(out) >= limit:
                    return out
    return out
