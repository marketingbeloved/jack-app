"""Залить знания о бренде (позиционирование, ЦА, тон, конкуренты) в общую базу Supabase.

Зачем: на Streamlit Cloud нет ~/BP-Work и brand_data/, поэтому Джек на сайте планировал
вслепую. models/brand_knowledge.py на сайте читает текст отсюда.

Запуск из папки code (нужен .streamlit/secrets.toml с SUPABASE_*):
    .venv/bin/python scripts/upload_brand_knowledge.py            # оба бренда
Повторный запуск перезаписывает текст свежей версией исходников.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import shared_store  # noqa: E402
from models.brand_knowledge import build, shared_key  # noqa: E402

for brand in ("BelovedPets", "Tobydic"):
    text = build(brand)
    if not text:
        print(f"{brand}: исходников нет — пропускаю.")
        continue
    ok = shared_store.put_json(shared_key(brand), {"text": text, "updated": date.today().isoformat()})
    back = (shared_store.get_json(shared_key(brand), {}) or {}).get("text", "")
    print(f"{brand}: собрано {len(text)} знаков, в базе {len(back)} · {'OK' if ok else 'ОШИБКА'}")
