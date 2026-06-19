"""Content Plan — June 2026 as a week-by-week calendar grid (matches Darya's Google Sheets layout)."""

from __future__ import annotations

import base64
import html
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

_URL_RE = re.compile(r"https?://[^\s)\]]+")

# ─── Команда: кто отвечает за пост (аватарка в углу ячейки) ──────────────────
# Исполнитель выбирается ЯВНО на каждом посте (поле "owner" = slug имени), список
# берётся из живой команды (общая база). Известным людям — фирменный цвет/инициал,
# новым — цвет из палитры + первая буква имени.
_AVATARS_DIR = Path(__file__).resolve().parent.parent / "assets" / "avatars"
# gen — имя в родительном падеже («для Вики», «от Дины»); role — для какого ТЗ (graphics/video).
_OWNER_STYLE = {
    "vika":  {"name": "Вика",  "gen": "Вики",  "initial": "В", "color": "#3D7EDB", "role": "graphics"},
    "dina":  {"name": "Дина",  "gen": "Дины",  "initial": "Д", "color": "#D9568C", "role": "video"},
    "tanya": {"name": "Таня",  "gen": "Тани",  "initial": "Т", "color": "#E0902B", "role": "TOBYDIC"},
    "darya": {"name": "Дарья", "gen": "Дарьи", "initial": "Д", "color": "#2BB58C", "role": "admin"},
}
_PALETTE = ["#7A5FC2", "#2BB58C", "#C2557A", "#4F9D69", "#B5642B", "#5566C2"]

# Легаси-посевы без поля owner: эти ID исторически были на Вике, остальное — Дина.
_VIKA_IDS = {"p0206a", "p0806a", "p1606a", "p2206a", "p3006a", "p0306a", "p1006a"}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _team_owners() -> dict:
    """slug→{name,initial,color} по ЖИВОЙ команде (из общей базы). Меняешь команду в
    сайдбаре — список исполнителей на постах меняется сразу у всех."""
    try:
        from models import shared_store
        team = shared_store.get_team()
    except Exception:
        team = []
    owners: dict = {}
    for i, m in enumerate(team):
        nm = (m.get("name") or "").strip()
        if not nm:
            continue
        s = _slug(nm)
        base = dict(_OWNER_STYLE[s]) if s in _OWNER_STYLE else {
            "name": nm, "gen": nm, "initial": nm[0].upper(), "color": _PALETTE[i % len(_PALETTE)]}
        # роль из живой команды важнее (Сергей может её менять), но не затираем фирменную пустой
        if m.get("role"):
            base["role"] = str(m["role"]).strip()
        base.setdefault("role", "")
        base.setdefault("gen", base["name"])
        owners[s] = base
    return owners


def _owner_meta(slug: str, owners: dict | None = None) -> dict:
    """Стиль аватарки для slug: из живой команды → из фирменного словаря → серая заглушка."""
    if owners and slug in owners:
        return owners[slug]
    if slug in _OWNER_STYLE:
        return dict(_OWNER_STYLE[slug])
    return {"name": slug.title() or "?", "gen": slug.title() or "?",
            "initial": (slug[:1].upper() or "?"), "color": "#8A93A3", "role": ""}


def _owner_of(item: dict) -> str:
    """Явно выбранный исполнитель; для старых постов без поля — легаси-правило."""
    o = item.get("owner")
    if o:
        return o
    return "vika" if item.get("id") in _VIKA_IDS else "dina"


_AVATAR_CACHE: dict = {}


def _avatar_src(owner: str) -> str:
    """data: URI фото из assets/avatars/<owner>.(png|jpg|jpeg|webp). Кэш по mtime файла."""
    for ext in ("png", "jpg", "jpeg", "webp"):
        f = _AVATARS_DIR / f"{owner}.{ext}"
        if f.exists():
            key = (owner, f.stat().st_mtime)
            if key in _AVATAR_CACHE:
                return _AVATAR_CACHE[key]
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            uri = f"data:image/{mime};base64," + base64.b64encode(f.read_bytes()).decode()
            _AVATAR_CACHE[key] = uri
            return uri
    # No local file (e.g. in the cloud) → load the photo from Supabase (kept private,
    # NOT in the public repo). Cached once per process.
    return _db_avatar(owner)


