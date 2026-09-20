"""
parse_receipt.py
----------------
Turns OCR text from a Danish grocery receipt into structured lines:

    store, date, [(name, unit_price, qty, line_total), ...]

This is the half of receipt scanning that has nothing to do with OCR.
Feed it text from Tesseract (browser or server) and it handles the Danish
receipt conventions: comma decimals, pant lines, rabat lines, quantity
sub-lines, weight lines, and the totals block.

Used standalone for testing:
    python scrapers/parse_receipt.py            # runs the built-in test suite

Or imported:
    from parse_receipt import parse_receipt
    result = parse_receipt(ocr_text)
"""

import re
from datetime import datetime

# ─────────────────── STORE DETECTION ───────────────────
# Matched against the first ~12 lines of the receipt.
STORE_PATTERNS = [
    (r"rema\s*1000",                      "Rema1000"),
    (r"\bnetto\b",                        "Netto"),
    (r"\blidl\b",                         "Lidl"),
    (r"f[øo0]tex",                        "Føtex"),
    (r"\bbilka\b",                        "Bilka"),
    (r"\bmeny\b",                         "Meny"),
    (r"superbrugsen",                     "SuperBrugsen & Kvickly"),
    (r"kvickly",                          "SuperBrugsen & Kvickly"),
    (r"d[ae]gli.?brugsen",                "Brugsen"),
    (r"\bbrugsen\b",                      "Brugsen"),
    (r"365\s*discount|coop\s*365",        "365"),
    (r"\bspar\b",                         "Spar"),
    (r"min\s*k[øo]bmand",                 "Min Kobmand"),
]

# ─────────────────── LINES TO IGNORE ───────────────────
# Totals, tax, payment, loyalty — everything that isn't a product.
SKIP_PATTERNS = [
    r"^\s*i\s*alt\b", r"^\s*total\b", r"^\s*subtotal\b",
    r"^\s*at\s*betale\b", r"^\s*betalt\b", r"^\s*betaling\b",
    r"\bmoms\b", r"\bvat\b",
    r"^\s*dankort\b", r"^\s*visa\b", r"^\s*mastercard\b",
    r"^\s*kontant\b", r"^\s*mobilepay\b", r"^\s*byttepenge\b",
    r"\bcvr\b", r"\bkvittering\b", r"^\s*bon\b", r"\bbonnr\b",
    r"\bkassenr\b", r"\bekspedient\b", r"\bterminal\b",
    r"\bafrunding\b", r"\breturneres\b", r"\bbyttes\b",
    r"\btak for bes[øo]get\b", r"\bvel m[øo]dt\b",
    r"\bmedlemsnr\b", r"\bkundenr\b", r"\bbonuspoint\b",
    r"^\s*[-=_*]{3,}\s*$",              # separator rules
    r"^\s*$",
]
SKIP_RE = re.compile("|".join(SKIP_PATTERNS), re.I)

# Deposit and discount lines — real money, but not products
PANT_RE   = re.compile(r"^\s*pant\b", re.I)
RABAT_RE  = re.compile(r"\b(rabat|tilbud|besparelse|medlemspris)\b", re.I)

# ─────────────────── LINE SHAPES ───────────────────
# "MINIMÆLK 0,4%              7,95"   product + total
ITEM_RE = re.compile(
    r"^\s*(?P<name>.+?)\s{2,}(?P<price>-?\d{1,4}[.,]\d{2})\s*[A-Z]?\s*$"
)
# Same, tolerating a single space when the name has no trailing digits
ITEM_LOOSE_RE = re.compile(
    r"^\s*(?P<name>[A-Za-zÆØÅæøå][^\d]{2,40}?)\s+(?P<price>-?\d{1,4}[.,]\d{2})\s*[A-Z]?\s*$"
)
# "  2 x 12,25"  or  "2 stk a 12,25"
QTY_RE = re.compile(
    r"^\s*(?P<qty>\d{1,3})\s*(?:x|stk\.?\s*[aà]?|\*)\s*(?P<unit>\d{1,4}[.,]\d{2})\s*$",
    re.I
)
# "  0,486 kg x 29,95 /kg"
WEIGHT_RE = re.compile(
    r"^\s*(?P<w>\d{1,3}[.,]\d{1,3})\s*(?P<unit_t>kg|g|l|ml)\s*(?:x|\*)\s*"
    r"(?P<unit>\d{1,4}[.,]\d{2})",
    re.I
)
# "LAKSEFILET        0,486 kg x 129,95"  — total sits on the NEXT line
NAME_WEIGHT_RE = re.compile(
    r"^\s*(?P<name>[A-Za-zÆØÅæøå][^\d]{2,40}?)\s{2,}"
    r"(?P<w>\d{1,3}[.,]\d{1,3})\s*(?P<unit_t>kg|g|l|ml)\s*(?:x|\*)\s*"
    r"(?P<unit>\d{1,4}[.,]\d{2})\s*$",
    re.I
)
# A bare price on its own line, e.g. the total for the line above
BARE_PRICE_RE = re.compile(r"^\s*(?P<price>-?\d{1,4}[.,]\d{2})\s*[A-Z]?\s*$")

DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})")


def _num(s):
    """Danish decimal comma -> float."""
    return float(str(s).replace(".", "").replace(",", ".")) \
        if str(s).count(",") == 1 else float(str(s).replace(",", ""))


def detect_store(lines):
    head = " ".join(lines[:12]).lower()
    for pattern, store in STORE_PATTERNS:
        if re.search(pattern, head):
            return store
    return None


def detect_date(lines):
    for line in lines[:20] + lines[-20:]:
        m = DATE_RE.search(line)
        if not m:
            continue
        d, mo, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            dt = datetime(y, int(mo), int(d))
            # Ignore anything implausible — OCR mangles digits
            if 2020 <= dt.year <= datetime.now().year + 1:
                return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_receipt(text):
    """
    Parse OCR text into {store, date, items, skipped, warnings}.

    Each item: {name, line_total, qty, unit_price, kind}
      kind: 'item' | 'weighted'
    """
    raw_lines = [l.rstrip() for l in (text or "").splitlines()]
    lines = [l for l in raw_lines if l.strip()]

    store = detect_store(lines)
    date  = detect_date(lines)

    items, skipped, warnings = [], [], []
    deposits, discounts = 0.0, 0.0

    # Stop at the totals block — anything after is payment detail
    end = len(lines)
    for i, line in enumerate(lines):
        if re.match(r"^\s*(i\s*alt|total|at\s*betale)\b", line, re.I):
            end = i
            break

    i = 0
    while i < end:
        line = lines[i]

        if SKIP_RE.search(line):
            skipped.append(line.strip())
            i += 1
            continue

        # Weighted goods where the total is printed on the following line
        nw = NAME_WEIGHT_RE.match(line)
        if nw and i + 1 < end:
            bp = BARE_PRICE_RE.match(lines[i + 1])
            if bp:
                nm = re.sub(r"\s{2,}", " ", nw.group("name")).strip(" .-*")
                items.append({
                    "name": nm.upper(),
                    "line_total": round(_num(bp.group("price")), 2),
                    "qty": 1,
                    "unit_price": round(_num(nw.group("unit")), 2),
                    "kind": "weighted",
                })
                i += 2
                continue

        m = ITEM_RE.match(line) or ITEM_LOOSE_RE.match(line)
        if not m:
            skipped.append(line.strip())
            i += 1
            continue

        name  = re.sub(r"\s{2,}", " ", m.group("name")).strip(" .-*")
        try:
            total = _num(m.group("price"))
        except ValueError:
            skipped.append(line.strip())
            i += 1
            continue

        # Deposit and discount lines carry a price but aren't products
        if PANT_RE.match(name):
            deposits += total
            i += 1
            continue
        if RABAT_RE.search(name) or total < 0:
            discounts += total
            i += 1
            continue

        # A name that's basically a number is OCR noise
        if len(re.sub(r"[^A-Za-zÆØÅæøå]", "", name)) < 3:
            skipped.append(line.strip())
            i += 1
            continue

        qty, unit_price, kind = 1, total, "item"

        # Look ahead one line for a quantity or weight breakdown
        if i + 1 < end:
            nxt = lines[i + 1]
            qm = QTY_RE.match(nxt)
            wm = WEIGHT_RE.match(nxt)
            if qm:
                qty = int(qm.group("qty"))
                unit_price = _num(qm.group("unit"))
                i += 1
            elif wm:
                kind = "weighted"
                unit_price = _num(wm.group("unit"))
                qty = 1
                i += 1

        items.append({
            "name": name.upper(),
            "line_total": round(total, 2),
            "qty": qty,
            "unit_price": round(unit_price, 2),
            "kind": kind,
        })
        i += 1

    if not store:
        warnings.append("Butik ikke genkendt")
    if not items:
        warnings.append("Ingen varelinjer fundet")
    # Cross-check: do the line totals add up to the printed total?
    printed_total = None
    for line in lines[end:end + 6] if end < len(lines) else []:
        m = re.search(r"(\d{1,4}[.,]\d{2})", line)
        if m and re.match(r"^\s*(i\s*alt|total|at\s*betale)\b", line, re.I):
            printed_total = _num(m.group(1))
            break
    if printed_total is not None:
        summed = sum(x["line_total"] for x in items) + deposits + discounts
        if abs(summed - printed_total) > 0.5:
            warnings.append(
                f"Sum stemmer ikke: linjer {summed:.2f} vs bon {printed_total:.2f}"
            )

    return {
        "store": store,
        "date": date,
        "items": items,
        "deposits": round(deposits, 2),
        "discounts": round(discounts, 2),
        "printed_total": printed_total,
        "skipped": skipped,
        "warnings": warnings,
    }


