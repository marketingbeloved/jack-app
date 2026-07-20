"""Content Factory — 3 phones, each branches into 4 socials (tree layout).

Live data: GeeLark API + Telegram bot @belovedpets_factory_bot.
"""

import streamlit as st

from models.geelark import health as geelark_health, list_phones as geelark_phones, get_phone
from models.telegram_bot import health as tg_health, get_updates as tg_updates, count_approvals
from models.socials import fetch_all as fetch_socials, BRAND_HANDLES
from models.content_factory_data import fetch_year as cf_fetch_year, available_months as cf_months, build_lookup as cf_lookup, diagnose as cf_diagnose


PHONES = [
    {
        "id": "vermont",
        "name": "Vermont",
        "geelark_id": "616135880154808620",
        "store": "Amazon",
        "cluster": "ASMR / Emotional",
        "country": "🇺🇸",
        "card_bg": "linear-gradient(135deg, #FFF4E0 0%, #FFE4B5 100%)",
        "card_border": "#FF9900",
        "card_glow": "rgba(255, 153, 0, 0.18)",
    },
    {
        "id": "newyork",
        "name": "New York",
        "geelark_id": "616135949276938540",
        "store": "Shopify",
        "cluster": "Vet Expert",
        "country": "🇺🇸",
        "card_bg": "linear-gradient(135deg, #E7F5E1 0%, #D1E9C5 100%)",
        "card_border": "#5E8E3E",
        "card_glow": "rgba(94, 142, 62, 0.18)",
    },
    {
        "id": "pensilvania",
        "name": "Pensilvania",
        "geelark_id": "616136029354590511",
        "store": "Chewy",
        "cluster": "Reviewer",
        "country": "🇺🇸",
        "card_bg": "linear-gradient(135deg, #FCE7F3 0%, #FBCFE8 100%)",
        "card_border": "#E60023",
        "card_glow": "rgba(230, 0, 35, 0.18)",
    },
]

SOCIALS = [
    {"id": "tiktok",    "name": "TikTok",    "icon": "🎵", "color": "#000000"},
    {"id": "pinterest", "name": "Pinterest", "icon": "📌", "color": "#E60023"},
    {"id": "youtube",   "name": "YouTube",   "icon": "▶️", "color": "#FF0000"},
    {"id": "instagram", "name": "Instagram", "icon": "📷", "color": "#E1306C"},
]

STORE_STYLE = {
    "Amazon":  {"bg": "linear-gradient(135deg, #FF9900 0%, #B7660F 100%)", "color": "#FFFFFF"},
    "Shopify": {"bg": "linear-gradient(135deg, #5E8E3E 0%, #3E6B25 100%)", "color": "#FFFFFF"},
    "Chewy":   {"bg": "linear-gradient(135deg, #F58220 0%, #A24700 100%)", "color": "#FFFFFF"},
}


def _fmt_val(v):
    """Metric value for a leaf card: em dash if missing, thousands-separated if int."""
    if v in (None, ""):
        return "—"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:,}" if isinstance(v, int) else str(v)


