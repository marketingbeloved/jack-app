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

# Одно фото от блогера в неделю (Вика), остальное — статика и карусели (Вика),
# рилсы и анимации фото (Дина). Решение Марии 2026-11-13: life pic в новых планах нет.
FORMAT_MIX = ["carousel", "static", "animation", "reel"]

_ALLOWED_TYPES = {"engaging", "selling", "viral", "neutral"}
_ALLOWED_FORMATS = {"blogger_photo", "carousel", "static", "animation", "reel", "lifestyle", "promo"}


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
    "static":    "graphics",
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


def _catalog_block(brand: str = "BelovedPets", limit: int = 200, market: str = "US") -> str:
    """Точный список SKU с категорией — чтобы Джек не выдумывал товары и не путал
    тритсы с добавками (от категории зависит, можно ли ставить бейдж 'Lab tested')."""
    # У каждого бренда свой каталог (products.brand_products): Tobydic — 7 своих SKU, без
    # товаров BelovedPets. Раньше Тане подсовывали пустоту, и Джек вписывал чужие SKU.
    # Полные названия со вкусом — через общую библиотеку. Раньше здесь стоял
    # short_title(..., 50), и хвост «(Salmon (for Cats))» отрезался вместе со вкусом.
    try:
        from models.products import catalog_block as _cb, product_rule as _pr
        return "\n" + _cb(brand, limit, market) + "\n" + _pr(brand) + "\n"
    except Exception:
        pass
    try:
        from models.products import brand_products, short_title
    except Exception:
        return ""
    lines = []
    for p in brand_products(brand)[:limit]:
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


# ─── Что команда хочет в этом месяце — ГЛАВНЫЙ сигнал (решение Марии 2026-11-13) ──
# Раньше «Что учесть» стояло после 6000 знаков истории и тонуло. Теперь — первым блоком,
# и каждая конкретная идея из него обязана стать постом.

def _wishes_block(extra: str) -> str:
    extra = (extra or "").strip()
    if not extra:
        return "ГЛАВНОЕ ОТ КОМАНДЫ НА ЭТОТ МЕСЯЦ: пожеланий нет."
    return ("ГЛАВНОЕ ОТ КОМАНДЫ НА ЭТОТ МЕСЯЦ — ВЫПОЛНИТЬ В ПЕРВУЮ ОЧЕРЕДЬ. Каждая конкретная "
            "идея, акция или новинка отсюда должна стать отдельным постом месяца:\n" + extra)


def _competitors_block(limit: int = 10) -> str:
    """Хуки конкурентов из уже собранной бесплатной базы (competitor_parser.SEED_IDEAS).
    Сеть не трогаем: свежий парсинг — только через платный Apify и с разрешения Марии."""
    try:
        from models.competitor_parser import SEED_IDEAS
    except Exception:
        return ""
    lines = ["ЧТО РАБОТАЕТ У КОНКУРЕНТОВ (Pet Honesty, Zesty Paws, Native Pet…; база июня 2026). "
             "Бери МЕХАНИКУ и упаковку, а не копию; названия конкурентов в посты не пиши:"]
    for i in SEED_IDEAS[:limit]:
        lines.append(f"  • {i.get('source', '')}: «{i.get('hook', '')}» — {i.get('views', '?')} "
                     f"просмотров, {i.get('kind', '')}; {i.get('why', '')}")
    return "\n".join(lines)


def _bank_for_month(strategy: dict, bank: list[dict], used_ids: set[str]) -> list[dict]:
    """Идеи банка, которые стратегия выбрала на месяц и которые ещё не стали постами."""
    chosen = {str(x) for x in (strategy.get("bank_ids") or [])}
    return [i for i in bank if i["id"] in chosen and i["id"] not in used_ids]


