"""Банк идей — идеи команды без даты (решение Марии 2026-11-13).

Кидаете идею в любой момент, Джек при планировании месяца берёт из банка несколько
свободных, разворачивает их в посты и помечает, в какой месяц они ушли. Хранится в
общем хранилище (Supabase), поэтому видна всей команде.
"""

from __future__ import annotations

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


def add(brand: str, text: str, by: str = "") -> bool:
    text = (text or "").strip()
    if not text:
        return False
    items = load(brand)
    items.append({"id": uuid.uuid4().hex[:8], "text": text, "by": by,
                  "added": date.today().isoformat(), "used": ""})
    return _save(brand, items)


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
    lines = ["БАНК ИДЕЙ КОМАНДЫ (без даты, придумала команда — бери их в первую очередь, "
             "ставь id в поле `bank_id` поста, который из идеи вырос):"]
    for i in ideas[:30]:
        lines.append(f"  • [{i['id']}] {i['text'][:300]}")
    return "\n".join(lines)
