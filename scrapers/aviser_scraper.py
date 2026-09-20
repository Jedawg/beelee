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
    "Netto": "https://netto.dayli.eu/2856-netto-au39-2026/feed.json?session_id=bcaf307c-db61-4ac7-b56a-74f4613a93f4&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Lidl": "https://lidl.dayli.eu/a17f-lidl-avis-uge-39/feed.json?session_id=bcaf307c-db61-4ac7-b56a-74f4613a93f4&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Rema1000": "https://rema1000.aviou.io/4e4c-2026-uge-39-rema-1000/feed.json?session_id=bcaf307c-db61-4ac7-b56a-74f4613a93f4&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Brugsen": "https://brugsen.dayli.se/9c9f-2026-uge-37-brugsen/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Bilka": "https://bilka.dayli.se/497c-2026-uge-39-bilka-food/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Føtex": "https://foetex.dayli.eu/3e0e-2026-uge-39-foetex/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "SuperBrugsen & Kvickly": "https://superbrugsen.dayli.eu/aded-2026-uge-38-superbrugsen/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Meny": "https://meny.dayli.eu/f84e-2026-uge-39-meny/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Min Kobmand": "https://min-koebmand.dayli.eu/9c9f-2026-uge-39-min-koebmand/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "Spar": "https://spar.dayli.eu/bb39-2026-uge-39-spar/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
    "365": "https://coop-365.dayli.eu/77c7-2026-uge-38-365-discount/feed.json?session_id=de4a2630-26be-40f5-9179-37eb05e923c2&operating_system_version=macintosh&application_version=web_version&device=embed&mtuuid=ea98e203-7566-4275-b388-2c86b7be90e3",
}

# MEDIUM RESOLUTION - Higher quality images!
PRODUCT_IMAGE_SIZE = (300, 300)  # Medium resolution
IMAGE_QUALITY = 75  # Good quality
REQUEST_TIMEOUT = 20

# Same path handling as the other scrapers: repo root in Actions,
# next to the script when run locally.
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, "data") if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, "aviser_products.xlsx")

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
DEAD_FEEDS = []   # stores whose weekly URL has expired
EMPTY_FEEDS = []  # stores that returned a feed but no products
print("🐝 Aviser Scraper - FULL CATALOG MODE")
print("=" * 60)

# ---------------- SCRAPER ----------------

for store, url in CATALOGS.items():
    print(f"\n⏳ Processing {store}...")
    store_count = 0

    try:
        print(f"   Fetching catalog...")
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            raise ValueError("404 — the weekly catalog URL has expired")
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"   ❌ Failed to fetch {store}: {e}")
        DEAD_FEEDS.append((store, str(e)[:60]))
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

    if store_count == 0:
        print(f"   ⚠️  {store}: 0 products — feed loaded but contained nothing")
        EMPTY_FEEDS.append(store)
    else:
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

if DEAD_FEEDS or EMPTY_FEEDS:
    print()
    print("⚠️  CATALOG URLS NEED REFRESHING")
    print("   The URLs in CATALOGS have week numbers baked in (uge-37, au38…)")
    print("   and expire. Get fresh ones from each store's online avis.")
    for store, err in DEAD_FEEDS:
        print(f"   ✗ {store}: {err}")
    for store in EMPTY_FEEDS:
        print(f"   ∅ {store}: feed loaded but produced no products")

if total_products == 0:
    print("\n❌ No products at all — every catalog URL is stale.")
    raise SystemExit(1)
