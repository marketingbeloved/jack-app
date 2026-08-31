"""Jack writes a whole month of content plan from the previous months' evidence.

Two-stage on purpose. One giant call for ~22 posts with full scripts gets truncated and
the tail turns to mush, so:
  1. `month_strategy()` — one small call: what the month is about, which formats to push
     or drop, which mistakes from last month not to repeat. Cheap, reviewable.
  2. `generate_week()` — one call per week, ~5 posts with hook + ready script. Short
     enough to come back complete, and each call sees the titles already generated so
     weeks don't repeat each other.

The calendar skeleton (which dates exist, which slot is the weekly blogger photo) is built
in code, not asked of the model — dates are the one thing an LLM reliably gets wrong.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, timedelta

from models.jack_engine import _parse_json, _system_prompt, call_claude

WEEKDAY_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

# The structure Darya fixed: one blogger photo a week (Vika), the rest split between
# carousels, animations and reels of varying formats (Dina).
FORMAT_MIX = ["carousel", "animation", "reel", "lifestyle"]

_ALLOWED_TYPES = {"engaging", "selling", "viral", "neutral"}
_ALLOWED_FORMATS = {"blogger_photo", "carousel", "animation", "reel", "lifestyle", "promo"}


def owners_from_history(analysis: dict) -> tuple[str, str]:
    """Who does the blogger photo, and who does everything else — read off past months.

    Hardcoding Vika and Dina would break the moment Tanya generates a month for TOBYDIC,
    where the weekly photo is hers. Falls back to the BelovedPets pair when a brand has
    no history to learn from.
    """
    photo_counts = {k: v for k, v in (analysis.get("blogger_photo", {}).get("owners") or {}).items()
                    if k and k != "—"}
    rest_counts = {k: v for k, v in (analysis.get("by_owner") or {}).items()
                   if k and k != "—" and k not in photo_counts}
    if not rest_counts:  # everyone shares the same slot type — fall back to all owners
        rest_counts = {k: v for k, v in (analysis.get("by_owner") or {}).items()
                       if k and k != "—"}
    photo = max(photo_counts, key=photo_counts.get) if photo_counts else "vika"
    video = max(rest_counts, key=rest_counts.get) if rest_counts else "dina"
    return photo, video


def month_skeleton(year: int, month: int, *,
                   weekdays_only: bool = True,
                   photo_owner: str = "vika",
                   video_owner: str = "dina") -> list[list[dict]]:
    """Weeks of empty slots for the month. Monday of each week is the blogger-photo slot."""
    last = calendar.monthrange(year, month)[1]
    days = [date(year, month, d) for d in range(1, last + 1)]
    if weekdays_only:
        days = [d for d in days if d.weekday() < 5]

    weeks: list[list[dict]] = []
    current: list[dict] = []
    current_week_no = days[0].isocalendar()[1] if days else 0
    for d in days:
        wk = d.isocalendar()[1]
        if wk != current_week_no and current:
            weeks.append(current)
            current = []
            current_week_no = wk
        current.append({
            "date": d.strftime("%d.%m"),
            "iso": d.isoformat(),
            "weekday": WEEKDAY_RU[d.weekday()],
            "format": "",
            "owner": "",
        })
    if current:
        weeks.append(current)

    # First slot of every week = the fixed blogger-photo post, Vika's.
    for week in weeks:
        week[0]["format"] = "blogger_photo"
        week[0]["owner"] = photo_owner
        for slot in week[1:]:
            slot["owner"] = video_owner
    return weeks


def _rules_block(brand: str) -> str:
    try:
        from models.jack_lessons import render_rules_for_prompt
        return render_rules_for_prompt(brand)
    except Exception:
        return ""


def _month_ru(month: int) -> str:
    return ["", "январь", "февраль", "март", "апрель", "май", "июнь", "июль",
            "август", "сентябрь", "октябрь", "ноябрь", "декабрь"][month]


def month_strategy(analysis: dict, year: int, month: int, brand: str = "BelovedPets",
                   extra: str = "") -> dict:
    """One call: the month's angle, what to push, what to drop. Returns a dict, never raises."""
    from models.plan_analytics import as_prompt_block

    system = _system_prompt() + _rules_block(brand)
    prompt = f"""\
Ты планируешь Instagram-контент {brand} на {_month_ru(month)} {year}.

{as_prompt_block(analysis)}

ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ОТ КОМАНДЫ:
{extra or '(нет)'}

Задача: дай СТРАТЕГИЮ месяца, ещё без конкретных постов. Опирайся на факты выше.
Если цифр Instagram нет — так и скажи в поле `data_gaps`, не выдумывай числа.

Верни ЧИСТЫЙ JSON без обёрток:
{{
  "big_idea": "1-2 фразы — про что месяц, чем отличается от прошлого",
  "keep": ["что из прошлых месяцев работает и повторяем — с обоснованием из данных"],
  "drop": ["что перестаём делать и почему"],
  "new_bets": ["2-4 новых захода, которых не было"],
  "format_mix": {{"reel": 8, "carousel": 5, "animation": 3, "lifestyle": 2}},
  "weekly_themes": ["тема недели 1", "тема недели 2", "тема недели 3", "тема недели 4", "тема недели 5"],
  "data_gaps": ["чего не хватает, чтобы планировать точнее"]
}}
"""
    out = call_claude(prompt, system, timeout=180)
    parsed = _parse_json(out)
    if parsed.get("error"):
        return {"error": parsed["error"], "raw": parsed.get("raw", "")}
    return parsed


