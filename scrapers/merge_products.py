"""
merge_products_with_categories.py
----------------------------------
Merges products AND harmonizes categories automatically!
"""

import pandas as pd
import os
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

# Keywords for auto-categorization (EXPANDED!)
KEYWORD_CATEGORIES = {
    "Frugt og grønt": [
        # Danish
        "tomat", "agurk", "salat", "peber", "løg", "hvidløg", "kartoffel", "kartofler",
        "gulerod", "gulerødder", "broccoli", "blomkål", "squash", "zucchini", "aubergine",
        "spinat", "grønkål", "rosenkål", "spidskål", "hvidkål", "rødkål", "blomme",
        "æble", "æbler", "banan", "bananer", "appelsin", "appelsiner", "pære", "pærer",
        "citron", "citroner", "lime", "avocado", "druer", "jordbær", "hindbær", "blåbær",
        "melon", "vandmelon", "ananas", "kiwi", "mango", "paprika", "chili",
        "persille", "basilikum", "koriander", "timian", "rosmarin", "dild",
        "grøn", "grønt", "frugt", "grøntsag", "bær",
        # English
        "tomato", "cucumber", "lettuce", "pepper", "onion", "garlic", "potato", "potatoes",
        "carrot", "carrots", "broccoli", "cauliflower", "zucchini", "eggplant", "aubergine",
        "spinach", "kale", "cabbage", "brussels",
        "apple", "apples", "banana", "bananas", "orange", "oranges", "pear", "pears",
        "lemon", "lemons", "lime", "avocado", "grapes", "strawberry", "raspberry", "blueberry",
        "melon", "watermelon", "pineapple", "kiwi", "mango", "bell pepper",
        "parsley", "basil", "cilantro", "thyme", "rosemary", "dill",
        "vegetable", "vegetables", "fruit", "fruits", "berry", "berries", "salad"
    ],
    
    "Kød": [
        # Danish
        "oksekød", "kalvekød", "svinekød", "lammekød", "kylling", "kyllinge",
        "bacon", "pølse", "pølser", "medister", "hamburger", "hakket", "hakkekød",
        "bøf", "steak", "koteletter", "kotelet", "schnitzel", "skinke",
        "lever", "hjerter", "kødfars", "Fars", "indmad",
        "kalkun", "and", "gås", "kød",
        # English
        "beef", "veal", "pork", "lamb", "chicken", "turkey", "duck", "goose",
        "bacon", "sausage", "sausages", "minced", "mince", "ground beef",
        "steak", "chop", "chops", "schnitzel", "ham", "meat", "patties"
    ],
    
    "Fisk": [
        # Danish
        "laks", "ørred", "torsk", "tuna", "tunfisk", "makrel", "sild", "sardiner",
        "rejer", "reje", "hummer", "krabbe", "muslinger", "østers", "blæksprutte",
        "fiskefillet", "fisk", "røget", "gravet",
        # English
        "salmon", "trout", "cod", "tuna", "mackerel", "herring", "sardine", "sardines",
        "shrimp", "shrimps", "prawn", "prawns", "lobster", "crab", "mussels", "oyster",
        "squid", "octopus", "fish", "fillet", "smoked", "seafood"
    ],
    
    "Mejeri": [
        # Danish
        "mælk", "skummetmælk", "sødmælk", "letmælk", "minimælk",
        "ost", "cheddar", "mozzarella", "feta", "brie", "parmigiano", "parmesan",
        "yoghurt", "yogurt", "skyr", "ymer", "kærnemælk",
        "smør", "margarine", "fløde", "piskefløde", "creme fraiche", "cremefraiche",
        "kvark", "hytteost", "cottage cheese", "ricotta",
        # English
        "milk", "skim milk", "whole milk", "semi-skimmed",
        "cheese", "yogurt", "yoghurt", "butter", "cream", "whipping cream",
        "sour cream", "buttermilk", "cottage", "curd", "dairy"
    ],
    
    "Brød og kager": [
        # Danish
        "brød", "rugbrød", "franskbrød", "ciabatta", "focaccia",
        "rundstykke", "rundstykker", "bolle", "boller", "morgenbolle",
        "kage", "wienerbrød", "croissant", "kanelsngl", "kanel", "snegl",
        "bagel", "toast", "knækbrød", "crispbread", "kiks", "småkager",
        "muffin", "brownie", "tærte", "lagkage",
        # English
        "bread", "rye bread", "french bread", "baguette", "roll", "rolls", "bun", "buns",
        "cake", "danish", "croissant", "cinnamon", "bagel", "toast", "crispbread",
        "cookie", "cookies", "biscuit", "biscuits", "cracker", "crackers",
        "muffin", "brownie", "pie", "pastry"
    ],
    
    "Drikkevarer": [
        # Danish
        "vand", "mineralvand", "kildevand", "danskvand",
        "juice", "appelsinjuice", "æblejuice",
        "sodavand", "cola", "pepsi", "fanta", "sprite", "cocio",
        "kaffe", "te", "kakao", "chokolade",
        "mælk", "smoothie", "energidrik", "sportsdrik",
        "øl", "pilsner", "vin", "rødvin", "hvidvin", "champagne",
        # English
        "water", "mineral water", "sparkling water",
        "juice", "orange juice", "apple juice",
        "soda", "soft drink", "cola", "lemonade",
        "coffee", "tea", "cocoa", "chocolate milk",
        "smoothie", "energy drink", "sports drink",
        "beer", "wine", "red wine", "white wine", "champagne", "beverage", "drink"
    ],
    
    "Slik og snacks": [
        # Danish
        "chips", "popcorn", "nødder", "peanuts", "cashew", "mandler",
        "chokolade", "slik", "vingummi", "lakrids", "bolcher", "tyggegummi",
        "guld barre", "twix", "snickers", "mars", "kitkat", "bounty",
        "haribo", "malaco", "toms",
        # English
        "chips", "crisps", "popcorn", "nuts", "peanuts", "cashews", "almonds",
        "chocolate", "candy", "sweets", "gummy", "liquorice", "licorice",
        "chewing gum", "lollipop", "snack", "snacks"
    ],
    
    "Frost": [
        # Danish
        "frosne", "frost", "is", "ispinde", "isterninger",
        "pizza", "lasagne", "pommes frites", "grøntsager frosne",
        # English
        "frozen", "ice cream", "popsicle", "ice cubes",
        "frost", "freezer"
    ],
    
    "Morgenmad": [
        # Danish
        "cornflakes", "müsli", "musli", "havregryn", "havre", "grød",
        "honning", "marmelade", "syltetøj", "nutella", "pålæg",
        "morgenmad",
        # English
        "cereal", "cornflakes", "muesli", "granola", "oatmeal", "oats", "porridge",
        "honey", "jam", "marmalade", "spread", "breakfast"
    ],
    
    "Kolonial": [
        # Danish
        "pasta", "spaghetti", "macaroni", "penne", "fusilli",
        "ris", "risotto", "basmati", "jasmin",
        "mel", "hvedemel", "sukker", "salt", "peber",
        "olie", "olivenolie", "rapsolie", "eddike", "balsamico",
        "sauce", "ketchup", "mayo", "mayonnaise", "remoulade", "dressing",
        "bouillon", "fond", "krydderi", "krydderier",
        "dåse", "hermetik", "konserves",
        # English
        "pasta", "spaghetti", "macaroni", "penne",
        "rice", "risotto", "basmati", "jasmine",
        "flour", "sugar", "salt", "pepper", "spice", "spices",
        "oil", "olive oil", "vinegar", "balsamic",
        "sauce", "ketchup", "mayo", "mayonnaise", "dressing",
        "stock", "broth", "bouillon", "seasoning",
        "canned", "tinned", "can"
    ]
}

