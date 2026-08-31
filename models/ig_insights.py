"""Per-post Instagram numbers — the fact base Jack uses to judge what actually worked.

Why a CSV and not the Graph API: a Meta app + long-lived token is a setup Darya would
have to sit through, and the export from Meta Business Suite / Instagram Insights is two
clicks. The parser is deliberately tolerant — Meta renames these columns between exports
and between locales, so we match on substrings instead of exact headers.

Stored in the shared Supabase store (key `ig_insights_<brand>`) so all four teammates —
and the cloud app after a reboot — see the same numbers.

Shape of one stored row:
    {"date": "12.08", "iso": "2026-08-12", "kind": "reel", "caption": "...",
     "views": 12043, "reach": 9800, "likes": 210, "comments": 14, "shares": 8,
     "saves": 31, "url": "https://..."}
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

STORE_KEY = "ig_insights_{brand}"

# Header substrings → normalised field. First match wins, so order matters:
# "views" must be tried before "reach", or a "Reach (views)" column lands wrong.
_COLUMN_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("views",    ("plays", "video views", "views", "просмотр", "impressions", "показы")),
    ("reach",    ("reach", "accounts reached", "охват")),
    ("likes",    ("likes", "нравится", "лайк")),
    ("comments", ("comments", "комментар")),
    ("shares",   ("shares", "поделились", "репост")),
    ("saves",    ("saves", "saved", "сохранен")),
    ("url",      ("permalink", "post url", "link", "ссылка")),
    ("caption",  ("caption", "description", "post text", "подпись", "описание", "title")),
    ("kind",     ("post type", "media type", "media product type", "тип")),
    ("date",     ("publish time", "date", "time", "created", "дата", "опублик")),
]

_KIND_MAP = {
    "reel": "reel", "reels": "reel", "video": "reel", "clip": "reel", "рилс": "reel",
    "carousel": "carousel", "carousel_album": "carousel", "album": "carousel", "карусел": "carousel",
    "image": "photo", "photo": "photo", "feed": "photo", "фото": "photo",
    "story": "story", "stories": "story", "истор": "story",
}

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%d.%m.%Y %H:%M", "%d.%m.%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y", "%d/%m/%Y",
)


def _map_columns(headers: list[str]) -> dict[str, str]:
    """Return {normalised field: actual header}. A header is claimed by one field only."""
    taken: set[str] = set()
    mapping: dict[str, str] = {}
    for field, hints in _COLUMN_HINTS:
        for hint in hints:
            match = next((h for h in headers
                          if h and h not in taken and hint in h.strip().lower()), None)
            if match:
                mapping[field] = match
                taken.add(match)
                break
    return mapping


def _num(raw: str) -> int:
    """'1,204' / '1 204' / '1.2K' / '' → int. Unparseable becomes 0, never crashes a row."""
    s = (raw or "").strip().replace(",", "").replace(" ", "").replace(" ", "")
    if not s or s in {"-", "—"}:
        return 0
    mult = 1
    if s[-1:].upper() in {"K", "M"}:
        mult = 1_000 if s[-1].upper() == "K" else 1_000_000
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def _parse_date(raw: str) -> tuple[str, str]:
    """Return (iso, 'DD.MM') or ('', '') — the DD.MM key is what the content plan uses."""
    s = (raw or "").strip()
    if not s:
        return "", ""
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(s[:len(datetime.now().strftime(fmt)) + 4].strip(), fmt)
            return d.strftime("%Y-%m-%d"), d.strftime("%d.%m")
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0), f"{m.group(3)}.{m.group(2)}"
    return "", ""


def _kind(raw: str, caption: str = "") -> str:
    low = (raw or "").strip().lower()
    for token, norm in _KIND_MAP.items():
        if token in low:
            return norm
    low_cap = (caption or "").lower()
    if "reel" in low_cap:
        return "reel"
    return "post"


def parse_csv(raw: bytes | str) -> tuple[list[dict], str]:
    """Parse a Meta/Instagram insights export. Returns (rows, human-readable note)."""
    if isinstance(raw, bytes):
        for enc in ("utf-8-sig", "utf-16", "cp1251", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            return [], "Не смог прочитать файл — сохрани его как CSV в UTF-8."
    else:
        text = raw

    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    headers = [h for h in (reader.fieldnames or []) if h]
    if not headers:
        return [], "В файле нет заголовков колонок."

    cols = _map_columns(headers)
    if "date" not in cols:
        return [], (f"Не нашёл колонку с датой. Заголовки в файле: {', '.join(headers[:12])}")
    if not ({"views", "reach", "likes", "comments"} & set(cols)):
        return [], (f"Не нашёл ни одной колонки с цифрами (просмотры/охват/лайки/комменты). "
                    f"Заголовки: {', '.join(headers[:12])}")

    rows: list[dict] = []
    skipped = 0
    for r in reader:
        iso, dk = _parse_date(r.get(cols["date"], ""))
        if not dk:
            skipped += 1
            continue
        caption = (r.get(cols.get("caption", ""), "") or "").strip()
        rows.append({
            "date": dk,
            "iso": iso,
            "kind": _kind(r.get(cols.get("kind", ""), ""), caption),
            "caption": caption[:300],
            "views": _num(r.get(cols.get("views", ""), "")),
            "reach": _num(r.get(cols.get("reach", ""), "")),
            "likes": _num(r.get(cols.get("likes", ""), "")),
            "comments": _num(r.get(cols.get("comments", ""), "")),
            "shares": _num(r.get(cols.get("shares", ""), "")),
            "saves": _num(r.get(cols.get("saves", ""), "")),
            "url": (r.get(cols.get("url", ""), "") or "").strip(),
        })

    note = f"Распознал {len(rows)} постов · колонки: {', '.join(sorted(cols))}"
    if skipped:
        note += f" · пропущено строк без даты: {skipped}"
    return rows, note


# ─── storage ────────────────────────────────────────────────────────────────
def load(brand: str = "BelovedPets") -> list[dict]:
    try:
        from models import shared_store
        return shared_store.get_json(STORE_KEY.format(brand=brand.lower()), []) or []
    except Exception:
        return []


def save(rows: list[dict], brand: str = "BelovedPets") -> bool:
    """Replace stored insights for the brand (an export is a full snapshot, not a delta)."""
    try:
        from models import shared_store
        return shared_store.put_json(STORE_KEY.format(brand=brand.lower()), rows)
    except Exception:
        return False


def merge(new_rows: list[dict], brand: str = "BelovedPets") -> int:
    """Add rows for dates we don't have yet, keep existing ones. Returns how many were added."""
    have = load(brand)
    seen = {(r.get("iso") or r.get("date"), r.get("caption", "")[:40]) for r in have}
    added = [r for r in new_rows if (r.get("iso") or r.get("date"), r.get("caption", "")[:40]) not in seen]
    if added:
        save(sorted(have + added, key=lambda r: r.get("iso") or ""), brand)
    return len(added)


def by_month(brand: str = "BelovedPets") -> dict[str, list[dict]]:
    """{'08': [rows…]} — grouped the same way the content plan keys its dates."""
    out: dict[str, list[dict]] = {}
    for r in load(brand):
        mm = (r.get("date") or "").split(".")[-1]
        if mm:
            out.setdefault(mm, []).append(r)
    return out
