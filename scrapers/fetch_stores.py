"""
fetch_stores.py
---------------
Builds data/stores.json — every supermarket in Denmark belonging to a chain
Beelee tracks, with coordinates and opening hours.

Source: OpenStreetMap via the Overpass API. Free, no API key, ODbL licensed
(attribution required — see ATTRIBUTION below).

Runs weekly rather than nightly: shops don't move.

    python scrapers/fetch_stores.py

Install: pip install requests
"""

import os, json, time, re
import requests

# ─────────────────── CONFIG ───────────────────
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, "data") if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, "stores.json")

# OSM brand/name text -> the store name Beelee uses in products.xlsx.
# Order matters: the first pattern that matches wins, so put the more
# specific chains first (SuperBrugsen before Brugsen).
CHAIN_PATTERNS = [
    (r"rema\s*1000",              "Rema1000"),
    (r"\bnetto\b",                "Netto"),
    (r"\blidl\b",                 "Lidl"),
    (r"f[øo]tex",                 "Føtex"),
    (r"\bbilka\b",                "Bilka"),
    (r"\bmeny\b",                 "Meny"),
    (r"superbrugsen",             "SuperBrugsen & Kvickly"),
    (r"kvickly",                  "SuperBrugsen & Kvickly"),
    (r"d[ae]gli.?brugsen",        "Brugsen"),
    (r"\bbrugsen\b",              "Brugsen"),
    (r"365\s*discount|coop\s*365","365"),
    (r"\bspar\b",                 "Spar"),
    (r"min\s*k[øo]bmand",         "Min Kobmand"),
]

# Overpass mirrors — tried in order, they rate-limit and go down often
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

TIMEOUT = 180
ATTRIBUTION = "© OpenStreetMap contributors, ODbL"
# ──────────────────────────────────────────────

# Every shop in Denmark that looks like a supermarket. We filter to our
# chains in Python rather than in the query — the brand tag is missing on
# plenty of nodes, so we need the name as a fallback.
QUERY = """
[out:json][timeout:170];
area["ISO3166-1"="DK"][admin_level=2]->.dk;
(
  nwr["shop"="supermarket"](area.dk);
  nwr["shop"="convenience"]["brand"](area.dk);
);
out center tags;
"""


def match_chain(tags):
    """Map an OSM element to one of Beelee's store names, or None."""
    haystack = " ".join(filter(None, [
        tags.get("brand", ""),
        tags.get("name", ""),
        tags.get("operator", ""),
    ])).lower()
    for pattern, store in CHAIN_PATTERNS:
        if re.search(pattern, haystack):
            return store
    return None


def build_address(tags):
    street = tags.get("addr:street", "")
    number = tags.get("addr:housenumber", "")
    city   = tags.get("addr:city", "")
    post   = tags.get("addr:postcode", "")
    line1  = " ".join(filter(None, [street, number]))
    line2  = " ".join(filter(None, [post, city]))
    return ", ".join(filter(None, [line1, line2])) or None


def fetch():
    last_error = None
    for url in ENDPOINTS:
        print(f"  Trying {url.split('/')[2]}...")
        try:
            r = requests.post(url, data={"data": QUERY}, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"    failed: {e}")
            last_error = e
            time.sleep(3)
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")


# ──────────────────────────────────────────────
print("📍 Beelee store locations — OpenStreetMap")
print("=" * 60)
print("\n🌐 Querying Overpass (this takes 30-90 seconds)...")

data = fetch()
elements = data.get("elements", [])
print(f"  {len(elements)} supermarkets returned for Denmark")

stores = []
skipped = 0

for el in elements:
    tags = el.get("tags") or {}
    chain = match_chain(tags)
    if not chain:
        skipped += 1
        continue

    # Nodes carry lat/lon directly; ways and relations carry a "center"
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    if lat is None or lon is None:
        continue

    stores.append({
        "id":      f"{el.get('type','n')}{el.get('id')}",
        "chain":   chain,
        "name":    tags.get("name") or chain,
        "lat":     round(float(lat), 6),
        "lon":     round(float(lon), 6),
        "address": build_address(tags),
        "hours":   tags.get("opening_hours"),
    })

# Two OSM entries occasionally describe the same shop (a node inside a way).
# Collapse anything within ~25 m of a same-chain store we already have.
deduped = []
for s in stores:
    dup = False
    for t in deduped:
        if t["chain"] == s["chain"] \
           and abs(t["lat"] - s["lat"]) < 0.00025 \
           and abs(t["lon"] - s["lon"]) < 0.00040:
            dup = True
            break
    if not dup:
        deduped.append(s)

payload = {
    "attribution": ATTRIBUTION,
    "generated":   time.strftime("%Y-%m-%d"),
    "count":       len(deduped),
    "stores":      deduped,
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

kb = os.path.getsize(OUTPUT_FILE) / 1024

print(f"\n{'=' * 60}")
print(f"📍 Done!")
print(f"{'=' * 60}")
print(f"Stores matched:   {len(deduped)}")
print(f"Duplicates merged:{len(stores) - len(deduped)}")
print(f"Not our chains:   {skipped}")
print(f"Output:           {OUTPUT_FILE}  ({kb:.0f} KB)")

print(f"\n📊 Per chain:")
counts = {}
for s in deduped:
    counts[s["chain"]] = counts.get(s["chain"], 0) + 1
for chain, n in sorted(counts.items(), key=lambda kv: -kv[1]):
    with_hours = sum(1 for s in deduped if s["chain"] == chain and s["hours"])
    print(f"   {chain}: {n}  ({with_hours} with opening hours)")

missing = [c for _, c in CHAIN_PATTERNS if c not in counts]
if missing:
    print(f"\n⚠️  No stores found for: {', '.join(sorted(set(missing)))}")
    print("   Either the chain isn't tagged in OSM, or the pattern needs work.")
