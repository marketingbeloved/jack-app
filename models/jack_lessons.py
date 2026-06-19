"""Jack lessons — Darya's running corrections that become Jack's institutional memory.

Every time Darya edits, rejects or comments on a concept, we save a "lesson":
"в таком-то случае она просила переделать так". On next runs Jack reads these
lessons and avoids repeating the mistake.

File: ~/Databases/jack-app/cache/jack_lessons.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

LESSONS_FILE = Path(__file__).resolve().parent.parent / "cache" / "jack_lessons.json"
LESSONS_FILE.parent.mkdir(exist_ok=True)


def load_lessons() -> list[dict]:
    if not LESSONS_FILE.exists():
        return []
    try:
        return json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def add_lesson(brand: str, kind: str, note: str, concept_title: str = "") -> None:
    """Save a correction Darya made.

    Args:
        brand: BelovedPets | Tobydic
        kind: edit | reject | praise | tone_fix | format_fix | hook_fix | other
        note: Darya's actual comment / what she said wrong
        concept_title: optional reference to the concept that triggered the lesson
    """
    if not note.strip():
        return
    items = load_lessons()
    items.append({
        "ts": time.time(),
        "brand": brand,
        "kind": kind,
        "note": note.strip()[:500],
        "concept": concept_title[:120],
    })
    # Keep last 200 lessons max
    items = items[-200:]
    LESSONS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def render_for_prompt(brand: str, max_count: int = 15) -> str:
    """Format recent lessons for the LLM system prompt."""
    items = [x for x in load_lessons() if x.get("brand", "").upper() == brand.upper()]
    items = items[-max_count:]
    if not items:
        return ""
    out = "\n\n=== DARYA'S RUNNING CORRECTIONS (what she's taught Jack to do/avoid) ===\n"
    for it in items:
        out += f"- [{it.get('kind','note')}] {it.get('note')}"
        if it.get("concept"):
            out += f"  (context: «{it['concept']}»)"
        out += "\n"
    return out


# ─── Standing instructions Джеку — правила, которые Дарья/Таня пишут словами ──
# В отличие от lessons (авто-правки на концептах), это ПОСТОЯННЫЕ инструкции,
# которые вводят прямо в UI и которые применяются ко ВСЕМ ответам Джека.
# Живут в общей базе (Supabase) → синк у всех + переживают ребут облака.
RULES_FILE = LESSONS_FILE.parent / "jack_rules.json"


def _rules_local() -> list[dict]:
    if not RULES_FILE.exists():
        return []
    try:
        return json.loads(RULES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def load_rules() -> list[dict]:
    """Источник правды = общая база (если настроена), иначе локальный файл."""
    try:
        from models import shared_store
        if shared_store.configured():
            cloud = shared_store.get_json("jack_rules", None)
            if cloud is None:
                local = _rules_local()
                if local:
                    shared_store.put_json("jack_rules", local)
                return local
            return cloud
    except Exception:
        pass
    return _rules_local()


def _rules_write(items: list[dict]) -> None:
    try:
        from models import shared_store
        if shared_store.configured():
            shared_store.put_json("jack_rules", items)
    except Exception:
        pass
    try:
        RULES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def add_rule(brand: str, text: str, author: str = "") -> None:
    """Добавить постоянную инструкцию Джеку (видят все, применяется всегда)."""
    text = (text or "").strip()
    if not text:
        return
    items = load_rules()
    items.append({"ts": time.time(), "brand": brand, "text": text[:600], "author": author[:40]})
    _rules_write(items[-100:])


def delete_rule(ts: float) -> None:
    _rules_write([r for r in load_rules() if r.get("ts") != ts])


def list_rules(brand: str) -> list[dict]:
    """Правила для бренда + общие (brand пустой/ALL) — свежие сверху."""
    items = [r for r in load_rules()
             if not r.get("brand") or r.get("brand", "").upper() in (brand.upper(), "ALL")]
    return sorted(items, key=lambda r: r.get("ts", 0), reverse=True)


def render_rules_for_prompt(brand: str) -> str:
    """Инструкции Джеку для system-промпта (применяются ко всем ответам)."""
    items = list_rules(brand)
    if not items:
        return ""
    out = ("\n\n=== ИНСТРУКЦИИ ДЖЕКУ (постоянные правила от Дарьи и Тани — "
           "ОБЯЗАТЕЛЬНО соблюдай в каждом ответе) ===\n")
    for it in items:
        who = f" — {it['author']}" if it.get("author") else ""
        out += f"- {it.get('text','')}{who}\n"
    return out
