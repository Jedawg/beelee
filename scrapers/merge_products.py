"""
merge_products_with_categories.py
----------------------------------
Merges products AND harmonizes categories automatically!
"""

import pandas as pd
import os
import re  # ADDED: For regex matching in categorization
from datetime import datetime

os.makedirs("data", exist_ok=True)

# ==================== CONFIG ====================
MAX_TOTAL_PRODUCTS = 10000
HARMONIZE_CATEGORIES = True  # Set to False to skip

# Category mapping
CATEGORY_MAP = {
    # Common variations to Rema1000 format
    "Frugt & Grønt": "Frugt og grønt",
    "Kød & Fjerkræ": "Kød",
    "Vegetables": "Frugt og grønt",
    "Fruits": "Frugt og grønt",
    "Meat": "Kød",
    "Dairy": "Mejeri",
    "Beverages": "Drikkevarer",
    "Snacks": "Slik og snacks",
    "Frozen": "Frost",
    "Breakfast": "Morgenmad",
    "": "Andet",
    None: "Andet"
}

# Keywords for auto-categorization (MASSIVE EXPANSION!)
KEYWORD_CATEGORIES = {
    "Frugt og grønt": [
        # Danish vegetables
        "tomat", "tomater", "agurk", "agurker", "salat", "peber", "peberfrugter", 
        "løg", "rødløg", "hvidløg", "kartoffel", "kartofler", "gulerod", "gulerødder",
        "broccoli", "blomkål", "squash", "zucchini", "aubergine", "auberginer",
        "spinat", "grønkål", "rosenkål", "spidskål", "hvidkål", "rødkål", "kål",
        "porre", "porrer", "selleri", "knoldselleri", "pastinak", "persillerod",
        "radise", "radiser", "roe", "roer", "majskolbe", "majs",
        # Danish fruits
        "æble", "æbler", "banan", "bananer", "appelsin", "appelsiner", "pære", "pærer",
        "citron", "citroner", "lime", "limer", "avocado", "avocadoer",
        "druer", "vindruer", "jordbær", "hindbær", "blåbær", "brombær", "solbær",
        "melon", "vandmelon", "honningmelon", "ananas", "kiwi", "kiwifrugter", 
        "mango", "papaya", "fersken", "ferskner", "nektarin", "abrikos", "abrikoser",
        # Herbs & greens
        "paprika", "chili", "chilipeber", "jalapeño",
        "persille", "basilikum", "koriander", "timian", "rosmarin", "dild", "mynte",
        "ruccola", "rucola", "iceberg", "lollo", "feldsalat", "romana",
        # General terms
        "grøn", "grønt", "grøntsag", "grøntsager", "frugt", "frugter", "bær",
        "økologisk", "øko", "organic", "bio",
        # English
        "tomato", "tomatoes", "cucumber", "cucumbers", "lettuce", "pepper", "peppers",
        "onion", "onions", "garlic", "potato", "potatoes", "carrot", "carrots",
        "broccoli", "cauliflower", "zucchini", "eggplant", "aubergine",
        "spinach", "kale", "cabbage", "brussels", "leek", "celery",
        "apple", "apples", "banana", "bananas", "orange", "oranges", "pear", "pears",
        "lemon", "lemons", "lime", "limes", "avocado", "avocados",
        "grapes", "strawberry", "strawberries", "raspberry", "raspberries", 
        "blueberry", "blueberries", "melon", "watermelon", "pineapple", 
        "kiwi", "mango", "peach", "nectarine", "apricot",
        "parsley", "basil", "cilantro", "coriander", "thyme", "rosemary", "dill", "mint",
        "vegetable", "vegetables", "fruit", "fruits", "berry", "berries", "salad"
    ],
    
    "Kød": [
        # Danish meat types
        "oksekød", "kalvekød", "svinekød", "lammekød", "lam", "kylling", "kyllinge",
        "bacon", "pølse", "pølser", "medister", "medisterpølse", "hamburger", 
        "hakket", "hakkekød", "fars", "kødfars",
        "bøf", "bøffer", "steak", "koteletter", "kotelet", "mørbrad", "kamsteg",
        "schnitzel", "schnitzler", "skinke", "spegepølse",
        "lever", "leverpostej", "hjerter", "nyrer", "indmad",
        "kalkun", "kalkunbryst", "and", "andebryst", "gås",
        "culotte", "ribeye", "entrecote", "filet", "T-bone",
        # Prepared meat
        "grillpølse", "wienerpølse", "frankfurter", "bratwurst",
        "bacon", "bacontern", "pancetta",
        # General meat terms
        "kød", "kødstykke", "kødstykker", "marineret", "krydret",
        # English
        "beef", "veal", "pork", "lamb", "chicken", "turkey", "duck", "goose",
        "bacon", "sausage", "sausages", "minced", "mince", "ground beef", "ground pork",
        "steak", "steaks", "chop", "chops", "cutlet", "schnitzel", "ham",
        "liver", "hearts", "kidneys", "meat", "patties", "burger", "patty"
    ],
    
    "Fisk": [
        # Danish fish
        "laks", "laksefillet", "ørred", "ørredfillet", "torsk", "torskerogn",
        "tuna", "tunfisk", "makrel", "sild", "sildemadder", "sardiner",
        "rødspætte", "pighvar", "hellefisk", "sei", "kuller",
        # Shellfish & seafood
        "rejer", "reje", "jomfruhummer", "hummer", "krabbe", "krabbekløer",
        "muslinger", "østers", "kammuslinger", "blåmuslinger",
        "blæksprutte", "calamari", "blekksprut",
        # Prepared fish
        "fiskefillet", "fiskefilet", "røget", "gravet", "marineret",
        "fiskeburger", "fiskeboller", "fiskefrikadeller",
        # General fish terms
        "fisk", "seafood", "skaldyr",
        # English
        "salmon", "trout", "cod", "tuna", "mackerel", "herring", "sardine", "sardines",
        "shrimp", "shrimps", "prawn", "prawns", "lobster", "crab", "crabmeat",
        "mussels", "clams", "oyster", "oysters", "scallops",
        "squid", "octopus", "calamari", "fish", "fillet", "smoked", "seafood"
    ],
    
    "Mejeri": [
        # Milk types
        "mælk", "sødmælk", "skummetmælk", "letmælk", "minimælk", "kærnemælk",
        "laktosefri", "økologisk mælk",
        # Cheese varieties
        "ost", "cheddar", "gouda", "havarti", "danbo", "maribo", "esrom", "danish blue",
        "mozzarella", "feta", "brie", "camembert", "parmigiano", "parmesan", "pecorino",
        "gorgonzola", "roquefort", "emmentaler", "gruyère", "edamer",
        "frisk ost", "hjemmelavet", "rygeost", "gråskimmelost",
        # Yogurt & cultured
        "yoghurt", "yogurt", "skyr", "ymer", "tykmælk", "a38", "kefir",
        "græsk yoghurt", "naturel yoghurt", "frugtyoghurt",
        # Cream & butter
        "smør", "bregott", "kærgården", "margarine", "becel",
        "fløde", "piskefløde", "matfløde", "crème fraîche", "creme fraiche", "cremefraiche",
        # Cream cheese & spreads
        "kvark", "hytteost", "cottage cheese", "ricotta", "mascarpone", "philadephia",
        # General dairy
        "mejeri", "mejeriprodukter", "dairy",
        # English
        "milk", "skim milk", "whole milk", "semi-skimmed", "lactose free",
        "cheese", "yogurt", "yoghurt", "butter", "cream", "whipping cream", "sour cream",
        "buttermilk", "cottage", "curd"
    ],
    
    "Brød og kager": [
        # Bread types
        "brød", "rugbrød", "franskbrød", "ciabatta", "focaccia", "baguette",
        "fuldkornsbrød", "grahamsbrød", "solsikkebrød", "havregrødsbrød",
        "pitabrød", "fladbrød", "tortilla", "wrap",
        # Rolls & buns
        "rundstykke", "rundstykker", "morgenbolle", "bolle", "boller",
        "burgerbolle", "hotdogbolle", "tebirkes", "chokoladebolle",
        "bagel", "bagels",
        # Cakes & pastries
        "kage", "lagkage", "drømmekage", "æblekage", "gulerodskage",
        "wienerbrød", "croissant", "kanelsnegl", "kanelgifler", "snegl",
        "spandauer", "frøsnapper", "romkugle",
        "muffin", "cupcake", "brownie", "cookie", "småkage",
        # Crackers & crispbread
        "knækbrød", "cracker", "kiks", "digestive", "marie", "cornflakes",
        # Pastry & dough
        "butterdej", "mørdej", "pizzadej",
        # General terms
        "bagværk", "konditori",
        # English
        "bread", "rye bread", "french bread", "roll", "rolls", "bun", "buns",
        "cake", "danish", "croissant", "cinnamon roll", "cinnamon",
        "bagel", "toast", "crispbread", "cookie", "cookies", "biscuit", "biscuits",
        "cracker", "crackers", "muffin", "brownie", "pie", "tart", "pastry"
    ],
    
    "Drikkevarer": [
        # Water
        "vand", "mineralvand", "kildevand", "danskvand", "postevand",
        "brusvand", "sodavand med brus",
        # Juice
        "juice", "appelsinjuice", "æblejuice", "tomatjuice", "multivitamin",
        "smoothie", "nektar",
        # Soda
        "sodavand", "cola", "coca cola", "cocio", "pepsi", "fanta", "sprite", 
        "7up", "schweppes", "squash", "saft",
        # Hot beverages  
        "kaffe", "kaffebønner", "espresso", "cappuccino", "latte",
        "te", "grøn te", "sort te", "urtete", "kamillete",
        "kakao", "chokolade", "nesquik", "chokolademælk",
        # Energy & sports
        "energidrik", "red bull", "monster", "burn", "sportsdrik", "powerade", "gatorade",
        # Alcohol
        "øl", "pilsner", "tuborg", "carlsberg", "cider",
        "vin", "rødvin", "hvidvin", "rosé", "champagne", "mousserende",
        # General
        "drikke", "drikkevare",
        # English
        "water", "mineral water", "sparkling water", "still water",
        "juice", "orange juice", "apple juice", "smoothie",
        "soda", "soft drink", "cola", "lemonade", "pop",
        "coffee", "espresso", "tea", "green tea", "black tea", "herbal tea",
        "cocoa", "chocolate milk", "hot chocolate",
        "energy drink", "sports drink",
        "beer", "lager", "ale", "wine", "red wine", "white wine", "rosé", "champagne",
        "beverage", "drink", "drinks"
    ],
    
    "Slik og snacks": [
        # Chips & salty snacks
        "chips", "popcorn", "nachos", "tortilla chips", "pringles", "kims",
        "nødder", "nøddeblandning", "peanuts", "cashew", "cashewnødder", 
        "mandler", "hasselnødder", "valnødder", "pistacienødder",
        "peanøtter", "jordnødder", "salte peanuts",
        # Candy
        "chokolade", "slik", "godteri", "bolsjer", "vingummi", "skumfiduser",
        "lakrids", "salt lakrids", "tyggegummi",
        "guld barre", "guldkarameller", "karamel", "karameller",
        # Chocolate bars
        "twix", "snickers", "mars", "bounty", "kitkat", "lion",
        "milka", "marabou", "toblerone", "after eight",
        # Brands
        "haribo", "malaco", "toms", "anthon berg", "ga-jol",
        # General
        "snack", "snacks",
        # English
        "chips", "crisps", "popcorn", "nuts", "peanuts", "cashews", "almonds",
        "walnuts", "hazelnuts", "pistachios",
        "chocolate", "candy", "sweets", "gummy", "gummies", "liquorice", "licorice",
        "chewing gum", "bubblegum", "lollipop", "lollipops", "caramel"
    ],
    
    "Frost": [
        # General frozen
        "frosne", "frost", "frossen", "dybfrossen", "frozen",
        # Ice cream
        "is", "ispinde", "isbar", "isterninger", "flødeis", "sorbet",
        "magnum", "ben & jerry", "ben and jerry", "häagen-dazs",
        # Frozen meals
        "pizza", "frostpizza", "lasagne", "frosne ret", "frosne retter",
        # Frozen vegetables
        "pommes frites", "frosne grøntsager", "ærter", "spinat", "majs",
        # General
        "freezer", "ice cream", "popsicle", "ice cubes"
    ],
    
    "Morgenmad": [
        # Cereal
        "cornflakes", "müsli", "musli", "havregryn", "havre", "grød", "havregr ød",
        "cheerios", "frosties", "coco pops", "Special K",
        # Spreads
        "honning", "marmelade", "syltetøj", "jam", "nutella", "pålæg",
        "peanutbutter", "peanøtsmør", "peanut butter", "chokoladepålæg",
        # Breakfast items
        "morgenmad", "breakfast",
        # English
        "cereal", "cornflakes", "muesli", "granola", "oatmeal", "oats", "porridge",
        "honey", "marmalade", "spread"
    ],
    
    "Kolonial": [
        # Pasta & rice
        "pasta", "spaghetti", "macaroni", "penne", "fusilli", "farfalle", "tagliatelle",
        "ris", "risotto", "basmati", "jasmin", "jasminris", "parboiled",
        # Flour & baking
        "mel", "hvedemel", "rugmel", "bagepulver", "gær", "natron",
        "sukker", "flormelis", "farin", "rørsukker",
        # Salt & pepper
        "salt", "havsalt", "peber", "hvidpeber", "sortpeber",
        # Oil & vinegar
        "olie", "olivenolie", "rapsolie", "solsikkeolie",
        "eddike", "hvidvinseddike", "balsamico", "æbleeddike",
        # Sauces & condiments
        "sauce", "ketchup", "mayo", "mayonnaise", "remoulade", "sennep",
        "dressing", "salatdressing",
        "soyasauce", "soya", "worcester", "tabasco", "sriracha",
        # Stock & bouillon
        "bouillon", "fond", "bouillonterning", "bouillonterninger",
        # Spices
        "krydderi", "krydderier", "salt", "peber", "paprika", "kanel",
        "oregano", "basilikum", "timian", "karry", "spidskommen",
        # Canned goods
        "dåse", "hermetik", "konserves", "dåsetomater", "bønner",
        "tun", "makrel på dåse",
        # General
        "varer", "dagligvarer",
        # English
        "pasta", "spaghetti", "macaroni", "penne", "noodles",
        "rice", "risotto", "basmati", "jasmine",
        "flour", "wheat flour", "baking powder", "yeast", "sugar",
        "salt", "pepper", "spice", "spices", "herbs",
        "oil", "olive oil", "vinegar", "balsamic",
        "sauce", "ketchup", "mayo", "mayonnaise", "mustard", "dressing",
        "soy sauce", "worcestershire",
        "stock", "broth", "bouillon", "cube", "seasoning",
        "canned", "tinned", "can", "beans", "tomatoes"
    ]
}

