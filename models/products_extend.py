"""Extend products library with new SKUs Darya/Tanya add via chat.

When Jack engine receives a task with a product not in products.json,
it asks for: name, category, ingredients, benefits, usage, listing URL,
then this module appends a new entry to the local catalogue.

We do NOT write into Content Factory's products.json (read-only source of truth).
Instead, we keep added items in jack-app/cache/products_extra.json, and the
products.all_products() function merges both sources.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

EXTRA_FILE = Path(__file__).resolve().parent.parent / "cache" / "products_extra.json"
EXTRA_FILE.parent.mkdir(exist_ok=True)


def load_extra() -> list[dict]:
    if not EXTRA_FILE.exists():
        return []
    try:
        return json.loads(EXTRA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def add_product(
    title: str,
    category: str,
    ingredients: str = "",
    benefits: str = "",
    usage: str = "",
    listing_url: str = "",
    drive_url: str = "",
    safe_claims: list[str] | None = None,
    forbidden: list[str] | None = None,
) -> dict:
    """Add a new SKU to the extra library and return the saved record."""
    record = {
        "id": f"extra-{int(time.time())}-{title.lower().replace(' ', '-')[:30]}",
        "title": title,
        "category": category,
        "description_short": benefits or "—",
        "ingredients": ingredients,
        "usage": usage,
        "url": listing_url,
        "drive": drive_url,
        "compliance": {
            "category_rules": {
                "forbidden_phrases": forbidden or ["cures", "treats", "heal", "FDA approved", "100% effective"],
                "safe_claims": safe_claims or ["supports", "may help with", "natural ingredients", "gentle daily care"],
                "made_in_usa": category == "treats",
                "lab_tested_usa": category == "treats",
                "medical_claims_allowed": False,
            },
        },
        "source": "darya-chat",
        "added_at": time.time(),
    }
    items = load_extra()
    items.append(record)
    EXTRA_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def search_extra(query: str) -> list[dict]:
    q = query.lower()
    return [p for p in load_extra() if q in p.get("title", "").lower() or q in p.get("ingredients", "").lower()]
