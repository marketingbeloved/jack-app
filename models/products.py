"""База товаров BP и TOBYDIC — models/product_base.json (из Excel Маши, 2026-11-12).

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
if not PRODUCTS_JSON.exists():
    # На чужом маке Content Factory нет — копия каталога лежит в brand_data/ (gitignored)
    PRODUCTS_JSON = Path(__file__).resolve().parent.parent / "brand_data" / "products.json"


# Ключ каталога в общей базе. brand_data/ в git не уходит (репо публичный), поэтому на
# Streamlit Cloud файла нет — и Джек видел пустую «библиотеку» и выдумывал товары.
# Каталог заливается в Supabase скриптом scripts/upload_products.py.
SHARED_KEY = "products_belovedpets"


@lru_cache(maxsize=1)
def _load():
    if PRODUCTS_JSON.exists():
        return json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    try:
        from models import shared_store
        data = shared_store.get_json(SHARED_KEY, None)
        if isinstance(data, dict) and data.get("products"):
            return data
    except Exception:
        pass
    return {"products": [], "global_compliance": {}, "category_knowledge_base": {}}


# ─── База товаров: единственный источник (решение Марии 2026-11-12) ─────────
# «База товаров BP и TOBYDIC (Amazon)» → models/product_base.json. Одна запись = один
# ASIN на одном рынке (US/UK/CA). Название — колонка «Чёткое название (EN)», бенефиты —
# из базы без запрещённых формулировок, применение и состав — дословно из базы.
# Пересборка: scripts/build_product_base.py <xlsx>.
BASE_JSON = Path(__file__).resolve().parent / "product_base.json"
DEFAULT_MARKET = "US"


@lru_cache(maxsize=1)
def _base() -> tuple:
    try:
        rows = json.loads(BASE_JSON.read_text(encoding="utf-8"))
    except Exception:
        rows = []
    out = []
    for r in rows:
        out.append({**r, "id": f'{r["asin"]}-{r["market"]}', "flavor": "",
                    "description_short": " · ".join(r.get("benefits") or [])})
    return tuple(out)


def _is_tobydic(brand: str) -> bool:
    return (brand or "").strip().lower() == "tobydic"


def _brand_key(brand: str) -> str:
    return "TOBYDIC" if _is_tobydic(brand) else "BelovedPets"


def brand_products(brand: str = "BelovedPets", market: str | None = None) -> list[dict]:
    """Товары бренда на рынке (по умолчанию US). Чужой бренд сюда не попадает никогда.

    market="all" — все рынки (для проверки названий: имена на рынках совпадают).
    """
    b = _brand_key(brand)
    m = (market or DEFAULT_MARKET).upper()
    return [dict(p) for p in _base()
            if p["brand"] == b and (m == "ALL" or p["market"] == m)]


TOBYDIC_PRODUCTS = brand_products("TOBYDIC")


def beloved_products(market: str | None = None) -> list[dict]:
    return brand_products("BelovedPets", market)


def product_facts(name: str, brand: str = "BelovedPets", market: str | None = None) -> str:
    """Бенефиты, применение и состав товара из базы — для промпта ТЗ (правило 3)."""
    p = find_exact(name, brand, market) or find_mentioned(name, brand, market)
    if not p:
        return ""
    ben = "; ".join(p.get("benefits") or []) or "нет в базе — не придумывать, спросить Машу"
    use = p.get("how_to_use") or "нет в базе — не придумывать, спросить Машу"
    return (f"ФАКТЫ О ТОВАРЕ ИЗ БАЗЫ ({p['market']}) — бери только отсюда:\n"
            f"• Товар: {p['title']} · ASIN {p['asin']} · {p['url']}\n"
            f"• Бенефиты: {ben}\n• Как использовать: {use[:700]}\n"
            f"• Состав: {(p.get('ingredients') or 'нет в базе')[:700]}\n")


def product_url(name: str, brand: str = "BelovedPets", market: str | None = None) -> str:
    """Ссылка на Amazon для товара по его названию ('' — не нашли)."""
    p = find_exact(name, brand, market) or find_mentioned(name, brand, market)
    return (p or {}).get("url", "")


def other_brand_product(name: str, brand: str = "BelovedPets") -> dict | None:
    """Товар ДРУГОГО бренда с таким названием (None — чужим он не является).

    Правило Марии (2026-11-11): бренды не смешиваются — в контенте TOBYDIC только товары
    TOBYDIC, в Beloved Pets — только Beloved Pets.
    """
    other = "BelovedPets" if _is_tobydic(brand) else "TOBYDIC"
    if find_exact(name, brand, "all"):
        return None
    return find_exact(name, other, "all") or find_mentioned(name, other, "all")


def attach_link(text: str, brand: str = "BelovedPets", market: str | None = None) -> str:
    """Дописать ссылку Amazon в строку «**Товар:** …», если Джек её не поставил."""
    def fix(m: "re.Match") -> str:
        line = m.group(0)
        if "amazon." in line:
            return line
        named = m.group(2).strip().strip("*").split("·")[0].strip()
        link = product_url(named, brand, market)
        return f"{line.rstrip()} · {link}" if link else line
    return re.sub(r"^(\s*\*\*Товар(?: в кадре)?:\*\*)\s*(.+)$", fix, text or "", flags=re.M)


def all_products() -> list[dict]:
    """Все товары обоих брендов (US) — только из базы товаров."""
    return beloved_products() + brand_products("TOBYDIC")


def categories(brand: str = "BelovedPets", market: str | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in brand_products(brand, market):
        out[p.get("category", "?")] = out.get(p.get("category", "?"), 0) + 1
    return out


def global_compliance() -> dict:
    return _load().get("global_compliance", {})


def category_kb() -> dict:
    return _load().get("category_knowledge_base", {})


def get_product(product_id: str) -> dict | None:
    for p in all_products():
        if p.get("id") == product_id:
            return p
    return None


def list_products(category: str | None = None, search: str | None = None,
                  brand: str | None = None, market: str | None = None) -> list[dict]:
    items = brand_products(brand, market) if brand else all_products()
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
    "топпер": "shreds", "topper": "shreds", "шредс": "shreds", "shreds": "shreds",
    "gravy": "shreds", "соус": "shreds", "влажн": "shreds",
}


def resolve_products(text: str, limit: int = 4, brand: str = "BelovedPets") -> list[dict]:
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
        for p in list_products(search=term, brand=brand):
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
    if isinstance(p, dict) and p.get("flavor"):
        return p["flavor"]                   # чистый каталог знает вкус точно
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


def find_exact(title: str, brand: str = "BelovedPets", market: str | None = "all") -> dict | None:
    """Товар по полному названию из базы (регистр и пунктуация не важны). None — нет.

    По умолчанию ищем по всем рынкам бренда (названия на рынках одинаковые); если
    передан рынок — сначала он, чтобы ссылка/ASIN были того рынка.
    """
    n = _norm(title)
    if not n:
        return None
    pools = [brand_products(brand, market)] if market and market.lower() == "all" else \
        [brand_products(brand, market), brand_products(brand, "all")]
    for pool in pools:
        for p in pool:
            if _norm(p.get("title", "")) == n:
                return p
    return None


def candidates(title: str, brand: str = "BelovedPets", market: str | None = None) -> list[dict]:
    """Товары, чьё название начинается с указанного: «… Chicken Jerky Strips for Dogs»
    → варианты 300 g и 680 g. Для подсказки «какой именно?» (правило 2)."""
    n = _norm(title)
    if len(n) < 8:
        return []
    out, seen = [], set()
    for p in brand_products(brand, market):
        if _norm(p["title"]).startswith(n) and p["title"] not in seen:
            seen.add(p["title"])
            out.append(p)
    return out


def find_mentioned(title: str, brand: str = "BelovedPets", market: str | None = None) -> dict | None:
    """Неполное название → товар, только если вариант ОДИН (иначе угадывать нельзя)."""
    c = candidates(title, brand, market)
    return c[0] if len(c) == 1 else None


def catalog_block(brand: str = "BelovedPets", limit: int = 200, market: str | None = None) -> str:
    """Библиотека для промпта: точные названия из базы + ASIN, ссылка и короткие бенефиты."""
    m = (market or DEFAULT_MARKET).upper()
    items = brand_products(brand, m)[:limit]
    if not items:
        return (f"\nВ БАЗЕ ТОВАРОВ НЕТ ТОВАРОВ {brand} ДЛЯ РЫНКА {m}. Конкретные товары НЕ "
                "называй и не подставляй другой рынок: в строке **Товар:** пиши «нет в базе "
                f"для {m} — спросить Машу».\n")
    head = "TOBYDIC" if _is_tobydic(brand) else "BELOVED PETS"
    lines = [f"=== БАЗА ТОВАРОВ {head} · рынок {m} (единственный источник, {len(items)} позиций) ===",
             "Название — СЛОВО В СЛОВО, с вкусом и размером. Бенефиты — только указанные здесь; "
             "у кого бенефитов нет — не придумывай. Бейдж «Lab tested in the USA» — только [treats]."]
    if _is_tobydic(brand):
        lines.append("Все — herbal liquid drops для собак и кошек. Фокус ~70% контента: Urinary, "
                     "21-in-1 Multivitamin, Yeast & Itch.")
    else:
        lines.append("Cat Food Topper (Shreds in Gravy) подаётся ПОВЕРХ полноценного корма, не вместо.")
    by_cat: dict[str, list[dict]] = {}
    for p in items:
        by_cat.setdefault(str(p.get("category") or "?"), []).append(p)
    for cat, group in by_cat.items():
        lines.append(f"\n[{cat}]")
        for p in group:
            ben = " · ".join(p.get("benefits") or [])[:110]
            lines.append(f"  • {p['title']} · ASIN {p['asin']} · {p['url']}"
                         + (f"\n      бенефиты: {ben}" if ben else ""))
    other = "Beloved Pets" if _is_tobydic(brand) else "TOBYDIC"
    lines.append(f"\nСТРОГО ЗАПРЕЩЕНО называть товары {other} и любых других брендов, товары "
                 "других рынков, а также товары, вкусы и размеры, которых нет в этом списке.")
    return "\n".join(lines)


def product_rule(brand: str = "BelovedPets") -> str:
    """Правила Маши по товарам (база товаров, 2026-11-12) — во ВСЕ промпты, где пишется ТЗ."""
    return (
        "\n⛔ ПРАВИЛА ПО ТОВАРАМ (нарушение = ТЗ бракуется):\n"
        "1. ТОЛЬКО БАЗА. Единственный источник о товарах — база выше. Название, бенефиты,\n"
        "   применение и состав — только оттуда. Не бери из Shopify, Amazon, соцсетей, старых\n"
        "   постов и ТЗ, из памяти. Товара нет в базе — его нет: не пиши о нём, спроси Машу.\n"
        "2. НАЗВАНИЕ СЛОВО В СЛОВО. Строка «**Товар:** <название из базы целиком, с вкусом и\n"
        "   размером> · ASIN <ASIN> · <ссылка>». Не сокращай, не переводи, не смешивай два товара.\n"
        "   Если в запросе название неточное («джерки» без вкуса и веса) — не угадывай:\n"
        "   перечисли 2–3 подходящих из базы и спроси, какой.\n"
        "3. ФАКТЫ ТОЛЬКО ИЗ БАЗЫ. Не добавляй бенефитов, вкусов, размеров и цифр, которых там\n"
        "   нет. Запрещено: Made in USA, vet-developed, vet approved, treatment, cure, medicine,\n"
        "   antibiotic, infection, Revolution. Слово «Natural Antibiotic» допустимо ТОЛЬКО в\n"
        "   строке «Товар:» как часть названия — в хуках, текстах на экране и подписях нет.\n"
        "   Lab tested in USA — только у лакомств. Мы добавка, не лекарство («supports»).\n"
        "4. БРЕНДЫ И РЫНКИ НЕ СМЕШИВАТЬ. Beloved Pets — только его товары, TOBYDIC — только\n"
        "   свои. Для US — строки US, UK — UK, CA — CA. Нет товара на рынке — скажи об этом.\n"
    )


def validate_products(text: str, brand: str = "BelovedPets", market: str | None = None) -> list[str]:
    """Проверка ТЗ: товар из базы, название дословно, нужного бренда. [] — всё ок."""
    problems: list[str] = []
    if not brand_products(brand, "all"):
        return problems                      # база не загрузилась — проверять не с чем
    m = re.search(r"^\s*\*\*Товар(?: в кадре)?:\*\*\s*(.+)$", text or "", re.M)
    if not m:
        return ["в ТЗ нет строки «**Товар:**» с названием из базы"]
    named = m.group(1).strip().strip("*").split("·")[0].strip()
    # Короткое название + ссылка (формат ТЗ с 2026-11-13): товар узнаём по ASIN в ссылке.
    ma = re.search(r"/dp/([A-Z0-9]{10})", m.group(1))
    if ma:
        hit = by_asin(ma.group(1))
        if hit and _brand_key(hit["brand"]) == _brand_key(brand):
            return problems
        if hit:
            return [f"«{hit['title'][:70]}» — товар другого бренда; бренды не смешиваем, "
                    f"бери только из базы {brand}"]
    if named.lower().startswith(("вся линейка", "бренд", "нет", "—", "уточнить")):
        return problems                      # бренд-ТЗ без конкретного SKU — это законно
    if find_exact(named, brand, market):
        return problems
    if other_brand_product(named, brand):
        return [f"«{named[:70]}» — товар другого бренда; бренды не смешиваем, "
                f"бери только из базы {brand}"]
    c = candidates(named, brand, market or "all")
    if c:
        return ["название неполное — в базе: " + " / ".join(f"«{p['title']}»" for p in c[:3])]
    return [f"товара «{named[:70]}» нет в базе — название выдумано или искажено"]


# ─── Короткое название в ТЗ (решение Марии 2026-11-13) ────────────────────────
# Исполнителям — «название кратко + ссылка». Полное название остаётся в базе и в плане,
# в ТЗ строку «Товар:» код переписывает сам, чтобы модель не сокращала по-своему.

def by_asin(asin: str) -> dict | None:
    asin = (asin or "").strip().upper()
    return next((p for p in _base() if p.get("asin", "").upper() == asin), None)


_SIZE_RE = re.compile(r"\d[\d.,]*\s*(g|kg|ml|oz|lb|tubes?|pack|doses?|refills?|diffusers?)\b"
                      r"|\d+\s*×", re.I)


_FOR_RE = re.compile(r"\s+for\s+((?:Dogs?|Cats?|Ferrets)(?:(?:\s*,\s*|\s*&\s*|\s+and\s+)"
                     r"(?:Dogs?|Cats?|Ferrets))*)(\s*\((?!\d)[^)]*\))?", re.I)


def _short(title: str, keep_animal: bool) -> str:
    t = re.sub(r"^(Beloved Pets|TOBYDIC)\s+", "", (title or "").strip(), flags=re.I)
    t = re.sub(r"\s+—\s+(Dog|Cat) Treats\b", "", t)
    t = re.sub(r"\s+—\s+", ", ", t)
    t = re.sub(r"\s*\((\d[^)]*)\)", "", t)                 # «300 g (10.6 oz)» → «300 g»
    t = _FOR_RE.sub(lambda m: f" for {m.group(1)}" if keep_animal else "", t)
    return re.sub(r"\s{2,}", " ", t).strip(" ,")


def short_name(title: str) -> str:
    """«Beloved Pets Sweet Potato Wrapped with Chicken — Dog Treats, 300 g (10.6 oz)»
    → «Sweet Potato Wrapped with Chicken, 300 g». Бренд и «for Dogs & Cats» убираем,
    вкус и размер оставляем. «for Cats / for Dogs» остаётся, только если без него
    один и тот же товар бренда есть для разных животных (ошейник для кошек и для собак)."""
    short = _short(title, False)
    brand = "TOBYDIC" if (title or "").upper().startswith("TOBYDIC") else "BelovedPets"
    stem = short.split(",")[0]
    animals = {(_FOR_RE.search(p["title"]) or [None, ""])[1] for p in _base()
               if _brand_key(p["brand"]) == _brand_key(brand)
               and _short(p["title"], False).split(",")[0] == stem}
    return _short(title, True) if len(animals) > 1 else short


def shorten_product_line(text: str, brand: str = "BelovedPets", market: str | None = None) -> str:
    """Строку «**Товар:** <полное> · ASIN · ссылка» → «**Товар:** <кратко> · ссылка»."""
    def fix(m: "re.Match") -> str:
        body = m.group(2)
        ma = re.search(r"/dp/([A-Z0-9]{10})", body)
        p = by_asin(ma.group(1)) if ma else None
        if not p:
            named = body.strip().strip("*").split("·")[0].strip()
            p = find_exact(named, brand, market or "all")
        if not p:
            return m.group(0)
        url = re.search(r"https?://\S+", body)
        link = url.group(0) if url else p.get("url", "")
        return f"{m.group(1)} {short_name(p['title'])}" + (f" · {link}" if link else "")
    return re.sub(r"^(\s*\*\*Товар(?: в кадре)?:\*\*)\s*(.+)$", fix, text or "", flags=re.M)
