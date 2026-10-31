import sys
sys.stdout.reconfigure(encoding="utf-8")
from text_frontend import normalize

def check(text, **kw):
    r = normalize(text, **kw)
    for t in r.transformations:
        assert r.original_text[slice(*t.original_span)] == t.original_text, "ORIGINAL SPAN MISMATCH"
        assert r.normalized_text[slice(*t.output_span)] == t.normalized_text, "OUTPUT SPAN MISMATCH"
    
    stray = any(c in r.normalized_text for c in "\u00a0\u2009\u202f")
    print(repr(text), "->", repr(r.normalized_text), r.status,
          [(w.code, w.severity) for w in r.warnings],
          "STRAY SPACE" if stray else "")

for t in [
    "I paid $12.50.",
    "(15% of users) and ($500 per month) and (2020)",
    "1984 pages, in 1984, Room 1984",
    "1900 1905 2005 2010",
    "see https://api.example.com/v2/item-3 now",
    "1\u2009000\u2009000 units",
    "call 555 0199",
    "5\u00a0apples",
    "e\u0301 costs $3",
    "👨‍👩‍👧 paid $5",
    "$5-$10",
    "12..34",
]:
    check(t)

check("₹1,00,000", locale="en-IN")
check("1,00,000", locale="en-US")