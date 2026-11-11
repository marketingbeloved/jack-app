"""Каталог Джека = только актуальные листинги Amazon US (решение Марии, 2026-11-11).

Источник списка: таблица «ALL ASINS» (Google Sheets 1qwK5Y2r31dZGJU5_rq1eEjDcRUAQ9xz9iOgb_NRHhjU,
лист USA). Каждый ASIN проверен на amazon.com 2026-11-11 (заголовок, бренд, наличие) —
снимок лежит в «03 Jack/_context/amazon/amazon-titles-2026-11-11.json».

Название — короткое имя из заголовка того же листинга. Полные заголовки Amazon в контент
брать нельзя: в них «Treatment», «Medicine», «Natural Antibiotic», «Made in USA» — это
запрещено правилами бренда. Поэтому здесь имя товара + вкус/размер, без SEO-хвоста.

Не вошли (сознательно):
  • MaxBuddy (B0DT4LMXVM, B0DHHKD25C, B0DHHK2YYQ) — чужой бренд;
  • UK / Canada ASIN (B0GLQBDMNX, B0FXXQ3769, B0GK91FSWK, B0GK9278G1, B0GK98T99C) — на .com 404;
  • Dewormer «red» B097KTGTQW — в таблице помечен «на Амазон скрыт»;
  • Neoterica Protecto 4 (5-22, 23-45, 89-132 lb) и Calming Collar for Dogs B01FSFY624 — 404.

Новый товар на Amazon → добавь строку сюда. Чего здесь нет, того для Джека не существует.

shopify_id — только чтобы подтянуть состав и описание того же товара из выгрузки Shopify.
Название и сам факт существования товара берутся отсюда.
"""

from __future__ import annotations

AMAZON_US = "https://www.amazon.com/dp/"

