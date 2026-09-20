"""
product_key.py — the stable identity for a product across scrapes and devices.

IndexedDB hands out a fresh UUID on every refresh, so it can't be the key.
Barcodes are stable when we have them; otherwise a normalised title is the
best available. Readable rather than hashed, so rows are debuggable in psql.

The JavaScript version in index.html must produce byte-identical output —
parity is tested in test_product_key.py.
"""

import re

_FOLD = [("æ", "ae"), ("ø", "o"), ("å", "aa")]


def product_key(title, barcode=None):
    """'ean:5701234567890' when a barcode exists, else 't:normalised-title'."""
    if barcode is not None:
        bc = re.sub(r"\D", "", str(barcode))
        bc = bc.lstrip("0")
        if len(bc) >= 8:
            return "ean:" + bc

    s = str(title or "").lower()
    for a, b in _FOLD:
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return "t:" + (s[:120] or "ukendt")
