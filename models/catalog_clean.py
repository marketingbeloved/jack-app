"""Чистые названия товаров Beloved Pets для контента — то, что Джек пишет в ТЗ.

Почему не названия из products.json: там SEO-заголовки Shopify на 200 знаков — «UTI
Treatment», «Natural Antibiotics», «Made for USA», «Revolution» (чужая марка), дубли
«copy-of…». Правило «бери название слово в слово» заставляло Джека тащить этот мусор
в ТЗ, а сокращать он начинал по-своему — отсюда «левые названия» (жалоба Марии,
2026-11-04). Здесь каждому SKU (ключ — shopify_id) дано одно короткое имя, верная
категория и вкус. Состав, цена и комплаенс по-прежнему берутся из products.json.

Категория важна для комплаенса: «Lab tested in the USA» — только для `treats`. В Shopify
диффузоры, капли и chew-добавки лежали в «treats», и бейдж мог уехать на добавку.

Источник имён: Контент-завод knowledge/products/beloved-pets.md + подписи в нашем IG.
Новый SKU в Shopify без строки здесь в промпт не попадёт — добавь строку.
"""

from __future__ import annotations

# shopify_id: (название для контента, категория, вкус)
NAMES: dict[int, tuple[str, str, str]] = {
    10911675580609: ('Relaxiv Calming Pheromone Spray for Cats (2-Pack)', 'calming', ''),  # Calming Pheromone Spray & Scratch Repellent for Cats - Reduc
    10911673778369: ('Yeast & Skin Support Drops (2-Pack)', 'supplement', ''),  # Natural Cats & Dogs Yeast Infection Anti Itch Treatment - It
    10911673155777: ('Urinary Tract Support Drops with Cranberry', 'supplement', ''),  # Cat & Dog Urinary Tract Infection Treatment & Natural UTI Me
    10911672238273: ('Intestinal Cleanse Herbal Drops (2-Pack)', 'supplement', ''),  # Natural Intestinal Defense for Dogs & Cats – Herbal Cleanse 
    10911671484609: ('Double Sweet Potato with Duck Dog Treats (10.6 oz)', 'treats', 'Duck'),  # Beloved Pets Sweet Potato Dog Treats & Healthy Duck Chews 10
    10734511751361: ('Creamy Lickable Cat Treats (Tuna & Chicken Mix)', 'treats', 'Tuna & Chicken'),  # Creamy Lickable Cat Treats & Wet Squeeze Tubes – Tuna Mix, L
    10625799160001: ('Freeze-Dried Chicken Cubes for Cats & Small Dogs', 'treats', 'Chicken'),  # Freeze Dried Chicken Treats for Cats and Small Dogs - All Na
    10625782808769: ('Sweet Potato Chips Dog Treats', 'treats', 'Sweet Potato'),  # Sweet Potato Dog Treats Chips - All Natural Pet Snack Chews 
    7106567569601: ('Flea & Tick Support Chews for Dogs & Cats', 'supplement', ''),  # Flea and Tick Prevention Chewable Pills for Dogs and Cats - 
    7259761148097: ('Relaxiv Cat Calming Diffuser Refills (6-Pack)', 'calming', ''),  # Relaxiv Calming Cat Diffuser Refill & Anti Anxiety Pet Produ
    10454875439297: ('Probiotics & Prebiotics with Enzymes Drops', 'supplement', ''),  # Probiotics & Prebiotics with Enzymes for Dogs and Cats - Dig
    10454881632449: ('Herbiotic Complex Drops', 'supplement', ''),  # Natural Herbiotic for Cats & Dogs – Cranberry & Herbal Blend
    7106558918849: ('Flea & Tick Home Spray (Plant-Based)', 'flea & tick', ''),  # Natural Flea and Tick Home Spray for Dogs, Cats & Ferret - M
    7378562154689: ('Flea & Tick Collar for Dogs', 'flea & tick', ''),  # Natural Flea & Tick Collar for Dogs - 6 Months Control of Be
    7288670716097: ('Flea & Tick Collar for Cats (2-Pack)', 'flea & tick', ''),  # Natural Flea & Tick Collar for Cats - 12 Months Control of B
    10425990447297: ('Kabobs Dog Treats (Duck & Chicken)', 'treats', 'Duck & Chicken'),  # Kabobs Dog Treats with Duck & Chicken Human Grade Meat - All
    7240694563009: ('Plant-Based Flea & Tick Spot-On for Cats & Small Dogs', 'flea & tick', ''),  # Flea and Tick Prevention for Small Dogs & Cats, Rabbits - Na
    7728773431489: ('Flea & Tick Support Chews for Cats (Chicken)', 'supplement', 'Chicken'),  # Beloved Pets Flea & Tick Support Chewable Treats with Chicke
    6718797414593: ('Flea & Tick Support Chews for Dogs (Chicken)', 'supplement', 'Chicken'),  # Beloved Pets Flea & Tick Support Chicken Flavor Pest Support
    7609183174849: ('Flea & Tick + Multivitamin Soft Chews for Dogs (Chicken)', 'supplement', 'Chicken'),  # Beloved Pets Natural Flea & Tick Support + Complex Multivita
    6718797381825: ('Hip & Joint Soft Chews for Dogs', 'supplement', ''),  # Dog Hip and Joint Supplement & Arthritis Pain Relief Treats 
    6718797676737: ('Skin & Immune Soft Chews for Dogs (Bacon)', 'supplement', 'Bacon'),  # Dog Anti Itch & Allergy Relief Chews - Dry Itchy Skin & Hot 
    7543024943297: ('Relaxiv Cat Calming Diffuser Kit (Bundle)', 'calming', ''),  # Cat Calming Pheromone Diffuser Kit | Improved DE-Stress Form
    7728773136577: ('Multivitamin 21-in-1 Drops', 'supplement', ''),  # Cat & Dog Multivitamin Liquid with Glucosamine & Cranberry |
    7378813812929: ('Hemp Calming Oil Drops', 'supplement', ''),  # Cat & Dog Hemp Oil Drops - Pet Calming Anti Anxiety & Herbal
    6718797643969: ('Eye Wash Drops', 'eye & ear', ''),  # Cat & Dog Eye Wash Drops & Tear Stain Remover, Cleaner | Eye
    7378793201857: ('Relaxiv Calming Collar for Cats', 'calming', ''),  # Calming Collar for Cats | Improved DE-Stress Formula | Reduc
    7542293627073: ('Calming Chews for Dogs with Melatonin (Bacon)', 'supplement', 'Bacon'),  # Beloved Pets Calming Chews for Dogs with Melatonin - Bacon F
    10418151751873: ('Biscuit Sticks Wrapped with Chicken', 'treats', 'Chicken'),  # Biscuits Sticks Dog Treats Chicken Wrapped Human Grade Meat 
    7106561999041: ('Flea & Tick Support Chews for Dogs', 'supplement', ''),  # Beloved Pets Flea and Tick Prevention Chewable Pills for Dog
    10418150146241: ('Cod Sticks Wrapped with Chicken', 'treats', 'Cod & Chicken'),  # Beloved Pets Cod Sticks Dog Treats Chicken Wrapped - All Nat
    10580130234561: ('Herbal Comfort & Wellness Drops', 'supplement', ''),  # Beloved Pets Herbal Comfort & Wellness Liquid Supplement for
    7543010132161: ('Digestive Support Drops with Probiotics', 'supplement', ''),  # Natural Digestive Support for Dogs & Cats – Herbal Blend wit
    7126166470849: ('Relaxiv Dog Calming Diffuser Refills (2-Pack)', 'calming', ''),  # Relaxiv Dog Pheromone Diffuser Refill – 2 Count
    6718797906113: ('Eye Wash Drops', 'eye & ear', ''),  # All Pets Eye Wash Drops for Relieve Pink Eye, Allergies Symp
    10456971182273: ('Ear Cleaner Drops', 'eye & ear', ''),  # Cat & Dog Ear Cleaner Drops & Wash Solution - Yeast Otic Inf
    10454868918465: ('Oral Flea & Tick Support Multivitamin Drops', 'supplement', ''),  # Beloved Pets Oral Flea & Tick Support Multivitamin Supplemen
    10426000703681: ('Triple Flavor Sticks (Duck & Chicken)', 'treats', 'Duck & Chicken'),  # Triple Flavor Dog Rawhide Treats - Duck & Chicken Human Grad
    10420801142977: ('Kabobs Dog Treats (Duck & Chicken)', 'treats', 'Duck & Chicken'),  # Kabobs Dog Rawhide Treats with Duck & Chicken Human Grade Me
    10420787642561: ('Chicken Jerky Strips Dog Treats', 'treats', 'Chicken'),  # Chicken Jerky Strips Dog Treats - Human Grade Meat Sticks - 
    10418137628865: ('Sweet Potato Chicken Wraps Dog Treats (1.5 lb)', 'treats', 'Chicken & Sweet Potato'),  # Sweet Potato Jerky Chicken Wraps - Dog Treats Human Grade - 
    10146387689665: ('Duck Jerky Dog Treats (1.5 lb)', 'treats', 'Duck'),  # Duck Jerky Dog Treats - Human Grade Pet Snacks & Grain Free 
    7691154620609: ('Chicken Jerky Dog Treats', 'treats', 'Chicken'),  # Beloved Pets Chicken Jerky Dog Treats & All Natural and Orga
    7728773300417: ('Tear Stain Eye Wipes', 'eye & ear', ''),  # Cat & Dog Eye Wash Wipes & Tear Stain Remover, Cleaner | Hel
    7543081959617: ('Smoked Rawhide Sticks Wrapped with Chicken', 'treats', 'Chicken'),  # Dog Smoked Rawhide Sticks Wrapped Chicken & Pet Natural Chew
    7543068131521: ('Calcium Bones Wrapped with Chicken', 'treats', 'Chicken'),  # Dog Calcium Bones Wrapped Chicken & Rawhide Free Chew Treats
    7543042015425: ('Sweet Potato Twists Wrapped with Chicken', 'treats', 'Chicken & Sweet Potato'),  # Dog Sweet Potato Wrapped with Chicken & Pet Natural Chew Tre
    7543016489153: ('Rawhide Sticks Wrapped with Chicken', 'treats', 'Chicken'),  # Dog Rawhide Sticks Wrapped with Chicken & Pet Natural Chew T
    7543008100545: ('Peanut Butter Bones with Cranberry', 'treats', 'Peanut Butter'),  # Dog Peanut Butter Bones with Cranberry & Rawhide Free Chew T
    7542279176385: ('Relaxiv Cat Calming Diffuser Kit', 'calming', ''),  # Relaxiv Cat Calming Diffuser & Pet Anti Anxiety Products - F
    7378818826433: ('Throat & Respiratory Support Drops', 'supplement', ''),  # Herbal Respiratory Support for Dogs & Cats – Natural Comfort
    6718797185217: ('Chicken Jerky Fillet Dog Treats (1.5 lb)', 'treats', 'Chicken'),  # Chicken Jerky Dog Treats 1.5 Lb - Human Grade Pet Snacks & G
    7259787428033: ('Chicken Jerky Slices Dog Treats (1.5 lb)', 'treats', 'Chicken'),  # Chicken Jerky Slices Dog Treats 1.5 Lb - Human Grade Pet Sna
    7378803982529: ('Urinary Tract Support Drops with Cranberry', 'supplement', ''),  # Cat & Dog Natural Urinary Support with Cranberry Bladder & K
    6718797742273: ('Relaxiv Calming Pheromone Spray for Cats', 'calming', ''),  # RELAXIV Calming Pheromone Spray & Scratch Repellent for Cats
    6718797283521: ('Relaxiv Cat Calming Diffuser Refills (2-Pack)', 'calming', ''),  # Calming Cat Diffuser Refill & Anti Anxiety Pet Products - Fe
    6718797840577: ('Relaxiv Dog Calming Diffuser Kit', 'calming', ''),  # Calming Diffuser Kit for Dogs & Puppy - Pet Separation Anxie
    6718797217985: ('Relaxiv Calming Collar for Cats (2-Pack)', 'calming', ''),  # Cat Calming Collar & Pet Anti Anxiety Products - Feline Calm
}

