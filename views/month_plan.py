"""Monthly Content Creation — Джек читает прошлые месяцы и пишет следующий целиком.

Отдельный раздел, а не блок внизу контент-плана: это самостоятельная работа на несколько
минут со своим черновиком и своей кнопкой публикации, и искать её под календарём никто
не догадается. Календарь остаётся местом, где план правят руками.
"""

from __future__ import annotations

import streamlit as st

from datetime import date

from views.content_plan import (TYPE_COLORS, _shift_month, _team_owners,
                                months_available)
from views.content_plan import month_label as month_label_for

_FMT_RU = {"reel": "🎬 рилс", "carousel": "🖼 карусель", "animation": "✨ анимация",
           "lifestyle": "📷 life pic", "static": "🖼 статика", "blogger_photo": "🐶 фото блогера", "promo": "🏷 промо"}


def render() -> None:
    from models import ig_insights, plan_analytics, plan_generator

    brand = st.session_state.get("brand", "BelovedPets")
    owners = _team_owners()

    st.markdown(f"# ✨ Monthly Content Creation · {brand}")

    analysis = plan_analytics.collect(brand)
    photo_owner, video_owner = plan_generator.owners_from_history(analysis)
    photo_name = owners.get(photo_owner, {}).get("name", photo_owner.title())
    video_name = owners.get(video_owner, {}).get("name", video_owner.title())

    st.caption("Джек читает прошлые месяцы — темы, форматы, наши ТЗ, цифры Instagram — "
               "и пишет весь следующий месяц: темы, хуки, готовые скрипты, подписи. "
               f"Постим 3 раза в неделю: {plan_generator.posting_days_ru(brand)}. "
               f"Первый пост недели — фото от блогера у {photo_name}, "
               f"остальное — карусели, анимации и рилсы разных форматов у {video_name}. "
               "Исполнители подставляются по прошлым месяцам этого бренда.")

    with st.expander("📊 Что Джек увидел в прошлых месяцах", expanded=False):
        st.markdown(plan_analytics.as_markdown(analysis))
        st.markdown("---")
        st.markdown("**Цифры Instagram по постам.** Обычно их приносит сборщик на маке "
                    "(`scripts/ig_safari.py` — Джек сам читает наш профиль в Safari). "
                    "Ручная выгрузка ниже — запасной путь.")
        up = st.file_uploader("Загрузить выгрузку CSV (Meta Business Suite → Insights → Экспорт)",
                              type=["csv"], key="ig_csv_up")
        if up is not None and st.button("Загрузить цифры", key="ig_csv_btn"):
            rows, note = ig_insights.parse_csv(up.getvalue())
            if not rows:
                st.error(note)
            else:
                added = ig_insights.merge(rows, brand)
                st.success(f"{note}. Новых постов добавлено: {added}. "
                           f"Всего в базе: {len(ig_insights.load(brand))}.")
                st.rerun()
        have = ig_insights.load(brand)
        if have:
            st.caption(f"В базе {len(have)} постов с цифрами. Обновится у всей команды.")

    gc1, gc2 = st.columns([1, 1])
    # Месяцы считаются от сегодняшней даты (прошлый, текущий и горизонт вперёд) —
    # список больше не вписан в код, новый месяц не нужно добавлять руками.
    # По умолчанию предлагаем следующий месяц: текущий обычно уже расписан.
    months = months_available()
    _labels = list(months.keys())
    _next = month_label_for(*_shift_month(date.today().year, date.today().month, 1))
    month_label = gc1.selectbox("Месяц, который писать", _labels,
                                index=_labels.index(_next) if _next in _labels else 0,
                                key="gen_month_sel")
    gy, gm = months[month_label]
    weeks = plan_generator.month_skeleton(gy, gm, brand=brand, photo_owner=photo_owner,
                                          video_owner=video_owner)
    ideas = plan_analytics.month_posts(brand, f"{gm:02d}")
    weeks = plan_generator.apply_team_ideas(weeks, ideas, photo_owner)
    n_free = plan_generator.free_slots(weeks)
    gc2.metric("Джек напишет постов", n_free,
               f"{sum(len(w) for w in weeks)} дней постинга · {len(ideas)} идей команды уже в плане")
    to_develop = plan_generator.ideas_to_develop(ideas)
    if ideas:
        with st.expander(f"💡 Ваши идеи на {month_label.lower()} ({len(ideas)}) — "
                         f"Джек допишет ТЗ к {len(to_develop)} без ТЗ", expanded=False):
            st.caption("Название и дату Джек не меняет. Где ТЗ ещё нет — допишет формат, товар, "
                       "надписи или сцены и подпись. Где ТЗ уже есть — не трогает.")
            for i in ideas:
                mark = "✍️ допишет ТЗ" if i in to_develop else "✅ ТЗ есть"
                st.markdown(f"- {i['date']} · {_FMT_RU.get(i['format'], 'идея')} — {i['title']} · {mark}")
            off = [i for i in ideas
                   if date(gy, gm, int(i["date"].split(".")[0])).weekday()
                   not in plan_generator.posting_days(brand)]
            if off:
                st.caption("Не в дни постинга (" + plan_generator.posting_days_ru(brand) + "): "
                           + ", ".join(i["date"] for i in off) + ". Джек их оставит как есть.")

    _idea_bank(brand)
    _offer_saved_draft(brand, gy, gm, month_label)

    market = st.selectbox("Рынок", ["US", "UK", "CA"], index=0, key="gen_month_market")
    extra = st.text_area(
        "Что учесть в этом месяце (пожелания, акции, новинки)",
        key="gen_month_extra", height=90,
        placeholder="напр. запуск нового вкуса; акцент на возврате в школу")

    if st.button(f"🐾 Джек, напиши план на {month_label.lower()}", type="primary",
                 use_container_width=True, key="gen_month_go"):
        if not analysis.get("total") and not ideas:
            st.error("В базе нет прошлых месяцев — Джеку не на чем строить анализ.")
        elif not n_free and not to_develop:
            st.info("Все дни постинга этого месяца уже заняты вашими постами с ТЗ — писать нечего.")
        else:
            _generate(plan_generator, weeks, analysis, gy, gm, brand, market, extra,
                      owners, month_label, ideas)

    _preview(brand, owners)


