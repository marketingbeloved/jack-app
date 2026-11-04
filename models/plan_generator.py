"""Jack writes a whole month of content plan from the previous months' evidence.

Two-stage on purpose. One giant call for ~13 posts with full scripts gets truncated and
the tail turns to mush, so:
  1. `month_strategy()` — one small call: what the month is about, which formats to push
     or drop, which mistakes from last month not to repeat. Cheap, reviewable.
  2. `generate_week()` — one call per week, ~3 posts with hook + ready script. Short
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

from models.jack_engine import (MAX_HASHTAGS, _parse_json, _system_prompt, call_claude,
                                limit_hashtags)

WEEKDAY_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

# Дни постинга по брендам (0 = понедельник). Решение Марии от 2026-10-24:
# BelovedPets — пн/ср/пт, Tobydic — пн/вт/чт. Бренд без записи постит по будням.
POSTING_DAYS = {
    "belovedpets": (0, 2, 4),
    "tobydic": (0, 1, 3),
}


def posting_days(brand: str) -> tuple[int, ...]:
    return POSTING_DAYS.get((brand or "").strip().lower(), (0, 1, 2, 3, 4))


def posting_days_ru(brand: str) -> str:
    return ", ".join(WEEKDAY_RU[d] for d in posting_days(brand))

# The structure Darya fixed: one blogger photo a week (Vika), the rest split between
# carousels, animations and reels of varying formats (Dina).
FORMAT_MIX = ["carousel", "animation", "reel", "lifestyle"]

_ALLOWED_TYPES = {"engaging", "selling", "viral", "neutral"}
_ALLOWED_FORMATS = {"blogger_photo", "carousel", "animation", "reel", "lifestyle", "promo"}


def _active_executors() -> set[str]:
    """slug'и исполнителей из живой команды — те, у кого роль graphics или video.

    Таня ушла (решение Марии, 2026-11-04), но в истории Tobydic её посты остались — без
    этого фильтра Джек «выводил из истории», что фото недели делает она.
    """
    try:
        from models import shared_store
        team = shared_store.get_team()
    except Exception:
        return {"vika", "dina"}
    out = {re.sub(r"[^a-z0-9]+", "", (m.get("name") or "").lower()) for m in team
           if any(r in (m.get("role") or "").lower() for r in ("graphics", "video"))}
    return out or {"vika", "dina"}


def owners_from_history(analysis: dict) -> tuple[str, str]:
    """Who does the blogger photo, and who does everything else — read off past months.

    Only people who are still executors count (see _active_executors). Falls back to the
    Vika/Dina pair when a brand has no usable history.
    """
    active = _active_executors()
    photo_counts = {k: v for k, v in (analysis.get("blogger_photo", {}).get("owners") or {}).items()
                    if k in active}
    rest_counts = {k: v for k, v in (analysis.get("by_owner") or {}).items()
                   if k in active and k not in photo_counts}
    if not rest_counts:  # everyone shares the same slot type — fall back to all owners
        rest_counts = {k: v for k, v in (analysis.get("by_owner") or {}).items()
                       if k in active}
    photo = max(photo_counts, key=photo_counts.get) if photo_counts else "vika"
    video = max(rest_counts, key=rest_counts.get) if rest_counts else "dina"
    return photo, video


# Кто делает какой формат — по РОЛИ, а не по тому, кто исторически хватал задачу.
# Карусель — это графика, значит графдизайнер, даже если в прошлые месяцы её собирал
# видеомейкер. Роль ищется в живой команде; нет подходящей — падаем на исполнителя,
# выведенного из истории.
_FORMAT_ROLE = {
    "carousel":  "graphics",
    "reel":      "video",
    "animation": "video",
    "lifestyle": "video",
    "promo":     "graphics",
}


def owner_for_format(fmt: str, team_roles: dict[str, str], fallback: str) -> str:
    """slug исполнителя под формат: по роли из живой команды, иначе fallback."""
    need = _FORMAT_ROLE.get(fmt)
    if not need:
        return fallback
    for slug, role in team_roles.items():
        if need in (role or "").lower():
            return slug
    return fallback


def month_skeleton(year: int, month: int, *,
                   brand: str = "",
                   photo_owner: str = "vika",
                   video_owner: str = "dina") -> list[list[dict]]:
    """Weeks of empty slots for the month, only on the brand's posting days.
    The first slot of each week is the blogger-photo slot."""
    last = calendar.monthrange(year, month)[1]
    allowed = posting_days(brand)
    days = [date(year, month, d) for d in range(1, last + 1)]
    days = [d for d in days if d.weekday() in allowed]

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


def apply_team_ideas(weeks: list[list[dict]], ideas: list[dict],
                     photo_owner: str = "vika") -> list[list[dict]]:
    """Пометить дни, где у команды уже стоит пост, как занятые (`fixed`).

    Занятые слоты Джек не пишет — генерация идёт только по свободным. Если идея команды
    встала на слот «фото от блогера», фото переезжает на первый свободный день недели;
    если в неделе фото блогера уже есть у команды — второе не ставим.
    """
    by_date: dict[str, list[dict]] = {}
    for idea in ideas:
        by_date.setdefault(idea["date"], []).append(idea)

    for week in weeks:
        week_dates = {s["date"] for s in week}
        has_photo = any(i["format"] == "blogger_photo"
                        for d in week_dates for i in by_date.get(d, []))
        for slot in week:
            if slot["date"] in by_date:
                slot["fixed"] = by_date[slot["date"]]
        photo_slot = next((s for s in week if s["format"] == "blogger_photo"), None)
        if photo_slot and (photo_slot.get("fixed") or has_photo):
            photo_slot["format"] = ""
            free = next((s for s in week if not s.get("fixed")), None)
            if free and not has_photo:
                free["owner"], photo_slot["owner"] = photo_owner, free["owner"]
                free["format"] = "blogger_photo"
    return weeks


def free_slots(weeks: list[list[dict]]) -> int:
    return sum(1 for w in weeks for s in w if not s.get("fixed"))


def team_ideas_block(ideas: list[dict]) -> str:
    """Идеи команды на этот месяц — текстом для промпта."""
    if not ideas:
        return "ИДЕИ КОМАНДЫ НА ЭТОТ МЕСЯЦ: пока нет — весь месяц пишешь ты."
    from models.plan_analytics import _FORMAT_LABELS
    lines = ["ИДЕИ КОМАНДЫ НА ЭТОТ МЕСЯЦ — уже стоят в плане, их придумала Мария/команда. "
             "Это ГЛАВНЫЙ сигнал, куда двигаться:"]
    for i in ideas:
        brief = re.sub(r"\s+", " ", i.get("brief") or "")[:220]
        lines.append(f"  • {i['date']} «{i['title']}» [{_FORMAT_LABELS.get(i['format'], i['format'])}"
                     f"{', ' + i['pillar'] if i.get('pillar') else ''}]" + (f" — {brief}" if brief else ""))
    lines.append(
        "Как с ними работать: НЕ удаляй, НЕ переписывай и НЕ ставь в `drop`. Разбери, что в них "
        "общего (темы, товары, боли, тон), и предложи НОВЫЕ посты, которые эти идеи развивают и "
        "дополняют — другой угол, другой формат, другой товар. Дословно не повторяй.")
    return "\n".join(lines)


def _rules_block(brand: str) -> str:
    try:
        from models.jack_lessons import render_rules_for_prompt
        rules = render_rules_for_prompt(brand)
    except Exception:
        rules = ""
    try:
        from models.audience_insights import render_for_prompt as _insights
        rules += _insights(brand)
    except Exception:
        pass
    return rules


def _catalog_block(brand: str = "BelovedPets", limit: int = 60) -> str:
    """Точный список SKU с категорией — чтобы Джек не выдумывал товары и не путал
    тритсы с добавками (от категории зависит, можно ли ставить бейдж 'Lab tested')."""
    # У каждого бренда свой каталог (products.brand_products): Tobydic — 7 своих SKU, без
    # товаров BelovedPets. Раньше Тане подсовывали пустоту, и Джек вписывал чужие SKU.
    # Полные названия со вкусом — через общую библиотеку. Раньше здесь стоял
    # short_title(..., 50), и хвост «(Salmon (for Cats))» отрезался вместе со вкусом.
    try:
        from models.products import catalog_block as _cb, product_rule as _pr
        return "\n" + _cb(brand, limit) + "\n" + _pr(brand) + "\n"
    except Exception:
        pass
    try:
        from models.products import all_products, short_title
    except Exception:
        return ""
    lines = []
    for p in all_products()[:limit]:
        cat = (p.get("category") or "?").upper()
        kb = p.get("knowledge_base_details") or {}
        use = (kb.get("Use cases") or kb.get("For") or "").strip()
        short = re.sub(r"\s+", " ", (p.get("description_short") or ""))[:110]
        bits = " · ".join(x for x in (use, short) if x)
        lines.append(f"  [{cat}] {short_title(p, 70)}" + (f"\n        бенефиты: {bits}" if bits else ""))
    if not lines:
        return ""
    return ("\nКАТАЛОГ — бери `product` ТОЧНО отсюда, полным названием, и бенефиты бери "
            "ОТСЮДА же, не выдумывай:\n" + "\n".join(lines) + "\n")


def _month_ru(month: int) -> str:
    return ["", "январь", "февраль", "март", "апрель", "май", "июнь", "июль",
            "август", "сентябрь", "октябрь", "ноябрь", "декабрь"][month]


def month_strategy(analysis: dict, year: int, month: int, brand: str = "BelovedPets",
                   extra: str = "", slots: int = 0, ideas: list[dict] | None = None) -> dict:
    """One call: the month's angle, what to push, what to drop. Returns a dict, never raises."""
    from models.plan_analytics import as_prompt_block

    slots = slots or sum(len(w) for w in month_skeleton(year, month, brand=brand))
    ideas = ideas or []
    system = _system_prompt() + _rules_block(brand)
    prompt = f"""\
Ты планируешь Instagram-контент {brand} на {_month_ru(month)} {year}.
Постим 3 раза в неделю: {posting_days_ru(brand)}. Тебе писать {slots} новых постов
(идеи команды ниже уже стоят в плане и в это число не входят) — сумма чисел в `format_mix`
должна быть ровно {slots}.
Исполнители — только Вика (графика: фото от блогера, carousel, promo) и Дина (видео: reel,
animation, lifestyle), нагрузка 50/50 (решение Марии). Подбирай `format_mix` так, чтобы
вместе с еженедельным «фото от блогера» графики и видео в месяце было примерно поровну.

{team_ideas_block(ideas)}

{as_prompt_block(analysis)}

ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ОТ КОМАНДЫ:
{extra or '(нет)'}

Задача: дай СТРАТЕГИЮ месяца, ещё без конкретных постов. Опирайся на идеи команды и факты выше.
Если цифр Instagram нет — так и скажи в поле `data_gaps`, не выдумывай числа.
«Идея команды (формат в названии не указан)» в истории — это НЕ брак и не «прочее», а темы,
придуманные командой. Их не убираем, а анализируем.
В `drop` — только то, что ПРОВАЛИЛОСЬ по цифрам Instagram. Нет цифр — `drop` пустой.
НЕ ХОДИ ПО КРУГУ (решение Марии): прошлые месяцы — фон, а не шаблон. Минимум ПОЛОВИНА
постов месяца — новые форматы, идеи и темы, которых в истории выше НЕТ. `keep` — не больше
3 пунктов. Новое бери из ресёрча ЦА, трендов и механик, которые у нас уже сработали
(участие, награда, реакция питомца), — но в новой упаковке, а не повтором старых постов.

Верни ЧИСТЫЙ JSON без обёрток:
{{
  "big_idea": "1-2 фразы — про что месяц, чем отличается от прошлого",
  "team_ideas": ["что ты увидел в идеях команды (темы, товары, углы) и как новые посты их развивают"],
  "keep": ["до 3 пунктов: что из прошлых месяцев работает и повторяем — с обоснованием из данных"],
  "drop": ["только провалы по цифрам; нет цифр — пустой список"],
  "new_bets": ["4-6 новых форматов/идей/тем, которых у нас ещё не было — на них минимум половина постов"],
  "format_mix": {{"reel": 4, "carousel": 3, "animation": 1, "lifestyle": 1}},
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
                  extra: str = "", owner_names: dict[str, str] | None = None,
                  team_roles: dict[str, str] | None = None,
                  ideas: list[dict] | None = None) -> list[dict]:
    """Fill one week's FREE slots with real posts — hook, script, caption. Returns [] on failure.

    Slots marked `fixed` (the team already put a post there) are shown to the model as
    context and never written over.
    """
    from models.plan_analytics import as_prompt_block, _FORMAT_LABELS

    fixed = [s for s in week_slots if s.get("fixed")]
    week_slots = [s for s in week_slots if not s.get("fixed")]
    if not week_slots:
        return []
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
                f'исполнитель {who(s["owner"])}. title строго "фото от блогера", не меняй.')
        else:
            slot_lines.append(
                f'- {s["date"]} ({s["weekday"]}) — свободный слот, исполнитель {who(s["owner"])}. '
                f'Выбери формат: carousel / animation / reel / lifestyle.')
    fixed_lines = [f'- {s["date"]} ({s["weekday"]}) — ЗАНЯТО идеей команды: «{i["title"]}» '
                   f'[{_FORMAT_LABELS.get(i["format"], i["format"])}]. Не пиши для этого дня.'
                   for s in fixed for i in s["fixed"]]

    system = _system_prompt() + _rules_block(brand)
    prompt = f"""\
