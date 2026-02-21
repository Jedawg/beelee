"""
merge_products.py
----------------------------------
Merges products AND harmonizes categories automatically!
"""

import pandas as pd
import os
from datetime import datetime

os.makedirs("data", exist_ok=True)

# ==================== CONFIG ====================
MAX_TOTAL_PRODUCTS = 100000
HARMONIZE_CATEGORIES = True  # Set to False to skip

# Category mapping
CATEGORY_MAP = {
    # Common variations to Rema1000 format
    "Frugt & Grønt": "Frugt og grønt",
    "Kød & Fjerkræ": "Kød",
    "Vegetables": "Frugt og grønt",
    "Fruits": "Frugt og grønt",
    "Meat": "Kød",
    "Dairy": "Mejeri",
    "Beverages": "Drikkevarer",
    "Snacks": "Slik og snacks",
    "Frozen": "Frost",
    "Breakfast": "Morgenmad",
    "": "Andet",
    None: "Andet"
}

# Keywords for auto-categorization
KEYWORD_CATEGORIES = {
    "Frugt og grønt": ["tomat", "agurk", "salat", "æble", "banan", "kartoffel", "tomato", "apple", "banana"],
    "Kød": ["oksekød", "kylling", "bacon", "pølse", "beef", "chicken", "pork"],
    "Fisk": ["laks", "tuna", "rejer", "salmon", "fish"],
    "Mejeri": ["mælk", "ost", "yoghurt", "smør", "milk", "cheese", "butter"],
    "Brød og kager": ["brød", "kage", "bread", "cake", "cookie"],
    "Drikkevarer": ["vand", "juice", "kaffe", "cola", "water", "coffee"],
    "Slik og snacks": ["chips", "chokolade", "chocolate", "candy"],
    "Frost": ["frosne", "is", "frozen", "ice cream"],
    "Morgenmad": ["cornflakes", "müsli", "cereal"],
    "Kolonial": ["pasta", "ris", "mel", "rice", "flour", "sauce"]
}

# ==================== FUNCTIONS ====================

def categorize_by_title(title, master_categories):
    """Categorize based on product title"""
    if pd.isna(title):
        return "Andet"
    
    title_lower = title.lower()
    
    for category, keywords in KEYWORD_CATEGORIES.items():
        if category in master_categories:
            for keyword in keywords:
                if keyword in title_lower:
                    return category
    
    return "Andet"

def harmonize_categories(df):
    """Harmonize all categories to Rema1000 standard"""
    
    print("\n🔄 Harmonizing categories...")
    
    # Extract Rema1000 categories as master
    rema_products = df[df['store'] == 'Rema1000']
    master_categories = list(rema_products['category'].dropna().unique())
    master_categories.append("Andet")
    
    print(f"   Master categories ({len(master_categories)}): {', '.join(sorted(master_categories)[:10])}...")
    
    # Track changes
    changed = 0
    uncategorized_before = df['category'].isna().sum()
    
    new_categories = []
    for idx, row in df.iterrows():
        current_cat = row['category']
        store = row['store']
        title = row['title']
        
        # Keep Rema1000 categories as-is
        if store == 'Rema1000' and pd.notna(current_cat):
            new_categories.append(current_cat)
        
        # Map known categories
        elif current_cat in CATEGORY_MAP:
            new_categories.append(CATEGORY_MAP[current_cat])
            changed += 1
        
        # Check if already valid
        elif current_cat in master_categories:
            new_categories.append(current_cat)
        
        # Categorize by title
        else:
            cat = categorize_by_title(title, master_categories)
            new_categories.append(cat)
            if pd.isna(current_cat):
                changed += 1
    
    df['category'] = new_categories
    
    uncategorized_after = (df['category'] == 'Andet').sum()
    
    print(f"   ✅ Categorized {changed} products")
    print(f"   ✅ Uncategorized: {uncategorized_before} → {uncategorized_after}")
    
    return df

# ==================== MAIN ====================

print("🐝 Merge Products with Category Harmonization")
print("=" * 60)

files = {
    "Aviser": "data/aviser_products.xlsx",
    "Rema1000": "data/rema1000_products.xlsx",
}

all_dfs = []

for name, path in files.items():
    if os.path.exists(path):
        df = pd.read_excel(path)
        print(f"\n✅ Loaded {name}: {len(df)} products")
        all_dfs.append(df)
    else:
        print(f"\n⚠️  {name} not found")

if not all_dfs:
    print("\n❌ No data files!")
    exit(1)

# Merge
merged = pd.concat(all_dfs, ignore_index=True)
print(f"\n📊 Combined: {len(merged)} products")

# Ensure columns
for col in ["title", "price", "category", "store", "remaining_days", "image_base64"]:
    if col not in merged.columns:
        merged[col] = None

# Keep only required columns
merged = merged[["title", "price", "category", "store", "remaining_days", "image_base64"]]

# Cleanup
merged = merged.dropna(subset=["title", "price"])
merged = merged[merged["title"].str.strip() != ""]
print(f"After cleanup: {len(merged)} products")

# Remove without images
merged = merged[merged["image_base64"].notna()]
print(f"With images: {len(merged)} products")

# HARMONIZE CATEGORIES
if HARMONIZE_CATEGORIES:
    merged = harmonize_categories(merged)

# Limit products
if len(merged) > MAX_TOTAL_PRODUCTS:
    print(f"\n⚠️  Limiting to {MAX_TOTAL_PRODUCTS} products")
    
    # Prioritize offers
    offers = merged[merged["remaining_days"].notna()].head(600)
    regular = merged[merged["remaining_days"].isna()].head(MAX_TOTAL_PRODUCTS - len(offers))
    merged = pd.concat([offers, regular], ignore_index=True)

# Sort
merged['sort_priority'] = merged['remaining_days'].notna().astype(int)
merged = merged.sort_values(['sort_priority', 'remaining_days', 'price'], 
                            ascending=[False, True, True])
merged = merged.drop('sort_priority', axis=1)

# Save
output = "data/products.xlsx"
merged.to_excel(output, index=False)

file_size_mb = os.path.getsize(output) / (1024 * 1024)

print(f"\n{'=' * 60}")
print(f"🐝 Merge Complete!")
print(f"{'=' * 60}")
print(f"Total Products:    {len(merged)}")
print(f"Stores:            {sorted(merged['store'].unique().tolist())}")
print(f"Categories:        {merged['category'].nunique()}")
print(f"Output File:       {output}")
print(f"File Size:         {file_size_mb:.2f} MB")
print(f"Timestamp:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"")

# Category breakdown
print("📊 Category Distribution:")
for cat, count in merged['category'].value_counts().head(15).items():
    pct = (count / len(merged)) * 100
    print(f"   • {cat}: {count} ({pct:.1f}%)")

print(f"\n{'=' * 60}")
