"""Jack conversational reply — human-style chat replies instead of JSON briefs.

Use when Darya is discussing/clarifying, not when she's giving a full brief ready
to generate a concept. The chat builds context from past messages and Jack's
brand knowledge so he sounds like a real teammate, not a chatbot.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from models.jack_engine import _brand_context, _load_corpus_examples


def chat_system_prompt() -> str:
    brand_ctx = _brand_context()
    return textwrap.dedent(f"""\
        You are JACK — 28, senior SMM creative for Beloved Pets and Tobydic.
        You're chatting with Darya in Telegram-style: short, warm, human.

        HOW YOU REPLY:
        - 1–4 short sentences max per message — like a real chat with a colleague.
        - Russian, since Darya writes in Russian. English only inside quotes
          for on-screen captions / voiceover lines.
        - JACK IS A MAN. Always refer to yourself in masculine Russian:
          «понял» not «поняла», «готов» not «готова», «посмотрел» not «посмотрела»,
          «написал» not «написала», «сделал» not «сделала», «думал» not «думала»,
          «отправил» not «отправила». NEVER use feminine verb endings.
        - Ask ONE clarifying question at a time when you need detail. Don't dump
          a 5-question form.
        - When she gives a clear brief — just say "понял, иду писать" and let
          the brief generator do its thing.
        - Reference real competitor moves naturally ("у Pet Honesty залетел
          формат, давай попробуем флипнуть").
        - Push back on weak angles politely with a stronger alternative.
        - Celebrate small wins, give encouragement. You're a creative partner.
        - Never output JSON in chat. Never use markdown headers (###). Use
          plain text. Light bold (**word**) is okay sparingly.

        TONE EXAMPLES (this is how you sound):
        - "Окей, понял. А рынок US или UK? И есть фотки товара?"
        - "Я бы тут зашёл с POV-формата — у Pet Honesty похожий зашёл на 780K."
        - "Готово, набросал в карточке ниже. Глянь, если что — переделаю."
        - "Хмм, этот хук уже был у нас в апреле. Давай попробуем угол через
          ингредиенты — типа adaptogen-deep-dive как у Bark Botanica?"
        - "Можно я уточню — это для Amazon или для соцсетей? У меня разные
          форматы получаются."

        {brand_ctx}
    """)


def jack_chat_reply(messages: list[dict], current_input: str, refs: str = "") -> str:
    """Generate a conversational reply from Jack.

    Args:
        messages: prior chat history [{"who": "darya|jack|tanya", "text": "..."}]
        current_input: the message Darya just sent
        refs: parsed reference snippets from URLs in current_input (optional)
    """
    history = ""
    for m in messages[-10:]:  # last 10 messages for context, no need for more
        who = m.get("who", "?")
        label = "Darya" if who == "darya" else ("Tanya" if who == "tanya" else "Jack")
        history += f"\n{label}: {m.get('text','')}"

    prompt = textwrap.dedent(f"""\
        Recent chat:
        {history}

        Darya just wrote:
        {current_input}

        {f'Links Darya provided (parsed):{chr(10)}{refs}' if refs else ''}

        Reply as Jack — short, warm, human Russian message. Ask a clarifying
        question if you need it. If she's given a complete brief (product +
        market + duration + benefit), just say "понял, иду писать" — the
        full brief generator runs separately.
    """)

    from models.llm import smart_text
    out = smart_text(prompt, system=chat_system_prompt(), timeout=90)
    if out.startswith("⚠️"):
        return f"(Jack offline · {out[:120]})"
    return out


PRODUCT_KEYWORDS = [
    "eye wash", "eye wipe", "calming", "hemp oil", "yeast", "uti", "flea", "tick",
    "treats", "chews", "spray", "probiotic", "intestinal", "scratch",
    "jerky", "tuna", "chicken", "duck", "sweet potato", "herbiotic", "dewo",
]


def brief_has_product(text: str) -> bool:
    """True if the message names a concrete product Jack can build a brief around.

    Used to stop Jack from guessing a SKU on a vague brief like «сделай про сон».
    """
    return any(p in text.lower() for p in PRODUCT_KEYWORDS)


def looks_like_full_brief(text: str) -> bool:
    """Heuristic: does the message look like a brief ready to generate?

    Triggers brief mode if:
    - Action words present ("напиши ТЗ", "сделай", "придумай") — even if vague
    - OR enough detail signals (≥3 of: product / market / format / duration)
    """
    t = text.lower()

    # Strong action words — go straight to brief generation
    action_triggers = [
        "напиши тз", "напиши скрипт", "напиши пост", "напиши caption", "напиши текст",
        "сделай тз", "сделай скрипт", "сделай пост", "сделай для",
        "придумай тз", "придумай скрипт", "придумай идею",
        "тз для", "тз на", "скрипт для", "скрипт на",
        "идея для", "концепт для", "контент про", "контент для",
    ]
    if any(trig in t for trig in action_triggers):
        return True

    has_product = brief_has_product(t)
    has_market = any(m in t for m in ["us", "uk", "ca", "usa", "сша", "великобритан", "канад"])
    has_format = any(f in t for f in ["amazon", "reel", "static", "carousel", "tiktok", "видео", "пост", "caption", "подпись", "текст для"])
    has_duration = "сек" in t or "s" in t and any(c.isdigit() for c in t)
    score = sum([has_product, has_market, has_format, has_duration])
    return score >= 3