def _experiments_block(strategy: dict) -> str:
    exps = strategy.get("experiments") or []
    if not exps:
        return ""
    lines = ["ЭКСПЕРИМЕНТЫ МЕСЯЦА — каждый проверяется одним постом; у такого поста заполни "
             "поле `experiment` текстом гипотезы (дословно отсюда):"]
    for e in exps[:3]:
        h = e.get("hypothesis") if isinstance(e, dict) else str(e)
        lines.append(f"  • {h}")
    return "\n".join(lines)


def _bank_prompt(bank: list[dict] | None, week: bool = False) -> str:
    from models.idea_bank import prompt_block
    if week and not bank:
        return ""
    head = ("ИДЕИ ИЗ БАНКА, ВЗЯТЫЕ НА МЕСЯЦ и ещё не ставшие постами — если идея подходит "
            "к слотам этой недели, сделай из неё пост и поставь её id в `bank_id`:\n") if week else ""
    return head + prompt_block(bank or [])


def _post_rules() -> str:
    return f"""Правила:
- Формат «фото от блогера» — только в зафиксированном слоте. Остальные слоты РАЗНЫЕ:
  не ставь три рилса подряд, чередуй carousel / static / animation / reel.
- ВАЖНО ПРО «фото от блогера». Ты выбираешь, КАКОЙ ТОВАР показать, а фото с этим товаром
  Маша подберёт на Диске сама. Что на фото (животное, поза, обстановка) — не придумывай.
  `title` = «фото от блогера · <товар коротко, 2-4 слова>», напр.
  «фото от блогера · Hip & Joint Chews».
- `hook` — на АНГЛИЙСКОМ: первые 2 секунды видео или надпись на первом экране графики.
- ТЗ исполнителям ЛАКОНИЧНЫЕ. Шрифты, цвета, плашки, айдентику, пропорции, монтаж Вика и
  Дина знают — про них НИ слова. Никаких советов по съёмке и обработке.
- `hook` — на АНГЛИЙСКОМ: надпись на обложке видео или на первом слайде графики.
- `script`:
  • ГРАФИКА (Вика: фото от блогера, static, carousel) — ТОЛЬКО надписи на английском.
    Статика — одна строка «"..."». Карусель — МАКСИМУМ 4 слайда, по строке на слайд:
    «1. "..."», «2. "..."». Больше ничего.
  • ВИДЕО (Дина: reel, animation) — МАКСИМУМ 3 сцены, каждая одной строкой строго так:
    «1. что в кадре (по-русски, 1 фраза). Надпись: "English"». Сцены такие, чтобы их
    легко было сгенерировать ИИ: одно животное, одна локация, одно простое действие
    (спит, поворачивает голову, лижет, виляет хвостом, бежит к миске). Нельзя: несколько
    животных во взаимодействии, этикетки и мелкий текст крупно, сложные действия рук,
    смена локаций, сложные движения камеры. Без таймингов.
- `cover` — только для видео, обложка одной строкой.
  Reel: «что на обложке (по-русски, 1 фраза). Надпись: "English"».
  Animation: «фото — даст Маша. Надпись: "English"» (что на фото — не выдумывай).
  Для графики `cover` — пустая строка.
- `caption` — подпись под пост на английском, 2-4 строки + CTA. Хэштеги — В КОНЦЕ подписи,
  НЕ БОЛЬШЕ {MAX_HASHTAGS} штук на пост (лишние отрежутся автоматически).
- `why` — одной фразой, на чём основано решение: факт из истории/цифр ИЛИ какую новую
  гипотезу проверяет пост (для постов из `new_bets` стратегии).
- НОВИЗНА. Минимум половина постов недели — из `new_bets` стратегии: форматы, идеи и темы,
  которых у нас ещё не было. Не пересобирай прошлые посты другими словами.
- НЕ МУДРИТЬ, но делать КРУТО. Простая съёмка не значит скучная идея: вся выдумка уходит
  в хук и в саму мысль, а не в сложность продакшена.
- ПОДПИСЫВАТЬ ВСЁ. В каждой сцене — надпись на экране, ролик должен читаться без звука.
- ТОВАР называй точно и целиком, и бенефиты бери из каталога ниже, а не из головы.
- БАЛАНС. В месяце должен быть РАЗНЫЙ контент: ориентир ~50% вовлекающих (engaging),
  ~25% ПРОДАЮЩИХ (selling) и ~25% вирусных (viral). Месяц из одних вовлекающих — ошибка.
  Продающие — офферы, скидки, бандлы, Subscribe & Save, Amazon / Chewy / Faire, запуски.
  Смотри, какие категории уже заняты в предыдущих неделях, и добирай недостающие.
- ДЛИНА РИЛСА — строго ДО 20 СЕКУНД. Тайминг сцен должен укладываться в 20 сек, не больше.
- ПРОСТОТА. Рилс Дина генерирует ИИ. Максимум 3 сцены. Без сплит-скринов, без зумов на
  этикетку, без реквизита вроде календарей и досок, без нескольких локаций и сложного
  монтажа. Одна сцена — одна простая мысль. Идея требует продакшена — упрости идею.
- РАЗНООБРАЗИЕ. Один и тот же шаблон или рубрика — не чаще 2 раз за месяц. Чередуй заходы:
  POV, до/после, один кадр с закадровым голосом, разговор с питомцем, распаковка,
  ошибка-и-исправление, реакция на отзыв, крупный план проблемы. Смотри список уже занятых
  тем выше и не повторяй структуру, а не только слова.
- ANIMATION — это НЕ мультик и не motion-графика с нуля. Это: берём готовое ФОТО,
  Дина его оживляет (лёгкое движение в кадре), сверху накладывает текст и звук.
  Фото даёт Маша (одобренный UGC с Диска) — поэтому в `cover` пиши «фото — даст Маша».
  Что именно на фото — НЕ придумывай, как и в слоте «фото от блогера».
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
"""


