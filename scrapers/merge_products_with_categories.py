"""
merge_products_with_categories.py
----------------------------------
Merges ALL scraper outputs + harmonizes categories automatically.
Add a new scraper? Just save its output to data/ and it's included.
"""

import pandas as pd
import os
import re
from datetime import datetime
from glob import glob

# ── Always work relative to THIS script's location ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== CONFIG ====================
MAX_TOTAL_PRODUCTS   = 10000
HARMONIZE_CATEGORIES = True

# ── Which files to include ──────────────────────
AUTO_DISCOVER = True   # Auto-find all *_products.xlsx in data/

EXPLICIT_FILES = {
    "Aviser":   os.path.join(DATA_DIR, "aviser_products.xlsx"),
    "Rema1000": os.path.join(DATA_DIR, "rema1000_products.xlsx"),
    "Wolt":     os.path.join(DATA_DIR, "wolt_products.xlsx"),
}
# ─────────────────────────────────────────────────

COLUMNS = ["title", "price", "category", "store", "remaining_days", "image_base64"]

# ==================== CATEGORY CONFIG ====================

CATEGORY_MAP = {
    # Wolt categories → standard
    "Frugt & grønt":      "Frugt og grønt",
    "Kød & fisk":         "Kød",
    "Mejeri & køl":       "Mejeri",
    "Kiks & kager":       "Brød og kager",
    "Slik & chocolade":   "Slik og snacks",
    "Chips & snacks":     "Slik og snacks",
    "Kaffe & te":         "Drikkevarer",
    "Drikkevarer":        "Drikkevarer",
    "Spisekammeret":      "Kolonial",
    "Verdensmad":         "Kolonial",
    "Convenience":        "Kolonial",
    # Other common variations
    "Frugt & Grønt":      "Frugt og grønt",
    "Kød & Fjerkræ":      "Kød",
    "Vegetables":         "Frugt og grønt",
    "Fruits":             "Frugt og grønt",
    "Meat":               "Kød",
    "Dairy":              "Mejeri",
    "Beverages":          "Drikkevarer",
    "Snacks":             "Slik og snacks",
    "Frozen":             "Frost",
    "Breakfast":          "Morgenmad",
    "":                   "Andet",
    None:                 "Andet",
}

MASTER_CATEGORIES = [
    "Frugt og grønt", "Kød", "Fisk", "Mejeri",
    "Brød og kager", "Drikkevarer", "Slik og snacks",
    "Frost", "Morgenmad", "Kolonial", "Andet",
]

