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


def chat_system_prompt(brand: str = "BelovedPets") -> str:
    brand_ctx = _brand_context()
    try:
        from models.jack_lessons import render_rules_for_prompt
        rules = render_rules_for_prompt(brand)
    except Exception:
        rules = ""
    base = textwrap.dedent(f"""\
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
        - КОММИТЬСЯ БЫСТРО. Задай МАКСИМУМ ОДИН уточняющий вопрос за весь диалог,
          и только если реально не понятна тема. Как только знаешь ТЕМУ (товар или
          «весь shop» и т.п.) — ВСЁ, хватит уточнять. Длину, вайб, рынок (если не
          сказан — бери US), формат выбери САМ по практике. Лучше написать и дать
          ей переделать, чем доспрашивать. НЕ задавай второй/третий вопрос.
        - Как только готов писать — ОБЯЗАТЕЛЬНО закончи сообщение фразой
          «понял, иду писать» (буквально эти слова) — это запускает генератор.
          Если уже был один твой вопрос в диалоге — на следующем сообщении НЕ
          спрашивай снова, а пиши «понял, иду писать».
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
    return base + rules


def jack_chat_reply(messages: list[dict], current_input: str, refs: str = "", brand: str = "BelovedPets") -> str:
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
    out = smart_text(prompt, system=chat_system_prompt(brand), timeout=90)
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
    Сначала быстрые англ. ключевые слова, затем резолвер каталога (рус/англ):
    «салфетки», «успокоительное» и т.п. → товар из библиотеки, Джек не переспрашивает.
    """
    if any(p in text.lower() for p in PRODUCT_KEYWORDS):
        return True
    try:
        from models.products import resolve_products
        return bool(resolve_products(text))
    except Exception:
        return False


# Brief types that legitimately have NO product/SKU — don't ask «по какому товару?».
B2B_SIGNALS = [
    "faire", "фейр", "ритейлер", "retailer", "b2b", "оптов", "wholesale",
    "приглашени", "invite", "дистрибьютор", "distributor", "магазин", "stockist",
    "fb group", "facebook group", "фб групп", "сообществ", "подписчик", "follow",
    # «про весь магазин / витрину / ассортимент» — конкретного SKU нет, не спрашиваем товар
    "тт шоп", "tt шоп", "tiktok shop", "tt shop", "тикток шоп", "весь шоп", "весь магазин",
    "витрин", "storefront", "ассортимент", "линейк", "бренд в целом", "о бренде", "про бренд",
]


def brief_needs_no_product(text: str) -> bool:
    """True for briefs that don't revolve around a SKU (Faire/B2B invites, community
    /follow asks, etc.) — so Jack generates instead of demanding a product."""
    return any(s in text.lower() for s in B2B_SIGNALS)


def looks_like_full_brief(text: str) -> bool:
    """Heuristic: does the message look like a brief ready to generate?

    Triggers brief mode if:
    - A write-verb + a content-noun appear ("напиши скрипт", "написать сценарий",
      "сделай пост", "придумай тз") — in ANY word order / verb form
    - OR phrase patterns like "скрипт про/для/на", "контент про"
    - OR enough detail signals (≥3 of: product / market / format / duration)
    """
    t = text.lower()

    # Write-verb (любая форма: напиши/написать/напишешь…) + content-noun anywhere.
    write_verbs = ["напиш", "написа", "сдела", "придума", "набросай", "набросать",
                   "сочини", "сгенери", "состав", "оформи"]
    content_nouns = ["скрипт", "сценари", "тз", "пост", "caption", "подпис", "текст",
                     "питч", "pitch", "концепт", "рилс", "reel", "видео", "карусел"]
    has_verb = any(v in t for v in write_verbs)
    has_noun = any(n in t for n in content_nouns)
    if has_verb and has_noun:
        return True

    # Phrase patterns even без явного глагола рядом.
    action_triggers = [
        "тз для", "тз на", "тз по", "скрипт для", "скрипт на", "скрипт про", "скрипт по",
        "сценарий для", "сценарий про", "идея для", "концепт для",
        "контент про", "контент для", "пост про", "питч для", "pitch for",
    ]
    if any(trig in t for trig in action_triggers):
        return True

    has_product = brief_has_product(t)
    has_market = any(m in t for m in ["us", "uk", "ca", "usa", "сша", "великобритан", "канад"])
    has_format = any(f in t for f in ["amazon", "reel", "static", "carousel", "tiktok", "видео", "пост", "caption", "подпись", "текст для"])
    has_duration = "сек" in t or "s" in t and any(c.isdigit() for c in t)
    score = sum([has_product, has_market, has_format, has_duration])
    return score >= 3
