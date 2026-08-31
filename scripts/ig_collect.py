#!/usr/bin/env python3
"""Jack goes to Instagram himself and reads the numbers off our own posts.

Why a local script and not something the Streamlit app runs: the shared cloud app has no
browser and no Instagram session, and Instagram stopped showing view/like/comment counts
to logged-out visitors — an anonymous profile page returns post links and nothing else.
So the browsing happens on the Mac, and the numbers go straight into Supabase, which the
cloud app already reads. Same split the rest of Jack uses: cloud is the source of truth.

    python3 scripts/ig_collect.py login     # once — log in by hand, session persists
    python3 scripts/ig_collect.py collect   # headless, reads the profile, writes Supabase
    python3 scripts/ig_collect.py collect --posts 60 --show

The scrape reads Instagram's own GraphQL responses rather than the DOM. Instagram renames
CSS classes constantly but the media objects keep the same field names, so we walk the
JSON looking for anything that has a shortcode and a timestamp.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROFILE_DIR = pathlib.Path.home() / ".config" / "bp" / "ig-profile"
HANDLE = "beloved_pets_brand"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _chromium_path() -> str | None:
    """Newest chromium Playwright has already downloaded.

    Pinned rather than left to Playwright, because the installed playwright package on
    this Mac asks for a build number that was never downloaded and dies on launch.
    """
    base = pathlib.Path.home() / "Library" / "Caches" / "ms-playwright"

    def build_no(p: pathlib.Path) -> int:
        # …/chromium-1217/chrome-mac-arm64/<name>.app/Contents/MacOS/<binary>
        for parent in p.parents:
            if parent.name.startswith("chromium-"):
                tail = parent.name.split("-", 1)[1]
                return int(tail) if tail.isdigit() else 0
        return 0

    builds = sorted(base.glob("chromium-*/chrome-mac-arm64/*.app/Contents/MacOS/*"),
                    key=build_no, reverse=True)
    return str(builds[0]) if builds else None


def _context(p, headless: bool):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = dict(headless=headless, user_agent=UA, locale="en-US",
                  viewport={"width": 1440, "height": 900})
    exe = _chromium_path()
    if exe:
        kwargs["executable_path"] = exe
    return p.chromium.launch_persistent_context(str(PROFILE_DIR), **kwargs)


def _logged_in(page) -> bool:
    """Instagram keeps the flag in the page bootstrap; the URL alone lies on redirects."""
    try:
        return bool(page.evaluate(
            "() => document.documentElement.innerHTML.includes('\"is_logged_in\":true')"))
    except Exception:
        return False


# ─── extraction ─────────────────────────────────────────────────────────────
_COUNT_FIELDS = {
    "views": ("play_count", "ig_play_count", "video_view_count", "view_count"),
    "likes": ("like_count", "edge_liked_by", "edge_media_preview_like"),
    "comments": ("comment_count", "edge_media_to_comment", "edge_media_to_parent_comment"),
}


def _count(node: dict, names: tuple[str, ...]) -> int:
    for n in names:
        v = node.get(n)
        if isinstance(v, int):
            return v
        if isinstance(v, dict) and isinstance(v.get("count"), int):
            return v["count"]
    return 0


def _caption(node: dict) -> str:
    cap = node.get("caption")
    if isinstance(cap, dict):
        return (cap.get("text") or "")[:300]
    edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
    if edges:
        return ((edges[0].get("node") or {}).get("text") or "")[:300]
    return ""


def _kind(node: dict) -> str:
    pt = str(node.get("product_type") or node.get("__typename") or "").lower()
    if "clips" in pt or "reel" in pt or node.get("clips_metadata"):
        return "reel"
    if "carousel" in pt or node.get("carousel_media") or "sidecar" in pt:
        return "carousel"
    if node.get("is_video") or node.get("video_versions"):
        return "reel"
    return "photo"


def _walk(obj, found: dict) -> None:
    """Collect every media object anywhere in the payload, keyed by shortcode."""
    if isinstance(obj, dict):
        code = obj.get("code") or obj.get("shortcode")
        ts = obj.get("taken_at") or obj.get("taken_at_timestamp") or obj.get("device_timestamp")
        if isinstance(code, str) and isinstance(ts, int) and ts > 1_000_000_000:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            row = {
                "date": dt.strftime("%d.%m"),
                "iso": dt.strftime("%Y-%m-%d"),
                "kind": _kind(obj),
                "caption": _caption(obj),
                "views": _count(obj, _COUNT_FIELDS["views"]),
                "reach": 0,
                "likes": _count(obj, _COUNT_FIELDS["likes"]),
                "comments": _count(obj, _COUNT_FIELDS["comments"]),
                "shares": 0,
                "saves": 0,
                "url": f"https://www.instagram.com/p/{code}/",
            }
            prev = found.get(code)
            # Payloads repeat the same media at different depths; keep the richest copy.
            if not prev or (row["views"] + row["likes"] + row["comments"]) > \
                           (prev["views"] + prev["likes"] + prev["comments"]):
                found[code] = row
        for v in obj.values():
            _walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, found)


def collect(handle: str, want: int, headless: bool, show: bool) -> list[dict]:
    from playwright.sync_api import sync_playwright

    found: dict[str, dict] = {}
    with sync_playwright() as p:
        ctx = _context(p, headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_response(resp):
            if "/api/" not in resp.url and "graphql" not in resp.url:
                return
            try:
                _walk(resp.json(), found)
            except Exception:
                pass

        page.on("response", on_response)
        page.goto(f"https://www.instagram.com/{handle}/",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        if not _logged_in(page):
            ctx.close()
            raise SystemExit(
                "Не залогинены в Instagram. Инста показывает цифры только своим.\n"
                "Один раз выполни:  python3 scripts/ig_collect.py login\n"
                "— откроется браузер, войди под @beloved_pets_brand, закрой окно. "
                "Сессия сохранится, дальше сбор идёт сам.")

        # Scroll until Instagram stops adding posts or we have enough.
        stale = 0
        for _ in range(40):
            if len(found) >= want:
                break
            before = len(found)
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(2200)
            stale = stale + 1 if len(found) == before else 0
            if stale >= 4:
                break

        if show:
            page.wait_for_timeout(2000)
        ctx.close()

    rows = sorted(found.values(), key=lambda r: r["iso"], reverse=True)[:want]
    return rows


def login(handle: str) -> None:
    from playwright.sync_api import sync_playwright
    print("Открываю браузер. Войди под аккаунтом бренда и закрой окно — сессия сохранится.")
    with sync_playwright() as p:
        ctx = _context(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
        try:
            page.wait_for_event("close", timeout=600000)
        except Exception:
            pass
        try:
            ok = _logged_in(page)
        except Exception:
            ok = True  # окно уже закрыто — считаем, что вошли; collect перепроверит
        ctx.close()
    print("Готово." if ok else "Похоже, вход не завершён — запусти login ещё раз.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Jack reads Instagram numbers off our profile")
    ap.add_argument("action", choices=["login", "collect"])
    ap.add_argument("--handle", default=HANDLE)
    ap.add_argument("--brand", default="BelovedPets")
    ap.add_argument("--posts", type=int, default=60, help="сколько последних постов забрать")
    ap.add_argument("--show", action="store_true", help="показать браузер (по умолчанию скрыт)")
    ap.add_argument("--dry", action="store_true", help="не писать в Supabase, только показать")
    args = ap.parse_args()

    if args.action == "login":
        login(args.handle)
        return

    rows = collect(args.handle, args.posts, headless=not args.show, show=args.show)
    if not rows:
        print("Ничего не собрал — Instagram не отдал ни одного поста.")
        raise SystemExit(1)

    with_numbers = [r for r in rows if r["views"] or r["likes"] or r["comments"]]
    print(f"Собрал постов: {len(rows)} · с цифрами: {len(with_numbers)}")
    for r in rows[:12]:
        print(f"  {r['iso']} [{r['kind']:8}] {r['views']:>7} просм · {r['likes']:>5} лайк · "
              f"{r['comments']:>4} комм · {r['caption'][:48]}")

    if args.dry:
        print("\n--dry: в базу не писал.")
        return

    from models import ig_insights
    added = ig_insights.merge(rows, args.brand)
    total = len(ig_insights.load(args.brand))
    print(f"\nВ Supabase добавлено новых: {added} · всего в базе: {total}. "
          f"Джек увидит их в «План на месяц».")


if __name__ == "__main__":
    main()
