"""Скачать видео референса по ссылке — чтобы Джек посмотрел САМ рилс, а не описание.

Зачем отдельный модуль: Instagram и TikTok без авторизации видео не отдают. Проверено
07.09.2026 — `yt-dlp` на IG-рилс отвечает «rate-limit reached or login required», на
TikTok «Unable to extract webpage video data», а embed-страница IG приезжает пустой
（весь контент подгружается JS, ни og:video, ни caption в HTML нет). Поэтому:

  • ссылку ВСЕГДА пробуем скачать (открытые YouTube/Shorts и часть TikTok отдаются);
  • для Instagram работает только с cookies — либо файл рядом с приложением
    (`cache/ig_cookies.txt`), либо секрет `IG_COOKIES` в Streamlit (текст в формате
    Netscape), либо живой профиль браузера на маке (`--cookies-from-browser`);
  • если не вышло — возвращаем ЧЕСТНУЮ ошибку с подсказкой, а UI просит залить файл
    или скриншоты. Никаких «Джек посмотрел» без реального видео.

Ничего платного: yt-dlp бесплатен, аккаунты и сервисы скрейпинга не нужны.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

# Gemini принимает видео до ~20 МБ инлайном и крупнее через Files API (см. llm.gemini_video),
# но 15-секундный рилс весит единицы мегабайт — ограничиваем, чтобы не тянуть 4K-исходники.
MAX_BYTES = 60 * 1024 * 1024
COOKIES_FILE = Path(__file__).resolve().parent.parent / "cache" / "ig_cookies.txt"


def looks_like_url(text: str) -> bool:
    return bool(re.match(r"https?://", (text or "").strip(), re.I))


def platform_of(url: str) -> str:
    u = (url or "").lower()
    if "instagram.com" in u:
        return "Instagram"
    if "tiktok.com" in u:
        return "TikTok"
    if "youtube.com" in u or "youtu.be" in u:
        return "YouTube"
    return "ссылка"


def _cookies_path() -> str:
    """Файл cookies в формате Netscape: локально — cache/ig_cookies.txt, в облаке — секрет."""
    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 50:
        return str(COOKIES_FILE)
    raw = ""
    try:
        import streamlit as st
        if "IG_COOKIES" in st.secrets:
            raw = str(st.secrets["IG_COOKIES"])
    except Exception:
        pass
    raw = raw or os.environ.get("IG_COOKIES", "")
    if raw.strip():
        tmp = Path(tempfile.gettempdir()) / "jack_ig_cookies.txt"
        tmp.write_text(raw if raw.startswith("# Netscape") else "# Netscape HTTP Cookie File\n" + raw,
                       encoding="utf-8")
        return str(tmp)
    return ""


def _attempts(url: str) -> list[dict]:
    """Попытки по возрастанию требований: без cookies → файл cookies → профиль браузера."""
    tries: list[dict] = [{}]
    cp = _cookies_path()
    if cp:
        tries.append({"cookiefile": cp})
    # Локально на маке Дарьи в браузере уже есть живая сессия Instagram. В облаке этих
    # браузеров нет — попытка просто не сработает и мы пойдём дальше.
    for browser in ("chrome", "safari", "firefox", "edge"):
        tries.append({"cookiesfrombrowser": (browser, None, None, None)})
    return tries


def fetch_video(url: str, timeout: int = 120) -> tuple[bytes, str, dict]:
    """Скачать видео по ссылке.

    Returns:
        (bytes, суффикс файла, meta) — meta: {"title","uploader","duration","platform","via"}.
        При неудаче: (b"", "", {"error": "человеческое объяснение, что делать"}).
    """
    url = (url or "").strip()
    if not looks_like_url(url):
        return b"", "", {"error": "Это не похоже на ссылку — нужна ссылка на рилс/видео."}
    try:
        import yt_dlp
    except Exception:
        return b"", "", {"error": "На этой машине нет yt-dlp (`pip install yt-dlp`) — "
                                  "залей видеофайл или скриншоты."}

    plat = platform_of(url)
    last_err = ""
    with tempfile.TemporaryDirectory() as tmp:
        for extra in _attempts(url):
            opts = {
                "outtmpl": os.path.join(tmp, "ref.%(ext)s"),
                "format": "mp4/bv*[ext=mp4]+ba[ext=m4a]/best",
                "quiet": True, "no_warnings": True, "noprogress": True,
                "socket_timeout": 30, "retries": 2, "noplaylist": True,
                "max_filesize": MAX_BYTES,
            }
            opts.update(extra)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
            except Exception as e:  # noqa: BLE001
                last_err = str(e).split("\n")[0][:300]
                continue
            files = sorted(Path(tmp).glob("ref.*"), key=lambda p: p.stat().st_size, reverse=True)
            if not files:
                last_err = last_err or "файл не скачался"
                continue
            f = files[0]
            data = f.read_bytes()
            if not data:
                last_err = "скачался пустой файл"
                continue
            via = ("cookies" if "cookiefile" in extra else
                   f"браузер {extra['cookiesfrombrowser'][0]}" if "cookiesfrombrowser" in extra
                   else "без авторизации")
            meta = {
                "platform": plat, "via": via,
                "title": (info or {}).get("title", "") or "",
                "uploader": (info or {}).get("uploader", "") or "",
                "duration": (info or {}).get("duration") or 0,
                "description": ((info or {}).get("description") or "")[:1500],
                "size_mb": round(len(data) / 1024 / 1024, 1),
            }
            return data, f.suffix or ".mp4", meta

    hint = ("Instagram отдаёт видео только со входом. Открой рилс, сохрани видео и залей "
            "файлом — или сделай 3-5 скриншотов ключевых моментов, Джеку этого хватит."
            if plat == "Instagram" else
            "Платформа не отдала видео без входа. Залей файл или скриншоты — "
            "или опиши рилс словами, Джек честно пометит, что не смотрел его.")
    return b"", "", {"error": f"{plat}: не удалось скачать. {hint}", "detail": last_err}
