"""Phase 3 Comprehensive Verification Script for text_frontend.

Verifies:
- Markup preprocessing (HTML tags, script/style drop, entities, markdown)
- URLs, Emails, Hashes, Versions, IPv4, Identifiers
- Abbreviations, Acronyms, Disambiguation (St., Dr.), Initials
- Symbols (@, &, #, _, ~, /, typography)
- Monotonicity and non-overlapping transformation invariants across all cases
- Dynamically counts cases and prints locale with each case
"""

from __future__ import annotations

import sys
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants

CASES: list[tuple[str, str, str]] = [
    # (input_text, expected_normalized, locale)
    # 1. Markup - HTML Tags & Script/Style
    ("First paragraph.<p>Second paragraph.</p>More text.", "First paragraph. Second paragraph. More text.", "en-US"),
    ("<b>Bold</b> and <i>italic</i>.", "Bold and italic.", "en-US"),
    ("Drop<script>alert(1);</script> code.", "Drop code.", "en-US"),
    ("Line 1<br>Line 2.", "Line one Line two.", "en-US"),

    # 2. Markup - HTML Entities
    ("Tom &amp; Jerry &quot;Show&#39;s&quot;.", "Tom and Jerry \"Show's\".", "en-US"),
    ("Ten &lt; twenty and fifty &gt; thirty.", "Ten < twenty and fifty > thirty.", "en-US"),

    # 3. Markup - Markdown
    ("# Main Heading\nSecond line.", "Main Heading\nSecond line.", "en-US"),
    ("Visit [our site](https://example.com) now.", "Visit our site now.", "en-US"),
    ("Very *important* matter.", "Very important matter.", "en-US"),

    # 4. URLs & Emails
    ("Visit https://example.com/api/v1 today.", "Visit example dot com slash api slash v1 today.", "en-US"),
    ("Check www.example.org/about.", "Check example dot org slash about.", "en-US"),
    ("Contact alice@example.com for help.", "Contact alice at example dot com for help.", "en-US"),
    ("Email sales.info@corp.co.uk today.", "Email sales dot info at corp dot co dot uk today.", "en-US"),

    # 5. Technical Identifiers: Versions, IPv4, Hashes, Case splitting
    ("Release v2.1.3 is live.", "Release version two point one point three is live.", "en-US"),
    ("Server 192.168.1.1 online.", "Server one nine two dot one six eight dot one dot one online.", "en-US"),
    ("Git commit 4b825dc merged.", "Git commit four b eight two five d c merged.", "en-US"),
    ("Function getUserName called.", "Function get User Name called.", "en-US"),
    ("Constant MAX_BUFFER_SIZE reached.", "Constant MAX BUFFER SIZE reached.", "en-US"),

    # 6. Titles, Honorifics & Disambiguation
    ("Meeting with Mr. Smith and Dr. Watson.", "Meeting with Mister Smith and Doctor Watson.", "en-US"),
    ("Visiting St. Jude Hospital.", "Visiting Saint Jude Hospital.", "en-US"),
    ("He lives on 42nd St.", "He lives on forty-second Street.", "en-US"),
    ("Office at 123 Main St. in New York.", "Office at one hundred twenty-three Main Street in New York.", "en-US"),
    ("House on Maple Dr. sold.", "House on Maple Drive sold.", "en-US"),
    ("Dr. Jekyll and Mr. Hyde.", "Doctor Jekyll and Mister Hyde.", "en-US"),

    # 7. End-of-sentence abbreviations & Latin
    ("Apples, oranges, pears, etc.", "Apples, oranges, pears, etcetera.", "en-US"),
    ("Provide fruits, e.g., apples and pears.", "Provide fruits, for example, apples and pears.", "en-US"),
    ("Main issue, i.e., latency.", "Main issue, that is, latency.", "en-US"),
    ("Match: Ali vs. Frazier.", "Match: Ali versus Frazier.", "en-US"),
    ("Price approx. $50.", "Price approximately fifty dollars.", "en-US"),

    # 8. Name Initials, Initialisms, Acronyms, Mixed
    ("Author J. K. Rowling wrote novels.", "Author J K Rowling wrote novels.", "en-US"),
    ("Agents of FBI and CIA.", "Agents of F B I and C I A.", "en-US"),
    ("NASA and NATO summit.", "NASA and NATO summit.", "en-US"),
    ("Platform for B2B and B2C.", "Platform for B to B and B to C.", "en-US"),
    ("Streaming 1080p video over 5G.", "Streaming ten eighty P video over five G.", "en-US"),

    # 9. Symbols (@, &, #, ~, /, typography)
    ("Tickets @ $10 each.", "Tickets at ten dollars each.", "en-US"),
    ("Rock & Roll band.", "Rock and Roll band.", "en-US"),
    ("Winner is #1 always.", "Winner is number one always.", "en-US"),
    ("Trending tag #TTS today.", "Trending tag hashtag TTS today.", "en-US"),
    ("Duration ~10 minutes.", "Duration approximately ten minutes.", "en-US"),
    ("Choose either/or option.", "Choose either slash or option.", "en-US"),
    ("Acme Corp. © 2024.", "Acme Corporation copyright twenty twenty-four.", "en-US"),
    # 10. Multi-locale variations
    ("Smith & Co. Ltd. earned £1,500.", "Smith and Company Limited earned one thousand five hundred pounds.", "en-GB"),
    ("Call Dr. Sharma at +91 98765 43210.", "Call Doctor Sharma at plus nine one, nine eight seven six five, four three two one zero.", "en-IN"),
]


def main():
    normalizers = {
        "en-US": TextNormalizer(NormalizerConfig.for_locale("en-US")),
        "en-GB": TextNormalizer(NormalizerConfig.for_locale("en-GB")),
        "en-IN": TextNormalizer(NormalizerConfig.for_locale("en-IN")),
    }

    total_cases = len(CASES)
    print(f"Running Phase 3 verification suite on {total_cases} test cases...\n")

    passed = 0
    failed = 0

    for idx, (raw, expected, locale) in enumerate(CASES, 1):
        norm = normalizers[locale]
        res = norm.normalize(raw)

        # Invariant checks
        try:
            assert_transformation_invariants(raw, res)
            invariants_ok = True
        except AssertionError as e:
            invariants_ok = False
            inv_error = str(e)

        if res.normalized_text == expected and invariants_ok:
            print(f"[{idx:02d}/{total_cases:02d}] [{locale}] PASS: {raw!r}")
            print(f"       -> {res.normalized_text!r}")
            passed += 1
        else:
            print(f"[{idx:02d}/{total_cases:02d}] [{locale}] FAIL: {raw!r}")
            print(f"       Expected: {expected!r}")
            print(f"       Got:      {res.normalized_text!r}")
            if not invariants_ok:
                print(f"       Invariant Error: {inv_error}")
            failed += 1

    print(f"\nPhase 3 Verification Summary: {passed}/{total_cases} passed ({failed} failed).")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
