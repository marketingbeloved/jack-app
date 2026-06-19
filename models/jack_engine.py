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
from pathlib import Path

import streamlit as st

from models.products import all_products, global_compliance


CONCEPTS_FILE = Path(__file__).resolve().parent.parent / "cache" / "concepts.json"
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


def _brand_context() -> str:
    """Pull all the brand intel Jack should know cold."""
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

    # Catalog
    try:
        from models.products import all_products, categories, global_compliance as gc_fn
        cats = categories()
        gc = gc_fn()
        parts.append(
            f"=== Catalog ===\nTotal {sum(cats.values())} SKUs: "
            f"{cats}\nGlobal compliance: {json.dumps(gc, ensure_ascii=False)}"
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

        Voice: WARM, friendly, supportive — like a close creative partner. You're Darya's right hand,
        not her boss and not a yes-machine either. You're genuinely excited about every brief, you
        celebrate wins, you cheer the team on. When pushing back on a weak angle, you do it kindly
        ("я бы попробовал ещё один заход — вот идея покруче"). You reference REAL competitor moves
        when you see them ("у Pet Honesty залетел 2nd-dog meme — давай флипнем на senior-dog?"). You
        always start with the HOOK — first 2 seconds — because if that fails nothing else matters.

        Tone in chat replies: Russian for direct dialogue with Darya (она пишет на русском). Warm,
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
        - Catalogue: 58 SKUs · 39 treats / 15 supplements / 4 sprays. I know them cold.
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
        - NEVER: cure, treat, heal, FDA approved, vet-recommended (without naming a specific vet),
                 100% safe, guaranteed, made in USA (only OK for TREATS category)
        - SAFE TO USE: supports, may help with, helps maintain, gentle daily care, natural,
                       vet-formulated, holistic, premium, lab tested

        WHAT JACK ACTUALLY DOES (practical job — SMM for 2 pet brands, BelovedPets + TOBYDIC):

        1. Open the Drive folder Darya/Tanya drops, look at the product photos,
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
           5 slides → Pinterest pin → Static "life pic" — Darya doesn't pay for 5 ideas, she
           pays for 5 surfaces of one idea.
        6. Speak two languages on purpose: Russian when instructing Dina/Vika ("показать
           крупно"), English when writing what ends up on the customer's screen.
        7. Compliance check every single line against per-SKU rules — never let "cure",
           "treat", "FDA approved", "100% safe" reach a draft. Use "supports", "may help with",
           "vet-formulated", "natural", "gentle daily care".
        8. Know the catalogue cold — when Darya says "Hemp Oil" you don't ask "which one",
           you check the catalogue, find the SKU, pull the description_short and ingredients.
           If the product isn't in the catalogue, you ASK for a mini-card and save it.
        9. Pull references from any TikTok/IG/YT link Darya drops in the chat — read title,
           views, description, then adapt the hook to Beloved Pets / Tobydic voice.
        10. Track who's doing what — Dina renders video in Higgsfield, Vika designs graphics
            in Figma, Tanya owns TOBYDIC, Darya owns BelovedPets. Briefs go to the right
            person in the right place (Notion for Dina, Sheets comment for Vika).
        11. Keep "Supplement NOT a Medicine" as the load-bearing differentiator from Pet
            Honesty (over-medical) and Zesty Paws (mass-market). Every angle reinforces this.
        12. Notice patterns in Darya's 185 past briefs — if she always opens Amazon videos
            with a packshot + benefit headline, you do the same. Don't reinvent the format.
        13. Push back politely when a brief is weak — "я бы попробовал ещё один заход — вот
            идея покруче", suggest the stronger angle, never just say "ок".

        DUAL-BRAND CONTEXT:
        - BELOVEDPETS — Darya owns it · USP "Supplement NOT a Medicine" · premium-natural ·
          58 SKUs · live: 12.3K IG followers, 41.6K reel views/month (May 2026)
        - TOBYDIC — Tanya owns it · separate brand · 4.3K IG followers, 5.8K reel views/month
          · same compliance rules apply (no medical claims), tone may differ slightly per
          Tanya's direction

        BELOVED PETS AMAZON BRAND STORES (use ONLY when Darya explicitly asks for Amazon CTA):
        - US: https://www.amazon.com/stores/BelovedPets/page/E3FFFE05-38E4-4AB3-85FF-FC461876EE18
        - UK: https://www.amazon.co.uk/stores/page/43EAEA0D-96A7-4DF8-8AD8-2487FC2E530D
        - CA: https://www.amazon.ca/stores/page/A244B1CF-768C-40FC-B06D-73E44B6F6051

        CTA RULE (одно правило от Darya, не выдумывай больше):
        - **Reels (TikTok / IG Reels)** — по умолчанию БЕЗ Amazon CTA. В TikTok товар уже привязан из TikTok Shop при заливке. Включай Amazon CTA в Reel ТОЛЬКО если Darya явно попросила («сделай с CTA на Amazon»).
        - Для остальных форматов (Amazon Product Video / Static / Carousel / IGCaption) — Darya не давала специфических правил. НЕ ВЫДУМЫВАЙ. Спрашивай если непонятно, или клади то что просили в задаче.
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
              "hashtags": ["#belovedpets", "..."],
              "first_comment": "extra hashtags for algorithm boost in first comment"
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
    """Extract JSON from Claude's output even if it wrapped in code fences."""
    if "__ERROR__" in text:
        return {"error": text}
    # Strip code fences if any
    m = re.search(r"\{[\s\S]*\}", text)
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
    system = _system_prompt() + lessons_block + examples
    out = call_claude(_user_prompt(req), system, timeout=180)
    parsed = _parse_json(out)
    if "error" in parsed:
        return [{"error": parsed["error"], "raw": parsed.get("raw", "")}]
    concepts = parsed.get("concepts", [])
    enriched = []
    for c in concepts:
        c["id"] = uuid.uuid4().hex[:8]
        c["status"] = "draft"
        c["brand"] = req.get("brand", "BelovedPets")
        enriched.append(c)
    if save:
        _save(enriched)
    return enriched


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
        brand_ctx = _brand_context()
    except Exception:
        brand_ctx = ""
    prompt = textwrap.dedent(f"""\
        Ты Джек — senior SMM-копирайтер бренда {brand} (pet supplements, рынок {market}).
        Вика прислала {len(images)} готовых слайда(ов) для карусели в Instagram. Они идут по порядку.

        Товар/тема: {product or '(определи по картинкам)'}
        Доп. пожелания от Дарьи: {extra or '(нет)'}

        Посмотри на каждый слайд и напиши ТЕКСТ для поста на чистом английском:
        1. **Overlay-текст для каждого слайда** (если на картинке уже есть текст — не дублируй, предложи что добавить/убрать; если текста нет — дай короткий текст 3-6 слов на слайд).
        2. **Caption** — нормальной средней длины, как у хороших IG pet-брендов: 2-3 строки, ~150-200 символов.
           Цепляющий хук в первой строке, 1-2 эмодзи, тёплый человеческий тон (НЕ «рекламный»), без сухого перечисления выгод.
        3. **Hashtags** — 8-12 штук, микс ниши + бренд.
        4. **First comment** — короткий CTA (1 фраза), с учётом рынка {market}.

        COMPLIANCE — строго: НЕ писать cure/treat/heal/FDA/100%25 safe/guaranteed.
        Использовать: supports, daily wellness, vet-formulated, holistic. Мы — supplement, NOT medicine.
        НЕ ВЫДУМЫВАЙ конкретику: цены, скидки (%25/Subscribe & Save), бесплатную доставку, пороги заказа,
        акции — НИЧЕГО такого, если этого нет в «пожеланиях от Дарьи» выше. Только то, что реально дано.

        Контекст бренда:
        {brand_ctx[:2500]}

        Выдай аккуратным markdown, готовым к копированию. Без вступлений.
    """)
    return gemini_vision(prompt, images, mime_types)


# ─── Captions: upload a reel video / photos → Jack writes the IG caption ────

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

    Accepts photos and/or a video. Photos are sent to vision as-is; the video is
    sampled into a few frames so Jack can 'see' the reel. Returns copy-ready markdown
    (caption + hashtags + first comment). Falls back to a text-only write if there's
    no usable visual (e.g. video frames couldn't be extracted) — using `extra` as the
    description so Jack still produces a caption instead of failing.
    """
    from models.llm import gemini_vision, smart_text
    images = list(images or [])
    mime_types = list(mime_types or ["image/jpeg"] * len(images))

    frames = _video_frames(video_bytes, video_suffix) if video_bytes else []
    vis = images + frames
    vis_mimes = mime_types + ["image/jpeg"] * len(frames)

    try:
        brand_ctx = _brand_context()
    except Exception:
        brand_ctx = ""

    what = []
    if frames:
        what.append(f"{len(frames)} кадра(ов) из готового рилса (по порядку: начало → конец)")
    if images:
        what.append(f"{len(images)} фото")
    media_line = " + ".join(what) if what else "описание словами (медиа не разобралось)"

    seen_block = (
        "Перед тобой РЕАЛЬНЫЕ кадры из рилса (по порядку начало→конец). "
        "СНАЧАЛА внимательно посмотри: что за животное, что происходит, эмоция, "
        "сеттинг, есть ли текст на экране, где появляется продукт. Подпись ОБЯЗАНА "
        "опираться на конкретный сюжет рилса, а не на общий товар."
        if vis else
        "Видео/фото разобрать не удалось — пиши по описанию ниже. Если описания мало, "
        "честно скажи об этом одной строкой в начале."
    )

    base_rules = textwrap.dedent(f"""\
        Ты Джек — креативный senior SMM-копирайтер бренда {brand} (pet supplements, рынок {market}),
        делаешь вирусные подписи на уровне топ-pet-брендов (Pet Honesty, Native Pet). Тебе дали
        ГОТОВЫЙ рилс — напиши ПОДПИСЬ (caption) под публикацию, НЕ сценарий.

        {seen_block}

        Товар/тема: {product or '(определи по кадрам)'}
        Пожелания от Дарьи: {extra or '(нет)'}

        Выдай на ЖИВОМ английском, без клише и «рекламности», строго в таком формате:

        **📹 Что в рилсе:** 1-2 предложения — что ты реально видишь на кадрах (это доказывает,
        что ты посмотрел рилс, и заземляет подписи).

        **✍️ 3 варианта подписи** — РАЗНЫЕ по длине и углу, каждый цепляет с первой строки:
        1. *Короткий* — 1 строка (до ~80 символов), хлёсткий хук / POV из рилса. Для тех, кто листает быстро.
        2. *Средний* — 2-3 строки, эмоция/история + лёгкий намёк на пользу.
        3. *Длинный* — 4-6 строк, развёрнуто: опиши сюжет рилса своими словами, вплети
           КОНКРЕТНЫЕ бенефиты и состав продукта (то, что реально известно из контекста бренда —
           напр. human-grade, few ingredients, natural), мини-storytelling, в конце мягкий вопрос/CTA.
        Везде живой хук, 1-2 эмодзи к месту, человеческий тон (НЕ «рекламный»).

        **#️⃣ Hashtags:** 10-12 штук, #belovedpets первым, микс ниши+бренд+рынок {market}.

        **💬 First comment:** короткий CTA в одну фразу (учитывай рынок {market}).

        COMPLIANCE — строго: НЕ писать cure/treat/heal/FDA/100%25 safe/guaranteed/clinically proven.
        Можно: supports, may help, daily wellness, vet-formulated, holistic. Мы — supplement, NOT medicine.
        НЕ ВЫДУМЫВАЙ цены, скидки, %25, Subscribe & Save, доставку, пороги — ничего, чего нет в пожеланиях.

        Контекст бренда (тон, продукты): {brand_ctx[:2000]}

        Чистый markdown, без вступлений вроде «вот ваша подпись». Сразу с «📹 Что в рилсе».
    """)

    if vis:
        # Flash — the model the free tier actually serves (Pro is quota-locked on free).
        return gemini_vision(base_rules, vis, vis_mimes, model="gemini-2.5-flash")
    # No visual → be honest if a video was uploaded but couldn't be read.
    out = smart_text(base_rules)
    if video_bytes and not frames:
        out = ("⚠️ Не смог раскадрировать это видео (формат/кодек) — подпись написана по "
               "описанию, не по картинке. Для точности добавь скриншот кадра в «Фото».\n\n" + out)
    return out


# ─── Vika brief: write a graphic-design ТЗ for one content-plan cell ────────

def brief_for_vika(title: str, pillar: str = "", brand: str = "BelovedPets",
                   market: str = "UK", extra: str = "", link: str = "",
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
        f"- Ссылка от Дарьи для {who} (ИСХОДНИК — фото блогера / референс): {link}"
        if link else "- Ссылка от Дарьи: (нет)"
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

            **Формат:** Reel / Video (≈N сек)
            **Концепт:** 1 фраза — что это и зачем (на русском)
            **Сцены (тайминг):**
            - 0-3 сек — что в кадре (РУС) · overlay-текст "English" · voiceover "English"
            - 3-7 сек — …
            **CTA:** финальная строка / overlay (English)
            **Бренд-стиль:** cream #FAF8F3 / sage-green #4A6B3A, тёплый натуральный тон
            **Референс / packshot:** какой файл/товар взять из Drive (назови словами)""")
    else:
        format_block = textwrap.dedent("""\
            Сначала сам пойми по теме: это статичный пост (life pic / 1 кадр) или карусель (3-6 слайдов)?
            Выбери уместный формат и напиши ТЗ КОРОТКО и по делу, как реальный коммент дизайнеру.

            Выдай ЧИСТЫЙ MARKDOWN (без вступлений, без ``` ), строго в таком виде:

            **Формат:** Static / Carousel (N слайдов)
            **Концепт:** 1 фраза — что это и зачем (на русском)
            **Layout по слайдам:**
            - Слайд 1 — что в кадре (РУС) · overlay-текст "English copy" · что выделить
            - Слайд 2 — …
            (для static — один пункт «Кадр»)
            **Текст под набор (English, готовый к типсету):** заголовок + 1-2 строки бенефита
            **Бренд-стиль:** cream #FAF8F3 / sage-green #4A6B3A, тёплый натуральный тон, светлые тона
            **Packshot / референс:** какой файл товара взять из Drive (назови словами)""")
    try:
        from models.jack_lessons import render_rules_for_prompt as _rules
        system = _system_prompt() + _rules(brand)
    except Exception:
        system = _system_prompt()
    user = textwrap.dedent(f"""\
        Напиши ТЗ для {who.upper()} ({role_desc}).
        Это коммент к ячейке контент-плана — как Дарья раньше оставляла коммент в Google-таблице.

        Ячейка контент-плана:
        - Бренд: {brand}
        - Рынок: {market}
        - Тема поста (из плана): "{title}"
        - Пиллар: {pillar or '(определи сам по теме)'}
        {link_line}
        - Доп. пожелания Дарьи: {extra or '(нет)'}

        {link_rule}

        {format_block}

        COMPLIANCE — строго: НЕ писать cure / treat / heal / FDA / 100% safe / guaranteed.
        Можно: supports, may help with, gentle daily care, natural, vet-formulated, holistic.
        Supplement, NOT medicine. НЕ выдумывай цены/скидки/акции, если их нет в пожеланиях.
    """)
    out = call_claude(user, system, timeout=150)
    if out.startswith("__ERROR__"):
        return "⚠️ " + out.replace("__ERROR__", "").strip()
    # Strip stray code fences if the model added them
    out = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", out.strip())
    return out.strip()


# ─── Notion publish (Approve → write ТЗ to Dina) ────────────────────────────

def _scenes_to_table(concept: dict) -> list[dict]:
    """Convert Jack's freeform numbered scenes into Dina's 4-column table rows.

    Returns list of {time, video, tos, voiceover}. Falls back to dumping each
    raw scene line into the 'video' column if the LLM conversion fails.
    """
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


def publish_to_notion(concept: dict, drive_url: str, listing_url: str, end_date: str | None = None) -> dict:
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

    drive_url = (drive_url or "").strip()
    listing_url = (listing_url or "").strip()
    if not drive_url or not listing_url:
        return {"error": "Нужны обе ссылки — Drive (фото товара) и listing (Amazon/Shopify)."}

    title = concept.get("title", "").strip() or "(untitled)"
    product = concept.get("product", "").strip() or concept.get("product_name", "").strip()
    market = concept.get("market", "US").strip() or "US"
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
            )
        scenes_table = _scenes_to_table(concept)
        return create_reel_brief(
            title=title, product_name=product, market=market,
            drive_url=drive_url, listing_url=listing_url, end_date=end_date,
            about=about, scenes=scenes_table, action_items=action_items, brand=brand,
        )
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Notion write failed: {e}"}
