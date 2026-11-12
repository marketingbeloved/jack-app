"""xlsx «База товаров BP и TOBYDIC (Amazon)» → models/product_base.json (без колонок Сергея)."""
import json, re, sys
rows = json.load(open(sys.argv[1]))
hdr, rows = rows[0], rows[1:]
CAT = {"Блохи и клещи": "flea & tick", "Успокаивающие феромоны": "calming",
       "Уход (глаза, уши)": "eye & ear"}
# Бенефиты с такими словами Джеку не показываем (правило 3 + compliance).
BAD = re.compile(r"vet|99%|pain|kidney|\buti\b|infection|treatment|\bcure|\bheal(s|ing)?\b|medicine|antibiotic|"
                 r"revolution|fast acting|stops?\b|sedative|prevention|prevent|relieve|"
                 r"restores|100%|tested by|approved|made in|how to use|first effect|"
                 r"correction|best replacement|inflammation|stones|organic|pest|intended for|"
                 r"current f|label|anxiet", re.I)
JUNK = {"active", "eyes", "behavior", "stomach", "urinary", "training", "inflammation", "anxiety"}

def bullets(text):
    out = []
    for b in re.split(r"\n+|✅", text or ""):
        b = b.strip(" •-\t")
        if not b:
            continue
        if b.startswith("(нет"):
            continue
        head = b.split(":")[0].strip() if ":" in b[:60] else b
        head = re.split(r"\s+[-–—]\s+", head)[0].strip(" .")
        letters = [c for c in head if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
            head = head[:1].upper() + head[1:].lower()
        if len(head) > 80:
            continue
        out.append(head[:1].upper() + head[1:])
    return out

def benefits(row):
    raw = row[10]
    items = bullets(raw) if raw and not raw.startswith("—") else bullets(row[11])
    items = [re.sub(r"^\((US|UK|CA)\)\s*", "", i).strip() for i in items]
    keep = []
    for i in items:
        if i.lower() in JUNK or BAD.search(i) or len(i) < 4:
            continue
        for part in re.split(r"\s*,\s*(?=[a-z])", i) if len(i) > 90 else [i]:
            if part and part not in keep:
                keep.append(part)
    if "Duck" in row[3] and "Chicken" not in row[3]:
        keep = [k for k in keep if "chicken" not in k.lower()]   # в базе ошибка: «chicken» у утки
    return keep[:6]

out = []
for r in rows:
    if not r or len(r) < 15 or not r[6]:
        continue
    cat_ru = r[2]
    name = r[3].strip()
    if "Topper" in name:
        cat = "cat topper"
    elif cat_ru.startswith("Лакомства"):
        cat = "treats"
    elif cat_ru.startswith("Добавки"):
        cat = "supplement"
    else:
        cat = CAT.get(cat_ru, cat_ru)
    usage = (r[12] or "").strip()
    out.append({"brand": "TOBYDIC" if r[0].upper().startswith("TOBY") else "BelovedPets",
                "market": r[1].strip(), "category": cat, "category_ru": cat_ru,
                "title": name, "title_ru": r[4].strip(), "size": r[5].strip(),
                "asin": r[6].strip(), "url": r[7].strip(),
                "benefits": benefits(r),
                "how_to_use": "" if usage.startswith("—") else usage,
                "ingredients": (r[14] or "").strip()})
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
import collections
print(len(out), collections.Counter((p["brand"], p["market"]) for p in out))
print("без бенефитов:", sum(1 for p in out if not p["benefits"]), "без применения:", sum(1 for p in out if not p["how_to_use"]))
dup = [k for k, v in collections.Counter((p["market"], p["title"]) for p in out).items() if v > 1]
print("дубли названий на рынке:", dup)
