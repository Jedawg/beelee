import requests
import time
import base64
from io import BytesIO
from datetime import datetime
import pandas as pd
from PIL import Image
import os

# ─────────────────── CONFIG ───────────────────
BASE_URL        = "https://api.digital.rema1000.dk/api/search/products"
DEPARTMENTS_URL = "https://api.digital.rema1000.dk/api/departments"
PER_PAGE        = 200
SORT            = "-popularity"
IMAGE_SIZE      = (300, 300)
IMAGE_QUALITY   = 75

# Save next to the script locally, but to repo root in GitHub Actions
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get('GITHUB_WORKSPACE')
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, 'data') if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, "rema1000_products.xlsx")
# ──────────────────────────────────────────────

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":          "application/json",
    "Accept-Language": "da-DK,da;q=0.9",
    "Referer":         "https://shop.rema1000.dk/",
    "Origin":          "https://shop.rema1000.dk",
}

print("🐝 Rema1000 Scraper — api.digital.rema1000.dk")
print("=" * 60)


# ──────────────────────────────────────────────
# Fetch one page
# ──────────────────────────────────────────────
def fetch_page(page, department_id=None):
    params = {
        "query":    "",
        "page":     page,
        "per_page": PER_PAGE,
        "sort":     SORT,
    }
    if department_id is not None:
        params["filter[departments]"] = department_id
    r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────
# Parse pagination from response
# Response shape: { "data": [...], "meta": { "pagination": { "last_page": 20, "total": 3830 } } }
# ──────────────────────────────────────────────
def parse_pagination(data):
    if isinstance(data, list):
        return data, len(data), 1

    items = (
        data.get("data")
        or data.get("products")
        or data.get("results")
        or []
    )

    # Pagination is nested: meta → pagination
    meta       = data.get("meta") or {}
    pagination = meta.get("pagination") or meta

    total      = int(pagination.get("total")     or len(items) or 0)
    last_page  = int(pagination.get("last_page") or 1)

    return items, total, last_page


# ──────────────────────────────────────────────
# Parse one product
# ──────────────────────────────────────────────
def parse_product(item):
    # Price from prices[0].price
    prices = item.get("prices") or []
    price  = None
    remaining_days = None

    if prices:
        p0    = prices[0]
        price = p0.get("price")

        # If ending_at is not year 2099, it's a limited-time offer
        ending_at = p0.get("ending_at") or ""
        if ending_at and not ending_at.startswith("2099"):
            try:
                exp = datetime.strptime(ending_at[:10], "%Y-%m-%d")
                remaining_days = max(0, (exp - datetime.now()).days)
            except Exception:
                pass

    try:
        price = float(price) if price is not None else None
    except (TypeError, ValueError):
        price = None

    # Category: category.name → department.name → "Andet"
    cat = None
    raw_cat  = item.get("category")  or {}
    raw_dept = item.get("department") or {}
    if isinstance(raw_cat, dict):
        cat = raw_cat.get("name")
    if not cat and isinstance(raw_dept, dict):
        cat = raw_dept.get("name")
    cat = cat or "Andet"

    # Image: images[0].medium (webp — PIL handles it)
    image_url = None
    images = item.get("images") or []
    if images and isinstance(images[0], dict):
        image_url = (
            images[0].get("medium")
            or images[0].get("large")
            or images[0].get("small")
        )

    # ── Barcode: the longest EAN-13 in the list is the real product barcode ──
    barcode = None
    codes = [str(b) for b in (item.get("barcodes") or []) if str(b).isdigit()]
    ean13 = [b for b in codes if len(b) == 13]
    if ean13:
        barcode = ean13[0]
    elif codes:
        barcode = max(codes, key=len)

    # ── Ingredients: Rema1000 exposes these as "declaration" ──
    ingredients = (item.get("declaration") or "").strip() or None

    return {
        "title":          item.get("name") or "Ukendt",
        "price":          price,
        "category":       cat,
        "store":          "Rema1000",
        "image_url":      image_url,
        "remaining_days": remaining_days,
        "barcode":        barcode,
        "ingredients":    ingredients,
    }


# ──────────────────────────────────────────────
# Collect all products (paginate all 20 pages)
# ──────────────────────────────────────────────
def collect_all_products():
    seen   = set()
    result = []

    print("\n📦 Fetching all products (empty query = full catalogue)...")

    # Page 1
    first = fetch_page(page=1)
    items, total, last_page = parse_pagination(first)

    print(f"  Total products: {total}  Pages: {last_page}")

    if not items:
        print("  ❌ No products on page 1 — check the API URL")
        return result

    for item in items:
        p = parse_product(item)
        k = p["title"].lower().strip()
        if k not in seen:
            seen.add(k)
            result.append(p)
    print(f"  Page  1/{last_page}: {len(result)} products")

    # Pages 2 → last_page
    for page in range(2, last_page + 1):
        try:
            data  = fetch_page(page=page)
            items, _, _ = parse_pagination(data)
            if not items:
                print(f"  Page {page:2}/{last_page}: empty — stopping")
                break
            added = 0
            for item in items:
                p = parse_product(item)
                k = p["title"].lower().strip()
                if k not in seen:
                    seen.add(k)
                    result.append(p)
                    added += 1
            print(f"  Page {page:2}/{last_page}: +{added:3}  (total: {len(result)})")
            time.sleep(0.25)
        except Exception as e:
            print(f"  ⚠️  Page {page} failed: {e} — stopping")
            break

    return result


# ──────────────────────────────────────────────
# Download images (webp → JPEG base64)
# ──────────────────────────────────────────────
def download_images(products):
    print(f"\n⏳ Downloading {len(products)} images ({IMAGE_SIZE[0]}×{IMAGE_SIZE[1]}px)...")
    ok = fail = 0

    for i, p in enumerate(products):
        url = p.pop("image_url", None)

        if not url:
            p["image_base64"] = None
            fail += 1
            continue

        try:
            r   = requests.get(url, timeout=15, headers=HEADERS)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.thumbnail(IMAGE_SIZE, Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=IMAGE_QUALITY)
            p["image_base64"] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
            ok += 1
        except Exception as e:
            p["image_base64"] = None
            fail += 1

        if (i + 1) % 200 == 0:
            pct = (i + 1) / len(products) * 100
            print(f"  {i+1}/{len(products)} ({pct:.0f}%)  ✅ {ok}  ❌ {fail}")

    print(f"✅ Images: {ok} ok  {fail} failed")
    return products


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────
products = collect_all_products()
print(f"\n✅ Collected {len(products)} unique products")

products = download_images(products)

df = pd.DataFrame(
    products,
    columns=["title", "price", "category", "store", "image_base64", "remaining_days", "barcode", "ingredients"]
)
df = df.dropna(subset=["title", "price"])
df.to_excel(OUTPUT_FILE, index=False)

size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)

print(f"\n{'=' * 60}")
print(f"🐝 Rema1000 Scraper Complete!")
print(f"{'=' * 60}")
print(f"Products saved:   {len(df)}")
print(f"Output file:      {OUTPUT_FILE}")
print(f"File size:        {size_mb:.2f} MB")
print(f"{'=' * 60}")

# Category breakdown
print("\n📊 Category breakdown:")
for cat, count in df["category"].value_counts().head(15).items():
    print(f"   {cat}: {count}")