Пишешь НЕДЕЛЮ {week_no} из {total_weeks} контент-плана {brand} на {_month_ru(int(week_slots[0]["date"].split(".")[1]))}.

СТРАТЕГИЯ МЕСЯЦА (её же и держись):
{json.dumps(strategy, ensure_ascii=False, indent=2)[:2500]}

Тема этой недели: {theme or '(выведи сам из стратегии)'}

{as_prompt_block(analysis)[:6000]}

ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ОТ КОМАНДЫ:
{extra or '(нет)'}

{_catalog_block(brand)}
{team_ideas_block(ideas or [])}

Уже занятые темы в этом месяце — НЕ повторяй:
{'; '.join(used[-40:]) or '(пока пусто)'}

СЛОТЫ НЕДЕЛИ (ровно столько постов, ни больше ни меньше, даты не меняй):
{chr(10).join(slot_lines)}
{('Уже стоит в этой неделе (контекст, НЕ пиши):' + chr(10) + chr(10).join(fixed_lines)) if fixed_lines else ''}

Рынок: {market}.

Правила:
- Формат «фото от блогера» — только в зафиксированном слоте. Остальные слоты РАЗНЫЕ:
  не ставь три рилса подряд, чередуй carousel / animation / reel / lifestyle.
- ВАЖНО ПРО «фото от блогера». Исходник выбирает Мария руками на Google Диске и присылает
  ссылку исполнителю. Ты НЕ знаешь, что на этом фото, и придумывать НЕЛЬЗЯ: не пиши, какое
  там животное, товар, поза или обстановка. В `title` пиши ровно «фото от блогера».
  В `script` дай только то, что применимо к ЛЮБОМУ фото блогера: первой строкой
  «Исходник: ссылка на фото от Марии (выберет с Диска)», затем overlay-текст на английском,
  кадрирование 4:5, тон обработки и что подпись/логотип не должны перекрывать питомца.
  `hook` для такого слота — это текст overlay, а не описание кадра.