# (ASIN, название для контента, категория, вкус/вариант, shopify_id или None)
BELOVED: list[tuple[str, str, str, str, int | None]] = [
    # ── Капли-добавки (liquid) ──
    ("B0B53WDY4M", "Urinary Tract Support Drops with Cranberry & D-Mannose", "supplement", "", 7378803982529),
    ("B0B56PBZJS", "Throat & Respiratory Support Drops", "supplement", "", 7378818826433),
    ("B0C49B8SK9", "Multivitamin 21-in-1 Drops with Glucosamine & Cranberry (60 ml)", "supplement", "", 7728773136577),
    ("B0B56LLBBB", "Hemp Oil Drops with Multivitamin", "supplement", "", 7378813812929),
    ("B0BDNLR81R", "Herbal Intestinal Cleanse Drops with Probiotic", "supplement", "", 7543010132161),
    ("B0CP8CYVGD", "Herbiotic Complex Drops", "supplement", "", 10454881632449),
    ("B0CP8BF4SG", "Probiotics & Prebiotics with Enzymes Drops", "supplement", "", 10454875439297),
    ("B0CP8G7B3K", "Yeast & Skin Support Drops", "supplement", "", 10911673778369),
    ("B0D1WQZW46", "Oral Flea & Tick Support Multivitamin Drops", "supplement", "", 10454868918465),
    # ── Добавки-жевашки (chews) ──
    ("B0854J3KJ3", "Skin & Immune Soft Chews for Dogs with Probiotic & Omega-3", "supplement", "", 6718797676737),
    ("B07YN2F9HX", "Hip & Joint Soft Chews for Dogs with Glucosamine, Chondroitin & MSM", "supplement", "", 6718797381825),
    ("B07YN39CDF", "Calming Chews for Dogs with Melatonin", "supplement", "", 7542293627073),
    ("B0C5Z7C7VY", "Flea & Tick Support Chews for Cats (Chicken)", "supplement", "Chicken", 7728773431489),
    ("B0B53VLLMT", "Flea & Tick Support Chews for Cats (Salmon)", "supplement", "Salmon", None),
    ("B087WJVKCJ", "Flea & Tick Support Chews for Dogs (Chicken)", "supplement", "Chicken", 6718797414593),
    ("B09JWFH7BM", "Flea & Tick Support Chews for Dogs (Beef)", "supplement", "Beef", None),
    ("B0BWDH8S3F", "Flea & Tick Support + Multivitamin Soft Chews for Dogs (10 oz)", "supplement", "", 7609183174849),
    # ── Лакомства для кошек ──
    ("B0F8QXWZN9", "Creamy Lickable Cat Treats (Chicken, 20 Sticks)", "treats", "Chicken", None),
    ("B0F8R916BK", "Creamy Lickable Cat Treats (Chicken, 40 Sticks)", "treats", "Chicken", None),
    ("B0F8QXF2LY", "Creamy Lickable Cat Treats (Tuna, 20 Sticks)", "treats", "Tuna", None),
    ("B0F8R6JP3C", "Creamy Lickable Cat Treats (Tuna, 40 Sticks)", "treats", "Tuna", None),
    ("B0F8R12SP6", "Creamy Lickable Cat Treats (Tuna & Chicken Mix, 40 Sticks)", "treats", "Tuna & Chicken", 10734511751361),
    ("B0D83RLKC2", "Freeze-Dried Chicken Cubes for Dogs & Cats (5.3 oz)", "treats", "Chicken", 10625799160001),
    # ── Лакомства для собак ──
    ("B087WJC3ZQ", "Chicken Jerky Slices Dog Treats (1.5 lb)", "treats", "Chicken", 7259787428033),
    ("B087WF4C7Y", "Chicken Jerky Fillet Dog Treats (1.5 lb)", "treats", "Chicken", 6718797185217),
    ("B0BX6N76K9", "Chicken Jerky Breast Dog Treats (10.6 oz)", "treats", "Chicken", 7691154620609),
    ("B0CN98YTNY", "Chicken Jerky Strips Dog Treats (10.6 oz)", "treats", "Chicken", 10420787642561),
    ("B0BXLHW1BR", "Duck Jerky Dog Treats (1.5 lb)", "treats", "Duck", 10146387689665),
    ("B0GR9T36HT", "Duck Jerky Breast Dog Treats (10.6 oz)", "treats", "Duck", None),
    ("B0CN993R6S", "Sweet Potato Chicken Wraps Dog Treats (1.5 lb)", "treats", "Chicken & Sweet Potato", 10418137628865),
    ("B0B82ZGT66", "Sweet Potato & Chicken Dog Chews (10.6 oz)", "treats", "Chicken & Sweet Potato", 7543042015425),
    ("B0FSRTPG1C", "Sweet Potato & Duck Dog Chews (10.6 oz)", "treats", "Duck & Sweet Potato", 10911671484609),
    ("B0D83TV648", "Sweet Potato Chips Dog Treats (10.6 oz)", "treats", "Sweet Potato", 10625782808769),
    ("B0CN9BX8MF", "Biscuit Sticks Wrapped with Chicken (10.6 oz)", "treats", "Chicken", 10418151751873),
    ("B0CN98NXHX", "Cod Sticks Wrapped with Chicken (10.6 oz)", "treats", "Cod & Chicken", 10418150146241),
    ("B0CN9C335K", "Rawhide-Free Kabobs with Duck & Chicken (10.6 oz)", "treats", "Duck & Chicken", 10425990447297),
    ("B0CN9D2MWG", "Rawhide Kabobs with Duck & Chicken (10.6 oz)", "treats", "Duck & Chicken", 10420801142977),
    ("B0CN9DKS7F", "Triple Flavor Rawhide Sticks with Chicken & Duck", "treats", "Chicken & Duck", 10426000703681),
    ("B0B82ZNVNY", "Rawhide Sticks Wrapped with Chicken", "treats", "Chicken", 7543016489153),
    ("B0B82YLYTH", "Smoked Rawhide Sticks Wrapped with Chicken", "treats", "Chicken", 7543081959617),
    ("B0B82Z1GZJ", "Rawhide Bones Wrapped with Chicken", "treats", "Chicken", None),
    ("B0B832CP9M", "Calcium Bones Wrapped with Chicken (10.6 oz)", "treats", "Chicken", 7543068131521),
    ("B0B832BZPD", "Peanut Butter Bones with Cranberry (10.6 oz)", "treats", "Peanut Butter", 7543008100545),
    # ── Топпер для кошек (новинка ноября 2026) ──
    ("B0HBQQ6ZTB", "Shreds in Gravy Cat Food Topper (Chicken Mix)", "cat topper", "Chicken Mix", None),
    ("B0HBR2TLHH", "Shreds in Gravy Cat Food Topper (Tuna Mix)", "cat topper", "Tuna Mix", None),
    # ── Глаза и уши ──
    ("B0052GRKZU", "Eye Wash Drops (100 ml)", "eye & ear", "", 6718797643969),
    ("B08SPZVVFS", "Eye Wash Drops (50 ml)", "eye & ear", "", 6718797906113),
    ("B0CC4T5K45", "Tear Stain Eye Wipes", "eye & ear", "", 7728773300417),
    ("B019NNTJ8S", "Ear Cleaner Drops", "eye & ear", "", 10456971182273),
    # ── Блохи и клещи (наружные) ──
    ("B00MN4ATVG", "Flea & Tick Spot-On Drops for Dogs & Cats (3 Pack)", "flea & tick", "", 7240694563009),
    ("B09DYRFMJV", "Neoterica Protecto 4 Flea & Tick Spot-On for Dogs (45-89 lb)", "flea & tick", "", None),
    ("B07SB5BD4W", "Flea & Tick Home Spray", "flea & tick", "", 7106558918849),
    ("B01JQHKVPQ", "Flea & Tick Collar for Cats (1 Pack)", "flea & tick", "", 7288670716097),
    ("B01IU8U7B0", "Flea & Tick Collar for Cats (2 Pack)", "flea & tick", "", 7288670716097),
    ("B06XGWYHWR", "Flea & Tick Collar for Dogs (1 Pack)", "flea & tick", "", 7378562154689),
    ("B07L2ZP6MZ", "Flea & Tick Collar for Dogs (2 Pack)", "flea & tick", "", 7378562154689),
    # ── Успокоительные (Relaxiv — название линейки, решение Марии 2026-11-04) ──
    ("B00KQ2P3K4", "Relaxiv Cat Calming Diffuser Kit", "calming", "", 7542279176385),
    ("B09VL6RNNC", "Relaxiv Cat Calming Diffuser Kit (2 Pack)", "calming", "", 7543024943297),
    ("B00BIMNFYM", "Relaxiv Cat Calming Diffuser Refills (2 Pack)", "calming", "", 6718797283521),
    ("B08SPZQ91T", "Relaxiv Cat Calming Diffuser Refills (6 Pack)", "calming", "", 7259761148097),
    ("B08773ZHYQ", "Relaxiv Dog Calming Diffuser Kit", "calming", "", 6718797840577),
    ("B09GFY84S4", "Relaxiv Dog Calming Diffuser Refills (2 Pack)", "calming", "", 7126166470849),
    ("B0112OD3LA", "Relaxiv Calming Pheromone Spray for Cats", "calming", "", 6718797742273),
    ("B00FAVJX2A", "Relaxiv Calming Collar for Cats", "calming", "", 7378793201857),
    ("B092VY96XD", "Relaxiv Calming Collar for Cats (2 Pack)", "calming", "", 6718797217985),
    ("B07H6LQVDQ", "Beloved Pets Cat Calming Diffuser Kit (new pack)", "calming", "", None),
    ("B08W9R1SKZ", "Beloved Pets Cat Calming Diffuser Refills (2 Pack, new pack)", "calming", "", None),
    ("B08549NNTG", "Beloved Pets Calming Pheromone Spray for Cats (new pack)", "calming", "", None),
]