# ──────────────────────────────────────────────
# Test suite — realistic Danish receipt shapes
# ──────────────────────────────────────────────
if __name__ == "__main__":

    REMA = """REMA 1000
NØRREBROGADE 155
2200 KØBENHAVN N
CVR: 25137619
Bon nr. 4471   Kasse 3
17-09-2026 17:42
--------------------------------
MINIMÆLK 0,4%             7,95
RUGBRØD SOLSIKKE         18,95
ØKO BANANER              24,50
  2 x 12,25
GULERØDDER 1KG            5,95
HAKKET OKSEKØD           32,00
PANT A                    3,00
--------------------------------
I ALT                    92,35
MOMS 25%                 18,47
DANKORT                  92,35
Tak for besøget"""

    NETTO = """Netto
Åboulevard 21
1960 Frederiksberg C
CVR 35954716
--------------------------------
SKYR NATUREL              12,50
KAFFE 400G                39,95
LAKSEFILET                0,486 kg x 129,95
                          63,16
ØKO GULERØDDER             9,95
RABAT MEDLEM              -5,00
================================
I ALT                    120,56
Betalt MobilePay         120,56"""

    MENY = """MENY Østerfælled Torv
Østerfælled Torv 39
2100 København Ø
Kvittering
20.09.2026
--------------------------------
HAVREGRYN 1KG   12,95
DANBO OST 45+   29,95
TOMATER LØSVÆGT 18,50
  0,650 kg x 28,46
--------------------------------
TOTAL           61,40"""

    NOISE = """R3MA 1OOO
%%%%%%%%
....
999
--------------------------------
||||
I ALT   0,00"""

    tests = [
        ("REMA 1000 — qty line + pant", REMA, "Rema1000", 5),
        ("Netto — weight line + rabat", NETTO, "Netto", 4),
        ("MENY — single-space columns", MENY, "Meny", 3),
        ("Pure OCR noise",              NOISE, None,     0),
    ]

    print("🧾 Danish receipt parser — test suite")
    print("=" * 64)
    passed = 0

    for label, text, want_store, want_items in tests:
        r = parse_receipt(text)
        ok_store = r["store"] == want_store
        ok_items = len(r["items"]) == want_items
        ok = ok_store and ok_items
        passed += ok
        print(f"\n{'✅' if ok else '❌'} {label}")
        print(f"   butik: {r['store']!r}  (forventet {want_store!r})")
        print(f"   varer: {len(r['items'])}  (forventet {want_items})")
        if r["date"]:
            print(f"   dato:  {r['date']}")
        for it in r["items"]:
            extra = f"  {it['qty']} x {it['unit_price']:.2f}" if it["qty"] > 1 else ""
            extra += "  (vægt)" if it["kind"] == "weighted" else ""
            print(f"     {it['name'][:30]:<30} {it['line_total']:>7.2f}{extra}")
        if r["deposits"]:
            print(f"     pant: {r['deposits']:.2f}")
        if r["discounts"]:
            print(f"     rabat: {r['discounts']:.2f}")
        for w in r["warnings"]:
            print(f"   ⚠️  {w}")

    print(f"\n{'=' * 64}")
    print(f"{passed}/{len(tests)} passed")
