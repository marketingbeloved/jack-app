"""Абстракция LLM-вызовов для Джека.

Главный мозг — Claude Code CLI через subprocess (корпоративная подписка, бесплатно).
Gemini — только «зрение» (смотрит картинки, пишет подписи). ТЗ пишет только Claude.
"""

from __future__ import annotations

import base64
import os
import subprocess
import time
from pathlib import Path


def _gemini_request(url: str, body: dict, timeout: int, attempts: int = 4) -> tuple[str, str]:
    """POST к Gemini с автоповтором при ВРЕМЕННОЙ перегрузке (503/429/500 — 'high demand').
    Возвращает (text, ""), либо ("", "⚠️ …") с человеческим текстом. Бэкофф 2/4/6 сек."""
    import requests
    for i in range(attempts):
        try:
            r = requests.post(url, json=body, timeout=timeout)
            if r.status_code == 200:
                try:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip(), ""
                except Exception:
                    return "", "⚠️ Gemini вернул пустой ответ — попробуй ещё раз."
            if r.status_code in (429, 500, 503) and i < attempts - 1:
                time.sleep(2 * (i + 1))  # 2s, 4s, 6s — переждать всплеск спроса
                continue
            if r.status_code in (429, 503):
                return "", ("⚠️ Gemini сейчас перегружен (всплеск спроса у Google). "
                            "Это временно — подожди минуту и нажми ещё раз.")
            return "", f"⚠️ Gemini ошибка {r.status_code}: {r.text[:300]}"
        except Exception as e:  # noqa: BLE001
            if i < attempts - 1:
                time.sleep(2 * (i + 1))
                continue
            return "", f"⚠️ Gemini запрос не прошёл: {e}"
    return "", "⚠️ Gemini перегружен — попробуй чуть позже."


def _gemini_key() -> str:
    """Find a working Gemini API key (Streamlit secrets → env → JoinBrands .env)."""
    try:
        import streamlit as st
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()
    env_path = Path.home() / "Downloads" / "joinbrands-automation" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


# При перегрузке одной модели (503 «high demand») пробуем другие — у них РАЗНЫЕ пулы
# мощностей, поэтому если одна легла, соседняя обычно отвечает. Все бесплатные.
# ВАЖНО: gemini-2.0-flash и gemini-2.5-pro Google СНЯЛ с обслуживания (404 «no longer
# available») — держать их в цепочке нельзя, она обрывалась на первом же 404.
_FALLBACK_MODELS = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-2.5-flash",
                    "gemini-flash-latest"]

# Модель «зрения» (видео/кадры/фото → подписи). Отдельно от текстовой, чтобы поднимать
# качество подписей, не трогая генерацию скриптов рилсов. Выбрана по замеру на реальном
# рилсе: подпись заземлена по видео за ~11 сек (3.5-flash даёт то же за ~67 сек — для
# веб-сессии Streamlit это риск обрыва, поэтому она в фолбэке, а не первой).
VISION_MODEL = "gemini-3-flash-preview"


def _is_overload(err: str) -> bool:
    e = (err or "").lower()
    return any(s in e for s in ("перегруж", "503", "429", "unavailable", "overload", "high demand"))


def _is_retired(err: str) -> bool:
    """Модель снята с обслуживания (404) — надо идти к следующей, а не сдаваться."""
    e = (err or "").lower()
    return "404" in e and ("no longer available" in e or "not found" in e)


def _gemini_call(body: dict, timeout: int, primary: str) -> str:
    """Вызов Gemini с фолбэком по моделям при перегрузке. Текст или '⚠️ …'."""
    key = _gemini_key()
    if not key:
        return "⚠️ Gemini key не найден."
    models = [primary] + [m for m in _FALLBACK_MODELS if m != primary]
    last_err = "⚠️ Gemini недоступен."
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        text, err = _gemini_request(url, body, timeout)
        if text:
            return text
        last_err = err
        if not (_is_overload(err) or _is_retired(err)):
            break  # не перегрузка и не снятая модель (битый ключ/лимит) — другая не спасёт
    return last_err


def gemini_vision(prompt: str, images: list[bytes], mime_types: list[str] | None = None,
                  model: str = "", timeout: int = 120) -> str:
    """Send a prompt + images to Gemini (с фолбэком по моделям). Returns text or '⚠️ …'."""
    mime_types = mime_types or ["image/jpeg"] * len(images)
    parts = [{"text": prompt}]
    for img, mt in zip(images, mime_types):
        parts.append({"inline_data": {"mime_type": mt or "image/jpeg",
                                       "data": base64.b64encode(img).decode()}})
    return _gemini_call({"contents": [{"parts": parts}]}, timeout, model or VISION_MODEL)


# ─── Видео целиком (а не кадры) — чтобы Джек реально «смотрел» рилс ──────────
# Inline-запрос к Gemini ограничен ~20 МБ вместе с base64 (+33%), поэтому рилсы
# тяжелее лимита уходят через Files API (там до 2 ГБ).
_VIDEO_INLINE_LIMIT = 12 * 1024 * 1024
_FILES_BASE = "https://generativelanguage.googleapis.com"


