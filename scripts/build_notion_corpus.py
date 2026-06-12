"""Read ALL pages from Dina's Notion Videos database and dump to a local corpus
so Jack can learn from Darya's real briefs (one-shot per run).

Output: jack-app/cache/notion_briefs_corpus.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

TOKEN = (Path.home() / ".bp-credentials" / "notion-token.txt").read_text().strip()
DB_ID = "2182452d-f1db-803d-ba88-d5bee781a6fd"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
OUT_DIR = Path(__file__).resolve().parent.parent / "cache"
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "notion_briefs_corpus.json"          # BelovedPets (legacy / default)
OUT_BP = OUT_DIR / "notion_briefs_belovedpets.json"
OUT_TB = OUT_DIR / "notion_briefs_tobydic.json"


def query_db():
    all_pages = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(f"https://api.notion.com/v1/databases/{DB_ID}/query", headers=HEADERS, json=body, timeout=20)
        r.raise_for_status()
        data = r.json()
        all_pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return all_pages


def get_blocks(page_id: str):
    r = requests.get(f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json().get("results", [])


def get_table_rows(table_id: str):
    r = requests.get(f"https://api.notion.com/v1/blocks/{table_id}/children?page_size=100", headers=HEADERS, timeout=20)
    r.raise_for_status()
    rows = []
    for row in r.json().get("results", []):
        cells = row.get("table_row", {}).get("cells", [])
        rows.append([" ".join(c.get("plain_text", "") for c in cell) for cell in cells])
    return rows


def block_text(b: dict) -> str:
    t = b["type"]
    content = b.get(t, {})
    rich = content.get("rich_text", [])
    text = "".join(r.get("plain_text", "") for r in rich)
    if t.startswith("heading"):
        return f"\n## {text}\n"
    if t == "paragraph":
        return text + "\n" if text.strip() else ""
    if t == "bulleted_list_item":
        return f"  • {text}\n"
    if t == "numbered_list_item":
        return f"  {text}\n"  # ordering matters less here
    if t == "to_do":
        m = "x" if content.get("checked") else " "
        return f"  [{m}] {text}\n"
    if t == "table":
        rows = get_table_rows(b["id"])
        return "\n" + "\n".join(" | ".join(r) for r in rows) + "\n"
    if t == "bookmark":
        return f"  [link] {content.get('url','')}\n"
    if t == "link_preview":
        return f"  [link] {content.get('url','')}\n"
    if t == "image":
        return "  [image]\n"
    if t == "video":
        return "  [video]\n"
    return ""


def main():
    pages = query_db()
    corpus_bp, corpus_tb = [], []
    print(f"Found {len(pages)} pages in Videos DB")
    for i, p in enumerate(pages):
        pid = p["id"]
        props = p.get("properties", {})
        title_arr = props.get("Project name", {}).get("title", [])
        title = "".join(r.get("plain_text", "") for r in title_arr)
        status = (props.get("Status", {}).get("status") or {}).get("name", "")
        brands = [b.get("name") for b in props.get("Brand", {}).get("multi_select", [])]
        date = (props.get("End date", {}).get("date") or {}).get("start", "")
        if not title.strip() or not brands:
            continue
        upper = [b.upper() for b in brands]
        bucket = None
        if "BELOVEDPETS" in upper:
            bucket = corpus_bp
        elif "TOBYDIC" in upper:
            bucket = corpus_tb
        else:
            continue
        try:
            blocks = get_blocks(pid)
        except Exception as e:
            print(f"  skip {title}: {e}")
            continue
        body = "".join(block_text(b) for b in blocks)
        bucket.append({
            "title": title,
            "status": status,
            "brand": brands,
            "date": date,
            "body": body.strip(),
        })
        if (i + 1) % 10 == 0:
            print(f"  …{i+1}/{len(pages)}  (BP {len(corpus_bp)} · TB {len(corpus_tb)})")
        time.sleep(0.15)  # polite
    OUT_BP.write_text(json.dumps(corpus_bp, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_TB.write_text(json.dumps(corpus_tb, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT.write_text(json.dumps(corpus_bp, ensure_ascii=False, indent=2), encoding="utf-8")  # legacy alias
    print(f"\n✓ BelovedPets → {len(corpus_bp)} briefs ({sum(len(c['body']) for c in corpus_bp):,} chars)")
    print(f"✓ TOBYDIC     → {len(corpus_tb)} briefs ({sum(len(c['body']) for c in corpus_tb):,} chars)")


if __name__ == "__main__":
    main()
