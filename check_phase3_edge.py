"""Edge case verification script for Phase 3 amendments.

Covers:
- Fenced code blocks (drop by default with CODE_BLOCK_DROPPED info warning; kept via code_block_policy="keep")
- Unclosed <script> tag dropped with UNCLOSED_SCRIPT_TAG warning, keeping content
- Unclosed tags (<b>unclosed -> unclosed)
- HTML comments (<!-- comment -->text -> text)
- Case-insensitive tags (<P>Upper</P> -> Upper)
- Self-closing tags and tags with attributes (<img alt="x"> stripped)
- Code spans with backticks (`code` -> code)
- Markdown list lines (- item, 1. item) not swallowed
- Math/asterisk preserved (2*3*4)
- All-caps rules (PLEASE CALL ME, WARNING: DO NOT ENTER, The US economy, Let us go, IT support, OK, UNICEF, XYZ Corp)
- Ampersand acronyms (AT&T, P&L, R&D, Q&A, S&P)
- Hashtags (#TTS, #GoodMorning)
- Word/word slashes (and/or, TCP/IP, either/or, yes/no, N/A)
- Pure fractions unit agreement (3/4 tsp -> three fourths teaspoon)
- Street address numbers in pairs (123 Main St., 1600 Pennsylvania Ave.)
- Mixed letter-digit tokens (v1, item-3, user123)
- Hex words (deadbeef alone vs commit deadbeef)
"""

from __future__ import annotations

import sys
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


def run_checks() -> int:
    norm_us = TextNormalizer(NormalizerConfig.for_locale("en-US"))
    norm_keep_code = TextNormalizer(NormalizerConfig.for_locale("en-US", code_block_policy="keep"))
    norm_slash = TextNormalizer(NormalizerConfig.for_locale("en-US", word_slash_style="slash"))

    cases = [
        # 1. Fenced code block (drop default)
        (norm_us, "Prefix\n```python\nprint(123)\n```\nSuffix", "Prefix\nSuffix", "info", "CODE_BLOCK_DROPPED"),
        # 2. Fenced code block (keep)
        (norm_keep_code, "Prefix\n```python\nprint(123)\n```\nSuffix", "Prefix\n```python\nprint(one hundred twenty-three)\n```\nSuffix", None, None),
        # 3. Unclosed <script>
        (norm_us, "<script>alert(1)", "alert(one)", "warning", "UNCLOSED_SCRIPT_TAG"),
        # 4. Unclosed tags
        (norm_us, "<b>unclosed text</b>", "unclosed text", None, None),
        (norm_us, "<b>unclosed", "unclosed", None, None),
        # 5. HTML comments
        (norm_us, "<!-- comment -->text", "text", None, None),
        # 6. Case-insensitive tags
        (norm_us, "<P>Upper</P>", "Upper", None, None),
        # 7. Self-closing / tags with attributes
        (norm_us, '<img alt="x">Photo', "Photo", None, None),
        # 8. Code spans with backticks
        (norm_us, "Run `code` now.", "Run code now.", None, None),
        # 9. Markdown list lines
        (norm_us, "- item", "- item", None, None),
        (norm_us, "1. item", "one. item", None, None),
        # 10. Math/asterisk operator verbalized in Phase 4
        (norm_us, "2*3*4", "two times three times four", None, None),
        # 11. All-caps rule (Amendment 4)
        (norm_us, "PLEASE CALL ME", "please call me", None, None),
        (norm_us, "WARNING: DO NOT ENTER", "warning: do not enter", None, None),
        (norm_us, "The US economy", "The U S economy", None, None),
        (norm_us, "Let us go", "Let us go", None, None),
        (norm_us, "IT support", "I T support", None, None),
        (norm_us, "OK", "okay", None, None),
        (norm_us, "UNICEF", "UNICEF", None, None),
        (norm_us, "XYZ Corp", "XYZ Corp", None, None),
        (norm_us, "CEOs met FBI's team", "C E Os met F B I's team", None, None),
        # 12. Ampersand acronyms (Amendment 5)
        (norm_us, "AT&T", "A T and T", None, None),
        (norm_us, "P&L", "P and L", None, None),
        (norm_us, "R&D", "R and D", None, None),
        (norm_us, "Q&A", "Q and A", None, None),
        (norm_us, "S&P", "S and P", None, None),
        # 13. Hashtags (Amendment 5)
        (norm_us, "#TTS", "hashtag T T S", None, None),
        (norm_us, "#GoodMorning", "hashtag Good Morning", None, None),
        # 14. Word/word slashes (Amendment 5)
        (norm_us, "and/or", "and or", None, None),
        (norm_us, "either/or", "either or", None, None),
        (norm_us, "yes/no", "yes or no", None, None),
        (norm_us, "Status: N/A", "Status: not applicable", None, None),
        (norm_us, "TCP/IP", "T C P slash I P", None, None),
        (norm_slash, "and/or", "and slash or", None, None),
        # 15. Pure fractions less than 1 take singular unit
        (norm_us, "3/4 tsp", "three fourths teaspoon", None, None),
        # 16. Street address pairing
        (norm_us, "123 Main St.", "one twenty-three Main Street.", None, None),
        (norm_us, "1600 Pennsylvania Ave.", "sixteen hundred Pennsylvania Avenue.", None, None),
        # 17. Mixed letter-digit tokens
        (norm_us, "v1", "v one", None, None),
        (norm_us, "item-3", "item dash three", None, None),
        (norm_us, "user123", "user one two three", None, None),
        # 18. Hex words in words.txt
        (norm_us, "A delicious deadbeef steak.", "A delicious deadbeef steak.", None, None),
        (norm_us, "Fixed in commit deadbeef.", "Fixed in commit d e a d b e e f.", None, None),
        (norm_us, "Building facade.", "Building facade.", None, None),
        (norm_us, "sha facade", "sha f a c a d e", None, None),
        # 19. SCREAMING_SNAKE
        (norm_us, "MAX_BUFFER_SIZE", "max buffer size", None, None),
    ]

    total = len(cases)
    passed = 0
    failures = []

    print(f"=== Running {total} check_phase3_edge.py cases ===")
    for idx, (norm, raw_input, expected_text, exp_sev, exp_code) in enumerate(cases, 1):
        res = norm.normalize(raw_input)
        ok = True
        err_msg = []

        if res.normalized_text != expected_text:
            ok = False
            err_msg.append(f"expected text {expected_text!r}, got {res.normalized_text!r}")

        if exp_code:
            matching = [w for w in res.warnings if w.code == exp_code]
            if not matching:
                ok = False
                err_msg.append(f"expected warning code '{exp_code}', got {[w.code for w in res.warnings]}")
            elif exp_sev and matching[0].severity != exp_sev:
                ok = False
                err_msg.append(f"expected warning severity '{exp_sev}', got '{matching[0].severity}'")

        if ok:
            passed += 1
            print(f"[{idx:02d}/{total:02d}] PASS: {raw_input!r} -> {res.normalized_text!r} (status={res.status})")
        else:
            failures.append((idx, raw_input, ", ".join(err_msg)))
            print(f"[{idx:02d}/{total:02d}] FAIL: {raw_input!r} -> {', '.join(err_msg)}")

    print(f"\nResult: {passed}/{total} cases passed.")
    if failures:
        print(f"FAILED {len(failures)} cases:")
        for idx, inp, msg in failures:
            print(f"  Case #{idx:02d} ({inp!r}): {msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_checks())
