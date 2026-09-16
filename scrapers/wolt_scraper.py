"""
wolt_scraper.py — extracts products from JSON embedded in Wolt HTML pages
Install: pip install requests beautifulsoup4 pandas pillow openpyxl
"""

import re, json, base64, time, os
from io import BytesIO
import requests
from bs4 import BeautifulSoup
import pandas as pd
from PIL import Image

# ─────────────────── CONFIG ───────────────────
# Brands to scrape — maps brand slug → store display name
# The scraper will auto-discover all venues and pick the best one
BRANDS = {
    "meny": "Meny",
    # Add more brands:
    # "irma": "Irma",
    # "lidl": "Lidl",
}

# How many venues to scrape per brand (1 = fastest, prices are same across stores)
VENUES_PER_BRAND = 1

IMAGE_SIZE    = (300, 300)
IMAGE_QUALITY = 75
DELAY         = 0.5

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get('GITHUB_WORKSPACE')
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, 'data') if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, "wolt_products.xlsx")

# Danish cities to search for venues (add more if needed)
CITIES = ["copenhagen", "aarhus", "odense", "aalborg", "herning"]
# ──────────────────────────────────────────────

BASE = "https://wolt.com"


# ── Excel-safe text ─────────────────────────────────────────────────────
# openpyxl refuses control characters, and rejects the ENTIRE workbook if
# one cell contains one. Some product descriptions carry stray control
# bytes, so scrub every string before writing.
ILLEGAL_XLSX = re.compile(r"[\000-\010\013\014\016-\037]")

def xlsx_safe(v, limit=32000):
    """Strip characters Excel can't store. Returns v unchanged if not a string."""
    if not isinstance(v, str):
        return v
    v = ILLEGAL_XLSX.sub("", v)
    v = v.replace("\r\n", "\n").replace("\r", "\n").strip()
    # Excel's hard cell limit is 32,767 characters
    return v[:limit] if len(v) > limit else v

sess = requests.Session()
sess.headers.update({
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    "Referer":         "https://wolt.com/da/dnk/copenhagen",
})


# ──────────────────────────────────────────────
# Extract products recursively from any JSON structure
# ──────────────────────────────────────────────
def find_products_in_json(obj, store, cat, seen, depth=0):
    """Walk any JSON structure, collect dicts that look like products."""
    if depth > 10:
        return []
    results = []

    if isinstance(obj, list):
        for item in obj:
            results.extend(find_products_in_json(item, store, cat, seen, depth+1))

    elif isinstance(obj, dict):
        # Does this dict look like a Wolt product?
        # Key indicators: has "name" (string or list), and "original_price" or "price"
        name_val  = obj.get("name")
        price_val = obj.get("original_price") or obj.get("price")
        has_image = bool(obj.get("images") or obj.get("image"))

        if name_val and price_val and has_image:
            # Extract name
            if isinstance(name_val, str):
                title = name_val
            elif isinstance(name_val, list):
                by_lang = {v.get("lang"): v.get("value") for v in name_val if isinstance(v, dict)}
                title = by_lang.get("da") or by_lang.get("en") or next(iter(by_lang.values()), "")
            else:
                title = str(name_val)

            if not title or len(title) < 2:
                pass
            else:
                # Extract price (Wolt stores prices in øre — divide by 100)
                try:
                    price = round(float(price_val) / 100, 2)
                except (TypeError, ValueError):
                    price = None

                # Extract image
                image_url = None
                images = obj.get("images") or []
                if isinstance(images, list) and images:
                    img = images[0]
                    image_url = img.get("url") if isinstance(img, dict) else None
                elif isinstance(obj.get("image"), dict):
                    image_url = obj["image"].get("url")

                # Deduplicate
                key = f"{title}|{price}"
                if price and key not in seen:
                    seen.add(key)
                    bc = obj.get("barcode_gtin") or obj.get("barcode")
                    bc = str(bc).lstrip("0") if bc else None
                    results.append({
                        "title":       title,
                        "price":       price,
                        "category":    cat,
                        "store":       store,
                        "image_url":   image_url,
                        "barcode":     bc,
                        "ingredients": (obj.get("description") or "").strip() or None,
                    })
        else:
            # Recurse into values
            for v in obj.values():
                results.extend(find_products_in_json(v, store, cat, seen, depth+1))

    return results


