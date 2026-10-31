"""Phase 4 Edge Case Verification Script for text_frontend.

Tests fixes B1-B7:
- B1: Exponents (x^2 -> x squared, x^3 -> x cubed, 10^5 -> ten to the fifth power)
- B2: Spaced operators vs ranges and scores (pages 10 - 20, Open 9 - 5, Score was 3 - 2, Option 1 / 2, 3 / 4 cup, 10 - 3 = 7, 20 / 4 = 5, what is 10 - 3)
- B3: < and > operands (Ten < twenty, a<b and c>d, x<3, <3)
- B4: Emoticon boundaries (Note:Please call, Re:Order, Total:OK, Step 3:Prepare, Dr:Smith, http://x.com, 16:9, XD-1000)
- B5: Collisions (0x1F, 0xFF00, 3x faster, 5x5 grid, 5 µs, 10 Ω, 100 µF, 3 µm)
- B6: Dashes (The strategy—which was bold—succeeded., New York–London flight, Paris–Berlin route, 10-20 pages)
- B7: Ligatures (Ærø, Cæsar, cœur, typographic ligatures)
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer

CASES: list[dict[str, str | dict]] = [
    # B1: Exponents
    {
        "name": "B1: Exponent squared",
        "input": "Compute x^2 now.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Compute x squared now.",
    },
    {
        "name": "B1: Exponent cubed",
        "input": "Volume is x^3.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Volume is x cubed.",
    },
    {
        "name": "B1: Exponent fifth power",
        "input": "Compute 10^5 now.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Compute ten to the fifth power now.",
    },
    # B2: Spaced operators vs ranges, scores, fractions
    {
        "name": "B2: Spaced hyphen range (pages)",
        "input": "Read pages 10 - 20.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Read pages ten to twenty.",
    },
    {
        "name": "B2: Spaced hyphen hours",
        "input": "Open 9 - 5 today.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Open nine to five today.",
    },
    {
        "name": "B2: Spaced hyphen score",
        "input": "Score was 3 - 2.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Score was three to two.",
    },
    {
        "name": "B2: Spaced slash fraction (option)",
        "input": "Choose Option 1 / 2.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Choose Option one half.",
    },
    {
        "name": "B2: Spaced slash fraction (recipe)",
        "input": "Add 3 / 4 cup flour.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Add three fourths cup flour.",
    },
    {
        "name": "B2: Spaced minus arithmetic with equals",
        "input": "10 - 3 = 7",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "ten minus three equals seven",
    },
    {
        "name": "B2: Spaced slash arithmetic with equals",
        "input": "20 / 4 = 5",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "twenty divided by four equals five",
    },
    {
        "name": "B2: Spaced minus arithmetic with cue",
        "input": "what is 10 - 3",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "what is ten minus three",
    },
    # B3: < and > operands
    {
        "name": "B3: Words around < unchanged",
        "input": "Ten < twenty",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Ten < twenty",
    },
    {
        "name": "B3: Single letters without numbers unchanged",
        "input": "a<b and c>d",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "a<b and c>d",
    },
    {
        "name": "B3: Single letter and number is math",
        "input": "Check if x<3.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Check if x is less than three.",
    },
    {
        "name": "B3: Standalone <3 is heart emoticon",
        "input": "Sending love <3",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Sending love heart",
    },
    # B4: Emoticon boundaries (negative tests)
    {
        "name": "B4: Negative emoticon Note:Please",
        "input": "Note:Please call tomorrow.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Note:Please call tomorrow.",
    },
    {
        "name": "B4: Negative emoticon Re:Order",
        "input": "Re:Order confirmation.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Re:Order confirmation.",
    },
    {
        "name": "B4: Negative emoticon Total:OK",
        "input": "Total:OK for shipment.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Total:okay for shipment.",
    },
    {
        "name": "B4: Negative emoticon Step 3:Prepare",
        "input": "Step 3:Prepare ingredients.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Step three:Prepare ingredients.",
    },
    {
        "name": "B4: Negative emoticon Dr:Smith",
        "input": "Dr:Smith will arrive.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Doctor:Smith will arrive.",
    },
    {
        "name": "B4: Negative emoticon URL http://x.com",
        "input": "Visit http://x.com now.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Visit x dot com now.",
    },
    {
        "name": "B4: Negative emoticon ratio 16:9",
        "input": "Aspect ratio 16:9.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Aspect ratio sixteen to nine.",
    },
    {
        "name": "B4: Negative emoticon identifier XD-1000",
        "input": "Model XD-1000 ready.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Model X D one thousand ready.",
    },
    # B5: Collisions
    {
        "name": "B5: Hex 0x1F preserved",
        "input": "Register value 0x1F.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Register value 0x1F.",
    },
    {
        "name": "B5: Hex 0xFF00 preserved",
        "input": "Memory at 0xFF00.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Memory at 0xFF00.",
    },
    {
        "name": "B5: Multiplier speed 3x faster",
        "input": "Engine runs 3x faster.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Engine runs three times faster.",
    },
    {
        "name": "B5: Grid dimension 5x5 grid",
        "input": "Layout on a 5x5 grid.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Layout on a five by five grid.",
    },
    {
        "name": "B5: Microsecond unit 5 µs",
        "input": "Latency is 5 µs.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Latency is five microseconds.",
    },
    {
        "name": "B5: Ohm unit 10 Ω",
        "input": "Resistance is 10 Ω.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Resistance is ten ohms.",
    },
    {
        "name": "B5: Microfarad unit 100 µF",
        "input": "Capacitor is 100 µF.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Capacitor is one hundred microfarads.",
    },
    {
        "name": "B5: Micrometer unit 3 µm",
        "input": "Diameter is 3 µm.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Diameter is three micrometers.",
    },
    # B6: Dashes
    {
        "name": "B6: Em dash prose pause",
        "input": "The strategy—which was bold—succeeded.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "The strategy, which was bold, succeeded.",
    },
    {
        "name": "B6: En dash between words (New York–London)",
        "input": "The New York–London flight departed.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "The New York to London flight departed.",
    },
    {
        "name": "B6: En dash between words (Paris–Berlin)",
        "input": "The Paris–Berlin route opened.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "The Paris to Berlin route opened.",
    },
    {
        "name": "B6: En dash number range preserved",
        "input": "Read pages 10–20.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Read pages ten to twenty.",
    },
    # B7: Ligatures
    {
        "name": "B7: Nordic name Ærø unchanged",
        "input": "Visited Ærø island.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Visited Ærø island.",
    },
    {
        "name": "B7: Classical name Cæsar unchanged",
        "input": "Julius Cæsar ruled.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Julius Cæsar ruled.",
    },
    {
        "name": "B7: French word cœur unchanged",
        "input": "Un coup de cœur.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Un coup de cœur.",
    },
    {
        "name": "B7: Typographic ligatures expand",
        "input": "A ﬁne ﬂight with ﬅyle.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "A fine flight with style.",
    },
]


def main() -> int:
    print(f"Running Phase 4 Edge Cases Verification Suite ({len(CASES)} cases)...")
    passed = 0
    failed = 0

    for i, case in enumerate(CASES, 1):
        name = case["name"]
        raw = case["input"]
        cfg = case["config"]
        expected = case["expected"]

        norm = TextNormalizer(cfg)
        res = norm.normalize(raw)
        actual = res.normalized_text

        print(f"[{i:02d}/{len(CASES)}] {name}")
        print(f"  Input:    {raw}")
        print(f"  Expected: {expected}")
        print(f"  Actual:   {actual}")
        cfg_str = f"locale={cfg.locale}, emoji_policy={cfg.emoji_policy}"
        print(f"  Config:   {cfg_str}")

        if actual == expected:
            passed += 1
            print("  Result:   PASS\n")
        else:
            failed += 1
            print("  Result:   FAIL\n")

    print(f"Phase 4 Edge Results: {passed} passed, {failed} failed out of {len(CASES)} cases.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