def _month_ru(month: int) -> str:
    return ["", "январь", "февраль", "март", "апрель", "май", "июнь", "июль",
            "август", "сентябрь", "октябрь", "ноябрь", "декабрь"][month]


def month_strategy(analysis: dict, year: int, month: int, brand: str = "BelovedPets",
                   extra: str = "", slots: int = 0, ideas: list[dict] | None = None,
                   bank: list[dict] | None = None) -> dict:
    """One call: the month's angle, what to push, what to drop. Returns a dict, never raises."""
    from models.plan_analytics import as_prompt_block

    slots = slots or sum(len(w) for w in month_skeleton(year, month, brand=brand))
    ideas = ideas or []
    system = _system_prompt() + _rules_block(brand)
    prompt = f"""\
Ты планируешь Instagram-контент {brand} на {_month_ru(month)} {year}.

{_wishes_block(extra)}

Постим 3 раза в неделю: {posting_days_ru(brand)}. Тебе писать {slots} новых постов
(идеи команды ниже уже стоят в плане и в это число не входят) — сумма чисел в `format_mix`
должна быть ровно {slots}.
Исполнители — только Вика (графика: фото от блогера, static, carousel) и Дина (видео: reel,
animation), нагрузка 50/50 (решение Марии). Подбирай `format_mix` так, чтобы
вместе с еженедельным «фото от блогера» графики и видео в месяце было примерно поровну.

{team_ideas_block(ideas)}

{_bank_prompt(bank)}

{_competitors_block()}

ИСТОРИЯ — это ФОН: что уже было и что сработало по цифрам. НЕ шаблон для копирования.
{as_prompt_block(analysis)}

Задача: дай СТРАТЕГИЮ месяца, ещё без конкретных постов. Порядок важности: пожелания
команды → идеи команды в плане и в банке → новые заходы (конкуренты, тренды, эксперименты)
→ и только потом история.
БАНК ИДЕЙ: выбери из банка 2-4 идеи, которые лучше всего ложатся на месяц, и верни их id в
`bank_ids` (если банк пуст — пустой список).
ЭКСПЕРИМЕНТЫ: придумай 2-3 гипотезы, которые мы ещё НЕ проверяли (новый формат, новый тип
хука, новая тема, новая механика вовлечения). Каждая — одной фразой «если …, то …» и с
метрикой, по которой поймём результат (просмотры / сохранения / комментарии / репосты).
Посмотри в истории блок «ПРОШЛЫЕ ЭКСПЕРИМЕНТЫ»: что сработало — развивай, что нет — не повторяй.
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
  "wishes": ["как закрыт каждый пункт из «ГЛАВНОЕ ОТ КОМАНДЫ»"],
  "bank_ids": ["id идей из банка, которые берём в этот месяц"],
  "experiments": [{{"hypothesis": "если …, то …", "metric": "сохранения"}}],
  "keep": ["до 3 пунктов: что из прошлых месяцев работает и повторяем — с обоснованием из данных"],
  "drop": ["только провалы по цифрам; нет цифр — пустой список"],
  "new_bets": ["4-6 новых форматов/идей/тем, которых у нас ещё не было — на них минимум половина постов"],
  "format_mix": {{"reel": 3, "carousel": 2, "static": 2, "animation": 2}},
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
                  ideas: list[dict] | None = None,
                  bank: list[dict] | None = None) -> list[dict]:
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
                f'исполнитель {who(s["owner"])}. title: "фото от блогера · <товар в 2-4 словах>".')
        else:
            slot_lines.append(
                f'- {s["date"]} ({s["weekday"]}) — свободный слот, исполнитель {who(s["owner"])}. '
                f'Выбери формат: carousel / static / animation / reel.')
    fixed_lines = [f'- {s["date"]} ({s["weekday"]}) — ЗАНЯТО идеей команды: «{i["title"]}» '
                   f'[{_FORMAT_LABELS.get(i["format"], i["format"])}]. Не пиши для этого дня.'
                   for s in fixed for i in s["fixed"]]

    system = _system_prompt() + _rules_block(brand)
    prompt = f"""\
