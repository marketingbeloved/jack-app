"""Отправка ТЗ в ClickUp — задачей исполнителю, который не снимает видео.

Зачем отдельно от Notion. ТЗ Дине уезжает в её базу Videos в Notion — там формат
со сценами и таймингом. У Вики, Тани и Марии работа живёт в ClickUp, а кнопка в
ячейке была одна и всегда называлась «Написать ТЗ Дине»: ТЗ для Вики улетало в
Динину видео-базу, то есть не туда, куда нужно.

Доступ. Нужен личный API-токен ClickUp (Settings → Apps → API Token, начинается
с `pk_`) и список, в который ставить задачи. Берём из первого доступного места:
  1. секреты Streamlit — CLICKUP_TOKEN / CLICKUP_LIST_ID (так работает облако);
  2. переменные окружения с теми же именами;
  3. файл ~/.config/clickup/token (локально на маке).
Списка можно не знать заранее: если задан CLICKUP_VIEW (id вида из ссылки вроде
app.clickup.com/9003222613/v/l/8ca4hjn-12392), список определяется по нему сам.

Без токена модуль не падает и ничего не выдумывает — возвращает понятную ошибку,
которую видно в приложении.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path

API = "https://api.clickup.com/api/v2"


def _secret(name: str) -> str:
    """Значение настройки: секреты Streamlit → переменная окружения → пусто."""
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return os.environ.get(name, "").strip()


def token() -> str:
    """API-токен ClickUp. Локально можно положить в ~/.config/clickup/token."""
    t = _secret("CLICKUP_TOKEN")
    if t:
        return t
    f = Path.home() / ".config" / "clickup" / "token"
    try:
        return f.read_text().strip()
    except Exception:
        return ""


def _headers() -> dict:
    return {"Authorization": token(), "Content-Type": "application/json"}


def view_id_from_url(url: str) -> str:
    """id вида из ссылки ClickUp: .../v/l/<view_id> или .../v/li/<view_id>."""
    m = re.search(r"/v/l[i]?/([A-Za-z0-9-]+)", url or "")
    return m.group(1) if m else ""


def _list_from_view(view: str) -> str:
    """Список, на котором построен вид. ClickUp отдаёт его в parent вида."""
    import requests
    try:
        r = requests.get(f"{API}/view/{view}", headers=_headers(), timeout=20)
        if r.status_code != 200:
            return ""
        parent = (r.json().get("view") or {}).get("parent") or {}
        # type 6 — список; у видов пространства/папки списка нет
        return str(parent.get("id") or "") if parent.get("type") == 6 else ""
    except Exception:
        return ""


def list_id() -> str:
    """Список, куда ставим задачи: прямой id или вычисленный из вида."""
    direct = _secret("CLICKUP_LIST_ID")
    if direct:
        return direct
    view = _secret("CLICKUP_VIEW")
    if view:
        return _list_from_view(view_id_from_url(view) or view)
    return ""


def configured() -> tuple[bool, str]:
    """(готово ли слать, что именно не хватает) — чтобы приложение сказало это словами."""
    if not token():
        return False, ("Нет токена ClickUp. Нужен личный API-токен (ClickUp → Settings → "
                       "Apps → API Token, начинается с `pk_`) — пришли его, пропишу в "
                       "секреты приложения.")
    if not list_id():
        return False, ("Токен есть, но не задан список ClickUp, куда ставить задачи. "
                       "Пришли ссылку на нужный список — пропишу (CLICKUP_LIST_ID).")
    return True, ""


def _due_ms(date_key: str) -> int | None:
    """Срок задачи — дата поста «ДД.ММ». Год берём ближайший: если месяц сильно
    позади текущего, значит это уже следующий год (декабрь → январь)."""
    try:
        d, m = (int(x) for x in date_key.split("."))
    except (ValueError, AttributeError):
        return None
    today = date.today()
    year = today.year
    if m < today.month - 6:
        year += 1
    try:
        dt = datetime(year, m, d, 12, 0)
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


def _body(post: dict, brief: dict, brand: str, date_key: str, for_name: str) -> str:
    """Текст задачи: ТЗ плюс короткая шапка — что за пост и откуда он."""
    from views.content_plan import POST_FORMATS, TYPE_COLORS  # локально: модуль UI

    fmt = POST_FORMATS.get(post.get("format", ""), "") if post.get("format") else ""
    cat = (TYPE_COLORS.get(post.get("type", ""), {}) or {}).get("label", "")
    head = [f"**Бренд:** {brand}", f"**Дата:** {date_key}"]
    if fmt:
        head.append(f"**Формат:** {fmt}")
    if cat:
        head.append(f"**Категория:** {cat}")
    if post.get("pillar"):
        head.append(f"**Пиллар:** {post['pillar']}")
    if brief.get("link"):
        head.append(f"**Исходники:** {brief['link']}")
    head.append(f"**Исполнитель:** {for_name}")
    return "\n".join(head) + "\n\n---\n\n" + (brief.get("text") or "")


def push_task(post: dict, brief: dict, *, brand: str = "BelovedPets", date_key: str = "",
              for_name: str = "", force: bool = False) -> dict:
    """Поставить задачу с ТЗ в ClickUp.

    Возвращает {"url":…}, {"skipped":…, "url":…} если задача уже стоит, или {"error":…}.
    Повторная отправка создаёт не новую задачу, а обновляет ту же — так же, как с
    Notion: там каждое нажатие кнопки когда-то плодило дубли у Дины.
    """
    text = (brief or {}).get("text", "") or ""
    if not text.strip():
        return {"error": "У поста нет ТЗ — сначала напиши его, потом отправляй."}

    ok, why = configured()
    if not ok:
        return {"error": why}

    import requests
    already = (brief or {}).get("clickup_url", "")
    name = f"{date_key} · {post.get('title', '')}".strip(" ·")
    payload = {"name": name, "markdown_description": _body(post, brief, brand, date_key, for_name)}
    due = _due_ms(date_key)
    if due:
        payload["due_date"] = due
        payload["due_date_time"] = False

    try:
        if already and not force:
            return {"skipped": "Эта задача уже стоит в ClickUp — второй раз не создаю.",
                    "url": already}
        if already and force:
            task_id = already.rstrip("/").split("/")[-1]
            r = requests.put(f"{API}/task/{task_id}", headers=_headers(), json=payload, timeout=30)
            if r.status_code != 200:
                return {"error": f"ClickUp не обновил задачу ({r.status_code}): {r.text[:200]}"}
            return {"url": already}
        r = requests.post(f"{API}/list/{list_id()}/task", headers=_headers(),
                          json=payload, timeout=30)
        if r.status_code not in (200, 201):
            return {"error": f"ClickUp не принял задачу ({r.status_code}): {r.text[:200]}"}
        return {"url": r.json().get("url", "")}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Не получилось достучаться до ClickUp: {type(e).__name__}"}