def generate_week(week_slots: list[dict], strategy: dict, analysis: dict,
                  week_no: int, total_weeks: int, *, brand: str = "BelovedPets",
                  market: str = "US", used_titles: list[str] | None = None,
                  extra: str = "", owner_names: dict[str, str] | None = None) -> list[dict]:
    """Fill one week's slots with real posts — hook, script, caption. Returns [] on failure."""
    from models.plan_analytics import as_prompt_block

    used = used_titles or []
    names = owner_names or {}
    theme = ""
    themes = strategy.get("weekly_themes") or []
    if week_no - 1 < len(themes):
        theme = themes[week_no - 1]

    def who(slug: str) -> str:
        return names.get(slug) or (slug.title() if slug else "исполнитель")

    slot_lines = []
    for s in week_slots:
        if s["format"] == "blogger_photo":
            slot_lines.append(
                f'- {s["date"]} ({s["weekday"]}) — ЗАФИКСИРОВАНО: «фото от блогера», '
                f'исполнитель {who(s["owner"])}. '
                f'Формат менять нельзя, но тему/подачу/подпись придумай.')
        else:
            slot_lines.append(
                f'- {s["date"]} ({s["weekday"]}) — свободный слот, исполнитель {who(s["owner"])}. '
                f'Выбери формат: carousel / animation / reel / lifestyle.')

    system = _system_prompt() + _rules_block(brand)
    prompt = f"""\
Пишешь НЕДЕЛЮ {week_no} из {total_weeks} контент-плана {brand} на {_month_ru(int(week_slots[0]["date"].split(".")[1]))}.

СТРАТЕГИЯ МЕСЯЦА (её же и держись):
{json.dumps(strategy, ensure_ascii=False, indent=2)[:2500]}

Тема этой недели: {theme or '(выведи сам из стратегии)'}

{as_prompt_block(analysis)[:6000]}

ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ОТ КОМАНДЫ:
{extra or '(нет)'}

Уже занятые темы в этом месяце — НЕ повторяй:
{'; '.join(used[-40:]) or '(пока пусто)'}

СЛОТЫ НЕДЕЛИ (ровно столько постов, ни больше ни меньше, даты не меняй):
{chr(10).join(slot_lines)}

Рынок: {market}.

Правила:
- Формат «фото от блогера» — только в зафиксированном слоте. Остальные слоты РАЗНЫЕ:
  не ставь три рилса подряд, чередуй carousel / animation / reel / lifestyle.
- `hook` — это первые 2 секунды рилса или первый экран карусели, на АНГЛИЙСКОМ, готовый к съёмке.
- `script` — ГОТОВОЕ ТЗ исполнителю в markdown. Для видео: сцены с таймингом
  («0-3 сек — что в кадре (РУС) · overlay "English" · voiceover "English"»).
  Для карусели: слайды («Слайд 1 — что в кадре · overlay "English copy"»).
  Для фото от блогера: что за кадр, какой overlay-текст, что выделить.
- `caption` — подпись под пост на английском, 2-4 строки + CTA.
- `why` — одной фразой, на чём основано решение (какой факт из истории/цифр).
- COMPLIANCE строго: НЕЛЬЗЯ cure / treat / heal / FDA / 100% safe / guaranteed /
  "Made in USA" / "vet-developed". МОЖНО: supports, may help with, gentle daily care,
  natural, holistic. Supplement, NOT medicine.
- Не выдумывай скидки, цены и промо, которых нет в контексте выше.

Верни ЧИСТЫЙ JSON без обёрток и без текста вокруг:
{{"posts": [
  {{"date": "01.09", "title": "короткая тема строчными, как в плане",
    "type": "engaging|selling|viral", "format": "reel|carousel|animation|lifestyle|blogger_photo",
    "pillar": "Product Highlight|Community / UGC|Education|Trend|Promo / Discount",
    "product": "какой SKU в кадре", "hook": "English hook",
    "script": "готовое ТЗ в markdown", "caption": "English caption",
    "why": "обоснование из данных"}}
]}}
"""
    out = call_claude(prompt, system, timeout=300)
    parsed = _parse_json(out)
    if parsed.get("error"):
        return []
    posts = parsed.get("posts") or []
    return _normalise(posts, week_slots)