KEYWORD_CATEGORIES = {
    "Frugt og grønt": [
        "tomat", "tomater", "agurk", "agurker", "salat", "peber", "peberfrugter",
        "løg", "rødløg", "hvidløg", "kartoffel", "kartofler", "gulerod", "gulerødder",
        "broccoli", "blomkål", "squash", "zucchini", "aubergine", "auberginer",
        "spinat", "grønkål", "rosenkål", "spidskål", "hvidkål", "rødkål", "kål",
        "porre", "porrer", "selleri", "pastinak", "persillerod", "radise", "majs",
        "æble", "æbler", "banan", "bananer", "appelsin", "appelsiner", "pære", "pærer",
        "citron", "lime", "avocado", "blomme", "druer", "jordbær", "hindbær",
        "blåbær", "brombær", "melon", "vandmelon", "ananas", "kiwi", "mango",
        "fersken", "nektarin", "abrikos", "paprika", "chili",
        "persille", "basilikum", "koriander", "timian", "rosmarin", "dild", "mynte",
        "ruccola", "iceberg", "grøntsag", "grøntsager", "frugt", "bær",
        "tomato", "cucumber", "lettuce", "onion", "garlic", "potato", "carrot",
        "spinach", "cabbage", "apple", "banana", "orange", "lemon", "grape",
        "strawberry", "raspberry", "blueberry", "vegetable", "fruit", "berry",
    ],
    "Kød": [
        "oksekød", "kalvekød", "svinekød", "lammekød", "lam", "kylling",
        "bacon", "pølse", "pølser", "medister", "hamburger", "hakket", "hakkekød",
        "bøf", "steak", "kotelet", "mørbrad", "schnitzel", "skinke",
        "leverpostej", "kalkun", "and", "culotte", "ribeye", "filet",
        "grillpølse", "wienerpølse", "kød",
        "karbonader", "karbonade", "frikadeller", "frikadelle",
        "beef", "pork", "lamb", "chicken", "turkey", "duck",
        "sausage", "minced", "mince", "ham", "meat", "burger",
    ],
    "Fisk": [
        "laks", "ørred", "torsk", "tuna", "tunfisk", "makrel", "sild", "sardiner",
        "rejer", "reje", "hummer", "krabbe", "muslinger", "østers",
        "fiskefillet", "fiskefilet", "røget", "fisk", "seafood", "skaldyr",
        "salmon", "trout", "cod", "mackerel", "herring", "shrimp", "prawn",
        "lobster", "crab", "mussels", "oyster", "fish", "fillet",
    ],
    "Mejeri": [
        "mælk", "sødmælk", "skummetmælk", "letmælk", "minimælk", "kærnemælk",
        "ost", "cheddar", "mozzarella", "feta", "brie", "parmesan", "havarti",
        "yoghurt", "yogurt", "skyr", "ymer", "kefir",
        "smør", "margarine", "fløde", "piskefløde", "creme fraiche",
        "kvark", "hytteost", "cottage cheese", "ricotta",
        "æg", "æggene", "skrabeæg", "frilandsæg", "fraiche",
        "milk", "cheese", "butter", "cream", "yogurt", "dairy", "egg", "eggs",
    ],
    "Brød og kager": [
        "brød", "rugbrød", "franskbrød", "ciabatta", "baguette", "pitabrød", "tortilla",
        "rundstykke", "bolle", "boller", "bagel",
        "kage", "lagkage", "wienerbrød", "croissant", "kanelsnegl", "muffin", "brownie",
        "knækbrød", "cracker", "kiks",
        "bread", "roll", "bun", "cake", "croissant", "bagel", "toast",
        "cookie", "biscuit", "cracker", "muffin", "pastry",
    ],
    "Drikkevarer": [
        "vand", "mineralvand", "kildevand", "danskvand",
        "juice", "appelsinjuice", "æblejuice", "smoothie",
        "sodavand", "cola", "pepsi", "fanta", "sprite", "cocio", "saft",
        "kaffe", "espresso", "te", "kakao",
        "øl", "pilsner", "vin", "rødvin", "hvidvin", "champagne", "cider",
        "energidrik", "sportsdrik",
        "water", "juice", "soda", "coffee", "tea", "beer", "wine", "beverage", "drink",
    ],
    "Slik og snacks": [
        "chips", "popcorn", "nachos", "pringles",
        "nødder", "peanuts", "cashew", "mandler", "hasselnødder", "valnødder",
        "chokolade", "slik", "bolsjer", "vingummi", "lakrids", "tyggegummi",
        "twix", "snickers", "mars", "kitkat", "haribo", "malaco",
        "nuts", "chocolate", "candy", "sweets", "gummy", "liquorice", "snack",
    ],
    "Frost": [
        "frosne", "frost", "frossen", "dybfrossen",
        "is", "ispinde", "flødeis", "sorbet", "magnum",
        "pizza", "lasagne", "pommes frites",
        "frozen", "ice cream", "popsicle",
    ],
    "Morgenmad": [
        "cornflakes", "müsli", "musli", "havregryn", "havre", "grød",
        "honning", "marmelade", "syltetøj", "nutella", "peanut butter",
        "cereal", "muesli", "granola", "oatmeal", "honey", "jam",
    ],
    "Kolonial": [
        "pasta", "spaghetti", "macaroni", "penne", "fusilli",
        "ris", "risotto", "basmati", "jasmin",
        "mel", "hvedemel", "sukker", "salt", "peber",
        "olie", "olivenolie", "rapsolie", "eddike", "balsamico",
        "sauce", "ketchup", "mayonnaise", "remoulade", "sennep", "dressing",
        "bouillon", "fond", "krydderi",
        "dåse", "konserves", "bønner",
        "gær", "bagepulver", "rosiner", "korender", "sirup", "nougat",
        "rice", "flour", "sugar", "oil", "vinegar", "ketchup",
        "mayo", "mustard", "spice", "stock", "canned", "beans",
    ],
}


# ==================== FUNCTIONS ====================

def categorize_by_title(title):
    if pd.isna(title):
        return "Andet"
    title_norm = ' '.join(re.sub(r'[^\w\s]', ' ', title.lower()).split())
    best_cat, best_score = "Andet", 0
    for cat, keywords in KEYWORD_CATEGORIES.items():
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            pattern = r'\b' + re.escape(kw_lower) + r'\b'
            if re.search(pattern, title_norm):
                score += 20
            elif kw_lower in title_norm:
                score += 10
            elif any(w.startswith(kw_lower) for w in title_norm.split()):
                score += 5
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat if best_score >= 5 else "Andet"


