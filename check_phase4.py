"""Phase 4 Verification Script for text_frontend.

Runs a comprehensive test of all Phase 4 capabilities:
- D1: Emojis, emoticons, and non-speech brackets
- D2: Math operators, dimensions, scientific notation, exponents, superscripts, square root, chemical formulas, Greek letters
- D3: Typographic ligatures, punctuation normalization, hyphenation repair, prose dashes
- D4: SSML tag preservation and stripping
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer

CASES: list[dict[str, str | dict]] = [
    # D1: Emojis & Emoticons
    {
        "name": "Emoji Drop Policy (Default)",
        "input": "Hello 👋 world! Nice job 👍.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="drop"),
        "expected": "Hello world! Nice job.",
    },
    {
        "name": "Emoji Verbalize Policy",
        "input": "Hello 👋 world! Party 🎉 time.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Hello waving hand world! Party party popper time.",
    },
    {
        "name": "Emoji ZWJ Sequence Verbalize",
        "input": "Family 👨‍👩‍👧 dinner with 👍🏻.",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Family family: man, woman, girl dinner with thumbs up: light skin tone.",
    },
    {
        "name": "Emoticon Verbalize",
        "input": "Great news :) Have fun :D love you <3",
        "config": NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"),
        "expected": "Great news smiling face Have fun grinning face love you heart",
    },
    # D1: Non-Speech
    {
        "name": "Non-Speech Drop Policy (Default)",
        "input": "She said [laughter] that was funny [pause] indeed.",
        "config": NormalizerConfig.for_locale("en-US", non_speech_policy="drop"),
        "expected": "She said that was funny indeed.",
    },
    {
        "name": "Non-Speech Keep Policy",
        "input": "The crowd (applause) cheered loudly.",
        "config": NormalizerConfig.for_locale("en-US", non_speech_policy="keep"),
        "expected": "The crowd (applause) cheered loudly.",
    },
    {
        "name": "Non-Speech Pause Policy",
        "input": "Wait [pause] right here.",
        "config": NormalizerConfig.for_locale("en-US", non_speech_policy="pause"),
        "expected": "Wait, right here.",
    },
    # D2: Dimensions
    {
        "name": "Dimensions 2D",
        "input": "Room is 10x20 feet.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Room is ten by twenty feet.",
    },
    {
        "name": "Dimensions 3D",
        "input": "Box is 4 x 6 x 8 inches.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Box is four by six by eight inches.",
    },
    {
        "name": "Display Resolution",
        "input": "Display is 1920x1080 resolution.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Display is nineteen twenty by ten eighty resolution.",
    },
    # D2: Scientific Notation
    {
        "name": "Scientific Notation 10^exp",
        "input": "Speed of light is 3.0 x 10^8 meters per second.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Speed of light is three point zero times ten to the eighth meters per second.",
    },
    {
        "name": "Scientific Notation Superscript",
        "input": "Constant is 6.02 × 10²³ atoms.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Constant is six point zero two times ten to the power of twenty-three atoms.",
    },
    {
        "name": "Scientific E-Notation Negative",
        "input": "Small value 1e-6 seconds.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Small value one times ten to the negative six seconds.",
    },
    {
        "name": "Scientific E-Notation Positive",
        "input": "Distance 2.5E10 meters.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Distance two point five times ten to the tenth meters.",
    },
    # D2: Powers & Square Root
    {
        "name": "Exponent 10^5",
        "input": "Compute 10^5 now.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Compute ten to the fifth power now.",
    },
    {
        "name": "Superscript Squared",
        "input": "Value is 5² units.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Value is five squared units.",
    },
    {
        "name": "Superscript Cubed",
        "input": "Volume is x³.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Volume is x cubed.",
    },
    {
        "name": "Square Root",
        "input": "Calculate √16 easily.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Calculate square root of sixteen easily.",
    },
    # D2: Chemical Formulas
    {
        "name": "Chemical Formulas",
        "input": "Drink H2O and reduce CO2 and SO2.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Drink H two O and reduce C O two and S O two.",
    },
    # D2: Greek Letters & Constants
    {
        "name": "Greek Letters",
        "input": "Angle α and angle β sum to γ.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Angle alpha and angle beta sum to gamma.",
    },
    {
        "name": "Attached Greek Pi",
        "input": "Circumference is 2π times r.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Circumference is two pi times r.",
    },
    # D2: Math Operators
    {
        "name": "Math Addition & Equals",
        "input": "Equation: 2 + 2 = 4.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Equation: two plus two equals four.",
    },
    {
        "name": "Math Subtraction & Equals",
        "input": "Result: 10 - 3 = 7.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Result: ten minus three equals seven.",
    },
    {
        "name": "Math Multiplication & Division",
        "input": "Math: 5 * 6 = 30 and 20 / 4 = 5.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Math: five times six equals thirty and twenty divided by four equals five.",
    },
    {
        "name": "Math Inequalities",
        "input": "Logic: 10 < 20 and 50 > 30 and 5 ≠ 10.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Logic: ten is less than twenty and fifty is greater than thirty and five does not equal ten.",
    },
    {
        "name": "Math Plus-Minus",
        "input": "Tolerance is ±5 mm.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Tolerance is plus or minus five millimeters.",
    },
    # D2: Safeguards
    {
        "name": "Prose Dimension Safeguard",
        "input": "Remember that x marks the spot.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Remember that x marks the spot.",
    },
    {
        "name": "Prose Dash Safeguard",
        "input": "Choose between option a - b today.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Choose between option a - b today.",
    },
    # D3: Ligatures & Punctuation
    {
        "name": "Typographic Ligatures",
        "input": "A ﬁne ﬂight with æsthetic œvre.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "A fine flight with æsthetic œvre.",
    },
    {
        "name": "Multiple Punctuation & Ellipsis",
        "input": "Really?? Yes!! It happened.... Wait… now.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "Really? Yes! It happened... Wait... now.",
    },
    {
        "name": "Hyphenation Repair Across Newline",
        "input": "This is a great exam-\nple of hyphen repair.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "This is a great example of hyphen repair.",
    },
    {
        "name": "Prose Dashes",
        "input": "The strategy—which was bold—succeeded.",
        "config": NormalizerConfig.for_locale("en-US"),
        "expected": "The strategy, which was bold, succeeded.",
    },
    # D4: SSML Mode
    {
        "name": "SSML Mode Enabled (Preserve Tags)",
        "input": '<speak>Hello <break time="1s"/> <prosody rate="fast">world</prosody>!</speak>',
        "config": NormalizerConfig.for_locale("en-US", ssml_mode=True),
        "expected": '<speak>Hello <break time="1s"/> <prosody rate="fast">world</prosody>!</speak>',
    },
    {
        "name": "SSML Mode Disabled (Strip Tags)",
        "input": '<speak>Hello <prosody rate="fast">world</prosody>!</speak>',
        "config": NormalizerConfig.for_locale("en-US", ssml_mode=False),
        "expected": "Hello world!",
    },
]


def main() -> int:
    print(f"Running Phase 4 Verification Suite ({len(CASES)} test cases)...")
    passed = 0
    failed = 0

    for i, case in enumerate(CASES, 1):
        name = case["name"]
        raw = case["input"]
        cfg = case["config"]
        expected = case["expected"]

        norm = TextNormalizer(cfg)
        res = norm.normalize(raw)
        actual = res.normalized_text.strip() if "<" in raw else res.normalized_text

        cfg_str = f"locale={cfg.locale}, emoji_policy={cfg.emoji_policy}, ssml_mode={cfg.ssml_mode}"
        print(f"[{i:02d}/{len(CASES)}] {name}")
        print(f"  Input:    {raw}")
        print(f"  Output:   {actual}")
        print(f"  Config:   {cfg_str}")

        if actual == expected:
            passed += 1
            print("  Status:   PASS\n")
        else:
            failed += 1
            print(f"  Status:   FAIL (Expected: {expected})\n")

    print(f"Phase 4 Results: {passed} passed, {failed} failed out of {len(CASES)} cases.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
