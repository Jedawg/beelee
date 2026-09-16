"""
enrich_nutrition.py
-------------------
Adds nutrition data + Nutri-Score to data/products.xlsx.

Two sources, in order:
  1. Open Food Facts lookup by barcode  (best — gives an official Nutri-Score)
  2. Local Nutri-Score calculation from the per-100g values OFF returns

Run AFTER merge_products_with_categories.py:
    python scrapers/enrich_nutrition.py

Caches every lookup in data/off_cache.json so re-runs are nearly free.

Install: pip install requests pandas openpyxl
"""

import os, json, time, re
import requests
import pandas as pd

# ─────────────────── CONFIG ───────────────────
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, "data") if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, "data")

PRODUCTS_FILE = os.path.join(DATA_DIR, "products.xlsx")
CACHE_FILE    = os.path.join(DATA_DIR, "off_cache.json")

DELAY         = 0.12    # seconds between OFF requests (their fair-use guidance)
MAX_LOOKUPS   = 2000    # cap per run so a nightly job stays bounded
# ──────────────────────────────────────────────

OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{}.json"
FIELDS  = ",".join([
    "product_name", "nutriscore_grade", "nova_group", "ecoscore_grade",
    "ingredients_text", "ingredients_text_da", "allergens_tags",
    "nutriments", "quantity",
])

sess = requests.Session()
# OFF asks every client to identify itself
sess.headers["User-Agent"] = "Beelee/1.0 (Danish grocery price comparison; github.com/Jedawg/beelee)"


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache):
    json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False)


def lookup(barcode, cache):
    """Fetch one product from Open Food Facts. Returns dict or None."""
    if barcode in cache:
        return cache[barcode]
    try:
        r = sess.get(OFF_URL.format(barcode), params={"fields": FIELDS}, timeout=12)
        if r.status_code == 404:
            cache[barcode] = None
            return None
        r.raise_for_status()
        data = r.json()
        if data.get("status") != 1:
            cache[barcode] = None
            return None

        p = data.get("product") or {}
        n = p.get("nutriments") or {}

        result = {
            "nutriscore":  (p.get("nutriscore_grade") or "").upper() or None,
            "nova":        p.get("nova_group"),
            "ecoscore":    (p.get("ecoscore_grade") or "").upper() or None,
            "ingredients": p.get("ingredients_text_da") or p.get("ingredients_text") or None,
            "allergens":   ", ".join(
                                t.split(":")[-1] for t in (p.get("allergens_tags") or [])
                            ) or None,
            "energy_kcal": n.get("energy-kcal_100g"),
            "fat":         n.get("fat_100g"),
            "sat_fat":     n.get("saturated-fat_100g"),
            "sugars":      n.get("sugars_100g"),
            "salt":        n.get("salt_100g"),
            "fiber":       n.get("fiber_100g"),
            "protein":     n.get("proteins_100g"),
        }
        cache[barcode] = result
        return result
    except Exception:
        return None


# ──────────────────────────────────────────────
# Local Nutri-Score fallback (2023 algorithm, general foods)
# Used when OFF has nutrition values but no computed grade.
# ──────────────────────────────────────────────
def _points(value, thresholds):
    if value is None:
        return 0
    for i, t in enumerate(thresholds):
        if value <= t:
            return i
    return len(thresholds)


