"""Jack engine — calls Claude Code CLI to generate concept drafts.

The output schema is fixed JSON so the UI can render Kanban cards reliably.
Uses your Claude Code subscription (no Anthropic API key needed).
"""

from __future__ import annotations

import json
import subprocess
import re
import uuid
import textwrap
from datetime import date as _date
from pathlib import Path

import streamlit as st

from models.products import all_products, global_compliance


CONCEPTS_FILE = Path(__file__).resolve().parent.parent / "cache" / "concepts.json"

# Хэштегов на пост — не больше пяти (решение Марии от 2026-10-24). Промпты просят об этом
# словами, а limit_hashtags режет лишнее в коде: модель любит добавить «ещё парочку».
MAX_HASHTAGS = 5
_HASHTAG_RE = re.compile(r"(?<![\w&/])#[A-Za-z][\w]*")


def limit_hashtag_list(tags: list, n: int = MAX_HASHTAGS) -> list[str]:
    """Первые n уникальных хэштегов из списка."""
    out: list[str] = []
    for t in tags or []:
        t = str(t).strip()
        if t and t.lower() not in (x.lower() for x in out):
            out.append(t)
    return out[:n]


def limit_hashtags(text: str, n: int = MAX_HASHTAGS) -> str:
    """Оставить в тексте первые n хэштегов, остальные убрать (вместе с лишними пробелами)."""
    seen: list[str] = []

    def keep(m: re.Match) -> str:
        tag = m.group(0).lower()
        if tag in seen:
            return ""
        if len(seen) >= n:
            return ""
        seen.append(tag)
        return m.group(0)

    out = _HASHTAG_RE.sub(keep, text or "")
    out = re.sub(r"[ \t]{2,}", " ", out)
    return re.sub(r"[ \t]+$", "", out, flags=re.M)
CONCEPTS_FILE.parent.mkdir(exist_ok=True)
CORPUS_FILE = CONCEPTS_FILE.parent / "notion_briefs_corpus.json"


def _load_corpus_examples(n: int = 3, kind_hint: str = "", brand: str = "BelovedPets") -> str:
    """Pull n recent briefs from the right brand's Notion corpus as few-shot examples.

    Args:
        n: how many briefs to include
        kind_hint: optional ('amazon', 'reel', 'static', 'carousel')
        brand: 'BelovedPets' or 'Tobydic' — picks the matching corpus file
    """
    cache_dir = CONCEPTS_FILE.parent
    if brand.upper() == "TOBYDIC":
        f = cache_dir / "notion_briefs_tobydic.json"
    else:
        f = cache_dir / "notion_briefs_belovedpets.json"
    if not f.exists():
        f = CORPUS_FILE  # legacy fallback
    items = []
    if f.exists():
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            items = []
    if not items:
        # No local corpus (e.g. on Streamlit Cloud) → pull the shared copy from
        # Supabase so Tobydic / BelovedPets generation stays grounded for everyone.
        try:
            from models import shared_store
            items = shared_store.get_json(f"corpus_{brand.lower()}", []) or []
        except Exception:
            items = []
    if not items:
        return ""

    hint = kind_hint.lower()
    if hint:
        # Prefer matching titles first
        matched = [c for c in items if hint in c.get("title", "").lower()]
        other = [c for c in items if c not in matched]
        ordered = matched + other
    else:
        ordered = items

    # Prefer Done briefs (clean, finished examples)
    done = [c for c in ordered if c.get("status") == "Done"]
    pool = done if done else ordered
    picks = pool[:n]
    if not picks:
        return ""

    out = "\n\n=== DARYA'S REAL BRIEFS (use these as the canonical format, vocabulary, vibe) ===\n"
    for p in picks:
        body = p.get("body", "")[:1800]  # cap to keep prompt size sane
        out += f"\n--- Title: {p.get('title')} ---\n{body}\n"
    return out


def _load_text(path: Path, max_chars: int = 8000) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        pass
    return ""


BRAND_DATA_DIR = Path(__file__).resolve().parent.parent / "brand_data"


def _load_brand_file(fname: str, max_chars: int, home_path: Path) -> str:
    """Prefer the live local file; fall back to the bundled copy (for cloud deploy)."""
    txt = _load_text(home_path, max_chars)
    if txt:
        return txt
    return _load_text(BRAND_DATA_DIR / fname, max_chars)


def _brand_context(brand: str = "BelovedPets") -> str:
    """Pull all the brand intel Jack should know cold.

    brand нужен из-за каталога: в products.json только SKU BelovedPets, и Тане его
    подсовывать нельзя. Раньше сюда уходило лишь «Total 58 SKUs: {категории}» — самих
    названий Джек не видел, поэтому и выдумывал товары и терял вкус.
    """
    home = Path.home()
    parts = []

    brief = _load_brand_file("BP-Brand-Brief.md", 6000, home / "Databases" / "BP-Brand-Brief.md")
    if brief:
        parts.append("=== BP-Brand-Brief.md (canonical brand truth) ===\n" + brief)

    mem_dir = home / ".claude" / "projects" / "-Users-macbook-Databases" / "memory"
    for fname in ("bp-usp.md", "bp-competitors.md", "bp-notion-format.md", "bp-ig-current-style.md"):
        txt = _load_brand_file(fname, 3000, mem_dir / fname)
        if txt:
            parts.append(f"=== {fname} ===\n{txt}")

    # Live brand stats
    try:
        from models.brand_stats import fetch_report, trend, format_num
        report = fetch_report()
        bp = report.get("BELOVEDPETS", {})
        stats_lines = []
        for m in ["followers", "reach", "reel views", "post likes", "multilink cliks"]:
            l, p = trend(bp, m)
            if l is not None:
                stats_lines.append(f"  {m}: {format_num(l)}" + (f" (prev: {format_num(p)})" if p else ""))
        if stats_lines:
            parts.append("=== Latest BelovedPets numbers (May 2026) ===\n" + "\n".join(stats_lines))
    except Exception:
        pass

    # Catalog — точные названия со вкусами, а не только счётчик по категориям
    try:
        from models.products import brand_products, global_compliance as gc_fn, catalog_block, product_rule
        # Счётчик — по каталогу ЭТОГО бренда: раньше Таня видела «58 SKUs» Beloved Pets.
        gc = gc_fn()
        parts.append(
            f"=== Catalog ===\nTotal {len(brand_products(brand))} SKUs ({brand})\n"
            f"Global compliance: {json.dumps(gc, ensure_ascii=False)}\n\n"
            + catalog_block(brand) + "\n" + product_rule(brand)
        )
    except Exception:
        pass

    return "\n\n".join(parts)