def _files_upload(video_bytes: bytes, mime: str, timeout: int = 300) -> tuple[str, str, str]:
    """Залить видео в Gemini Files API → (file_name, file_uri, ""), либо ("", "", "⚠️ …").

    Google дожимает видео на своей стороне: пока state != ACTIVE, generateContent
    отвечает 400 — поэтому ждём готовности. Файл живёт у Google 48 ч, мы убираем его
    сразу после ответа (см. gemini_video).
    """
    import requests
    key = _gemini_key()
    try:
        start = requests.post(
            f"{_FILES_BASE}/upload/v1beta/files?key={key}",
            headers={"X-Goog-Upload-Protocol": "resumable",
                     "X-Goog-Upload-Command": "start",
                     "X-Goog-Upload-Header-Content-Length": str(len(video_bytes)),
                     "X-Goog-Upload-Header-Content-Type": mime,
                     "Content-Type": "application/json"},
            json={"file": {"display_name": "reel"}}, timeout=60,
        )
        up_url = start.headers.get("X-Goog-Upload-URL", "")
        if start.status_code != 200 or not up_url:
            return "", "", f"⚠️ Gemini не принял загрузку видео ({start.status_code})."
        fin = requests.post(
            up_url,
            headers={"Content-Length": str(len(video_bytes)), "X-Goog-Upload-Offset": "0",
                     "X-Goog-Upload-Command": "upload, finalize"},
            data=video_bytes, timeout=timeout,
        )
        if fin.status_code != 200:
            return "", "", f"⚠️ Видео не догрузилось в Gemini ({fin.status_code})."
        f = fin.json().get("file", {})
        name, uri = f.get("name", ""), f.get("uri", "")
        for _ in range(45):  # до ~90 сек на обработку
            if f.get("state") == "ACTIVE":
                return name, uri, ""
            time.sleep(2)
            try:
                f = requests.get(f"{_FILES_BASE}/v1beta/{name}?key={key}", timeout=30).json()
            except Exception:  # noqa: BLE001, PERF203
                continue
        return name, "", "⚠️ Gemini не успел обработать видео — попробуй ещё раз."
    except Exception as e:  # noqa: BLE001
        return "", "", f"⚠️ Загрузка видео в Gemini не прошла: {str(e)[:200]}"


def _files_delete(name: str) -> None:
    if not name:
        return
    try:
        import requests
        requests.delete(f"{_FILES_BASE}/v1beta/{name}?key={_gemini_key()}", timeout=30)
    except Exception:
        pass


def gemini_video(prompt: str, video_bytes: bytes, mime_type: str = "video/mp4",
                 images: list[bytes] | None = None, mime_types: list[str] | None = None,
                 model: str = "", timeout: int = 240) -> str:
    """Отправить в Gemini САМО ВИДЕО (движение, звук, текст на экране), а не раскадровку.

    Мелкие рилсы уходят inline, тяжёлые — через Files API. Можно добавить фото
    (доп. кадры/референсы). Возвращает текст или '⚠️ …' — вызывающий тогда падает
    на кадры (см. jack_engine.caption_from_media).
    """
    if not _gemini_key():
        return "⚠️ Gemini key не найден."
    images = list(images or [])
    mime_types = list(mime_types or ["image/jpeg"] * len(images))

    parts: list = [{"text": prompt}]
    fname = ""
    if len(video_bytes) <= _VIDEO_INLINE_LIMIT:
        parts.append({"inline_data": {"mime_type": mime_type,
                                      "data": base64.b64encode(video_bytes).decode()}})
    else:
        fname, uri, err = _files_upload(video_bytes, mime_type, timeout)
        if err:
            _files_delete(fname)
            return err
        parts.append({"file_data": {"mime_type": mime_type, "file_uri": uri}})
    for img, mt in zip(images, mime_types):
        parts.append({"inline_data": {"mime_type": mt or "image/jpeg",
                                      "data": base64.b64encode(img).decode()}})
    try:
        return _gemini_call({"contents": [{"parts": parts}]}, timeout, model or VISION_MODEL)
    finally:
        _files_delete(fname)