# ==================== FUNCTIONS ====================

def categorize_by_title(title, master_categories):
    """Categorize based on product title with smart matching"""
    if pd.isna(title):
        return "Andet"
    
    title_lower = title.lower()
    
    # Score each category
    category_scores = {}
    
    for category, keywords in KEYWORD_CATEGORIES.items():
        if category in master_categories or category == "Andet":
            score = 0
            matched_keywords = []
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                
                # Exact word match (highest score)
                if f" {keyword_lower} " in f" {title_lower} ":
                    score += 10
                    matched_keywords.append(keyword)
                # Start of title match
                elif title_lower.startswith(keyword_lower):
                    score += 8
                    matched_keywords.append(keyword)
                # End of title match
                elif title_lower.endswith(keyword_lower):
                    score += 7
                    matched_keywords.append(keyword)
                # Contains match
                elif keyword_lower in title_lower:
                    score += 5
                    matched_keywords.append(keyword)
            
            if score > 0:
                category_scores[category] = {
                    'score': score,
                    'keywords': matched_keywords
                }
    
    # Return category with highest score
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1]['score'])
        
        # Debug output for low confidence
        if best_category[1]['score'] < 5:
            # Low confidence, might want to review
            pass
        
        return best_category[0]
    
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
                
                # Sample
                if changed_by_type['title_categorized'] <= 5:
                    sample_categorizations.append(f"      By title: '{title[:50]}' → '{cat}'")
            else:
                changed_by_type['failed_andet'] += 1
    
    df['category'] = new_categories
    
    # Show samples
    if sample_categorizations:
        print("\n   Sample categorizations:")
        for sample in sample_categorizations:
            print(sample)
    
    print(f"\n   ✅ Categorization results:")
    print(f"      Kept Rema1000: {changed_by_type['kept_rema']}")
    print(f"      Mapped categories: {changed_by_type['mapped']}")
    print(f"      Kept valid: {changed_by_type['kept_valid']}")
    print(f"      Categorized by title: {changed_by_type['title_categorized']}")
    print(f"      Couldn't categorize (Andet): {changed_by_type['failed_andet']}")
    
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