def _idea_bank(brand: str) -> None:
    """Банк идей без даты: кидаете в любой момент, Джек берёт 2-4 в каждый месяц."""
    from models import idea_bank
    try:
        items = idea_bank.load(brand)
    except Exception:
        items = []
    free = [i for i in items if not i.get("used")]
    with st.expander(f"🏦 Банк идей · {brand} — свободных {len(free)}", expanded=False):
        st.caption("Идеи без даты. При планировании месяца Джек выбирает 2-4 подходящие, "
                   "делает из них посты и помечает, в какой месяц они ушли.")
        txt = st.text_area("Новая идея — текст или ссылка на рилс (Instagram / TikTok)",
                           key="bank_new", height=80,
                           placeholder="напр. рубрика «кот против пылесоса»\n"
                                       "или https://www.instagram.com/reel/… + пару слов, что понравилось")
        if st.button("➕ Добавить в банк — Джек разберёт", key="bank_add"):
            has_link = "http" in (txt or "")
            with st.spinner("🐾 Джек смотрит ролик и думает, как адаптировать нам…" if has_link
                            else "🐾 Джек думает, как адаптировать идею нам…"):
                item = idea_bank.add(brand, txt, by=st.session_state.get("user_name", ""))
            if item:
                st.session_state.pop("bank_new", None)
                st.rerun()
            else:
                st.error("Не сохранилось — пустой текст или нет связи с базой.")
        for i in free:
            c1, c2, c3 = st.columns([8, 1, 1])
            label = ("🔗 " if i.get("url") else "💬 ") + i["text"]
            c1.markdown(f"**{label[:160]}**  \n<span style='color:#888;font-size:0.8em'>"
                        f"{i.get('added', '')}</span>", unsafe_allow_html=True)
            if c2.button("🔄", key=f"bank_re_{i['id']}", help="Разобрать заново"):
                with st.spinner("🐾 Джек разбирает заново…"):
                    idea_bank.reanalyse(brand, i["id"])
                st.rerun()
            if c3.button("✕", key=f"bank_del_{i['id']}", help="Удалить идею"):
                idea_bank.remove(brand, i["id"])
                st.rerun()
            if i.get("analysis"):
                with st.expander("🐾 Разбор Джека: почему зашло и как адаптировать нам"):
                    st.markdown(i["analysis"])
        used = [i for i in items if i.get("used")]
        if used:
            st.caption("Уже в планах: " + "; ".join(f"{i['text'][:50]} → {i['used']}" for i in used[-10:]))