_AVATAR_DB_CACHE: dict = {}


def _db_avatar(owner: str) -> str:
    """Avatar data-URI из Supabase (__avatar_<slug>__.b64) — напрямую, минуя
    plan_briefs.load_all() (тот выбрасывает все '__'-строки и прятал бы фото).
    Кэш по процессу, ленивая загрузка по slug."""
    if owner in _AVATAR_DB_CACHE:
        return _AVATAR_DB_CACHE[owner]
    try:
        from models import shared_store
        uri = shared_store.get_avatar(owner)
        if uri:
            _AVATAR_DB_CACHE[owner] = uri
        return uri
    except Exception:
        return ""


def _avatar_html(slug: str, owners: dict | None = None) -> str:
    o = _owner_meta(slug, owners)
    src = _avatar_src(slug)
    inner = (f'<img src="{src}" alt="{o["name"]}">' if src else f'<span>{o["initial"]}</span>')
    return f'<div class="avatar" title="{o["name"]}" style="background:{o["color"]};">{inner}</div>'


def _save_avatar(owner: str, uploaded) -> None:
    """Save an uploaded photo as the avatar for owner: local file (Mac) + общая база (облако)."""
    _AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = _AVATARS_DIR / f"{owner}.{ext}"
        if p.exists():
            p.unlink()
    name = (uploaded.name or "").lower()
    ext = "jpg" if name.endswith((".jpg", ".jpeg")) else ("webp" if name.endswith(".webp") else "png")
    raw = uploaded.getvalue()
    (_AVATARS_DIR / f"{owner}.{ext}").write_bytes(raw)
    # Дублируем в общую базу, чтобы фото пережило ребут облака и увидела вся команда.
    try:
        from models import shared_store
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        uri = f"data:image/{mime};base64," + base64.b64encode(raw).decode()
        shared_store.put_avatar(owner, uri)
        _AVATAR_DB_CACHE[owner] = uri  # видно сразу, без повторной загрузки из базы
    except Exception:
        pass


def _avatar_uploader(owners: dict) -> None:
    """In-app upload фото для всей команды — кружки в углу постов станут фотографиями."""
    with st.expander("👤 Фото команды — поставь аватарки", expanded=False):
        st.caption("Выбери фото с компа для любого члена команды — кружок в углу его постов станет фотографией.")
        members = list(owners.items())
        for row_start in range(0, len(members), 2):
            cols = st.columns(2)
            for (slug, o), col in zip(members[row_start:row_start + 2], cols):
                with col:
                    cur = _avatar_src(slug)
                    if cur:
                        st.markdown(
                            f'<img src="{cur}" style="width:56px;height:56px;border-radius:50%;'
                            f'object-fit:cover;border:2px solid {o["color"]};">',
                            unsafe_allow_html=True,
                        )
                    up = st.file_uploader(f"Фото — {o['name']}", type=["png", "jpg", "jpeg", "webp"],
                                          key=f"av_up_{slug}")
                    if up is not None:
                        sig = f"{up.name}:{up.size}"
                        if st.session_state.get(f"av_sig_{slug}") != sig:
                            _save_avatar(slug, up)
                            st.session_state[f"av_sig_{slug}"] = sig
                            st.success(f"Готово — фото {o['name']} в кружках ✅")
                            st.rerun()


def _now() -> str:
    return datetime.now().strftime("%d.%m %H:%M")


def _clickable_links(field: str) -> str:
    """Turn a link field (one or several URLs) into clickable markdown links."""
    urls = _URL_RE.findall(field or "")
    if not urls:
        return ""
    if len(urls) == 1:
        return f"[открыть ссылку →]({urls[0]})"
    return " · ".join(f"[ссылка {i + 1} →]({u})" for i, u in enumerate(urls))


