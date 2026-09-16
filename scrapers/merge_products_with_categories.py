"""
merge_products_with_categories.py
----------------------------------
Merges ALL scraper outputs + harmonizes categories automatically.
Add a new scraper? Just save its output to data/ and it's included.
"""

import pandas as pd
import os
import re
import base64
from io import BytesIO
from datetime import datetime
from glob import glob

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️  pytesseract not installed — image OCR disabled. Run: pip install pytesseract")

# ── Always work relative to THIS script's location ──
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
GITHUB_WORKSPACE = os.environ.get('GITHUB_WORKSPACE')
DATA_DIR         = os.path.join(GITHUB_WORKSPACE, 'data') if GITHUB_WORKSPACE else os.path.join(SCRIPT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== CONFIG ====================
MAX_TOTAL_PRODUCTS   = 10000
HARMONIZE_CATEGORIES = True

# ── Which files to include ──────────────────────
AUTO_DISCOVER = True   # Auto-find all *_products.xlsx in data/

EXPLICIT_FILES = {
    "Aviser":   os.path.join(DATA_DIR, "aviser_products.xlsx"),
    "Rema1000": os.path.join(DATA_DIR, "rema1000_products.xlsx"),
    "Wolt":     os.path.join(DATA_DIR, "wolt_products.xlsx"),
}
# ─────────────────────────────────────────────────

COLUMNS = ["title", "price", "category", "subcategory", "store", "remaining_days", "image_base64", "barcode", "ingredients"]
# Nutrition columns are added later by enrich_nutrition.py / estimate_nutriscore.py

# ==================== CATEGORY CONFIG ====================

CATEGORY_MAP = {
    # ── Frugt og grønt ──────────────────────────────────────────────────────
    "Frugt & grønt":                               "Frugt og grønt",
    "Frugt & Grønt":                               "Frugt og grønt",
    "Grøntsager, frugt & bær":                     "Frugt og grønt",
    "Salater, fint grønt & avocado":               "Frugt og grønt",
    "Grov grønt":                                  "Frugt og grønt",
    "Kål":                                         "Frugt og grønt",
    "Kartofler & løg":                             "Frugt og grønt",
    "Agurk, tomat & peberfrugt":                   "Frugt og grønt",
    "Melon, bær, vindruer & eksotisk frugt":       "Frugt og grønt",
    "Pære, æble, banan & citrusfrugt":             "Frugt og grønt",
    "Snittet frugt & grønt":                       "Frugt og grønt",
    "Blommer, fersken, nektariner & kiwi":         "Frugt og grønt",
    "Krydderurter & smagsforstærkere":             "Frugt og grønt",
    "HVERDAGSPRIS":                                "Frugt og grønt",
    "Vegetables":                                  "Frugt og grønt",
    "Fruits":                                      "Frugt og grønt",

    # ── Kød ─────────────────────────────────────────────────────────────────
    "Kød & fjerkræ":                               "Kød",
    "Kød & fisk":                                  "Kød",
    "Kød & Fjerkræ":                               "Kød",
    "Hakket kød":                                  "Kød",
    "Oksekød":                                     "Kød",
    "Gris":                                        "Kød",
    "Kylling":                                     "Kød",
    "Lam":                                         "Kød",
    "Pølser":                                      "Kød",
    "Pålæg":                                       "Kød",
    "Pålægs salater":                              "Kød",
    "Bacon & toppings":                            "Kød",
    "Postej/pate":                                 "Kød",
    "Skiveskåret":                                 "Kød",
    "Måltidssalater, pastasalater & nudelsalater": "Kød",
    "Delikatesser":                                "Kød",
    "Meat":                                        "Kød",

    # ── Fisk ────────────────────────────────────────────────────────────────
    "Fisk & skaldyr":                              "Fisk",
    "Fisk & Skaldyr":                              "Fisk",
    "Fisk, sild & skaldyr":                        "Fisk",
    "Fiskekonserves":                              "Fisk",

    # ── Mejeri ──────────────────────────────────────────────────────────────
    "Mejeri & køl":                                "Mejeri",
    "Mælk m.v.":                                   "Mejeri",
    "Yoghurt m.v.":                                "Mejeri",
    "Fløde m.v.":                                  "Mejeri",
    "Smør & fedtstoffer":                          "Mejeri",
    "Margarine":                                   "Mejeri",
    "Syrnede produkter":                           "Mejeri",
    "Æg":                                          "Mejeri",
    "Hytteost":                                    "Mejeri",
    "Specialost":                                  "Mejeri",
    "Skæreost":                                    "Mejeri",
    "Hård ost":                                    "Mejeri",
    "Madlavningsost m.v.":                         "Mejeri",
    "Smøreost":                                    "Mejeri",
    "Børneost":                                    "Mejeri",
    "Koldskål":                                    "Mejeri",
    "Mælkesnitte/dessert":                         "Mejeri",
    "Plantedrikke":                                "Mejeri",
    "Plantebaseret":                               "Mejeri",
    "Plantebaserede produkter":                    "Mejeri",
    "Plantebaserede alternativer":                 "Mejeri",
    "Ost":                                         "Mejeri",
    "Juice, kakao, drikkeyoghurt m.v.":            "Mejeri",
    "Dairy":                                       "Mejeri",

    # ── Brød og kager ───────────────────────────────────────────────────────
    "Brød & kager":                                "Brød og kager",
    "Brød":                                        "Brød og kager",
    "Rugbrød":                                     "Brød og kager",
    "Boller":                                      "Brød og kager",
    "Kiks, kager & knækbrød":                      "Brød og kager",
    "Kiks & kager":                                "Brød og kager",
    "Bavinchi bager":                              "Brød og kager",
    "Baguette/flutes":                             "Brød og kager",
    "Fast food brød":                              "Brød og kager",
    "Sandwiches & wraps":                          "Brød og kager",
    "Dej":                                         "Brød og kager",
    "Kager":                                       "Brød og kager",
    "Frisk pasta":                                 "Brød og kager",

    # ── Drikkevarer ─────────────────────────────────────────────────────────
    "Sodavand, vand, smoothies m.v.":              "Drikkevarer",
    "Juice m.v.":                                  "Drikkevarer",
    "Saft m.v.":                                   "Drikkevarer",
    "Kaffe":                                       "Drikkevarer",
    "Instant kaffe":                               "Drikkevarer",
    "Kaffetilbehør":                               "Drikkevarer",
    "Te":                                          "Drikkevarer",
    "Kakao":                                       "Drikkevarer",
    "Kaffe & te":                                  "Drikkevarer",
    "Øl":                                          "Drikkevarer",
    "Special øl":                                  "Drikkevarer",
    "Alkoholfri øl/vin":                           "Drikkevarer",
    "Rødvin":                                      "Drikkevarer",
    "Hvidvin":                                     "Drikkevarer",
    "Rosevin":                                     "Drikkevarer",
    "Mousserende vin":                             "Drikkevarer",
    "Vin":                                         "Drikkevarer",
    "Hedvin/aperitif":                             "Drikkevarer",
    "Spiritus":                                    "Drikkevarer",
    "Energidrikke":                                "Drikkevarer",
    "Ready to drink":                              "Drikkevarer",
    "Shots, juice & smoothies":                    "Drikkevarer",
    "Cider & RTD":                                 "Drikkevarer",
    "Drikkevarer":                                 "Drikkevarer",
    "Beverages":                                   "Drikkevarer",

    # ── Slik og snacks ──────────────────────────────────────────────────────
    "Chips og snacks":                             "Slik og snacks",
    "Chips & snacks":                              "Slik og snacks",
    "Chokolade m.v.":                              "Slik og snacks",
    "Lakrids m.v.":                                "Slik og snacks",
    "Vingummi":                                    "Slik og snacks",
    "Bolcher":                                     "Slik og snacks",
    "Nødder & tørret frugt":                       "Slik og snacks",
    "Pastiller":                                   "Slik og snacks",
    "Skum":                                        "Slik og snacks",
    "Mixposer":                                    "Slik og snacks",
    "Karamel m.v.":                                "Slik og snacks",
    "Tyggegummi":                                  "Slik og snacks",
    "Marcipan m.v.":                               "Slik og snacks",
    "Slik & chocolade":                            "Slik og snacks",
    "Snacks":                                      "Slik og snacks",

    # ── Frost ───────────────────────────────────────────────────────────────
    "Is og dessert":                               "Frost",
    "Pizza":                                       "Frost",
    "Kartofler":                                   "Frost",
    "Frys-selv-is":                                "Frost",
    "Frozen":                                      "Frost",

    # ── Morgenmad ───────────────────────────────────────────────────────────
    "Marmelade & chokolade pålæg m.v.":            "Morgenmad",
    "Morgenmad":                                   "Morgenmad",
    "Breakfast":                                   "Morgenmad",

    # ── Kolonial ────────────────────────────────────────────────────────────
    "Mel, sukker, bagning":                        "Kolonial",
    "Ris & pasta, mv":                             "Kolonial",
    "Konserves & survarer":                        "Kolonial",
    "Saucer & nem mad":                            "Kolonial",
    "Dressing":                                    "Kolonial",
    "Dressing & saucer":                           "Kolonial",
    "Ketchup, remoulade, mayonnaise m.v.":         "Kolonial",
    "Krydderier":                                  "Kolonial",
    "Olie, eddike & balsamico":                    "Kolonial",
    "Suppe & suppefyld":                           "Kolonial",
    "Tex mex":                                     "Kolonial",
    "Gær":                                         "Kolonial",
    "Ready to cook":                               "Kolonial",
    "Færdigretter":                                "Kolonial",
    "Verdensmad":                                  "Kolonial",
    "Spisekammeret":                               "Kolonial",
    "Convenience":                                 "Kolonial",
    "Delikatesse":                                 "Kolonial",
    "Kosttilskud":                                 "Kolonial",

    # ── Andet (non-food) ────────────────────────────────────────────────────
    "Tekstil":                                     "Andet",
    "Rengøringsartikler":                          "Andet",
    "Rengøringsmidler":                            "Andet",
    "Papir & poser":                               "Andet",
    "Lys & servietter":                            "Andet",
    "Kontor & legetøj":                            "Andet",
    "Service":                                     "Andet",
    "Køkkenredskaber":                             "Andet",
    "Vask & opvask":                               "Andet",
    "Kemisk teknisk":                              "Andet",
    "El":                                          "Andet",
    "Batterier":                                   "Andet",
    "Fuglefoder":                                  "Andet",
    "Hundemad":                                    "Andet",
    "Kattemad":                                    "Andet",
    "Dyreartikler":                                "Andet",
    "Kæledyr":                                     "Andet",
    "Baby- og småbørnsmad":                        "Andet",
    "Baby":                                        "Andet",
    "Bleer":                                       "Andet",
    "Sutter":                                      "Andet",
    "Diverse baby":                                "Andet",
    "Vat, bind & tamponer":                        "Andet",
    "Sæbe":                                        "Andet",
    "Mundpleje":                                   "Andet",
    "Shampoo/Balsam":                              "Andet",
    "Deodorant":                                   "Andet",
    "Cremer til krop/hænder":                      "Andet",
    "Ansigt":                                      "Andet",
    "Hår styling":                                 "Andet",
    "Læbepomade":                                  "Andet",
    "Lommeletter/plaster":                         "Andet",
    "Barberartikler":                              "Andet",
    "Ugeblade":                                    "Andet",
    "Cigaretter":                                  "Andet",
    "Pibetobak":                                   "Andet",
    "Tobak":                                       "Andet",
    "Hylster/papir/renser":                        "Andet",
    "Optænding":                                   "Andet",
    "Indpakning/kort":                             "Andet",
    "Fødselsdag":                                  "Andet",
    "Toiletpapir/køkkenruller":                    "Andet",
    "Sæson":                                       "Andet",
    "Tilbehør":                                    "Andet",
    "Diverse":                                     "Andet",
    "Aviser":                                      "Andet",
    "Husholdning":                                 "Andet",
    "Personlig pleje":                             "Andet",
    # NOTE: "DANSKE MADSKATTE" and "Aarstiderne" intentionally omitted here
    # so they fall through to keyword matching (they contain real food products)
    "":                                            "Andet",
    None:                                          "Andet",
}

MASTER_CATEGORIES = [
    "Øko",
    "Frugt og grønt", "Kød", "Fisk", "Mejeri",
    "Brød og kager", "Drikkevarer", "Slik og snacks",
    "Frost", "Morgenmad", "Kolonial", "Andet",
]

# Non-food category names — products in these are dropped entirely before harmonizing.
# Food-adjacent categories (Baby- og småbørnsmad, Kosttilskud, Sæson) are kept.
EXCLUDE_CATEGORIES = {
    # Personal care
    "Sæbe", "Mundpleje", "Shampoo/Balsam", "Deodorant",
    "Cremer til krop/hænder", "Ansigt", "Hår styling",
    "Læbepomade", "Barberartikler", "Lommeletter/plaster",
    "Personlig pleje",
    # Tobacco
    "Cigaretter", "Pibetobak", "Hylster/papir/renser", "Tobak",
    # Household & cleaning
    "Rengøringsartikler", "Rengøringsmidler", "Vask & opvask",
    "Kemisk teknisk", "Toiletpapir/køkkenruller", "Papir & poser",
    "Lys & servietter", "Husholdning",
    # Non-food goods
    "Tekstil", "El", "Batterier", "Kontor & legetøj",
    "Køkkenredskaber", "Service", "Indpakning/kort",
    "Optænding", "Tilbehør", "Diverse",
    # Pets
    "Hundemad", "Kattemad", "Dyreartikler", "Fuglefoder", "Kæledyr",
    # Baby non-food
    "Bleer", "Sutter", "Diverse baby", "Vat, bind & tamponer", "Baby",
    # Media
    "Ugeblade", "Aviser",
    # Seasonal / misc
    "Fødselsdag",
}

KEYWORD_CATEGORIES = {
    "Frugt og grønt": [
        "tomat", "tomater", "agurk", "agurker", "salat", "peber", "peberfrugter",
        "løg", "rødløg", "hvidløg", "kartoffel", "kartofler", "gulerod", "gulerødder",
        "broccoli", "blomkål", "squash", "zucchini", "aubergine", "auberginer",
        "spinat", "grønkål", "rosenkål", "spidskål", "hvidkål", "rødkål", "kål",
        "porre", "porrer", "selleri", "pastinak", "persillerod", "radise", "majs",
        "æble", "æbler", "banan", "bananer", "appelsin", "appelsiner", "pære", "pærer",
        "citron", "lime", "avocado", "blomme", "druer", "jordbær", "hindbær",
        "blåbær", "brombær", "melon", "vandmelon", "ananas", "kiwi", "mango",
        "fersken", "nektarin", "abrikos", "paprika", "chili",
        "persille", "basilikum", "koriander", "timian", "rosmarin", "dild", "mynte",
        "ruccola", "iceberg", "grøntsag", "grøntsager", "frugt", "bær",
        "tomato", "cucumber", "lettuce", "onion", "garlic", "potato", "carrot",
        "spinach", "cabbage", "apple", "banana", "orange", "lemon", "grape",
        "strawberry", "raspberry", "blueberry", "vegetable", "fruit", "berry",
    ],
    "Kød": [
        "oksekød", "kalvekød", "svinekød", "lammekød", "lam", "kylling",
        "bacon", "pølse", "pølser", "medister", "hamburger", "hakket", "hakkekød",
        "bøf", "steak", "kotelet", "mørbrad", "schnitzel", "skinke",
        "leverpostej", "kalkun", "and", "culotte", "ribeye", "filet",
        "grillpølse", "wienerpølse", "kød",
        "karbonader", "karbonade", "frikadeller", "frikadelle",
        "beef", "pork", "lamb", "chicken", "turkey", "duck",
        "sausage", "minced", "mince", "ham", "meat", "burger",
    ],
    "Fisk": [
        "laks", "ørred", "torsk", "tuna", "tunfisk", "makrel", "sild", "sardiner",
        "rejer", "reje", "hummer", "krabbe", "muslinger", "østers",
        "fiskefillet", "fiskefilet", "røget", "fisk", "seafood", "skaldyr",
        "salmon", "trout", "cod", "mackerel", "herring", "shrimp", "prawn",
        "lobster", "crab", "mussels", "oyster", "fish", "fillet",
    ],
    "Mejeri": [
        "mælk", "sødmælk", "skummetmælk", "letmælk", "minimælk", "kærnemælk",
        "ost", "cheddar", "mozzarella", "feta", "brie", "parmesan", "havarti",
        "yoghurt", "yogurt", "skyr", "ymer", "kefir",
        "smør", "margarine", "fløde", "piskefløde", "creme fraiche",
        "kvark", "hytteost", "cottage cheese", "ricotta",
        "æg", "æggene", "skrabeæg", "frilandsæg", "fraiche",
        "milk", "cheese", "butter", "cream", "yogurt", "dairy", "egg", "eggs",
    ],
    "Brød og kager": [
        "brød", "rugbrød", "franskbrød", "ciabatta", "baguette", "pitabrød", "tortilla",
        "rundstykke", "bolle", "boller", "bagel",
        "kage", "lagkage", "wienerbrød", "croissant", "kanelsnegl", "muffin", "brownie",
        "knækbrød", "cracker", "kiks",
        "bread", "roll", "bun", "cake", "croissant", "bagel", "toast",
        "cookie", "biscuit", "cracker", "muffin", "pastry",
    ],
    "Drikkevarer": [
        "vand", "mineralvand", "kildevand", "danskvand",
        "juice", "appelsinjuice", "æblejuice", "smoothie",
        "sodavand", "cola", "pepsi", "fanta", "sprite", "cocio", "saft",
        "kaffe", "espresso", "te", "kakao",
        "øl", "pilsner", "vin", "rødvin", "hvidvin", "champagne", "cider",
        "energidrik", "sportsdrik",
        "water", "juice", "soda", "coffee", "tea", "beer", "wine", "beverage", "drink",
    ],
    "Slik og snacks": [
        "chips", "popcorn", "nachos", "pringles",
        "nødder", "peanuts", "cashew", "mandler", "hasselnødder", "valnødder",
        "chokolade", "slik", "bolsjer", "vingummi", "lakrids", "tyggegummi",
        "twix", "snickers", "mars", "kitkat", "haribo", "malaco",
        "nuts", "chocolate", "candy", "sweets", "gummy", "liquorice", "snack",
    ],
    "Frost": [
        "frosne", "frost", "frossen", "dybfrossen",
        "is", "ispinde", "flødeis", "sorbet", "magnum",
        "pizza", "lasagne", "pommes frites",
        "frozen", "ice cream", "popsicle",
    ],
    "Morgenmad": [
        "cornflakes", "müsli", "musli", "havregryn", "havre", "grød",
        "honning", "marmelade", "syltetøj", "nutella", "peanut butter",
        "cereal", "muesli", "granola", "oatmeal", "honey", "jam",
    ],
    "Kolonial": [
        "pasta", "spaghetti", "macaroni", "penne", "fusilli",
        "ris", "risotto", "basmati", "jasmin",
        "mel", "hvedemel", "sukker", "salt", "peber",
        "olie", "olivenolie", "rapsolie", "eddike", "balsamico",
        "sauce", "ketchup", "mayonnaise", "remoulade", "sennep", "dressing",
        "bouillon", "fond", "krydderi",
        "dåse", "konserves", "bønner",
        "gær", "bagepulver", "rosiner", "korender", "sirup", "nougat",
        "rice", "flour", "sugar", "oil", "vinegar", "ketchup",
        "mayo", "mustard", "spice", "stock", "canned", "beans",
    ],
}


# ==================== FUNCTIONS ====================

def categorize_by_title(title):
    if pd.isna(title):
        return "Andet"
    title_norm = ' '.join(re.sub(r'[^\w\s]', ' ', title.lower()).split())
    best_cat, best_score = "Andet", 0
    for cat, keywords in KEYWORD_CATEGORIES.items():
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            pattern = r'\b' + re.escape(kw_lower) + r'\b'
            if re.search(pattern, title_norm):
                score += 20
            elif kw_lower in title_norm:
                score += 10
            elif any(w.startswith(kw_lower) for w in title_norm.split()):
                score += 5
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat if best_score >= 5 else "Andet"


def detect_organic_in_image(image_base64):
    """
    Run OCR on product image to detect organic labels/text.
    Catches products where title doesn't say ØKO but image shows:
    - The red Danish Ø-label
    - Text like "ØKO", "ORGANIC", "ÉCONOMIQUE" on packaging
    """
    if not OCR_AVAILABLE or not image_base64:
        return False
    try:
        img_data  = base64.b64decode(image_base64.split(",")[1])
        img       = Image.open(BytesIO(img_data)).convert("RGB")
        # Upscale 3× — improves OCR accuracy on small 300×300 images
        w, h      = img.size
        img       = img.resize((w * 3, h * 3), Image.LANCZOS)
        text      = pytesseract.image_to_string(img, lang="dan+eng").upper()
        ORGANIC_KEYWORDS = ["ØKO", "ØKOLOGISK", "ORGANIC", "BIO "]
        return any(kw in text for kw in ORGANIC_KEYWORDS)
    except Exception:
        return False


def harmonize_categories(df):
    print("\n🔄 Harmonizing categories...")

    # Keep the original store category as the subcategory (e.g. "Kylling", "Gris")
    def clean_sub(s):
        s = str(s or "").strip()
        if not s or s.lower() in ("nan", "none", "andet"):
            return ""
        s = re.sub(r"\s*m\.?v\.?\s*$", "", s, flags=re.I)   # "Yoghurt m.v." -> "Yoghurt"
        s = re.sub(r",?\s*mv\s*$", "", s, flags=re.I)         # "Ris & pasta, mv" -> "Ris & pasta"
        s = re.sub(r"\s*\d+\s*$", "", s)                     # "Frugt Grønt 48" -> "Frugt Grønt"
        return s.strip(" ,&")

    df["subcategory"] = df["category"].map(clean_sub)

    # Use hardcoded master categories (not dependent on Rema1000 being present)
    masters = set(MASTER_CATEGORIES)

    new_cats = []
    counts   = dict(kept_rema=0, mapped=0, kept_valid=0, by_title=0, andet=0)
    samples  = []
    fails    = []

    for _, row in df.iterrows():
        cat   = row.get("category")
        store = row.get("store", "")
        title = row.get("title", "")

        # 0. Øko check — takes priority over everything else
        title_str  = str(title).upper() if pd.notna(title) else ""
        from_title = (
            "ØKO" in title_str or
            "ØKOLOGISK" in title_str or
            "ORGANIC" in title_str
        )
        # Also check image (especially useful for aviser products)
        image_b64  = row.get("image_base64", "")
        from_image = (not from_title) and detect_organic_in_image(image_b64)

        if from_title or from_image:
            new_cats.append("Øko")
            counts["mapped"] += 1
            if from_image and not from_title:
                counts.setdefault("øko_from_image", 0)
                counts["øko_from_image"] += 1
            continue

        # 1. Keep Rema1000 categories (already correct)
        if store == "Rema1000" and pd.notna(cat) and cat != "" and cat in masters:
            new_cats.append(cat)
            counts["kept_rema"] += 1

        # 2. Map known category names
        elif cat in CATEGORY_MAP:
            mapped = CATEGORY_MAP[cat]
            new_cats.append(mapped)
            counts["mapped"] += 1

        # 3. Already a valid master category
        elif pd.notna(cat) and cat in masters:
            new_cats.append(cat)
            counts["kept_valid"] += 1

        # 4. Categorize by product title
        else:
            guessed = categorize_by_title(title)
            new_cats.append(guessed)
            if guessed != "Andet":
                counts["by_title"] += 1
                if len(samples) < 8:
                    samples.append(f"      '{title[:55]}' → '{guessed}'")
            else:
                counts["andet"] += 1
                if len(fails) < 8:
                    fails.append(f"      '{title[:55]}' → Andet")

    df["category"] = new_cats

    if samples:
        print("   ✅ Categorized by title (sample):")
        for s in samples: print(s)
    if fails:
        print("   ⚠️  Could not categorize (sample):")
        for f in fails: print(f)

    need  = counts["by_title"] + counts["andet"]
    rate  = counts["by_title"] / need * 100 if need else 0
    print(f"\n   Kept Rema1000: {counts['kept_rema']}")
    print(f"   Mapped:        {counts['mapped']}")
    print(f"   Kept valid:    {counts['kept_valid']}")
    print(f"   By title:      {counts['by_title']}")
    print(f"   Andet:         {counts['andet']}")
    if counts.get("øko_from_image"):
        print(f"   🌿 Øko via image OCR: {counts['øko_from_image']}")
    print(f"   🎯 Title success rate: {rate:.1f}%")
    return df


# ==================== MAIN ====================

print("🐝 Merge Products with Category Harmonization")
print("=" * 60)

# ── Discover files ──────────────────────────────
if AUTO_DISCOVER:
    found_files = sorted(glob(os.path.join(DATA_DIR, "*_products.xlsx")))
    files = {os.path.basename(f).replace("_products.xlsx", "").title(): f
             for f in found_files}
    print(f"\n📂 Looking in: {DATA_DIR}")
    print(f"📂 Auto-discovered {len(files)} file(s):")
    for name, path in files.items():
        size_mb = os.path.getsize(path) / 1024 / 1024 if os.path.exists(path) else 0
        print(f"   {name}: {path}  ({size_mb:.1f} MB)")
else:
    files = EXPLICIT_FILES
    print(f"\n📂 Using explicit file list:")
    for name, path in files.items():
        exists = "✅" if os.path.exists(path) else "❌"
        print(f"   {exists} {name}: {path}")

# ── Load ────────────────────────────────────────
all_dfs = []
for name, path in files.items():
    if os.path.exists(path):
        df = pd.read_excel(path)
        print(f"\n✅ Loaded {name}: {len(df)} products")
        all_dfs.append(df)
    else:
        print(f"\n⚠️  Not found, skipping: {path}")

if not all_dfs:
    print("\n❌ No data files found!")
    exit(1)

# ── Merge ───────────────────────────────────────
merged = pd.concat(all_dfs, ignore_index=True)
print(f"\n📊 Combined: {len(merged)} products")

for col in COLUMNS:
    if col not in merged.columns:
        merged[col] = None

merged = merged[COLUMNS]
merged = merged.dropna(subset=["title", "price"])
merged = merged[merged["title"].astype(str).str.strip() != ""]
print(f"After cleanup: {len(merged)} products")

# Show store breakdown BEFORE image filter (helps diagnose missing stores)
print(f"\n📊 Store counts before image filter:")
for store, n in merged["store"].value_counts().items():
    has_img = merged[merged["store"] == store]["image_base64"].notna().sum()
    print(f"   {store}: {n} total  ({has_img} with images)")

merged = merged[merged["image_base64"].notna()]
print(f"\nWith images: {len(merged)} products")

# Drop known non-food categories before harmonizing
before_excl = len(merged)
merged = merged[~merged["category"].isin(EXCLUDE_CATEGORIES)]
dropped = before_excl - len(merged)
if dropped:
    print(f"Removed {dropped} non-food products (tobacco, cleaning, pets, textiles…)")

# ── Harmonize ───────────────────────────────────
if HARMONIZE_CATEGORIES:
    merged = harmonize_categories(merged)

# ── Limit ───────────────────────────────────────
if len(merged) > MAX_TOTAL_PRODUCTS:
    print(f"\n⚠️  Limiting to {MAX_TOTAL_PRODUCTS}")
    offers  = merged[merged["remaining_days"].notna()].head(600)
    regular = merged[merged["remaining_days"].isna()].head(MAX_TOTAL_PRODUCTS - len(offers))
    merged  = pd.concat([offers, regular], ignore_index=True)

# ── Sort ────────────────────────────────────────
merged["sort_priority"] = merged["remaining_days"].notna().astype(int)
merged = merged.sort_values(
    ["sort_priority", "remaining_days", "price"],
    ascending=[False, True, True]
).drop("sort_priority", axis=1)

# ── Save ────────────────────────────────────────
output = os.path.join(DATA_DIR, "products.xlsx")
merged.to_excel(output, index=False)
mb = os.path.getsize(output) / 1024 / 1024

print(f"\n{'='*60}")
print(f"🐝 Merge Complete!")
print(f"{'='*60}")
print(f"Total Products: {len(merged)}")
print(f"Stores:         {sorted(merged['store'].unique().tolist())}")
print(f"Categories:     {merged['category'].nunique()}")
print(f"Output:         {output}  ({mb:.2f} MB)")
print(f"Timestamp:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n📊 Category Distribution:")
for cat, n in merged["category"].value_counts().head(15).items():
    pct = n / len(merged) * 100
    print(f"   {cat}: {n} ({pct:.1f}%)")
print(f"\n📊 Store Distribution:")
for store, n in merged["store"].value_counts().items():
    print(f"   {store}: {n}")