def harmonize_categories(df):
    print("\n🔄 Harmonizing categories...")

    # Use hardcoded master categories (not dependent on Rema1000 being present)
    masters = set(MASTER_CATEGORIES)

    new_cats = []
    counts   = dict(kept_rema=0, mapped=0, kept_valid=0, by_title=0, andet=0)
    samples  = []
    fails    = []

    for _, row in df.iterrows():
        cat   = row.get("category")
        store = row.get("store", "")
        title = row.get("title", "")

        # 1. Keep Rema1000 categories (already correct)
        if store == "Rema1000" and pd.notna(cat) and cat != "" and cat in masters:
            new_cats.append(cat)
            counts["kept_rema"] += 1

        # 2. Map known category names
        elif cat in CATEGORY_MAP:
            mapped = CATEGORY_MAP[cat]
            new_cats.append(mapped)
            counts["mapped"] += 1

        # 3. Already a valid master category
        elif pd.notna(cat) and cat in masters:
            new_cats.append(cat)
            counts["kept_valid"] += 1

        # 4. Categorize by product title
        else:
            guessed = categorize_by_title(title)
            new_cats.append(guessed)
            if guessed != "Andet":
                counts["by_title"] += 1
                if len(samples) < 8:
                    samples.append(f"      '{title[:55]}' → '{guessed}'")
            else:
                counts["andet"] += 1
                if len(fails) < 8:
                    fails.append(f"      '{title[:55]}' → Andet")

    df["category"] = new_cats

    if samples:
        print("   ✅ Categorized by title (sample):")
        for s in samples: print(s)
    if fails:
        print("   ⚠️  Could not categorize (sample):")
        for f in fails: print(f)

    need  = counts["by_title"] + counts["andet"]
    rate  = counts["by_title"] / need * 100 if need else 0
    print(f"\n   Kept Rema1000: {counts['kept_rema']}")
    print(f"   Mapped:        {counts['mapped']}")
    print(f"   Kept valid:    {counts['kept_valid']}")
    print(f"   By title:      {counts['by_title']}")
    print(f"   Andet:         {counts['andet']}")
    print(f"   🎯 Title success rate: {rate:.1f}%")
    return df


# ==================== MAIN ====================

print("🐝 Merge Products with Category Harmonization")
print("=" * 60)

# ── Discover files ──────────────────────────────
if AUTO_DISCOVER:
    found_files = sorted(glob(os.path.join(DATA_DIR, "*_products.xlsx")))
    files = {os.path.basename(f).replace("_products.xlsx", "").title(): f
             for f in found_files}
    print(f"\n📂 Looking in: {DATA_DIR}")
    print(f"📂 Auto-discovered {len(files)} file(s):")
    for name, path in files.items():
        size_mb = os.path.getsize(path) / 1024 / 1024 if os.path.exists(path) else 0
        print(f"   {name}: {path}  ({size_mb:.1f} MB)")
else:
    files = EXPLICIT_FILES
    print(f"\n📂 Using explicit file list:")
    for name, path in files.items():
        exists = "✅" if os.path.exists(path) else "❌"
        print(f"   {exists} {name}: {path}")

# ── Load ────────────────────────────────────────
all_dfs = []
for name, path in files.items():
    if os.path.exists(path):
        df = pd.read_excel(path)
        print(f"\n✅ Loaded {name}: {len(df)} products")
        all_dfs.append(df)
    else:
        print(f"\n⚠️  Not found, skipping: {path}")

if not all_dfs:
    print("\n❌ No data files found!")
    exit(1)

# ── Merge ───────────────────────────────────────
merged = pd.concat(all_dfs, ignore_index=True)
print(f"\n📊 Combined: {len(merged)} products")

for col in COLUMNS:
    if col not in merged.columns:
        merged[col] = None

merged = merged[COLUMNS]
merged = merged.dropna(subset=["title", "price"])
merged = merged[merged["title"].astype(str).str.strip() != ""]
print(f"After cleanup: {len(merged)} products")

# Show store breakdown BEFORE image filter (helps diagnose missing stores)
print(f"\n📊 Store counts before image filter:")
for store, n in merged["store"].value_counts().items():
    has_img = merged[merged["store"] == store]["image_base64"].notna().sum()
    print(f"   {store}: {n} total  ({has_img} with images)")

merged = merged[merged["image_base64"].notna()]
print(f"\nWith images: {len(merged)} products")

# ── Harmonize ───────────────────────────────────
if HARMONIZE_CATEGORIES:
    merged = harmonize_categories(merged)

# ── Limit ───────────────────────────────────────
if len(merged) > MAX_TOTAL_PRODUCTS:
    print(f"\n⚠️  Limiting to {MAX_TOTAL_PRODUCTS}")
    offers  = merged[merged["remaining_days"].notna()].head(600)
    regular = merged[merged["remaining_days"].isna()].head(MAX_TOTAL_PRODUCTS - len(offers))
    merged  = pd.concat([offers, regular], ignore_index=True)

# ── Sort ────────────────────────────────────────
merged["sort_priority"] = merged["remaining_days"].notna().astype(int)
merged = merged.sort_values(
    ["sort_priority", "remaining_days", "price"],
    ascending=[False, True, True]
).drop("sort_priority", axis=1)

# ── Save ────────────────────────────────────────
output = os.path.join(DATA_DIR, "products.xlsx")
merged.to_excel(output, index=False)
mb = os.path.getsize(output) / 1024 / 1024

print(f"\n{'='*60}")
print(f"🐝 Merge Complete!")
print(f"{'='*60}")
print(f"Total Products: {len(merged)}")
print(f"Stores:         {sorted(merged['store'].unique().tolist())}")
print(f"Categories:     {merged['category'].nunique()}")
print(f"Output:         {output}  ({mb:.2f} MB)")
print(f"Timestamp:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n📊 Category Distribution:")
for cat, n in merged["category"].value_counts().head(15).items():
    pct = n / len(merged) * 100
    print(f"   {cat}: {n} ({pct:.1f}%)")
print(f"\n📊 Store Distribution:")
for store, n in merged["store"].value_counts().items():
    print(f"   {store}: {n}")
