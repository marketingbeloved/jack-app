"""Dashboard — command center: today's content, live followers, team pipeline, hot competitor wins."""

from datetime import date

import streamlit as st

from utils.jack_svg import render_jack
from models.competitor_parser import fetch_competitor_ideas, last_refresh
from models.jack_engine import load_concepts
from models.brand_stats import fetch_report, trend, format_num, format_delta


# ─── June 2026 content plan — kept in sync with content_plan.py ─────────────
JUNE_TODAY_DEMO = {
    "08.06": [{"title": "фото от блогера", "type": "engaging"}],
    "09.06": [{"title": "persian eye tear stains POV", "type": "entertaining"}],
    "10.06": [{"title": "eye wipes carousel uk", "type": "selling"}],
    "11.06": [{"title": "faire canada reel invite", "type": "selling"}],
    "12.06": [{"title": "gut health 30s breakdown", "type": "engaging"}],
}


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

    # ─── Today's pipeline ───────────────────────────────────────────────────
    today_str = date.today().strftime("%d.%m")
    today_items = JUNE_TODAY_DEMO.get(today_str, [])

    st.markdown(f'<div class="section-label" style="margin-top:28px;">📅 Today · {today_str}</div>', unsafe_allow_html=True)
    if today_items:
        type_color = {"engaging":("#D9F0D1","#3A6B2A"), "selling":("#F4C7C7","#8E2424"), "entertaining":("#D7CBE8","#553A8B")}
        for item in today_items:
            bg, fg = type_color.get(item["type"], ("#EEF4FA","#1F2A3F"))
            st.markdown(
                f"""
                <div style="background:#FFF; border:1px solid #D9E2EE; border-radius:10px; padding:10px 14px; margin:4px 0;">
                    <span style="background:{bg}; color:{fg}; padding:2px 10px; border-radius:100px; font-weight:800; font-size:0.7rem; text-transform:uppercase; margin-right:8px;">{item['type']}</span>
                    <strong style="color:#060B17;">{item['title']}</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("Сегодня в КП пусто — открой Content Plan чтобы добавить.")

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