def render():
    st.markdown("# 🏭 Content Factory")
    st.caption("3 GeeLark phones · each branches into 4 social channels · live data via GeeLark API + Telegram bot.")

    # ─── Telegram bot — live ─────────────────────────────────────────────────
    tg = tg_health()
    tg_status = "✅" if tg.get("ok") else "⚠️"
    st.markdown(
        f'<div class="section-label">🤖 Telegram bot · {tg.get("message", "—")} {tg_status}</div>',
        unsafe_allow_html=True,
    )
    if tg.get("ok"):
        updates = tg_updates()
        counts = count_approvals(updates)
        bc = st.columns(4)
        bc[0].metric("Messages (24h)", counts["messages"])
        bc[1].metric("Approved", counts["approved"])
        bc[2].metric("Rejected", counts["rejected"])
        bc[3].metric("Pending", counts["pending"])
    else:
        bc = st.columns(4)
        bc[0].metric("Awaiting approval", "—")
        bc[1].metric("Approved", "—")
        bc[2].metric("Rejected", "—")
        bc[3].metric("Posted", "—")
        st.caption("⚠️ Telegram bot not reachable — check TELEGRAM_BOT_TOKEN in CF .env")

    # GeeLark status caption removed — kept polling in background

    st.markdown(_CSS, unsafe_allow_html=True)

    # ─── 3 phones, each as a tree ───────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:28px;">📱 Phone farms — branching to 4 socials each</div>', unsafe_allow_html=True)

    # Pull live GeeLark data once for all phones
    live_phones = {str(p.get("id")): p for p in geelark_phones()}
    status_label = {1: ("🟢", "running"), 2: ("🟡", "stopped"), 3: ("🟠", "starting"), 4: ("🔴", "error")}

    # Content Factory metrics from the SMM report (Supabase table content_factory_metrics)
    cf_rows = cf_fetch_year(2026)
    cf_avail = cf_months(cf_rows)
    cf_month = None
    if cf_avail:
        cf_month = st.selectbox("📅 Metrics month", cf_avail, index=len(cf_avail) - 1)
    else:
        st.caption(f"ℹ️ Content Factory metrics source: {cf_diagnose()}")
    cf_data = cf_lookup(cf_rows, cf_month) if cf_month else {}

    # Brand-wide social followers (real, from public scrape)
    brand_socials = fetch_socials(BRAND_HANDLES)

    st.markdown('<div class="section-label" style="margin-top:24px;">📊 Brand-wide social followers (live)</div>', unsafe_allow_html=True)
    sc = st.columns(5)
    for i, (platform, sdata) in enumerate([("tiktok", "TikTok"), ("instagram", "Instagram"), ("facebook", "Facebook"), ("youtube", "YouTube"), ("pinterest", "Pinterest")]):
        val = brand_socials.get(platform, {})
        sc[i].metric(sdata, val.get("human", "—") if val else "—")

    for phone in PHONES:
        store = STORE_STYLE[phone["store"]]
        live = live_phones.get(phone["geelark_id"], {})
        st_code = live.get("status", 0)
        st_emoji, st_text = status_label.get(st_code, ("⚫", "unknown"))
        proxy_ip = (live.get("proxy") or {}).get("server", "—")
        os_ver = (live.get("equipmentInfo") or {}).get("osVersion", "—")

        # Render each phone as a tree: phone box on left, 4 social branches on right
        branches_html = ""
        for s in SOCIALS:
            slots = cf_data.get((phone["id"], s["id"]), {})
            fo = _fmt_val(slots.get("followers"))
            vi = _fmt_val(slots.get("views"))
            rc = _fmt_val(slots.get("reach"))
            branches_html += f"""
            <div class="branch-row">
                <div class="branch-line"></div>
                <div class="social-leaf" style="border-left-color:{s['color']};">
                    <div class="leaf-head">
                        <span class="leaf-icon" style="color:{s['color']};">{s['icon']}</span>
                        <strong>{s['name']}</strong>
                    </div>
                    <div class="leaf-stats">
                        <span>👥 {fo} followers</span>
                        <span>👀 {vi} views</span>
                        <span>📈 {rc} reach</span>
                    </div>
                </div>
            </div>
            """

        st.markdown(
            f"""
            <div class="tree" style="background:{phone['card_bg']}; border-color:{phone['card_border']}; box-shadow: 0 8px 28px {phone['card_glow']}, 0 2px 6px rgba(6,11,23,0.05);">
                <div class="tree-root">
                    <div class="phone-box" style="border-color:{phone['card_border']};">
                        <div class="phone-flag">{phone['country']}</div>
                        <div class="phone-title">
                            <span class="phone-name">{phone['name']}</span>
                            <span class="phone-arrow">→</span>
                            <span class="store-inline" style="background:{store['bg']};color:{store['color']};">{phone['store']}</span>
                        </div>
                        <div class="phone-cluster">{phone['cluster']}</div>
                        <div class="phone-live">
                            <span class="live-status">{st_emoji} {st_text}</span>
                            <span class="live-meta">{os_ver}</span>
                            <span class="live-meta">🌐 {proxy_ip}</span>
                        </div>
                        <div class="phone-id">id {phone['geelark_id']}</div>
                    </div>
                </div>
                <div class="tree-branches">
                    {branches_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ─── Integration roadmap ─────────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:28px;">🔌 Integration status</div>', unsafe_allow_html=True)
    st.markdown(
        """
        | Source | What it gives | Status |
        | --- | --- | --- |
        | **GeeLark API** | Phone profile state, post history, success/fail per profile | ⏳ keys found, polling next |
        | **Telegram bot** `@belovedpets_factory_bot` | Approval queue, approve/reject events | ⏳ token found, polling next |
        | **TikTok Business API** | Followers, views, engagement per @handle | ⏳ per-account OAuth |
        | **IG Graph API** | Followers, reach, impressions | ⏳ Meta Business token |
        | **YouTube Data API v3** | Channel stats, video views | ⏳ Google API key |
        | **Pinterest API v5** | Pin impressions, saves, monthly views | ⏳ Pinterest token |
        """
    )


_CSS = """
<style>
.tree {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 28px;
    align-items: center;
    background: #FFFFFF;
    border: 1px solid #D9E2EE;
    border-radius: 16px;
    padding: 20px 24px;
    margin: 14px 0;
    box-shadow: 0 2px 6px rgba(6,11,23,0.05);
    position: relative;
}
.tree-root {
    display: flex;
    align-items: center;
    justify-content: center;
}
.phone-box {
    background: linear-gradient(135deg, #FFFFFF 0%, #F0F5FB 100%);
    border: 2px solid #3B5FFF;
    border-radius: 14px;
    padding: 18px 20px;
    text-align: center;
    box-shadow: 0 6px 18px rgba(30,64,255,0.15);
    min-width: 220px;
}
.phone-flag { font-size: 1.6rem; line-height: 1; }
.phone-title {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
    margin: 6px 0 6px 0;
}
.phone-name {
    font-weight: 900;
    font-size: 1.3rem;
    background: linear-gradient(135deg, #3B5FFF 0%, #1B339E 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.phone-arrow {
    color: #94A3B8;
    font-weight: 800;
    font-size: 1.1rem;
}
.store-inline {
    padding: 4px 12px;
    border-radius: 100px;
    font-weight: 900;
    font-size: 0.86rem;
    letter-spacing: 0.02em;
    box-shadow: 0 4px 10px rgba(0,0,0,0.14);
}
.phone-cluster {
    font-size: 0.82rem;
    color: #4F5B72;
    font-weight: 600;
    margin-bottom: 6px;
}
.phone-id {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: #1B339E;
    background: #F0F5FB;
    padding: 3px 8px;
    border-radius: 6px;
    margin-bottom: 12px;
    display: inline-block;
}
.phone-live {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 0.74rem;
    color: #2B3447;
    margin: 6px 0 8px 0;
    font-weight: 600;
}
.phone-live .live-status { font-weight: 800; color: #060B17; }
.phone-live .live-meta { color: #4F5B72; font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; }
.store-badge {
    padding: 6px 14px;
    border-radius: 100px;
    font-weight: 800;
    font-size: 0.84rem;
    letter-spacing: 0.02em;
    display: inline-block;
    box-shadow: 0 4px 10px rgba(0,0,0,0.12);
}

.tree-branches {
    display: flex;
    flex-direction: column;
    gap: 10px;
    position: relative;
}
.branch-row {
    display: flex;
    align-items: center;
    gap: 0;
}
.branch-line {
    width: 36px;
    height: 2px;
    background: linear-gradient(90deg, #3B5FFF 0%, #C8D5E3 100%);
    position: relative;
}
.branch-line::before {
    content: "";
    position: absolute;
    left: -1px;
    top: -4px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #3B5FFF;
}
.social-leaf {
    flex: 1;
    background: #F8FAFD;
    border: 1px solid #E3EDF7;
    border-left: 4px solid;
    border-radius: 10px;
    padding: 10px 14px;
    transition: all 0.15s ease;
}
.social-leaf:hover {
    background: #FFFFFF;
    transform: translateX(2px);
    box-shadow: 0 4px 12px rgba(6,11,23,0.06);
}
.leaf-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}
.leaf-icon { font-size: 1.1rem; }
.leaf-head strong {
    color: #060B17;
    font-weight: 800;
    font-size: 0.92rem;
}
.leaf-stats {
    display: flex;
    gap: 16px;
    font-size: 0.78rem;
    color: #4F5B72;
    font-weight: 500;
}
</style>
"""
