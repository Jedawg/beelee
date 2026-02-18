import requests
import time
import base64
from io import BytesIO
import pandas as pd
from PIL import Image
import os

# ---------------- CONFIG ----------------
ALGOLIA_APP_ID = "FLWDN2189E"
ALGOLIA_API_KEY = "fa20981a63df668e871a87a8fbd0caed"
INDEX_NAME = "aws-prod-products"

# FULL CATALOG MODE - Get ALL products!
MAX_PRODUCTS = None  # None = unlimited, get everything!

# MEDIUM RESOLUTION
IMAGE_SIZE = (300, 300)  # Medium quality
IMAGE_QUALITY = 85  # Good quality

os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/rema1000_products.xlsx"
# ----------------------------------------

print("🐝 Rema1000 Scraper - FULL CATALOG MODE")
print("=" * 60)

url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{INDEX_NAME}/browse"
headers = {
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "Content-Type": "application/json",
}

products = []
cursor = None

# ---------- FETCH ALL PRODUCTS ----------
print("⏳ Fetching ALL Rema1000 products from Algolia...")
batch = 0

while True:
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
        price = None
        pricing = hit.get("pricing", {})
        if isinstance(pricing, dict):
            price = pricing.get("price")

        image_url = None
        images = hit.get("images", [])
        if images:
            # Get the BEST available image (medium > small)
            image_url = images[0].get("medium") or images[0].get("large") or images[0].get("small")

        products.append({
            "title": hit.get("name"),
            "price": price,
            "category": hit.get("category_name"),
            "store": "Rema1000",
            "image_url": image_url,
        })

    batch += 1
    print(f"  Batch {batch}: {len(products)} products fetched...")

    cursor = data.get("cursor")
    if not cursor:
        break

    time.sleep(0.3)  # Be nice to the API

print(f"✅ Fetched {len(products)} products total")

# ---------- DOWNLOAD AND CONVERT IMAGES ----------
print(f"\n⏳ Downloading images (medium resolution {IMAGE_SIZE[0]}x{IMAGE_SIZE[1]}px)...")
print("   This may take a while for the full catalog...")

success = 0
failed = 0

for i, product in enumerate(products):
    image_url = product.pop("image_url", None)
    
    if not image_url:
        product["image_base64"] = None
        failed += 1
        continue

    try:
        r = requests.get(image_url, timeout=15)
        r.raise_for_status()

        img = Image.open(BytesIO(r.content)).convert("RGB")
        
        # Resize to medium resolution
        img.thumbnail(IMAGE_SIZE, Image.Resampling.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=IMAGE_QUALITY)
        img_str = base64.b64encode(buffer.getvalue()).decode()

        product["image_base64"] = f"data:image/jpeg;base64,{img_str}"
        success += 1
    except Exception as e:
        product["image_base64"] = None
        failed += 1

    # Progress update every 500 products
    if (i + 1) % 500 == 0:
        print(f"  Processed {i + 1}/{len(products)} images ({success} successful, {failed} failed)...")

print(f"✅ Images processed: {success} successful, {failed} failed")

# ---------- SAVE TO EXCEL ----------
print(f"\n💾 Saving to {OUTPUT_FILE}...")

df = pd.DataFrame(products, columns=["title", "price", "category", "store", "image_base64"])
df.to_excel(OUTPUT_FILE, index=False)

file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)

print(f"\n{'=' * 60}")
print(f"🐝 Rema1000 Scraper Complete!")
print(f"{'=' * 60}")
print(f"Total Products:    {len(products)}")
print(f"With Images:       {success}")
print(f"Without Images:    {failed}")
print(f"Image Size:        {IMAGE_SIZE[0]}x{IMAGE_SIZE[1]}px")
print(f"Image Quality:     {IMAGE_QUALITY}%")
print(f"Output File:       {OUTPUT_FILE}")
print(f"File Size:         {file_size_mb:.2f} MB")
print(f"{'=' * 60}")
