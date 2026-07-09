"""Jack Workspace — Darya and Tanya talk to Jack here. Lottie animated Jack on the side."""

import html
import re
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

from utils.jack_svg import render_jack
from models.jack_engine import load_concepts, update_status, delete_concept

# Make scripts/jack_notion.py importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_URL_RE = re.compile(r'(https?://[^\s<]+)')


def _linkify(text: str) -> str:
    """URL в сообщении → кликабельная ссылка (ссылку на ТЗ в Notion делаем кнопкой-текстом)."""
    def _repl(m):
        url = m.group(1)
        label = "🔗 Открыть ТЗ в Notion" if "notion" in url else url
        return (f'<a href="{url}" target="_blank" '
                f'style="color:#1B339E;font-weight:700;text-decoration:underline;">{label}</a>')
    return _URL_RE.sub(_repl, text or "")


def _products_for(text: str) -> list:
    """Опознать товар(ы) из текста задачи через каталог (рус/англ).
    Возвращает короткие названия для запроса генерации; если не опознано —
    ['см. запрос'] (Джек возьмёт из контекста как раньше)."""
    try:
        from models.products import resolve_products, short_title
        matched = resolve_products(text)
        if matched:
            return [short_title(p) for p in matched]
    except Exception:
        pass
    return ["см. запрос"]


def _signals_ready_to_write(reply: str) -> bool:
    """Джек в чате сказал «иду писать» → это сигнал запустить генерацию по диалогу."""
    t = (reply or "").lower()
    return any(s in t for s in [
        "иду писать", "иду делать", "сейчас напишу", "сейчас набросаю", "напишу сейчас",
        "пишу рилс", "пишу скрипт", "набросаю", "погнал", "поехали",
        "это все данные", "это всё данные", "все данные, которые мне нужны",
        "всё, что мне нужно", "все что мне нужно",
    ])


def _assemble_brief_from_chat(messages: list, refs: str = "") -> str:
    """Собрать бриф из всего диалога — исходный запрос + все уточнения Дарьи/Тани."""
    lines = [f"- {m.get('text','')}" for m in messages[-14:]
             if m.get("who") in ("darya", "tanya") and m.get("text")]
    ctx = ("Собери рилс по этому диалогу — учти ВСЕ уточнения (товар/без товара, рынок, "
           "пожелания по формату):\n" + "\n".join(lines))
    if refs:
        ctx += "\n\nREFERENCES:\n" + refs
    return ctx


def _market_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(m in t for m in ["uk", "британ", "англи"]):
        return "UK"
    if any(m in t for m in ["canada", "канад", " ca "]):
        return "CA"
    return "US"


def _pillar_to_type(pillar: str) -> str:
    """Маппинг пиллара концепта → цвет ячейки в КП (как Дарины 3 категории)."""
    p = (pillar or "").lower()
    if any(k in p for k in ("promo", "amazon", "faire", "discount", "product", "selling")):
        return "selling"
    if any(k in p for k in ("trend", "meme", "comedy", "pov", "viral")):
        return "viral"
    return "engaging"


def _now_hm() -> str:
    return datetime.now().strftime("%H:%M")


def _now_dt() -> str:
    return datetime.now().strftime("%d.%m %H:%M")


# ─── Хранилище подписей (Captions) — в общей базе, чтобы не терялись после сна вкладки ──
def _captions_load(brand: str) -> list:
    try:
        from models import shared_store
        return shared_store.get_json(f"captions_{brand.lower()}", []) or []
    except Exception:
        return []


def _captions_save(brand: str, product: str, market: str, text: str) -> None:
    if not (text or "").strip():
        return
    try:
        from models import shared_store
        items = _captions_load(brand)
        items.insert(0, {"ts": _now_dt(), "product": product, "market": market, "text": text})
        shared_store.put_json(f"captions_{brand.lower()}", items[:30])  # держим последние 30
    except Exception:
        pass


def _captions_delete(brand: str, idx: int) -> None:
    try:
        from models import shared_store
        items = _captions_load(brand)
        if 0 <= idx < len(items):
            items.pop(idx)
            shared_store.put_json(f"captions_{brand.lower()}", items)
    except Exception:
        pass


def _launch_bg_generation(req: dict, t: str) -> None:
    """Запустить генерацию рилса В ФОНЕ (отдельный поток) + показать, что Джек пишет.
    Результат подтянет polling-фрагмент — даже если соединение сбросится или вкладку
    перезагрузят (job_id хранится в URL). Это и есть фикс «Джек не пишет» на free-облаке."""
    from models.jack_jobs import start_job
    job_id = start_job(req)
    st.session_state["active_job"] = job_id
    try:
        st.query_params["job"] = job_id   # переживёт перезагрузку вкладки
    except Exception:
        pass
    st.session_state["ws_messages"].append({"who": "jack", "text": (
        "🐾 Принял — пишу скрипт в фоне. Появится здесь сам через ~30–60 сек. "
        "Можно закрыть или обновить вкладку — не потеряется."), "time": t})
    st.session_state["jack_mood"] = "thinking"


@st.fragment(run_every=3)
def _poll_active_job() -> None:
    """Каждые 3 сек опрашивает фоновую задачу. Когда готово — вписывает скрипт в чат
    и делает полный rerun. Тикает только пока есть активная задача."""
    job_id = st.session_state.get("active_job")
    if not job_id:
        try:
            job_id = st.query_params.get("job")
        except Exception:
            job_id = None
    if not job_id:
        return
    if st.session_state.get("shown_job") == job_id:
        return  # результат этой задачи уже вписан — не дублируем
    from models.jack_jobs import get_job
    job = get_job(job_id)
    if not job or job.get("status") == "pending":
        st.info("🐾 **Джек пишет скрипт в фоне…** (~30–60 сек). Можно обновить вкладку — не потеряется.")
        return
    st.session_state["shown_job"] = job_id
    st.session_state.setdefault("ws_messages", [])
    if job.get("status") == "done" and job.get("result"):
        c = job["result"]
        st.session_state["draft_concept"] = c
        scenes = "\n".join(c.get("scenes", [])) or "(сцен нет)"
        why = c.get("why_it_works", "")
        st.session_state["ws_messages"].append({"who": "jack", "text": (
            f"Окей, набросал — **{c.get('title','—')}**\n\nИдея: {c.get('angle','—')}\n\n"
            f"**Script:**\n{scenes}\n\nCTA: {c.get('cta','—')}"
            + (f"\n\nПочему сработает: {why}" if why else "")
            + "\n\nСкажи что поменять — перепишу. Готово? Напиши «создай ТЗ Дине в Notion» — оформлю ей сразу."), "time": _now_hm()})
    else:
        st.session_state["ws_messages"].append({"who": "jack", "text": (
            f"Хм, не получилось — {job.get('error','')}. Нажми «Написать рилс сейчас» ещё раз."), "time": _now_hm()})
    st.session_state.pop("active_job", None)
    try:
        del st.query_params["job"]
    except Exception:
        pass
    st.session_state["jack_mood"] = "happy"
    st.rerun()


