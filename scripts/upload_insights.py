"""Залить знания о ЦА (brand_data/audience_insights_<brand>.md) в общую базу Supabase.

Зачем: brand_data/ в git не уходит (репо публичный), и на Streamlit Cloud Джек не видел бы
ресёрч. models/audience_insights.py читает текст из общей базы, если локального файла нет.

Запуск из папки jack-app (нужен .streamlit/secrets.toml с SUPABASE_*):
    .venv/bin/python scripts/upload_insights.py              # BelovedPets
    .venv/bin/python scripts/upload_insights.py tobydic
Повторный запуск просто перезаписывает текст свежей версией.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import shared_store  # noqa: E402
from models.audience_insights import local_file, shared_key  # noqa: E402

brand = sys.argv[1] if len(sys.argv) > 1 else "belovedpets"
src = local_file(brand)
if not src.exists():
    sys.exit(f"Нет файла {src} — заливать нечего.")
text = src.read_text(encoding="utf-8").strip()

if not shared_store.put_json(shared_key(brand), {"text": text, "updated": date.today().isoformat()}):
    sys.exit("Не получилось записать в Supabase — проверь SUPABASE_URL / SUPABASE_KEY.")

back = shared_store.get_json(shared_key(brand), {}) or {}
print(f"Залито знаний: {len(text)} знаков. В базе под ключом __{shared_key(brand)}__: "
      f"{len(back.get('text', ''))} знаков.")