def draft_key(brand: str, year: int, month: int) -> str:
    """Ключ готового черновика месяца в общей базе (его кладёт Claude вне сайта)."""
    return f"month_draft_{brand.lower()}_{year}-{month:02d}"


def _offer_saved_draft(brand: str, year: int, month: int, month_label: str) -> None:
    """Готовый черновик, написанный вне сайта (когда генерация на сайте глючит).

    Только открывает его в превью ниже — в план он попадает той же кнопкой «Залить»,
    после того как Мария его посмотрела.
    """
    from models import shared_store
    key = draft_key(brand, year, month)
    try:
        draft = shared_store.get_json(key, None)
    except Exception:
        draft = None
    if not isinstance(draft, dict) or not draft.get("posts"):
        return
    n = len(draft["posts"])
    st.info(f"📝 Есть готовый черновик на {month_label.lower()}: {n} постов "
            f"({draft.get('author', 'Claude')}, {draft.get('created', '')}).")
    if st.button(f"📂 Открыть черновик ({n} постов)", key="gen_month_open_saved",
                 use_container_width=True):
        st.session_state["gen_month_posts"] = draft["posts"]
        st.session_state["gen_month_strategy"] = draft.get("strategy") or {}
        st.session_state["gen_month_brand"] = brand
        st.session_state["gen_month_label"] = month_label
        st.session_state["gen_month_failed"] = []
        st.session_state["gen_month_draft_key"] = key
        st.rerun()


def _generate(plan_generator, weeks, analysis, gy, gm, brand, market, extra,
              owners, month_label, ideas=None) -> None:
    from models import idea_bank, plan_analytics
    progress = st.progress(0.0, text="Джек разбирает ЦА и придумывает концепты месяца, "
                                     "потом строго их проверяет (1-2 мин)…")
    try:
        bank = idea_bank.unused(brand)
    except Exception:
        bank = []
    recent = plan_analytics.recent_titles(brand, gm)
    strategy = plan_generator.month_strategy(analysis, gy, gm, brand, extra,
                                             slots=plan_generator.free_slots(weeks),
                                             ideas=ideas, bank=bank, recent=recent)
    if strategy.get("error"):
        progress.empty()
        st.error(f"Не получилось собрать стратегию: {strategy['error']}")
        if strategy.get("raw"):
            st.code(strategy["raw"])
        return

    name_map = {s: m.get("name", s) for s, m in owners.items()}
    posts: list[dict] = []
    used: list[str] = [i["title"] for i in ideas or []] + recent[:40]
    failed: list[int] = []
    bank_used: set[str] = set()
    errors: list[str] = []
    for i, week in enumerate(weeks, start=1):
        if all(s.get("fixed") for s in week):
            continue                         # неделя целиком из идей команды
        progress.progress(i / (len(weeks) + 1),
                          text=f"Неделя {i} из {len(weeks)} — пишет посты, хуки и скрипты…")
        try:
            got = plan_generator.generate_week(
                week, strategy, analysis, i, len(weeks), brand=brand, market=market,
                used_titles=used, extra=extra, owner_names=name_map,
                team_roles={s: m.get("role", "") for s, m in owners.items()},
                ideas=ideas,
                bank=plan_generator._bank_for_month(strategy, bank, bank_used))
        except Exception as e:  # noqa: BLE001 — одна неделя не должна ронять весь месяц
            errors.append(f"неделя {i}: {type(e).__name__}: {str(e)[:150]}")
            got = []
        if not got:
            failed.append(i)
            continue
        posts.extend(got)
        used.extend(p["title"] for p in got)
        bank_used.update(p["bank_id"] for p in got if p.get("bank_id"))
    to_develop = plan_generator.ideas_to_develop(ideas)
    if to_develop:
        progress.progress(len(weeks) / (len(weeks) + 1),
                          text=f"Дописывает ТЗ к вашим идеям ({len(to_develop)})…")
        try:
            posts.extend(plan_generator.develop_ideas(
                to_develop, strategy, gy, brand=brand, market=market, extra=extra,
                team_roles={s: m.get("role", "") for s, m in owners.items()}))
        except Exception as e:  # noqa: BLE001
            errors.append(f"идеи команды: {type(e).__name__}: {str(e)[:150]}")
        posts.sort(key=lambda p: p.get("iso", ""))
    history = plan_generator._history_titles(analysis, n=300, recent=recent)
    for p in posts:
        if not p.get("idea_id"):
            p["similar_to"] = plan_generator.similar_to_history(p.get("title", ""), history)
    progress.empty()

    st.session_state["gen_month_posts"] = posts
    st.session_state["gen_month_strategy"] = strategy
    st.session_state["gen_month_brand"] = brand
    st.session_state["gen_month_label"] = month_label
    st.session_state["gen_month_failed"] = failed
    st.session_state["gen_month_errors"] = errors
    # Черновик — сразу в общую базу: если страница упадёт или вкладка закроется, план не
    # пропадёт, а появится кнопкой «📂 Открыть черновик».
    if posts:
        try:
            from datetime import datetime
            from models import shared_store
            key = draft_key(brand, gy, gm)
            shared_store.put_json(key, {"posts": posts, "strategy": strategy, "author": "Джек",
                                        "created": datetime.now().strftime("%d.%m %H:%M")})
            st.session_state["gen_month_draft_key"] = key
        except Exception:
            pass