# ==================== FUNCTIONS ====================

def categorize_by_title(title, master_categories):
    """Categorize based on product title with smart matching"""
    if pd.isna(title):
        return "Andet"
    
    # Normalize title for better matching
    title_lower = title.lower()
    # Remove special characters and extra spaces
    title_normalized = re.sub(r'[^\w\s]', ' ', title_lower)
    title_normalized = ' '.join(title_normalized.split())
    
    # Score each category
    category_scores = {}
    
    for category, keywords in KEYWORD_CATEGORIES.items():
        if category in master_categories or category == "Andet":
            score = 0
            matched_keywords = []
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                
                # Word boundary matching (most accurate)
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                if re.search(pattern, title_normalized):
                    score += 20  # High score for exact word match
                    matched_keywords.append(keyword)
                # Partial word match (e.g., "tomat" in "tomater")
                elif keyword_lower in title_normalized:
                    score += 10  # Medium score for partial match
                    matched_keywords.append(keyword)
                # Very loose match (beginning of words)
                elif any(word.startswith(keyword_lower) for word in title_normalized.split()):
                    score += 5  # Low score for starts-with
                    matched_keywords.append(keyword)
            
            if score > 0:
                category_scores[category] = {
                    'score': score,
                    'keywords': matched_keywords
                }
    
    # Return category with highest score (must have at least score of 5)
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1]['score'])
        
        # Only return if confidence is decent
        if best_category[1]['score'] >= 5:
            return best_category[0]
    
    # Fallback to Andet
    return "Andet"

