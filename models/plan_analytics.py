"""What actually happened in the last months — the evidence Jack reasons from.

Reads three real sources and folds them into one block of facts:
  • the shared plan grid (shared_store `plan_<brand>`) — dates, themes, colour, executor;
  • the ТЗ the team already wrote (plan_briefs) — our own scripts, verbatim;
  • per-post Instagram numbers (models.ig_insights), when they've been uploaded.

Nothing here calls an LLM. It exists so the month generator argues from numbers instead
of inventing a plan out of thin air, and so the same summary can be shown to Darya.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

# Format is inferred from the theme text, because that's all the team writes in a cell.
# Order matters: the first matching rule wins, so the most specific patterns come first.
_FORMAT_RULES: list[tuple[str, str]] = [
    ("blogger_photo", r"фото\s*(?:от\s*)?блогер|photo\s*blog?ger|blogger\s*photo"),
    ("animation",     r"оживит|ожив |animat|фото\s*ии|ai\s*photo|alive"),
    ("carousel",      r"carousel|карусел"),
    ("reel",          r"\breel|рилс|\bvideo\b|видео|podcast|pov\b"),
    ("lifestyle",     r"life\s*pic|lifestyle|life\s*photo"),
    ("promo",         r"%|off\b|deal|discount|sale|prime\s*day|subscribe\s*&\s*save|offer"),
]

_FORMAT_LABELS = {
    "blogger_photo": "фото от блогера",
    "animation":     "анимация / оживление фото",
    "carousel":      "карусель",
    "reel":          "рилс / видео",
    "lifestyle":     "life pic (статичное фото)",
    "promo":         "промо / скидка",
    "other":         "прочее",
}

_TYPE_LABELS = {"engaging": "вовлекающий", "selling": "продающий",
                "viral": "вирусный", "neutral": "без категории"}

_MONTH_RU = {"01": "январь", "02": "февраль", "03": "март", "04": "апрель",
             "05": "май", "06": "июнь", "07": "июль", "08": "август",
             "09": "сентябрь", "10": "октябрь", "11": "ноябрь", "12": "декабрь"}


def detect_format(title: str) -> str:
    low = (title or "").lower()
    for name, pattern in _FORMAT_RULES:
        if re.search(pattern, low):
            return name
    return "other"


def _load_plan(brand: str) -> dict:
    try:
        from views.content_plan import load_plan
        return load_plan(brand) or {}
    except Exception:
        try:
            from models import shared_store
            return shared_store.get_json(f"plan_{brand.lower()}", {}) or {}
        except Exception:
            return {}


def _load_briefs() -> dict:
    try:
        from models import plan_briefs
        return plan_briefs.load_all() or {}
    except Exception:
        return {}


def _month_of(date_key: str) -> str:
    parts = (date_key or "").split(".")
    return parts[1] if len(parts) > 1 else ""


def collect(brand: str = "BelovedPets", months: list[str] | None = None) -> dict:
    """Fold plan + briefs + IG numbers into one analysis dict.

    months: list of 'MM' strings to include. Default — every month in the plan that has
    already fully run. The current month counts as finished once its last planned post is
    today or earlier; a month still mid-flight is dropped, since half a month of posts
    would drag every average down.
    """
    plan = _load_plan(brand)
    briefs = _load_briefs()

    present = sorted({_month_of(dk) for dk in plan if _month_of(dk)})
    if months is None:
        today = date.today()
        this_month = today.strftime("%m")
        last_day = max((int(dk.split(".")[0]) for dk in plan
                        if _month_of(dk) == this_month), default=0)
        finished = this_month in present and 0 < last_day <= today.day
        months = [m for m in present if m != this_month or finished] or present
    months = [m for m in months if m in present]

    posts: list[dict] = []
    for date_key, cell in plan.items():
        mm = _month_of(date_key)
        if mm not in months:
            continue
        for p in cell or []:
            title = p.get("title", "")
            brief = briefs.get(p.get("id", "")) or {}
            posts.append({
                "date": date_key,
                "month": mm,
                "title": title,
                "type": p.get("type", "neutral"),
                "pillar": p.get("pillar", ""),
                "owner": p.get("owner", "") or "",
                "format": detect_format(title),
                "brief": (brief.get("text") or "").strip(),
            })

    by_format = Counter(p["format"] for p in posts)
    by_type = Counter(p["type"] for p in posts)
    by_owner = Counter(p["owner"] or "—" for p in posts)
    by_month = Counter(p["month"] for p in posts)
    by_pillar = Counter(p["pillar"] for p in posts if p["pillar"])

    # Blogger photo is the one slot with a fixed cadence, so it gets checked explicitly.
    blogger = [p for p in posts if p["format"] == "blogger_photo"]
    weeks_covered = max(1.0, 4.3 * len(months))  # a calendar month is ~4.3 weeks

    fmt_per_month: dict[str, Counter] = defaultdict(Counter)
    for p in posts:
        fmt_per_month[p["month"]][p["format"]] += 1

    return {
        "brand": brand,
        "months": months,
        "total": len(posts),
        "posts": posts,
        "by_format": dict(by_format),
        "by_type": dict(by_type),
        "by_owner": dict(by_owner),
        "by_month": dict(sorted(by_month.items())),
        "by_pillar": dict(by_pillar.most_common()),
        "format_per_month": {m: dict(c) for m, c in sorted(fmt_per_month.items())},
        "blogger_photo": {
            "total": len(blogger),
            "per_month": dict(Counter(p["month"] for p in blogger)),
            "owners": dict(Counter(p["owner"] or "—" for p in blogger)),
        },
        "briefs_written": sum(1 for p in posts if p["brief"]),
        "avg_posts_per_week": round(len(posts) / weeks_covered, 1),
        "metrics": _metrics(brand, months, posts),
    }


def _metrics(brand: str, months: list[str], posts: list[dict]) -> dict:
    """Join IG per-post numbers onto plan posts by date. Empty dict when nothing uploaded."""
    try:
        from models import ig_insights
        rows = ig_insights.load(brand)
    except Exception:
        rows = []
    if not rows:
        return {}

    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_date[r.get("date", "")].append(r)

    matched: list[dict] = []
    for p in posts:
        for r in by_date.get(p["date"], []):
            matched.append({**p, **{k: r.get(k, 0) for k in
                                    ("views", "reach", "likes", "comments", "shares", "saves")},
                            "ig_kind": r.get("kind", "post"), "url": r.get("url", "")})

    scope = [r for r in rows if (r.get("date", "").split(".")[-1] in months)] or rows

    def avg(items: list[dict], field: str) -> int:
        vals = [i.get(field, 0) for i in items if i.get(field)]
        return round(sum(vals) / len(vals)) if vals else 0

    per_format: dict[str, dict] = {}
    for fmt in {m["format"] for m in matched}:
        group = [m for m in matched if m["format"] == fmt]
        per_format[fmt] = {
            "n": len(group),
            "avg_views": avg(group, "views"),
            "avg_likes": avg(group, "likes"),
            "avg_comments": avg(group, "comments"),
            "avg_saves": avg(group, "saves"),
        }

    top = sorted(matched, key=lambda m: m.get("views", 0), reverse=True)[:8]
    flop = [m for m in sorted(matched, key=lambda m: m.get("views", 0)) if m.get("views")][:5]

    return {
        "posts_with_numbers": len(matched),
        "total_rows": len(rows),
        "avg_views": avg(scope, "views"),
        "avg_comments": avg(scope, "comments"),
        "avg_likes": avg(scope, "likes"),
        "per_format": per_format,
        "top": [{k: t.get(k) for k in ("date", "title", "format", "views", "likes", "comments")} for t in top],
        "flop": [{k: t.get(k) for k in ("date", "title", "format", "views", "likes", "comments")} for t in flop],
    }


# ─── rendering ──────────────────────────────────────────────────────────────
def as_prompt_block(a: dict) -> str:
    """The analysis as plain text for the LLM prompt — facts only, no instructions."""
    if not a.get("total"):
        return "ИСТОРИЯ: постов за прошлые месяцы в базе нет."

    months = ", ".join(_MONTH_RU.get(m, m) for m in a["months"])
    lines = [
        f"ИСТОРИЯ КОНТЕНТ-ПЛАНА {a['brand']} за {months} — {a['total']} постов "
        f"(по месяцам: {a['by_month']}).",
        "",
        "Форматы, которые реально выходили:",
    ]
    for fmt, n in sorted(a["by_format"].items(), key=lambda x: -x[1]):
        share = round(n / a["total"] * 100)
        lines.append(f"  - {_FORMAT_LABELS.get(fmt, fmt)}: {n} шт ({share}%)")

    lines += ["", "Категории (цвет ячейки):"]
    for t, n in sorted(a["by_type"].items(), key=lambda x: -x[1]):
        lines.append(f"  - {_TYPE_LABELS.get(t, t)}: {n}")

    bp = a["blogger_photo"]
    lines += ["", f"«Фото от блогера»: {bp['total']} за период, по месяцам {bp['per_month']}, "
                  f"исполнители {bp['owners']} — это фиксированный еженедельный слот."]

    if a["by_pillar"]:
        top_pillars = list(a["by_pillar"].items())[:8]
        lines += ["", "Пиллары: " + ", ".join(f"{k} ({v})" for k, v in top_pillars)]

    m = a.get("metrics") or {}
    if m:
        lines += ["", f"ЦИФРЫ INSTAGRAM (реальные, из выгрузки): {m['total_rows']} постов, "
                      f"средние — {m['avg_views']} просмотров, {m['avg_likes']} лайков, "
                      f"{m['avg_comments']} комментариев."]
        if m.get("per_format"):
            lines.append("Средние по форматам (только посты, сматченные с планом "
                         f"— {m['posts_with_numbers']} шт):")
            for fmt, s in sorted(m["per_format"].items(), key=lambda x: -x[1]["avg_views"]):
                lines.append(f"  - {_FORMAT_LABELS.get(fmt, fmt)}: {s['avg_views']} просмотров, "
                             f"{s['avg_comments']} комментов, {s['avg_saves']} сохранений (n={s['n']})")
        if m.get("top"):
            lines.append("ЛУЧШИЕ посты периода:")
            for t in m["top"]:
                lines.append(f"  - {t['date']} «{t['title']}» [{_FORMAT_LABELS.get(t['format'], t['format'])}] "
                             f"— {t['views']} просмотров, {t['comments']} комментов")
        if m.get("flop"):
            lines.append("ХУДШИЕ посты периода (не повторять формат/угол в лоб):")
            for t in m["flop"]:
                lines.append(f"  - {t['date']} «{t['title']}» [{_FORMAT_LABELS.get(t['format'], t['format'])}] "
                             f"— {t['views']} просмотров")
    else:
        lines += ["", "ЦИФРЫ INSTAGRAM: выгрузка не загружена. Опирайся на структуру плана и "
                      "здравый смысл, и НЕ выдумывай числа просмотров — их нет."]

    themes = [p["title"] for p in a["posts"]]
    lines += ["", "ВСЕ темы за период (не повторять дословно, но видеть, что уже отработано):",
              "; ".join(themes[:80])]

    scripts = [p for p in a["posts"] if p["brief"]][:12]
    if scripts:
        lines += ["", f"НАШИ СОБСТВЕННЫЕ ТЗ ({a['briefs_written']} шт всего) — "
                      "пиши в этом же тоне и структуре:"]
        for s in scripts:
            body = re.sub(r"\s+", " ", s["brief"])[:320]
            lines.append(f"  • [{s['date']} · {s['title']}] {body}")

    return "\n".join(lines)


def as_markdown(a: dict) -> str:
    """Short human-readable summary for the Streamlit UI."""
    if not a.get("total"):
        return "_Истории пока нет — план за прошлые месяцы пустой._"
    months = ", ".join(_MONTH_RU.get(m, m) for m in a["months"])
    rows = [f"**{a['total']} постов** за {months} · ТЗ написано: {a['briefs_written']}", ""]
    rows.append("| формат | сколько | доля |")
    rows.append("|---|---:|---:|")
    for fmt, n in sorted(a["by_format"].items(), key=lambda x: -x[1]):
        rows.append(f"| {_FORMAT_LABELS.get(fmt, fmt)} | {n} | {round(n / a['total'] * 100)}% |")
    m = a.get("metrics") or {}
    if m:
        rows += ["", f"**Instagram:** {m['total_rows']} постов в выгрузке · "
                     f"в среднем {m['avg_views']} просмотров, {m['avg_comments']} комментов"]
    else:
        rows += ["", "_Цифры Instagram не загружены — Джек будет опираться только на структуру плана._"]
    return "\n".join(rows)
