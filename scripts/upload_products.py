"""Залить каталог BelovedPets (brand_data/products.json) в общую базу Supabase.

Зачем: brand_data/ в git не уходит (репо публичный), и на Streamlit Cloud Джек видел
пустую библиотеку товаров — отсюда выдуманные SKU. models/products.py читает каталог
из общей базы, если локального файла нет.

Запуск из папки jack-app (нужен .streamlit/secrets.toml с SUPABASE_*):
    .venv/bin/python scripts/upload_products.py
Повторный запуск просто перезаписывает каталог свежей версией.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import shared_store  # noqa: E402
from models.products import SHARED_KEY  # noqa: E402

src = ROOT / "brand_data" / "products.json"
data = json.loads(src.read_text(encoding="utf-8"))
n = len(data.get("products", []))
if not n:
    sys.exit(f"В {src} нет товаров — заливать нечего.")

if not shared_store.put_json(SHARED_KEY, data):
    sys.exit("Не получилось записать в Supabase — проверь SUPABASE_URL / SUPABASE_KEY.")

back = shared_store.get_json(SHARED_KEY, {}) or {}
print(f"Залито товаров: {n}. В базе под ключом __{SHARED_KEY}__: {len(back.get('products', []))}.")