def _preview(brand: str, owners: dict) -> None:
    posts = st.session_state.get("gen_month_posts") or []
    if not posts:
        return
    strategy = st.session_state.get("gen_month_strategy") or {}
    label = st.session_state.get("gen_month_label", "")
    failed = st.session_state.get("gen_month_failed") or []

    st.markdown("---")
    st.markdown(f"### Черновик плана · {label} · {len(posts)} постов")
    if failed:
        st.warning(f"Недели {', '.join(map(str, failed))} не сгенерировались — Джек не вернул "
                   f"валидный ответ. Их в черновике нет; можно перезапустить генерацию.")
    for err in st.session_state.get("gen_month_errors") or []:
        st.caption(f"⚙️ {err}")
    if st.session_state.get("gen_month_brand") != brand:
        st.warning("Черновик сделан для другого бренда — перегенерируй, прежде чем заливать.")

    if strategy.get("big_idea"):
        st.info(f"**Идея месяца.** {strategy['big_idea']}")
    aud = [a for a in strategy.get("audience") or [] if isinstance(a, dict)]
    if aud:
        with st.expander("👥 ЦА этого месяца — кому и о чём говорим", expanded=False):
            for a in aud[:4]:
                st.markdown(f"- **{a.get('segment', '')}** — {a.get('moment', '')}  \n"
                            f"  _{a.get('pain_or_desire', '')}_ · барьер: {a.get('barrier', '')}")
    cons = [c for c in strategy.get("concepts") or [] if isinstance(c, dict)]
    if cons:
        rev = {r.get("concept"): r for r in strategy.get("review") or [] if isinstance(r, dict)}
        st.markdown("**💡 Концепты месяца**")
        for c in cons[:6]:
            r = rev.get(c.get("name")) or {}
            sc = r.get("scores") or {}
            score = (f" · оценка {round(sum(v for v in sc.values() if isinstance(v, (int, float))) / max(len(sc), 1), 1)}/5"
                     if sc else "")
            with st.expander(f"{c.get('name', '')}{score}", expanded=False):
                st.markdown(f"**Для кого:** {c.get('segment', '')}  \n"
                            f"**Инсайт:** {c.get('insight', '')}  \n"
                            f"**Идея:** {c.get('idea', '')}  \n"
                            f"**Почему мы:** {c.get('why_us', '')}  \n"
                            f"**Новизна:** {c.get('new_vs_history', '')}")
                hooks = c.get("hooks") or []
                if hooks:
                    st.markdown("**Хуки:** " + " · ".join(f"“{h}”" for h in hooks if isinstance(h, str)))
                if r.get("verdict"):
                    st.caption(f"Ревью креативного директора: {r['verdict']}")
    if strategy.get("wishes"):
        st.markdown("**📌 Как закрыты ваши пожелания**\n"
                    + "\n".join(f"- {x}" for x in strategy["wishes"][:6]))
    if strategy.get("experiments"):
        st.markdown("**🧪 Эксперименты месяца**\n" + "\n".join(
            f"- {e.get('hypothesis', e) if isinstance(e, dict) else e}"
            + (f" · смотрим: {e['metric']}" if isinstance(e, dict) and e.get("metric") else "")
            for e in strategy["experiments"][:3]))
    if strategy.get("team_ideas"):
        st.markdown("**💡 Что Джек увидел в ваших идеях**\n"
                    + "\n".join(f"- {x}" for x in strategy["team_ideas"][:5]))
    sc1, sc2, sc3 = st.columns(3)
    for col, key, title in ((sc1, "keep", "✅ Оставляем"), (sc2, "drop", "🚫 Провалилось по цифрам"),
                            (sc3, "new_bets", "🎲 Новые заходы")):
        items = strategy.get(key) or []
        if items:
            col.markdown(f"**{title}**\n" + "\n".join(f"- {x}" for x in items[:5]))
    if strategy.get("data_gaps"):
        st.caption("Чего не хватило Джеку для точности: " + "; ".join(strategy["data_gaps"]))

    st.markdown("**Посты**")
    for p in posts:
        owner_name = owners.get(p["owner"], {}).get("name", p["owner"])
        tags = ("💡 ваша идея · " if p.get("idea_id") else "") + \
               ("🏦 из банка · " if p.get("bank_id") else "") + \
               ("🧪 эксперимент · " if p.get("experiment") else "") + \
               ("♻️ похоже на прошлое · " if p.get("similar_to") else "")
        head = (f'{p["date"]} · {tags}{_FMT_RU.get(p["format"], p["format"])} · {owner_name} — '
                f'{p["title"]}')
        with st.expander(head, expanded=False):
            if p.get("hook"):
                st.markdown(f'**Хук:** {p["hook"]}')
            if p.get("product"):
                link = f' · [Amazon]({p["product_url"]})' if p.get("product_url") else ""
                st.caption(f'Товар: {p["product"]}{link} · пиллар: {p.get("pillar") or "—"} · '
                           f'категория: {TYPE_COLORS.get(p["type"], {}).get("label") or p["type"]}')
            if p.get("script"):
                st.markdown(p["script"])
            if p.get("caption"):
                st.markdown(f'**Подпись (EN):**\n\n{p["caption"]}')
            if p.get("concept"):
                st.caption(f'💡 Концепт: {p["concept"]}')
            if p.get("similar_to"):
                st.warning(f'♻️ Похоже на прошлый пост «{p["similar_to"]}» — проверь, не повтор ли.')
            if p.get("experiment"):
                st.caption(f'🧪 Проверяем: {p["experiment"]}')
            if p.get("why"):
                st.caption(f'Почему в плане: {p["why"]}')

    st.markdown("")
    bc1, bc2 = st.columns([2, 1])
    with_briefs = bc2.checkbox("Сразу сохранить ТЗ", value=True, key="gen_month_briefs",
                               help="Скрипты лягут в комментарии к ячейкам — команда увидит сразу.")
    if bc1.button(f"📥 Залить {len(posts)} постов в контент-план", type="primary",
                  use_container_width=True, key="gen_month_commit"):
        from models import plan_generator
        res = plan_generator.commit_to_plan(posts, brand, write_briefs=with_briefs)
        if res["errors"]:
            st.error("Часть не записалась:\n" + "\n".join(f"- {e}" for e in res["errors"][:10]))
        try:
            from models import idea_bank
            idea_bank.mark_used(brand, [p.get("bank_id", "") for p in posts],
                                st.session_state.get("gen_month_label", ""))
        except Exception:
            pass
        st.success(f"Добавлено постов: {res['added']} · ТЗ к вашим идеям: {res.get('developed', 0)} · "
                   f"ТЗ сохранено всего: {res['briefs']}. Смотри в разделе «📅 Content Plan».")
        used = st.session_state.pop("gen_month_draft_key", None)
        if used and (res["added"] or res.get("developed")):
            from models import shared_store
            shared_store.put_json(used, {})      # залитый черновик второй раз не предлагаем
        for k in ("gen_month_posts", "gen_month_strategy", "gen_month_failed"):
            st.session_state.pop(k, None)
        st.rerun()
    if st.button("Очистить черновик", key="gen_month_clear"):
        for k in ("gen_month_posts", "gen_month_strategy", "gen_month_failed"):
            st.session_state.pop(k, None)
        st.rerun()
