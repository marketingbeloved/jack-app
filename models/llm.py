"""Абстракция LLM-вызовов для Джека.

Главный мозг — Claude Code CLI через subprocess (корпоративная подписка, бесплатно).
Gemini — только «зрение» (смотрит картинки, пишет подписи). ТЗ пишет только Claude.
"""

from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path


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


def gemini_vision(prompt: str, images: list[bytes], mime_types: list[str] | None = None,
                  model: str = "gemini-2.5-flash", timeout: int = 90) -> str:
    """Send a prompt + images to Gemini and return the text reply.

    images: list of raw image bytes. mime_types: parallel list (default image/jpeg).
    """
    import requests
    key = _gemini_key()
    if not key:
        return "⚠️ Gemini key не найден (ни в secrets, ни в env, ни в JoinBrands .env)."
    mime_types = mime_types or ["image/jpeg"] * len(images)
    parts = [{"text": prompt}]
    for img, mt in zip(images, mime_types):
        parts.append({"inline_data": {"mime_type": mt or "image/jpeg",
                                       "data": base64.b64encode(img).decode()}})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    try:
        r = requests.post(url, json={"contents": [{"parts": parts}]}, timeout=timeout)
        if r.status_code != 200:
            return f"⚠️ Gemini ошибка {r.status_code}: {r.text[:300]}"
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001
        return f"⚠️ Gemini запрос не прошёл: {e}"


def gemini_text(prompt: str, system: str = "", model: str = "gemini-2.5-flash",
                timeout: int = 120) -> str:
    """Text-only Gemini call. Returns reply text or a '⚠️ …' error string."""
    import requests
    key = _gemini_key()
    if not key:
        return "⚠️ Gemini key не найден."
    contents = [{"parts": [{"text": prompt}]}]
    body: dict = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    try:
        r = requests.post(url, json=body, timeout=timeout)
        if r.status_code != 200:
            return f"⚠️ Gemini ошибка {r.status_code}: {r.text[:300]}"
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001
        return f"⚠️ Gemini запрос не прошёл: {e}"


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
    # Cloud, no Claude: write with the strongest FREE model (Gemini 2.5 Pro) so the
    # shared site isn't read-only. Falls back to Flash if Pro is rate-limited.
    out = gemini_text(prompt, system=system, model="gemini-2.5-pro", timeout=timeout)
    if out and not out.startswith("⚠️"):
        return out
    out = gemini_text(prompt, system=system, model="gemini-2.5-flash", timeout=timeout)
    if out and not out.startswith("⚠️"):
        return out
    return ("⚠️ Генерация недоступна: нет ни Claude (мак), ни ключа Gemini. "
            "Добавь GEMINI_API_KEY в Settings → Secrets, чтобы Джек писал на сайте.")


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
