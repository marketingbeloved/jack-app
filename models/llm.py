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
# мощностей, поэтому если 2.5-flash лёг, 2.0-flash обычно отвечает. Все бесплатные.
_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]


def _is_overload(err: str) -> bool:
    e = (err or "").lower()
    return any(s in e for s in ("перегруж", "503", "429", "unavailable", "overload", "high demand"))


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
        if not _is_overload(err):
            break  # не перегрузка (битый ключ/лимит) — другая модель не спасёт
    return last_err


def gemini_vision(prompt: str, images: list[bytes], mime_types: list[str] | None = None,
                  model: str = "gemini-2.5-flash", timeout: int = 90) -> str:
    """Send a prompt + images to Gemini (с фолбэком по моделям). Returns text or '⚠️ …'."""
    mime_types = mime_types or ["image/jpeg"] * len(images)
    parts = [{"text": prompt}]
    for img, mt in zip(images, mime_types):
        parts.append({"inline_data": {"mime_type": mt or "image/jpeg",
                                       "data": base64.b64encode(img).decode()}})
    return _gemini_call({"contents": [{"parts": parts}]}, timeout, model)


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