def _system_prompt() -> str:
    gc = global_compliance()
    brand_ctx = _brand_context()
    return textwrap.dedent(f"""\
        You are JACK — a 28-year-old senior SMM creative director with 7+ years in pet-niche marketing
        on US/UK/CA. You've shipped 800+ reels for DTC pet brands, several hit 1M+ views. You think
        like a creative who actually scrolls TikTok 3 hours a day, not a corporate copywriter.

        Voice: WARM, friendly, supportive — like a close creative partner. You're Maria's right hand (Maria leads all content for both brands),
        not her boss and not a yes-machine either. You're genuinely excited about every brief, you
        celebrate wins, you cheer the team on. When pushing back on a weak angle, you do it kindly
        ("я бы попробовал ещё один заход — вот идея покруче"). You reference REAL competitor moves
        when you see them ("у Pet Honesty залетел 2nd-dog meme — давай флипнем на senior-dog?"). You
        always start with the HOOK — first 2 seconds — because if that fails nothing else matters.

        Tone in chat replies: Russian for direct dialogue with Maria (она пишет на русском). Warm,
        slightly emoji-friendly (🐾 ✨ 🎬), never cold or robotic. Always sign off with what comes
        next ("посмотри карточку ниже" / "если ок — апрувай, и я пушаю Дине в Notion").

        CRITICAL: Jack is a MAN. Always masculine Russian endings:
        «понял» / «готов» / «посмотрел» / «написал» / «сделал» / «отправил» / «думал».
        NEVER use feminine forms «поняла / готова / посмотрела / написала».

        BRAND CONTEXT — Beloved Pets:
        - USP: "Supplement NOT a Medicine" — clean ingredients, holistic, never claim cures
        - Competitors I watch: Pet Honesty (premium-natural · main peer), Native Pet (vet-developed
          · most science-y), Zesty Paws (mass-market · we go premium NOT them), Bark Botanica
          (adaptogens · we steal their ingredient deep-dive format), Finn (premium minimal)
        - Catalogue: ONLY Maria's product base («БАЗА ТОВАРОВ» below, per brand and market):
          names, benefits, usage, ingredients. I never use products or facts from memory.
        - Brand sells via Shopify (DTC), Amazon US/UK/CA, TikTok Shop, Chewy
        - Audience: 25-45 pet parents, premium-natural seekers, TikTok-search natives

        FORMAT RULES per platform:
        - Amazon Product Video (15-60s, target 30s): brand-hook 0-3s → problem 3-8s →
          solution 8-18s → benefits 18-26s (trust badges: Lab tested · Vet recommended ·
          HACCP · COA · GMP) → end-card with packshot + "Available on Amazon". Voiceover +
          closed captions mandatory. NO external URLs. NO competitor names. NO medical claims.
        - Reel/TikTok (15-30s): hook 0-3s, problem-reveal-transformation arc, trending sound,
          subtitles on-screen, last frame = CTA + product
        - IG Carousel (3-10 slides): slide 1 hook, slide N CTA, no walls of text

        COMPLIANCE (HARD STOPS — never use these words):
        - NEVER: cure, treat, heal, FDA approved, vet-recommended, vet-developed, vet-formulated,
                 100% safe, guaranteed, made in USA (false for every product)
        - SAFE TO USE: supports, may help with, helps maintain, gentle daily care, natural,
                       holistic, premium; "lab tested in the USA" — ONLY for TREATS
        - HASHTAGS: max 5 per post, all at the end of the caption. No extra hashtags in the
                    first comment.

        WHAT JACK ACTUALLY DOES (practical job — SMM for 2 pet brands, BelovedPets + TOBYDIC):

        1. Open the Drive folder Maria drops, look at the product photos,
           read the Amazon/Shopify listing, understand what this SKU is, who buys it,
           what's the pain it solves.
        2. Write Amazon Product Video briefs in Darya's exact Notion format —
           numbered scenes, file references in brackets, Russian instructions for the
           video creator + English captions/voiceover in quotes.
        3. Write Reel briefs (TikTok + IG Reels) — hook in first 2 seconds, problem-reveal
           -transformation arc, trending sound suggestion, on-screen captions, last frame CTA.
        4. Write static post / carousel briefs for Vika (graphic designer) — concept,
           slide-by-slide layout, English copy ready to typeset, brand colour notes,
           reference to packshot files in Drive.
        5. Repurpose one hero idea across formats: Amazon 35s → IG Reel 22s → IG Carousel
           5 slides → Pinterest pin → Static "life pic" — Maria doesn't pay for 5 ideas, she
           pays for 5 surfaces of one idea.
        6. Speak two languages on purpose: Russian when instructing Dina/Vika ("показать
           крупно"), English when writing what ends up on the customer's screen.
        7. Compliance check every single line against per-SKU rules — never let "cure",
           "treat", "FDA approved", "100% safe" reach a draft. Use "supports", "may help with",
           "natural", "gentle daily care".
        8. Know the catalogue cold — when Maria says "Hemp Oil" you don't ask "which one",
           you check the catalogue, find the SKU, pull the description_short and ingredients.
           If the product isn't in the catalogue, you ASK for a mini-card and save it.
        9. You CANNOT open links yourself — Instagram and TikTok don't serve video without a
           login. A reference reaches you already watched: either the app downloaded the reel
           and you see the video/frames (section «🎬 Похожий скрипт»), or Maria described
           it in words. NEVER invent what's inside a link you weren't shown — say you haven't
           seen it and ask for the file, screenshots or a description.
        10. Track who's doing what — Dina renders video in Higgsfield, Vika designs graphics
            in Figma, Maria leads BOTH brands (BelovedPets + TOBYDIC); executors are only Vika (graphics) and Dina (video), split ~50/50. Briefs go to the right
            person in the right place (Notion for Dina, Sheets comment for Vika).
        11. Keep "Supplement NOT a Medicine" as the load-bearing differentiator from Pet
            Honesty (over-medical) and Zesty Paws (mass-market). Every angle reinforces this.
        12. Notice patterns in Darya's 185 past briefs — if she always opens Amazon videos
            with a packshot + benefit headline, you do the same. Don't reinvent the format.
        13. Push back politely when a brief is weak — "я бы попробовал ещё один заход — вот
            идея покруче", suggest the stronger angle, never just say "ок".

        DUAL-BRAND CONTEXT:
        - BELOVEDPETS — Maria leads · USP "Supplement NOT a Medicine" · premium-natural ·
          live: 12.3K IG followers, 41.6K reel views/month (May 2026)
        - TOBYDIC — Maria leads · separate brand · 4.3K IG followers, 5.8K reel views/month
          · same compliance rules apply (no medical claims), tone may differ slightly per
          Maria's direction
        - ⛔ BRANDS NEVER MIX (Maria's rule): a TOBYDIC plan / brief / caption uses ONLY the 7
          TOBYDIC products; a BelovedPets one uses ONLY BelovedPets products. Never put a
          BelovedPets SKU (treats, chews, Relaxiv, Shreds, drops…) into TOBYDIC content and
          vice versa — even if it fits the topic. No fitting product → «вся линейка».

        BELOVED PETS AMAZON BRAND STORES (use ONLY when Maria explicitly asks for Amazon CTA):
        - US: https://www.amazon.com/stores/BelovedPets/page/E3FFFE05-38E4-4AB3-85FF-FC461876EE18
        - UK: https://www.amazon.co.uk/stores/page/43EAEA0D-96A7-4DF8-8AD8-2487FC2E530D
        - CA: https://www.amazon.ca/stores/page/A244B1CF-768C-40FC-B06D-73E44B6F6051

        CTA RULE (одно правило, не выдумывай больше):
        - **Reels (TikTok / IG Reels)** — по умолчанию БЕЗ Amazon CTA. В TikTok товар уже привязан из TikTok Shop при заливке. Включай Amazon CTA в Reel ТОЛЬКО если Мария явно попросила («сделай с CTA на Amazon»).
        - Для остальных форматов (Amazon Product Video / Static / Carousel / IGCaption) — Мария не давала специфических правил. НЕ ВЫДУМЫВАЙ. Спрашивай если непонятно, или клади то что просили в задаче.
        In the CTA scene always name the specific market: "Amazon UK", "Amazon Canada",
        "Amazon US". Drop the URL into the `links.listing_url` field of the JSON output.

        {brand_ctx}

        OUTPUT FORMAT — write briefs THE WAY DARYA WRITES THEM in Notion. Numbered scenes,
        simple human language (mix of Russian for instructions + English in quotes for on-screen
        captions). NO timing tables, NO voiceover columns — just storyboard scenes.

        Example of Darya's REAL Amazon brief (Chicken Jerky Fillet):
            1. сделать с помощью ИИ как в кадре появляется большая упаковка и из нее
               разлетаются тритсы филе, надпись снизу "Chicken Jerky Fillet for Dogs"
            2. показать крупно одну тритс и появление буллитов с benefits
            3. показать как собаки жуют тритс и подпись "support healthy teeth and gums"
            4. кадр как хозяйка тренирует собаку и подпись "what's inside?" и появляются ингредиенты
            5. текст на экране "trusted by pet parents" (фото от блогеров)
            6. more from Belovedpets и показать серию трит с похожих пачках + Amazon link

        Return STRICT JSON ONLY, no commentary, no markdown fences.
        Schema:
        {{
          "concepts": [
            {{
              "title": "short slug like 'Amazon video CHICKEN JERKY FILLET + resize reel'",
              "format": "AmazonVid|Reel|Static|Carousel|Story|IGCaption",
              "market": "US|UK|CA",
              "product": "exact SKU name from request",
              "pillar": "Amazon Video|Product Highlight|Pet Care Tip|Heartwarming|Education|Community / UGC|Meme / POV|Trend|Comedy|Faire B2B",
              "hook": "what happens in the first 2-3 seconds (Russian instruction + English on-screen text)",
              "angle": "one sentence on the creative angle and why it beats a template",
              "scenes": [
                "1. сцена на русском с инструкцией визуала + английская надпись/voiceover в кавычках",
                "2. ...",
                "3. ...",
                "4. ...",
                "5. ...",
                "6. финал — packshot + 'Available on Amazon' + Amazon listing link if known"
              ],
              "cta": "финальный CTA на экране",
              "duration_s": 30,
              "why_it_works": "one sharp sentence — reference a competitor pattern if relevant",
              "compliance_notes": "что нельзя использовать для этого SKU (cure/treat/FDA etc)",
              "links": {{
                "product_pics_drive": "Drive URL if Darya provided one",
                "listing_url": "Amazon listing URL if known"
              }},

              "// For IGCaption format ONLY — additional fields": "↓",
              "caption": "publish-ready 150-220 char caption with line breaks (only when format=IGCaption)",
              "hashtags": ["#belovedpets", "... MAX 5 hashtags total"],
              "first_comment": "short CTA, one sentence, NO hashtags"
            }}
          ]
        }}
    """)


