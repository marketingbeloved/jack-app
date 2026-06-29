"""Сводка по контент-плану — отдельный сборщик данных о КП (НЕ соцсети, НЕ Content Factory).

Читает общий план (shared_store: plan_<brand>) + ТЗ (plan_briefs) и считает:
сколько постов, по типам/исполнителям/месяцам, покрытие ТЗ, что на этой неделе.
Используется и на Dashboard, и Джеком — единая точка «данных по плану».
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

# Имена исполнителей для человекочитаемой сводки (slug → имя).
_OWNER_NAMES = {"vika": "Вика", "dina": "Дина", "tanya": "Таня", "darya": "Дарья"}
_VIKA_LEGACY = {"p0206a", "p0806a", "p1606a", "p2206a", "p3006a", "p0306a", "p1006a"}
_TYPE_LABELS = {"engaging": "Вовлекающий", "selling": "Продающий",
                "viral": "Вирусный", "neutral": "Без категории"}


def _load_plan(brand: str) -> dict:
    try:
        from models import shared_store
        return shared_store.get_json(f"plan_{brand.lower()}", {}) or {}
    except Exception:
        return {}


def _owner_of(item: dict) -> str:
    o = item.get("owner")
    if o:
        return o
    return "vika" if item.get("id") in _VIKA_LEGACY else "dina"


def _briefs() -> dict:
    try:
        from models import plan_briefs
        return plan_briefs.load_all() or {}
    except Exception:
        return {}


def summarize_plan(brand: str) -> dict:
    """Единая сводка по плану бренда. Возвращает dict с числами и разбивками.

    {
      "total": int, "with_brief": int, "brief_pct": int,
      "by_type": {label: n}, "by_owner": {Имя: n}, "by_month": {"06": n, "07": n},
      "this_week": [{"date","title","owner","type","has_brief"}],
      "no_brief": [{"date","title","owner"}],   # посты без ТЗ (надо написать)
    }
    """
    plan = _load_plan(brand)
    briefs = _briefs()

    total = with_brief = 0
    by_type: dict[str, int] = {}
    by_owner: dict[str, int] = {}
    by_month: dict[str, int] = {}
    this_week: list[dict] = []
    no_brief: list[dict] = []

    today = date.today()
    week_keys = {(today + timedelta(days=d)).strftime("%d.%m") for d in range(7)}

    for dk, posts in plan.items():
        mm = dk.split(".")[1] if "." in dk else "?"
        for p in posts or []:
            total += 1
            t_label = _TYPE_LABELS.get(p.get("type", "neutral"), "Без категории")
            by_type[t_label] = by_type.get(t_label, 0) + 1
            owner = _OWNER_NAMES.get(_owner_of(p), _owner_of(p).title())
            by_owner[owner] = by_owner.get(owner, 0) + 1
            by_month[mm] = by_month.get(mm, 0) + 1
            has_brief = bool((briefs.get(p.get("id", "")) or {}).get("text"))
            if has_brief:
                with_brief += 1
            else:
                no_brief.append({"date": dk, "title": p.get("title", "—"), "owner": owner})
            if dk in week_keys:
                this_week.append({"date": dk, "title": p.get("title", "—"),
                                  "owner": owner, "type": p.get("type", "neutral"),
                                  "has_brief": has_brief})

    this_week.sort(key=lambda x: x["date"])
    return {
        "total": total,
        "with_brief": with_brief,
        "brief_pct": round(with_brief / total * 100) if total else 0,
        "by_type": by_type,
        "by_owner": by_owner,
        "by_month": dict(sorted(by_month.items())),
        "this_week": this_week,
        "no_brief": no_brief,
    }