def _linkify(text: str) -> str:
    """Make bare URLs in the ТЗ clickable, without breaking existing [text](url) links."""
    # Skip URLs that are already the target of a markdown link: preceded by '(' .
    return re.sub(r"(?<!\()(https?://[^\s)\]]+)", r"[\1](\1)", text or "")


# ─── Colour system — Дарины 3 категории + белый (некрашеный) ─────────────────
# Цвет ставится ЯВНО на каждый пост (поле "type"), как в Google-таблице — не авто.
TYPE_COLORS = {
    "engaging": {"bg": "#D9F0D1", "border": "#86C45E", "text": "#3A6B2A", "label": "Вовлекающий"},
    "selling":  {"bg": "#F4C7C7", "border": "#E68585", "text": "#8E2424", "label": "Продающий"},
    "viral":    {"bg": "#D7CBE8", "border": "#A88FCE", "text": "#553A8B", "label": "Вирусный"},
    "neutral":  {"bg": "#FFFFFF", "border": "#D9E2EE", "text": "#2B2A28", "label": ""},
}


# ─── Plan data — keyed by date (DD.MM) ──────────────────────────────────────
# Перенос 1-в-1 из реального Google-КП Дарьи (июнь 2026). Mon–Fri заполнены,
# выходные пустые. "type" = цвет ячейки как в таблице: engaging(зел)/selling(крас)/
# viral(фиол)/neutral(бел). "pillar" — для контекста ТЗ (Джеку), на цвет не влияет.
_PLAN_BELOVEDPETS: dict[str, list[dict]] = {
    # неделя 1
    "02.06": [{"id": "p0206a", "title": "фото от блогера", "type": "engaging", "pillar": "Community / UGC"}],
    "03.06": [{"id": "p0306a", "title": "hemp oil carousel canada", "type": "selling", "pillar": "Product Highlight"}],
    "04.06": [{"id": "p0406a", "title": "uk new liquids reel", "type": "neutral", "pillar": "Product Highlight"}],
    "05.06": [{"id": "p0506a", "title": "tuna mix life pic red cat", "type": "neutral", "pillar": "Product Highlight"}],

    # неделя 2
    "08.06": [{"id": "p0806a", "title": "фото от блогера", "type": "engaging", "pillar": "Community / UGC"}],
    "09.06": [{"id": "p0906a", "title": "life pic flea spot on", "type": "neutral", "pillar": "Product Highlight"}],
    "10.06": [{"id": "p1006a", "title": "eye wipes carousel uk", "type": "selling", "pillar": "Product Highlight"}],
    "11.06": [{"id": "p1106a", "title": "faire canada reel invite", "type": "selling", "pillar": "Faire B2B"}],
    "12.06": [{"id": "p1206a", "title": "life pic chicken cubes", "type": "neutral", "pillar": "Product Highlight"}],

    # неделя 3
    "15.06": [{"id": "p1506a", "title": "resize amazon video duck strips", "type": "neutral", "pillar": "Amazon Video"}],
    "16.06": [{"id": "p1606a", "title": "фото от блогера", "type": "engaging", "pillar": "Community / UGC"}],
    "17.06": [{"id": "p1706a", "title": "amazon prime day canada", "type": "neutral", "pillar": "Promo / Discount"}],
    "18.06": [{"id": "p1806a", "title": "faire uk reel invite", "type": "selling", "pillar": "Faire B2B"}],
    "19.06": [{"id": "p1906a", "title": "amazon prime day uk", "type": "neutral", "pillar": "Promo / Discount"}],

    # неделя 4
    "22.06": [{"id": "p2206a", "title": "фото от блогера", "type": "engaging", "pillar": "Community / UGC"}],
    "23.06": [{"id": "p2306a", "title": "reel follow up amazon prime day uk and ca", "type": "neutral", "pillar": "Promo / Discount"}],
    "24.06": [{"id": "p2406a", "title": "subscribe & save canada amazon", "type": "selling", "pillar": "Promo / Discount"}],
    "25.06": [{"id": "p2506a", "title": "reel invite to fb group amazon blogers", "type": "neutral", "pillar": "Community / UGC"}],
    "26.06": [{"id": "p2606a", "title": "cat podcast new", "type": "viral", "pillar": "Trend"}],

    # неделя 5
    "29.06": [{"id": "p2906a", "title": "subscribe & save uk amazon", "type": "selling", "pillar": "Promo / Discount"}],
    "30.06": [{"id": "p3006a", "title": "фото от блогера", "type": "engaging", "pillar": "Community / UGC"}],
}

