// receipt-engine.js — browser port of parse_receipt.py + match_receipt_items.py
//
// Runs on-device so receipt images never leave the phone.
// Kept behaviourally identical to the Python versions; the test suite at the
// bottom mirrors theirs case for case.

(function (global) {
  'use strict';

  // ══════════════════════════════════════════════════════════
  // PARSER
  // ══════════════════════════════════════════════════════════

  const STORE_PATTERNS = [
    [/rema\s*1000/i,               'Rema1000'],
    [/\bnetto\b/i,                 'Netto'],
    [/\blidl\b/i,                  'Lidl'],
    [/f[øo0]tex/i,                 'Føtex'],
    [/\bbilka\b/i,                 'Bilka'],
    [/\bmeny\b/i,                  'Meny'],
    [/superbrugsen/i,              'SuperBrugsen & Kvickly'],
    [/kvickly/i,                   'SuperBrugsen & Kvickly'],
    [/d[ae]gli.?brugsen/i,         'Brugsen'],
    [/\bbrugsen\b/i,               'Brugsen'],
    [/365\s*discount|coop\s*365/i, '365'],
    [/\bspar\b/i,                  'Spar'],
    [/min\s*k[øo]bmand/i,          'Min Kobmand'],
  ];

  const SKIP_RE = new RegExp([
    /^\s*i\s*alt\b/, /^\s*total\b/, /^\s*subtotal\b/,
    /^\s*at\s*betale\b/, /^\s*betalt\b/, /^\s*betaling\b/,
    /\bmoms\b/, /\bvat\b/,
    /^\s*dankort\b/, /^\s*visa\b/, /^\s*mastercard\b/,
    /^\s*kontant\b/, /^\s*mobilepay\b/, /^\s*byttepenge\b/,
    /\bcvr\b/, /\bkvittering\b/, /^\s*bon\b/, /\bbonnr\b/,
    /\bkassenr\b/, /\bekspedient\b/, /\bterminal\b/,
    /\bafrunding\b/, /\breturneres\b/, /\bbyttes\b/,
    /\btak for bes[øo]get\b/, /\bvel m[øo]dt\b/,
    /\bmedlemsnr\b/, /\bkundenr\b/, /\bbonuspoint\b/,
    /^\s*[-=_*]{3,}\s*$/,
  ].map(r => r.source).join('|'), 'i');

  const PANT_RE  = /^\s*pant\b/i;
  const RABAT_RE = /\b(rabat|tilbud|besparelse|medlemspris)\b/i;

  const ITEM_RE       = /^\s*(.+?)\s{2,}(-?\d{1,4}[.,]\d{2})\s*[A-Z]?\s*$/;
  const ITEM_LOOSE_RE = /^\s*([A-Za-zÆØÅæøå][^\d]{2,40}?)\s+(-?\d{1,4}[.,]\d{2})\s*[A-Z]?\s*$/;
  const QTY_RE        = /^\s*(\d{1,3})\s*(?:x|stk\.?\s*[aà]?|\*)\s*(\d{1,4}[.,]\d{2})\s*$/i;
  const WEIGHT_RE     = /^\s*(\d{1,3}[.,]\d{1,3})\s*(kg|g|l|ml)\s*(?:x|\*)\s*(\d{1,4}[.,]\d{2})/i;
  const NAME_WEIGHT_RE= /^\s*([A-Za-zÆØÅæøå][^\d]{2,40}?)\s{2,}(\d{1,3}[.,]\d{1,3})\s*(kg|g|l|ml)\s*(?:x|\*)\s*(\d{1,4}[.,]\d{2})\s*$/i;
  const BARE_PRICE_RE = /^\s*(-?\d{1,4}[.,]\d{2})\s*[A-Z]?\s*$/;
  const DATE_RE       = /(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})/;

  function num(s) {
    s = String(s);
    return (s.split(',').length - 1) === 1
      ? parseFloat(s.replace(/\./g, '').replace(',', '.'))
      : parseFloat(s.replace(/,/g, ''));
  }

  function detectStore(lines) {
    const head = lines.slice(0, 12).join(' ');
    for (const [re, store] of STORE_PATTERNS) if (re.test(head)) return store;
    return null;
  }

  function detectDate(lines) {
    const scan = lines.slice(0, 20).concat(lines.slice(-20));
    for (const line of scan) {
      const m = DATE_RE.exec(line);
      if (!m) continue;
      let [, d, mo, y] = m;
      y = parseInt(y, 10); if (y < 100) y += 2000;
      const dt = new Date(y, parseInt(mo, 10) - 1, parseInt(d, 10));
      if (dt.getFullYear() === y && dt.getMonth() === parseInt(mo, 10) - 1
          && y >= 2020 && y <= new Date().getFullYear() + 1) {
        const p = n => String(n).padStart(2, '0');
        return `${y}-${p(mo)}-${p(d)}`;
      }
    }
    return null;
  }

  function parseReceipt(text) {
    const lines = String(text || '').split(/\r?\n/)
      .map(l => l.replace(/\s+$/, '')).filter(l => l.trim());

    const store = detectStore(lines);
    const date  = detectDate(lines);

    const items = [], skipped = [], warnings = [];
    let deposits = 0, discounts = 0;

    let end = lines.length;
    for (let i = 0; i < lines.length; i++) {
      if (/^\s*(i\s*alt|total|at\s*betale)\b/i.test(lines[i])) { end = i; break; }
    }

    let i = 0;
    while (i < end) {
      const line = lines[i];

      if (SKIP_RE.test(line)) { skipped.push(line.trim()); i++; continue; }

      // Weighted goods where the total is on the next line
      const nw = NAME_WEIGHT_RE.exec(line);
      if (nw && i + 1 < end) {
        const bp = BARE_PRICE_RE.exec(lines[i + 1]);
        if (bp) {
          items.push({
            name: nw[1].replace(/\s{2,}/g, ' ').replace(/^[\s.\-*]+|[\s.\-*]+$/g, '').toUpperCase(),
            line_total: Math.round(num(bp[1]) * 100) / 100,
            qty: 1,
            unit_price: Math.round(num(nw[4]) * 100) / 100,
            kind: 'weighted',
          });
          i += 2; continue;
        }
      }

      const m = ITEM_RE.exec(line) || ITEM_LOOSE_RE.exec(line);
      if (!m) { skipped.push(line.trim()); i++; continue; }

      const name = m[1].replace(/\s{2,}/g, ' ').replace(/^[\s.\-*]+|[\s.\-*]+$/g, '');
      const total = num(m[2]);
      if (!isFinite(total)) { skipped.push(line.trim()); i++; continue; }

      if (PANT_RE.test(name))  { deposits  += total; i++; continue; }
      if (RABAT_RE.test(name) || total < 0) { discounts += total; i++; continue; }
      if (name.replace(/[^A-Za-zÆØÅæøå]/g, '').length < 3) {
        skipped.push(line.trim()); i++; continue;
      }

      let qty = 1, unitPrice = total, kind = 'item';
      if (i + 1 < end) {
        const nxt = lines[i + 1];
        const qm = QTY_RE.exec(nxt), wm = WEIGHT_RE.exec(nxt);
        if (qm)      { qty = parseInt(qm[1], 10); unitPrice = num(qm[2]); i++; }
        else if (wm) { kind = 'weighted'; unitPrice = num(wm[3]); i++; }
      }

      items.push({
        name: name.toUpperCase(),
        line_total: Math.round(total * 100) / 100,
        qty, unit_price: Math.round(unitPrice * 100) / 100, kind,
      });
      i++;
    }

    if (!store)        warnings.push('Butik ikke genkendt');
    if (!items.length) warnings.push('Ingen varelinjer fundet');

    let printedTotal = null;
    for (const line of lines.slice(end, end + 6)) {
      if (/^\s*(i\s*alt|total|at\s*betale)\b/i.test(line)) {
        const m = /(\d{1,4}[.,]\d{2})/.exec(line);
        if (m) { printedTotal = num(m[1]); break; }
      }
    }
    if (printedTotal != null) {
      const summed = items.reduce((s, x) => s + x.line_total, 0) + deposits + discounts;
      if (Math.abs(summed - printedTotal) > 0.5) {
        warnings.push(`Sum stemmer ikke: linjer ${summed.toFixed(2)} vs bon ${printedTotal.toFixed(2)}`);
      }
    }

    return {
      store, date, items,
      deposits: Math.round(deposits * 100) / 100,
      discounts: Math.round(discounts * 100) / 100,
      printed_total: printedTotal, skipped, warnings,
    };
  }

  // ══════════════════════════════════════════════════════════
  // MATCHER
  // ══════════════════════════════════════════════════════════

  const NGRAM_N = 4, NGRAM_WEIGHT = 0.45, MIN_SCORE = 0.30, AMBIGUOUS_GAP = 0.06;

  const ABBREV = [
    [/\bhk\b/g, 'hakket'], [/\boko\b/g, 'okologisk'], [/\bokol\b/g, 'okologisk'],
    [/\bskivost\b/g, 'skiveost'], [/\bfl\b/g, 'flaske'],
    [/\bm\//g, 'med '], [/\bu\//g, 'uden '],
    [/\bkyll\b/g, 'kylling'], [/\bsvine\b/g, 'svinekod'], [/\bokse\b/g, 'oksekod'],
    [/\brugbr\b/g, 'rugbrod'], [/\bmineralv\b/g, 'mineralvand'],
    [/\bchok\b/g, 'chokolade'],
  ];

  const STOPWORDS = new Set([
    'stk','pk','pakke','pose','bakke','flaske','glas','dase',
    'ca','kg','gr','gram','liter','ltr','cl','dl',
    'dansk','danske','frisk','friske','naturel','original',
    'med','uden','og','til','fra','af','the','and',
    'vare','varer','produkt','tilbud','spar','pris',
  ]);

  function foldDanish(s) {
    return s.replace(/æ/g, 'ae').replace(/ø/g, 'o').replace(/å/g, 'aa');
  }

  function normalise(text) {
    let s = String(text || '').toLowerCase();
    s = s.replace(/\./g, ' ').replace(/\//g, ' / ');
    s = foldDanish(s);
    for (const [re, full] of ABBREV) s = s.replace(re, full);
    s = s.replace(/[^\w%\s]/g, ' ');
    return s.split(/\s+/).filter(Boolean).join(' ');
  }

  // OCR confuses these on thermal paper. Repair only inside words that are
  // otherwise letters, so "500G" is still treated as a size and dropped.
  const OCR_MAP = { '0': 'o', '1': 'i', '5': 's', '8': 'b', '6': 'g' };
  function repairOcr(word) {
    const letters = (word.match(/[a-zæøå]/g) || []).length;
    const digits  = (word.match(/\d/g) || []).length;
    if (digits && letters >= 3 && letters > digits)
      return word.replace(/[015 86]/g, c => OCR_MAP[c] || c);
    return word;
  }

  function tokenize(text) {
    const out = [];
    for (let w of normalise(text).split(' ')) {
      w = repairOcr(w);
      if (w.length < 3 || STOPWORDS.has(w)) continue;
      if (/\d/.test(w)) continue;
      for (const suf of ['erne','ene','er','en','et','e']) {
        if (w.length > 5 && w.endsWith(suf)) { w = w.slice(0, -suf.length); break; }
      }
      out.push(w);
    }
    return out;
  }

  function charNgrams(word, n) {
    n = n || NGRAM_N;
    if (word.length <= n) return [word];
    const out = [];
    for (let i = 0; i <= word.length - n; i++) out.push(word.slice(i, i + n));
    return out;
  }

  function buildBag(text) {
    const bag = new Map();
    for (const tok of tokenize(text)) {
      bag.set(tok, (bag.get(tok) || 0) + 1);
      for (const g of charNgrams(tok))
        bag.set('#' + g, (bag.get('#' + g) || 0) + NGRAM_WEIGHT);
    }
    return bag;
  }

  function cosine(a, b, idf) {
    if (!a.size || !b.size) return 0;
    let num = 0;
    for (const [t, va] of a) {
      const vb = b.get(t);
      if (vb === undefined) continue;
      const w = idf.get(t) || 1;
      num += va * vb * w * w;
    }
    if (!num) return 0;
    let na = 0, nb = 0;
    for (const [t, v] of a) { const w = idf.get(t) || 1; na += (v * w) ** 2; }
    for (const [t, v] of b) { const w = idf.get(t) || 1; nb += (v * w) ** 2; }
    return (na && nb) ? num / (Math.sqrt(na) * Math.sqrt(nb)) : 0;
  }

  class ReceiptMatcher {
    constructor(products) {
      this.products = products || [];
      this.bags = this.products.map(p => buildBag(p.title || ''));

      const df = new Map();
      for (const bag of this.bags)
        for (const t of bag.keys()) df.set(t, (df.get(t) || 0) + 1);
      const n = Math.max(1, this.bags.length);
      this.idf = new Map();
      for (const [t, f] of df) this.idf.set(t, Math.log(n / (1 + f)) + 1);

      this.byStore = new Map();
      this.products.forEach((p, i) => {
        const k = p.store;
        if (!this.byStore.has(k)) this.byStore.set(k, []);
        this.byStore.get(k).push(i);
      });
    }

    match(receiptName, store, price) {
      const bag = buildBag(receiptName);
      if (!bag.size) return null;

      const pool = this.byStore.get(store) || this.products.map((_, i) => i);
      const scored = [];
      for (const i of pool) {
        let s = cosine(bag, this.bags[i], this.idf);
        if (s <= 0) continue;
        if (price != null) {
          const pp = parseFloat(this.products[i].price);
          if (isFinite(pp)) {
            const d = Math.abs(pp - parseFloat(price));
            if (d < 0.5) s += 0.12; else if (d < 2.0) s += 0.04;
          }
        }
        scored.push([s, i]);
      }
      if (!scored.length) return null;
      scored.sort((a, b) => b[0] - a[0]);
      if (scored[0][0] < MIN_SCORE) return null;

      const runner = scored[1] || null;
      return {
        product: this.products[scored[0][1]],
        score: Math.round(scored[0][0] * 1000) / 1000,
        ambiguous: !!(runner && (scored[0][0] - runner[0]) < AMBIGUOUS_GAP),
        runner_up: runner ? this.products[runner[1]] : null,
      };
    }

    matchReceipt(parsed, store) {
      store = store || parsed.store;
      return (parsed.items || []).map(item => {
        const hit = this.match(item.name, store, item.unit_price);
        return {
          receipt: item,
          match: hit ? hit.product : null,
          score: hit ? hit.score : 0,
          ambiguous: hit ? hit.ambiguous : false,
          status: hit ? (hit.ambiguous ? 'ambiguous' : 'matched') : 'unmatched',
        };
      });
    }
  }

  global.BeeleeReceipt = { parseReceipt, ReceiptMatcher, normalise, tokenize };

})(typeof window !== 'undefined' ? window : globalThis);

// ══════════════════════════════════════════════════════════
// Node test suite — mirrors the Python fixtures exactly
// ══════════════════════════════════════════════════════════
if (typeof module !== 'undefined' && require.main === module) {
  const { parseReceipt, ReceiptMatcher } = globalThis.BeeleeReceipt;

  const REMA = `REMA 1000
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
Tak for besøget`;

  const NETTO = `Netto
Åboulevard 21
1960 Frederiksberg C
--------------------------------
SKYR NATUREL              12,50
KAFFE 400G                39,95
LAKSEFILET                0,486 kg x 129,95
                          63,16
ØKO GULERØDDER             9,95
RABAT MEDLEM              -5,00
================================
I ALT                    120,56`;

  const MENY = `MENY Østerfælled Torv
20.09.2026
--------------------------------
HAVREGRYN 1KG   12,95
DANBO OST 45+   29,95
TOMATER LØSVÆGT 18,50
  0,650 kg x 28,46
--------------------------------
TOTAL           61,40`;

  const NOISE = `R3MA 1OOO
%%%%%%%%
999
--------------------------------
I ALT   0,00`;

  let pass = 0, total = 0;
  const check = (ok, label, extra) => {
    total++; if (ok) pass++;
    console.log(`${ok ? '✅' : '❌'} ${label}${extra ? '  ' + extra : ''}`);
  };

  console.log('🧾 Parser — parity with parse_receipt.py');
  console.log('='.repeat(62));
  for (const [label, text, store, n] of [
    ['REMA — qty line + pant',      REMA,  'Rema1000', 5],
    ['Netto — split weight + rabat', NETTO, 'Netto',    4],
    ['MENY — single-space columns',  MENY,  'Meny',     3],
    ['Pure OCR noise',               NOISE, null,       0],
  ]) {
    const r = parseReceipt(text);
    check(r.store === store && r.items.length === n, label,
          `store=${r.store} items=${r.items.length}`);
  }

  console.log('\n🔗 Matcher — parity with match_receipt_items.py');
  console.log('='.repeat(62));
  const CAT = [
    { title: 'MINIMÆLK 0,4% FEDT',        store: 'Rema1000', price: 7.95 },
    { title: 'LETMÆLK 1,5% FEDT',         store: 'Rema1000', price: 8.50 },
    { title: 'SØDMÆLK 3,5%',              store: 'Rema1000', price: 9.50 },
    { title: 'SOLSIKKE RUGBRØD',          store: 'Rema1000', price: 18.95 },
    { title: 'KERNEGROVBRØD',             store: 'Rema1000', price: 17.50 },
    { title: 'ØKO. BANANER FAIRTRADE',    store: 'Rema1000', price: 12.25 },
    { title: 'BANAN',                     store: 'Rema1000', price: 3.50 },
    { title: 'GULERØDDER',                store: 'Rema1000', price: 5.95 },
    { title: 'SNACK GULERØDDER',          store: 'Rema1000', price: 12.95 },
    { title: 'HK. OKSEKØD 8-12%',         store: 'Rema1000', price: 32.00 },
    { title: 'HK. KYLLINGEKØD 4-7%',      store: 'Rema1000', price: 28.00 },
    { title: 'KYLLINGEBRYSTFILET',        store: 'Rema1000', price: 45.00 },
    { title: 'SKYR NATUREL',              store: 'Netto',    price: 12.50 },
    { title: 'SKYR VANILJE',              store: 'Netto',    price: 13.50 },
    { title: 'KAFFE SPECIALRISTET 400 G', store: 'Netto',    price: 39.95 },
    { title: 'DANSKE LAKSEFILETER',       store: 'Netto',    price: 63.16 },
    { title: 'ØKO. GULERØDDER',           store: 'Netto',    price: 9.95 },
    { title: 'HAVREGRYN 1 KG',            store: 'Meny',     price: 12.95 },
    { title: 'DANBO SKIVEOST 45+',        store: 'Meny',     price: 29.95 },
    { title: 'TOMATER LØSVÆGT',           store: 'Meny',     price: 18.50 },
    { title: 'AFFALDSPOSER 20 LTR',       store: 'Rema1000', price: 15.00 },
  ];
  const m = new ReceiptMatcher(CAT);
  for (const [line, store, price, want] of [
    ['MINIMÆLK 0,4%',    'Rema1000',  7.95, 'MINIMÆLK 0,4% FEDT'],
    ['RUGBRØD SOLSIKKE', 'Rema1000', 18.95, 'SOLSIKKE RUGBRØD'],
    ['ØKO BANANER',      'Rema1000', 12.25, 'ØKO. BANANER FAIRTRADE'],
    ['GULERØDDER 1KG',   'Rema1000',  5.95, 'GULERØDDER'],
    ['HAKKET OKSEKØD',   'Rema1000', 32.00, 'HK. OKSEKØD 8-12%'],
    ['HK. OKSEKØD',      'Rema1000', 32.00, 'HK. OKSEKØD 8-12%'],
    ['SKYR NATUREL',     'Netto',    12.50, 'SKYR NATUREL'],
    ['KAFFE 400G',       'Netto',    39.95, 'KAFFE SPECIALRISTET 400 G'],
    ['LAKSEFILET',       'Netto',    63.16, 'DANSKE LAKSEFILETER'],
    ['ØKO GULERØDDER',   'Netto',     9.95, 'ØKO. GULERØDDER'],
    ['HAVREGRYN 1KG',    'Meny',     12.95, 'HAVREGRYN 1 KG'],
    ['DANBO OST 45+',    'Meny',     29.95, 'DANBO SKIVEOST 45+'],
    ['TOMATER LØSVÆGT',  'Meny',     18.50, 'TOMATER LØSVÆGT'],
    ['XYZZY VARE 999',   'Rema1000', 99.00, null],
    ['AFFALDSPOSER 20L', 'Rema1000', 15.00, 'AFFALDSPOSER 20 LTR'],
    // OCR damage
    ['GULER0DDER',        'Rema1000', null, 'GULERØDDER'],
    ['KYLL1NGEBRYSTFILET','Rema1000', null, 'KYLLINGEBRYSTFILET'],
    ['S0LSIKKE RUGBR0D',  'Rema1000', null, 'SOLSIKKE RUGBRØD'],
    ['500G PASTA',        'Rema1000', null, null],
  ]) {
    const hit = m.match(line, store, price);
    const got = hit ? hit.product.title : null;
    check(got === want, line.padEnd(20), `-> ${got}`);
  }

  console.log('='.repeat(62));
  console.log(`${pass}/${total} passed`);
  process.exit(pass === total ? 0 : 1);
}