def harmonize_categories(df):
    """Harmonize all categories to Rema1000 standard"""
    
    print("\n🔄 Harmonizing categories...")
    
    # Extract Rema1000 categories as master
    rema_products = df[df['store'] == 'Rema1000']
    master_categories = list(rema_products['category'].dropna().unique())
    master_categories.append("Andet")
    
    print(f"   Master categories ({len(master_categories)}): {', '.join(sorted(master_categories))}")
    
    # Track changes
    changed_by_type = {
        'mapped': 0,
        'title_categorized': 0,
        'kept_rema': 0,
        'kept_valid': 0,
        'failed_andet': 0
    }
    
    new_categories = []
    sample_categorizations = []  # Track samples for debugging
    failed_samples = []  # Track failed categorizations
    
    for idx, row in df.iterrows():
        current_cat = row['category']
        store = row['store']
        title = row['title']
        
        # Keep Rema1000 categories as-is
        if store == 'Rema1000' and pd.notna(current_cat) and current_cat != "":
            new_categories.append(current_cat)
            changed_by_type['kept_rema'] += 1
        
        # Map known categories
        elif pd.notna(current_cat) and current_cat in CATEGORY_MAP:
            mapped_cat = CATEGORY_MAP[current_cat]
            new_categories.append(mapped_cat)
            changed_by_type['mapped'] += 1
            
            # Sample
            if changed_by_type['mapped'] <= 3:
                sample_categorizations.append(f"      Mapped: '{current_cat}' → '{mapped_cat}' (Product: {title[:40]})")
        
        # Check if already valid
        elif pd.notna(current_cat) and current_cat != "" and current_cat in master_categories:
            new_categories.append(current_cat)
            changed_by_type['kept_valid'] += 1
        
        # Categorize by title
        else:
            cat = categorize_by_title(title, master_categories)
            new_categories.append(cat)
            
            if cat != "Andet":
                changed_by_type['title_categorized'] += 1
                
                # Sample (show first 10)
                if changed_by_type['title_categorized'] <= 10:
                    sample_categorizations.append(f"      By title: '{title[:60]}' → '{cat}'")
            else:
                changed_by_type['failed_andet'] += 1
                
                # Sample failed (show first 10)
                if changed_by_type['failed_andet'] <= 10:
                    failed_samples.append(f"      Failed: '{title[:60]}' → Andet")
    
    df['category'] = new_categories
    
    # Show samples
    if sample_categorizations:
        print("\n   ✅ Sample successful categorizations:")
        for sample in sample_categorizations:
            print(sample)
    
    if failed_samples:
        print("\n   ⚠️  Sample failed categorizations (couldn't find keywords):")
        for sample in failed_samples:
            print(sample)
    
    print(f"\n   📊 Categorization results:")
    print(f"      Kept Rema1000: {changed_by_type['kept_rema']}")
    print(f"      Mapped categories: {changed_by_type['mapped']}")
    print(f"      Kept valid: {changed_by_type['kept_valid']}")
    print(f"      Categorized by title: {changed_by_type['title_categorized']}")
    print(f"      Couldn't categorize (Andet): {changed_by_type['failed_andet']}")
    
    # Show success rate
    total_needed_categorization = changed_by_type['title_categorized'] + changed_by_type['failed_andet']
    if total_needed_categorization > 0:
        success_rate = (changed_by_type['title_categorized'] / total_needed_categorization) * 100
        print(f"\n   🎯 Success rate: {success_rate:.1f}% ({changed_by_type['title_categorized']}/{total_needed_categorization})")
    
    return df