# TOBYDIC — 7 SKU, все herbal liquid drops 2 oz / 60 ml, с 12 недель.
TOBYDIC: list[tuple[str, str, str]] = [
    ("B0CJ2MMBND", "TOBYDIC Urinary Tract Support",
     "Herbal drops: cranberry, D-mannose — urinary tract & bladder support"),
    ("B0D4R4BJQH", "TOBYDIC Yeast & Skin Support",
     "Herbal drops with probiotics — skin & coat care, healthy immune function"),
    ("B0CJ2L1TZF", "TOBYDIC DEWO Herbal Intestinal Cleanse",
     "Herbal drops: pumpkin seed, wormwood, black walnut — healthy intestinal function"),
    ("B0CZPC2LDD", "TOBYDIC DEWO + Probiotics",
     "DEWO herbal blend + probiotic & prebiotic — healthy intestinal function"),
    ("B0CJ2QQKF3", "TOBYDIC Throat & Respiratory Support",
     "Herbal drops: elderberry, echinacea, mullein — throat, respiratory & immune support"),
    ("B0CZS94891", "TOBYDIC Multivitamin 21-in-1",
     "Daily multivitamin drops — immune, joint, skin & coat support"),
    ("B0DT1J7QJ8", "TOBYDIC Flea & Tick Support",
     "Oral herbal drops — flea & tick season support, skin & coat (never 'kills/prevents')"),
]

# Описания, которых нет в выгрузке Shopify.
DESCRIPTIONS: dict[str, str] = {
    "B0HBQQ6ZTB": "Wet cat food topper & lickable treat in one: tender shreds of real chicken in "
                  "savory gravy. 3 recipes: Chicken Bliss, Chicken & Rabbit, Chicken & Shrimp — "
                  "12 single-serve cups × 1.76 oz (4 of each). 88% moisture supports daily water "
                  "intake. Grain-free & soy-free, added vitamins & taurine. Contains egg and fish. "
                  "Serve on top of a complete meal or on its own as a treat.",
    "B0HBR2TLHH": "Wet cat food topper & lickable treat in one: tender shreds of real tuna in "
                  "savory gravy. 3 recipes: Tuna Bliss, Tuna & Salmon, Tuna & Shrimp — 12 "
                  "single-serve cups × 1.76 oz (4 of each). 88% moisture supports daily water "
                  "intake. Grain-free & soy-free, added taurine and vitamins A, B1, B2, B6, D3, E. "
                  "Serve on top of a complete meal or on its own as a treat.",
}


def url(asin: str) -> str:
    return AMAZON_US + asin
