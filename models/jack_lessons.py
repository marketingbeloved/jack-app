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