# TODO TOBYDIC: вставить реальный июньский план Тани (даты+темы), как у BelovedPets.
# Пока пусто — Таня увидит каркас календаря без потерь BP-плана.
_PLAN_TOBYDIC: dict[str, list[dict]] = {}

# План по бренду — render() берёт нужный по st.session_state["brand"].
PLANS_BY_BRAND: dict[str, dict[str, list[dict]]] = {
    "BelovedPets": _PLAN_BELOVEDPETS,
    "Tobydic": _PLAN_TOBYDIC,
}

# Месяцы, доступные в календаре (label → (год, месяц)).
MONTHS = {"Июнь 2026": (2026, 6), "Июль 2026": (2026, 7), "Август 2026": (2026, 8)}


# ─── Plan store (общая база) — даты/темы синхронятся у всех 4, правятся в UI ──
def _plan_key(brand: str) -> str:
    return f"plan_{brand.lower()}"


def load_plan(brand: str) -> dict:
    """Сетка плана из общей базы (Supabase). Первый раз засевается из захардкоженного
    каркаса (чтобы июньский BelovedPets не потерялся), дальше — источник правды облако."""
    seed = PLANS_BY_BRAND.get(brand, {})
    try:
        from models import shared_store
        if shared_store.configured():
            cloud = shared_store.get_json(_plan_key(brand), None)
            if cloud is None:
                if seed:
                    shared_store.put_json(_plan_key(brand), seed)
                return dict(seed)
            return cloud
    except Exception:
        pass
    return dict(seed)


def _save_plan(brand: str, plan: dict) -> None:
    try:
        from models import shared_store
        shared_store.put_json(_plan_key(brand), plan)
    except Exception:
        pass


def add_plan_post(brand: str, date_key: str, title: str, ptype: str, pillar: str,
                  owner: str = "") -> None:
    import uuid
    plan = load_plan(brand)
    pid = f"{brand[:2].lower()}{date_key.replace('.', '')}{uuid.uuid4().hex[:3]}"
    plan.setdefault(date_key, []).append(
        {"id": pid, "title": title.strip(), "type": ptype, "pillar": pillar.strip(),
         "owner": owner})
    _save_plan(brand, plan)


def set_plan_owner(brand: str, date_key: str, pid: str, owner: str) -> None:
    """Сменить исполнителя поста — сохраняется в общую базу, видит вся команда сразу."""
    plan = load_plan(brand)
    for p in plan.get(date_key, []):
        if p.get("id") == pid:
            p["owner"] = owner
            _save_plan(brand, plan)
            return


def delete_plan_post(brand: str, date_key: str, pid: str) -> None:
    plan = load_plan(brand)
    if date_key in plan:
        plan[date_key] = [p for p in plan[date_key] if p.get("id") != pid]
        if not plan[date_key]:
            plan.pop(date_key, None)
        _save_plan(brand, plan)


def _month_weeks(year: int, month: int) -> list[date]:
    """Список Monday-начал недель, покрывающих весь месяц."""
    first = date(year, month, 1)
    start = first - timedelta(days=first.weekday())  # понедельник на/до 1-го
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    weeks, wk = [], start
    while wk <= last:
        weeks.append(wk)
        wk += timedelta(weeks=1)
    return weeks


