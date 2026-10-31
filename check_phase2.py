import sys
sys.stdout.reconfigure(encoding="utf-8")
from text_frontend import normalize

def check(text, **kw):
    locale_str = kw.get("locale", "en-US")
    r = normalize(text, **kw)
    prev_orig = 0
    prev_out = 0
    for t in r.transformations:
        # Invariant 1: Slices match recorded text
        assert r.original_text[slice(*t.original_span)] == t.original_text, (
            f"ORIGINAL SPAN MISMATCH: expected {t.original_text!r}, got {r.original_text[slice(*t.original_span)]!r}"
        )
        assert r.normalized_text[slice(*t.output_span)] == t.normalized_text, (
            f"OUTPUT SPAN MISMATCH: expected {t.normalized_text!r}, got {r.normalized_text[slice(*t.output_span)]!r}"
        )
        # Invariant 2: Monotonic non-overlapping spans
        assert t.original_span[0] >= prev_orig, "ORIGINAL SPANS NOT MONOTONIC"
        assert t.output_span[0] >= prev_out, "OUTPUT SPANS NOT MONOTONIC"
        prev_orig = t.original_span[1]
        prev_out = t.output_span[1]
    
    stray = any(c in r.normalized_text for c in "\u00a0\u2009\u202f")
    warn_info = [(w.code, w.severity) for w in r.warnings]
    stray_flag = " [STRAY SPACE!]" if stray else ""
    print(f"[{locale_str:5}] {text!r:50} -> {r.normalized_text!r} [{r.status}] {warn_info}{stray_flag}")

print("=== Phase 2 Representative Verification ===")

cases = [
    # 1. Dates
    ("Meeting on Oct 29, 2023 at noon.", {}),
    ("Event on Mon, Oct 29, 2023.", {}),
    ("Born on 29 October 2023.", {"locale": "en-GB"}),
    ("10/11/2023", {"locale": "en-US"}),
    ("10/11/2023", {"locale": "en-GB"}),
    ("Dated 2023-10-29.", {}),
    ("Conference runs April 3-5, 2024.", {}),
    ("Born on 02/29/2024.", {}),
    ("Born on 02/29/2023.", {}),
    ("Due on 02/30/2023.", {}),
    ("Meeting on April 31, 2023.", {}),
    
    # 2. Times & Durations
    ("Breakfast at 9:05 AM.", {}),
    ("Meeting at 9:05 today.", {}),
    ("Lunch at 12:00 PM.", {}),
    ("Closed at 12:00 AM.", {}),
    ("Reset at 00:00.", {}),
    ("Departs at 12:01 PM.", {}),
    ("Flight lands at 14:30.", {}),
    ("Launch at 09:05:30 EST.", {}),
    ("Meeting at 14:30 +05:30.", {}),
    ("Hours are 2:00-4:00 PM.", {}),
    ("Trip duration: 2h 30m total.", {}),
    ("Wait 45s please.", {}),

    # 3. Fractions, Ratios, Ranges
    ("Use 1/2 cup sugar.", {}),
    ("Add 3/4 tsp salt.", {}),
    ("Walk 2 1/3 miles.", {}),
    ("Pour ½ cup milk.", {}),
    ("Aspect ratio 16:9.", {}),
    ("Mix ratio 3:1.", {}),
    ("Ages 10-20 welcome.", {}),
    ("Years 1995-1999 active.", {}),
    ("Costs $5-$10 per item.", {}),
    ("Price is £5-£10.", {"locale": "en-GB"}),
    ("Earned $5K-$10K.", {}),
    ("Price $5.50-$10.50.", {}),
    ("Exchange $5-EUR10.", {}),

    # 4. Units
    ("Run 5km and lift 10 kg.", {}),
    ("Walk 1 km vs 2 km.", {}),
    ("Scale shows 0 kg.", {}),
    ("Sample is 1.5 kg.", {}),
    ("Speed limit 60 km/h.", {}),
    ("Temp is 25°C.", {}),
    ("Input 120 V at 50 Hz.", {}),
    ("Circuit draw is 5A.", {}),
    ("There are 10 in the box vs 10in pipe.", {}),
    ("Hike 10-20 km daily.", {}),

    # 5. Phone Numbers & Technical IDs
    ("Call (555) 123-4567.", {}),
    ("Reach 555-123-4567 ext. 123.", {}),
    ("Contact +91 98765 43210.", {"locale": "en-IN"}),
    ("Dial 555-0199.", {}),
    ("Model RX-78 online.", {}),
    ("Apply WD-40 spray.", {}),
    ("The COVID-19 pandemic.", {}),
    ("Fighter jet F-16.", {}),

    # 6. Overlap Conflicts
    ("Special price $5-$10 or call 555-0199 on April 3-5 for 10-20 km trip.", {}),
    ("Take 2 1/3 doses of 3/4 solution at 14:30 EST.", {}),
]

for text, kw in cases:
    check(text, **kw)

print(f"\nAll {len(cases)} cases verified with zero invariant breaches.")
