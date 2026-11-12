"""Пересобрать models/product_base.json из Excel «База товаров BP и TOBYDIC (Amazon)».

Запуск:  python scripts/build_product_base.py "<путь к .xlsx>"
Берёт лист «Товары». Колонки сервиса Сергея (SKU, внутренние имена), полные SEO-заголовки
и Product information в репозиторий НЕ попадают — репо публичный.
"""
import html, json, re, subprocess, sys, tempfile, zipfile
from pathlib import Path

xlsx = sys.argv[1]
z = zipfile.ZipFile(xlsx)
wb = z.read("xl/workbook.xml").decode()
names = re.findall(r'<sheet [^>]*name="([^"]+)"', wb)
sheet = f"xl/worksheets/sheet{names.index('Товары') + 1}.xml"
shared = []
if "xl/sharedStrings.xml" in z.namelist():
    shared = [html.unescape(re.sub(r"<[^>]+>", "", s)) for s in
              re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]


def col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


rows = []
for r in re.findall(r"<row[^>]*>(.*?)</row>", z.read(sheet).decode(), re.S):
    d = {}
    for ref, attrs, body in re.findall(r'<c r="([A-Z]+\d+)"([^>]*)>(.*?)</c>', r, re.S):
        v = html.unescape(re.sub(r"<[^>]+>", "", body))
        if 't="s"' in attrs:
            v = shared[int(re.search(r"<v>(\d+)</v>", body).group(1))]
        d[col(ref)] = v
    rows.append([d.get(i, "") for i in range(max(d) + 1 if d else 0)])

tmp = Path(tempfile.mkdtemp()) / "rows.json"
tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
out = Path(__file__).resolve().parent.parent / "models" / "product_base.json"
subprocess.run([sys.executable, str(Path(__file__).with_name("build_product_base_core.py")),
                str(tmp), str(out)], check=True)
