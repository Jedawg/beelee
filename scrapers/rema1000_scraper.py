import requests
import time
import base64
from io import BytesIO
import pandas as pd
from PIL import Image

# ---------------- CONFIG ----------------
ALGOLIA_APP_ID = "FLWDN2189E"
ALGOLIA_API_KEY = "fa20981a63df668e871a87a8fbd0caed"
INDEX_NAME = "aws-prod-products"

# 🚀 LIMIT: Only get first 500 products (for speed!)
MAX_PRODUCTS = 500

import os
os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/rema1000_products.xlsx"
# ----------------------------------------

url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{INDEX_NAME}/browse"
headers = {
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "Content-Type": "application/json",
}

products = []
cursor = None

# ---------- FETCH PRODUCTS (LIMITED) ----------
print(f"⏳ Fetching up to {MAX_PRODUCTS} Rema1000 products...")
batch = 0

while len(products) < MAX_PRODUCTS:
    payload = {}
    if cursor:
        payload["cursor"] = cursor

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"❌ Failed to fetch batch: {e}")
        break

    hits = data.get("hits", [])
    if not hits:
        break

    for hit in hits:
        if len(products) >= MAX_PRODUCTS:
            break
            
        price = None
        pricing = hit.get("pricing", {})
        if isinstance(pricing, dict):
            price = pricing.get("price")

        image_url = None
        images = hit.get("images", [])
        if images:
            image_url = images[0].get("medium") or images[0].get("small")

        products.append({
            "title": hit.get("name"),
            "price": price,
            "category": hit.get("category_name"),
            "store": "Rema1000",
            "image_url": image_url,
        })

    batch += 1
    print(f"  Batch {batch}: {len(products)} products...")

    cursor = data.get("cursor")
    if not cursor:
        break

    time.sleep(0.3)

print(f"✅ Fetched {len(products)} products")

# ---------- DOWNLOAD IMAGES (SKIP IF TOO MANY) ----------
print("\n⏳ Downloading images...")
success = 0

for i, product in enumerate(products):
    image_url = product.pop("image_url", None)
    
    if not image_url:
        product["image_base64"] = None
        continue

    try:
        r = requests.get(image_url, timeout=10)
        r.raise_for_status()

        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.thumbnail((150, 150), Image.Resampling.LANCZOS)  # Smaller = faster

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=75)  # Lower quality = faster
        img_str = base64.b64encode(buffer.getvalue()).decode()

        product["image_base64"] = f"data:image/jpeg;base64,{img_str}"
        success += 1
    except:
        product["image_base64"] = None

    if (i + 1) % 100 == 0:
        print(f"  Processed {i + 1}/{len(products)} images...")

print(f"✅ Images embedded: {success}/{len(products)}")

# ---------- SAVE ----------
print(f"\n⏳ Saving to {OUTPUT_FILE}...")
df = pd.DataFrame(products, columns=["title", "price", "category", "store", "image_base64"])
df.to_excel(OUTPUT_FILE, index=False)

print(f"\n🐝 Rema1000 scraper done!")
print(f"   Products: {len(products)}")
print(f"   Images:   {success}")
print(f"   File:     {OUTPUT_FILE}")