def render():
    brand = st.session_state.get("brand", "BelovedPets")

    month_label = st.selectbox("Месяц", list(MONTHS.keys()), index=0, key="plan_month")
    year, month = MONTHS[month_label]

    st.markdown(f"# 📅 Контент-план · {brand} · {month_label}")
    st.caption("Календарь по неделям · цвет = категория · ➕ ТЗ в ячейке = Джек пишет ТЗ Вике. "
               "Даты/темы добавляются внизу (➕ Добавить пост) — появляются у всей команды сразу.")

    st.markdown(
        f"""
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin: 8px 0 20px 0;">
            {_legend_pill("engaging", "фото от блогера, забота, обучение")}
            {_legend_pill("selling", "карусели, Amazon, Faire, промо")}
            {_legend_pill("viral", "виральный, тренды, POV, мемы")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    from models import plan_briefs
    if not st.session_state.get("_briefs_synced"):
        try:
            plan_briefs.ensure_synced()  # re-push any local-only ТЗ to the shared cloud
        except Exception:
            pass
        st.session_state["_briefs_synced"] = True
    briefs = plan_briefs.load_all()

    plan = load_plan(brand)
    if not plan:
        st.info(f"План **{brand}** ещё пустой. Добавь даты и темы внизу — форма **«➕ Добавить пост»**. "
                f"Появятся ячейки, и их сразу увидит вся команда (без зипов и пересылок).")

    st.markdown(_GRID_CSS, unsafe_allow_html=True)

    mc1, _ = st.columns([1, 3])
    market = mc1.selectbox("Рынок для ТЗ Вики", ["UK", "US", "CA"], index=0, key="vika_market")
    st.caption("Нажми **➕ ТЗ** прямо в ячейке → Джек напишет ТЗ для Вики, оно сохранится в коммент (видят все 4). 💬 = ТЗ уже есть.")

    owners = _team_owners()
    _avatar_uploader(owners)

    # ─── Calendar grid — недели выбранного месяца ─────────────────────────────
    for week_start in _month_weeks(year, month):
        cols = st.columns(7, gap="small")
        for day_offset in range(7):
            d = week_start + timedelta(days=day_offset)
            key = d.strftime("%d.%m")
            items = plan.get(key, [])
            with cols[day_offset]:
                _render_cell(d, key, items, briefs, brand, market, owners)

    st.markdown("<br/>", unsafe_allow_html=True)
    n_comments = len([1 for e in briefs.values() if e.get("text")])
    st.caption(f"💬 {n_comments} ТЗ для Вики сохранено в этом плане")

    # ─── Добавить / удалить пост в плане (синхронно у всех 4) ─────────────────
    month_last = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - timedelta(days=1)
    with st.expander("➕ Добавить пост в план", expanded=(not plan)):
        st.caption("Добавляешь один раз — видят все. Без зипов и пересылок.")
        with st.form("add_plan_post", clear_on_submit=True):
            ac1, ac2 = st.columns(2)
            add_date = ac1.date_input("Дата", value=date(year, month, 1),
                                      min_value=date(year, month, 1), max_value=month_last,
                                      key="add_plan_date")
            add_type = ac2.selectbox("Тип (цвет ячейки)", ["engaging", "selling", "viral", "neutral"],
                                     key="add_plan_type")
            add_title = st.text_input("Тема поста", placeholder="напр. duck strips POV reel", key="add_plan_title")
            pc1, pc2 = st.columns(2)
            add_pillar = pc1.text_input("Пиллар (контекст Джеку, необязательно)",
                                        placeholder="напр. Product Highlight", key="add_plan_pillar")
            _own_slugs = list(owners.keys())
            add_owner = pc2.selectbox(
                "👤 Исполнитель", _own_slugs,
                format_func=lambda s: owners.get(s, {}).get("name", s),
                key="add_plan_owner") if _own_slugs else ""
            if st.form_submit_button("Добавить", type="primary", use_container_width=True):
                if add_title.strip():
                    add_plan_post(brand, add_date.strftime("%d.%m"), add_title, add_type,
                                  add_pillar, add_owner or "")
                    st.success(f"✓ {add_date.strftime('%d.%m')} — {add_title.strip()}. Видно всей команде.")
                    st.rerun()
                else:
                    st.warning("Впиши тему поста.")

        # удалить ошибочный пост
        flat = [(dk, p) for dk, posts in sorted(plan.items()) for p in posts]
        if flat:
            st.markdown("---")
            labels = {f"{dk} · {p['title']}": (dk, p["id"]) for dk, p in flat}
            to_del = st.selectbox("Удалить пост", ["—"] + list(labels.keys()), key="del_plan_sel")
            if st.button("🗑 Удалить", key="del_plan_btn") and to_del != "—":
                dk, pid = labels[to_del]
                delete_plan_post(brand, dk, pid)
                st.success("Удалено.")
                st.rerun()

    # ─── Brief Jack form ─────────────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:24px;">🚀 Brief Jack to generate concepts</div>', unsafe_allow_html=True)
    with st.form("brief_jack"):
        bc1, bc2 = st.columns(2)
        with bc1:
            n_concepts = st.number_input("How many concepts?", min_value=1, max_value=20, value=3, step=1)
            markets_in = st.multiselect("Markets", ["US", "UK", "CA"], default=["UK"])
        with bc2:
            from models.products import all_products, short_title as _short
            all_skus = [_short(p, 60) for p in all_products()]
            products_in = st.multiselect("Focus products", all_skus, default=all_skus[:3])
        pillars_in = st.multiselect("Pillars", ["Pet Care Tip", "Heartwarming", "Product Highlight", "Community / UGC", "Education", "Meme / POV", "Trend", "Comedy", "Amazon Video", "Faire B2B"])
        context_in = st.text_area("Extra context", placeholder="hooks to avoid, seasonal angles, tone notes…", height=70)
        go = st.form_submit_button("🐾 Ask Jack to generate", type="primary", use_container_width=True)

    if go:
        if not products_in or not markets_in:
            st.error("Pick markets and at least one product")
        else:
            from models.jack_engine import generate_concepts
            with st.spinner("🐾 Jack is thinking — generating concept seeds via Claude…"):
                concepts = generate_concepts({
                    "brand": brand,
                    "n": int(n_concepts),
                    "markets": markets_in,
                    "products": products_in,
                    "pillars": pillars_in,
                    "context": context_in,
                })
            if concepts and "error" in concepts[0]:
                st.error(concepts[0]["error"])
                if concepts[0].get("raw"):
                    st.code(concepts[0]["raw"])
            else:
                st.success(f"Jack generated {len(concepts)} concept(s). Review them in Jack Workspace → Pipeline → To approve.")


# ─── Helpers ────────────────────────────────────────────────────────────────
WEEKDAY_RU = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _render_cell(d: date, key: str, items: list[dict], briefs: dict, brand: str, market: str,
                 owners: dict) -> None:
    """Render one calendar day as a bordered table cell: date header + theme chip(s) + ➕ ТЗ."""
    weekday = WEEKDAY_RU[d.weekday()]
    is_weekend = d.weekday() >= 5
    with st.container(border=True):
        st.markdown(
            f'<div class="cal-date"><strong>{key}</strong> <span>{weekday}</span></div>',
            unsafe_allow_html=True,
        )
        if not items:
            # Выходные — штриховка; будни без постов — просто прочерк.
            st.markdown(
                '<div class="cell-weekend"></div>' if is_weekend
                else '<div class="cell-empty">—</div>',
                unsafe_allow_html=True,
            )
            return

        for it in items:
            pid = it["id"]
            c = TYPE_COLORS.get(it.get("type", "neutral"), TYPE_COLORS["neutral"])
            entry = briefs.get(pid, {})
            has = bool(entry.get("text"))
            dot = "💬 " if has else ""
            avatar = _avatar_html(_owner_of(it), owners)
            st.markdown(
                f'<div class="cell-item" style="background:{c["bg"]};border-color:{c["border"]};color:{c["text"]};">'
                f'{avatar}'
                f'<div class="cell-item-title">{dot}{html.escape(it["title"])}</div></div>',
                unsafe_allow_html=True,
            )
            with st.popover("💬 ТЗ" if has else "➕ ТЗ", use_container_width=True):
                _brief_editor(pid, it, entry, brand, market, key, owners)


def _brief_editor(pid: str, item: dict, entry: dict, brand: str, market: str, day_key: str,
                  owners: dict) -> None:
    """Generate / edit / save / delete the ТЗ for Vika for one cell (lives inside a popover)."""
    from models import plan_briefs

    st.markdown(f"**{day_key} · {item['title']}**")
    has = bool(entry.get("text"))

    # 👤 Исполнитель поста — выбор из живой команды, сохраняется в общую базу сразу.
    slugs = list(owners.keys())
    cur_owner = _owner_of(item)
    if cur_owner not in slugs:   # исполнитель уже не в команде — покажем его всё равно
        slugs = [cur_owner] + slugs
    sel = st.selectbox(
        "👤 Исполнитель", slugs, index=slugs.index(cur_owner),
        format_func=lambda s: _owner_meta(s, owners)["name"],
        key=f"owner_{pid}",
    )
    if sel != cur_owner:
        set_plan_owner(brand, day_key, pid, sel)
        st.rerun()

    # Имя выбранного исполнителя во всех подписях ниже следует за селектором.
    _meta = _owner_meta(sel, owners)
    who_gen = _meta.get("gen") or _meta["name"]      # родительный: «Вики» / «Дины»
    who_name = _meta["name"]                          # именительный
    who_role = (_meta.get("role") or "").lower()

    # Ссылка-исходник (фото блогера для ленты / референс). Джек вставит её в ТЗ.
    link = st.text_input(
        f"🔗 Ссылка для {who_gen} (фото блогера / референс)",
        value=entry.get("link", ""),
        key=f"link_{pid}",
        placeholder="вставь ссылку(и) на фото блогера — можно несколько через пробел",
    )
    # Кликабельные ссылки — чтобы Вика сразу переходила, не копируя.
    clickable = _clickable_links(link)
    if clickable:
        st.markdown("🔗 " + clickable)

    # Что Дарья хочет от поста — Джек пишет ТЗ под это (а не вслепую по одной теме).
    wish = st.text_input(
        f"✍️ Что хочешь от {who_gen}? (необязательно)",
        value=entry.get("wish", ""),
        key=f"wish_{pid}",
        placeholder="напр.: карусель 4 слайда, добавь UK-флаг, акцент на натуральность",
    )

    if st.button(f"🐾 Джек, напиши ТЗ для {who_gen}", key=f"gen_{pid}",
                 use_container_width=True, type="primary"):
        from models.jack_engine import brief_for_vika
        with st.spinner(f"🐾 Джек пишет ТЗ для {who_gen}…"):
            txt = brief_for_vika(title=item["title"], pillar=item["pillar"],
                                 brand=brand, market=market, extra=wish, link=link,
                                 for_name=who_name, for_role=who_role)
        if txt.startswith("⚠️"):
            st.error(txt)
        else:
            plan_briefs.save(pid, txt, title=item["title"], pillar=item["pillar"],
                             updated=_now(), link=link, wish=wish)
            st.rerun()

    # Поговорить с Джеком по-человечески — он уточнит/посоветует, прежде чем писать ТЗ.
    with st.expander("💬 Обсудить с Джеком (он уточнит / посоветует)"):
        q = st.text_input("Спроси Джека", key=f"ask_{pid}",
                          placeholder="напр.: какой формат тут зайдёт? стоит карусель или один кадр?")
        if st.button("🐾 Спросить", key=f"askbtn_{pid}", use_container_width=True) and q.strip():
            from models.jack_chat import jack_chat_reply
            ctx = f"Это пост из контент-плана: тема «{item['title']}», пиллар {item['pillar']}, рынок {market}. Дарья хочет: {wish or '(пока не сказала)'}."
            with st.spinner("🐾 Джек думает…"):
                reply = jack_chat_reply([], f"{ctx}\n\nВопрос: {q}", refs=link or "")
            st.session_state[f"jack_reply_{pid}"] = reply
        if st.session_state.get(f"jack_reply_{pid}"):
            st.info("🐾 " + st.session_state[f"jack_reply_{pid}"])

    # Готовое ТЗ — рендерим как markdown (ссылки внутри кликабельны).
    saved_txt = entry.get("text", "")
    if saved_txt:
        st.markdown(f"**📝 ТЗ для {who_gen}:**")
        st.markdown(_linkify(saved_txt))

    with st.expander("✏️ Редактировать ТЗ вручную", expanded=not saved_txt):
        new = st.text_area(
            f"ТЗ для {who_gen}",
            value=saved_txt,
            key=f"cmt_{pid}",
            placeholder=f"нажми кнопку выше — или впиши ТЗ для {who_gen} руками",
            height=240,
            label_visibility="collapsed",
        )
    if entry.get("updated"):
        st.caption(f"обновлено {entry['updated']}")

    b1, b2 = st.columns(2)
    if b1.button("💾 Сохранить", key=f"save_{pid}", use_container_width=True):
        plan_briefs.save(pid, new, title=item["title"], pillar=item["pillar"],
                         updated=_now(), link=link)
        st.rerun()
    if has and b2.button("🗑 Удалить", key=f"del_{pid}", use_container_width=True):
        plan_briefs.delete(pid)
        st.rerun()


def _legend_pill(t: str, desc: str) -> str:
    c = TYPE_COLORS[t]
    return (
        f'<span style="display:inline-flex; align-items:center; gap:6px; '
        f'background:{c["bg"]}; color:{c["text"]}; border:1px solid {c["border"]}; '
        f'padding:6px 12px; border-radius:100px; font-weight:700; font-size:0.82rem;">'
        f'<strong>{c["label"]}</strong> · {desc}</span>'
    )


_GRID_CSS = """
<style>
/* Календарь-таблица: каждая ячейка (st.container border) — клетка с границей, равная высота */
div[data-testid="stVerticalBlockBorderWrapper"] {
    min-height: 165px;
    border: 1px solid #C9D4E3 !important;
    border-radius: 6px !important;
    background: #FFFFFF;
}
/* плотнее колонки, чтобы границы читались как сетка */
div[data-testid="stHorizontalBlock"] { gap: 0.4rem !important; }
.cal-date {
    font-size: 0.74rem;
    color: #4F5B72;
    margin: 2px 0 6px 0;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
}
.cal-date strong { color: #060B17; font-weight: 800; font-size: 0.86rem; }
.cal-date span {
    color: #6B7A91; text-transform: uppercase;
    letter-spacing: 0.06em; font-size: 0.62rem; font-weight: 700;
}
.cell-empty { color: #C9D1DD; font-size: 1.1rem; text-align: center; padding: 8px 0; }
/* выходные — диагональная штриховка */
.cell-weekend {
    min-height: 96px;
    border-radius: 6px;
    background: repeating-linear-gradient(
        45deg, #EEF1F6, #EEF1F6 6px, #F8FAFC 6px, #F8FAFC 12px
    );
}
.cell-item {
    position: relative;
    border: 1px solid;
    border-radius: 8px;
    padding: 6px 8px;
    margin: 6px 0 4px 0;
    font-size: 0.78rem;
    line-height: 1.3;
    font-weight: 600;
}
.cell-item-title { font-weight: 700; margin-bottom: 2px; padding-right: 18px; }
/* аватарка ответственного (Вика/Дина) — кружок в правом верхнем углу поста */
.avatar {
    position: absolute;
    top: -9px; right: -7px;
    width: 24px; height: 24px;
    border-radius: 50%;
    border: 2px solid #FFFFFF;
    box-shadow: 0 1px 3px rgba(6,11,23,0.25);
    color: #FFFFFF;
    font-size: 0.66rem;
    font-weight: 800;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
    z-index: 2;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.cell-item-meta { font-size: 0.64rem; opacity: 0.82; font-weight: 600; }
</style>
"""
