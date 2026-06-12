"""Avatar resolution for Jack.

Streamlit static serving must be enabled (.streamlit/config.toml -> enableStaticServing = true).
Avatar files live in jack-app/static/avatars/jack_{state}.{jpg|png}
and are served at the URL /app/static/avatars/jack_{state}.{ext}?v=<mtime>
The ?v= cache-buster forces browsers to reload after upload.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "avatars"

DICEBEAR_PERSONAS = (
    "https://api.dicebear.com/9.x/personas/svg"
    "?seed=jack-belovedpets-v3"
    "&backgroundColor=4a6b3a,6b8e5a,d6c9a8"
    "&hair=shortCombover"
    "&hairColor=362c47"
    "&skinColor=e5a07e"
    "&clothingColor=2b2a28"
    "&facialHair=stubble"
    "&radius=50"
)


def get_avatar_url(state: str = "idle") -> str:
    """Return URL path Streamlit can serve, with ?v=<mtime> cache-bust."""
    for ext in ("jpg", "jpeg", "png", "webp"):
        f = STATIC_DIR / f"jack_{state}.{ext}"
        if f.exists():
            mtime = int(f.stat().st_mtime)
            return f"app/static/avatars/jack_{state}.{ext}?v={mtime}"
    # fallback to idle
    for ext in ("jpg", "jpeg", "png", "webp"):
        f = STATIC_DIR / f"jack_idle.{ext}"
        if f.exists():
            mtime = int(f.stat().st_mtime)
            return f"app/static/avatars/jack_idle.{ext}?v={mtime}"
    return DICEBEAR_PERSONAS
