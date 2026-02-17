"""
merge_products.py
-----------------
Merges aviser_products.xlsx + rema1000_products.xlsx into one
final data/products.xlsx that Beelee loads automatically.

Run this AFTER both scrapers have finished.
"""

import pandas as pd
import os
from datetime import datetime

os.makedirs("data", exist_ok=True)

files = {
    "Aviser (weekly offers)": "data/aviser_products.xlsx",
    "Rema1000 (full catalogue)": "data/rema1000_products.xlsx",
}

all_dfs = []

for name, path in files.items():
    if os.path.exists(path):
        df = pd.read_excel(path)
        print(f"✅ Loaded {name}: {len(df)} products")
        all_dfs.append(df)
    else:
        print(f"⚠️  Skipped {name} — file not found: {path}")

if not all_dfs:
    print("❌ No data files found! Make sure scrapers ran first.")
    exit(1)

# Merge all into one DataFrame
merged = pd.concat(all_dfs, ignore_index=True)

# Make sure required columns exist
for col in ["title", "price", "category", "store", "remaining_days", "image_base64"]:
    if col not in merged.columns:
        merged[col] = None

# Keep only the columns Beelee needs (in correct order)
merged = merged[["title", "price", "category", "store", "remaining_days", "image_base64"]]

# Drop rows with no title or price
merged = merged.dropna(subset=["title", "price"])
merged = merged[merged["title"].str.strip() != ""]

# Save final file
output = "data/products.xlsx"
merged.to_excel(output, index=False)

print(f"\n🐝 Merge complete!")
print(f"   Total products: {len(merged)}")
print(f"   Stores: {sorted(merged['store'].unique().tolist())}")
print(f"   Saved to: {output}")
print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