def _user_prompt(req: dict) -> str:
    brand = req.get("brand", "BelovedPets")
    n = req.get("n", 3)
    markets = ", ".join(req.get("markets", ["UK"]))
    products = ", ".join(req.get("products", []))
    pillars = ", ".join(req.get("pillars", [])) or "mix all 5 evenly"
    context = req.get("context", "").strip()
    return textwrap.dedent(f"""\
        Brief: generate {n} viral concept seeds.

        - Brand: {brand}
        - Markets: {markets}
        - Focus products: {products}
        - Pillars wanted: {pillars}
        - Extra context: {context or '(none)'}

        Make each concept HEAD-TURNING in the first 2 seconds. Never repeat a hook —
        each concept must be a distinct angle. Use competitor patterns from research
        when they fit our voice (Pet Honesty senior-pet emotion, Bark Botanica
        ingredient deep-dives, Native Pet vet authority, ASMR pours for liquids).

        Return JSON only.
    """)


def call_claude(prompt: str, system: str, timeout: int = 120) -> str:
    """Generate text — Claude CLI locally, Gemini on cloud (via smart_text)."""
    from models.llm import smart_text
    out = smart_text(prompt, system=system, timeout=timeout)
    if out.startswith("⚠️"):
        return f"__ERROR__ {out[:300]}"
    return out


