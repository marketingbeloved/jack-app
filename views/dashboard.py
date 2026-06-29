"""Dashboard — command center: today's content, live followers, team pipeline, hot competitor wins."""

from datetime import date

import streamlit as st

from utils.jack_svg import render_jack
from models.competitor_parser import fetch_competitor_ideas, last_refresh
from models.jack_engine import load_concepts
from models.brand_stats import fetch_report, trend, format_num, format_delta
from models import socials, plan_stats


def render():
    brand = st.session_state.get("brand", "BelovedPets")

    # ─── Hero ───────────────────────────────────────────────────────────────
    col_msg, col_jack = st.columns([2.2, 1])
    with col_msg:
        st.markdown(
            """
            <div class="jack-hero compact">
                <div class="jack-status-pill"><span class="dot"></span> JACK · ONLINE</div>
                <h1>Hey Darya 👋  let's ship some bombs today.</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_jack:
        st.markdown(render_jack(state="idle", action_text="online · listening for tasks"), unsafe_allow_html=True)

    # ─── Brand monthly stats (from Darya's Google Sheets report) ────────────
    report = fetch_report()
    # pick brand stats matching session brand (BELOVEDPETS or TOBYDIC)
    selected_key = "BELOVEDPETS" if brand.lower().startswith("beloved") else "TOBYDIC"
    bs = report.get(selected_key, {})
    st.markdown(f'<div class="section-label" style="margin-top:24px;">📊 {selected_key} · monthly stats (latest month)</div>', unsafe_allow_html=True)
    metric_pairs = [
        ("followers", "Followers"),
        ("reach", "Reach"),
        ("reel views", "Reel views"),
        ("post likes", "Post likes"),
        ("multilink cliks", "Link clicks"),
    ]
    sc = st.columns(5)
    for i, (key, label) in enumerate(metric_pairs):
        latest, prev = trend(bs, key)
        delta = format_delta(latest, prev) or None
        sc[i].metric(label, format_num(latest), delta=delta)

    # ─── Соцсети · живые подписчики по площадкам (БЕЗ Content Factory) ───────
    st.markdown('<div class="section-label" style="margin-top:24px;">📱 Соцсети · подписчики сейчас</div>', unsafe_allow_html=True)
    if brand.lower().startswith("beloved"):
        try:
            soc = socials.fetch_all(socials.BRAND_HANDLES)
        except Exception:
            soc = {}
        plat_labels = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube",
                       "pinterest": "Pinterest", "facebook": "Facebook"}
        soc_cols = st.columns(len(plat_labels))
        for i, (plat, lab) in enumerate(plat_labels.items()):
            human = (soc.get(plat) or {}).get("human", "—")
            soc_cols[i].metric(lab, human)
        st.caption("Тянется с публичных страниц (без логина), кэш 1 ч. «—» = площадка временно "
                   "не отдала данные (TikTok/IG иногда режут серверные запросы) — динамику смотри в "
                   "Google-отчёте выше. Content Factory сюда НЕ входит (отдельный массовый канал).")
    else:
        st.caption("Живые подписчики настроены для BelovedPets. Для Tobydic пришли хэндлы соцсетей — добавлю.")

    # ─── Контент-план · сводка (отдельный сборщик plan_stats) ───────────────
    ps = plan_stats.summarize_plan(brand)
    st.markdown('<div class="section-label" style="margin-top:28px;">📅 Контент-план · сводка</div>', unsafe_allow_html=True)
    kc = st.columns(4)
    kc[0].metric("Постов в плане", ps["total"])
    kc[1].metric("С ТЗ", ps["with_brief"], delta=(f'{ps["brief_pct"]}%' if ps["total"] else None))
    kc[2].metric("Без ТЗ", len(ps["no_brief"]))
    kc[3].metric("На этой неделе", len(ps["this_week"]))
    if ps["total"]:
        b1, b2 = st.columns(2)
        b1.caption("По исполнителям:")
        b1.markdown("  ·  ".join(f"**{k}** — {v}" for k, v in ps["by_owner"].items()) or "—")
        b2.caption("По типам:")
        b2.markdown("  ·  ".join(f"**{k}** — {v}" for k, v in ps["by_type"].items()) or "—")
    if ps["this_week"]:
        st.caption("На этой неделе:")
        for it in ps["this_week"]:
            mark = "💬" if it["has_brief"] else "✍️ (нет ТЗ)"
            st.markdown(f'{mark} **{it["date"]}** · {it["title"]} · 🎬 {it["owner"]}')
    else:
        st.caption("На этой неделе постов в плане нет — открой Content Plan, чтобы добавить.")

    # ─── Pipeline snapshot ──────────────────────────────────────────────────
    concepts = load_concepts()
    drafts = [c for c in concepts if c.get("status") == "draft"]
    approved = [c for c in concepts if c.get("status") == "approved"]
    edits = [c for c in concepts if c.get("status") == "edit"]

    st.markdown('<div class="section-label" style="margin-top:24px;">⚙️ Pipeline</div>', unsafe_allow_html=True)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Awaiting approval", len(drafts))
    p2.metric("Needs edit", len(edits))
    p3.metric("Approved", len(approved))
    p4.metric("Published (mock)", 0)

    # ─── Hot competitor ideas (top 3) ───────────────────────────────────────
    ideas = fetch_competitor_ideas()
    top3 = sorted(ideas, key=lambda i: int(i["views"].rstrip("MK").replace(".", "").replace(",", "") or 0) * (1_000_000 if i["views"].endswith("M") else 1_000), reverse=True)[:3]

    st.markdown(f'<div class="section-label" style="margin-top:24px;">🔥 Hot from competitors · refreshed {last_refresh()}</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for i, idea in enumerate(top3):
        kind_color = {
            "comedy":    ("#EDE9FE","#6D28D9"), "pov": ("#EDE9FE","#6D28D9"),
            "authority": ("#D9F0D1","#3A6B2A"), "education": ("#D9F0D1","#3A6B2A"),
            "asmr":      ("#F4C7C7","#8E2424"), "community": ("#FFF4E0","#92400E"),
        }.get(idea.get("kind"), ("#F0F5FB","#1F2A3F"))
        with cols[i]:
            st.markdown(
                f"""
                <div style="background:#FFF; border:1px solid #D9E2EE; border-radius:12px; padding:14px; height:100%;">
                    <div style="font-size:0.7rem; font-weight:700; color:#4F5B72; text-transform:uppercase; margin-bottom:4px;">{idea['source']}</div>
                    <div style="font-weight:700; color:#060B17; font-style:italic; font-size:0.92rem; line-height:1.3; margin-bottom:8px;">"{idea['hook']}"</div>
                    <div style="display:flex; gap:10px; font-size:0.78rem; color:#4F5B72; margin-bottom:8px;">
                        <span>👀 <strong>{idea['views']}</strong></span>
                        <span>💬 <strong>{idea['comments']:,}</strong></span>
                    </div>
                    <span style="background:{kind_color[0]}; color:{kind_color[1]}; padding:2px 8px; border-radius:100px; font-size:0.66rem; font-weight:800; text-transform:uppercase;">{idea['kind']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ─── Team snapshot ──────────────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:24px;">👥 Team</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    t1.metric("Dina · video", f"{len([c for c in concepts if c.get('format') in ('Reel','AmazonVid')])} briefs")
    t2.metric("Vika · graphics", f"{len([c for c in concepts if c.get('format') in ('Carousel','Static')])} briefs")
    t3.metric("Tanya · TOBYDIC", "—")
