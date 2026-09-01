"""Пост из контент-плана → ТЗ в Notion для Дины.

Автопуш в Notion в Джеке уже был, но умел только «концепты» из Jack Workspace. Посты
плана устроены иначе: у них markdown-ТЗ в ячейке, а не поля концепта. Этот адаптер
разбирает ТЗ обратно на части и отдаёт в тот же publish_to_notion.

Отправка — ТОЛЬКО по кнопке. Дарья смотрит план, правит, и лишь потом решает, что уходит
Дине. Ничего не уезжает в Notion само.
"""

from __future__ import annotations

import re
from datetime import date

# «0-3 сек — …», «**0-3 сек** …», «- 3-7 сек: …» — Джек пишет тайминг по-разному.
_SCENE_RE = re.compile(r"^\s*(?:[-*•]\s*)?(?:\*\*)?\s*(\d+\s*[-–—]\s*\d+\s*(?:сек|s|sec)\b.*)$",
                       re.IGNORECASE | re.MULTILINE)
_SLIDE_RE = re.compile(r"^\s*(?:[-*•]\s*)?(?:\*\*)?\s*(Слайд\s*\d+.*)$",
                       re.IGNORECASE | re.MULTILINE)


def _field(text: str, *labels: str) -> str:
    """Достать значение из строки вида «**Метка:** значение»."""
    for label in labels:
        m = re.search(rf"\*\*{re.escape(label)}[^:*]*:?\*\*[:\s]*(.+)", text, re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip(" *·—-")
    return ""


def _caption(text: str) -> str:
    """Подпись под пост — блок после «**Подпись под пост (EN):**» до следующего заголовка."""
    m = re.search(r"\*\*Подпись под пост[^*]*\*\*[:\s]*\n?(.+?)(?=\n\*\*|\Z)", text,
                  re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _scenes(text: str) -> list[str]:
    scenes = [s.strip(" *") for s in _SCENE_RE.findall(text)]
    if not scenes:
        scenes = [s.strip(" *") for s in _SLIDE_RE.findall(text)]
    return scenes


# «0-3 сек — что в кадре · на экране "English"» — ровно так Джек пишет сцены сейчас.
_TIME_RE = re.compile(r"^\s*(\d+\s*[-–—]\s*\d+\s*(?:сек|s|sec)\b\.?)\s*[—–\-:]?\s*(.*)$", re.I)
_TOS_RE = re.compile(r"(?:·\s*)?(?:на экране|overlay|on-?screen|текст на экране)\s*:?\s*(.+)$", re.I)
_VO_RE = re.compile(r"(?:·\s*)?(?:voiceover|озвучка|голос за кадром)\s*:?\s*(.+)$", re.I)


def scene_rows(text: str) -> list[dict]:
    """Разобрать сцены в 4 колонки Дининой таблицы БЕЗ помощи модели.

    Раньше строка сцены целиком уходила в LLM на пересборку, и та возвращала ярлыки
    («Крючок», «Трансформация») вместо содержания — в Notion приезжала пустая таблица.
    Разметка в ТЗ уже есть, её достаточно разобрать регуляркой.
    """
    rows: list[dict] = []
    for line in text.split("\n"):
        line = line.strip().lstrip("-*• ").strip()
        m = _TIME_RE.match(re.sub(r"\*\*", "", line))
        if not m:
            continue
        time_s, rest = m.group(1).strip(), m.group(2).strip()

        vo = ""
        mv = _VO_RE.search(rest)
        if mv:
            vo = mv.group(1).strip(' *"«»·')
            rest = rest[:mv.start()].strip(" ·")

        tos = ""
        mt = _TOS_RE.search(rest)
        if mt:
            tos = mt.group(1).strip(' *"«»·')
            rest = rest[:mt.start()].strip(" ·")

        rows.append({"time": time_s, "video": rest.strip(" ·—-"),
                     "tos": tos, "voiceover": vo})
    return rows


def _is_static(post: dict, text: str) -> bool:
    fmt = (post.get("format") or "").lower()
    title = (post.get("title") or "").lower()
    blob = f"{fmt} {title} {text[:200]}".lower()
    if "carousel" in blob or "карусел" in blob:
        return True
    if "слайд" in text.lower() and not _SCENE_RE.search(text):
        return True
    return False


def build_concept(post: dict, brief_text: str, brand: str = "BelovedPets",
                  market: str = "US") -> dict:
    """Собрать из поста плана словарь в том виде, который ждёт publish_to_notion."""
    text = brief_text or ""
    return {
        "title": (post.get("title") or "").strip() or "(без темы)",
        "product": _field(text, "Товар в кадре", "Товар", "Packshot"),
        "market": market,
        "brand": brand,
        "hook": _field(text, "Хук", "Overlay сверху", "Hook"),
        "angle": _field(text, "Концепт", "Формат"),
        "cta": _caption(text),
        "format": "carousel" if _is_static(post, text) else "reel",
        "scenes": _scenes(text),
        # Готовая таблица — publish_to_notion возьмёт её вместо пересборки моделью.
        "scene_rows": scene_rows(text),
    }


def push_post(post: dict, brief: dict, *, brand: str = "BelovedPets", market: str = "US",
              date_key: str = "", force: bool = False) -> dict:
    """Отправить один пост в Notion.

    Возвращает {"url":…}, {"skipped":…, "url":…} если уже отправляли, или {"error":…}.
    Защита от повтора обязательна: у «концептов» она была, у постов плана её не было, и
    Дина получала по два одинаковых ТЗ на один пост — каждое нажатие кнопки создавало
    новую страницу.
    """
    text = (brief or {}).get("text", "") or ""
    if not text.strip():
        return {"error": "У поста нет ТЗ — сначала напиши его, потом отправляй Дине."}

    already = (brief or {}).get("notion_url", "")
    if already and not force:
        return {"skipped": "Это ТЗ уже в Notion — второй раз не отправляю.", "url": already}

    concept = build_concept(post, text, brand=brand, market=market)
    if not concept["scenes"]:
        return {"error": "В ТЗ не нашлись ни сцены с таймингом, ни слайды — "
                         "Notion-таблицу собрать не из чего. Проверь текст ТЗ."}

    end_date = _end_date(date_key)
    if not end_date:
        return {"error": f"Не смог понять дату поста «{date_key}» — без неё в Notion "
                         f"страница уедет без срока. Проверь дату в плане."}

    from models.jack_engine import publish_to_notion
    res = publish_to_notion(concept, drive_url=(brief or {}).get("link", ""),
                            listing_url="", end_date=end_date)
    if res.get("url"):
        from models import plan_briefs
        b = brief or {}
        plan_briefs.save(post["id"], text, title=b.get("title", ""), pillar=b.get("pillar", ""),
                         for_who=b.get("for", "dina"), updated=b.get("updated", ""),
                         link=b.get("link", ""), wish=b.get("wish", ""),
                         notion_url=res["url"])
    return res


def _end_date(date_key: str) -> str | None:
    """'12.09' → ISO-дата. Год берём текущий; если дата уже прошла — значит следующий."""
    if not re.fullmatch(r"\d{2}\.\d{2}", date_key or ""):
        return None
    dd, mm = int(date_key[:2]), int(date_key[3:])
    today = date.today()
    try:
        d = date(today.year, mm, dd)
    except ValueError:
        return None
    if (d - today).days < -180:
        d = date(today.year + 1, mm, dd)
    return d.isoformat()
