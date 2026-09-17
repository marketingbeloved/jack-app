"""Products knowledge base — loads 58 BelovedPets SKUs from Content Factory products.json.

Provides:
- list_products(category=None, search=None) — filtered list
- get_product(id) — single SKU with full data
- categories() — {treats: 39, supplement: 15, spray: 4}
- global_compliance() — brand-wide compliance rules
- compliance_for(product) — per-SKU compliance (forbidden + safe phrases)
"""

from __future__ import annotations

import re

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


# ─── Железное правило по товарам: точное название + вкус, без выдумок ───────
#
# Джек выдумывал товары и терял вкус («чуйбол флиантик пилс»), потому что в промпт
# уходило только «Total 58 SKUs» с количеством по категориям — самих названий он не
# видел. Ниже всё, что нужно, чтобы он брал название из библиотеки и называл вкус.

_FLAVOR_WORDS = ("salmon", "chicken", "beef", "bacon", "duck", "tuna", "turkey",
                 "peanut butter", "sweet potato", "cod")


def flavor_of(p: dict) -> str:
    """Вкус/вариант товара — он живёт внутри названия, отдельного поля в данных нет.

    Форматы, которые реально встречаются: «… (Salmon (for Cats))», «… (Beef)»,
    «… with Chicken Flavor …», «… Bacon Flavor», «… Tuna + Chicken Mix 40 Sticks».
    """
    title = p.get("title", "") if isinstance(p, dict) else str(p)
    m = re.search(r"\(([^()]*(?:\([^()]*\))?[^()]*)\)\s*$", title)
    if m:
        inside = m.group(1).strip()
        if any(w in inside.lower() for w in _FLAVOR_WORDS):
            return inside
    m = re.search(r"\b((?:%s)(?:\s*\+\s*\w+)?)\s+Flavou?r(?:ed)?\b" % "|".join(_FLAVOR_WORDS),
                  title, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\bwith\s+((?:%s))\b" % "|".join(_FLAVOR_WORDS), title, re.I)
    if m:
        return m.group(1).strip()
    return ""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def find_exact(title: str) -> dict | None:
    """Товар по полному названию (регистр и пунктуация не важны). None — такого нет."""
    n = _norm(title)
    if not n:
        return None
    for p in all_products():
        if _norm(p.get("title", "")) == n:
            return p
    return None


def find_mentioned(title: str) -> dict | None:
    """Товар, чьё название совпадает или является началом указанного (и наоборот).

    Джек иногда обрезает хвост названия — это не «выдуманный товар», а неполное имя.
    """
    n = _norm(title)
    if len(n) < 12:
        return None
    for p in all_products():
        pn = _norm(p.get("title", ""))
        if n == pn or n.startswith(pn[:60]) or pn.startswith(n[:60]):
            return p
    return None


def catalog_block(brand: str = "BelovedPets", limit: int = 80) -> str:
    """ТОЧНЫЕ названия товаров для промпта — целиком, со вкусом, без обрезки.

    Раньше в промпт уходил `short_title(..., 50)`, и хвост «(Salmon (for Cats))»
    отрезался вместе со вкусом — Джек про вкус и не знал.
    """
    if (brand or "").strip().lower() != "belovedpets":
        return ("\nБИБЛИОТЕКИ ТОВАРОВ ПО ЭТОМУ БРЕНДУ НЕТ. Бери товары ТОЛЬКО из прошлых постов "
                "и ТЗ этого бренда. СТРОГО ЗАПРЕЩЕНО называть SKU другого бренда (Beloved Pets "
                "и его линейки) — это разные бренды. Не знаешь точное название — напиши общо "
                "(«наши капли»), но чужое имя не подставляй и своё не выдумывай.\n")

    by_cat: dict[str, list[dict]] = {}
    for p in all_products()[:limit]:
        by_cat.setdefault(str(p.get("category") or "Прочее"), []).append(p)

    lines = ["=== БИБЛИОТЕКА ТОВАРОВ (единственный источник названий) ==="]
    for cat, items in by_cat.items():
        lines.append(f"\n[{cat}]")
        for p in items:
            fl = flavor_of(p)
            lines.append(f"  • {p.get('title','')}" + (f"   ← ВКУС: {fl}" if fl else ""))

    # Семейства с несколькими вкусами — самая частая ошибка: назвать «чуйбы» без вкуса.
    fams: dict[str, set] = {}
    for p in all_products():
        fl = flavor_of(p)
        if not fl:
            continue
        key = _norm(p.get("title", "")).replace(_norm(fl), "")[:40]
        fams.setdefault(key, set()).add(fl)
    multi = {k: v for k, v in fams.items() if len(v) > 1}
    if multi:
        lines.append("\nУ ЭТИХ ПОЗИЦИЙ НЕСКОЛЬКО ВКУСОВ — вкус называть ОБЯЗАТЕЛЬНО:")
        for v in multi.values():
            lines.append("  • варианты: " + ", ".join(sorted(v)))
    return "\n".join(lines)


def product_rule(brand: str = "BelovedPets") -> str:
    """Железное правило про товары — вставляется во ВСЕ промпты, где пишется ТЗ."""
    return (
        "\n⛔ ЖЕЛЕЗНОЕ ПРАВИЛО ПО ТОВАРАМ (нарушение = ТЗ бракуется и переписывается):\n"
        "1. Товар берётся ТОЛЬКО из библиотеки выше. Товаров, которых там нет, не существует —\n"
        "   не выдумывай ни названий, ни линеек, ни форматов упаковки.\n"
        "2. В ТЗ обязательна строка **Товар:** с ПОЛНЫМ названием из библиотеки, СЛОВО В СЛОВО,\n"
        "   вместе со скобками и размером. Не сокращай, не переводи, не переставляй слова.\n"
        "3. ВКУС/вариант обязателен, если он есть у товара: «(Salmon (for Cats))», «(Beef)»,\n"
        "   «with Chicken Flavor». Формулировки вроде «чуйбы флиантик» — брак.\n"
        "4. Если у линейки несколько вкусов — выбери ОДИН и назови его явно. «Любой вкус» и\n"
        "   «на выбор» в ТЗ не пишем: креатор должен знать, какую пачку ставить в кадр.\n"
        "5. Не знаешь, какой товар подходит теме — возьми ближайший из библиотеки и скажи об\n"
        "   этом одной строкой. Придумать товар нельзя ни при каких условиях.\n"
    )


def validate_products(text: str, brand: str = "BelovedPets") -> list[str]:
    """Проверка готового ТЗ: товар назван, существует, вкус указан. Пустой список — всё ок."""
    problems: list[str] = []
    if (brand or "").strip().lower() != "belovedpets":
        return problems                      # каталога по бренду нет — проверять не с чем
    m = re.search(r"^\s*\*\*Товар(?: в кадре)?:\*\*\s*(.+)$", text or "", re.M)
    if not m:
        return ["в ТЗ нет строки «**Товар:**» с названием из библиотеки"]
    named = m.group(1).strip().strip("*").split("·")[0].strip()
    if named.lower().startswith(("вся линейка", "бренд", "нет", "—")):
        return problems                      # бренд-ТЗ без конкретного SKU — это законно
    p = find_exact(named) or find_mentioned(named)
    if not p:
        problems.append(f"товара «{named[:70]}» нет в библиотеке — название выдумано или искажено")
        return problems
    # Пробелы при сравнении не считаем: «60 ml» и «60ml» — одно и то же, ругаться на это
    # значит приучить команду игнорировать проверку.
    tight = lambda x: _norm(x).replace(" ", "")
    if tight(named) != tight(p.get("title", "")):
        problems.append(f"название не совпадает с библиотекой дословно — в базе: «{p['title'][:90]}»")
    fl = flavor_of(p)
    if fl and _norm(fl) not in _norm(named):
        problems.append(f"не указан вкус — у этого товара он есть: «{fl}»")
    return problems