- `hook` — это первые 2 секунды рилса или первый экран карусели, на АНГЛИЙСКОМ, готовый к съёмке.
- `script` — ГОТОВОЕ ТЗ исполнителю в markdown. Для видео: сцены с таймингом
  («0-3 сек — что в кадре (РУС) · overlay "English" · voiceover "English"»).
  Для карусели: слайды («Слайд 1 — что в кадре · overlay "English copy"»).
  Для фото от блогера: что за кадр, какой overlay-текст, что выделить.
- `caption` — подпись под пост на английском, 2-4 строки + CTA. Хэштеги — В КОНЦЕ подписи,
  НЕ БОЛЬШЕ {MAX_HASHTAGS} штук на пост (лишние отрежутся автоматически).
- `why` — одной фразой, на чём основано решение: факт из истории/цифр ИЛИ какую новую
  гипотезу проверяет пост (для постов из `new_bets` стратегии).
- НОВИЗНА. Минимум половина постов недели — из `new_bets` стратегии: форматы, идеи и темы,
  которых у нас ещё не было. Не пересобирай прошлые посты другими словами.
- НЕ МУДРИТЬ, но делать КРУТО. Простая съёмка не значит скучная идея: вся выдумка уходит
  в хук и в саму мысль, а не в сложность продакшена.
