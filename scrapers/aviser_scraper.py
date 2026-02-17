import os
import requests
from PIL import Image
from io import BytesIO
import re
import base64
from datetime import datetime, date
from openpyxl import Workbook

# ---------------- CONFIG ----------------

# ⚠️ UPDATE THESE URLS EACH WEEK with the latest catalog links!
CATALOGS = {
    "Netto": "https://netto.dayli.eu/f596-2026-nette-au08/feed.json",
    "Spar": "https://spar.dayli.eu/9733-2026-uge-8-spar/feed.json",
    "Min Kobmand": "https://min-koebmand.dayli.eu/e52b-2026-uge-8-min-koebmand/feed.json",
    # Add more stores as needed, but fewer = faster!
}

PRODUCT_IMAGE_SIZE = (100, 100)  # Smaller = faster
IMAGE_QUALITY = 70  # Lower = faster
REQUEST_TIMEOUT = 15  # Seconds before giving up

os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/aviser_products.xlsx"

# ---------------- HELPERS ----------------

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'[\x00-\x1F]', '', str(text)).strip()

def image_to_base64(img):
    """Convert PIL image to base64 (no disk)"""
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

# ---------------- SCRAPER ----------------

for store, url in CATALOGS.items():
    print(f"⏳ Processing {store}...")
    store_count = 0

    try:
        print(f"  Fetching catalog...")
        data = requests.get(url, timeout=REQUEST_TIMEOUT).json()
    except Exception as e:
        print(f"  ❌ Failed to fetch {store}: {e}")
        continue

    remaining_days = calculate_remaining_days(data)

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
                    print(f"  ⚠️  Failed to load page image: {e}")
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
                        cropped = page_img.crop((x, y, x + w, y + h)).resize(PRODUCT_IMAGE_SIZE)
                        img_b64 = image_to_base64(cropped)
                    except:
                        img_b64 = ""

                    ws.append([title, price, category, store, remaining_days, img_b64])
                    store_count += 1

    print(f"  ✅ {store}: {store_count} products")
    total_products += store_count

# ---------------- SAVE ----------------

wb.save(OUTPUT_FILE)
print(f"\n🐝 Aviser scraper done! {total_products} products saved to {OUTPUT_FILE}")
