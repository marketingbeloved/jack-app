"""Monthly Content Creation — Джек читает прошлые месяцы и пишет следующий целиком.

Отдельный раздел, а не блок внизу контент-плана: это самостоятельная работа на несколько
минут со своим черновиком и своей кнопкой публикации, и искать её под календарём никто
не догадается. Календарь остаётся местом, где план правят руками.
"""

from __future__ import annotations

import streamlit as st

from views.content_plan import MONTHS, TYPE_COLORS, _team_owners

_FMT_RU = {"reel": "🎬 рилс", "carousel": "🖼 карусель", "animation": "✨ анимация",
           "lifestyle": "📷 life pic", "blogger_photo": "🐶 фото блогера", "promo": "🏷 промо"}


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
               f"Структура держится: 1 пост в неделю — фото от блогера у {photo_name}, "
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
    month_label = gc1.selectbox("Месяц, который писать", list(MONTHS.keys()),
                                index=len(MONTHS) - 1, key="gen_month_sel")
    gy, gm = MONTHS[month_label]
    weeks = plan_generator.month_skeleton(gy, gm, photo_owner=photo_owner,
                                          video_owner=video_owner)
    gc2.metric("Слотов в месяце", sum(len(w) for w in weeks),
               f"{len(weeks)} недель · {len(weeks)} фото блогера")

    market = st.selectbox("Рынок", ["US", "UK", "CA"], index=0, key="gen_month_market")
    extra = st.text_area(
        "Что учесть в этом месяце (пожелания, акции, новинки)",
        key="gen_month_extra", height=90,
        placeholder="напр. запуск нового вкуса; акцент на возврате в школу")

    if st.button(f"🐾 Джек, напиши план на {month_label.lower()}", type="primary",
                 use_container_width=True, key="gen_month_go"):
        if not analysis.get("total"):
            st.error("В базе нет прошлых месяцев — Джеку не на чем строить анализ.")
        else:
            _generate(plan_generator, weeks, analysis, gy, gm, brand, market, extra,
                      owners, month_label)

    _preview(brand, owners)


def _generate(plan_generator, weeks, analysis, gy, gm, brand, market, extra,
              owners, month_label) -> None:
    progress = st.progress(0.0, text="Джек читает прошлые месяцы…")
    strategy = plan_generator.month_strategy(analysis, gy, gm, brand, extra)
    if strategy.get("error"):
        progress.empty()
        st.error(f"Не получилось собрать стратегию: {strategy['error']}")
        if strategy.get("raw"):
            st.code(strategy["raw"])
        return

    name_map = {s: m.get("name", s) for s, m in owners.items()}
    posts: list[dict] = []
    used: list[str] = []
    failed: list[int] = []
    for i, week in enumerate(weeks, start=1):
        progress.progress(i / (len(weeks) + 1),
                          text=f"Неделя {i} из {len(weeks)} — пишет посты, хуки и скрипты…")
        got = plan_generator.generate_week(
            week, strategy, analysis, i, len(weeks), brand=brand, market=market,
            used_titles=used, extra=extra, owner_names=name_map,
            team_roles={s: m.get("role", "") for s, m in owners.items()})
        if not got:
            failed.append(i)
            continue
        posts.extend(got)
        used.extend(p["title"] for p in got)
    progress.empty()

    st.session_state["gen_month_posts"] = posts
    st.session_state["gen_month_strategy"] = strategy
    st.session_state["gen_month_brand"] = brand
    st.session_state["gen_month_label"] = month_label
    st.session_state["gen_month_failed"] = failed


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
    if st.session_state.get("gen_month_brand") != brand:
        st.warning("Черновик сделан для другого бренда — перегенерируй, прежде чем заливать.")

    if strategy.get("big_idea"):
        st.info(f"**Идея месяца.** {strategy['big_idea']}")
    sc1, sc2, sc3 = st.columns(3)
    for col, key, title in ((sc1, "keep", "✅ Оставляем"), (sc2, "drop", "🚫 Убираем"),
                            (sc3, "new_bets", "🎲 Новые заходы")):
        items = strategy.get(key) or []
        if items:
            col.markdown(f"**{title}**\n" + "\n".join(f"- {x}" for x in items[:5]))
    if strategy.get("data_gaps"):
        st.caption("Чего не хватило Джеку для точности: " + "; ".join(strategy["data_gaps"]))

    st.markdown("**Посты**")
    for p in posts:
        owner_name = owners.get(p["owner"], {}).get("name", p["owner"])
        head = (f'{p["date"]} · {_FMT_RU.get(p["format"], p["format"])} · {owner_name} — '
                f'{p["title"]}')
        with st.expander(head, expanded=False):
            if p.get("hook"):
                st.markdown(f'**Хук:** {p["hook"]}')
            if p.get("product"):
                st.caption(f'Товар: {p["product"]} · пиллар: {p.get("pillar") or "—"} · '
                           f'категория: {TYPE_COLORS.get(p["type"], {}).get("label") or p["type"]}')
            if p.get("script"):
                st.markdown(p["script"])
            if p.get("caption"):
                st.markdown(f'**Подпись (EN):**\n\n{p["caption"]}')
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
        st.success(f"Добавлено постов: {res['added']} · ТЗ сохранено: {res['briefs']}. "
                   f"Смотри в разделе «📅 Content Plan».")
        for k in ("gen_month_posts", "gen_month_strategy", "gen_month_failed"):
            st.session_state.pop(k, None)
        st.rerun()
    if st.button("Очистить черновик", key="gen_month_clear"):
        for k in ("gen_month_posts", "gen_month_strategy", "gen_month_failed"):
            st.session_state.pop(k, None)
        st.rerun()
