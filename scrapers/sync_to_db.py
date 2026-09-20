"""
sync_to_db.py
-------------
Pushes the nightly scrape into Postgres so the consensus view has a baseline
and the database is never empty.

  * products.xlsx  -> products   (upsert)
  * stores.json    -> stores     (upsert)
  * today's prices -> price_observations  (source='scraper')

Run after estimate_nutriscore.py:

    DATABASE_URL=postgres://... python scrapers/sync_to_db.py

Install: pip install psycopg2-binary pandas openpyxl
"""

import os, json, sys
from datetime import date

import pandas as pd

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("❌ pip install psycopg2-binary")
    raise SystemExit(1)

from product_key import product_key

# ─────────────────── CONFIG ───────────────────
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, "data") if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, "data")

PRODUCTS_FILE = os.path.join(DATA_DIR, "products.xlsx")
STORES_FILE   = os.path.join(DATA_DIR, "stores.json")
BATCH         = 500
# ──────────────────────────────────────────────

DSN = os.environ.get("DATABASE_URL")
if not DSN:
    print("❌ DATABASE_URL not set")
    raise SystemExit(1)

print("🗄️  Sync scrape → Postgres")
print("=" * 60)

conn = psycopg2.connect(DSN, sslmode="require" if "localhost" not in DSN else "prefer")
conn.autocommit = False
cur = conn.cursor()


# ── Stores ────────────────────────────────────
if os.path.exists(STORES_FILE):
    payload = json.load(open(STORES_FILE, encoding="utf-8"))
    rows = [
        (s["id"], s["chain"], s["name"], s["lat"], s["lon"],
         s.get("address"), s.get("hours"))
        for s in payload.get("stores", [])
    ]
    execute_values(cur, """
        INSERT INTO stores (id, chain, name, lat, lon, address, hours)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            chain = EXCLUDED.chain, name = EXCLUDED.name,
            lat = EXCLUDED.lat, lon = EXCLUDED.lon,
            address = EXCLUDED.address, hours = EXCLUDED.hours,
            updated_at = now()
    """, rows, page_size=BATCH)
    print(f"  stores:   {len(rows)} upserted")
else:
    print(f"  stores:   skipped ({STORES_FILE} not found)")


# ── Products ──────────────────────────────────
if not os.path.exists(PRODUCTS_FILE):
    print(f"❌ {PRODUCTS_FILE} not found — run the merge script first")
    raise SystemExit(1)

df = pd.read_excel(PRODUCTS_FILE)
print(f"\n  loaded {len(df)} rows from products.xlsx")

if "product_key" not in df.columns:
    print("  product_key missing — computing it now")
    bc = df["barcode"] if "barcode" in df.columns else [None] * len(df)
    df["product_key"] = [product_key(t, b) for t, b in zip(df["title"], bc)]

# Excel turns barcodes into floats; normalise back to digits
def clean_barcode(v):
    if pd.isna(v):
        return None
    s = str(v).replace(".0", "").strip()
    return s if s.isdigit() and len(s) >= 8 else None

df["barcode"] = df["barcode"].map(clean_barcode) if "barcode" in df.columns else None

# One row per product_key — the catalogue is keyed by product, not by listing
prod = df.drop_duplicates(subset=["product_key"], keep="first")
prod_rows = [
    (r["product_key"], r.get("barcode"), str(r["title"])[:500],
     r.get("category"), r.get("subcategory"))
    for _, r in prod.iterrows()
]
execute_values(cur, """
    INSERT INTO products (product_key, barcode, title, category, subcategory)
    VALUES %s
    ON CONFLICT (product_key) DO UPDATE SET
        barcode = COALESCE(EXCLUDED.barcode, products.barcode),
        title = EXCLUDED.title,
        category = EXCLUDED.category,
        subcategory = EXCLUDED.subcategory,
        updated_at = now()
""", prod_rows, page_size=BATCH)
print(f"  products: {len(prod_rows)} upserted")


# ── Scraped prices as observations ────────────
# One per (product, chain) per day. Re-running the same day is a no-op.
today = date.today()
seen = set()
obs_rows = []
for _, r in df.iterrows():
    key = (r["product_key"], r.get("store"))
    if key in seen or pd.isna(r.get("price")) or pd.isna(r.get("store")):
        continue
    seen.add(key)
    obs_rows.append((r["product_key"], r["store"], round(float(r["price"]), 2), today))

cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS obs_scraper_daily_uidx
        ON price_observations (product_key, chain, observed_at)
        WHERE source = 'scraper'
""")

execute_values(cur, """
    INSERT INTO price_observations
        (product_key, chain, price, source, observed_at)
    VALUES %s
    ON CONFLICT DO NOTHING
""", [(k, c, p, d) for k, c, p, d in obs_rows], page_size=BATCH,
    template="(%s, %s, %s, 'scraper', %s)")

conn.commit()

cur.execute("SELECT COUNT(*) FROM price_observations")
total_obs = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM price_observations WHERE source <> 'scraper'")
user_obs = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM current_prices")
current = cur.fetchone()[0]

print(f"  prices:   {len(obs_rows)} scraped observations for {today}")
print(f"\n{'=' * 60}")
print(f"🗄️  Done")
print(f"{'=' * 60}")
print(f"Observations total:   {total_obs}")
print(f"  from users:         {user_obs}")
print(f"Products with a price:{current}")

cur.close()
conn.close()
