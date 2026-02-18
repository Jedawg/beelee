import os
import requests
from PIL import Image
from io import BytesIO
import re
import base64
from datetime import datetime, date
from openpyxl import Workbook

# ---------------- CONFIG ----------------

# ⚠️ UPDATE THESE URLS EACH WEEK with latest catalog links!
CATALOGS = {
    "Netto": "https://netto.dayli.eu/f596-2026-nette-au08/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Lidl": "https://lidl.dayli.eu/36e9-soen-d-15-l-r-d-21-februar/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Rema1000": "https://rema1000.aviou.io/c8f6-2026-uge-8-rema-1000/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Brugsen": "https://brugsen.dayli.se/cb5e-2026-uge-7-brugsen/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Føtex": "https://foetex.dayli.eu/9049-2026-uge-8-9-foetex/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "SuperBrugsen & Kvickly": "https://kvickly.dayli.eu/c49f-2026-uge-6-7-kvickly/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Meny": "https://meny.dayli.eu/7959-2026-uge-8-meny/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Min Kobmand": "https://min-koebmand.dayli.eu/e52b-2026-uge-8-min-koebmand/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Spar": "https://spar.dayli.eu/9733-2026-uge-8-spar/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "365": "https://coop-365.dayli.eu/9ec8-2026-uge-7-365-discount/feed.json?session_id=8d218c17-a144-41ca-b999-7f69b7f7a251&operating_system_version=unknown&application_version=web_version&device=web&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
}

# MEDIUM RESOLUTION - Higher quality images!
PRODUCT_IMAGE_SIZE = (300, 300)  # Medium resolution
IMAGE_QUALITY = 75  # Good quality
REQUEST_TIMEOUT = 20

os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/aviser_products.xlsx"

# ---------------- HELPERS ----------------

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'[\x00-\x1F]', '', str(text)).strip()

def image_to_base64(img):
    """Convert PIL image directly to base64 (no disk needed)"""
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=IMAGE_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

def calculate_remaining_days(data):
    try:
        offers = data.get("variables", {}).get("offers", {})
        expiration = offers.get("expiration")
        if not expiration:
            return ""
        exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
        today = date.today()
        return max((exp_date - today).days, 0)
    except:
        return ""

# ---------------- EXCEL SETUP ----------------

wb = Workbook()
ws = wb.active
ws.title = "Offers"
ws.append(["title", "price", "category", "store", "remaining_days", "image_base64"])

total_products = 0
print("🐝 Aviser Scraper - FULL CATALOG MODE")
print("=" * 60)

# ---------------- SCRAPER ----------------

for store, url in CATALOGS.items():
    print(f"\n⏳ Processing {store}...")
    store_count = 0

    try:
        print(f"   Fetching catalog...")
        data = requests.get(url, timeout=REQUEST_TIMEOUT).json()
    except Exception as e:
        print(f"   ❌ Failed to fetch {store}: {e}")
        continue

    remaining_days = calculate_remaining_days(data)
    print(f"   Offer expires in: {remaining_days if remaining_days else 'N/A'} days")

    for content in data.get("content", []):
        for pageflip in content.get("content_items", []):
            for page in pageflip.get("content_items", []):

                image_url = page.get("overrides", {}).get("image_url")
                if not image_url:
                    continue

                try:
                    page_img = Image.open(
                        BytesIO(requests.get(image_url, timeout=REQUEST_TIMEOUT).content)
                    ).convert("RGB")
                except Exception as e:
                    print(f"   ⚠️  Failed to load page image")
                    continue

                for zone in page.get("content_items", []):
                    o = zone.get("overrides", {})

                    title = clean_text(o.get("title"))
                    price = clean_text(o.get("price"))
                    category = clean_text(o.get("category"))

                    if not title or not price:
                        continue

                    try:
                        x = int(o.get("x", 0))
                        y = int(o.get("y", 0))
                        w = int(o.get("width", 0))
                        h = int(o.get("height", 0))
                    except:
                        continue

                    if w <= 0 or h <= 0:
                        continue

                    try:
                        # Crop and resize to MEDIUM resolution
                        cropped = page_img.crop((x, y, x + w, y + h)).resize(PRODUCT_IMAGE_SIZE)
                        img_b64 = image_to_base64(cropped)
                    except:
                        img_b64 = ""

                    ws.append([title, price, category, store, remaining_days, img_b64])
                    store_count += 1
                    
                    # Progress indicator
                    if store_count % 50 == 0:
                        print(f"   ... {store_count} products")

    print(f"   ✅ {store}: {store_count} products")
    total_products += store_count

# ---------------- SAVE ----------------

print(f"\n💾 Saving to {OUTPUT_FILE}...")
wb.save(OUTPUT_FILE)

print(f"\n{'=' * 60}")
print(f"🐝 Aviser Scraper Complete!")
print(f"{'=' * 60}")
print(f"Total Products: {total_products}")
print(f"Stores: {len(CATALOGS)}")
print(f"Image Size: {PRODUCT_IMAGE_SIZE[0]}x{PRODUCT_IMAGE_SIZE[1]}px")
print(f"Image Quality: {IMAGE_QUALITY}%")
print(f"Output File: {OUTPUT_FILE}")
print(f"{'=' * 60}")
