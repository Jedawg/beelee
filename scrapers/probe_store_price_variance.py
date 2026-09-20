"""
probe_store_price_variance.py
-----------------------------
Answers one question before you build anything: do prices actually differ
between branches of the same chain?

Scrapes the same category from several venues of one brand on Wolt, then
reports how many products differ in price and by how much.

    python scrapers/probe_store_price_variance.py

If variance is ~0%, per-store pricing is a fiction for that chain and
geofencing buys you nothing. If it's meaningful, it's worth building.

Install: pip install requests beautifulsoup4
"""

import re, json, time, os
from collections import defaultdict
import requests
from bs4 import BeautifulSoup

# ─────────────────── CONFIG ───────────────────
BRAND = "meny"          # brand slug on Wolt
CITY  = "copenhagen"
MAX_VENUES     = 4      # how many branches to compare
MAX_CATEGORIES = 3      # categories per venue — keep it small, this is a probe
DELAY = 0.6
# ──────────────────────────────────────────────

BASE = "https://wolt.com"
sess = requests.Session()
sess.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    "Referer": f"{BASE}/da/dnk/{CITY}",
})


def get_html(url):
    try:
        r = sess.get(url, timeout=25)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    fetch failed: {e}")
        return None


def find_products(obj, out, depth=0):
    """Walk embedded JSON for objects that look like Wolt products."""
    if depth > 9:
        return
    if isinstance(obj, list):
        for v in obj:
            find_products(v, out, depth + 1)
    elif isinstance(obj, dict):
        name  = obj.get("name")
        price = obj.get("original_price") or obj.get("price") or obj.get("baseprice")
        if isinstance(name, str) and isinstance(price, (int, float)) and obj.get("images"):
            out[name.strip().upper()] = round(float(price) / 100, 2)
        for v in obj.values():
            find_products(v, out, depth + 1)


def scrape_page(url):
    html = get_html(url)
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    found = {}

    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            find_products(json.loads(tag.string), found)
        except Exception:
            pass

    if not found:
        # Fall back to pulling product objects straight out of the raw HTML
        for m in re.finditer(r'"id"\s*:\s*"([a-f0-9]{24})"', html):
            pos = m.start()
            start, depth = pos, 0
            for i in range(pos, max(pos - 6000, 0), -1):
                if html[i] == "}":
                    depth += 1
                elif html[i] == "{":
                    if depth == 0:
                        start = i
                        break
                    depth -= 1
            depth, end = 0, pos
            for i in range(pos, min(pos + 6000, len(html))):
                if html[i] == "{":
                    depth += 1
                elif html[i] == "}":
                    if depth == 0:
                        end = i + 1
                        break
                    depth -= 1
            try:
                find_products(json.loads(html[start:end]), found)
            except Exception:
                pass
    return found


def discover_venues(brand):
    print(f"🔍 Finding {brand} venues in {CITY}...")
    html = get_html(f"{BASE}/en/dnk/{CITY}/brand/{brand}")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen, venues = set(), []
    for a in soup.find_all("a", href=re.compile(r"/venue/[^/\"?#]+")):
        m = re.search(r"/venue/([^/\"?#]+)", a["href"])
        if not m:
            continue
        slug = m.group(1)
        if slug in seen or brand.replace("-", "") not in slug.replace("-", ""):
            continue
        seen.add(slug)
        venues.append((slug, a.get_text(strip=True) or slug))
    print(f"   found {len(venues)}")
    return venues


def category_urls(slug, limit):
    html = get_html(f"{BASE}/da/dnk/{CITY}/venue/{slug}/")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    urls, seen = [], set()
    for a in soup.find_all("a", href=re.compile(rf"/venue/{re.escape(slug)}/items/")):
        u = BASE + a["href"].split("?")[0]
        if u not in seen and "itemid" not in u:
            seen.add(u)
            urls.append(u)
    return urls[:limit]


# ──────────────────────────────────────────────
print("🔬 Per-branch price variance probe")
print("=" * 62)

venues = discover_venues(BRAND)[:MAX_VENUES]
if len(venues) < 2:
    print("\n❌ Need at least 2 venues to compare. Try another brand or city.")
    raise SystemExit(1)

by_venue = {}
for slug, label in venues:
    print(f"\n🏪 {label}  ({slug})")
    prices = {}
    for url in category_urls(slug, MAX_CATEGORIES):
        time.sleep(DELAY)
        prices.update(scrape_page(url))
    print(f"   {len(prices)} products")
    if prices:
        by_venue[label] = prices

if len(by_venue) < 2:
    print("\n❌ Could not scrape 2+ venues.")
    raise SystemExit(1)

# Compare only products present in every venue — anything else is a
# range difference, not a price difference
labels = list(by_venue)
common = set(by_venue[labels[0]])
for l in labels[1:]:
    common &= set(by_venue[l])

print(f"\n{'=' * 62}")
print(f"🔬 Result — {len(labels)} branches, {len(common)} products in common")
print(f"{'=' * 62}")

if not common:
    print("No overlapping products. Increase MAX_CATEGORIES and retry.")
    raise SystemExit(0)

same, diff, examples = 0, 0, []
for name in common:
    vals = [by_venue[l][name] for l in labels]
    if max(vals) - min(vals) < 0.01:
        same += 1
    else:
        diff += 1
        spread = max(vals) - min(vals)
        pct = spread / min(vals) * 100 if min(vals) else 0
        examples.append((spread, pct, name, vals))

pct_diff = diff / len(common) * 100
print(f"Identical price:  {same:5}  ({100 - pct_diff:.1f}%)")
print(f"Different price:  {diff:5}  ({pct_diff:.1f}%)")

if examples:
    examples.sort(reverse=True)
    print(f"\nBiggest differences:")
    print(f"   {'Product':<40} " + " ".join(f"{l[:12]:>12}" for l in labels))
    for spread, pct, name, vals in examples[:12]:
        print(f"   {name[:40]:<40} " + " ".join(f"{v:>12.2f}" for v in vals)
              + f"   +{spread:.2f} kr ({pct:.0f}%)")

print(f"\n{'─' * 62}")
if pct_diff < 2:
    print("VERDICT: prices are effectively national for this chain.")
    print("Per-store geolocation would show identical numbers — skip it.")
elif pct_diff < 15:
    print("VERDICT: mostly national with some local variation.")
    print("Worth showing the nearest branch, but don't build the whole feature")
    print("around it — most products will look the same either way.")
else:
    print("VERDICT: prices genuinely vary by branch.")
    print("Per-store data is worth scraping, and geofencing has something to show.")
print(f"{'─' * 62}")