# ==================== MAIN ====================

print("🐝 Merge Products with Category Harmonization")
print("=" * 60)

files = {
    "Aviser": "data/aviser_products.xlsx",
    "Rema1000": "data/rema1000_products.xlsx",
}

all_dfs = []

for name, path in files.items():
    if os.path.exists(path):
        df = pd.read_excel(path)
        print(f"\n✅ Loaded {name}: {len(df)} products")
        all_dfs.append(df)
    else:
        print(f"\n⚠️  {name} not found")

if not all_dfs:
    print("\n❌ No data files!")
    exit(1)

# Merge
merged = pd.concat(all_dfs, ignore_index=True)
print(f"\n📊 Combined: {len(merged)} products")

# Ensure columns
for col in ["title", "price", "category", "store", "remaining_days", "image_base64"]:
    if col not in merged.columns:
        merged[col] = None

# Keep only required columns
merged = merged[["title", "price", "category", "store", "remaining_days", "image_base64"]]

# Cleanup
merged = merged.dropna(subset=["title", "price"])
merged = merged[merged["title"].str.strip() != ""]
print(f"After cleanup: {len(merged)} products")

# Remove without images
merged = merged[merged["image_base64"].notna()]
print(f"With images: {len(merged)} products")

# HARMONIZE CATEGORIES
if HARMONIZE_CATEGORIES:
    merged = harmonize_categories(merged)