# Товары, которых ещё нет в выгрузке Shopify. Shreds in Gravy — запуск ноябрь 2026,
# по 4 чашки каждого из 3 рецептов, 12 × 1.76 oz. Это топпер (подаётся ПОВЕРХ корма,
# не вместо) и лакомство-«лизун», но не treats для бейджа «Lab tested».
EXTRA: list[dict] = [
    {"id": "shreds-in-gravy-chicken-mix", "asin": "B0HBQQ6ZTB",
     "title": "Shreds in Gravy Cat Food Topper (Chicken Mix)", "category": "cat topper",
     "flavor": "Chicken Mix",
     "url": "https://www.amazon.com/dp/B0HBQQ6ZTB",
     "description_short": "Wet cat food topper & lickable treat in one: tender shreds of real chicken "
                          "in savory gravy. 3 recipes: Chicken Bliss, Chicken & Rabbit, Chicken & Shrimp — "
                          "12 single-serve cups × 1.76 oz (4 of each). 88% moisture supports daily water intake. Grain-free & soy-free, added "
                          "vitamins & taurine, with chicken liver and egg yolk. Contains egg and fish. "
                          "Serve on top of a complete meal or on its own as a treat."},
    {"id": "shreds-in-gravy-tuna-mix", "asin": "B0HBR2TLHH",
     "title": "Shreds in Gravy Cat Food Topper (Tuna Mix)", "category": "cat topper",
     "flavor": "Tuna Mix",
     "url": "https://www.amazon.com/dp/B0HBR2TLHH",
     "description_short": "Wet cat food topper & lickable treat in one: tender shreds of real tuna in "
                          "savory gravy. 3 recipes: Tuna Bliss, Tuna & Salmon, Tuna & Shrimp — "
                          "12 single-serve cups × 1.76 oz (4 of each). 88% moisture supports daily "
                          "water intake. Grain-free & soy-free, added taurine and vitamins A, B1, B2, "
                          "B6, D3, E. Contains tuna, fish and egg; some recipes also chicken, salmon "
                          "or shrimp. Serve on top of a complete meal or on its own as a treat."},
]
