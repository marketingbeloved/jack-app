#!/usr/bin/env python3
"""jack_notion.py — модуль для Джека (SMM-помощник Beloved Pets).
Создаёт страницы ТЗ в Динином Notion (база Videos) в её живом формате.

Формат ТЗ (см. memory/bp-notion-format.md):
- Рилс/видео: About project → Сценарный план (таблица 4 кол. × N сцен) → Action items → Documents
- Статичный пост: About project (текст + референс) → Action items → Documents

Использование:
  from jack_notion import create_reel_brief, create_static_brief, list_recent, delete_page

  # Рилс
  url = create_reel_brief(
      title="uk eye wash persian reel",
      end_date="2026-06-15",
      about="Референс: <tiktok url>. Сделать в стиле POV. Voiceover UK English.",
      scenes=[
          {"time": "0:00-0:06", "video": "...", "tos": "...", "voiceover": "..."},
          ...
      ],
      action_items=["Найти tiktok-референс", "Снять b-roll глаз кота"],
  )

  # Статичный пост
  url = create_static_brief(
      title="life pic uk yeast liquid",
      end_date="2026-06-10",
      about="Кот на подоконнике, UK setting. Бутылка Yeast Support на переднем плане.",
  )

  # Список последних
  for b in list_recent(5):
      print(b)

  # Удалить (для тестов)
  delete_page("36d2452d-f1db-...")

CLI:
  python3 jack_notion.py test         # создаёт тестовую страницу
  python3 jack_notion.py list         # 10 последних страниц
  python3 jack_notion.py delete <id>  # удалить страницу
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOKEN_PATH = Path.home() / ".bp-credentials" / "notion-token.txt"
DATABASE_ID = "2182452d-f1db-803d-ba88-d5bee781a6fd"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _token() -> str:
    # 1) Streamlit secrets (cloud)
    try:
        import streamlit as st
        if "NOTION_TOKEN" in st.secrets:
            return str(st.secrets["NOTION_TOKEN"]).strip()
    except Exception:
        pass
    # 2) env var
    if os.environ.get("NOTION_TOKEN"):
        return os.environ["NOTION_TOKEN"].strip()
    # 3) local credentials file
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    raise RuntimeError(
        "Notion token не найден (ни в secrets, ни в env, ни в ~/.bp-credentials/notion-token.txt)."
    )


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{NOTION_API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        sys.exit(f"Notion API error {e.code} on {method} {path}:\n{body}")


def _rich_text(text: str) -> list:
    """Notion rich_text block из обычной строки."""
    if not text:
        return []
    return [{"type": "text", "text": {"content": text}}]


def _heading(level: int, text: str) -> dict:
    return {
        "object": "block",
        "type": f"heading_{level}",
        f"heading_{level}": {"rich_text": _rich_text(text)},
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _todo(text: str, checked: bool = False) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": _rich_text(text), "checked": checked},
    }


def _table_row(cells: list[str]) -> dict:
    return {
        "type": "table_row",
        "table_row": {"cells": [_rich_text(c) for c in cells]},
    }


def _scene_table(scenes: list[dict]) -> dict:
    """Сценарный план как таблица 4 колонки.

    scenes: [{time, video, tos, voiceover}, ...]
    """
    header = ["Тайминг", "Видеоряд (Инструкция для монтажа)", "Текст на экране (TOS)", "Озвучка (Voiceover)"]
    rows = [_table_row(header)]
    for s in scenes:
        rows.append(_table_row([
            s.get("time", ""),
            s.get("video", ""),
            s.get("tos", ""),
            s.get("voiceover", ""),
        ]))
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": 4,
            "has_column_header": True,
            "has_row_header": False,
            "children": rows,
        },
    }


def _normalize_brand(brand: str) -> str:
    """Привести бренд к ТОЧНОМУ имени опции в Notion-поле Brand (регистр важен — иначе
    Notion создаст дубликат опции). Существующие опции: BelovedPets / TOBYDIC / MAXBUDDY."""
    b = str(brand or "").lower()
    if b.startswith(("tob", "тоб")):
        return "TOBYDIC"
    if "max" in b or "buddy" in b or "бади" in b:
        return "MAXBUDDY"
    return "BelovedPets"


def _build_properties(title: str, end_date: str | None, brand: str = "BelovedPets") -> dict:
    brand_name = _normalize_brand(brand)
    props = {
        "Project name": {"title": _rich_text(title)},
        "Status": {"status": {"name": "Not started"}},
        "Brand": {"multi_select": [{"name": brand_name}]},
        "AI generated": {"checkbox": True},
    }
    if end_date:
        props["End date"] = {"date": {"start": end_date}}
    return props


VALID_MARKETS = {"US", "UK", "CA"}


def _product_block(product_name: str, market: str, drive_url: str, listing_url: str) -> list:
    """Информация о товаре + рынок + Drive + listing в начале страницы.

    Согласно памяти bp-notion-format: любое ТЗ для Дины ВСЕГДА должно включать
    название товара, Drive-ссылку на материалы и listing-ссылку для CTA-контекста.
    """
    blocks = [_paragraph(f"Товар: {product_name}  ·  Рынок: {market}")]
    blocks.append({
        "object": "block",
        "type": "bookmark",
        "bookmark": {"url": drive_url, "caption": []},
    })
    blocks.append({
        "object": "block",
        "type": "bookmark",
        "bookmark": {"url": listing_url, "caption": []},
    })
    return blocks


def create_reel_brief(
    title: str,
    product_name: str,
    market: str,
    drive_url: str,
    listing_url: str,
    end_date: str | None = None,
    about: str = "",
    scenes: list[dict] | None = None,
    action_items: list[str] | None = None,
    documents_urls: list[str] | None = None,
    brand: str = "BelovedPets",
) -> dict:
    """Создать страницу в базе Videos в формате рилса (с таблицей сценария).

    Обязательные параметры (по правилу bp-notion-format):
        title — название страницы (lowercase, формат как у Дины)
        product_name — полное название товара с объёмом/категорией
        market — US / UK / CA
        drive_url — Google Drive ссылка на материалы товара (фото, упаковка)
        listing_url — Amazon / Shopify / Chewy listing для CTA

    Возвращает dict с полями id, url.
    """
    if not product_name:
        raise ValueError("product_name обязателен. Дина не угадает что снимать без названия товара.")
    if not drive_url:
        raise ValueError("drive_url обязателен. Дина теряет время если ищет материалы вручную.")
    if not listing_url:
        raise ValueError("listing_url обязателен. Без него нет контекста для CTA в финальной сцене.")
    if market not in VALID_MARKETS:
        raise ValueError(f"market должен быть US / UK / CA, получено: {market!r}")

    scenes = scenes or []
    action_items = action_items or [""]
    documents_urls = documents_urls or []

    children = [_heading(3, "About project")]
    children.extend(_product_block(product_name, market, drive_url, listing_url))
    if about:
        children.append(_paragraph(about))
    children.extend([
        _heading(3, "Сценарный план (ТЗ):"),
        _scene_table(scenes) if scenes else _paragraph("(сцены будут заполнены)"),
        _heading(3, "Action items"),
    ])
    for item in action_items:
        children.append(_todo(item))
    children.append(_heading(3, "Documents"))
    for url in documents_urls:
        children.append({
            "object": "block",
            "type": "bookmark",
            "bookmark": {"url": url, "caption": []},
        })

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": _build_properties(title, end_date, brand),
        "children": children,
    }
    resp = _request("POST", "/pages", payload)
    return {"id": resp["id"], "url": resp["url"]}


def create_static_brief(
    title: str,
    product_name: str,
    market: str,
    drive_url: str,
    listing_url: str,
    end_date: str | None = None,
    about: str = "",
    action_items: list[str] | None = None,
    documents_urls: list[str] | None = None,
    brand: str = "BelovedPets",
) -> dict:
    """Создать страницу для статичного поста (без таблицы сценария).

    Обязательно: title + product_name + market + drive_url + listing_url.
    """
    if not product_name:
        raise ValueError("product_name обязателен. Дина не угадает что снимать без названия товара.")
    if not drive_url:
        raise ValueError("drive_url обязателен. Дина теряет время если ищет материалы вручную.")
    if not listing_url:
        raise ValueError("listing_url обязателен. Без него нет контекста для CTA.")
    if market not in VALID_MARKETS:
        raise ValueError(f"market должен быть US / UK / CA, получено: {market!r}")

    action_items = action_items or [""]
    documents_urls = documents_urls or []

    children = [_heading(3, "About project")]
    children.extend(_product_block(product_name, market, drive_url, listing_url))
    if about:
        children.append(_paragraph(about))
    children.append(_heading(3, "Action items"))
    for item in action_items:
        children.append(_todo(item))
    children.append(_heading(3, "Documents"))
    for url in documents_urls:
        children.append({
            "object": "block",
            "type": "bookmark",
            "bookmark": {"url": url, "caption": []},
        })

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": _build_properties(title, end_date, brand),
        "children": children,
    }
    resp = _request("POST", "/pages", payload)
    return {"id": resp["id"], "url": resp["url"]}


def list_recent(limit: int = 10) -> list[dict]:
    """10 последних страниц в базе Videos."""
    resp = _request("POST", f"/databases/{DATABASE_ID}/query", {
        "page_size": limit,
        "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
    })
    out = []
    for p in resp["results"]:
        props = p.get("properties", {})
        title_field = props.get("Project name", {}).get("title", [])
        title = title_field[0]["plain_text"] if title_field else "(untitled)"
        status = (props.get("Status", {}).get("status") or {}).get("name", "-")
        brand = [b["name"] for b in props.get("Brand", {}).get("multi_select", [])]
        date = (props.get("End date", {}).get("date") or {}).get("start", "-")
        out.append({"id": p["id"], "url": p["url"], "title": title, "status": status, "brand": brand, "date": date})
    return out


def delete_page(page_id: str) -> None:
    """Архивирует страницу (Notion не удаляет, помечает archived=true)."""
    _request("PATCH", f"/pages/{page_id}", {"archived": True})


def _cli_test() -> None:
    """Создаёт тестовую страницу с примером данных, чтобы Дарья посмотрела формат."""
    result = create_reel_brief(
        title="[ТЕСТ Jack v4] eye wash persian uk reel",
        product_name="Beloved Pets Eye Wash 100ml (2-in-1, Eye & Ear Care)",
        market="UK",
        drive_url="https://drive.google.com/drive/folders/REPLACE_ME_eye_wash_assets",
        listing_url="https://www.amazon.co.uk/dp/REPLACE_ME",
        end_date="2026-06-15",
        about=(
            "ТЕСТОВЫЙ ТЗ для проверки формата Джека (v2 — с товаром). "
            "Референс: https://www.tiktok.com/@example/video/123 — POV-формат с persian cat. "
            "Сделать в стиле problem → reveal → transformation. Voiceover UK English. "
            "После проверки формата — можно удалить."
        ),
        scenes=[
            {
                "time": "0:00-0:06",
                "video": "Крупный план персидского кота с мокрыми слёзными дорожками, грустный взгляд в камеру.",
                "tos": "POV: your Persian's eyes are leaking again 😢",
                "voiceover": "If your flat-faced cat has tear stains, this isn't allergies — it's their anatomy.",
            },
            {
                "time": "0:06-0:13",
                "video": "Руки берут флакон Beloved Pets Eye Wash, капают 2 капли в глаз коту. Кот спокойно реагирует.",
                "tos": "2 drops. 60 seconds. Done ✨",
                "voiceover": "Two gentle drops, wipe, and you're done. That's the whole routine.",
            },
            {
                "time": "0:13-0:20",
                "video": "Before/after split-screen: грустный кот → тот же кот с сухой мордочкой, 7 дней спустя.",
                "tos": "7 days later 👀",
                "voiceover": "Your cat won't tell you it bothers them. That's our job.",
            },
            {
                "time": "0:20-0:25",
                "video": "Кот на подоконнике, Beloved Pets Eye Wash на переднем плане. UK флаг в углу.",
                "tos": "Gentle care on Amazon UK 🇬🇧",
                "voiceover": "Search Beloved Pets Eye Wash on Amazon UK today.",
            },
        ],
        action_items=[
            "Найти/снять кадры персидского кота (5-7 сек b-roll)",
            "Снять кадр капля в глаз — крупный план, daylight",
            "Etiketka Eye Wash крупно (packshot)",
            "Подобрать UK Voiceover актёра",
            "Submit в Higgsfield → final review",
        ],
    )
    print(f"OK — создана тестовая страница:")
    print(f"  ID:  {result['id']}")
    print(f"  URL: {result['url']}")
    print()
    print("Открой в Notion и проверь формат. Если ок — удали через:")
    print(f"  python3 {Path(__file__).name} delete {result['id']}")


def _cli_list() -> None:
    for b in list_recent(10):
        print(f"  • {b['title'][:60]:60s} | {b['status']:12s} | {','.join(b['brand']):12s} | {b['date']} | {b['id']}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "test":
        _cli_test()
    elif cmd == "list":
        _cli_list()
    elif cmd == "delete":
        if len(args) < 2:
            sys.exit("Usage: python3 jack_notion.py delete <page_id>")
        delete_page(args[1])
        print(f"Archived: {args[1]}")
    else:
        sys.exit(f"Unknown command: {cmd}. Run with -h for help.")


if __name__ == "__main__":
    main()
