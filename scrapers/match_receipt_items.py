"""
match_receipt_items.py
----------------------
Matches abbreviated receipt line names to products in data/products.xlsx.

Receipts print "HK. OKSEKØD 8-12%" where the catalogue says
"Hakket oksekød 8-12% 500 g", and "RUGBRØD SOLSIKKE" where the catalogue
says "Solsikke rugbrød". So this needs to be order-independent, tolerant
of truncation, and aware of Danish receipt abbreviations.

Same engine as estimate_nutriscore.py: IDF-weighted character n-grams,
which is what makes Danish compounds match.

    python scrapers/match_receipt_items.py        # runs the test suite

Or:
    from match_receipt_items import ReceiptMatcher
    m = ReceiptMatcher(products_df)
    hit = m.match("HK. OKSEKØD 8-12%", store="Rema1000")
"""

import os, re, math
from collections import Counter, defaultdict

# ─────────────────── CONFIG ───────────────────
NGRAM_N       = 4
NGRAM_WEIGHT  = 0.45   # receipts are short, so substrings matter more here
MIN_SCORE     = 0.30   # below this we return no match rather than a bad one
AMBIGUOUS_GAP = 0.06   # if 1st and 2nd are this close, flag it for review
# ──────────────────────────────────────────────

# Abbreviations Danish receipts use. Expanded before tokenising.
ABBREV = {
    r"\bhk\b":        "hakket",
    r"\bøko\b":       "økologisk",
    r"\boko\b":       "økologisk",
    r"\bøkol\b":      "økologisk",
    r"\bmælk\b":      "mælk",
    r"\bml\b":        "mælk",          # only in dairy context; harmless elsewhere
    r"\bskivost\b":   "skiveost",
    r"\bfl\b":        "flaske",
    r"\bstk\b":       "stk",
    r"\bm/\b":        "med ",
    r"\bu/\b":        "uden ",
    r"\bkyll\b":      "kylling",
    r"\bsvine\b":     "svinekød",
    r"\bokse\b":      "oksekød",
    r"\brugbr\b":     "rugbrød",
    r"\bfrugtyog\b":  "frugtyoghurt",
    r"\bmineralv\b":  "mineralvand",
    r"\bchok\b":      "chokolade",
    r"\bflødeost\b":  "flødeost",
}

# Words carrying no identifying information
STOPWORDS = {
    "stk", "pk", "pakke", "pose", "bakke", "flaske", "glas", "dåse",
    "ca", "kg", "gr", "gram", "liter", "ltr", "cl", "dl",
    "dansk", "danske", "frisk", "friske", "naturel", "original",
    "med", "uden", "og", "til", "fra", "af", "the", "and",
    "vare", "varer", "produkt", "tilbud", "spar", "pris",
}


# Fold Danish characters so an OCR-repaired "o" matches a real "ø".
# Applied to BOTH receipt lines and catalogue titles, so nothing is lost.
DANISH_FOLD = [("æ", "ae"), ("ø", "o"), ("å", "aa")]


def fold_danish(s):
    for a, b in DANISH_FOLD:
        s = s.replace(a, b)
    return s


def normalise(text):
    """Lowercase, expand abbreviations, fold Danish chars, strip punctuation."""
    s = (text or "").lower()
    s = s.replace(".", " ").replace("/", " / ")
    for pattern, full in ABBREV.items():
        s = re.sub(fold_danish(pattern), fold_danish(full), s)
    s = fold_danish(s)
    s = re.sub(r"[^\w%\s]", " ", s)
    return " ".join(s.split())


# Characters OCR commonly confuses on thermal receipts. Applied only when
# the digit sits inside a word that is otherwise letters — so "GULER0DDER"
# is repaired but "500G" is still treated as a size and dropped.
OCR_CONFUSIONS = str.maketrans({"0": "o", "1": "i", "5": "s", "8": "b", "6": "g"})


def repair_ocr(word):
    letters = sum(ch.isalpha() for ch in word)
    digits  = sum(ch.isdigit() for ch in word)
    if digits and letters >= 3 and letters > digits:
        return word.translate(OCR_CONFUSIONS)
    return word


