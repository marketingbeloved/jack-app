"""Products Library — full BelovedPets catalogue (58 SKUs) with search, filter, compliance.

Loaded from Content Factory's products.json — single source of truth.
"""

import streamlit as st

from models.products import (
    list_products,
    categories,
    global_compliance,
    short_title,
    safe_phrases,
    forbidden_phrases,
)


CATEGORY_BADGE = {
    "treats":     {"bg": "#FEF3C7", "text": "#92400E", "border": "#FCD34D", "label": "🍖 Treats"},
    "supplement": {"bg": "#D1FAE5", "text": "#065F46", "border": "#6EE7B7", "label": "💊 Supplement"},
    "spray":      {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#93C5FD", "label": "🌫 Spray"},
}


def render():
    cats = categories()
    total = sum(cats.values())

    st.markdown(f"# 📦 Products Library · BelovedPets")
    st.caption(f"Single source of truth · {total} SKUs · loaded from Content Factory `products.json`")

    # ─── Global compliance banner ────────────────────────────────────────────
    gc = global_compliance()
    if gc:
        principle = gc.get("principle", "")
        safe = ", ".join(gc.get("always_use_safe_phrases", []))
        st.markdown(
            f"""
            <div style="background:#F0F5FB; border:1px solid #BFDBFE; border-left:4px solid #3B5FFF;
                        padding:12px 16px; border-radius:10px; margin: 12px 0;">
                <div style="font-weight:800; color:#1E40FF; font-size:0.74rem; letter-spacing:0.08em;
                            text-transform:uppercase; margin-bottom:4px;">⚖️ Global compliance</div>
                <div style="color:#1F2A3F; font-size:0.86rem; font-weight:500;">{principle}</div>
                <div style="color:#4F5B72; font-size:0.78rem; margin-top:4px;">
                    <strong>Safe:</strong> {safe}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ─── Stats by category ──────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TOTAL SKUs", total)
    c2.metric("TREATS",     cats.get("treats", 0))
    c3.metric("SUPPLEMENTS", cats.get("supplement", 0))
    c4.metric("SPRAYS",     cats.get("spray", 0))

    # ─── Filter bar ─────────────────────────────────────────────────────────
    fc1, fc2 = st.columns([1, 3])
    cat_filter = fc1.selectbox("Category", ["all", "treats", "supplement", "spray"], index=0)
    search = fc2.text_input("Search by title or description", placeholder="e.g. calming, eye, hemp...")

    items = list_products(category=cat_filter, search=search if search else None)
    st.caption(f"Showing **{len(items)}** of {total} products")

    # ─── Product grid ───────────────────────────────────────────────────────
    st.markdown(_CSS, unsafe_allow_html=True)
    for p in items:
        badge = CATEGORY_BADGE.get(p.get("category"), CATEGORY_BADGE["treats"])
        title = short_title(p, 80)
        desc = p.get("description_short", "")[:200].replace("\n", " ").replace("✅", "")
        price = p.get("price_usd", "—")
        url = p.get("url", "#")

        with st.container():
            st.markdown(
                f"""
                <div class="product-card">
                    <div class="product-head">
                        <span class="cat-badge" style="background:{badge['bg']};color:{badge['text']};border-color:{badge['border']};">{badge['label']}</span>
                        <span class="price">${price}</span>
                    </div>
                    <div class="product-title">{title}</div>
                    <div class="product-desc">{desc}…</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("⚖️ Compliance & writing rules for Jack", expanded=False):
                safe = safe_phrases(p)
                forb = forbidden_phrases(p)
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.markdown("**✅ Safe phrases**")
                    for s in safe[:12]:
                        st.markdown(f"- {s}")
                with cc2:
                    st.markdown("**❌ Forbidden**")
                    for f in forb[:12]:
                        st.markdown(f"- {f}")
                st.link_button("Open on belovedpets.com", url)


_CSS = """
<style>
.product-card {
    background: #FFFFFF;
    border: 1px solid #D9E2EE;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 6px;
    transition: all 0.15s ease;
}
.product-card:hover {
    border-color: #3B5FFF;
    box-shadow: 0 6px 18px rgba(30,64,255,0.08);
}
.product-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}
.cat-badge {
    padding: 2px 10px;
    border-radius: 100px;
    border: 1px solid;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.price {
    background: linear-gradient(135deg, #3B5FFF 0%, #1B339E 100%);
    color: #FFFFFF;
    padding: 3px 10px;
    border-radius: 100px;
    font-weight: 800;
    font-size: 0.78rem;
}
.product-title {
    font-weight: 700;
    color: #060B17;
    font-size: 0.92rem;
    line-height: 1.3;
    margin-bottom: 4px;
}
.product-desc {
    font-size: 0.8rem;
    color: #4F5B72;
    line-height: 1.45;
    font-weight: 500;
}
</style>
"""