def gemini_text(prompt: str, system: str = "", model: str = "gemini-2.5-flash",
                timeout: int = 120) -> str:
    """Text-only Gemini call (с фолбэком по моделям при перегрузке). Returns text or '⚠️ …'."""
    body: dict = {"contents": [{"parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return _gemini_call(body, timeout, model)


def has_claude_cli() -> bool:
    """Is the `claude` CLI available (i.e. running locally, not on Streamlit Cloud)?"""
    import shutil
    return shutil.which("claude") is not None


def _anthropic_key() -> str:
    """Anthropic API key (Streamlit secrets → env). Used when the CLI is absent (cloud)."""
    try:
        import streamlit as st
        if "ANTHROPIC_API_KEY" in st.secrets:
            return str(st.secrets["ANTHROPIC_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def _anthropic_model() -> str:
    try:
        import streamlit as st
        if "ANTHROPIC_MODEL" in st.secrets:
            return str(st.secrets["ANTHROPIC_MODEL"]).strip()
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()


def claude_api(prompt: str, system: str = "", timeout: int = 180) -> str:
    """Call Claude via the Anthropic API (same Claude brain, billed per token).

    Used on cloud where the CLI/subscription isn't available. Returns text or '⚠️ …'.
    """
    key = _anthropic_key()
    if not key:
        return "⚠️ ANTHROPIC_API_KEY не задан."
    try:
        from anthropic import Anthropic
    except Exception:
        return "⚠️ пакет anthropic не установлен."
    try:
        client = Anthropic(api_key=key, timeout=float(timeout))
        msg = client.messages.create(
            model=_anthropic_model(),
            max_tokens=4096,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        return "\n".join(parts).strip() or "⚠️ пустой ответ от Claude API."
    except Exception as e:  # noqa: BLE001
        return f"⚠️ Claude API ошибка: {str(e)[:300]}"


def smart_text(prompt: str, system: str = "", timeout: int = 180) -> str:
    """Text generation with the best brain available, so the SHARED cloud site can write.

    Order of preference (best quality first, transparent to the caller):
      1. Claude Code CLI — on Darya's / Tanya's Mac (corporate subscription, free, best tone).
      2. Claude API — only if ANTHROPIC_API_KEY is set (needs a card; off by default).
      3. Gemini 2.5 Pro — FREE, no card, runs server-side. Powers the one shared site so
         all 4 teammates use a single app, no local copies. Pro (not Flash) for quality.
    Returns a clear '⚠️ …' notice only if NONE are available.
    """
    if has_claude_cli():
        out = claude(prompt, system=system, timeout=timeout)
        if out and not out.startswith("⚠️"):
            return out
    if _anthropic_key():
        out = claude_api(prompt, system=system, timeout=timeout)
        if out and not out.startswith("⚠️"):
            return out
    # Cloud, no Claude: write with Gemini 2.5 Flash — the strongest model that the FREE
    # tier actually serves (Pro is quota-locked to 429 on free). Free + no card, so the
    # one shared site can write for the whole team. ANTHROPIC_MODEL/billing unlocks Pro later.
    out = gemini_text(prompt, system=system, model="gemini-2.5-flash", timeout=timeout)
    if out and not out.startswith("⚠️"):
        return out
    # Честная диагностика: если ключ ВООБЩЕ не настроен — одно; если ключ есть, но
    # Gemini вернул ошибку (протух токен / лимит / перегрузка) — показываем ЕЁ, а не
    # вводящее в заблуждение «нет ключа».
    if not _gemini_key():
        return ("⚠️ Ключ Gemini не настроен. Добавь GEMINI_API_KEY в Settings → Secrets.")
    return ("⚠️ Gemini не ответил (ключ есть, но запрос отклонён — возможно протух токен, "
            f"лимит или перегрузка). Точный ответ Gemini: {out[:200]}")


def claude(prompt: str, system: str = "", timeout: int = 600) -> str:
    """Запросить Claude Code через CLI subprocess.

    Args:
        prompt: пользовательский запрос
        system: системный промпт (опционально)
        timeout: таймаут в секундах

    Returns:
        текст ответа от Claude
    """
    cmd = ["claude", "-p", prompt]
    if system:
        cmd.extend(["--system-prompt", system])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        return f"⚠️ Claude ошибка: {result.stderr.strip()}"
    return result.stdout.strip()


def jack(prompt: str) -> str:
    """Запросить Claude в роли Джека (через skill jack).

    Skill `jack` уже зарегистрирован в ~/.claude/skills/jack/SKILL.md
    Передаём промпт с упоминанием Джека — Claude активирует skill.
    """
    system = (
        "Ты Джек — senior SMM-креативщик Beloved Pets с 7+ лет опыта. "
        "Следуй инструкциям из ~/.claude/skills/jack/SKILL.md. "
        "Тон: прямой, тёплый, по делу, без emoji в чате. "
        "Перед ТЗ читай ~/Databases/BP-Brand-Brief.md и связанные памяти bp-*."
    )
    return claude(prompt, system=system)


def available_models() -> dict:
    """Реально работающие модели (без пустышек)."""
    return {
        "claude_code": {
            "name": "Claude (корпоративный)",
            "use_for": "Главный мозг — пишет все ТЗ, скрипты, концепты, анализирует",
            "cost": "$0 (ваша безлимитная корпоративная подписка)",
            "how": "claude CLI на маке (Дарья/Таня, один аккаунт)",
            "status": "✅ работает",
        },
        "gemini_vision": {
            "name": "Gemini (зрение)",
            "use_for": "Смотрит на готовые картинки/карусели и пишет к ним текст и подписи",
            "cost": "$0 (ключ без карты)",
            "how": "REST API, только для картинок — НЕ пишет ТЗ",
            "status": "✅ работает",
        },
    }