def tokenize(text):
    out = []
    for w in normalise(text).split():
        w = repair_ocr(w)
        if len(w) < 3 or w in STOPWORDS:
            continue
        if any(ch.isdigit() for ch in w):     # "500g", "8-12%", "45"
            continue
        for suf in ("erne", "ene", "er", "en", "et", "e"):
            if len(w) > 5 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


def char_ngrams(word, n=NGRAM_N):
    if len(word) <= n:
        return [word]
    return [word[i:i + n] for i in range(len(word) - n + 1)]


def build_bag(text):
    bag = Counter()
    for tok in tokenize(text):
        bag[tok] += 1.0
        for g in char_ngrams(tok):
            bag["#" + g] += NGRAM_WEIGHT
    return bag


def cosine(a, b, idf):
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    num = sum(a[t] * b[t] * (idf.get(t, 1.0) ** 2) for t in shared)
    na = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in a.items()))
    nb = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in b.items()))
    return num / (na * nb) if na and nb else 0.0


class ReceiptMatcher:
    """Index a catalogue once, then match many receipt lines against it."""

    def __init__(self, products):
        """products: list of dicts with at least 'title', 'store', 'price'."""
        self.products = list(products)
        self.bags = [build_bag(p.get("title", "")) for p in self.products]

        df = Counter()
        for bag in self.bags:
            df.update(set(bag))
        n = max(1, len(self.bags))
        self.idf = {t: math.log(n / (1 + f)) + 1.0 for t, f in df.items()}

        self.by_store = defaultdict(list)
        for i, p in enumerate(self.products):
            self.by_store[p.get("store")].append(i)

    def match(self, receipt_name, store=None, price=None):
        """
        Returns {product, score, ambiguous, runner_up} or None.

        store  — restrict to that chain's catalogue (much more accurate)
        price  — if given, nudges candidates whose price is close
        """
        bag = build_bag(receipt_name)
        if not bag:
            return None

        pool = self.by_store.get(store) or range(len(self.products))

        scored = []
        for i in pool:
            s = cosine(bag, self.bags[i], self.idf)
            if s <= 0:
                continue
            # A price within 50 øre is strong corroboration
            if price is not None:
                pp = self.products[i].get("price")
                if pp is not None:
                    try:
                        if abs(float(pp) - float(price)) < 0.5:
                            s += 0.12
                        elif abs(float(pp) - float(price)) < 2.0:
                            s += 0.04
                    except (TypeError, ValueError):
                        pass
            scored.append((s, i))

        if not scored:
            return None

        scored.sort(reverse=True)
        best_score, best_i = scored[0]
        if best_score < MIN_SCORE:
            return None

        runner = scored[1] if len(scored) > 1 else None
        ambiguous = bool(runner and (best_score - runner[0]) < AMBIGUOUS_GAP)

        return {
            "product": self.products[best_i],
            "score": round(best_score, 3),
            "ambiguous": ambiguous,
            "runner_up": self.products[runner[1]] if runner else None,
        }

    def match_receipt(self, parsed, store=None):
        """Match every item from parse_receipt() output."""
        store = store or parsed.get("store")
        results = []
        for item in parsed.get("items", []):
            hit = self.match(item["name"], store=store, price=item["unit_price"])
            results.append({
                "receipt": item,
                "match": hit["product"] if hit else None,
                "score": hit["score"] if hit else 0.0,
                "ambiguous": hit["ambiguous"] if hit else False,
                "status": ("ambiguous" if hit and hit["ambiguous"]
                           else "matched" if hit else "unmatched"),
            })
        return results