Пишешь НЕДЕЛЮ {week_no} из {total_weeks} контент-плана {brand} на {_month_ru(int(week_slots[0]["date"].split(".")[1]))}.

{_wishes_block(extra)}

СТРАТЕГИЯ МЕСЯЦА (её же и держись):
{json.dumps(strategy, ensure_ascii=False, indent=2)[:2500]}

Тема этой недели: {theme or '(выведи сам из стратегии)'}

{_bank_prompt(bank, week=True)}

{_experiments_block(strategy)}

ИСТОРИЯ (кратко, ФОН — не шаблон; не повторяй структуру прошлых постов):
{as_prompt_block(analysis)[:2500]}

{_catalog_block(brand, market=market)}
{team_ideas_block(ideas or [])}

Уже занятые темы в этом месяце — НЕ повторяй:
{'; '.join(used[-40:]) or '(пока пусто)'}

СЛОТЫ НЕДЕЛИ (ровно столько постов, ни больше ни меньше, даты не меняй):
{chr(10).join(slot_lines)}
{('Уже стоит в этой неделе (контекст, НЕ пиши):' + chr(10) + chr(10).join(fixed_lines)) if fixed_lines else ''}

Рынок: {market}.

{_post_rules()}

Верни ЧИСТЫЙ JSON без обёрток и без текста вокруг:
{{"posts": [
  {{"date": "01.09", "title": "короткая тема строчными, как в плане",
    "type": "engaging|selling|viral", "format": "reel|animation|carousel|static|blogger_photo",
    "pillar": "Product Highlight|Community / UGC|Education|Trend|Promo / Discount",
    "product": "какой SKU в кадре", "hook": "English hook",
    "cover": "обложка (только видео)", "script": "надписи / сцены", "caption": "English caption",
    "bank_id": "id идеи из банка, если пост из неё вырос, иначе пусто",
    "experiment": "гипотеза эксперимента, если пост её проверяет, иначе пусто",
    "why": "обоснование из данных"}}
]}}
"""
    out = call_claude(prompt, system, timeout=300)
    parsed = _parse_json(out)
    if parsed.get("error"):
        return []
    posts = parsed.get("posts") or []
    return _normalise(posts, week_slots, team_roles, brand, market)


def ideas_to_develop(ideas: list[dict]) -> list[dict]:
    """Идеи команды в ячейках месяца, у которых ещё нет ТЗ, — их Джек разворачивает в посты."""
    return [i for i in ideas or [] if i.get("id") and not (i.get("brief") or "").strip()]


def develop_ideas(ideas: list[dict], strategy: dict, year: int, *, brand: str = "BelovedPets",
                  market: str = "US", extra: str = "",
                  team_roles: dict[str, str] | None = None) -> list[dict]:
    """Развернуть идеи команды из ячеек плана в полноценные посты (решение Марии 2026-11-13).

    Раньше Джек дни с идеями команды просто пропускал: в плане оставалось одно название
    без товара и ТЗ. Теперь название и дата остаются как у команды, а Джек дописывает
    формат, товар, надписи / сцены и подпись. Пишем пачками по 6, чтобы ответ не обрезался.
    """
    from models.plan_analytics import _FORMAT_LABELS
    out: list[dict] = []
    for k in range(0, len(ideas), 6):
        chunk = ideas[k:k + 6]
        lines = [f'- [{i["id"]}] {i["date"]} — «{i["title"]}»'
                 + (f' [формат по названию: {_FORMAT_LABELS.get(i["format"], i["format"])}]'
                    if i.get("format") in _ALLOWED_FORMATS else "")
                 for i in chunk]
        prompt = f"""\
