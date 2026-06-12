"""Animated Jack — real photo with CSS aura + rotating humour jokes.

CSS lives globally in utils/styles.py (JACK_AVATAR_CSS).
This module only renders HTML for the avatar block.
"""

from utils.avatar import get_avatar_url


JACK_JOKES = [
    "doomscrolling for ideas — totally research 🪙",
    "wait, is that a viral hook or just a cat? 🐈",
    "Pet Honesty just dropped — let's clown it 🤡",
    "POV: typing your next million-view reel ✍️",
    "scrolling TikTok at work? me? never. 🙄",
    "vet-tech said it works — citation needed 📚",
    "found gold in the algorithm 🌊",
]


def render_jack(state: str = "idle", action_text: str = "online · listening for tasks", mood: str = "idle") -> str:
    """HTML only — CSS is injected once globally via utils.styles.inject().

    Args:
        state:  which photo file to load (idle/working/thinking/done/error)
        mood:   which CSS animation class to apply on the wrap
                (idle/thinking/typing/happy/tilt)
    """
    url = get_avatar_url(state)
    jokes_html = "".join(f'<div class="joke">{j}</div>' for j in JACK_JOKES)
    mood_class = f"jack-portrait-wrap {mood}".strip()
    return f"""<div class="{mood_class}"><div class="jack-photo"><img src="{url}" alt="Jack" /></div><div class="jack-live-badge"><span class="live-dot"></span>LIVE</div></div><div class="jack-action-line"><span class="typing-dots"><span></span><span></span><span></span></span><div class="text"><strong>Jack</strong> · {action_text}</div></div><div class="jack-joke-box">{jokes_html}</div>"""