def _parse_json(text: str) -> dict:
    """Extract JSON from the model output even if wrapped in prose / code fences."""
    if "__ERROR__" in text:
        return {"error": text}
    t = (text or "").strip()
    # Снять ```json … ``` обёртку, если есть
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    # 1) Попробовать распарсить целиком
    try:
        return json.loads(t)
    except Exception:
        pass
    # 2) Выдернуть самый большой {...}-блок
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        return {"error": "no JSON in response", "raw": text[:400]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse: {e}", "raw": text[:400]}


def generate_concepts(req: dict, save: bool = True) -> list[dict]:
    """Ask Claude to generate concept seeds.

    Args:
        req: brief dict
        save: if True, persist to cache/concepts.json. If False, just return without saving.
    """
    # Build kind hint from request to pull relevant past briefs
    ctx_lower = (req.get("context", "") + " " + " ".join(req.get("pillars", []))).lower()
    hint = ""
    if "amazon" in ctx_lower:
        hint = "amazon"
    elif "reel" in ctx_lower or "tiktok" in ctx_lower:
        hint = "reel"
    elif "static" in ctx_lower or "life pic" in ctx_lower:
        hint = "life pic"
    elif "carousel" in ctx_lower:
        hint = "carousel"

    brand = req.get("brand", "BelovedPets")
    examples = _load_corpus_examples(n=3, kind_hint=hint, brand=brand)
    # Pull Darya's running corrections so Jack avoids repeating mistakes
    try:
        from models.jack_lessons import render_for_prompt as _lessons, render_rules_for_prompt as _rules
        lessons_block = _rules(brand) + _lessons(brand=brand, max_count=15)
    except Exception:
        lessons_block = ""
    try:
        from models.audience_insights import render_for_prompt as _insights
        lessons_block += _insights(brand)
    except Exception:
        pass
    system = _system_prompt() + lessons_block + examples
    out = call_claude(_user_prompt(req), system, timeout=180)
    parsed = _parse_json(out)

    # Gemini Flash нестабилен с JSON. Если ответ ПРИШЁЛ, но не распарсился —
    # повторяем один раз с жёстким требованием чистого JSON.
    llm_failed = "__ERROR__" in str(parsed.get("error", "")) or "⚠️" in str(parsed.get("error", ""))
    if "error" in parsed and not llm_failed:
        strict_sys = system + ("\n\nКРИТИЧНО: верни СТРОГО валидный JSON-объект и НИЧЕГО больше — "
                               "без текста до/после, без markdown-фенсов. Начни с '{' и закончи '}'.")
        out2 = call_claude(_user_prompt(req) + "\n\nReturn ONLY a valid JSON object — no prose, no ``` fences.",
                           strict_sys, timeout=180)
        parsed2 = _parse_json(out2)
        if "error" not in parsed2:
            parsed = parsed2
        else:
            # Спасаем контент: показываем текст Джека как скрипт (лучше, чем «no JSON»).
            raw = out2 if (out2 and "__ERROR__" not in out2) else out
            if raw and "__ERROR__" not in raw and len(raw.strip()) > 40:
                lines = [ln for ln in raw.strip().splitlines() if ln.strip()]
                return [{
                    "id": uuid.uuid4().hex[:8], "status": "draft",
                    "brand": req.get("brand", "BelovedPets"),
                    "title": "Скрипт рилса", "angle": "", "hook": "",
                    "scenes": lines, "cta": "", "why_it_works": "",
                }]
            return [{"error": parsed.get("error", "no JSON"), "raw": parsed.get("raw", "")}]

    if "error" in parsed:
        return [{"error": parsed["error"], "raw": parsed.get("raw", "")}]
    concepts = parsed.get("concepts", [])
    enriched = []
    for c in concepts:
        c["id"] = uuid.uuid4().hex[:8]
        c["status"] = "draft"
        if c.get("hashtags"):
            c["hashtags"] = limit_hashtag_list(c["hashtags"])
        if c.get("caption"):
            c["caption"] = limit_hashtags(c["caption"])
        c["brand"] = req.get("brand", "BelovedPets")
        enriched.append(c)
    if save:
        _save(enriched)
    return enriched


def generate_concepts_deep(req: dict, save: bool = False) -> list[dict]:
    """Многопроходная («вдумчивая») генерация — ответ на «нельзя написать креативный
    скрипт за 40 сек». Проход 1: Джек накидывает 4 разных угла, критикует их как
    креатив-директор и выбирает/затачивает сильнейший. Проход 2: разворачивает
    ИМЕННО этот угол в детальный посценный скрипт (через обычный структурный генератор).
    ~1.5-2 мин против ~40 сек, но заметно глубже и небанальнее."""
    brand = req.get("brand", "BelovedPets")
    base_ctx = req.get("context", "")
    markets = ", ".join(req.get("markets", ["US"]))
    try:
        from models.jack_lessons import render_for_prompt as _les, render_rules_for_prompt as _rul
        extra = _rul(brand) + _les(brand=brand, max_count=15)
    except Exception:
        extra = ""
    try:
        from models.audience_insights import render_for_prompt as _insights
        extra += _insights(brand)
    except Exception:
        pass
    system = _system_prompt() + extra + _load_corpus_examples(n=3, kind_hint="", brand=brand)

    angle_prompt = textwrap.dedent(f"""\
        Бриф: {base_ctx}
        Бренд: {brand}. Рынки: {markets}.

        Ты senior creative-директор. Сделай ТРИ шага в одном ответе (русский, без JSON, без ```):
        1) Накидай 4 РАЗНЫХ вирусных угла под этот бриф — разные механики
           (POV / образовательный / trend-jack / эмоционально-relatable / комедийный).
           Для каждого: цепляющий hook (первые 2 сек) + одной строкой почему сработает.
        2) Жёстко раскритикуй их как придирчивый креатив-директор: что шаблонно, что
           уже все делали, где слабый или предсказуемый hook.
        3) Выбери ОДИН самый сильный (или собери лучшее из нескольких) и ЗАОСТРИ его:
           финальный hook, эмоция, структура по секундам в общих чертах, чем он
           отличается от того, что уже делают Zesty Paws / Pet Honesty.
        Верни подробно ВЫБРАННЫЙ заострённый угол — дальше развернём его в полный скрипт.
    """)
    chosen = call_claude(angle_prompt, system, timeout=150)
    if not chosen or chosen.startswith("__ERROR__") or chosen.startswith("⚠️"):
        chosen = ""  # фолбэк: если первый проход не удался — просто обычная генерация

    req2 = dict(req)
    if chosen:
        req2["context"] = (
            base_ctx
            + "\n\n=== ВЫБРАННЫЙ УГОЛ (уже отобран и заострён креатив-директором — "
            "разворачивай ИМЕННО его, детально и посценно, НЕ переобобщай в шаблон) ===\n"
            + chosen
        )
    return generate_concepts(req2, save=save)


def promote_to_approve(concept: dict) -> None:
    """Save a concept from chat-session into the Approve cache."""
    if not concept:
        return
    if "id" not in concept:
        concept["id"] = uuid.uuid4().hex[:8]
    concept["status"] = "draft"
    _save([concept])


def _read_local_concepts() -> list[dict]:
    if not CONCEPTS_FILE.exists():
        return []
    try:
        return json.loads(CONCEPTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_concepts(items: list[dict]) -> None:
    """Persist the full concepts list everywhere it must live:
    the shared cloud (so Darya, Tanya and the team see the same pipeline and it
    survives Streamlit Cloud reboots) AND a local mirror (durable backup)."""
    try:
        from models import shared_store
        if shared_store.configured():
            shared_store.put_json("concepts", items)
    except Exception:
        pass
    try:
        CONCEPTS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_concepts() -> list[dict]:
    """Source of truth = shared cloud when configured (keeps Darya/Tanya/team in
    sync); otherwise the local file. Seeds the cloud from local on first run so
    nothing already drafted disappears."""
    try:
        from models import shared_store
        if shared_store.configured():
            cloud = shared_store.get_json("concepts", None)
            if cloud is None:  # no cloud row yet → seed from local once
                local = _read_local_concepts()
                if local:
                    shared_store.put_json("concepts", local)
                return local
            return cloud
    except Exception:
        pass
    return _read_local_concepts()


def _save(new_concepts: list[dict]) -> None:
    existing = load_concepts()
    # de-dup by id, prepend new
    seen = {c["id"] for c in new_concepts if "id" in c}
    keep_old = [c for c in existing if c.get("id") not in seen]
    _write_concepts(new_concepts + keep_old)


def update_status(concept_id: str, new_status: str, note: str = "") -> None:
    items = load_concepts()
    for c in items:
        if c.get("id") == concept_id:
            c["status"] = new_status
            if note:
                c["note"] = note
            break
    _write_concepts(items)


def delete_concept(concept_id: str) -> None:
    items = [c for c in load_concepts() if c.get("id") != concept_id]
    _write_concepts(items)


def set_concept_fields(concept_id: str, **fields) -> None:
    """Durably set arbitrary fields on a concept (shared cloud + local mirror).
    Used e.g. to remember that an approved reel был внесён в контент-план (plan_date)."""
    items = load_concepts()
    for c in items:
        if c.get("id") == concept_id:
            c.update(fields)
            break
    _write_concepts(items)


# ─── Vision: write text for Vika's finished carousel images ─────────────────

def text_for_carousel_images(images: list[bytes], mime_types: list[str],
                             brand: str = "BelovedPets", market: str = "US",
                             product: str = "", extra: str = "") -> str:
    """Look at Vika's finished IG carousel slides and write the post text.

    Returns ready-to-copy markdown: text per slide + caption + hashtags + 1st comment.
    """
    from models.llm import gemini_vision
    try:
        brand_ctx = _brand_context(brand)
    except Exception:
        brand_ctx = ""
    prompt = textwrap.dedent(f"""\
        Ты Джек — senior SMM-копирайтер бренда {brand} (pet supplements, рынок {market}).
        Вика прислала {len(images)} готовых слайда(ов) для карусели в Instagram. Они идут по порядку.

        Товар/тема: {product or '(определи по картинкам)'}
        Доп. пожелания от Марии: {extra or '(нет)'}

        Посмотри на каждый слайд и напиши ТЕКСТ для поста на чистом английском:
        1. **Overlay-текст для каждого слайда** (если на картинке уже есть текст — не дублируй, предложи что добавить/убрать; если текста нет — дай короткий текст 3-6 слов на слайд).
        2. **Caption** — нормальной средней длины, как у хороших IG pet-брендов: 2-3 строки, ~150-200 символов.
           Цепляющий хук в первой строке, 1-2 эмодзи, тёплый человеческий тон (НЕ «рекламный»), без сухого перечисления выгод.
        3. **Hashtags** — НЕ БОЛЬШЕ {MAX_HASHTAGS} штук на пост, микс ниши + бренд.
        4. **First comment** — короткий CTA (1 фраза), с учётом рынка {market}. Без хэштегов.

        COMPLIANCE — строго: НЕ писать cure/treat/heal/FDA/100%25 safe/guaranteed/vet-formulated/vet-developed/Made in USA.
        Использовать: supports, daily wellness, gentle daily care, holistic. Мы — supplement, NOT medicine.
        НЕ ВЫДУМЫВАЙ конкретику: цены, скидки (%25/Subscribe & Save), бесплатную доставку, пороги заказа,
        акции — НИЧЕГО такого, если этого нет в «пожеланиях от Марии» выше. Только то, что реально дано.

        Контекст бренда:
        {brand_ctx[:2500]}

        Выдай аккуратным markdown, готовым к копированию. Без вступлений.
    """)
    return limit_hashtags(gemini_vision(prompt, images, mime_types))


# ─── Captions: upload a reel video / photos → Jack writes the IG caption ────

def _video_mime(suffix: str) -> str:
    """MIME по расширению файла — Gemini принимает video/mp4|mov|webm (см. gemini_video)."""
    s = (suffix or "").lower().lstrip(".")
    return {"mov": "video/mov", "webm": "video/webm"}.get(s, "video/mp4")


def _video_frames(video_bytes: bytes, suffix: str = ".mp4", n: int = 8) -> list[bytes]:
    """Extract up to n evenly-spaced frames from a video → list of JPEG bytes.

    Uses imageio + the bundled imageio-ffmpeg binary (no system ffmpeg needed).
    Returns [] if the libraries or the file can't be read — caller degrades gracefully.
    """
    import tempfile
    import io as _io
    try:
        import imageio.v2 as imageio  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
    except Exception:
        return []
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(video_bytes)
            tmp = f.name
        reader = imageio.get_reader(tmp, "ffmpeg")
        try:
            total = reader.count_frames()
            if not total or total < 1 or total > 10_000_000:
                raise ValueError
            # n frames spread evenly across the whole reel (start → end)
            idxs = [int(total * (i + 0.5) / n) for i in range(n)]
        except Exception:
            idxs = list(range(0, n * 12, 12))  # fallback: sample across early frames
        out: list[bytes] = []
        for i in idxs:
            try:
                frame = reader.get_data(i)
            except Exception:
                continue
            buf = _io.BytesIO()
            Image.fromarray(frame).convert("RGB").save(buf, format="JPEG", quality=85)
            out.append(buf.getvalue())
        reader.close()
        return out
    except Exception:
        return []
    finally:
        if tmp:
            try:
                Path(tmp).unlink()
            except Exception:
                pass


def caption_from_media(images: list[bytes] | None = None,
                       mime_types: list[str] | None = None,
                       video_bytes: bytes | None = None,
                       video_suffix: str = ".mp4",
                       brand: str = "BelovedPets", market: str = "US",
                       product: str = "", extra: str = "") -> str:
    """Write an IG/TikTok caption for a finished reel/post from uploaded media.

    Лучший путь — отдать Gemini САМО ВИДЕО (движение, звук, тайминг текста на экране):
    раскадровка на 8 картинок теряла ровно то, из-за чего подписи звучали «мимо рилса».
    Если видео не прошло (формат/размер/перегрузка) — падаем на кадры, а если и они не
    вышли — пишем по описанию из `extra`, честно предупредив об этом.
    """
    from models.llm import gemini_video, gemini_vision, smart_text
    images = list(images or [])
    mime_types = list(mime_types or ["image/jpeg"] * len(images))

    try:
        brand_ctx = _brand_context(brand)
    except Exception:
        brand_ctx = ""

    _SEEN_VIDEO = (
        "Перед тобой САМ РИЛС — видео целиком (движение, звук, текст на экране). "
        "СНАЧАЛА посмотри его: что за животное, что происходит по ходу сюжета, эмоция, "
        "сеттинг, какой текст появляется на экране и в какой момент, где появляется "
        "продукт. Подпись ОБЯЗАНА опираться на конкретный сюжет рилса, а не на общий товар."
    )
    _SEEN_FRAMES = (
        "Перед тобой РЕАЛЬНЫЕ кадры из рилса (по порядку начало→конец). "
        "СНАЧАЛА внимательно посмотри: что за животное, что происходит, эмоция, "
        "сеттинг, есть ли текст на экране, где появляется продукт. Подпись ОБЯЗАНА "
        "опираться на конкретный сюжет рилса, а не на общий товар."
    )
    _SEEN_NONE = (
        "Видео/фото разобрать не удалось — пиши по описанию ниже. Если описания мало, "
        "честно скажи об этом одной строкой в начале."
    )

    def _rules(seen_block: str) -> str:
        return textwrap.dedent(f"""\
        Ты Джек — креативный senior SMM-копирайтер бренда {brand} (pet supplements, рынок {market}),
        делаешь вирусные подписи на уровне топ-pet-брендов (Pet Honesty, Native Pet). Тебе дали
        ГОТОВЫЙ рилс — напиши ПОДПИСЬ (caption) под публикацию, НЕ сценарий.

        {seen_block}

        Товар/тема: {product or '(определи сам по медиа)'}
        Пожелания от Марии: {extra or '(нет)'}

        ЯЗЫК — ЖЁСТКО: сами подписи, хэштеги и first comment ТОЛЬКО на английском (рынок
        {market}) — даже если пожелания Марии и этот промпт написаны по-русски. По-русски
        можно ОДИН блок — «📹 Что в рилсе» (это для Марии, а не для публикации).

        Пиши на ЖИВОМ английском, без клише и «рекламности», строго в таком формате:

        **📹 Что в рилсе:** 1-2 предложения — что ты реально видишь (это доказывает,
        что ты посмотрел рилс, и заземляет подписи).

        **✍️ 3 варианта подписи** — РАЗНЫЕ по длине и углу, каждый цепляет с первой строки:
        1. *Короткий* — 1 строка (до ~80 символов), хлёсткий хук / POV из рилса. Для тех, кто листает быстро.
        2. *Средний* — 2-3 строки, эмоция/история + лёгкий намёк на пользу.
        3. *Длинный* — 4-6 строк, развёрнуто: опиши сюжет рилса своими словами, вплети
           КОНКРЕТНЫЕ бенефиты и состав продукта (то, что реально известно из контекста бренда —
           напр. human-grade, few ingredients, natural), мини-storytelling, в конце мягкий вопрос/CTA.
        Везде живой хук, 1-2 эмодзи к месту, человеческий тон (НЕ «рекламный»).

        **#️⃣ Hashtags:** ОДИН общий блок на все варианты, НЕ БОЛЬШЕ {MAX_HASHTAGS} штук,
        фирменный хэштег бренда первым, микс ниши+бренд+рынок {market}. В самих вариантах подписи хэштегов нет.

        **💬 First comment:** короткий CTA в одну фразу (учитывай рынок {market}), без хэштегов.

        COMPLIANCE — строго: НЕ писать cure/treat/heal/FDA/100%25 safe/guaranteed/clinically proven/
        vet-formulated/vet-developed/Made in USA.
        Можно: supports, may help, daily wellness, gentle daily care, holistic. Мы — supplement, NOT medicine.
        НЕ ВЫДУМЫВАЙ цены, скидки, %25, Subscribe & Save, доставку, пороги — ничего, чего нет в пожеланиях.

        Контекст бренда (тон, продукты): {brand_ctx[:2000]}

        Чистый markdown, без вступлений вроде «вот ваша подпись». Сразу с «📹 Что в рилсе».
    """)

    # 1. Главный путь: Джек смотрит САМ РИЛС (видео + фото, если есть).
    if video_bytes:
        out = gemini_video(_rules(_SEEN_VIDEO), video_bytes, _video_mime(video_suffix),
                           images, mime_types)
        if not out.startswith("⚠️"):
            return limit_hashtags(out)

    # 2. Видео не прошло (формат/размер/перегрузка) → раскадровка, как раньше.
    frames = _video_frames(video_bytes, video_suffix) if video_bytes else []
    vis = images + frames
    vis_mimes = mime_types + ["image/jpeg"] * len(frames)
    if vis:
        out = gemini_vision(_rules(_SEEN_FRAMES if frames else _SEEN_VIDEO), vis, vis_mimes)
        if not out.startswith("⚠️"):
            if video_bytes and frames:
                out = (f"ℹ️ Само видео Gemini не взял — подпись по {len(frames)} кадрам "
                       f"(движение и звук не учтены).\n\n" + out)
            return limit_hashtags(out)

    # 3. Ни видео, ни кадров → пишем по описанию и говорим об этом честно.
    out = smart_text(_rules(_SEEN_NONE))
    if video_bytes:
        out = ("⚠️ Это видео не удалось ни отправить целиком, ни раскадрировать "
               "(формат/кодек/размер) — подпись написана по описанию, не по картинке. "
               "Для точности добавь скриншот кадра в «Фото».\n\n" + out)
    return limit_hashtags(out)


# ─── Проверка заявлений: ловим то, что нам нельзя писать ───────────────────

_FORBIDDEN = [
    r"\bcure[sd]?\b", r"\bheal(s|ed|ing)?\b", r"\bmedicine\b", r"\bmedical\b",
    r"\bFDA\b", r"\b100%\s*safe\b", r"\bguaranteed\b", r"\bclinically proven\b",
    r"\bvet[- ](developed|recommended|approved|formulated)\b",
    r"\bmade in (the )?usa\b", r"\bdiagnos(e|is|tic)\b",
    r"\bantibiotics?\b", r"\btreatments?\b", r"\binfections?\b", r"\brevolution\b",
    r"\b(made|developed|approved|tested) by (usa |german )?vet", r"\bvet[- ]approved\b",
]


def scan_claims(text: str) -> list[str]:
    """Найти запрещённые заявления в готовом ТЗ/подписи.

    Строки **Товар:** и **Референс:** пропускаем: в названиях SKU с этикетки законно
    стоят Prevention/Treatment/Medication, и проверка на них раньше давала ложную
    тревогу. Ищем по границе слова — «heal» внутри #HealthyPetsHappyLife не считается.
    """
    hits: list[str] = []
    for line in (text or "").split("\n"):
        low = line.strip().lower()
        if low.startswith(("**товар:**", "**референс:**", "**исходник:**")):
            continue
        # «supplement, NOT a medicine» — наш собственный USP, а не заявление. Убираем
        # фразу из строки, иначе проверка ругается на позиционирование бренда.
        line = re.sub(r"not\s+(a\s+)?medicine", "", line, flags=re.I)
        for pat in _FORBIDDEN:
            for m in re.finditer(pat, line, re.I):
                hits.append(m.group(0).strip())
    seen, out = set(), []
    for h in hits:
        if h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out


# ─── Приёмка ТЗ: товары из библиотеки, стиль карусели, заявления ───────────

def check_brief(text: str, brand: str = "BelovedPets") -> list[str]:
    """Собрать ВСЕ претензии к готовому ТЗ. Пустой список — ТЗ принято.

    Три проверки, каждая закрывает конкретную жалобу команды:
      • товары — Джек выдумывал SKU и не называл вкус;
      • графика — Вика получала карусели-близнецы с прыгающими плашками;
      • заявления — нам нельзя обещать лечение.
    """
    problems: list[str] = []
    try:
        from models.products import validate_products
        problems += validate_products(text, brand)
    except Exception:
        pass
    # Проверку раскладки слайдов (Layout / Плашка / Акцент) сняли 2026-11-11: Мария
    # попросила минимальные ТЗ для Вики, этих блоков в них больше нет.
    bad = scan_claims(text)
    if bad:
        problems.append("запрещённые заявления: " + ", ".join(f"«{b}»" for b in bad))
    return problems


def _retry_with_problems(user: str, system: str, out: str, problems: list[str],
                         brand: str, timeout: int = 150) -> str:
    """Один повтор с перечнем претензий. Если и он не проходит — честно пишем сверху."""
    fix = (user + "\n\nТВОЙ ПРЕДЫДУЩИЙ ВАРИАНТ ЗАБРАКОВАН. Претензии:\n"
           + "\n".join(f"- {p}" for p in problems)
           + "\n\nПерепиши ТЗ целиком, устранив КАЖДУЮ претензию. Товар бери дословно из "
             "библиотеки выше, вместе со вкусом. Ответ — только готовое ТЗ.")
    second = call_claude(fix, system, timeout=timeout)
    if second.startswith("__ERROR__"):
        return out
    second = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", second.strip())
    left = check_brief(second, brand)
    if not left:
        return second
    return ("⚠️ Проверка ТЗ: " + "; ".join(left)
            + "\n(исправь вручную — Джек не смог со второй попытки)\n\n" + second)


# ─── Референс → похожий скрипт (ссылка на чужой рилс → наше ТЗ) ────────────

def script_from_reference(url: str = "", video_bytes: bytes | None = None,
                          video_suffix: str = ".mp4", images: list[bytes] | None = None,
                          mime_types: list[str] | None = None, brand: str = "BelovedPets",
                          market: str = "US", product: str = "", extra: str = "",
                          ref_meta: dict | None = None) -> str:
    """Разобрать референс (чужой рилс) и написать НАШ похожий сценарий-ТЗ.

    Дарья и Таня кидают ссылку на понравившийся рилс — Джек смотрит его и пишет ТЗ
    в нашем формате (до 15 сек, озвучка + текст на экране в каждой сцене), под наш
    товар и наши правила. Ссылка остаётся в ТЗ, чтобы Дина могла посмотреть исходник.

    Порядок надёжности тот же, что у подписей: САМО ВИДЕО → кадры → только описание,
    и на каждом уровне мы честно говорим, что Джек реально видел.
    """
    from models.llm import gemini_video, gemini_vision, smart_text
    images = list(images or [])
    mime_types = list(mime_types or ["image/jpeg"] * len(images))
    ref_meta = ref_meta or {}

    try:
        brand_ctx = _brand_context(brand)
    except Exception:
        brand_ctx = ""
    try:
        from models.jack_lessons import render_rules_for_prompt
        team_rules = render_rules_for_prompt(brand)
    except Exception:
        team_rules = ""
    try:
        from models.products import resolve_products, catalog_block, product_rule
        found = resolve_products(product, brand=brand) if product else []
        product_block = "\n".join(
            f"- {p.get('title', '')} · {(p.get('description_short') or '')[:220]}" for p in found[:2]
        )
        catalog = catalog_block(brand) + "\n" + product_rule(brand)
    except Exception:
        product_block = ""
        catalog = ""

    ref_line = f"Ссылка на референс: {url}" if url else "Ссылка на референс: (не дали)"
    if ref_meta.get("title") or ref_meta.get("uploader"):
        ref_line += f"\nЧей рилс: {ref_meta.get('uploader', '')} · «{ref_meta.get('title', '')[:120]}»"
    if ref_meta.get("duration"):
        ref_line += f"\nДлина референса: {ref_meta['duration']} сек"

    _SEEN_VIDEO = (
        "Перед тобой САМ РЕФЕРЕНС — видео целиком (движение, звук, текст на экране). "
        "СНАЧАЛА посмотри его и разбери как креативщик: чем цепляет первые 2 секунды, "
        "как устроен сюжет по сценам, где смена ритма, какой текст появляется и когда, "
        "что говорит голос, где показывают продукт, почему это залетело."
    )
    _SEEN_FRAMES = (
        "Перед тобой КАДРЫ референса по порядку (начало→конец). Посмотри их и разбери "
        "структуру: хук, развитие, финал, какой текст на экране. Про звук и точный ритм "
        "честно скажи, что судишь по кадрам."
    )
    _SEEN_NONE = (
        "Видео референса посмотреть НЕ УДАЛОСЬ (платформа не отдала). Работай по описанию "
        "ниже и ОБЯЗАТЕЛЬНО начни ответ строкой «ℹ️ Рилс я не смотрел — сценарий по "
        "описанию». Значок именно ℹ️ — ответ, начинающийся со «⚠️», приложение считает "
        "ошибкой генерации и показывает как сбой."
    )

    def _rules(seen_block: str) -> str:
        return textwrap.dedent(f"""\
        Ты Джек — senior SMM-креативщик бренда {brand} (pet supplements, рынок {market}).
        Задача: взять ЧУЖОЙ рилс-референс и написать НАШ похожий сценарий (ТЗ для видео-креатора).

        {seen_block}

        {ref_line}
        Наш товар/тема: {product or '(выбери из каталога бренда сам, по смыслу референса)'}
        {('Что известно о товаре:' + chr(10) + product_block) if product_block else ''}
        Пожелания: {extra or '(нет)'}

        ЧТО ЗАИМСТВУЕМ: структуру, ритм, приём, тип хука, монтажную логику.
        ЧТО НЕ ЗАИМСТВУЕМ: чужой бренд, чужой товар, чужой закадровый текст дословно,
        музыку по названию. Не «перепиши их рилс», а «сделай наш по той же схеме».

        ФОРМАТ ОТВЕТА — строго так, чистый markdown, без вступлений:

        **🎬 Разбор референса:** 3-5 строк — приём, хук, структура по сценам словами,
        почему работает. ВАЖНО: в разборе НЕ пиши тайминги в виде «0-3 сек —», описывай
        словами («первые две секунды…»), иначе они попадут в таблицу видео-креатору.

        **♻️ Что переносим:** 2-3 пункта — что именно берём из референса.

        ---

        **Формат:** Reel 9:16, до 15 сек
        **Референс:** {url or '(нет)'}
        **Товар:** полное точное название нашего товара
        **Хук (0-2 сек):** что видит зритель в первые 2 секунды
        **Сцены:**
        - 0-4 сек — что в кадре и как снимать (по-русски) · на экране **"English text"** · озвучка: "English voiceover"
        - (ещё 2-3 таких строки, тайминги подряд, финал ровно на 15 сек)
        **Звук:** музыка/атмосфера коротко
        **Подпись под пост (EN):** 2-4 строки живого английского

        ЖЁСТКИЕ ПРАВИЛА (правила команды, действуют всегда):
        1. Рилс строго ДО 15 СЕКУНД, 3-4 сцены по 3-5 сек.
        2. В КАЖДОЙ сцене обязательны И текст на экране, И озвучка. Порядок блоков в строке
           менять нельзя — его разбирает код при отправке в Notion.
        3. Озвучка — разговорный английский, 8-12 слов на сцену, вся вместе читается
           как один связный голос.
        4. Снимается телефоном дома за 20-30 минут. Без студии, сплит-скринов, сложного
           монтажа и реквизита. Один кадр = одна мысль.
        5. Товар называть полностью и точно, бенефиты только реальные, из контекста бренда.
        6. COMPLIANCE: мы supplement, NOT medicine. НЕЛЬЗЯ cure/treat/heal/prevent/medicine/
           FDA/100% safe/guaranteed/Made in USA и любые «vet-» заявления (vet-developed,
           vet-recommended, vet-approved, vet-formulated) — их нам подтвердить нечем.
           Можно supports, may help, gentle daily care, natural, holistic.
        7. Товар: пиши про заданный. Если в референсе показан ДРУГОЙ наш товар и по смыслу
           он уместнее — можно взять его, но скажи об этом одной строкой в разборе.

        Контекст бренда: {brand_ctx[:1800]}
        {catalog}
        {('ПОСТОЯННЫЕ ИНСТРУКЦИИ КОМАНДЫ:' + chr(10) + team_rules[:2500]) if team_rules else ''}
    """)

    def _accept(out: str) -> str:
        """Приёмка: товар из библиотеки со вкусом + заявления. Один повтор текстом.

        Повтор идёт через текстовую модель, а не через повторный просмотр видео —
        разбор уже сделан, переписать надо только ТЗ.
        """
        problems = check_brief(out, brand)
        if not problems:
            return _with_link(out, brand)
        fix = ("Вот ТЗ, которое ты написал:\n\n" + out + "\n\nОно забраковано. Претензии:\n"
               + "\n".join(f"- {p}" for p in problems)
               + "\n\n" + catalog + "\n\nПерепиши ТЗ целиком, устранив КАЖДУЮ претензию. "
               "Структуру и разбор референса сохрани. Ответ — только готовое ТЗ.")
        second = smart_text(fix)
        if second.startswith("⚠️"):
            return out
        if not check_brief(second, brand):
            return _with_link(second, brand)
        return ("⚠️ Проверка ТЗ: " + "; ".join(check_brief(second, brand))
                + "\n(поправь вручную)\n\n" + second)

    # 1. Главный путь — Джек смотрит сам референс.
    if video_bytes:
        out = gemini_video(_rules(_SEEN_VIDEO), video_bytes, _video_mime(video_suffix),
                           images, mime_types)
        if not out.startswith("⚠️"):
            return _accept(out)

    # 2. Видео не прошло → кадры (свои скриншоты Дарьи или раскадровка).
    frames = _video_frames(video_bytes, video_suffix) if video_bytes else []
    vis = images + frames
    vis_mimes = mime_types + ["image/jpeg"] * len(frames)
    if vis:
        out = gemini_vision(_rules(_SEEN_FRAMES), vis, vis_mimes)
        if not out.startswith("⚠️"):
            out = _accept(out)
            if video_bytes and frames:
                out = ("ℹ️ Само видео Gemini не взял — разбор по "
                       f"{len(frames)} кадрам (звук и точный ритм не учтены).\n\n" + out)
            return out

    # 3. Ни видео, ни кадров — только описание, и мы это честно помечаем.
    out = smart_text(_rules(_SEEN_NONE))
    return out if out.startswith("⚠️") else _accept(out)


# ─── Vika brief: write a graphic-design ТЗ for one content-plan cell ────────

def brief_for_vika(title: str, pillar: str = "", brand: str = "BelovedPets",
                   market: str = "", extra: str = "", link: str = "",
                   for_name: str = "Вика", for_role: str = "graphics") -> str:
    """Write a ready-to-read ТЗ for ONE plan cell, addressed to the chosen executor.

    for_name / for_role follow the «👤 Исполнитель» selector in the cell:
    - graphics (Вика) → static post / carousel layout brief (slides + typeset copy).
    - video    (Дина) → short video brief (numbered scenes + timing + voiceover).

    link: optional Drive/photo link Darya gives (e.g. blogger photo for «фото от блогера»).
    When present, Jack must reference it in the ТЗ as the source asset.
    """
    link = (link or "").strip()
    who = (for_name or "Вика").strip()
    is_video = "video" in (for_role or "").lower() or "видео" in (for_role or "").lower()
    role_desc = (
        "видео-креатор (делает рилсы/короткие видео; на «фото от блогера» — оформляет фото-пост)"
        if is_video else
        "графдизайнер (делает статичные посты / карусели в Figma для Instagram)"
    )
    link_line = (
        f"- Ссылка от Марии для {who} (ИСХОДНИК — фото блогера / референс): {link}"
        if link else "- Ссылка от Марии: (нет)"
    )
    link_rule = (
        f"В ТЗ ОБЯЗАТЕЛЬНО укажи эту ссылку отдельной строкой как исходник, который {who} "
        "берёт для поста (например для «фото от блогера» — это фото блогера для ленты). "
        "Напиши прямо: «Исходник (фото блогера): <ссылка>»."
        if link else ""
    )
    if is_video:
        format_block = textwrap.dedent("""\
            Выдай ЧИСТЫЙ MARKDOWN (без вступлений, без ``` ), строго в таком виде:

            **Формат:** Reel, до 15 сек (или Анимация фото)
            **Товар:** название из базы целиком (с вкусом и размером) · ASIN · ссылка
            **Идея:** 1 фраза по-русски
            **Хук (0-2 сек):** "English"
            **Сцены:**
            - 0-4 сек — что в кадре (РУС, коротко) · на экране "English" · озвучка "English"
            - (ещё 1-3 строки, тайминги подряд, финал не позже 15 сек)
            **Подпись под пост (EN):** 2-4 строки

            Больше НИЧЕГО. Айдентика, шрифты, цвета, пропорции кадра, стиль субтитров и
            логотип Дине уже известны — про них не пиши. Без советов по свету, съёмке,
            монтажу и звуку, без вступлений и примечаний. Озвучку в сцене можно пропустить.
            Порядок блоков в строке сцены менять нельзя — его разбирает код при отправке в Notion.""")
    else:
        format_block = textwrap.dedent("""\
            ТЗ дизайнеру МИНИМАЛЬНОЕ — ровно 4 блока, больше ничего.
            Выдай ЧИСТЫЙ MARKDOWN (без вступлений, без ``` ), строго в таком виде:

            **Вид креатива:** фото от блогера / статичный пост / карусель N экранов / промо
            **Товар:** название из базы целиком (с вкусом и размером) · ASIN · ссылка
            **Надпись на креативе:** текст на английском. Для карусели — по строке на экран:
              1: "..."
              2: "..."
            **Подпись для поста (EN):** 2-4 строки + CTA

            НЕ пиши: концепт, композицию, холст и размеры, поля, цвета и HEX, плашки, шрифты,
            packshot, описание кадра. Айдентику и пропорции Вика знает.""")
    try:
        from models.jack_lessons import render_rules_for_prompt as _rules
        system = _system_prompt() + _rules(brand)
    except Exception:
        system = _system_prompt()
    # Библиотека товаров и правило про вкус — в КАЖДОЕ ТЗ, это главная причина брака.
    try:
        from models.products import catalog_block, product_rule
        mk = (market or "US").upper() if (market or "").upper() in ("US", "UK", "CA") else "US"
        system += "\n\n" + catalog_block(brand, market=mk) + "\n" + product_rule(brand)
        from models.products import resolve_products, product_facts, find_exact
        named = [p["title"] for p in resolve_products(f"{title} {extra}", limit=2, brand=brand)]
        facts = [product_facts(n, brand, mk) for n in named]
        if any(facts):
            system += "\n" + "\n".join(f for f in facts if f)
    except Exception:
        pass
    # Визуальную систему (холст, HEX, плашки) больше не подкладываем: решение Марии
    # 2026-11-11 — ТЗ Вике минимальное, айдентику она знает.
    user =textwrap.dedent(f"""\
        Напиши ТЗ для {who.upper()} ({role_desc}).
        Это коммент к ячейке контент-плана — как раньше оставляли коммент в Google-таблице.

        Ячейка контент-плана:
        - Бренд: {brand}
        - Рынок: {market or 'НЕ УКАЗАН — не выдумывай и не пиши рынок в ТЗ вообще'}
        - Тема поста (из плана): "{title}"
        - Пиллар: {pillar or '(определи сам по теме)'}
        {link_line}
        - Доп. пожелания Марии: {extra or '(нет)'}

        {link_rule}

        {format_block}

        COMPLIANCE — строго: НЕ писать cure / treat / heal / prevent / FDA / 100% safe /
        guaranteed и любые «vet-» заявления (vet-developed, vet-recommended, vet-formulated) —
        подтвердить их нечем. Можно: supports, may help with, gentle daily care, natural,
        holistic. Supplement, NOT medicine.
        НЕ выдумывай цены/скидки/акции, если их нет в пожеланиях.
        ТОВАР и факты о нём — только из базы, название дословно. Выдуманное = брак ТЗ.
    """)
    out = call_claude(user, system, timeout=150)
    if out.startswith("__ERROR__"):
        return "⚠️ " + out.replace("__ERROR__", "").strip()
    # Strip stray code fences if the model added them
    out = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", out.strip())
    out = out.strip()
    # Приёмка: товар из библиотеки со вкусом, стиль карусели, заявления. Один повтор.
    problems = check_brief(out, brand)
    if problems:
        out = _retry_with_problems(user, system, out, problems, brand)
    return _with_link(out, brand, market)


def _with_link(text: str, brand: str, market: str | None = None) -> str:
    """Ссылка на листинг Amazon к товару в ТЗ (решение Марии 2026-11-11)."""
    try:
        from models.products import attach_link
        mk = (market or "").upper()
        return attach_link(text, brand, mk if mk in ("US", "UK", "CA") else None)
    except Exception:
        return text


# ─── Threads — готовый текст поста, а не ТЗ ─────────────────────────────────
# Threads — канал узнаваемости (решение Марии, 2026-11-03): ни товаров, ни цен, ни
# ссылок на магазин. Путь Threads → Instagram → Shopify, продаёт уже Instagram.
THREADS_PART_LIMIT = 500

_SELLING = (r"\bshop now\b", r"\bbuy\b", r"\bdiscount", r"\bsale\b", r"\bpromo",
            r"\$\d", r"%\s*off", r"link in bio", r"amazon", r"chewy", r"tiktok shop",
            r"shopify", r"belovedpets\.com", r"subscribe\s*&\s*save")


def check_threads_post(text: str) -> list[str]:
    """Претензии к тексту для Threads: заявления, продажа, части длиннее 500 знаков."""
    problems: list[str] = []
    bad = scan_claims(text)
    if bad:
        problems.append("запрещённые заявления: " + ", ".join(f"«{b}»" for b in bad))
    sell = sorted({m.group(0) for p in _SELLING for m in re.finditer(p, text or "", re.I)})
    if sell:
        problems.append("продающие слова (в Threads нельзя): " + ", ".join(f"«{s}»" for s in sell))
    for i, part in enumerate(re.split(r"^\s*—\s*$", text or "", flags=re.M), 1):
        if len(part.strip()) > THREADS_PART_LIMIT:
            problems.append(f"часть {i} длиннее {THREADS_PART_LIMIT} знаков ({len(part.strip())})")
    return problems


def threads_post(title: str, pillar: str = "", brand: str = "BelovedPets", extra: str = "") -> str:
    """Текст одного поста для Threads по теме из календаря (EN, готов к публикации)."""
    system = _system_prompt()
    try:
        from models.jack_lessons import render_rules_for_prompt as _rules
        system += _rules(brand)
    except Exception:
        pass
    try:
        from models.audience_insights import render_for_prompt as _insights
        system += _insights(brand)
    except Exception:
        pass
    if brand.upper() == "TOBYDIC":
        account = ("TOBYDIC (Instagram @tobydic_brand_). Голос: тёплый, честный — «herbal isn't instant "
                   "magic», заботливый, но не врач. Две линии: приюты и adoption + ежедневная забота")
    else:
        account = "@beloved_pets_brand"
    user = textwrap.dedent(f"""\
        Напиши ГОТОВЫЙ текст поста для Threads {account} (рынок US).

        Тема из календаря: "{title}"
        Рубрика: {pillar or '(определи сам по теме)'}
        Пожелания: {extra or '(нет)'}

        ПРАВИЛА THREADS:
        - Только вовлечение и узнаваемость. НИКАКИХ товаров, цен, скидок, ссылок на магазин,
          Amazon, Shopify, «link in bio». Продаёт Instagram, не Threads.
        - Тон: тёплый, как друг; сначала эмпатия; реальная польза; без CAPS, кликбейта, запугивания.
        - Пост заканчивается вопросом или просьбой ответить (фото, слово, опыт).
        - Если тема — ветка 🧵: части разделяй строкой с одним символом «—». Каждая часть ≤ {THREADS_PART_LIMIT} знаков.
        - Симптомы — одна строка «call your vet», без советов по лечению.
        - Можно мостик в Instagram: «the best ones go on our Instagram» — без ссылок.
        - Запрещено: cure / treat / heal / relief / prevent / UTI / infection / anti-anxiety /
          FDA / 100% safe / guaranteed / clinically proven / vet-developed / Made in USA /
          dewormer / anti-parasitic / kidney.

        Выдай только текст поста на английском (без кавычек, без вступлений, без ``` ).
        Последней строкой на русском: «Тег: Dogs of Threads / Cats of Threads / Pet Parents / Rescue Pets» — один, по теме.
    """)
    out = call_claude(user, system, timeout=120)
    if out.startswith("__ERROR__"):
        return "⚠️ " + out.replace("__ERROR__", "").strip()
    out = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", out.strip()).strip()
    problems = check_threads_post(out)
    if problems:
        fix = (user + "\n\nПРЕДЫДУЩИЙ ВАРИАНТ ЗАБРАКОВАН:\n" + "\n".join(f"- {p}" for p in problems)
               + "\n\nПерепиши пост целиком без этих ошибок.\n\nПредыдущий вариант:\n" + out)
        second = call_claude(fix, system, timeout=120)
        if not second.startswith("__ERROR__"):
            second = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", second.strip()).strip()
            left = check_threads_post(second)
            out = second if not left else (
                "⚠️ Проверка: " + "; ".join(left) + "\n(исправь вручную)\n\n" + second)
    return out


# ─── Notion publish (Approve → write ТЗ to Dina) ────────────────────────────

def _scenes_to_table(concept: dict) -> list[dict]:
    """Convert Jack's freeform numbered scenes into Dina's 4-column table rows.

    Returns list of {time, video, tos, voiceover}. Falls back to dumping each
    raw scene line into the 'video' column if the LLM conversion fails.
    """
    # Пост плана приносит уже разобранную таблицу — модель тут только портила: вместо
    # содержания сцены возвращала ярлыки, и Дина получала пустые колонки.
    ready = concept.get("scene_rows")
    if ready and isinstance(ready, list):
        return [{"time": str(r.get("time", "")), "video": str(r.get("video", "")),
                 "tos": str(r.get("tos", "")), "voiceover": str(r.get("voiceover", ""))}
                for r in ready if isinstance(r, dict)]
    scenes = concept.get("scenes") or []
    if not scenes:
        return []
    raw = "\n".join(scenes)
    system = (
        "You convert a storyboard into Darya's exact Notion 4-column scene table for the "
        "video creator Dina. Output JSON only: {\"rows\":[{\"time\":\"\",\"video\":\"\",\"tos\":\"\",\"voiceover\":\"\"}]}. "
        "Columns: time = тайминг (e.g. '0-3 сек'); video = видеоряд, инструкция для монтажа НА РУССКОМ; "
        "tos = текст на экране (on-screen text) на английском как в ролике; voiceover = озвучка на английском. "
        "Keep the same scenes and order. Don't invent new scenes. If a field is absent leave it \"\"."
    )
    out = call_claude(f"Storyboard:\n{raw}\n\nReturn the JSON table.", system, timeout=120)
    parsed = _parse_json(out)
    rows = parsed.get("rows") if isinstance(parsed, dict) else None
    if rows and isinstance(rows, list):
        clean = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            clean.append({
                "time": str(r.get("time", "")),
                "video": str(r.get("video", "")),
                "tos": str(r.get("tos", "")),
                "voiceover": str(r.get("voiceover", "")),
            })
        if clean:
            return clean
    # Fallback — keep the raw lines so Dina still gets the script
    return [{"time": "", "video": s, "tos": "", "voiceover": ""} for s in scenes]


def publish_to_notion(concept: dict, drive_url: str, listing_url: str, end_date: str | None = None,
                      update_url: str = "") -> dict:
    """Create a brief page for Dina in the Notion Videos DB from an approved concept.

    Title = concept title (как в КП), date = end_date, scenes copied as a 4-column
    table, drive + listing links attached. Returns {"url": ...} or {"error": ...}.
    """
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from jack_notion import create_reel_brief, create_static_brief
    except Exception as e:  # noqa: BLE001
        return {"error": f"Notion module not importable: {e}"}

    # Ссылки НЕ обязательны — Дина берёт материалы с общего Диска сама.
    drive_url = (drive_url or "").strip()
    listing_url = (listing_url or "").strip()

    title = concept.get("title", "").strip() or "(untitled)"
    product = concept.get("product", "").strip() or concept.get("product_name", "").strip()
    # Рынка может не быть вовсе — тогда его просто не будет на странице у Дины.
    market = (concept.get("market") or "").strip()
    brand = concept.get("brand", "BelovedPets")
    about_bits = [b for b in [concept.get("hook", ""), concept.get("angle", "")] if b]
    about = " — ".join(about_bits)
    cta = concept.get("cta", "")
    action_items = [f"CTA: {cta}"] if cta else [""]

    fmt = (concept.get("format") or "").lower()
    is_static = fmt in ("static", "carousel", "igcaption")

    try:
        if is_static:
            return create_static_brief(
                title=title, product_name=product, market=market,
                drive_url=drive_url, listing_url=listing_url, end_date=end_date,
                about=about, action_items=action_items, brand=brand,
                body=concept.get("brief_text", ""), update_url=update_url,
            )
        scenes_table = _scenes_to_table(concept)
        return create_reel_brief(
            title=title, product_name=product, market=market,
            drive_url=drive_url, listing_url=listing_url, end_date=end_date,
            about=about, scenes=scenes_table, action_items=action_items, brand=brand,
            update_url=update_url,
        )
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Notion write failed: {e}"}


def autopush_to_notion(concept: dict, end_date: str | None = None) -> dict:
    """Оформить ТЗ Дине в Notion автоматически. Ссылки НЕ обязательны — если они
    есть у концепта, прикрепим; нет — Дина берёт материалы с Диска сама.
    Сохраняет notion_url на концепте при успехе, чтобы не запушить дважды.

    Возвращает:
      {"url": ...}         — оформил ТЗ в Notion прямо сейчас
      {"skipped": "..."}   — уже в Notion (не ошибка)
      {"error": ...}       — Notion write не удался (напр. нет NOTION_TOKEN в secrets)
    """
    if not concept:
        return {"skipped": "нет концепта"}
    if concept.get("notion_url"):
        return {"skipped": "уже в Notion"}
    links = concept.get("links") or {}
    drive = str(links.get("product_pics_drive", "")).strip()
    listing = str(links.get("listing_url", "")).strip()
    # Дата обязательна: без неё Notion создаёт страницу без срока, и Дина не понимает,
    # к какому числу снимать. Вызовы отсюда её раньше не передавали вовсе — берём с
    # концепта, а если и там нет, ставим сегодня, но НЕ оставляем пустой.
    if not end_date:
        end_date = (str(concept.get("air_date") or concept.get("date") or "").strip()
                    or _date.today().isoformat())
    res = publish_to_notion(concept, drive, listing, end_date)
    if res and res.get("url"):
        set_concept_fields(concept["id"], notion_url=res["url"])
    return res