Команда сама придумала эти посты и поставила их в контент-план {brand}. Сейчас у каждого
только название. Твоя задача — РАЗВЕРНУТЬ каждую идею в готовый пост, сохранив её смысл.

{_wishes_block(extra)}

СТРАТЕГИЯ МЕСЯЦА (для контекста):
{json.dumps(strategy, ensure_ascii=False, indent=2)[:1500]}

{_catalog_block(brand, market=market)}

ИДЕИ КОМАНДЫ (id в квадратных скобках):
{chr(10).join(lines)}

Как разворачивать:
- `date` и `title` — РОВНО как у команды, не меняй ни слова. В `idea_id` — id идеи.
- Смысл идеи — главный. Не подменяй её своей. Можно усилить хук и упаковку.
- Формат: если он понятен из названия — бери его; иначе выбери сам
  (carousel / static / animation / reel). «фото от блогера» оставляй только если так в названии.
- Товар выбери из каталога, если идея про товар или товар естественно в неё ложится.
  Идея про бренд в целом — `product` «вся линейка».

{_post_rules()}

Верни ЧИСТЫЙ JSON без обёрток и без текста вокруг:
{{"posts": [
  {{"idea_id": "id", "date": "дата как у команды", "title": "название как у команды",
    "type": "engaging|selling|viral", "format": "reel|animation|carousel|static|blogger_photo",
    "pillar": "Product Highlight|Community / UGC|Education|Trend|Promo / Discount",
    "product": "какой SKU в кадре", "hook": "English hook",
    "cover": "обложка (только видео)", "script": "надписи / сцены", "caption": "English caption",
    "why": "как пост раскрывает идею команды"}}
]}}
"""
        parsed = _parse_json(call_claude(prompt, _system_prompt() + _rules_block(brand), timeout=300))
        if parsed.get("error"):
            continue
        got = {str(p.get("idea_id")): p for p in parsed.get("posts") or [] if isinstance(p, dict)}
        for i in chunk:
            post = got.get(i["id"])
            if not post:
                continue
            d, m = (int(x) for x in i["date"].split(".")[:2])
            slot = {"date": i["date"], "iso": date(year, m, d).isoformat(),
                    "weekday": WEEKDAY_RU[date(year, m, d).weekday()],
                    "format": "blogger_photo" if i.get("format") == "blogger_photo" else "",
                    "owner": i.get("owner") or ""}
            post["date"] = i["date"]
            norm = _normalise([post], [slot], team_roles, brand, market)
            if norm:
                norm[0]["title"] = i["title"]          # название команды — дословно
                norm[0]["idea_id"] = i["id"]
                out.append(norm[0])
    return out

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
        from models.products import (brand_products, find_exact, find_mentioned,
                                     other_brand_product)
        if not brand_products(brand):
            return name                      # каталог не загрузился — сверять не с чем
        p = find_exact(name, brand) or find_mentioned(name, brand)
        if not p and other_brand_product(name, brand):
            return f"⚠️ товар другого бренда, заменить: {name}"
    except Exception:
        return name
    if p:
        return p.get("title", name)
    return f"⚠️ нет в каталоге, проверить: {name}"


def _product_link(name: str, brand: str, market: str = "US") -> str:
    """Ссылка на листинг Amazon для товара из базы ('' — бренд целиком или ⚠️)."""
    try:
        from models.products import product_url
        return product_url(name, brand, market) if name and not name.startswith("⚠️") else ""
    except Exception:
        return ""


def _normalise(posts: list[dict], slots: list[dict],
               team_roles: dict[str, str] | None = None,
               brand: str = "BelovedPets", market: str = "US") -> list[dict]:
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

        product = _check_product(post.get("product") or "", brand)[:160]
        title = (post.get("title") or "").strip()[:120] or "(без темы)"
        if fmt == "blogger_photo":
            title = _blogger_title(title, product)

        out.append({
            "date": slot["date"],
            "iso": slot["iso"],
            "weekday": slot["weekday"],
            "title": title,
            "type": ptype,
            "format": fmt,
            "owner": owner,
            "pillar": (post.get("pillar") or "").strip()[:60],
            "product": product,
            "product_url": _product_link(product, brand, market),
            "hook": (post.get("hook") or "").strip(),
            "cover": (post.get("cover") or "").strip(),
            "bank_id": str(post.get("bank_id") or "").strip(),
            "experiment": (post.get("experiment") or "").strip()[:200],
            "script": _clean_md(post.get("script") or ""),
            "caption": limit_hashtags((post.get("caption") or "").strip()),
            "why": (post.get("why") or "").strip(),
        })
    return out


def _blogger_title(title: str, product: str) -> str:
    """«фото от блогера · <товар коротко>» — чтобы в календаре было видно, что за товар.

    Анализ прошлых месяцев ищет рубрику по началу «фото от блогера», хвост ему не мешает.
    """
    tail = re.sub(r"^\s*фото\s*(?:от\s*)?блогер[а-я]*\s*[·:—\-]*\s*", "", title, flags=re.I).strip()
    if not tail and product and not product.startswith("⚠️"):
        # «TOBYDIC Herbal Intestinal Cleanse Drops with Probiotic for Dogs & Cats, 60 ml»
        # → «Herbal Intestinal Cleanse with Probiotic»; «… Topper — Tuna Shreds in Gravy»
        # → «Tuna Shreds in Gravy». Размер и «for Dogs & Cats» в календаре не нужны.
        t = re.sub(r"^(Beloved Pets|TOBYDIC)\s+", "", product, flags=re.I)
        t = re.split(r",\s*\d|,\s*\d?\s*pack|\s+\(", t)[0]
        if " — " in t:
            left, right = t.split(" — ", 1)
            t = right if len(right.split()) >= 2 else f"{left} {right}"
        t = re.split(r"\s+for\s+", t, maxsplit=1, flags=re.I)[0]
        t = re.sub(r"\b(?:Drops|Soft Chews|Dog Treats)\b", "", t)
        tail = " ".join(t.split()[:6])
        fl = re.search(r",\s*([A-Za-z][A-Za-z &]+)$", product)       # «…, Salmon» — вкус
        if fl and not re.search(r"pack|refill|diffuser", fl.group(1), re.I) and fl.group(1) not in tail:
            tail += f" ({fl.group(1).strip()})"
    return f"фото от блогера · {tail}" if tail else "фото от блогера"


def _clean_md(text: str) -> str:
    return re.sub(r"^```(?:markdown)?\s*|\s*```$", "", (text or "").strip()).strip()


def commit_to_plan(posts: list[dict], brand: str = "BelovedPets",
                   write_briefs: bool = True) -> dict:
    """Write the generated month into the shared plan + save each script as its ТЗ.

    Returns {"added": n, "briefs": n, "errors": [...]}. Existing posts are left alone —
    this only appends, so a second run won't wipe anything the team edited by hand.
    """
    # Раньше каждый пост отдельно скачивал и сохранял весь план, а каждое ТЗ — дважды
    # всю таблицу ТЗ: на 11 постов ~40 запросов, сайт «глючил» (Мария, 2026-11-11).
    # Теперь: план читается один раз, ТЗ уходят одним запросом, план — одним.
    import uuid
    from views.content_plan import _save_plan, load_plan
    from models import plan_briefs

    errors: list[str] = []
    stamp = date.today().strftime("%d.%m %H:%M")
    plan = load_plan(brand)
    entries: dict[str, dict] = {}
    added = 0

    existing = plan_briefs.load_all() or {}
    developed = 0
    for p in posts:
        if p.get("idea_id"):
            # Идея команды: ячейку не создаём, а дописываем к ней ТЗ. Уже есть ТЗ — не трогаем.
            item = next((x for x in plan.get(p["date"], []) if x.get("id") == p["idea_id"]), None)
            if not item or (existing.get(p["idea_id"]) or {}).get("text") or p["idea_id"] in entries:
                continue
            for f in ("format", "owner"):
                if not item.get(f) and p.get(f):
                    item[f] = p[f]
            body = _brief_text(p) if write_briefs else ""
            if body:
                entries[p["idea_id"]] = {"text": body, "link": "", "title": item.get("title", ""),
                                         "pillar": item.get("pillar", ""),
                                         "for": item.get("owner") or p.get("owner", "dina"),
                                         "updated": stamp, "wish": ""}
                developed += 1
            continue
        try:
            day = plan.setdefault(p["date"], [])
            if any(x.get("title") == p["title"] for x in day):
                continue                     # повторное нажатие не плодит дубли
            pid = f"{brand[:2].lower()}{p['date'].replace('.', '')}{uuid.uuid4().hex[:3]}"
            item = {"id": pid, "title": p["title"].strip(), "type": p["type"],
                    "pillar": p.get("pillar", "").strip(), "owner": p.get("owner", ""),
                    "format": p.get("format", "")}
            if p.get("experiment"):
                item["experiment"] = p["experiment"]
            if p.get("bank_id"):
                item["bank_id"] = p["bank_id"]
            day.append(item)
            added += 1
        except Exception as e:
            errors.append(f'{p.get("date")}: {e}')
            continue
        body = _brief_text(p) if write_briefs else ""
        if body:
            entries[pid] = {"text": body, "link": "", "title": p["title"],
                            "pillar": p.get("pillar", ""), "for": p.get("owner", "dina"),
                            "updated": stamp, "wish": ""}

    # Сначала ТЗ, потом план: если база не ответит, в календаре не будет постов без ТЗ.
    try:
        plan_briefs.save_many(entries)
    except Exception as e:
        return {"added": 0, "briefs": 0, "errors": [f"ТЗ не сохранились: {e}"]}
    if added or developed:
        _save_plan(brand, plan)
    return {"added": added, "developed": developed, "briefs": len(entries), "errors": errors}


_FORMAT_RU = {"reel": "Reel / видео", "carousel": "Карусель", "animation": "Анимация (оживление фото)",
              "lifestyle": "Life pic (статичное фото)", "blogger_photo": "Фото от блогера",
              "promo": "Промо", "static": "Статика"}


_GRAPHIC_FORMATS = {"blogger_photo", "carousel", "promo", "static"}


def _product_line(p: dict) -> str:
    """«**Товар:** <кратко> · ссылка». Полное название остаётся в плане (p["product"])."""
    link = p.get("product_url") or ""
    name = p["product"]
    try:
        from models.products import find_exact, short_name, by_asin
        m = re.search(r"/dp/([A-Z0-9]{10})", link)
        hit = (by_asin(m.group(1)) if m else None) or find_exact(name, p.get("brand") or "BelovedPets")
        if hit:
            name = short_name(hit["title"])
    except Exception:
        pass
    return f"**Товар:** {name}" + (f" · {link}" if link else "")


_GRAPHIC_KIND = {"carousel": "карусель", "blogger_photo": "статика · фото от блогера",
                 "promo": "статика · промо", "static": "статика"}
_VIDEO_KIND = {"reel": "рилс", "animation": "анимация фото", "lifestyle": "рилс"}
_NUM_LINE = re.compile(r"^\s*\d+[.:)]\s")


def _brief_text(p: dict) -> str:
    """Собрать ТЗ так, как его читает исполнитель в ячейке плана.

    Решение Марии (2026-11-13), лаконично:
      Вика — тип (статика / карусель до 4 слайдов), товар кратко + ссылка, надписи, подпись.
      Дина — тип (рилс / анимация фото), товар кратко + ссылка, обложка, до 3 сцен, подпись.
    Шрифты, цвета, плашки, айдентику и правила монтажа исполнители знают.
    Уже залитые ТЗ (ноябрь, декабрь) не пересобираются: текст пишется только при заливке.
    """
    fmt = p.get("format", "")
    script = (p.get("script") or "").strip()
    script = re.sub(r"^\s*\**\s*Идея\s*:?\**\s*:?.*(?:\n|$)", "", script).strip()
    caption = (p.get("caption") or "").strip()

    if fmt in _GRAPHIC_FORMATS:
        slides = [l.strip() for l in script.splitlines() if _NUM_LINE.match(l)][:4]
        kind = _GRAPHIC_KIND.get(fmt, "статика")
        if fmt == "carousel" and slides:
            kind = f"карусель, {len(slides)} " + ("слайда" if len(slides) > 1 else "слайд")
        parts = [f"**Тип креатива:** {kind}"]
        if p.get("product"):
            parts.append(_product_line(p))
        if fmt == "carousel" and slides:
            parts.append("**Надписи:**\n" + "\n".join(slides))
        else:
            text_on = script or (f'"{p["hook"]}"' if p.get("hook") else "")
            if text_on:
                parts.append(f"**Надпись на креативе:** {text_on}")
        if caption:
            parts.append(f"**Подпись к посту:** {caption}")
        return "\n\n".join(parts).strip()

    parts = [f"**Тип креатива:** {_VIDEO_KIND.get(fmt, 'рилс')}"]
    if p.get("product"):
        parts.append(_product_line(p))
    cover = (p.get("cover") or "").strip()
    if not cover and p.get("hook"):
        cover = ("фото — даст Маша. " if fmt == "animation" else "") + f'Надпись: "{p["hook"]}"'
    if cover:
        parts.append(f"**Обложка:** {cover}")
    scenes = [l.strip() for l in script.splitlines() if l.strip()][:3]
    if scenes:
        parts.append("**Сцены:**\n" + "\n".join(scenes))
    if caption:
        parts.append(f"**Подпись к посту:** {caption}")
    return "\n\n".join(parts).strip()
