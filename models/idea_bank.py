"""Банк идей — идеи команды без даты (решение Марии 2026-11-13).

Кидаете идею в любой момент, Джек при планировании месяца берёт из банка несколько
свободных, разворачивает их в посты и помечает, в какой месяц они ушли. Хранится в
общем хранилище (Supabase), поэтому видна всей команде.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from models import shared_store


def _key(brand: str) -> str:
    return f"idea_bank_{(brand or 'BelovedPets').lower()}"


def load(brand: str) -> list[dict]:
    items = shared_store.get_json(_key(brand), []) or []
    return [i for i in items if isinstance(i, dict) and i.get("text")]


def _save(brand: str, items: list[dict]) -> bool:
    return shared_store.put_json(_key(brand), items)


_URL_RE = re.compile(r"https?://\S+", re.I)


def add(brand: str, text: str, by: str = "", analyse: bool = True) -> dict | None:
    """Добавить идею (текст и/или ссылку). Сразу же Джек её разбирает. None — не сохранилось."""
    text = (text or "").strip()
    if not text:
        return None
    m = _URL_RE.search(text)
    item = {"id": uuid.uuid4().hex[:8], "text": text, "url": m.group(0).rstrip(".,)") if m else "",
            "by": by, "added": date.today().isoformat(), "used": "", "analysis": "", "seen": ""}
    if analyse:
        item["analysis"], item["seen"] = analyse_idea(item, brand)
    items = load(brand)
    items.append(item)
    return item if _save(brand, items) else None


def reanalyse(brand: str, idea_id: str) -> bool:
    items = load(brand)
    for i in items:
        if i.get("id") == idea_id:
            i["analysis"], i["seen"] = analyse_idea(i, brand)
    return _save(brand, items)


# ─── Разбор идеи Джеком (решение Марии 2026-11-13) ──────────────────────────
# Ссылка на рилс → Джек скачивает и смотрит ролик (Gemini, бесплатно), объясняет, почему
# он залетел, и предлагает 2 адаптации под наш бренд. Текстовая идея → 2 адаптации.

_SEEN_NOTE = {
    "video": "",
    "frames": "ℹ️ Видео целиком не взялось — разбор по кадрам (звук не учтён).\n\n",
    "none": "ℹ️ Ролик посмотреть не удалось — разбор по ссылке и вашему описанию.\n\n",
    "text": "",
}


def _prompt(item: dict, brand: str, seen: str) -> str:
    from models.products import catalog_block
    try:
        from models.jack_engine import _brand_context
        ctx = _brand_context(brand)[:1500]
    except Exception:
        ctx = ""
    is_link = bool(item.get("url"))
    note = (item.get("text") or "").replace(item.get("url") or "", "").strip()
    look = {
        "video": "Перед тобой САМ ролик целиком (движение, звук, текст на экране). Посмотри его как креативщик.",
        "frames": "Перед тобой кадры ролика по порядку. Про звук и ритм честно скажи, что судишь по кадрам.",
        "none": "Ролик посмотреть НЕ удалось. Работай по ссылке и комментарию команды, не выдумывай, что в нём.",
        "text": "Это текстовая идея команды.",
    }[seen]
    why_block = ("**🔥 Почему зашёл:** 3-4 пункта — хук первых 2 секунд, структура, эмоция или "
                 "механика (участие, юмор, узнавание, польза), почему досматривают и сохраняют."
                 if is_link else
                 "**🔥 Почему может зайти:** 2-3 пункта — на какую эмоцию или боль аудитории давит.")
    what = "**🔗 Что это:** 1 строка — чей ролик и о чём.\n" if is_link else ""
    return f"""\
Ты Джек — senior SMM-креативщик бренда {brand} (добавки и лакомства для собак и кошек).
Команда закинула в банк идей {'ссылку на понравившийся ролик' if is_link else 'идею'}.
{look}

{('Ссылка: ' + item['url']) if is_link else ''}
Комментарий команды: {note or '(нет)'}

Ответ — чистый markdown, без вступлений, строго в таком виде:

{what}{why_block}

**🐾 Как адаптировать нам:** ровно 2 варианта, каждый так:
1. **<название поста строчными>** · формат: рилс / анимация фото / карусель / статика ·
   товар: <название из базы ниже, кратко> · хук: "English" · идея: 1-2 фразы по-русски
2. ...

**⛔ Что не переносим:** 1 строка (чужой бренд, сложный продакшен, рискованные заявления) — или «—».

ПРАВИЛА:
- Берём МЕХАНИКУ и приём, а не копию. Чужой бренд и чужой текст дословно — нельзя.
- Рилс Дина генерирует ИИ: максимум 3 простые сцены, одно животное, одна локация.
- Товары — ТОЛЬКО из базы ниже, бренды не смешивать.
- Мы supplement, NOT medicine: нельзя cure / treat / heal / prevent / medicine / FDA /
  guaranteed / Made in USA / любые vet-заявления. Можно supports, may help, natural.

Контекст бренда: {ctx}

{catalog_block(brand)}
"""


def analyse_idea(item: dict, brand: str) -> tuple[str, str]:
    """(разбор markdown, что Джек видел: video / frames / none / text). Никогда не падает."""
    try:
        from models.llm import gemini_video, gemini_vision, smart_text
        from models.jack_engine import _video_frames, _video_mime
        url = item.get("url") or ""
        if not url:
            out = smart_text(_prompt(item, brand, "text"))
            return (out, "text")
        from models.reference_dl import fetch_video
        data, suffix, _meta = fetch_video(url)
        if data:
            out = gemini_video(_prompt(item, brand, "video"), data, _video_mime(suffix))
            if not out.startswith("⚠️"):
                return (out, "video")
            frames = _video_frames(data, suffix)
            if frames:
                out = gemini_vision(_prompt(item, brand, "frames"), frames, ["image/jpeg"] * len(frames))
                if not out.startswith("⚠️"):
                    return (_SEEN_NOTE["frames"] + out, "frames")
        out = smart_text(_prompt(item, brand, "none"))
        return ((out if out.startswith("⚠️") else _SEEN_NOTE["none"] + out), "none")
    except Exception as e:  # noqa: BLE001
        return (f"⚠️ Разобрать не получилось: {e}", "")


def remove(brand: str, idea_id: str) -> bool:
    return _save(brand, [i for i in load(brand) if i.get("id") != idea_id])


def unused(brand: str) -> list[dict]:
    return [i for i in load(brand) if not i.get("used")]


def mark_used(brand: str, ids: list[str], month_label: str) -> None:
    ids = {i for i in ids if i}
    if not ids:
        return
    items = load(brand)
    for i in items:
        if i.get("id") in ids:
            i["used"] = month_label
    _save(brand, items)


def prompt_block(ideas: list[dict]) -> str:
    """Свободные идеи из банка — текстом для промпта."""
    if not ideas:
        return "БАНК ИДЕЙ КОМАНДЫ: пусто."
    lines = ["БАНК ИДЕЙ КОМАНДЫ (без даты: текстовые идеи и ссылки на чужие ролики, которые "
             "понравились команде, с разбором Джека — почему зашло и как адаптировать нам). "
             "Бери их в первую очередь, опирайся на разбор, ставь id в `bank_id` поста:"]
    for i in ideas[:30]:
        lines.append(f"  • [{i['id']}] {i['text'][:300]}")
        an = (i.get("analysis") or "").strip()
        if an and not an.startswith("⚠️"):
            lines.append("    Разбор Джека: " + re.sub(r"\s+", " ", an)[:900])
    return "\n".join(lines)
