import sys
sys.stdout.reconfigure(encoding="utf-8")
from text_frontend import normalize

def check(text, expected_substrs=None, **kw):
    locale_str = kw.get("locale", "en-US")
    r = normalize(text, **kw)
    prev_orig = 0
    prev_out = 0
    for t in r.transformations:
        assert r.original_text[slice(*t.original_span)] == t.original_text, (
            f"ORIGINAL SPAN MISMATCH: expected {t.original_text!r}, got {r.original_text[slice(*t.original_span)]!r}"
        )
        assert r.normalized_text[slice(*t.output_span)] == t.normalized_text, (
            f"OUTPUT SPAN MISMATCH: expected {t.normalized_text!r}, got {r.normalized_text[slice(*t.output_span)]!r}"
        )
        assert t.original_span[0] >= prev_orig, "ORIGINAL SPANS NOT MONOTONIC"
        assert t.output_span[0] >= prev_out, "OUTPUT SPANS NOT MONOTONIC"
        prev_orig = t.original_span[1]
        prev_out = t.output_span[1]
    
    stray = any(c in r.normalized_text for c in "\u00a0\u2009\u202f")
    warn_info = [(w.code, w.severity) for w in r.warnings]
    stray_flag = " [STRAY SPACE!]" if stray else ""
    print(f"[{locale_str:5}] {text!r:45} -> {r.normalized_text!r} [{r.status}] {warn_info}{stray_flag}")
    
    if expected_substrs:
        for sub in expected_substrs:
            assert sub in r.normalized_text, f"Expected substring {sub!r} not in {r.normalized_text!r}"

print("=== Phase 2 Edge Case Verification ===")

edge_cases = [
    ("Open 24/7.", ["twenty-four seven"], {}),
    ("Wait 30m please.", ["thirty minutes"], {}),
    ("Run 30m sprints.", ["thirty meters"], {}),
    ("Rate is -$10.", ["negative ten dollars"], {}),
    ("Temps from -5 to 5 degrees.", ["negative five to five degrees"], {}),
    ("Work 9-5, Mon-Fri.", ["nine to five", "Monday to Friday"], {}),
    ("3/4/2023", ["March fourth", "twenty twenty-three"], {"locale": "en-US"}),
    ("3/4/2023", ["April third", "twenty twenty-three"], {"locale": "en-GB"}),
    ("the 3rd of July 2023", ["the third of July", "twenty twenty-three"], {}),
    ("Sept. 5, 2023", ["September fifth, twenty twenty-three"], {}),
    ("5ft 10in tall", ["five feet ten inches tall"], {}),
    ("Meet at 3 PM IST.", ["three P M I S T"], {}),
    ("Call at 3:15pm.", ["three fifteen P M"], {}),
    ("Chapter 3:16.", ["Chapter three, sixteen."], {}),
    ("Score was 3-2.", ["three to two"], {}),
    ("Dial 911.", ["nine one one"], {}),
    ("Call 112.", ["one one two"], {}),
    ("Call 1-800-555-0199.", ["one, eight oh oh, five five five, oh one nine nine"], {}),
    ("Pay $1,000-$2,000.", ["one thousand to two thousand dollars"], {}),
    ("Hours 9 a.m.-5 p.m.", ["nine A M to five P M."], {}),
    ("5-star hotel, T-shirt, X-ray.", ["five-star hotel, T-shirt, X-ray."], {}),
    ("Add 3/4 tsp salt and 2 tbsp oil.", ["three fourths teaspoon salt and two tablespoons oil."], {}),
]

for text, expected, kw in edge_cases:
    check(text, expected_substrs=expected, **kw)

print(f"\nAll {len(edge_cases)} edge cases verified successfully with zero invariant breaches.")
