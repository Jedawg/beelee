"""
diagnose_categories.py
Run this locally to see exactly which categories are in each file
and which ones are ending up as Andet.

Usage: python diagnose_categories.py
"""

import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "data")

MASTER = {
    "Frugt og grønt", "Kød", "Fisk", "Mejeri",
    "Brød og kager", "Drikkevarer", "Slik og snacks",
    "Frost", "Morgenmad", "Kolonial", "Andet"
}

files = {
    "Rema1000": os.path.join(DATA_DIR, "rema1000_products.xlsx"),
    "Aviser":   os.path.join(DATA_DIR, "aviser_products.xlsx"),
    "Wolt":     os.path.join(DATA_DIR, "wolt_products.xlsx"),
}

for name, path in files.items():
    if not os.path.exists(path):
        print(f"\n⚠️  {name}: file not found ({path})")
        continue

    df = pd.read_excel(path)
    print(f"\n{'='*60}")
    print(f"📦 {name}: {len(df)} products")
    print(f"{'='*60}")

    if "category" not in df.columns:
        print("  ❌ No 'category' column!")
        print(f"  Columns: {list(df.columns)}")
        continue

    cats = df["category"].value_counts()
    print(f"\n  All categories ({len(cats)} unique):")
    for cat, count in cats.items():
        pct    = count / len(df) * 100
        status = "✅" if cat in MASTER else "❓"
        print(f"    {status} {cat!r}: {count} ({pct:.1f}%)")

    # Show examples of unmapped categories
    unmapped = df[~df["category"].isin(MASTER)]
    if len(unmapped) > 0:
        print(f"\n  ❓ Unmapped categories ({len(unmapped)} products):")
        for cat, group in unmapped.groupby("category"):
            sample = group["title"].head(3).tolist()
            print(f"    '{cat}': {sample}")