def calc_nutriscore(row, is_beverage=False, is_cheese=False):
    energy_kj = (row.get("energy_kcal") or 0) * 4.184

    if is_beverage:
        neg = (
            _points(energy_kj,        [30, 90, 150, 210, 240, 270, 300, 330, 360, 390])
            + _points(row.get("sugars"),  [0.5, 2, 3.5, 5, 6, 7, 8, 9, 10, 11])
            + _points(row.get("sat_fat"), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
            + _points(row.get("salt"),    [0.2, 0.4, 0.6, 0.8, 1, 1.2, 1.4, 1.6, 1.8, 2])
        )
    else:
        neg = (
            _points(energy_kj,        [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350])
            + _points(row.get("sugars"),  [3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51])
            + _points(row.get("sat_fat"), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
            + _points(row.get("salt"),    [0.2, 0.4, 0.6, 0.8, 1, 1.2, 1.4, 1.6, 1.8, 2, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0])
        )

    pos = (
        _points(row.get("fiber"),   [3.0, 4.1, 5.2, 6.3, 7.4])
        + _points(row.get("protein"), [2.4, 4.8, 7.2, 9.6, 12, 14, 17])
    )

    # Protein points only count fully below the negative-point cap
    score = neg - pos if (neg < 11 or is_cheese) else neg - _points(row.get("fiber"), [3.0, 4.1, 5.2, 6.3, 7.4])

    if is_beverage:
        cuts = [(2, "B"), (6, "C"), (9, "D")]
        if score <= 2:  return "B"
        if score <= 6:  return "C"
        if score <= 9:  return "D"
        return "E"

    if score <= 0:   return "A"
    if score <= 2:   return "B"
    if score <= 10:  return "C"
    if score <= 18:  return "D"
    return "E"


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────
print("🥗 Beelee nutrition enrichment")
print("=" * 60)

if not os.path.exists(PRODUCTS_FILE):
    print(f"❌ {PRODUCTS_FILE} not found — run the merge script first")
    raise SystemExit(1)

df = pd.read_excel(PRODUCTS_FILE)
print(f"\n📦 Loaded {len(df)} products")

if "barcode" not in df.columns:
    print("❌ No 'barcode' column — re-run the scrapers with the updated versions")
    raise SystemExit(1)

# Normalise barcodes to strings without a trailing .0 from Excel
df["barcode"] = (
    df["barcode"].astype(str)
      .str.replace(r"\.0$", "", regex=True)
      .replace({"nan": None, "None": "", "": None})
)

with_bc = df["barcode"].notna().sum()
print(f"   {with_bc} have a barcode ({with_bc/len(df)*100:.0f}%)")

cache = load_cache()
print(f"   {len(cache)} barcodes already cached")

NEW_COLS = ["nutriscore", "nova", "ecoscore", "allergens",
            "energy_kcal", "fat", "sat_fat", "sugars", "salt", "fiber", "protein"]
for col in NEW_COLS:
    if col not in df.columns:
        df[col] = None
if "ingredients" not in df.columns:
    df["ingredients"] = None

todo = [b for b in df["barcode"].dropna().unique() if b not in cache][:MAX_LOOKUPS]
print(f"\n🔍 Looking up {len(todo)} new barcodes on Open Food Facts...")

hits = 0
for i, bc in enumerate(todo):
    if lookup(bc, cache):
        hits += 1
    if (i + 1) % 100 == 0:
        print(f"   {i+1}/{len(todo)}  ✅ {hits} found")
        save_cache(cache)
    time.sleep(DELAY)

save_cache(cache)
print(f"✅ {hits}/{len(todo)} found on Open Food Facts")

# ── Apply cached data to the dataframe ──
print("\n📝 Applying nutrition data...")
applied = calculated = 0

BEVERAGE_CATS = {"Drikkevarer"}
CHEESE_WORDS  = ("ost", "cheese", "cheddar", "mozzarella", "brie", "feta")

for idx, row in df.iterrows():
    bc = row["barcode"]
    if not bc:
        continue
    info = cache.get(bc)
    if not info:
        continue

    for col in NEW_COLS:
        if info.get(col) is not None:
            df.at[idx, col] = info[col]

    # Prefer the scraper's own ingredient text, fall back to OFF
    if not row.get("ingredients") and info.get("ingredients"):
        df.at[idx, "ingredients"] = info["ingredients"]

    applied += 1

    # If OFF has no grade but has the numbers, compute one locally
    if not info.get("nutriscore") and info.get("energy_kcal") is not None:
        title = str(row.get("title") or "").lower()
        grade = calc_nutriscore(
            info,
            is_beverage=row.get("category") in BEVERAGE_CATS,
            is_cheese=any(w in title for w in CHEESE_WORDS),
        )
        df.at[idx, "nutriscore"] = grade
        calculated += 1

df.to_excel(PRODUCTS_FILE, index=False)
mb = os.path.getsize(PRODUCTS_FILE) / 1024 / 1024

print(f"\n{'='*60}")
print(f"🥗 Enrichment complete!")
print(f"{'='*60}")
print(f"Products with nutrition:  {applied}")
print(f"Nutri-Score calculated:   {calculated}")
print(f"Nutri-Score total:        {df['nutriscore'].notna().sum()}")
print(f"Ingredients total:        {df['ingredients'].notna().sum()}")
print(f"Output:                   {PRODUCTS_FILE}  ({mb:.1f} MB)")

if df["nutriscore"].notna().any():
    print(f"\n📊 Nutri-Score distribution:")
    for g, n in df["nutriscore"].value_counts().sort_index().items():
        bar = "█" * int(n / max(1, df["nutriscore"].notna().sum()) * 30)
        print(f"   {g}: {n:5}  {bar}")