def render():
    brand = st.session_state.get("brand", "BelovedPets")
    st.markdown(f"# 🐾 Jack Workspace · {brand}")

    # ─── Layout: chat left, animated Jack right ─────────────────────────────
    col_chat, col_jack = st.columns([2, 1])

    with col_jack:
        st.markdown('<div class="section-label">Jack at work</div>', unsafe_allow_html=True)
        mood = st.session_state.get("jack_mood", "idle")
        action = {
            "idle":     "online · listening for tasks",
            "typing":   "typing reply…",
            "thinking": "reading the brief…",
            "happy":    "✨ on it!",
        }.get(mood, "online")
        st.markdown(render_jack(state="working", action_text=action, mood=mood), unsafe_allow_html=True)

        # ─── Change Jack's face (collapsed by default) ───────────────────────
        with st.expander("⚙️ Change Jack's face", expanded=False):
            from pathlib import Path
            import shutil
            import time as _t
            STATIC_AVATAR = Path(__file__).resolve().parent.parent / "static" / "avatars"
            STATIC_AVATAR.mkdir(parents=True, exist_ok=True)
            STATES = ["idle", "working", "thinking", "done", "error"]

            sub_up, sub_gallery = st.tabs(["📤 Upload", "🎭 Gallery"])
            with sub_up:
                st.caption("Drop a square portrait (JPG/PNG). Applies across the whole app.")
                uploaded = st.file_uploader(
                    "Drop Jack's portrait here",
                    type=["jpg", "jpeg", "png", "webp"],
                    label_visibility="collapsed",
                )
                if uploaded is not None:
                    data = uploaded.getvalue()
                    for state in STATES:
                        (STATIC_AVATAR / f"jack_{state}.png").write_bytes(data)
                        for old_ext in ("jpg", "jpeg", "webp"):
                            f = STATIC_AVATAR / f"jack_{state}.{old_ext}"
                            if f.exists():
                                f.unlink()
                    st.cache_data.clear()
                    (STATIC_AVATAR / ".bust").write_text(str(_t.time()))
                    st.success("✓ Jack updated — refreshing…")
                    st.rerun()

            with sub_gallery:
                st.caption("Pick a portrait. Click and Jack updates across the whole app.")
                CANDIDATES = sorted(
                    (Path(__file__).resolve().parent.parent / "static" / "candidates").glob("*.jpg"),
                    key=lambda p: int(p.stem.split("_", 1)[0]) if p.stem.split("_", 1)[0].isdigit() else 99,
                )

                cols = st.columns(3)
                for i, cand in enumerate(CANDIDATES):
                    with cols[i % 3]:
                        st.image(str(cand), use_container_width=True)
                        label = cand.stem.split("_", 1)[1].replace("_", " ") if "_" in cand.stem else cand.stem
                        if st.button(f"✓ Use {label}", key=f"use_{cand.stem}_{i}", use_container_width=True, type="primary"):
                            try:
                                for state in STATES:
                                    shutil.copyfile(cand, STATIC_AVATAR / f"jack_{state}.jpg")
                                    p_png = STATIC_AVATAR / f"jack_{state}.png"
                                    if p_png.exists():
                                        p_png.unlink()
                                st.cache_data.clear()
                                (STATIC_AVATAR / ".bust").write_text(str(_t.time()))
                                st.success(f"✓ Jack is now «{label}» — refreshing…")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to copy: {e}")

    with col_chat:
        st.markdown('<div class="section-label">Drop a task or a fix for Jack</div>', unsafe_allow_html=True)
        st.caption("Darya and Tanya can write here. Jack will pull comments, then go fill Content Plan + push briefs to Dina in Notion.")

        # Chat-like history
        if "ws_messages" not in st.session_state:
            st.session_state["ws_messages"] = [
                {"who": "jack", "text": "Привет, Даша 🐾 Я с тобой. Кидай задачу — буду писать, или скажи в чём ты застряла, поможем вместе.", "time": "now"},
            ]

        # render history
        for msg in st.session_state["ws_messages"]:
            who = msg["who"]
            if who == "jack":
                st.markdown(
                    f'<div class="msg jack-msg"><div class="msg-label">🐾 Jack · {msg["time"]}</div>{_linkify(msg["text"])}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="msg user-msg"><div class="msg-label">{msg["who"].title()} · {msg["time"]}</div>{msg["text"]}</div>',
                    unsafe_allow_html=True,
                )

        # Фоновая генерация: показываем статус и сами подтягиваем готовый скрипт.
        # Тикаем только когда задача есть (в сессии или в URL — переживает перезагрузку).
        _has_job = bool(st.session_state.get("active_job"))
        if not _has_job:
            try:
                _has_job = bool(st.query_params.get("job"))
            except Exception:
                _has_job = False
        if _has_job:
            _poll_active_job()

        # ─── Черновик Джека → СРАЗУ в контент-план (без цепочки апрува) ─────
        _draft = st.session_state.get("draft_concept")
        if _draft and not st.session_state.get("active_job"):
            from datetime import date as _date
            with st.container(border=True):
                st.markdown(f"📌 **Черновик Джека:** {_draft.get('title','рилс')}")
                dcol1, dcol2 = st.columns([1.3, 1])
                _pd = dcol1.date_input("Дата в КП", value=_date.today(),
                                       key="draft_plan_date", label_visibility="collapsed")
                if dcol2.button("📅 Поставить в КП", key="draft_to_plan",
                                use_container_width=True, type="primary"):
                    from views import content_plan
                    from models import plan_briefs
                    _b = _draft.get("brand", brand)
                    _dk = _pd.strftime("%d.%m")
                    _pid = content_plan.add_plan_post(
                        _b, _dk, _draft.get("title", "рилс"),
                        _pillar_to_type(_draft.get("pillar", "")),
                        _draft.get("pillar", ""), owner="dina")
                    # прицепляем сам скрипт как ТЗ к новому посту — чтобы не потерялся
                    _scr = "\n".join(_draft.get("scenes", []) or [])
                    _txt = (f"**{_draft.get('title','')}**\nHook: {_draft.get('hook','')}\n\n"
                            f"{_scr}\n\nCTA: {_draft.get('cta','')}")
                    try:
                        plan_briefs.save(_pid, _txt, title=_draft.get("title", ""),
                                         pillar=_draft.get("pillar", ""), updated=_now_hm())
                    except Exception:
                        pass
                    st.session_state["ws_messages"].append({"who": "jack", "text": (
                        f"✓ Поставил «{_draft.get('title','рилс')}» в контент-план на {_dk} "
                        f"(🎬 Дина), скрипт сохранил в ТЗ. Видит вся команда."), "time": _now_hm()})
                    st.session_state.pop("draft_concept", None)
                    st.rerun()
                # ─── Прямая кнопка: оформить ТЗ Дине в Notion сразу из черновика ───
                if st.button("📨 Создать ТЗ Дине в Notion", key="draft_to_notion",
                             use_container_width=True):
                    from models.jack_engine import (
                        promote_to_approve, update_status, autopush_to_notion,
                        load_concepts as _lcn,
                    )
                    promote_to_approve(_draft)
                    update_status(_draft["id"], "approved")
                    _fresh = next((x for x in _lcn() if x.get("id") == _draft.get("id")), _draft)
                    with st.spinner("🐾 Джек оформляет ТЗ Дине в Notion…"):
                        _ap = autopush_to_notion(_fresh)
                    if _ap.get("url"):
                        _msg = (f"✓ Готово — ТЗ «{_draft.get('title','—')}» у Дины в Notion (база Videos):\n"
                                f"{_ap['url']}")
                    elif _ap.get("skipped"):
                        _msg = f"«{_draft.get('title','—')}» уже лежит у Дины в Notion — не дублирую."
                    else:
                        _msg = (f"⚠️ Не смог записать в Notion: {_ap.get('error','неизвестная ошибка')}. "
                                f"Проверь NOTION_TOKEN в secrets и что приложение перезагружено.")
                    st.session_state["ws_messages"].append({"who": "jack", "text": _msg, "time": _now_hm()})
                    st.session_state.pop("draft_concept", None)
                    st.rerun()
                st.caption("🎬 «Создать ТЗ Дине» — оформит скрипт в Notion Дине сразу. 📅 «Поставить в КП» — в контент-план на дату. Обычно нужно и то, и то.")

        # Кто пишет — ВНЕ формы и с key, чтобы выбор не сбрасывался; имена из общей команды
        try:
            from models import shared_store
            _team_names = [m.get("name") for m in shared_store.get_team() if m.get("name")] or ["Darya", "Tanya"]
        except Exception:
            _team_names = ["Darya", "Tanya"]
        if st.session_state.get("ws_sender") not in _team_names:
            st.session_state.pop("ws_sender", None)
        sender = st.selectbox("Кто пишет", _team_names, key="ws_sender",
                              label_visibility="collapsed")

        # ─── ⚙️ Инструкции Джеку — постоянные правила «делай так-то» ──────────
        # И Дарья, и Таня. Применяются ко ВСЕМ ответам Джека (концепты/ТЗ/чат),
        # хранятся в общей базе → видят все, переживают ребут. Это НЕ правка кода,
        # а управление поведением Джека словами.
        _rules_brand = "Tobydic" if sender.lower() == "tanya" else brand
        with st.expander(f"⚙️ Инструкции Джеку · {_rules_brand} — чему научить (действует всегда)", expanded=False):
            st.caption("Пиши правила простым текстом — Джек будет соблюдать их в каждом ответе. "
                       "Напр.: «всегда добавляй UK-флаг», «хук ≤ 3 сек», «не используй слово cure», "
                       "«CTA всегда про link in bio». Видит вся команда.")
            from models import jack_lessons
            with st.form("add_jack_rule", clear_on_submit=True):
                rule_txt = st.text_input("Новое правило", key="new_rule_txt",
                                         placeholder="напр.: всегда упоминай, что это supplement, не medicine")
                if st.form_submit_button("➕ Добавить правило", use_container_width=True) and rule_txt.strip():
                    jack_lessons.add_rule(_rules_brand, rule_txt, author=sender)
                    st.success("✓ Джек запомнил — применит во всех следующих ответах.")
                    st.rerun()
            _rules = jack_lessons.list_rules(_rules_brand)
            if _rules:
                st.caption(f"Активные правила ({len(_rules)}):")
                for r in _rules:
                    rc1, rc2 = st.columns([6, 1])
                    _who = f" · _{r['author']}_" if r.get("author") else ""
                    rc1.markdown(f"• {r.get('text','')}{_who}")
                    if rc2.button("🗑", key=f"delrule_{r.get('ts')}", help="удалить правило"):
                        jack_lessons.delete_rule(r.get("ts"))
                        st.rerun()
            else:
                st.caption("Пока правил нет — Джек работает по базовым настройкам.")

        # ─── ✍️ Гарантированный запуск: написать рилс СЕЙЧАС по всему диалогу ──
        # Чтобы Джек не зацикливался на уточнениях — Дарья/Таня в любой момент жмут
        # кнопку, и он пишет скрипт по всему сказанному выше (не ждёт «иду писать»).
        _said = [m for m in st.session_state.get("ws_messages", []) if m.get("who") in ("darya", "tanya")]
        if _said and not st.session_state.get("active_job") and st.button(
                "✍️ Написать рилс сейчас (по всему, что сказали выше)",
                use_container_width=True, key="force_write"):
            t = datetime.now().strftime("%H:%M")
            eff_brand = "Tobydic" if sender.lower() == "tanya" else brand
            all_txt = " ".join(m.get("text", "") for m in _said)
            req = {
                "brand": eff_brand, "n": 1, "markets": [_market_from_text(all_txt)],
                "products": _products_for(all_txt),
                "pillars": ["Amazon Video"] if "amazon" in all_txt.lower() else [],
                "context": _assemble_brief_from_chat(st.session_state["ws_messages"]),
            }
            _launch_bg_generation(req, t)
            st.rerun()

        # input
        with st.form("jack_msg", clear_on_submit=True):
            user_text = st.text_area("Your task / feedback for Jack", height=80, placeholder="e.g. 'переделай UK Eye Wash рилс — слишком грустно начало', 'возьми идею Pet Honesty 2nd-dog меме для Calming Chews'", label_visibility="collapsed")
            sent = st.form_submit_button("Send", type="primary", use_container_width=True)
            if sent and user_text.strip():
                t = datetime.now().strftime("%H:%M")
                st.session_state["ws_messages"].append({"who": sender.lower(), "text": user_text.strip(), "time": t})
                st.session_state["jack_mood"] = "thinking"

                # МГНОВЕННАЯ обратная связь: история сверху отрендерилась ещё БЕЗ этого
                # сообщения (форма очистилась) — поэтому эхо + явный баннер «Джек пишет»
                # прямо тут, чтобы не выглядело «ничего не происходит» все 20-40 сек.
                st.markdown(
                    f'<div class="msg user-msg"><div class="msg-label">{sender} · {t}</div>'
                    f'{html.escape(user_text.strip())}</div>',
                    unsafe_allow_html=True,
                )
                st.info("🐾 **Джек принял задачу…**")

                # Detect URLs and try to read them (TikTok / IG / YouTube / Drive / web pages)
                import re
                import requests as _rq
                urls = re.findall(r'https?://\S+', user_text)
                refs_context = ""
                drive_url = None
                for url in urls[:5]:
                    if "drive.google.com" in url:
                        drive_url = url
                        continue
                    try:
                        r = _rq.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, allow_redirects=True)
                        if r.status_code == 200:
                            page_html = r.text[:80_000]
                            # Pull og:title / og:description / view counts
                            m_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', page_html)
                            m_desc = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', page_html)
                            m_views = re.search(r'"(playCount|view_count|viewCount)"\s*:\s*(\d+)', page_html)
                            m_likes = re.search(r'"(diggCount|like_count|likeCount)"\s*:\s*(\d+)', page_html)
                            piece = f"\n--- {url} ---\n"
                            if m_title: piece += f"Title: {m_title.group(1)}\n"
                            if m_desc: piece += f"Desc: {m_desc.group(1)[:300]}\n"
                            if m_views: piece += f"Views: {m_views.group(2)}\n"
                            if m_likes: piece += f"Likes: {m_likes.group(2)}\n"
                            refs_context += piece
                    except Exception:
                        pass

                from models.jack_chat import jack_chat_reply, looks_like_full_brief

                if drive_url and not looks_like_full_brief(user_text):
                    # Just acknowledge the drive link, in a human voice
                    with st.spinner("🐾 Jack читает…"):
                        reply = jack_chat_reply(
                            st.session_state["ws_messages"][:-1],
                            user_text + "\n\n(Drive URL detected — без Service Account я внутрь не залезу)",
                            refs_context,
                            brand=("Tobydic" if sender.lower() == "tanya" else brand),
                        )
                    st.session_state["ws_messages"].append({"who": "jack", "text": reply, "time": t})
                    st.session_state["jack_mood"] = "happy"
                    st.rerun()

                # Brand auto-detection from sender: Tanya → Tobydic, others → current sidebar brand
                effective_brand = "Tobydic" if sender.lower() == "tanya" else brand

                # Notion-push triggers — Дарья прямо говорит «иди создай ТЗ Дине в Notion».
                # Оформляем ТЗ в базе Videos СРАЗУ (ссылки не обязательны — Дина берёт с Диска).
                notion_triggers = [
                    "создай тз", "оформи тз", "иди создай", "тз дине", "тз для дины",
                    "дине в notion", "дине в ноуш", "дине в ноушн", "отправь дине",
                    "пушай в notion", "пушни в notion", "в ноушн дине", "создай ноушн",
                ]
                if any(tr in user_text.lower() for tr in notion_triggers):
                    from models.jack_engine import promote_to_approve, update_status, autopush_to_notion, load_concepts as _lcn
                    _draft = st.session_state.get("draft_concept")
                    if _draft:
                        # Свежий концепт прямо из чата → сохранить и запушить его.
                        promote_to_approve(_draft)                 # сохранить (проставит id)
                        update_status(_draft["id"], "approved")    # сразу approved
                        _target_id = _draft.get("id")
                    else:
                        # Нет чат-драфта → берём самый свежий концепт, которого ещё нет в Notion.
                        _cands = [x for x in _lcn() if not x.get("notion_url")]
                        _target_id = _cands[0].get("id") if _cands else None
                    _fresh = next((x for x in _lcn() if x.get("id") == _target_id), None) if _target_id else None
                    if not _fresh:
                        reply = ("Пока нечего отправлять Дине — сначала пришли бриф, я сделаю концепт, "
                                 "потом скажи «создай ТЗ Дине в Notion». Или одобри концепт в Pipeline (✅ Approve).")
                        st.session_state["jack_mood"] = "neutral"
                    else:
                        with st.spinner("🐾 Джек оформляет ТЗ Дине в Notion…"):
                            _ap = autopush_to_notion(_fresh)
                        title = _fresh.get("title", "—")
                        if _ap.get("url"):
                            reply = f"✓ Готово — ТЗ «{title}» у Дины в Notion (база Videos):\n{_ap['url']}"
                            st.session_state["jack_mood"] = "happy"
                        elif _ap.get("skipped"):
                            reply = f"«{title}» уже лежит у Дины в Notion — не дублирую."
                            st.session_state["jack_mood"] = "happy"
                        else:
                            reply = (f"⚠️ Не смог записать в Notion: {_ap.get('error','неизвестная ошибка')}. "
                                     f"Проверь, что NOTION_TOKEN есть в secrets и приложение перезагружено.")
                            st.session_state["jack_mood"] = "neutral"
                    st.session_state.pop("draft_concept", None)
                    st.session_state["ws_messages"].append({"who": "jack", "text": reply, "time": t})
                    st.rerun()

                # Promotion triggers — Darya wants the in-chat draft saved to Approve (без Notion)
                promote_triggers = [
                    "сохрани", "добавь в апрув", "в апрув", "в план", "в кп",
                    "финал", "это финал", "ок сохрани",
                    "ок добавь", "добавь это", "это в апрув", "save", "promote",
                ]
                if any(tr in user_text.lower() for tr in promote_triggers) and st.session_state.get("draft_concept"):
                    from models.jack_engine import promote_to_approve
                    promote_to_approve(st.session_state["draft_concept"])
                    title = st.session_state["draft_concept"].get("title", "—")
                    reply = (
                        f"✓ Сохранил «{title}» в Approve (Pipeline → 🟡 To approve). "
                        f"Когда скажешь «создай ТЗ Дине в Notion» — сразу оформлю ей в базе Videos."
                    )
                    st.session_state.pop("draft_concept", None)
                    st.session_state["ws_messages"].append({"who": "jack", "text": reply, "time": t})
                    st.session_state["jack_mood"] = "happy"
                    st.rerun()

                # Guard: vague brief with no product named → ask, don't guess a SKU.
                # НО: B2B/Faire/приглашения/community-посты товара не требуют — для них не спрашиваем.
                from models.jack_chat import brief_has_product, brief_needs_no_product
                prior_draft = st.session_state.get("draft_concept")
                if (
                    looks_like_full_brief(user_text)
                    and not brief_has_product(user_text)
                    and not brief_needs_no_product(user_text)
                    and not prior_draft
                ):
                    reply = (
                        "Понял, давай сделаю — только скажи, **по какому товару**? "
                        "(напр. Calming Chews, Hemp Oil, Eye Wipes, Probiotic…) "
                        "Не хочу гадать и взять не тот SKU."
                    )
                    st.session_state["ws_messages"].append({"who": "jack", "text": reply, "time": t})
                    st.session_state["jack_mood"] = "happy"
                    st.rerun()

                # Decide mode: полный бриф → ФОНОВАЯ генерация (переживает сбросы);
                # короткий запрос → разговорный ответ (короткий, остаётся inline).
                if looks_like_full_brief(user_text):
                    prior = st.session_state.get("draft_concept")
                    ctx = user_text + (("\n\nREFERENCES:\n" + refs_context) if refs_context else "")
                    if prior:
                        ctx = (
                            f"=== PREVIOUS DRAFT ===\n"
                            f"Title: {prior.get('title','')}\nFormat: {prior.get('format','')}\nHook: {prior.get('hook','')}\nAngle: {prior.get('angle','')}\n"
                            f"Scenes:\n" + "\n".join(prior.get('scenes', [])) + "\n\n"
                            f"=== DARYA WANTS TO CHANGE ===\n{user_text}\n\n"
                            f"Перепиши концепт с учётом её правки. Та же база — формат/продукт/рынок, но меняй то что она просит."
                        )
                    req = {
                        "brand": effective_brand, "n": 1, "markets": [_market_from_text(user_text)],
                        "products": _products_for(user_text),
                        "pillars": ["Amazon Video"] if "amazon" in user_text.lower() else [],
                        "context": ctx,
                    }
                    _launch_bg_generation(req, t)
                    st.rerun()
                else:
                    # Conversational reply
                    with st.spinner("🐾 Jack думает…"):
                        reply = jack_chat_reply(
                            st.session_state["ws_messages"][:-1],
                            user_text,
                            refs_context,
                            brand=effective_brand,
                        )
                    st.session_state["ws_messages"].append({"who": "jack", "text": reply, "time": t})
                    # «иду писать» → запускаем ФОНОВУЮ генерацию по всему диалогу
                    if _signals_ready_to_write(reply):
                        all_darya = " ".join(m.get("text", "") for m in st.session_state["ws_messages"]
                                             if m.get("who") in ("darya", "tanya"))
                        req = {
                            "brand": effective_brand, "n": 1,
                            "markets": [_market_from_text(all_darya)],
                            "products": _products_for(all_darya),
                            "pillars": ["Amazon Video"] if "amazon" in all_darya.lower() else [],
                            "context": _assemble_brief_from_chat(st.session_state["ws_messages"], refs_context),
                        }
                        _launch_bg_generation(req, t)
                    st.session_state["jack_mood"] = "happy"
                    st.rerun()

        # ─── Vika's images → Jack writes the post text ──────────────────────
        with st.expander("📸 Картинки Вики → Джек напишет текст", expanded=False):
            st.caption("Залей готовые слайды карусели (или один пост). Джек посмотрит на них и напишет overlay-текст, caption, хэштеги и first comment.")
            with st.form("vika_imgs", clear_on_submit=False):
                imgs = st.file_uploader(
                    "Слайды (по порядку)", type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True, key="vika_uploader",
                )
                vc1, vc2 = st.columns(2)
                img_product = vc1.text_input("Товар/тема (необязательно)", placeholder="напр. Calming Chews")
                img_market = vc2.selectbox("Рынок", ["US", "UK", "CA"], index=0)
                img_extra = st.text_input("Пожелания (необязательно)", placeholder="напр. «потеплее, упор на сон»")
                go = st.form_submit_button("✍️ Написать текст", type="primary", use_container_width=True)
                if go:
                    if not imgs:
                        st.warning("Сначала залей хотя бы одну картинку.")
                    else:
                        from models.jack_engine import text_for_carousel_images
                        data = [f.getvalue() for f in imgs]
                        mimes = [f.type or "image/jpeg" for f in imgs]
                        with st.spinner(f"🐾 Джек смотрит на {len(data)} картинк(и) и пишет текст…"):
                            txt = text_for_carousel_images(
                                data, mimes, brand=brand, market=img_market,
                                product=img_product.strip(), extra=img_extra.strip(),
                            )
                        st.session_state["vika_text_result"] = txt
                        st.session_state["vika_text_n"] = st.session_state.get("vika_text_n", 0) + 1
            if st.session_state.get("vika_text_result"):
                st.markdown("---")
                _vn = st.session_state.get("vika_text_n", 0)
                st.text_area("Текст — редактируй прямо здесь и копируй",
                             value=st.session_state["vika_text_result"],
                             height=340, key=f"vika_text_edit_{_vn}")
                st.caption("✏️ Можно править прямо в поле, потом выделить и скопировать.")

        # ─── Captions: upload a finished reel video / photos → Jack writes the caption ─
        with st.expander("✍️ Captions — залей видео/фото, Джек напишет подпись", expanded=True):
            st.caption("Готовый рилс или фото от Дины. Залей видео и/или фото, скажи что в кадре — "
                       "Джек посмотрит и напишет подпись для поста + хэштеги + первый коммент. Это подпись, не сценарий.")
            with st.form("caption_media", clear_on_submit=False):
                cap_video = st.file_uploader(
                    "🎬 Видео рилса (необязательно)", type=["mp4", "mov", "m4v", "webm"],
                    accept_multiple_files=False, key="caption_video",
                )
                cap_imgs = st.file_uploader(
                    "🖼 Фото / кадры (необязательно, можно несколько)",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True, key="caption_imgs",
                )
                cc1, cc2 = st.columns(2)
                cap_product = cc1.text_input("Товар/тема", placeholder="напр. Calming Chews")
                cap_market = cc2.selectbox("Рынок", ["US", "UK", "CA"], index=0, key="cap_market")
                cap_extra = st.text_area(
                    "Что в кадре / пожелания", height=70,
                    placeholder="напр. «собака не спит, хозяин даёт чесалку, утром бодрая — упор на спокойный сон»",
                )
                cap_go = st.form_submit_button("✍️ Написать подпись", type="primary", use_container_width=True)
                if cap_go:
                    has_media = bool(cap_video) or bool(cap_imgs)
                    if not has_media and not cap_extra.strip():
                        st.warning("Залей видео/фото или хотя бы опиши словами, что в рилсе.")
                    else:
                        from models.jack_engine import caption_from_media
                        img_data = [f.getvalue() for f in cap_imgs] if cap_imgs else []
                        img_mimes = [f.type or "image/jpeg" for f in cap_imgs] if cap_imgs else []
                        vid_data = cap_video.getvalue() if cap_video else None
                        vid_suffix = ("." + cap_video.name.rsplit(".", 1)[-1]) if cap_video and "." in cap_video.name else ".mp4"
                        if cap_video:
                            spin = "🐾 Джек смотрит рилс и пишет подпись…"
                        elif cap_imgs:
                            spin = "🐾 Джек смотрит фото и пишет подпись…"
                        else:
                            spin = "🐾 Джек пишет подпись…"
                        with st.spinner(spin):
                            cap_txt = caption_from_media(
                                images=img_data, mime_types=img_mimes,
                                video_bytes=vid_data, video_suffix=vid_suffix,
                                brand=brand, market=cap_market,
                                product=cap_product.strip(), extra=cap_extra.strip(),
                            )
                        st.session_state["caption_media_result"] = cap_txt
                        st.session_state["caption_media_n"] = st.session_state.get("caption_media_n", 0) + 1
                        # СОХРАНЯЕМ подпись в общую базу — чтобы не пропала после перезагрузки/сна
                        if not cap_txt.startswith("⚠️"):
                            _captions_save(brand, cap_product.strip(), cap_market, cap_txt)
            if st.session_state.get("caption_media_result"):
                st.markdown("---")
                _n = st.session_state.get("caption_media_n", 0)
                st.text_area("Подпись — редактируй прямо здесь и копируй",
                             value=st.session_state["caption_media_result"],
                             height=340, key=f"caption_media_edit_{_n}")
                st.caption("✏️ Можно править текст прямо в поле, потом выделить и скопировать. "
                           "Перегенерить — поправь «что в кадре» и жми «Написать подпись».")

            # ─── 🗂 Сохранённые подписи — не теряются, копируй снова / удаляй ──
            _saved_caps = _captions_load(brand)
            if _saved_caps:
                st.markdown("---")
                st.markdown(f"**🗂 Сохранённые подписи ({len(_saved_caps)})** — скопировать снова или удалить")
                for _ci, _cap in enumerate(_saved_caps):
                    _head = " · ".join(x for x in [_cap.get("product") or "подпись",
                                                   _cap.get("market", ""), _cap.get("ts", "")] if x)
                    cc1, cc2 = st.columns([5, 1])
                    cc1.caption(f"#{_ci + 1} · {_head}")
                    if cc2.button("🗑", key=f"delcap_{brand}_{_ci}", help="Удалить эту подпись"):
                        _captions_delete(brand, _ci)
                        st.rerun()
                    st.text_area("сохранённая подпись", value=_cap.get("text", ""), height=170,
                                 key=f"savedcap_{brand}_{_ci}", label_visibility="collapsed")

    # ─── Tabs below — queues + context ──────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:32px;">Pipeline</div>', unsafe_allow_html=True)
    tab_appr, tab1, tab2, tab3, tab4 = st.tabs([
        "🟡 To approve",
        "🎬 Dina's queue (Notion)",
        "🖼  Vika's queue (Sheets)",
        "📖 Brand Brief",
        "🧠 Neural stack",
    ])

    with tab_appr:
        _render_approve_kanban()

    with tab1:
        st.markdown("**Approved reel briefs — Dina renders in Higgsfield**")
        try:
            from jack_notion import list_recent
            briefs = list_recent(10)
            st.caption(f"Last {len(briefs)} pages from Notion Videos database")
            for b in briefs:
                status_emoji = {"Not started": "📋", "In progress": "🔵", "Done": "✅"}.get(b["status"], "•")
                with st.container():
                    cc1, cc2, cc3 = st.columns([3, 1, 1])
                    cc1.markdown(f"{status_emoji} **{b['title']}**")
                    cc2.caption(f"{'·'.join(b['brand'])} · {b['date']}")
                    cc3.link_button("Open", b["url"])
        except Exception as e:
            st.warning(f"Couldn't read Notion: {e}")

    with tab2:
        st.markdown("**Graphics tasks for Vika** — IG carousels, posts, stories")
        try:
            from models.jack_sheets import is_configured
            if is_configured():
                st.success("✅ Google Sheets подключён — задачи Вике уходят в КП (вкладка «Vika tasks»). "
                           "Жми «📤 Вике в Sheets» в карточке концепта.")
            else:
                st.warning("⚙️ Google Sheets ещё не настроен. Нужен Service Account + ID таблицы КП. "
                           "Как настроишь — кнопка «📤 Вике в Sheets» в карточках заработает.")
        except Exception as e:
            st.warning(f"Sheets-модуль не готов: {e}")

    with tab3:
        brief_path = Path.home() / "Databases" / "BP-Brand-Brief.md"
        bundled = Path(__file__).resolve().parent.parent / "brand_data" / "BP-Brand-Brief.md"
        if brief_path.exists():
            st.markdown(brief_path.read_text(encoding="utf-8"))
        elif bundled.exists():
            st.markdown(bundled.read_text(encoding="utf-8"))
        else:
            st.error("Brand Brief not found")

    with tab4:
        from models.llm import available_models
        models = available_models()
        for key, m in models.items():
            with st.expander(f"{m['name']} — {m['status']}", expanded=False):
                cc1, cc2 = st.columns([2, 1])
                cc1.markdown(f"**Use for:** {m['use_for']}")
                cc1.markdown(f"**How:** {m['how']}")
                cc2.metric("Cost", m["cost"])

    # ─── Chat CSS ───────────────────────────────────────────────────────────
    st.markdown(
        """
        <style>
        .msg {
            border-radius: 12px;
            padding: 10px 14px;
            margin: 6px 0;
            font-size: 0.92rem;
            line-height: 1.45;
            max-width: 90%;
        }
        .msg-label {
            font-size: 0.7rem;
            color: #4F5B72;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .jack-msg {
            background: #FFFFFF;
            border: 1px solid #D9E2EE;
            color: #060B17;
        }
        .user-msg {
            background: linear-gradient(135deg, #3B5FFF 0%, #1B339E 100%);
            color: #FFFFFF;
            margin-left: auto;
        }
        .user-msg .msg-label { color: rgba(255,255,255,0.82); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_approve_kanban():
    concepts = load_concepts()
    drafts = [c for c in concepts if c.get("status") == "draft"]
    approved = [c for c in concepts if c.get("status") == "approved"]
    edits = [c for c in concepts if c.get("status") == "edit"]

    if not concepts:
        st.info("No concepts yet. Go to **📅 Content Plan** → scroll down → **🚀 Brief Jack to generate concepts**.")
        return

    st.markdown(f"**{len(drafts)} draft · {len(edits)} need edit · {len(approved)} approved**")

    PILL_COLOR = {
        "Pet Care Tip": ("#D9F0D1","#3A6B2A"), "Heartwarming": ("#D9F0D1","#3A6B2A"),
        "Education": ("#D9F0D1","#3A6B2A"),    "Community / UGC": ("#D9F0D1","#3A6B2A"),
        "Product Highlight": ("#F4C7C7","#8E2424"), "Amazon Video": ("#F4C7C7","#8E2424"),
        "Faire B2B": ("#F4C7C7","#8E2424"),     "Promo / Discount": ("#F4C7C7","#8E2424"),
        "Meme / POV": ("#D7CBE8","#553A8B"),    "Trend": ("#D7CBE8","#553A8B"),
        "Comedy": ("#D7CBE8","#553A8B"),
    }

    for c in drafts + edits:
        bg, fg = PILL_COLOR.get(c.get("pillar", ""), ("#EEF4FA","#0F1623"))
        # Build script (numbered scenes) HTML
        scenes = c.get("scenes") or []
        scenes_html = ""
        if scenes:
            scenes_lines = "".join(
                f'<div style="padding:6px 10px; border-left:2px solid #C8D5E3; margin:4px 0; color:#1F2A3F; font-size:0.86rem; line-height:1.45;">{s}</div>'
                for s in scenes
            )
            scenes_html = (
                '<div style="margin-top:10px;">'
                '<div style="font-weight:800; font-size:0.74rem; color:#4F5B72; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px;">📝 Script · numbered scenes</div>'
                f'{scenes_lines}'
                '</div>'
            )
        compliance = c.get("compliance_notes") or ""
        compliance_html = (
            f'<div style="margin-top:8px; padding:6px 10px; background:#FEF3C7; border-left:3px solid #F59E0B; border-radius:6px; font-size:0.78rem; color:#7C2D12;"><strong>⚠️ Compliance:</strong> {compliance}</div>'
            if compliance else ""
        )
        links = c.get("links") or {}
        links_html = ""
        if links:
            def _is_url(v):
                return isinstance(v, str) and v.strip().lower().startswith(("http://", "https://"))
            link_lines = []
            notes = []
            drive_v = links.get("product_pics_drive")
            listing_v = links.get("listing_url")
            if _is_url(drive_v):
                link_lines.append(f'<a href="{drive_v}" target="_blank" style="color:#1E40FF;">📁 Drive</a>')
            elif drive_v:
                notes.append(str(drive_v))
            if _is_url(listing_v):
                link_lines.append(f'<a href="{listing_v}" target="_blank" style="color:#1E40FF;">🛒 Listing</a>')
            elif listing_v:
                notes.append(str(listing_v))
            parts = []
            if link_lines:
                parts.append('<div style="margin-top:8px; font-size:0.84rem;">' + " · ".join(link_lines) + '</div>')
            if notes:
                # LLM put a note (not a URL) into a link field — show it as a plain note, не как сырой HTML
                import html as _html
                note_txt = " · ".join(_html.escape(n) for n in notes)
                parts.append(f'<div style="margin-top:8px; font-size:0.8rem; color:#7A6A20; background:#FFFBEB; border:1px dashed #FCD34D; border-radius:6px; padding:6px 10px;">📌 {note_txt}</div>')
            links_html = "".join(parts)

        # IG Caption fields (only when format == IGCaption)
        caption_html = ""
        if c.get("format") == "IGCaption" or c.get("caption"):
            cap = (c.get("caption") or "").replace("\n", "<br/>")
            tags = " ".join(c.get("hashtags") or [])
            first = c.get("first_comment") or ""
            caption_html = (
                '<div style="margin-top:10px; padding:12px 14px; background:#FFFBEB; border:1px solid #FCD34D; border-radius:10px;">'
                f'<div style="font-weight:800; font-size:0.74rem; color:#92400E; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;">📝 IG Caption (publish-ready)</div>'
                f'<div style="color:#0A0E1A; font-size:0.92rem; line-height:1.5; margin-bottom:8px;">{cap}</div>'
                f'<div style="color:#1E40FF; font-size:0.82rem; font-weight:600; margin-bottom:6px;">{tags}</div>'
                f'<div style="color:#5B6478; font-size:0.78rem;"><strong>1st comment:</strong> {first}</div>'
                '</div>'
            )

        # Vika brief block (graphic designer)
        vika_html = ""
        vb = c.get("vika_brief")
        if vb and vb.get("scenes"):
            slides = "".join(
                f'<div style="padding:6px 10px; border-left:2px solid #C4B5FD; margin:4px 0; color:#1F2A3F; font-size:0.84rem;">{s}</div>'
                for s in vb["scenes"]
            )
            vika_html = (
                '<div style="margin-top:10px; padding:12px 14px; background:#F5F3FF; border:1px solid #C4B5FD; border-radius:10px;">'
                '<div style="font-weight:800; font-size:0.74rem; color:#6D28D9; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;">🖼 ТЗ для Вики (графдизайн)</div>'
                f'<div style="font-weight:700; color:#0A0E1A; margin-bottom:6px;">{vb.get("title","")}</div>'
                f'{slides}'
                '</div>'
            )
        with st.container():
            st.markdown(
                f"""
                <div style="background:#FFF; border:1px solid #D9E2EE; border-radius:12px; padding:14px 18px; margin:8px 0;">
                    <div style="display:flex; gap:8px; align-items:center; margin-bottom:6px; flex-wrap:wrap;">
                        <span style="background:{bg};color:{fg};padding:2px 10px;border-radius:100px;font-weight:800;font-size:0.72rem;text-transform:uppercase;">{c.get('pillar','—')}</span>
                        <span style="background:#EEF4FA;color:#1B339E;padding:2px 8px;border-radius:6px;font-size:0.7rem;font-weight:700;">{c.get('format','—')}</span>
                        <span style="background:#FCE7F3;color:#9F1239;padding:2px 8px;border-radius:6px;font-size:0.7rem;font-weight:800;">{c.get('market','—')}</span>
                        <span style="color:#4F5B72;font-size:0.74rem;">· {c.get('product','—')}</span>
                    </div>
                    <div style="font-weight:800;font-size:1rem;color:#060B17;margin-bottom:4px;">{c.get('title','(untitled)')}</div>
                    <div style="color:#1F2A3F;font-style:italic;margin-bottom:6px;">"{c.get('hook','—')}"</div>
                    <div style="color:#4F5B72;font-size:0.82rem;">{c.get('angle','—')}</div>
                    {scenes_html}
                    <div style="background:#F0F5FB;border-left:3px solid #3B5FFF;padding:8px 10px;border-radius:6px;margin-top:8px;font-size:0.8rem;color:#1F2A3F;">
                        <strong>CTA:</strong> {c.get('cta','—')} · <strong>{c.get('duration_s','—')}s</strong> · <strong>Why:</strong> {c.get('why_it_works','—')}
                    </div>
                    {compliance_html}
                    {caption_html}
                    {vika_html}
                    {links_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Lesson note field — Darya can teach Jack what to fix
            note_key = f"note_{c['id']}"
            st.markdown(
                '<div style="margin-top:12px; font-weight:700; font-size:0.86rem; color:#1B339E;">'
                '✏️ Напиши тут, что переделать — и жми «🔄 Переписать». Джек сразу перепишет скрипт.</div>',
                unsafe_allow_html=True,
            )
            note_val = st.text_input(
                "Что переделать",
                key=note_key,
                placeholder="напр. «hook сделай повеселее», «убери стиль Pet Honesty», «CTA короче»",
                label_visibility="collapsed",
            )

            bc1, bc2, bc3, bc4, _ = st.columns([1.4, 1, 1, 1.2, 1.4])
            if bc1.button("✅ Approve", key=f"app_{c['id']}", use_container_width=True):
                update_status(c["id"], "approved")
                if note_val.strip():
                    from models.jack_lessons import add_lesson
                    add_lesson(c.get("brand", "BelovedPets"), "praise", note_val, c.get("title", ""))
                # Auto-generate caption if not already present
                if not c.get("caption"):
                    with st.spinner("🐾 Jack пишет caption для поста…"):
                        from models.jack_engine import generate_concepts, delete_concept as _dc, load_concepts as _lc, CONCEPTS_FILE as _cf
                        import json as _j
                        cap_req = {
                            "brand": c.get("brand", "BelovedPets"), "n": 1,
                            "markets": [c.get("market", "US")],
                            "products": [c.get("product", "")],
                            "pillars": [],
                            "context": (
                                f"Напиши IGCaption для УЖЕ approved рилса:\n"
                                f"Title: {c.get('title','')}\nHook: {c.get('hook','')}\nAngle: {c.get('angle','')}\n"
                                f"Product: {c.get('product','')}\nMarket: {c.get('market','')}\nCTA: {c.get('cta','')}\n\n"
                                "Output format=IGCaption with caption + hashtags + first_comment fields."
                            ),
                        }
                        cap_res = generate_concepts(cap_req)
                    if cap_res and "caption" in cap_res[0]:
                        all_c = _lc()
                        for item in all_c:
                            if item.get("id") == c["id"]:
                                item["caption"] = cap_res[0].get("caption")
                                item["hashtags"] = cap_res[0].get("hashtags")
                                item["first_comment"] = cap_res[0].get("first_comment")
                                break
                        _cf.write_text(_j.dumps(all_c, ensure_ascii=False, indent=2), encoding="utf-8")
                        _dc(cap_res[0].get("id", ""))
                # Автопуш Дине в Notion: если у концепта уже есть Drive+listing —
                # оформляем ТЗ сразу, без второй кнопки. Если ссылок нет — ниже в
                # разделе ✅ Approved Джек попросит их и запушит.
                from models.jack_engine import autopush_to_notion, load_concepts as _lcap
                _fresh = next((x for x in _lcap() if x.get("id") == c["id"]), c)
                _ap = autopush_to_notion(_fresh)
                if _ap.get("url"):
                    st.success("📄 ТЗ сразу ушло Дине в Notion")
                elif _ap.get("error"):
                    st.warning(f"⚠️ В Notion не ушло: {_ap['error']}")
                st.rerun()
            if bc2.button("🔄 Переписать", key=f"edt_{c['id']}", use_container_width=True, type="primary",
                          help="Jack перепишет скрипт с твоими правками. Сначала напиши правку в поле выше."):
                if not note_val.strip():
                    st.warning("👆 Сначала напиши правку в поле над кнопками — что именно переделать. Тогда Джек перепишет.")
                else:
                    from models.jack_lessons import add_lesson
                    from models.jack_engine import generate_concepts, load_concepts as _lc, CONCEPTS_FILE as _cf, delete_concept as _dc
                    import json as _j
                    add_lesson(c.get("brand", "BelovedPets"), "edit", note_val, c.get("title", ""))
                    with st.spinner("🐾 Jack переделывает с учётом правок…"):
                        rewrite_req = {
                            "brand": c.get("brand", "BelovedPets"), "n": 1,
                            "markets": [c.get("market", "US")],
                            "products": [c.get("product", "")],
                            "pillars": [c.get("pillar", "")] if c.get("pillar") else [],
                            "context": (
                                f"REWRITE предыдущий концепт с учётом правки Darya.\n\n"
                                f"=== ПРЕДЫДУЩИЙ КОНЦЕПТ ===\n"
                                f"Title: {c.get('title','')}\n"
                                f"Format: {c.get('format','')}\n"
                                f"Hook: {c.get('hook','')}\n"
                                f"Angle: {c.get('angle','')}\n"
                                f"Scenes:\n" + "\n".join(c.get('scenes', [])) + "\n"
                                f"CTA: {c.get('cta','')}\n\n"
                                f"=== ПРАВКА DARYA ===\n{note_val}\n\n"
                                f"Сделай новый концепт того же формата/продукта/рынка, но с учётом её правки. "
                                f"НЕ повторяй прошлый hook. Учти что именно ей не понравилось."
                            ),
                        }
                        new_result = generate_concepts(rewrite_req)
                    if new_result and "error" not in new_result[0]:
                        # link old to new as history
                        new = new_result[0]
                        new["prev_id"] = c["id"]
                        new["prev_note"] = note_val
                        new["status"] = "draft"
                        # save updated cache: remove old, keep new
                        all_c = _lc()
                        all_c = [x for x in all_c if x.get("id") != c["id"]]
                        # new already inserted by generate_concepts; ensure flags
                        for item in all_c:
                            if item.get("id") == new["id"]:
                                item["prev_id"] = c["id"]
                                item["prev_note"] = note_val
                        _cf.write_text(_j.dumps(all_c, ensure_ascii=False, indent=2), encoding="utf-8")
                        st.success(f"✓ Переписал — новый драфт «{new.get('title','—')[:50]}» выше.")
                        st.rerun()
                    else:
                        update_status(c["id"], "edit")
                        st.error("Не получилось переделать. Концепт помечен как edit — попробуй позже.")
                        st.rerun()
            if bc3.button("❌ Reject", key=f"rej_{c['id']}", use_container_width=True):
                if note_val.strip():
                    from models.jack_lessons import add_lesson
                    add_lesson(c.get("brand", "BelovedPets"), "reject", note_val, c.get("title", ""))
                delete_concept(c["id"])
                st.rerun()
            # extra row of generation buttons
            bvr1, bvr2, bvr3, _ = st.columns([1.2, 1.2, 1.4, 3])
            if bvr1.button("✍️ Vika brief", key=f"vk_{c['id']}", use_container_width=True,
                           help="ТЗ для графдизайнера Вики — слайды, текст, цвета. Появится в Content Plan как комментарий."):
                with st.spinner("🐾 Jack пишет ТЗ для Вики…"):
                    from models.jack_engine import generate_concepts, load_concepts as _lc, CONCEPTS_FILE as _cf, delete_concept as _dc
                    import json as _j
                    vk_req = {
                        "brand": c.get("brand", "BelovedPets"), "n": 1,
                        "markets": [c.get("market", "US")],
                        "products": [c.get("product", "")],
                        "pillars": [],
                        "context": (
                            f"Напиши ТЗ для графдизайнера Вики (статичный пост / карусель в Instagram) под концепт:\n"
                            f"Title: {c.get('title','')}\n"
                            f"Hook: {c.get('hook','')}\n"
                            f"Angle: {c.get('angle','')}\n"
                            f"Product: {c.get('product','')}\n"
                            f"Market: {c.get('market','')}\n\n"
                            "Output как format=Carousel ИЛИ Static. Опиши пронумерованные слайды (3-7 шт) — "
                            "в каждом слайде: что в кадре (РУС), text overlay (EN), цвета, шрифты, "
                            "brand-логотип где, packshot где. В конце — текст для подписи."
                        ),
                    }
                    vk_res = generate_concepts(vk_req)
                if vk_res and "scenes" in vk_res[0]:
                    all_c = _lc()
                    for item in all_c:
                        if item.get("id") == c["id"]:
                            item["vika_brief"] = {
                                "title": vk_res[0].get("title", ""),
                                "scenes": vk_res[0].get("scenes", []),
                                "caption": vk_res[0].get("caption", ""),
                            }
                            break
                    _cf.write_text(_j.dumps(all_c, ensure_ascii=False, indent=2), encoding="utf-8")
                    _dc(vk_res[0].get("id", ""))
                    st.success(f"✓ ТЗ для Вики готово — смотри в Content Plan под датой концепта или ниже в карточке.")
                    st.rerun()
                else:
                    st.error("Не получилось. Попробуй ещё раз.")
            if bvr2.button("✍️ Caption", key=f"cap_{c['id']}", use_container_width=True,
                          help="Сгенерировать IG/TikTok caption + хэштеги под этот концепт"):
                with st.spinner("🐾 Jack пишет caption…"):
                    from models.jack_engine import generate_concepts
                    cap_req = {
                        "brand": c.get("brand", "BelovedPets"),
                        "n": 1,
                        "markets": [c.get("market", "US")],
                        "products": [c.get("product", "")],
                        "pillars": [],
                        "context": (
                            f"Напиши IGCaption для УЖЕ ГОТОВОГО рилса:\n"
                            f"Title: {c.get('title','')}\n"
                            f"Hook: {c.get('hook','')}\n"
                            f"Angle: {c.get('angle','')}\n"
                            f"Product: {c.get('product','')}\n"
                            f"Market: {c.get('market','')}\n"
                            f"CTA: {c.get('cta','')}\n\n"
                            "Output format=IGCaption with caption + hashtags + first_comment fields."
                        ),
                    }
                    cap_result = generate_concepts(cap_req)
                if cap_result and "caption" in cap_result[0]:
                    # merge caption fields back into the original concept
                    from models.jack_engine import load_concepts as _lc, CONCEPTS_FILE as _cf
                    import json as _j
                    all_c = _lc()
                    for item in all_c:
                        if item.get("id") == c["id"]:
                            item["caption"] = cap_result[0].get("caption")
                            item["hashtags"] = cap_result[0].get("hashtags")
                            item["first_comment"] = cap_result[0].get("first_comment")
                            break
                    _cf.write_text(_j.dumps(all_c, ensure_ascii=False, indent=2), encoding="utf-8")
                    # remove the freshly created standalone caption concept to avoid duplication
                    from models.jack_engine import delete_concept as _dc
                    _dc(cap_result[0].get("id", ""))
                    st.rerun()
                else:
                    st.error("Caption не получился — попробуй ещё раз.")
            if bvr3.button("📤 Вике в Sheets", key=f"vksh_{c['id']}", use_container_width=True,
                           help="Отправить граф-задачу Вике строкой в КП (Google Sheets, вкладка «Vika tasks»)."):
                from datetime import date as _date
                from models.jack_sheets import push_vika_task
                with st.spinner("📤 Отправляю задачу Вике в Sheets…"):
                    res = push_vika_task(c, _date.today().isoformat())
                if res.get("ok"):
                    st.success("✓ Задача Вике добавлена в КП (вкладка «Vika tasks»).")
                else:
                    st.error(f"Не ушло: {res.get('error','неизвестно')}")

    if approved:
        st.markdown("---")
        st.markdown(f"### ✅ Approved · {len(approved)}")
        for c in approved:
            notion_url = c.get("notion_url")
            with st.container():
                st.markdown(
                    f"**{c.get('title','—')}** · {c.get('product','—')} · {c.get('market','—')}"
                )

                # ─── Внести рилс в контент-план на выбранную дату ───────────────
                _plan_date = c.get("plan_date")
                if _plan_date:
                    st.success(f"📅 В контент-плане на {_plan_date} · 🎬 Дина (видео)")
                else:
                    st.markdown(
                        '<div style="font-size:0.86rem; color:#1B339E;">🐾 Джек: '
                        'скрипт апрувлен. На какую дату ставим рилс в контент-план?</div>',
                        unsafe_allow_html=True,
                    )
                    from datetime import date as _date2
                    pc1, pc2 = st.columns([1.4, 1])
                    plan_d = pc1.date_input(
                        "📅 Дата в КП", value=_date2.today(),
                        key=f"plandate_{c['id']}", label_visibility="collapsed",
                    )
                    if pc2.button("📅 Внести в КП", key=f"plan_{c['id']}",
                                  use_container_width=True, type="primary"):
                        from views import content_plan
                        from models.jack_engine import set_concept_fields
                        dk = plan_d.strftime("%d.%m")
                        content_plan.add_plan_post(
                            c.get("brand", brand), dk,
                            c.get("title", "рилс"), _pillar_to_type(c.get("pillar", "")),
                            c.get("pillar", ""), owner="dina",
                        )
                        set_concept_fields(c["id"], plan_date=dk)
                        st.success(f"✓ Внёс «{c.get('title','рилс')}» в контент-план на {dk} (🎬 Дина). Видит вся команда.")
                        st.rerun()

                if notion_url:
                    # Already pushed to Dina
                    st.success("📄 ТЗ у Дины в Notion")
                    st.link_button("Открыть в Notion", notion_url)
                    continue

                # Ручная отправка (fallback, если автопуш не сработал). Ссылки
                # НЕ обязательны — Дина берёт материалы с общего Диска сама.
                st.markdown(
                    '<div style="font-size:0.86rem; color:#1B339E;">🐾 Джек: '
                    'скрипт готов и апрувлен. Жми «Отправить ТЗ Дине» — оформлю в Notion сразу. '
                    'Ссылки Drive/listing можно оставить пустыми (не обязательны).</div>',
                    unsafe_allow_html=True,
                )
                from datetime import date as _date
                with st.form(f"send_dina_{c['id']}"):
                    drive_in = st.text_input(
                        "📁 Drive — папка с фото товара (необязательно)",
                        value=(c.get("links") or {}).get("product_pics_drive", "") if str((c.get("links") or {}).get("product_pics_drive", "")).startswith("http") else "",
                        placeholder="можно пусто",
                        key=f"drive_{c['id']}",
                    )
                    listing_in = st.text_input(
                        "🛒 Listing — товар на Amazon/Shopify (необязательно)",
                        value=(c.get("links") or {}).get("listing_url", "") if str((c.get("links") or {}).get("listing_url", "")).startswith("http") else "",
                        placeholder="можно пусто",
                        key=f"listing_{c['id']}",
                    )
                    date_in = st.date_input(
                        "📅 Дата (End date в Notion)",
                        value=_date.today(),
                        key=f"date_{c['id']}",
                    )
                    send = st.form_submit_button("📨 Отправить ТЗ Дине в Notion", type="primary", use_container_width=True)
                    if send:
                        from models.jack_engine import publish_to_notion, set_concept_fields
                        with st.spinner("🐾 Джек оформляет ТЗ для Дины в Notion…"):
                            res = publish_to_notion(c, drive_in.strip(), listing_in.strip(), date_in.isoformat())
                        if res and res.get("url"):
                            set_concept_fields(c["id"], notion_url=res["url"], links={
                                **(c.get("links") or {}),
                                "product_pics_drive": drive_in.strip(),
                                "listing_url": listing_in.strip(),
                            })
                            st.success("✓ ТЗ ушло Дине в Notion!")
                            st.rerun()
                        else:
                            st.error(f"Не получилось: {res.get('error','неизвестная ошибка') if res else 'нет ответа'}")