- ПОДПИСЫВАТЬ ВСЁ. В каждой сцене — текст на экране (субтитры/overlay), ролик должен
  читаться без звука. Ни одной сцены без подписи.
- ТОВАР называй точно и целиком, и бенефиты бери из каталога ниже, а не из головы.
- БАЛАНС. В месяце должен быть РАЗНЫЙ контент: ориентир ~50% вовлекающих (engaging),
  ~25% ПРОДАЮЩИХ (selling) и ~25% вирусных (viral). Месяц из одних вовлекающих — ошибка.
  Продающие — офферы, скидки, бандлы, Subscribe & Save, Amazon / Chewy / Faire, запуски.
  Смотри, какие категории уже заняты в предыдущих неделях, и добирай недостающие.
- ДЛИНА РИЛСА — строго ДО 20 СЕКУНД. Тайминг сцен должен укладываться в 20 сек, не больше.
- СНИМАЕМОСТЬ. Рилс снимается на телефон дома за 20-30 минут. Максимум 3-4 сцены.
  Без сплит-скринов, без раскадровок на 5+ пунктов, без зумов на этикетку, без реквизита
  вроде календарей и досок, без нескольких локаций и сложного монтажа. Одна сцена — одна
  простая мысль. Идея требует продакшена — упрости идею, а не проси сложную съёмку.