def _normalise(posts: list[dict], slots: list[dict]) -> list[dict]:
    """Force the model's output back onto the real calendar.

    The model drifts on dates and occasionally drops or duplicates a slot, so slots are
    the source of truth: we walk them in order and take posts positionally, preferring a
    post that already claims the right date.
    """
    queue = [p for p in posts if isinstance(p, dict)]
    slot_dates = {s["date"] for s in slots}

    out: list[dict] = []
    for slot in slots:
        # Prefer the post that claims this exact date; otherwise take the first one left
        # that isn't claiming some other slot's date; otherwise just take the next one.
        post = (next((p for p in queue if p.get("date") == slot["date"]), None)
                or next((p for p in queue if p.get("date") not in slot_dates), None)
                or (queue[0] if queue else None))
        if post is None:
            continue
        queue.remove(post)

        fmt = (post.get("format") or "").strip().lower()
        if slot["format"] == "blogger_photo":
            fmt = "blogger_photo"
        elif fmt not in _ALLOWED_FORMATS or fmt == "blogger_photo":
            fmt = "reel"
        ptype = (post.get("type") or "").strip().lower()
        if ptype not in _ALLOWED_TYPES:
            ptype = "engaging"

        out.append({
            "date": slot["date"],
            "iso": slot["iso"],
            "weekday": slot["weekday"],
            "title": (post.get("title") or "").strip()[:120] or "(без темы)",
            "type": ptype,
            "format": fmt,
            "owner": slot["owner"] or (post.get("owner") or "dina"),
            "pillar": (post.get("pillar") or "").strip()[:60],
            "product": (post.get("product") or "").strip()[:120],
            "hook": (post.get("hook") or "").strip(),
            "script": _clean_md(post.get("script") or ""),
            "caption": (post.get("caption") or "").strip(),
            "why": (post.get("why") or "").strip(),
        })
    return out


def _clean_md(text: str) -> str:
    return re.sub(r"^```(?:markdown)?\s*|\s*```$", "", (text or "").strip()).strip()


def commit_to_plan(posts: list[dict], brand: str = "BelovedPets",
                   write_briefs: bool = True) -> dict:
    """Write the generated month into the shared plan + save each script as its ТЗ.

    Returns {"added": n, "briefs": n, "errors": [...]}. Existing posts are left alone —
    this only appends, so a second run won't wipe anything the team edited by hand.
    """
    from views.content_plan import add_plan_post
    from models import plan_briefs

    added = briefs = 0
    errors: list[str] = []
    stamp = date.today().strftime("%d.%m %H:%M")

    for p in posts:
        try:
            pid = add_plan_post(brand, p["date"], p["title"], p["type"],
                                p.get("pillar", ""), p.get("owner", ""))
            added += 1
        except Exception as e:
            errors.append(f'{p.get("date")}: {e}')
            continue

        if not write_briefs:
            continue
        body = _brief_text(p)
        if not body:
            continue
        try:
            plan_briefs.save(pid, body, title=p["title"], pillar=p.get("pillar", ""),
                             for_who=p.get("owner", "dina"), updated=stamp)
            briefs += 1
        except Exception as e:
            errors.append(f'ТЗ {p.get("date")}: {e}')

    return {"added": added, "briefs": briefs, "errors": errors}


_FORMAT_RU = {"reel": "Reel / видео", "carousel": "Карусель", "animation": "Анимация (оживление фото)",
              "lifestyle": "Life pic (статичное фото)", "blogger_photo": "Фото от блогера",
              "promo": "Промо"}


def _brief_text(p: dict) -> str:
    """Assemble the stored ТЗ exactly as the team reads it in a plan cell."""
    parts = [f'**Формат:** {_FORMAT_RU.get(p.get("format",""), p.get("format",""))}']
    if p.get("product"):
        parts.append(f'**Товар в кадре:** {p["product"]}')
    if p.get("hook"):
        parts.append(f'**Хук (первые 2 сек / первый экран):** {p["hook"]}')
    if p.get("script"):
        parts.append(p["script"])
    if p.get("caption"):
        parts.append(f'**Подпись под пост (EN):**\n{p["caption"]}')
    if p.get("why"):
        parts.append(f'_Почему этот пост в плане: {p["why"]}_')
    return "\n\n".join(parts).strip()
