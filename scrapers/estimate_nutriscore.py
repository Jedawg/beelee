"""
estimate_nutriscore.py
----------------------
Fills in Nutri-Score for products Open Food Facts didn't cover, by matching
them against the products that ARE covered.

How it works
------------
1. Products with an official OFF Nutri-Score become the reference corpus.
2. Every product is turned into a bag of weighted tokens drawn from its
   title, subcategory and ingredient list. Rare tokens ("skyr", "rugbrød")
   carry more weight than common ones ("dansk", "stk") via IDF.
3. For each unlabeled product we find the K most similar labeled products
   *within the same category*, and take a similarity-weighted vote on the
   grade.
4. If no neighbour is similar enough, we fall back to the median grade of
   its subcategory, then its category.

Every estimate is written with a source and a confidence so the app can
show it differently from an official score. Nothing overwrites an
official grade.

Run AFTER enrich_nutrition.py:
    python scrapers/estimate_nutriscore.py

Install: pip install pandas openpyxl
"""

import os, re, math
from collections import Counter, defaultdict
import pandas as pd

# ─────────────────── CONFIG ───────────────────
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, "data") if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, "data")
PRODUCTS_FILE    = os.path.join(DATA_DIR, "products.xlsx")

K_NEIGHBOURS   = 7      # how many labeled products vote
MIN_SIM        = 0.22   # below this a neighbour is ignored
MIN_CONF       = 0.30   # below this we fall back to the category median
MIN_CAT_SAMPLE = 5      # a category needs this many labeled items to vote
MIN_SUB_SAMPLE = 3      # a subcategory is a strong signal, needs fewer
NGRAM_WEIGHT   = 0.35   # how much char n-grams count vs whole words
# ──────────────────────────────────────────────

GRADES = ["A", "B", "C", "D", "E"]

# Words that say nothing about nutrition — packaging, origin, marketing
STOPWORDS = {
    "stk", "pk", "pakke", "pose", "bakke", "ds", "dåse", "flaske", "glas",
    "ca", "ml", "cl", "dl", "kg", "gr", "gram", "liter", "ltr",
    "dansk", "danske", "økologisk", "økologiske", "øko", "organic",
    "med", "uden", "og", "i", "til", "fra", "af", "på", "the", "and",
    "ny", "nye", "stor", "store", "lille", "mini", "maxi", "xl", "family",
    "tilbud", "spar", "vejl", "pris", "kun", "rema", "netto", "meny", "coop",
    "vare", "varer", "produkt", "frisk", "friske", "naturel", "original",
    "classic", "premium", "extra", "super", "plus", "light", "lidl",
}

# Weight per token source — ingredients are the most informative signal
FIELD_WEIGHT = {"title": 1.0, "subcategory": 0.8, "ingredients": 1.3}


def tokenize(text):
    """Danish-friendly tokenizer: lowercase, drop numbers/units/stopwords."""
    if not text or (isinstance(text, float) and math.isnan(text)):
        return []
    s = str(text).lower()
    s = re.sub(r"[^\wæøå]+", " ", s)
    out = []
    for w in s.split():
        if len(w) < 3:
            continue
        if w in STOPWORDS:
            continue
        if any(ch.isdigit() for ch in w):   # "500g", "2x200", "45"
            continue
        # crude Danish stemming: strip plural/definite endings
        for suf in ("erne", "ene", "er", "en", "et", "e"):
            if len(w) > 5 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


def char_ngrams(word, n=4):
    """Character n-grams — how we match Danish compound words.

    "kyllingebrystfilet" and "kyllingeinderfilet" share no whole token,
    but they share the n-grams kyll, ylli, llin, ling, ... and filet.
    """
    if len(word) <= n:
        return [word]
    return [word[i:i + n] for i in range(len(word) - n + 1)]


def build_bag(row):
    """Weighted token counts for one product: whole words + char n-grams."""
    bag = Counter()
    for field, weight in FIELD_WEIGHT.items():
        for tok in tokenize(row.get(field)):
            bag[tok] += weight                       # whole word, full weight
            for g in char_ngrams(tok):
                bag["#" + g] += weight * NGRAM_WEIGHT  # substring, partial weight
    return bag


