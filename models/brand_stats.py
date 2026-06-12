"""Brand monthly stats puller — reads Darya's public Google Sheets report.

Sheet: https://docs.google.com/spreadsheets/d/1OuQuKnDFLQrpmg4-PGgremEHli0Y59fx/edit?gid=1844466013

Structure (per brand):
    HEADER         | Jan | Feb | Mar | Apr | May | …
    followers      | …
    reach          | …
    reel views     | …
    post likes     | …
    story          | …
    multilink cliks| …
"""

from __future__ import annotations

import csv
import io
import time
import requests
import streamlit as st


SHEET_ID = "1OuQuKnDFLQrpmg4-PGgremEHli0Y59fx"
GID = "1844466013"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
METRICS = ["followers", "reach", "reel views", "post likes", "story", "multilink cliks"]


def _parse_num(s: str) -> int | None:
    s = (s or "").replace(" ", "").replace(",", "").strip()
    if not s or s == "—":
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return None


@st.cache_data(ttl=3600)
def fetch_report() -> dict:
    """Fetch and parse the Google Sheets report into {brand: {metric: {month: value}}}."""
    try:
        r = requests.get(CSV_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return {}
    except Exception:
        return {}

    rows = list(csv.reader(io.StringIO(r.text)))
    if not rows:
        return {}

    brands: dict = {}
    current_brand = None
    current_months: list[str] = []

    for row in rows:
        if not row or all(not c.strip() for c in row):
            continue
        # Brand header row: first cell has brand name, second cell has year (or blank)
        first = (row[0] or "").strip()
        # Detect brand header (UPPERCASE word, not a metric name)
        if first and first.isupper() and first.lower() not in METRICS:
            current_brand = first
            brands[current_brand] = {}
            current_months = []
            continue
        # Month header row: first cell empty, rest are month names
        if not first and len(row) > 1:
            maybe_months = [c.strip() for c in row[1:]]
            if any(m.lower() in [x.lower() for x in MONTHS] for m in maybe_months if m):
                current_months = maybe_months
                continue
        # Metric row: first cell is a metric name
        if first.lower() in METRICS and current_brand and current_months:
            metric = first.lower()
            values = row[1:]
            by_month: dict = {}
            for month_name, val in zip(current_months, values):
                if not month_name:
                    continue
                by_month[month_name] = _parse_num(val)
            brands[current_brand].setdefault(metric, {}).update(by_month)
    return brands


def latest_month_with_data(brand_stats: dict, metric: str) -> tuple[str, int | None] | None:
    """Find the most recent month that has a non-empty value for the metric."""
    series = brand_stats.get(metric, {})
    # Walk months in reverse (Dec → Jan)
    for m in reversed(MONTHS):
        v = series.get(m)
        if v is not None:
            return (m, v)
    return None


def trend(brand_stats: dict, metric: str) -> tuple[int | None, int | None]:
    """Return (latest_value, previous_month_value) so caller can compute delta %."""
    series = brand_stats.get(metric, {})
    months_with_data = [(m, series.get(m)) for m in MONTHS if series.get(m) is not None]
    if not months_with_data:
        return (None, None)
    latest = months_with_data[-1][1]
    prev = months_with_data[-2][1] if len(months_with_data) >= 2 else None
    return (latest, prev)


def format_delta(latest: int | None, prev: int | None) -> str:
    if latest is None or prev is None or prev == 0:
        return ""
    delta_pct = (latest - prev) / prev * 100
    arrow = "↑" if delta_pct >= 0 else "↓"
    return f"{arrow} {abs(delta_pct):.1f}%"


def format_num(n: int | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