# Limit products
if len(merged) > MAX_TOTAL_PRODUCTS:
    print(f"\n⚠️  Limiting to {MAX_TOTAL_PRODUCTS} products")
    
    # Prioritize offers
    offers = merged[merged["remaining_days"].notna()].head(600)
    regular = merged[merged["remaining_days"].isna()].head(MAX_TOTAL_PRODUCTS - len(offers))
    merged = pd.concat([offers, regular], ignore_index=True)

# Sort
merged['sort_priority'] = merged['remaining_days'].notna().astype(int)
merged = merged.sort_values(['sort_priority', 'remaining_days', 'price'], 
                            ascending=[False, True, True])
merged = merged.drop('sort_priority', axis=1)

# Save
output = "data/products.xlsx"
merged.to_excel(output, index=False)

file_size_mb = os.path.getsize(output) / (1024 * 1024)

print(f"\n{'=' * 60}")
print(f"🐝 Merge Complete!")
print(f"{'=' * 60}")
print(f"Total Products:    {len(merged)}")
print(f"Stores:            {sorted(merged['store'].unique().tolist())}")
print(f"Categories:        {merged['category'].nunique()}")
print(f"Output File:       {output}")
print(f"File Size:         {file_size_mb:.2f} MB")
print(f"Timestamp:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"")

# Category breakdown
print("📊 Category Distribution:")
for cat, count in merged['category'].value_counts().head(15).items():
    pct = (count / len(merged)) * 100
    print(f"   • {cat}: {count} ({pct:.1f}%)")

print(f"\n{'=' * 60}")