# ──────────────────────────────────────────────
if __name__ == "__main__":

    # A slice of catalogue that looks like the real thing
    CATALOGUE = [
        {"title": "MINIMÆLK 0,4% FEDT",        "store": "Rema1000", "price": 7.95},
        {"title": "LETMÆLK 1,5% FEDT",         "store": "Rema1000", "price": 8.50},
        {"title": "SØDMÆLK 3,5%",              "store": "Rema1000", "price": 9.50},
        {"title": "SOLSIKKE RUGBRØD",          "store": "Rema1000", "price": 18.95},
        {"title": "KERNEGROVBRØD",             "store": "Rema1000", "price": 17.50},
        {"title": "ØKO. BANANER FAIRTRADE",    "store": "Rema1000", "price": 12.25},
        {"title": "BANAN",                     "store": "Rema1000", "price": 3.50},
        {"title": "GULERØDDER",                "store": "Rema1000", "price": 5.95},
        {"title": "SNACK GULERØDDER",          "store": "Rema1000", "price": 12.95},
        {"title": "HK. OKSEKØD 8-12%",         "store": "Rema1000", "price": 32.00},
        {"title": "HK. KYLLINGEKØD 4-7%",      "store": "Rema1000", "price": 28.00},
        {"title": "KYLLINGEBRYSTFILET",        "store": "Rema1000", "price": 45.00},
        {"title": "SKYR NATUREL",              "store": "Netto",    "price": 12.50},
        {"title": "SKYR VANILJE",              "store": "Netto",    "price": 13.50},
        {"title": "KAFFE SPECIALRISTET 400 G", "store": "Netto",    "price": 39.95},
        {"title": "DANSKE LAKSEFILETER",       "store": "Netto",    "price": 63.16},
        {"title": "ØKO. GULERØDDER",           "store": "Netto",    "price": 9.95},
        {"title": "HAVREGRYN 1 KG",            "store": "Meny",     "price": 12.95},
        {"title": "DANBO SKIVEOST 45+",        "store": "Meny",     "price": 29.95},
        {"title": "TOMATER LØSVÆGT",           "store": "Meny",     "price": 18.50},
        {"title": "AFFALDSPOSER 20 LTR",       "store": "Rema1000", "price": 15.00},
    ]

    # (receipt line, store, price, expected catalogue title or None)
    CASES = [
        ("MINIMÆLK 0,4%",     "Rema1000",  7.95, "MINIMÆLK 0,4% FEDT"),
        ("RUGBRØD SOLSIKKE",  "Rema1000", 18.95, "SOLSIKKE RUGBRØD"),
        ("ØKO BANANER",       "Rema1000", 12.25, "ØKO. BANANER FAIRTRADE"),
        ("GULERØDDER 1KG",    "Rema1000",  5.95, "GULERØDDER"),
        ("HAKKET OKSEKØD",    "Rema1000", 32.00, "HK. OKSEKØD 8-12%"),
        ("HK. OKSEKØD",       "Rema1000", 32.00, "HK. OKSEKØD 8-12%"),
        ("SKYR NATUREL",      "Netto",    12.50, "SKYR NATUREL"),
        ("KAFFE 400G",        "Netto",    39.95, "KAFFE SPECIALRISTET 400 G"),
        ("LAKSEFILET",        "Netto",    63.16, "DANSKE LAKSEFILETER"),
        ("ØKO GULERØDDER",    "Netto",     9.95, "ØKO. GULERØDDER"),
        ("HAVREGRYN 1KG",     "Meny",     12.95, "HAVREGRYN 1 KG"),
        ("DANBO OST 45+",     "Meny",     29.95, "DANBO SKIVEOST 45+"),
        ("TOMATER LØSVÆGT",   "Meny",     18.50, "TOMATER LØSVÆGT"),
        ("XYZZY VARE 999",    "Rema1000", 99.00, None),
        ("AFFALDSPOSER 20L",  "Rema1000", 15.00, "AFFALDSPOSER 20 LTR"),
    ]

    m = ReceiptMatcher(CATALOGUE)

    print("🔗 Receipt line → catalogue matching")
    print("=" * 72)
    ok = 0
    for line, store, price, want in CASES:
        hit = m.match(line, store=store, price=price)
        got = hit["product"]["title"] if hit else None
        good = (got == want)
        ok += good
        flag = "✅" if good else "❌"
        amb = "  ⚠ tvetydig" if hit and hit["ambiguous"] else ""
        sc = f"{hit['score']:.2f}" if hit else "—"
        print(f"{flag} {line:<20} -> {str(got)[:32]:<34} {sc}{amb}")
        if not good:
            print(f"     forventet: {want}")

    print("=" * 72)
    print(f"{ok}/{len(CASES)} correct  ({ok/len(CASES)*100:.0f}%)")
