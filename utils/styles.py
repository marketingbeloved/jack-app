"""Global CSS — vibrant 3-tone aurora (azure + lazurite + coral) with neon sidebar."""

import streamlit as st


CSS = r"""
<style>
@import url('https://rsms.me/inter/inter.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ============================================================
   PALETTE
   ============================================================ */
:root {
    /* Surfaces — cool white base with strong aurora */
    --bg-base: #F4F7FC;
    --bg-elev-1: #FFFFFF;
    --bg-elev-2: #F0F5FB;
    --bg-elev-3: #E3EDF7;
    --bg-glass: rgba(255, 255, 255, 0.78);

    --border: #D9E2EE;
    --border-bright: #B6C5D9;
    --border-strong: #6B7A91;

    /* Text — high contrast */
    --text-primary: #060B17;
    --text-secondary: #1F2A3F;
    --text-tertiary: #4F5B72;
    --text-on-accent: #FFFFFF;

    /* Accents */
    --azure: #1E40FF;
    --azure-bright: #3B5FFF;
    --azure-neon: #4D7AFF;
    --azure-deep: #1330CC;
    --azure-soft: rgba(30, 64, 255, 0.12);
    --azure-glow: rgba(61, 95, 255, 0.45);

    --lazurite: #26619C;
    --lazurite-bright: #3B7CB8;
    --lazurite-soft: rgba(38, 97, 156, 0.10);

    --coral: #FF6B5C;
    --coral-bright: #FF8A78;
    --coral-deep: #E64A19;
    --coral-soft: rgba(255, 107, 92, 0.14);
    --coral-glow: rgba(255, 138, 120, 0.40);

    --violet: #8B5CF6;
}

html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif !important;
    font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11', 'ss01';
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    color: var(--text-primary);
}

/* AURORA background — saturated 3-tone blobs */
.stApp {
    background:
        radial-gradient(ellipse 70% 50% at 15% 0%, rgba(0, 212, 255, 0.32), transparent 55%),
        radial-gradient(ellipse 65% 45% at 90% 15%, rgba(255, 107, 92, 0.30), transparent 55%),
        radial-gradient(ellipse 60% 50% at 50% 105%, rgba(46, 92, 255, 0.25), transparent 55%),
        radial-gradient(ellipse 60% 60% at 0% 80%, rgba(139, 92, 246, 0.18), transparent 50%),
        var(--bg-base);
    background-attachment: fixed;
}

.main .block-container {
    max-width: 1320px;
    padding-top: 2rem;
    padding-bottom: 5rem;
}

/* ============================================================
   TYPOGRAPHY
   ============================================================ */
h1 {
    font-weight: 900 !important;
    letter-spacing: -0.035em !important;
    color: var(--text-primary) !important;
    margin-bottom: 0.3em !important;
    font-size: 2.5rem !important;
    line-height: 1.05 !important;
}
h2 {
    font-weight: 800 !important;
    letter-spacing: -0.022em !important;
    color: var(--text-primary) !important;
}
h3 {
    font-weight: 700 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.012em !important;
}
p, .stMarkdown, label, span {
    color: var(--text-secondary);
    font-weight: 450;
}
.stMarkdown strong, p strong { color: var(--text-primary); font-weight: 700; }
code, pre {
    font-family: 'JetBrains Mono', monospace !important;
    background: var(--bg-elev-3) !important;
    color: var(--azure-deep) !important;
    border-radius: 6px !important;
}
::selection { background: var(--azure-soft); color: var(--text-primary); }

/* ============================================================
   SIDEBAR — brand logos scattered as background-image layers
   (muted via opacity overlay so text stays clean)
   ============================================================ */
[data-testid="stSidebar"]::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(30, 64, 255, 0.55) 0%, rgba(27, 51, 158, 0.55) 100%);
    z-index: 1;
    pointer-events: none;
}
[data-testid="stSidebar"] > div:first-child {
    position: relative;
    z-index: 2;
}
[data-testid="stSidebar"] {
    background:
        /* Tonal watermark pattern — white outline icons, opacity ~8% */
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M16.6 6.7a3.5 3.5 0 0 1-2.7-3V3H11.5v9.8a2 2 0 0 1-3.7 1.2 2 2 0 0 1 1.7-3.4 2 2 0 0 1 .6.1V8.3a4.7 4.7 0 0 0-5 4.5 4.4 4.4 0 0 0 7.8 2.7v-5a5.7 5.7 0 0 0 3.3 1V9.3a3.5 3.5 0 0 1-1.3-.1z' fill='rgba(255,255,255,0.20)'/></svg>") 88% 17% / 22px 22px no-repeat,
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M16.6 6.7a3.5 3.5 0 0 1-2.7-3V3H11.5v9.8a2 2 0 0 1-3.7 1.2 2 2 0 0 1 1.7-3.4 2 2 0 0 1 .6.1V8.3a4.7 4.7 0 0 0-5 4.5 4.4 4.4 0 0 0 7.8 2.7v-5a5.7 5.7 0 0 0 3.3 1V9.3a3.5 3.5 0 0 1-1.3-.1z' fill='rgba(255,255,255,0.20)'/></svg>") 6% 70% / 20px 20px no-repeat,
        /* Instagram outline */
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.20)' stroke-width='1.8'><rect x='3' y='3' width='18' height='18' rx='5'/><circle cx='12' cy='12' r='4'/><circle cx='17.5' cy='6.5' r='1' fill='rgba(255,255,255,0.20)'/></svg>") 8% 38% / 22px 22px no-repeat,
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.20)' stroke-width='1.8'><rect x='3' y='3' width='18' height='18' rx='5'/><circle cx='12' cy='12' r='4'/><circle cx='17.5' cy='6.5' r='1' fill='rgba(255,255,255,0.20)'/></svg>") 90% 70% / 22px 22px no-repeat,
        /* Facebook outline */
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M14 12h2.4l.4-3H14V7.3c0-.9.3-1.5 1.5-1.5H17V3.1c-.3 0-1.2-.1-2.3-.1-2.3 0-3.7 1.4-3.7 3.9V9H8.6v3H11v8h3v-8z' fill='rgba(255,255,255,0.20)'/></svg>") 90% 38% / 22px 22px no-repeat,
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M14 12h2.4l.4-3H14V7.3c0-.9.3-1.5 1.5-1.5H17V3.1c-.3 0-1.2-.1-2.3-.1-2.3 0-3.7 1.4-3.7 3.9V9H8.6v3H11v8h3v-8z' fill='rgba(255,255,255,0.20)'/></svg>") 8% 17% / 20px 20px no-repeat,
        /* YouTube outline */
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M10 8.5v7l6-3.5z' fill='rgba(255,255,255,0.20)'/></svg>") 88% 90% / 22px 22px no-repeat,
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M10 8.5v7l6-3.5z' fill='rgba(255,255,255,0.20)'/></svg>") 92% 17% / 20px 20px no-repeat,
        /* Pinterest outline */
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 2a10 10 0 0 0-3.7 19.3c-.1-.8 0-2 .2-2.8.2-.7 1.2-5 1.2-5s-.3-.6-.3-1.5c0-1.4.8-2.4 1.8-2.4.9 0 1.3.6 1.3 1.4 0 .9-.5 2.2-.8 3.4-.2.9.5 1.7 1.4 1.7 1.7 0 3-1.8 3-4.4 0-2.3-1.7-4-4-4-2.8 0-4.4 2.1-4.4 4.3 0 .8.3 1.7.7 2.2.1.1.1.2.1.3l-.3 1.1c0 .2-.2.2-.4.1-1.2-.6-1.9-2.3-1.9-3.7 0-3 2.2-5.7 6.3-5.7 3.3 0 5.9 2.4 5.9 5.5 0 3.3-2.1 5.9-5 5.9-1 0-1.9-.5-2.2-1.1l-.6 2.3c-.2.8-.8 1.8-1.2 2.4A10 10 0 1 0 12 2z' fill='rgba(255,255,255,0.20)'/></svg>") 90% 55% / 22px 22px no-repeat,
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 2a10 10 0 0 0-3.7 19.3c-.1-.8 0-2 .2-2.8.2-.7 1.2-5 1.2-5s-.3-.6-.3-1.5c0-1.4.8-2.4 1.8-2.4.9 0 1.3.6 1.3 1.4 0 .9-.5 2.2-.8 3.4-.2.9.5 1.7 1.4 1.7 1.7 0 3-1.8 3-4.4 0-2.3-1.7-4-4-4-2.8 0-4.4 2.1-4.4 4.3 0 .8.3 1.7.7 2.2.1.1.1.2.1.3l-.3 1.1c0 .2-.2.2-.4.1-1.2-.6-1.9-2.3-1.9-3.7 0-3 2.2-5.7 6.3-5.7 3.3 0 5.9 2.4 5.9 5.5 0 3.3-2.1 5.9-5 5.9-1 0-1.9-.5-2.2-1.1l-.6 2.3c-.2.8-.8 1.8-1.2 2.4A10 10 0 1 0 12 2z' fill='rgba(255,255,255,0.20)'/></svg>") 8% 55% / 22px 22px no-repeat,
        /* Top area — subtle hearts watermark */
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 21s-7-4.5-9-9c-1.5-3.5 1-7 4.5-7 2 0 3.5 1 4.5 2.5C13 6 14.5 5 16.5 5 20 5 22.5 8.5 21 12c-2 4.5-9 9-9 9z' fill='rgba(255,255,255,0.22)'/></svg>") 25% 4% / 18px 18px no-repeat,
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 21s-7-4.5-9-9c-1.5-3.5 1-7 4.5-7 2 0 3.5 1 4.5 2.5C13 6 14.5 5 16.5 5 20 5 22.5 8.5 21 12c-2 4.5-9 9-9 9z' fill='rgba(255,255,255,0.22)'/></svg>") 60% 2% / 16px 16px no-repeat,
        url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 21s-7-4.5-9-9c-1.5-3.5 1-7 4.5-7 2 0 3.5 1 4.5 2.5C13 6 14.5 5 16.5 5 20 5 22.5 8.5 21 12c-2 4.5-9 9-9 9z' fill='rgba(255,255,255,0.22)'/></svg>") 80% 9% / 14px 14px no-repeat,
        /* Base aurora gradient */
        radial-gradient(ellipse 80% 40% at 50% 0%, rgba(139, 92, 246, 0.30), transparent 60%),
        radial-gradient(ellipse 80% 40% at 50% 100%, rgba(255, 107, 92, 0.20), transparent 60%),
        linear-gradient(180deg, #3B5FFF 0%, #1E40FF 50%, #1B339E 100%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.10) !important;
    box-shadow: 6px 0 32px rgba(30, 64, 255, 0.30);
    position: relative;
}
[data-testid="stSidebar"] > div:first-child {
    position: relative;
    padding: 20px 18px !important;
}
/* Make sure direct sidebar children sit above decor */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
    position: relative;
    z-index: 3;
}

/* Floating decoration layer (rendered via st.markdown into first column) */
.sidebar-decor {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
}
.sidebar-decor span {
    position: absolute;
    font-size: 28px;
    opacity: 0.55;
    user-select: none;
    animation: deco-float 8s ease-in-out infinite;
    text-shadow: 0 4px 12px rgba(0, 0, 0, 0.45);
    filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.35));
}
.sidebar-decor span.lg { font-size: 44px; opacity: 0.65; }
.sidebar-decor span.md { font-size: 34px; opacity: 0.60; }
.sidebar-decor span.sm { font-size: 22px; opacity: 0.50; }
.sidebar-decor span.logo {
    width: 38px;
    height: 38px;
    background-size: 100% 100%;
    background-repeat: no-repeat;
    border-radius: 9px;
    opacity: 0.75;
    text-shadow: none;
    filter: drop-shadow(0 6px 14px rgba(0,0,0,0.45));
}
.sidebar-decor span.logo.big { width: 52px; height: 52px; opacity: 0.80; }
.sidebar-decor span.logo.tt   { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect width='24' height='24' rx='5' fill='%23000'/><path d='M16.6 6.7a3.5 3.5 0 0 1-2.7-3V3H11.5v9.8a2 2 0 0 1-3.7 1.2 2 2 0 0 1 1.7-3.4 2 2 0 0 1 .6.1V8.3a4.7 4.7 0 0 0-5 4.5 4.4 4.4 0 0 0 7.8 2.7v-5a5.7 5.7 0 0 0 3.3 1V9.3a3.5 3.5 0 0 1-1.3-.1z' fill='%23fff'/></svg>"); }
.sidebar-decor span.logo.ig   { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><defs><linearGradient id='ig' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%23F58529'/><stop offset='0.5' stop-color='%23DD2A7B'/><stop offset='1' stop-color='%238134AF'/></linearGradient></defs><rect width='24' height='24' rx='6' fill='url(%23ig)'/><circle cx='12' cy='12' r='4' fill='none' stroke='%23fff' stroke-width='2'/><circle cx='18' cy='6' r='1.3' fill='%23fff'/></svg>"); }
.sidebar-decor span.logo.fb   { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect width='24' height='24' rx='12' fill='%231877F2'/><path d='M14 12h2.4l.4-3H14V7.3c0-.9.3-1.5 1.5-1.5H17V3.1c-.3 0-1.2-.1-2.3-.1-2.3 0-3.7 1.4-3.7 3.9V9H8.6v3H11v8h3v-8z' fill='%23fff'/></svg>"); }
.sidebar-decor span.logo.yt   { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect width='24' height='24' rx='5' fill='%23FF0000'/><path d='M10 8.5v7l6-3.5z' fill='%23fff'/></svg>"); }
.sidebar-decor span.logo.pin  { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='12' r='11' fill='%23E60023'/><path d='M12 5a7 7 0 0 0-2.6 13.5c-.1-.6 0-1.4.1-2 .1-.5 1-4 1-4s-.3-.5-.3-1.2c0-1.1.6-1.9 1.4-1.9.6 0 1 .5 1 1 0 .7-.4 1.7-.6 2.6-.2.7.4 1.4 1.1 1.4 1.4 0 2.5-1.5 2.5-3.6 0-1.9-1.4-3.2-3.3-3.2-2.3 0-3.6 1.7-3.6 3.5 0 .7.3 1.4.6 1.8.1.1.1.1 0 .2 0 .2-.2.7-.2.9 0 .1-.1.2-.3.1-.9-.5-1.6-1.8-1.6-3 0-2.4 1.8-4.6 5.1-4.6 2.7 0 4.7 1.9 4.7 4.4 0 2.7-1.7 4.8-4 4.8-.8 0-1.5-.4-1.7-.9 0 0-.4 1.5-.5 1.8-.2.6-.6 1.5-1 2A7 7 0 1 0 12 5z' fill='%23fff'/></svg>"); }

@keyframes deco-float {
    0%, 100% { transform: translateY(0) rotate(var(--rot, 0deg)); }
    50%      { transform: translateY(-8px) rotate(calc(var(--rot, 0deg) + 4deg)); }
}

.sidebar-decor span:nth-child(1)  { top: 3%;  left: 6%;  --rot: -14deg; animation-delay: 0s;   }
.sidebar-decor span:nth-child(2)  { top: 5%;  right: 8%; --rot:  16deg; animation-delay: 0.3s; }
.sidebar-decor span:nth-child(3)  { top: 11%; left: 72%; --rot:  -6deg; animation-delay: 0.6s; }
.sidebar-decor span:nth-child(4)  { top: 16%; left: 4%;  --rot:  20deg; animation-delay: 0.9s; }
.sidebar-decor span:nth-child(5)  { top: 22%; right: 4%; --rot: -14deg; animation-delay: 1.2s; }
.sidebar-decor span:nth-child(6)  { top: 29%; left: 76%; --rot:  10deg; animation-delay: 1.5s; }
.sidebar-decor span:nth-child(7)  { top: 36%; left: 8%;  --rot: -22deg; animation-delay: 1.8s; }
.sidebar-decor span:nth-child(8)  { top: 42%; right: 14%;--rot:  12deg; animation-delay: 2.1s; }
.sidebar-decor span:nth-child(9)  { top: 49%; left: 3%;  --rot:   8deg; animation-delay: 2.4s; }
.sidebar-decor span:nth-child(10) { top: 55%; right: 6%; --rot: -10deg; animation-delay: 2.7s; }
.sidebar-decor span:nth-child(11) { top: 62%; left: 72%; --rot:  18deg; animation-delay: 3.0s; }
.sidebar-decor span:nth-child(12) { top: 68%; left: 6%;  --rot: -14deg; animation-delay: 3.3s; }
.sidebar-decor span:nth-child(13) { top: 75%; right: 10%;--rot:   8deg; animation-delay: 3.6s; }
.sidebar-decor span:nth-child(14) { top: 81%; left: 22%; --rot: -18deg; animation-delay: 3.9s; }
.sidebar-decor span:nth-child(15) { top: 87%; right: 4%; --rot:  14deg; animation-delay: 4.2s; }
.sidebar-decor span:nth-child(16) { top: 92%; left: 8%;  --rot: -10deg; animation-delay: 4.5s; }
.sidebar-decor span:nth-child(17) { top: 97%; right: 22%;--rot:   6deg; animation-delay: 4.8s; }
.sidebar-decor span:nth-child(18) { top: 8%;  left: 38%; --rot:  -4deg; animation-delay: 1.0s; }
.sidebar-decor span:nth-child(19) { top: 45%; left: 42%; --rot:  12deg; animation-delay: 2.5s; }
.sidebar-decor span:nth-child(20) { top: 78%; left: 44%; --rot: -16deg; animation-delay: 3.8s; }

/* Brand social pills with real logos + follower counts */
.brand-socials {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 6px;
}
.brand-socials .soc-pill {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 10px;
    color: #FFFFFF !important;
    text-decoration: none !important;
    transition: all 0.15s ease;
    backdrop-filter: blur(8px);
}
.brand-socials .soc-pill:hover {
    background: rgba(255, 255, 255, 0.22);
    border-color: rgba(255, 255, 255, 0.50);
    transform: translateX(2px);
    text-decoration: none !important;
}
.brand-socials .soc-meta {
    display: flex;
    flex-direction: column;
    line-height: 1.1;
    flex: 1;
}
.brand-socials .soc-meta strong {
    font-size: 0.82rem;
    font-weight: 700;
    color: #FFFFFF !important;
}
.brand-socials .soc-meta small {
    font-size: 0.7rem;
    color: rgba(255,255,255,0.72);
    margin-top: 2px;
    font-weight: 500;
}

/* Social logos — real-brand SVG-style backgrounds */
.brand-socials .soc-logo {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    flex-shrink: 0;
    background-size: 70% 70%;
    background-repeat: no-repeat;
    background-position: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.18);
}
.tt-logo  { background-color: #000000; background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'><path d='M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5.8 20.1a6.34 6.34 0 0 0 10.86-4.43V8.71a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1.84-.14z'/></svg>"); }
.ig-logo  { background-image: linear-gradient(45deg, #F58529 0%, #DD2A7B 50%, #8134AF 100%); background-size: 80%; background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'><path d='M12 2.16c3.2 0 3.58 0 4.85.07 3.25.15 4.77 1.69 4.92 4.92.06 1.27.07 1.65.07 4.85s0 3.58-.07 4.85c-.15 3.23-1.66 4.77-4.92 4.92-1.27.06-1.64.07-4.85.07s-3.58 0-4.85-.07c-3.26-.15-4.77-1.7-4.92-4.92C2.16 15.58 2.16 15.2 2.16 12s0-3.58.07-4.85C2.38 3.92 3.9 2.38 7.15 2.23 8.42 2.18 8.8 2.16 12 2.16zM12 0C8.74 0 8.33 0 7.05.07 2.7.27.27 2.69.07 7.05.01 8.33 0 8.74 0 12s.01 3.67.07 4.95c.2 4.36 2.62 6.78 6.98 6.98C8.33 23.99 8.74 24 12 24s3.67-.01 4.95-.07c4.36-.2 6.78-2.62 6.98-6.98.06-1.28.07-1.69.07-4.95s-.01-3.67-.07-4.95C23.74 2.69 21.32.27 16.95.07 15.67.01 15.26 0 12 0zm0 5.84a6.16 6.16 0 1 0 0 12.32 6.16 6.16 0 0 0 0-12.32zm0 10.16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.4-11.85a1.44 1.44 0 1 0 0 2.88 1.44 1.44 0 0 0 0-2.88z'/></svg>"); background-color: #E1306C; }
.fb-logo  { background-color: #1877F2; background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'><path d='M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.79-4.69 4.53-4.69 1.31 0 2.69.24 2.69.24v2.97h-1.52c-1.5 0-1.96.93-1.96 1.89v2.27h3.34l-.53 3.5h-2.8V24C19.61 23.1 24 18.1 24 12.07z'/></svg>"); }
.yt-logo  { background-color: #FF0000; background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'><path d='M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8zM9.6 15.6V8.4l6.2 3.6-6.2 3.6z'/></svg>"); }
.pin-logo { background-color: #E60023; background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'><path d='M12 0a12 12 0 0 0-4.37 23.18c-.06-1 0-2.2.21-3.1.23-1 1.5-6.34 1.5-6.34s-.37-.74-.37-1.84c0-1.72 1-3 2.24-3 1.06 0 1.56.79 1.56 1.74 0 1.06-.67 2.65-1.02 4.12-.3 1.23.62 2.24 1.83 2.24 2.19 0 3.88-2.32 3.88-5.66 0-2.96-2.13-5.03-5.17-5.03-3.52 0-5.59 2.64-5.59 5.37 0 1.06.41 2.2.92 2.82.1.12.11.23.08.36-.09.36-.29 1.16-.33 1.32-.05.21-.17.26-.4.16-1.5-.7-2.43-2.89-2.43-4.65 0-3.79 2.75-7.27 7.94-7.27 4.17 0 7.41 2.97 7.41 6.94 0 4.14-2.61 7.48-6.24 7.48-1.22 0-2.36-.63-2.75-1.39 0 0-.6 2.3-.75 2.85-.27 1.04-1 2.35-1.49 3.15A12 12 0 1 0 12 0z'/></svg>"); }

[data-testid="stSidebar"] * {
    color: rgba(255, 255, 255, 0.94) !important;
}
[data-testid="stSidebar"] h2 {
    color: #FFFFFF !important;
    font-size: 1.55rem !important;
    -webkit-text-fill-color: #FFFFFF !important;
    font-weight: 900 !important;
    letter-spacing: -0.025em !important;
    text-shadow: 0 2px 12px rgba(0, 0, 0, 0.18);
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: rgba(255, 255, 255, 0.78) !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] [data-baseweb="radio"] label {
    padding: 11px 14px !important;
    border-radius: 10px !important;
    transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1) !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    color: rgba(255, 255, 255, 0.88) !important;
    margin: 2px 0 !important;
    background: rgba(255, 255, 255, 0.04) !important;
}
[data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
    background: rgba(255, 255, 255, 0.18) !important;
    color: #FFFFFF !important;
    transform: translateX(2px);
}
[data-testid="stSidebar"] [data-baseweb="radio"] [aria-checked="true"] + label,
[data-testid="stSidebar"] [data-baseweb="radio"] input:checked + div + label {
    background: rgba(255, 255, 255, 0.22) !important;
    color: #FFFFFF !important;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.30) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: rgba(255, 255, 255, 0.16) !important;
    border-color: rgba(255, 255, 255, 0.30) !important;
    color: #FFFFFF !important;
    backdrop-filter: blur(10px);
}
[data-testid="stSidebar"] [data-baseweb="select"] input {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255, 255, 255, 0.18) !important;
    opacity: 1 !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong {
    color: #FFFFFF !important;
}

/* ============================================================
   BUTTONS
   ============================================================ */
.stButton > button {
    border-radius: 10px !important;
    border: 1px solid var(--border) !important;
    background: #FFFFFF !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 10px 18px !important;
    transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 1px 3px rgba(6, 11, 23, 0.06) !important;
}
.stButton > button:hover {
    background: #FFFFFF !important;
    border-color: var(--azure) !important;
    color: var(--azure-deep) !important;
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(14, 165, 233, 0.22), 0 2px 4px rgba(6, 11, 23, 0.06) !important;
}
.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] button {
    background: #1B339E !important;
    color: #FFFFFF !important;
    border: 1px solid #0E2599 !important;
    font-weight: 800 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.30);
    box-shadow: 0 4px 14px rgba(27,51,158,0.35), inset 0 1px 0 rgba(255,255,255,0.18) !important;
}
.stButton > button[kind="primary"] *,
[data-testid="stFormSubmitButton"] button * {
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button:hover {
    background: #0E2599 !important;
    transform: translateY(-1px);
    box-shadow: 0 10px 24px rgba(27,51,158,0.50) !important;
}
.stButton > button:disabled {
    opacity: 0.4 !important;
}

/* ============================================================
   METRIC CARDS
   ============================================================ */
[data-testid="metric-container"] {
    background: var(--bg-glass);
    padding: 20px 22px;
    border-radius: 14px;
    border: 1px solid var(--border);
    backdrop-filter: blur(14px);
    box-shadow: 0 1px 4px rgba(6, 11, 23, 0.05);
    transition: all 0.2s ease;
}
[data-testid="metric-container"]:hover {
    border-color: var(--coral);
    box-shadow: 0 12px 32px rgba(255, 107, 92, 0.18);
    transform: translateY(-1px);
}
[data-testid="metric-container"] label {
    font-size: 0.74rem !important;
    color: var(--text-secondary) !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.95rem !important;
    font-weight: 800 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.025em !important;
}

/* ============================================================
   TABS
   ============================================================ */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 1px 3px rgba(6, 11, 23, 0.04);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 8px 16px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: var(--text-tertiary) !important;
    background: transparent !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #3B5FFF 0%, #1B339E 60%, #FF6B5C 130%) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 16px rgba(46, 92, 255, 0.35) !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.35);
    font-weight: 800 !important;
}
.stTabs [aria-selected="true"] * {
    color: #FFFFFF !important;
}
.stTabs [aria-selected="true"] p,
.stTabs [aria-selected="true"] span {
    color: #FFFFFF !important;
    font-weight: 800 !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.35);
}

/* ============================================================
   FORMS
   ============================================================ */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] {
    border-radius: 10px !important;
}
[data-baseweb="input"] > div, [data-baseweb="textarea"] > div, [data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border-color: var(--border) !important;
    color: var(--text-primary) !important;
}
[data-baseweb="input"]:focus-within > div,
[data-baseweb="textarea"]:focus-within > div,
[data-baseweb="select"]:focus-within > div {
    border-color: var(--azure) !important;
    box-shadow: 0 0 0 3px var(--azure-soft) !important;
}

/* ============================================================
   DIVIDERS / EXPANDERS / ALERTS
   ============================================================ */
hr { margin: 2rem 0 !important; border-color: var(--border) !important; opacity: 0.8; }

[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    background: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(6, 11, 23, 0.04) !important;
}
[data-testid="stExpander"] summary { color: var(--text-primary) !important; }

[data-testid="stAlert"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
    box-shadow: 0 1px 3px rgba(6, 11, 23, 0.04) !important;
}

/* ============================================================
   HERO CARD — saturated tri-color aurora
   ============================================================ */
.jack-hero {
    position: relative;
    background:
        radial-gradient(ellipse 70% 100% at 100% 0%, rgba(255, 107, 92, 0.42), transparent 55%),
        radial-gradient(ellipse 70% 100% at 0% 0%, rgba(0, 212, 255, 0.42), transparent 55%),
        radial-gradient(ellipse 60% 90% at 50% 120%, rgba(46, 92, 255, 0.30), transparent 50%),
        linear-gradient(135deg, #FFFFFF 0%, #F4F8FE 60%, #FFF7F4 100%);
    border: 1px solid rgba(217, 226, 238, 0.7);
    border-radius: 24px;
    padding: 40px 44px;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 36px;
    align-items: center;
    box-shadow:
        0 24px 60px rgba(46, 92, 255, 0.18),
        0 12px 32px rgba(255, 107, 92, 0.14),
        0 1px 0 rgba(255, 255, 255, 0.7) inset;
    margin-bottom: 32px;
    overflow: hidden;
}
.jack-hero h1 {
    background: linear-gradient(135deg, #060B17 0%, #3B5FFF 35%, #1B339E 65%, #FF6B5C 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2.7rem !important;
    margin: 8px 0 12px 0 !important;
}
.jack-hero.compact {
    padding: 28px 32px !important;
    display: block !important;
    grid-template-columns: none !important;
}
.jack-hero.compact h1 { font-size: 2.2rem !important; margin-top: 12px !important; }
.jack-hero .subtitle {
    color: var(--text-secondary);
    font-size: 1.05rem;
    line-height: 1.6;
    max-width: 680px;
    font-weight: 500;
}
.jack-hero strong { color: var(--text-primary); }

/* Status pill */
.jack-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, rgba(0, 212, 255, 0.18) 0%, rgba(255, 107, 92, 0.18) 100%);
    color: var(--azure-deep);
    padding: 6px 14px;
    border-radius: 100px;
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    border: 1px solid rgba(14, 165, 233, 0.30);
    box-shadow: 0 0 24px var(--azure-glow);
    text-transform: uppercase;
}
.jack-status-pill .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--azure);
    box-shadow: 0 0 10px var(--azure-neon);
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.85); }
}

/* Avatar frame — neon tri-color ring */
.jack-avatar-frame {
    position: relative;
    width: 156px;
    height: 156px;
}
.jack-avatar-frame::before {
    content: "";
    position: absolute;
    inset: -5px;
    border-radius: 50%;
    background: conic-gradient(from 0deg, #3B5FFF, #1B339E, #8B5CF6, #FF6B5C, #3B5FFF);
    animation: spin 8s linear infinite;
    opacity: 0.85;
    z-index: 0;
    filter: blur(0.5px);
}
@keyframes spin { to { transform: rotate(360deg); } }
.jack-avatar {
    position: relative;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: #FFFFFF;
    overflow: hidden;
    z-index: 1;
    border: 4px solid #FFFFFF;
    box-shadow: 0 12px 32px rgba(46, 92, 255, 0.30);
}
.jack-avatar img, .jack-avatar svg { width: 100%; height: 100%; object-fit: cover; }

/* ============================================================
   ACTION CARDS
   ============================================================ */
.action-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 14px;
    margin: 16px 0;
}
.action-card {
    position: relative;
    background: var(--bg-glass);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px 24px;
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    backdrop-filter: blur(12px);
    overflow: hidden;
}
.action-card::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, transparent 50%, var(--azure-soft) 80%, var(--coral-soft) 100%);
    opacity: 0;
    transition: opacity 0.25s ease;
}
.action-card:hover {
    border-color: var(--azure);
    transform: translateY(-3px);
    box-shadow: 0 14px 36px rgba(14, 165, 233, 0.18), 0 6px 20px rgba(255, 107, 92, 0.12);
    background: #FFFFFF;
}
.action-card:hover::after { opacity: 1; }
.action-card .icon { font-size: 1.7rem; margin-bottom: 12px; display: block; }
.action-card .title { font-weight: 700; font-size: 0.98rem; color: var(--text-primary); letter-spacing: -0.01em; }
.action-card .desc { font-size: 0.84rem; color: var(--text-secondary); margin-top: 6px; line-height: 1.45; font-weight: 500; }
.action-card .arrow {
    position: absolute; top: 22px; right: 22px;
    color: var(--text-tertiary); transition: all 0.2s ease;
}
.action-card:hover .arrow { color: var(--azure); transform: translate(2px, -2px); }
.action-card.disabled { opacity: 0.6; cursor: default; }
.action-card.disabled:hover { transform: none; border-color: var(--border); box-shadow: none; background: var(--bg-glass); }
.action-card.disabled .arrow { display: none; }
.action-card.disabled::after { display: none; }

.action-card .badge-coming {
    position: absolute;
    top: 18px; right: 18px;
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--coral-deep);
    background: var(--coral-soft);
    border: 1px solid rgba(255, 107, 92, 0.30);
    padding: 2px 8px;
    border-radius: 100px;
    font-weight: 800;
}

/* ============================================================
   SECTION LABEL
   ============================================================ */
.section-label {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.74rem;
    color: var(--text-secondary);
    font-weight: 800;
    margin: 0 0 14px 0;
}

/* ============================================================
   JACK AVATAR BLOCK
   ============================================================ */
.jack-portrait-wrap {
    position: relative;
    width: 100%;
    max-width: 260px;
    margin: 0 auto;
    aspect-ratio: 1 / 1;
    border-radius: 24px;
    padding: 14px;
    background:
        radial-gradient(ellipse 100% 100% at 50% 0%, rgba(61, 95, 255, 0.32), transparent 65%),
        radial-gradient(ellipse 70% 70% at 50% 100%, rgba(255, 107, 92, 0.18), transparent 70%),
        linear-gradient(160deg, #F0F5FB 0%, #FFFFFF 60%, #FFF7F4 100%);
    border: 1px solid #D9E2EE;
    box-shadow: 0 14px 36px rgba(6,11,23,0.10);
    overflow: hidden;
}
.jack-portrait-wrap::before {
    content: "";
    position: absolute;
    inset: 8px;
    border-radius: 50%;
    background: conic-gradient(from 0deg, #3B5FFF, #1B339E, #FF6B5C, #8B5CF6, #3B5FFF);
    animation: jack-spin 6s linear infinite;
    filter: blur(2px);
    opacity: 0.65;
}
@keyframes jack-spin { to { transform: rotate(360deg); } }
.jack-portrait-wrap::after {
    content: "";
    position: absolute;
    inset: 14px;
    border-radius: 50%;
    box-shadow: 0 0 32px rgba(61, 95, 255, 0.4) inset;
    animation: jack-pulse 2.5s ease-in-out infinite;
}
@keyframes jack-pulse {
    0%, 100% { box-shadow: 0 0 28px rgba(61, 95, 255, 0.30) inset; }
    50%      { box-shadow: 0 0 56px rgba(61, 95, 255, 0.55) inset; }
}
.jack-photo {
    position: relative;
    width: calc(100% - 28px);
    height: calc(100% - 28px);
    margin: 14px;
    border-radius: 50%;
    overflow: hidden;
    z-index: 2;
    border: 4px solid #FFFFFF;
    box-shadow: 0 8px 22px rgba(6, 11, 23, 0.25);
    animation: jack-float 4s ease-in-out infinite;
    transform-origin: 50% 80%;
}
@keyframes jack-float {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50%      { transform: translateY(-3px) rotate(0deg); }
}

/* State-driven animations */
.jack-portrait-wrap.thinking .jack-photo {
    animation: jack-think 3.5s ease-in-out infinite;
}
@keyframes jack-think {
    0%, 100% { transform: translateY(0) rotate(-5deg); }
    50%      { transform: translateY(-2px) rotate(5deg); }
}

.jack-portrait-wrap.typing .jack-photo {
    animation: jack-typing 1.4s ease-in-out infinite;
}
@keyframes jack-typing {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    25%      { transform: translateY(-2px) rotate(-2deg); }
    75%      { transform: translateY(-2px) rotate(2deg); }
}

.jack-portrait-wrap.happy .jack-photo {
    animation: jack-happy 0.9s ease-out;
}
@keyframes jack-happy {
    0%   { transform: translateY(0) rotate(0deg) scale(1); }
    25%  { transform: translateY(-14px) rotate(-6deg) scale(1.05); }
    50%  { transform: translateY(-4px) rotate(4deg) scale(1.02); }
    75%  { transform: translateY(-8px) rotate(-2deg) scale(1.03); }
    100% { transform: translateY(0) rotate(0deg) scale(1); }
}

.jack-portrait-wrap.tilt .jack-photo {
    animation: jack-tilt 0.6s ease-out;
}
@keyframes jack-tilt {
    0%   { transform: rotate(0deg); }
    50%  { transform: rotate(-8deg); }
    100% { transform: rotate(0deg); }
}
.jack-photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center top;
    filter: contrast(1.05) saturate(1.05);
}
.jack-live-badge {
    position: absolute;
    bottom: 18px;
    right: 18px;
    z-index: 3;
    background: #060B17;
    color: #FFFFFF;
    padding: 5px 12px 5px 8px;
    border-radius: 100px;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    text-transform: uppercase;
}
.jack-live-badge .live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #22C55E;
    box-shadow: 0 0 8px #22C55E;
    animation: live-blink 1.4s ease-in-out infinite;
}
@keyframes live-blink {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.4; transform: scale(0.7); }
}
.jack-action-line {
    margin-top: 12px;
    padding: 10px 14px;
    background: #FFFFFF;
    border: 1px solid #D9E2EE;
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 2px 8px rgba(6,11,23,0.04);
}
.jack-action-line .typing-dots {
    display: inline-flex;
    gap: 3px;
}
.jack-action-line .typing-dots span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #3B5FFF;
    animation: typing 1.4s infinite;
}
.jack-action-line .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.jack-action-line .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
    30%           { transform: translateY(-4px); opacity: 1; }
}
.jack-action-line .text {
    font-size: 0.8rem;
    color: #1F2A3F;
    font-weight: 600;
}
.jack-action-line .text strong {
    background: linear-gradient(135deg, #3B5FFF 0%, #1B339E 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.jack-joke-box {
    margin-top: 8px;
    padding: 14px;
    background: linear-gradient(135deg, #F0F5FB 0%, #FFF7F4 100%);
    border: 1px solid #D9E2EE;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
    min-height: 44px;
    font-size: 0.84rem;
    font-weight: 600;
    color: #1F2A3F;
    font-style: italic;
}
.jack-joke-box .joke {
    position: absolute;
    top: 50%;
    left: 14px;
    right: 14px;
    transform: translateY(-50%);
    opacity: 0;
    animation: joke-rotate 28s infinite;
}
.jack-joke-box .joke:nth-child(1) { animation-delay: 0s; }
.jack-joke-box .joke:nth-child(2) { animation-delay: 4s; }
.jack-joke-box .joke:nth-child(3) { animation-delay: 8s; }
.jack-joke-box .joke:nth-child(4) { animation-delay: 12s; }
.jack-joke-box .joke:nth-child(5) { animation-delay: 16s; }
.jack-joke-box .joke:nth-child(6) { animation-delay: 20s; }
.jack-joke-box .joke:nth-child(7) { animation-delay: 24s; }
@keyframes joke-rotate {
    0%, 13%  { opacity: 1; transform: translateY(-50%); }
    14%, 100% { opacity: 0; transform: translateY(-30%); }
}

/* ============================================================
   IDEAS GRID
   ============================================================ */
.ideas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
    margin-top: 12px;
}
.idea-card {
    background: #FFFFFF;
    border: 1px solid #D9E2EE;
    border-radius: 14px;
    padding: 16px 18px;
    transition: all 0.18s ease;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.idea-card:hover {
    border-color: #3B5FFF;
    transform: translateY(-2px);
    box-shadow: 0 10px 24px rgba(30,64,255,0.14);
}
.idea-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.idea-source {
    font-size: 0.74rem;
    color: #4F5B72;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.idea-kind {
    border: 1px solid;
    padding: 2px 8px;
    border-radius: 100px;
    font-size: 0.66rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.idea-hook {
    color: #060B17;
    font-weight: 700;
    font-size: 0.96rem;
    line-height: 1.3;
    font-style: italic;
}
.idea-stats { display: flex; gap: 14px; font-size: 0.8rem; color: #4F5B72; }
.idea-stats strong { color: #060B17; }
.idea-why {
    background: #F0F5FB;
    border-left: 3px solid #3B5FFF;
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    color: #1F2A3F;
    line-height: 1.4;
}
.idea-link { color: #1E40FF !important; text-decoration: none; font-size: 0.84rem; font-weight: 700; margin-top: auto; }
.idea-link:hover { text-decoration: underline; }

pre {
    background: #F6FAFE !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 16px !important;
}
pre code {
    background: transparent !important;
    color: var(--text-secondary) !important;
    font-size: 0.85rem !important;
}

.stLinkButton > a {
    border-radius: 8px !important;
    border: 1px solid var(--border) !important;
    background: #FFFFFF !important;
    color: var(--text-primary) !important;
}
.stLinkButton > a:hover {
    border-color: var(--azure) !important;
    color: var(--azure-deep) !important;
}
</style>
"""


def inject():
    """Call once after st.set_page_config — applies global styles."""
    st.markdown(CSS, unsafe_allow_html=True)
