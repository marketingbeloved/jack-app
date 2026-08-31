#!/usr/bin/env python3
"""Read our Instagram numbers through Darya's own Safari tab.

Chosen over a headless login because the brand account has 2FA and Darya is already
signed in to Instagram in Safari. Nothing here touches passwords, keychains or cookie
files — we drive the browser she already has open and ask Instagram's own API from
inside the page, so the request carries her session the same way a click would.

Requires two one-time switches on the Mac:
  • System Settings → Privacy & Security → Automation → <терминал/VS Code> → Safari
  • Safari → Develop → Allow JavaScript from Apple Events
      (Develop menu itself: Safari → Settings → Advanced → Show features for web developers)

    python3 scripts/ig_safari.py            # собрать и записать в Supabase
    python3 scripts/ig_safari.py --dry      # только показать
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HANDLE = "beloved_pets_brand"
IG_APP_ID = "936619743392459"  # публичный web app id, тот же шлёт сам instagram.com


class SafariError(RuntimeError):
    pass


def _osascript(script: str) -> str:
    """Run AppleScript from a temp file — avoids shell-quoting a page of JavaScript."""
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(script)
        path = fh.name
    try:
        proc = subprocess.run(["osascript", path], capture_output=True, text=True, timeout=180)
    finally:
        pathlib.Path(path).unlink(missing_ok=True)

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if "-1743" in err or "Not authorized" in err:
            raise SafariError(
                "macOS не разрешает управлять Safari.\n"
                "Системные настройки → Конфиденциальность и безопасность → Автоматизация →\n"
                "найди приложение, из которого я запущен (Visual Studio Code / Terminal) →\n"
                "включи галочку Safari.")
        if "privilege violation" in err.lower() or "-10004" in err:
            raise SafariError(
                "Safari не разрешает выполнять JavaScript из внешних команд.\n"
                "Safari → Настройки → Дополнения → «Показывать функции для веб-разработчиков»,\n"
                "затем меню Develop (Разработка) → Allow JavaScript from Apple Events.")
        raise SafariError(err or "osascript вернул ошибку без текста")
    return (proc.stdout or "").strip()


def _js(code: str) -> str:
    """Evaluate JS in the front Safari tab and return the result as text."""
    escaped = code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return _osascript(
        'tell application "Safari"\n'
        f'  do JavaScript "{escaped}" in front document\n'
        "end tell\n"
    )


PROFILE_URL = f"https://www.instagram.com/{HANDLE}/"


def open_instagram() -> None:
    """Point an Instagram tab at our profile — and make sure it actually lands there.

    Grabbing "any tab containing instagram.com" was not enough: Darya keeps the Instagram
    ads tool open too, and that page carries none of the profile data, which read as
    "не выполнен вход". So we navigate the tab explicitly and wait for the URL to settle.
    """
    _osascript(f'''
tell application "Safari"
  if (count of windows) = 0 then
    make new document with properties {{URL:"{PROFILE_URL}"}}
  else
    set tgt to missing value
    repeat with w in windows
      repeat with t in tabs of w
        if (URL of t as string) contains "instagram.com" then
          set tgt to t
          set current tab of w to t
          exit repeat
        end if
      end repeat
      if tgt is not missing value then exit repeat
    end repeat
    if tgt is missing value then
      tell front window
        set current tab to (make new tab with properties {{URL:"{PROFILE_URL}"}})
      end tell
    else
      set URL of tgt to "{PROFILE_URL}"
    end if
  end if
end tell
''')
    for _ in range(12):
        time.sleep(2)
        try:
            if HANDLE in _js("window.location.href"):
                time.sleep(2)
                return
        except SafariError:
            continue


# JavaScript that runs inside the logged-in page. Kicked off once, then polled: AppleScript
# returns immediately and would never wait for a promise.
_COLLECTOR = """
window.__jack = {done:false, err:null, rows:[]};
(async function(){
  try {
    var H = {'x-ig-app-id':'%(appid)s'};
    var rows = [];
    var push = function(n){
      if(!n) return;
      var code = n.code || n.shortcode;
      var ts = n.taken_at || n.taken_at_timestamp;
      if(!code || !ts) return;
      var likes = (n.like_count != null) ? n.like_count
        : ((n.edge_liked_by && n.edge_liked_by.count) ||
           (n.edge_media_preview_like && n.edge_media_preview_like.count) || 0);
      var comments = (n.comment_count != null) ? n.comment_count
        : ((n.edge_media_to_comment && n.edge_media_to_comment.count) || 0);
      var cap = '';
      if (n.caption && n.caption.text) cap = n.caption.text;
      else if (n.edge_media_to_caption && n.edge_media_to_caption.edges &&
               n.edge_media_to_caption.edges[0]) cap = n.edge_media_to_caption.edges[0].node.text;
      rows.push({
        code: code, ts: ts,
        pt: String(n.product_type || n.__typename || '') + (n.clips_metadata ? '|clips' : '') +
            ((n.carousel_media || n.edge_sidecar_to_children) ? '|carousel' : ''),
        v: n.play_count || n.ig_play_count || n.video_view_count || n.view_count || 0,
        l: likes, c: comments, cap: String(cap).slice(0,200)
      });
    };
    var html = document.documentElement.innerHTML;
    var m = html.match(/"profile_id":"(\\d+)"/) ||
            html.match(/"owner":\\{"id":"(\\d+)"/) ||
            html.match(/"user_id":"(\\d+)"/);
    var uid = m ? m[1] : '';
    var maxId = null, guard = 0, lastStatus = 0;
    while (rows.length < %(want)d && guard < 12) {
      guard++;
      var url = '/api/v1/feed/user/' + uid + '/?count=33' + (maxId ? ('&max_id=' + maxId) : '');
      var resp = await fetch(url, {headers:H, credentials:'include'});
      lastStatus = resp.status;
      var j = await resp.json();
      var items = (j && j.items) || [];
      if (!items.length) break;
      items.forEach(push);
      if (!j.more_available) break;
      maxId = j.next_max_id;
      await new Promise(function(r){ setTimeout(r, 1200); });
    }
    if (!rows.length) {
      throw new Error('Instagram вернул пусто (HTTP ' + lastStatus + ', uid="' + uid +
                      '") — возможно, в этой вкладке не выполнен вход');
    }
    var seen = {}; var uniq = [];
    rows.forEach(function(r){ if(!seen[r.code]){ seen[r.code]=1; uniq.push(r); } });
    window.__jack.rows = uniq;
    window.__jack.done = true;
  } catch(e) {
    window.__jack.err = String(e && e.message ? e.message : e);
    window.__jack.done = true;
  }
})();
'started';
"""


def collect(want: int = 60, timeout_s: int = 180) -> list[dict]:
    open_instagram()

    started = _js(_COLLECTOR % {"appid": IG_APP_ID, "handle": HANDLE, "want": want})
    if "started" not in started:
        raise SafariError(f"Не удалось запустить сбор в странице (ответ: {started!r})")

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(3)
        state = _js("JSON.stringify({d:!!window.__jack.done,"
                    "n:window.__jack.rows.length,e:window.__jack.err})")
        try:
            st = json.loads(state)
        except json.JSONDecodeError:
            continue
        print(f"  собрано: {st['n']}", end="\r", flush=True)
        if st["d"]:
            if st["e"]:
                raise SafariError(st["e"])
            break
    else:
        raise SafariError("Instagram не ответил за отведённое время — попробуй ещё раз.")

    total = int(json.loads(_js("JSON.stringify(window.__jack.rows.length)")))
    raw: list[dict] = []
    step = 20  # AppleScript давится очень длинными строками — забираем частями
    for i in range(0, total, step):
        chunk = _js(f"JSON.stringify(window.__jack.rows.slice({i},{i + step}))")
        raw.extend(json.loads(chunk))
    print(f"  собрано: {len(raw)}   ")
    return [_to_row(r) for r in raw]


def _to_row(r: dict) -> dict:
    dt = datetime.fromtimestamp(int(r["ts"]), tz=timezone.utc)
    pt = (r.get("pt") or "").lower()
    if "clips" in pt or "reel" in pt or "video" in pt:
        kind = "reel"
    elif "carousel" in pt or "sidecar" in pt:
        kind = "carousel"
    else:
        kind = "photo"
    return {
        "date": dt.strftime("%d.%m"),
        "iso": dt.strftime("%Y-%m-%d"),
        "kind": kind,
        "caption": (r.get("cap") or "")[:300],
        "views": int(r.get("v") or 0),
        "reach": 0,
        "likes": int(r.get("l") or 0),
        "comments": int(r.get("c") or 0),
        "shares": 0,
        "saves": 0,
        "url": f"https://www.instagram.com/p/{r['code']}/",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Джек читает цифры Instagram через Safari")
    ap.add_argument("--posts", type=int, default=60)
    ap.add_argument("--brand", default="BelovedPets")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    try:
        rows = collect(args.posts)
    except SafariError as e:
        print(f"\n⚠️  {e}")
        raise SystemExit(1)

    if not rows:
        print("Instagram не вернул ни одного поста.")
        raise SystemExit(1)

    rows.sort(key=lambda r: r["iso"], reverse=True)
    with_nums = [r for r in rows if r["views"] or r["likes"] or r["comments"]]
    print(f"\nПостов: {len(rows)} · с цифрами: {len(with_nums)}")
    for r in rows[:15]:
        print(f"  {r['iso']} [{r['kind']:8}] {r['views']:>7} просм · {r['likes']:>5} лайк · "
              f"{r['comments']:>4} комм · {r['caption'][:44]}")

    if args.dry:
        print("\n--dry: в базу не писал.")
        return

    from models import ig_insights
    added = ig_insights.merge(rows, args.brand)
    print(f"\nВ Supabase добавлено: {added} · всего: {len(ig_insights.load(args.brand))}")


if __name__ == "__main__":
    main()