- РАЗНООБРАЗИЕ. Один и тот же шаблон или рубрика — не чаще 2 раз за месяц. Чередуй заходы:
  POV, до/после, один кадр с закадровым голосом, разговор с питомцем, распаковка,
  ошибка-и-исправление, реакция на отзыв, крупный план проблемы. Смотри список уже занятых
  тем выше и не повторяй структуру, а не только слова.
- ANIMATION — это НЕ мультик и не motion-графика с нуля. Это: берём готовое ФОТО,
  Дина его оживляет (лёгкое движение в кадре), сверху накладывает текст и звук.
  Фото берётся из одобренного UGC-контента JoinBrands (папка на общем Диске) — так и пиши:
  «Исходник: одобренное фото из JoinBrands (ссылку даст Мария)». Что именно на фото —
  НЕ придумывай, как и в слоте «фото от блогера».
- `product` бери ТОЧНО из каталога брендa, полным названием SKU. Не сокращай, не выдумывай
  и не смешивай два товара в один. Если для идеи не нашёл подходящего SKU — поменяй идею.
  Пост про бренд в целом, без конкретного товара — пиши в `product` «вся линейка».
- COMPLIANCE строго. НЕЛЬЗЯ: cure / treat / heal / FDA / 100% safe / guaranteed /
  "Made in USA" / "vet-developed" / "vet-recommended" / kills / prevents / eliminates.
  МОЖНО: supports, may help with, gentle daily care, natural, holistic.
  Supplement, NOT medicine.
- ОТДЕЛЬНО про "Lab tested" (и HACCP / COA / GMP). Это можно ставить на экран ТОЛЬКО для
  ТРИТСОВ (jerky, chews-лакомства, freeze-dried). Для добавок, капель, спреев и flea & tick
  — НЕЛЬЗЯ, даже мелким бейджем. Из-за таких плашек режут рекламу.
- Список запретов в сам текст ТЗ НЕ переписывай — исполнителю он не нужен, а в ТЗ создаёт
  видимость нарушений. Просто соблюдай.
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
    return _normalise(posts, week_slots, team_roles, brand)


def _check_product(name: str, brand: str) -> str:
    """Товар из ответа модели → точное название из каталога, или пометка, что его нет.

    Промпт просит брать товар из каталога, но модель всё равно иногда сочиняет. Здесь
    это ловится до того, как пост уйдёт в план: команда видит ⚠️ прямо в ячейке.
    """
    name = (name or "").strip()
    if not name or name.lower().startswith(("вся линейка", "бренд", "нет", "—", "-", "уточнить",
                                            "n/a", "none", "any", "любой")):
        return name
    try:
        from models.products import brand_products, find_exact, find_mentioned
        if not brand_products(brand):
            return name                      # каталог не загрузился — сверять не с чем
        p = find_exact(name, brand) or find_mentioned(name, brand)
    except Exception:
        return name
    if p:
        return p.get("title", name)
    return f"⚠️ нет в каталоге, проверить: {name}"


def _normalise(posts: list[dict], slots: list[dict],
               team_roles: dict[str, str] | None = None,
               brand: str = "BelovedPets") -> list[dict]:
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

        # Исполнитель ставится ПОСЛЕ выбора формата: до генерации мы не знаем, что тут
        # будет — карусель (графика) или рилс (видео).
        owner = slot["owner"] or "dina"
        if fmt != "blogger_photo" and team_roles:
            owner = owner_for_format(fmt, team_roles, owner)

        out.append({
            "date": slot["date"],
            "iso": slot["iso"],
            "weekday": slot["weekday"],
            "title": (post.get("title") or "").strip()[:120] or "(без темы)",
            "type": ptype,
            "format": fmt,
            "owner": owner,
            "pillar": (post.get("pillar") or "").strip()[:60],
            "product": _check_product(post.get("product") or "", brand)[:160],
            "hook": (post.get("hook") or "").strip(),
            "script": _clean_md(post.get("script") or ""),
            "caption": limit_hashtags((post.get("caption") or "").strip()),
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