def cosine(a, b, idf):
    """IDF-weighted cosine similarity between two token bags."""
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    num = sum(a[t] * b[t] * (idf.get(t, 1.0) ** 2) for t in shared)
    na = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in a.items()))
    nb = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in b.items()))
    return num / (na * nb) if na and nb else 0.0


def median_grade(grades):
    """Median letter of a list of grades (A=0 … E=4)."""
    if not grades:
        return None
    idx = sorted(GRADES.index(g) for g in grades if g in GRADES)
    if not idx:
        return None
    return GRADES[idx[len(idx) // 2]]


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────
print("🔬 Nutri-Score estimation from similar products")
print("=" * 60)

if not os.path.exists(PRODUCTS_FILE):
    print(f"❌ {PRODUCTS_FILE} not found — run enrich_nutrition.py first")
    raise SystemExit(1)

df = pd.read_excel(PRODUCTS_FILE)
print(f"\n📦 {len(df)} products loaded")

if "nutriscore" not in df.columns:
    print("❌ No 'nutriscore' column — run enrich_nutrition.py first")
    raise SystemExit(1)

for col in ("subcategory", "ingredients"):
    if col not in df.columns:
        df[col] = None

# Mark what we already have as official before we add anything
if "nutriscore_source" not in df.columns:
    df["nutriscore_source"] = None
df.loc[df["nutriscore"].notna() & df["nutriscore_source"].isna(), "nutriscore_source"] = "official"
if "nutriscore_confidence" not in df.columns:
    df["nutriscore_confidence"] = None
df.loc[df["nutriscore_source"] == "official", "nutriscore_confidence"] = 1.0

# Only OFFICIAL scores are training data. Previous estimates are cleared and
# recomputed every run — otherwise estimates would feed on estimates and drift.
prev_est = df["nutriscore_source"].isin(["estimated", "subcategory", "category"])
if prev_est.any():
    print(f"   clearing {prev_est.sum()} estimates from a previous run")
    df.loc[prev_est, ["nutriscore", "nutriscore_source", "nutriscore_confidence"]] = None

labeled_mask  = df["nutriscore_source"] == "official"
labeled_idx   = df.index[labeled_mask].tolist()
unlabeled_idx = df.index[~labeled_mask].tolist()

print(f"   {len(labeled_idx)} with an official score ({len(labeled_idx)/len(df)*100:.0f}%)")
print(f"   {len(unlabeled_idx)} to estimate")

if len(labeled_idx) < 30:
    print("\n⚠️  Too few labeled products to learn from — skipping estimation.")
    print("   Run enrich_nutrition.py a few more times to grow the cache.")
    raise SystemExit(0)

# ── Build token bags ──
print("\n🧮 Building token bags...")
bags = {i: build_bag(df.loc[i]) for i in df.index}

# ── IDF over the whole catalogue ──
doc_freq = Counter()
for bag in bags.values():
    doc_freq.update(set(bag))
N = len(bags)
idf = {t: math.log(N / (1 + f)) + 1.0 for t, f in doc_freq.items()}

# ── Index labeled products by category for fast lookup ──
by_cat = defaultdict(list)
for i in labeled_idx:
    by_cat[df.at[i, "category"]].append(i)

# Category / subcategory priors
cat_grades = defaultdict(list)
sub_grades = defaultdict(list)
for i in labeled_idx:
    g = df.at[i, "nutriscore"]
    cat_grades[df.at[i, "category"]].append(g)
    sub = df.at[i, "subcategory"]
    if sub:
        sub_grades[(df.at[i, "category"], sub)].append(g)

cat_median = {c: median_grade(g) for c, g in cat_grades.items() if len(g) >= MIN_CAT_SAMPLE}
sub_median = {k: median_grade(g) for k, g in sub_grades.items() if len(g) >= MIN_SUB_SAMPLE}

# ── Estimate ──
print(f"\n🔍 Matching {len(unlabeled_idx)} products against {len(labeled_idx)} references...")
by_neighbour = by_subcat = by_cat_prior = skipped = 0

for n, i in enumerate(unlabeled_idx):
    row  = df.loc[i]
    cat  = row["category"]
    sub  = row.get("subcategory")
    bag  = bags[i]

    # Candidates: same category first, whole catalogue if that's too thin
    candidates = by_cat.get(cat, [])
    if len(candidates) < MIN_CAT_SAMPLE:
        candidates = labeled_idx

    sims = []
    for j in candidates:
        s = cosine(bag, bags[j], idf)
        if s >= MIN_SIM:
            sims.append((s, df.at[j, "nutriscore"]))

    grade = None
    conf  = 0.0
    source = None

    if sims:
        sims.sort(reverse=True)
        top = sims[:K_NEIGHBOURS]
        votes = defaultdict(float)
        for s, g in top:
            if g in GRADES:
                votes[g] += s
        if votes:
            total = sum(votes.values())
            grade, weight = max(votes.items(), key=lambda kv: kv[1])
            agreement = weight / total                  # how unanimous the neighbours were
            strength  = sum(s for s, _ in top) / len(top)
            # A single close neighbour is not strong evidence — damp by count
            support   = min(1.0, len(top) / 3.0)
            conf      = round(agreement * min(1.0, strength / 0.6) * support, 3)
            source    = "estimated"

    # Fall back to priors when the match is weak
    if grade is None or conf < MIN_CONF:
        prior = sub_median.get((cat, sub)) if sub else None
        if prior:
            grade, conf, source = prior, 0.25, "subcategory"
            by_subcat += 1
        else:
            prior = cat_median.get(cat)
            if prior:
                grade, conf, source = prior, 0.15, "category"
                by_cat_prior += 1
            else:
                grade = None
    elif source == "estimated":
        by_neighbour += 1

    if grade:
        df.at[i, "nutriscore"] = grade
        df.at[i, "nutriscore_source"] = source
        df.at[i, "nutriscore_confidence"] = conf
    else:
        skipped += 1

    if (n + 1) % 500 == 0:
        print(f"   {n+1}/{len(unlabeled_idx)}...")

# Numeric confidence column so sorting works
df["nutriscore_confidence"] = pd.to_numeric(df["nutriscore_confidence"], errors="coerce")

df.to_excel(PRODUCTS_FILE, index=False)

# ── Report ──
official = (df["nutriscore_source"] == "official").sum()
covered  = df["nutriscore"].notna().sum()

print(f"\n{'='*60}")
print(f"🔬 Estimation complete!")
print(f"{'='*60}")
print(f"Official (Open Food Facts):  {official}")
print(f"From similar products:       {by_neighbour}")
print(f"From subcategory median:     {by_subcat}")
print(f"From category median:        {by_cat_prior}")
print(f"Still unscored:              {skipped}")
print(f"─────────────────────────────────────")
print(f"Total coverage:              {covered}/{len(df)}  ({covered/len(df)*100:.0f}%)")

print(f"\n📊 Nutri-Score distribution:")
for g in GRADES:
    n = (df["nutriscore"] == g).sum()
    if n:
        bar = "█" * max(1, int(n / max(1, covered) * 30))
        print(f"   {g}: {n:5}  {bar}")

# Show a few estimates so you can sanity-check the matching
est = df[df["nutriscore_source"] == "estimated"].nlargest(8, "nutriscore_confidence")
if len(est):
    print(f"\n✅ Highest-confidence estimates:")
    for _, r in est.iterrows():
        print(f"   [{r['nutriscore']}] {str(r['title'])[:45]:45} conf {r['nutriscore_confidence']:.2f}")

low = df[(df["nutriscore_source"] == "estimated") & (df["nutriscore_confidence"] < 0.45)]
if len(low):
    print(f"\n⚠️  {len(low)} low-confidence estimates — shown as approximate in the app")