# ──────────────────────────────────────────────
# Fetch page and extract embedded JSON data
# ──────────────────────────────────────────────
def fetch_and_parse(url, store, cat, seen):
    """Fetch a Wolt page and extract all products from embedded JSON."""
    try:
        r = sess.get(url, timeout=20)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"     ⚠️  Fetch failed: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    products = []

    # ── Strategy 1: __NEXT_DATA__ script tag (Next.js) ──
    next_tag = soup.find("script", id="__NEXT_DATA__")
    if next_tag and next_tag.string:
        try:
            data = json.loads(next_tag.string)
            products = find_products_in_json(data, store, cat, seen)
            if products:
                print(f"        📄 __NEXT_DATA__: {len(products)} products")
                return products
        except Exception:
            pass

    # ── Strategy 2: any <script> tag containing "original_price" ──
    for script in soup.find_all("script"):
        content = script.string or ""
        if '"original_price"' not in content and "'original_price'" not in content:
            continue
        if len(content) < 500:
            continue

        # Try parsing as raw JSON
        try:
            data = json.loads(content)
            found = find_products_in_json(data, store, cat, seen)
            if found:
                products.extend(found)
                print(f"        📄 script JSON: {len(found)} products")
                continue
        except json.JSONDecodeError:
            pass

        # Try extracting JSON-like content (JS variable assignment)
        # e.g. window.__data = {...} or var data = {...}
        for pattern in [
            r'=\s*(\{.*?"original_price".*?\})\s*;',
            r'=\s*(\[.*?"original_price".*?\])\s*;',
        ]:
            m = re.search(pattern, content, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    found = find_products_in_json(data, store, cat, seen)
                    if found:
                        products.extend(found)
                        print(f"        📄 JS var: {len(found)} products")
                        break
                except Exception:
                    pass

    # ── Strategy 3: regex-extract product objects directly from raw HTML ──
    if not products:
        # Each product object has a 24-char hex "id" and "original_price"
        # Find all occurrences and extract the surrounding JSON object
        raw = html

        for m in re.finditer(r'"id"\s*:\s*"([a-f0-9]{24})"', raw):
            # Walk backwards to find the opening {
            pos = m.start()
            depth = 0
            start = pos
            for i in range(pos, max(pos - 5000, 0), -1):
                if raw[i] == '}': depth += 1
                elif raw[i] == '{':
                    if depth == 0:
                        start = i
                        break
                    depth -= 1

            # Walk forward to find the closing }
            depth = 0
            end = pos
            for i in range(pos, min(pos + 5000, len(raw))):
                if raw[i] == '{': depth += 1
                elif raw[i] == '}':
                    if depth == 0:
                        end = i + 1
                        break
                    depth -= 1

            obj_str = raw[start:end]
            if '"original_price"' not in obj_str and '"name"' not in obj_str:
                continue
            try:
                obj = json.loads(obj_str)
                found = find_products_in_json(obj, store, cat, seen)
                products.extend(found)
            except Exception:
                pass

        if products:
            print(f"        📄 regex extract: {len(products)} products")

    # ── Debug: if still nothing, show what script tags exist ──
    if not products:
        scripts = [(len(s.string or ""), s.string[:100] if s.string else "") for s in soup.find_all("script")]
        scripts.sort(reverse=True)
        print(f"        ⚠️  0 products. Largest scripts:")
        for size, preview in scripts[:5]:
            print(f"           {size} chars: {preview!r}")

    return products


# ──────────────────────────────────────────────
# Scrape a venue
# ──────────────────────────────────────────────
def get_category_links(slug):
    """Fetch the venue home page and extract all category URLs."""
    soup_home = BeautifulSoup(
        sess.get(f"{BASE}/da/dnk/copenhagen/venue/{slug}/", timeout=20).text,
        "html.parser"
    )
    pattern = re.compile(rf"/venue/{slug}/items/[^/\"?#]+")
    seen, links = set(), []
    for a in soup_home.find_all("a", href=pattern):
        href = a["href"].split("?")[0]
        if href not in seen:
            seen.add(href)
            links.append((BASE + href, a.get_text(strip=True)))
    return links


def scrape_venue(slug, store_name):
    print(f"\n  🏪 {store_name}  ({slug})")
    cat_links = get_category_links(slug)
    print(f"     📂 {len(cat_links)} categories")

    all_products = []
    seen = set()

    for cat_url, cat_name in cat_links:
        clean = re.sub(r'\s+\d+\s*$', '', cat_name).strip() or cat_name
        print(f"\n     📂 {clean}")
        time.sleep(DELAY)

        products = fetch_and_parse(cat_url, store_name, clean, seen)
        all_products.extend(products)
        print(f"        → {len(products)} new  (total: {len(all_products)})")

    return all_products


# ──────────────────────────────────────────────
# Image download
# ──────────────────────────────────────────────
def download_images(products):
    print(f"\n⏳ Downloading {len(products)} images...")
    ok = fail = 0
    for i, p in enumerate(products):
        url = p.pop("image_url", None)
        if not url:
            p["image_base64"] = None; fail += 1; continue
        try:
            r = sess.get(url, timeout=15); r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.thumbnail(IMAGE_SIZE, Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=IMAGE_QUALITY)
            p["image_base64"] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
            ok += 1
        except Exception:
            p["image_base64"] = None; fail += 1
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(products)}  ✅{ok}  ❌{fail}")
    print(f"✅ Images: {ok} ok  {fail} failed")
    return products


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────
def discover_venues(brand_slug, cities=CITIES):
    """
    Fetch brand pages across all cities to discover venue slugs.
    Returns list of (slug, display_name) tuples, best-rated first.
    """
    print(f"     🔍 Discovering venues for brand '{brand_slug}'...")
    seen   = set()
    venues = []  # (slug, name)

    for city in cities:
        url  = f"{BASE}/en/dnk/{city}/brand/{brand_slug}"
        try:
            r = sess.get(url, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            # Venue links pattern: /en/dnk/{city}/venue/{slug}
            for a in soup.find_all("a", href=re.compile(r"/venue/[^/\"?#]+")):
                href = a["href"]
                slug_match = re.search(r"/venue/([^/\"?#]+)", href)
                if not slug_match:
                    continue
                slug = slug_match.group(1)
                if slug in seen:
                    continue
                seen.add(slug)
                name = a.get_text(strip=True)
                # Skip generic/empty names
                if name and len(name) > 3 and brand_slug.replace("-", "").lower() in name.lower().replace(" ", ""):
                    venues.append((slug, name))

            time.sleep(0.3)
        except Exception:
            continue

    print(f"     ✅ Found {len(venues)} venues across {cities}")
    for slug, name in venues:
        print(f"        {slug}  →  {name}")
    return venues


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────
print("🐝 Wolt Scraper (embedded JSON)")
print("=" * 60)

all_products = []

for brand_slug, store_name in BRANDS.items():
    print(f"\n  🏪 {store_name}  (brand: {brand_slug})")

    # Auto-discover venues
    venues = discover_venues(brand_slug)

    if not venues:
        # Fallback to a hardcoded slug if discovery fails
        fallbacks = {
            "meny":  "meny-sterflled-torv",
            "irma":  "irma-nordhavn",
        }
        fb = fallbacks.get(brand_slug)
        if fb:
            venues = [(fb, store_name)]
            print(f"     ⚠️  Discovery failed — using fallback: {fb}")

    # Pick the best N venues (first = most popular/best rated on brand page)
    venues_to_scrape = venues[:VENUES_PER_BRAND]
    print(f"\n     📦 Scraping {len(venues_to_scrape)} venue(s)...")

    for venue_slug, venue_name in venues_to_scrape:
        products = scrape_venue(venue_slug, store_name)
        all_products.extend(products)
        print(f"     ✅ {len(products)} unique products from {venue_name}")

if not all_products:
    print("\n❌ No products.")
else:
    all_products = download_images(all_products)
    df = pd.DataFrame(
        [{k: xlsx_safe(v) for k, v in p.items()} for p in all_products],
        columns=["title","price","category","store","image_base64","barcode","ingredients"]
    ).dropna(subset=["title","price"])
    df.to_excel(OUTPUT_FILE, index=False)
    mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"\n{'='*60}")
    print(f"🐝 Done! {len(df)} products → {OUTPUT_FILE} ({mb:.1f} MB)")
    print(f"{'='*60}")
    print("\n📊 By store:");   [print(f"   {s}: {n}") for s,n in df["store"].value_counts().items()]
    print("\n📊 By category:"); [print(f"   {c}: {n}") for c,n in df["category"].value_counts().head(12).items()]
