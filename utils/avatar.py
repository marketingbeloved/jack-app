"""Avatar resolution for Jack.

Returns a base64 data: URI for jack_{state}.{jpg|png} so the photo renders WITHOUT
depending on Streamlit static serving (works the same locally and in the cloud).
Files live in jack-app/static/avatars/jack_{state}.{jpg|png}.
"""

import base64
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "avatars"

DICEBEAR_PERSONAS = (
    "https://api.dicebear.com/9.x/personas/svg"
    "?seed=jack-belovedpets-v3"
    "&backgroundColor=4a6b3a,6b8e5a,d6c9a8"
    "&hair=shortCombover&hairColor=362c47&skinColor=e5a07e"
    "&clothingColor=2b2a28&facialHair=stubble&radius=50"
)

_CACHE: dict = {}


def get_avatar_url(state: str = "idle") -> str:
    """Return a data: URI for the Jack photo (falls back to idle, then Dicebear)."""
    for s in (state, "idle"):
        for ext in ("jpg", "jpeg", "png", "webp"):
            f = STATIC_DIR / f"jack_{s}.{ext}"
            if f.exists():
                key = (s, ext, int(f.stat().st_mtime))
                if key in _CACHE:
                    return _CACHE[key]
                mime = "jpeg" if ext in ("jpg", "jpeg") else ext
                uri = "data:image/%s;base64,%s" % (
                    mime, base64.b64encode(f.read_bytes()).decode())
                _CACHE[key] = uri
                return uri
    return DICEBEAR_PERSONAS
