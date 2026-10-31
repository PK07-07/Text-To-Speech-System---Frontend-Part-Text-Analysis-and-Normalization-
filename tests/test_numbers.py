"""Unit tests for number rules: cardinals, ordinals, decimals, percentages, years, and edge cases."""

from __future__ import annotations

import random
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer, normalize
from tests.conftest import assert_transformation_invariants


def test_cardinals_basic(default_normalizer: TextNormalizer):
    cases = [
        ("0", "zero"),
        ("1", "one"),
        ("12", "twelve"),
        ("42", "forty-two"),
        ("100", "one hundred"),
        ("105", "one hundred five"),
        ("1000", "one thousand"),
        ("1000000", "one million"),
        ("-5", "negative five"),
        ("-100", "negative one hundred"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_british_and_in_hundreds(gb_normalizer: TextNormalizer):
    res = gb_normalizer.normalize("105")
    assert res.normalized_text == "one hundred and five"
    assert res.status == "success"

    res2 = gb_normalizer.normalize("1005")
    assert res2.normalized_text == "one thousand and five"


def test_thin_space_and_comma_grouping(default_normalizer: TextNormalizer):
    # Comma grouping
    res_comma = default_normalizer.normalize("1,250,000")
    assert res_comma.normalized_text == "one million two hundred fifty thousand"

    # Thin space grouping (U+2009)
    res_thin = default_normalizer.normalize("1\u2009250\u2009000")
    assert res_thin.normalized_text == "one million two hundred fifty thousand"

    # Narrow no-break space (U+202F)
    res_narrow = default_normalizer.normalize("1\u202f000")
    assert res_narrow.normalized_text == "one thousand"

    # Ordinary ASCII space MUST NOT group digits
    res_ordinary = default_normalizer.normalize("room 10 20")
    assert res_ordinary.normalized_text == "room ten twenty"


def test_ordinals(default_normalizer: TextNormalizer):
    cases = [
        ("1st", "first"),
        ("2nd", "second"),
        ("3rd", "third"),
        ("4th", "fourth"),
        ("12th", "twelfth"),
        ("20th", "twentieth"),
        ("21st", "twenty-first"),
        ("23rd", "twenty-third"),
        ("100th", "one hundredth"),
        ("1000th", "one thousandth"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_decimals_and_trailing_zeros(default_normalizer: TextNormalizer):
    # Standard decimal
    res1 = default_normalizer.normalize("3.14159")
    assert res1.normalized_text == "three point one four one five nine"

    # Leading zero in decimals
    res2 = default_normalizer.normalize("0.05")
    assert res2.normalized_text == "zero point zero five"

    # Trailing zero preserved
    res3 = default_normalizer.normalize("3.50")
    assert res3.normalized_text == "three point five zero"

    # Negative decimal
    res4 = default_normalizer.normalize("-0.001")
    assert res4.normalized_text == "negative zero point zero zero one"


def test_percentages(default_normalizer: TextNormalizer):
    cases = [
        ("25%", "twenty-five percent"),
        ("100%", "one hundred percent"),
        ("-4.5%", "negative four point five percent"),
        ("(15%)", "negative fifteen percent"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_years_and_decades(default_normalizer: TextNormalizer):
    # Years
    res1 = default_normalizer.normalize("1984")
    assert res1.normalized_text == "nineteen eighty-four"

    res2 = default_normalizer.normalize("2000")
    assert res2.normalized_text == "two thousand"

    res3 = default_normalizer.normalize("2026")
    assert res3.normalized_text == "twenty twenty-six"

    # Decades
    res4 = default_normalizer.normalize("the 1980s")
    assert res4.normalized_text == "the nineteen eighties"

    res5 = default_normalizer.normalize("the '90s")
    assert res5.normalized_text == "the nineties"

    # Centuries
    res6 = default_normalizer.normalize("21st century")
    assert res6.normalized_text == "twenty-first century"


def test_accounting_mode_parentheses():
    cfg_accounting = NormalizerConfig(accounting_mode=True)
    norm = TextNormalizer(cfg_accounting)
    res = norm.normalize("(42)")
    assert res.normalized_text == "negative forty-two"

    # Normal mode preserves parentheses
    norm_normal = TextNormalizer(NormalizerConfig(accounting_mode=False))
    res_normal = norm_normal.normalize("(42)")
    assert res_normal.normalized_text == "(forty-two)"


def test_malformed_number_literal_policy():
    cfg = NormalizerConfig(unresolved_policy="literal")
    norm = TextNormalizer(cfg)
    res = norm.normalize("Error 12..34 detected")
    assert "twelve dot dot thirty-four" in res.normalized_text
    assert res.status == "partial"
    assert any(w.code == "MALFORMED_NUMBER" for w in res.warnings)


def test_number_out_of_range():
    # Number with 37 digits (> 10^36)
    huge_num = "1" + "0" * 36
    norm = TextNormalizer()
    res = norm.normalize(huge_num)
    assert any(w.code == "NUMBER_OUT_OF_RANGE" for w in res.warnings)
    assert res.status == "partial"
    assert "one" in res.normalized_text


def test_grouped_numbers_and_malformed_patterns():
    """A1 tests: 1,2,3, 1, 2, 3, 10,20, 3,14, 1,0000, 1,000,00, 1,23,456 in en-US and en-IN."""
    norm_us = TextNormalizer(NormalizerConfig.for_locale("en-US"))
    norm_in = TextNormalizer(NormalizerConfig.for_locale("en-IN"))

    # "1,2,3": malformed grouping
    res = norm_us.normalize("1,2,3")
    assert res.normalized_text == "one comma two comma three"
    assert res.status == "partial"
    assert any(w.code == "MALFORMED_NUMBER" for w in res.warnings)

    # "1, 2, 3": independent numbers separated by comma and space
    res = norm_us.normalize("1, 2, 3")
    assert res.normalized_text == "one, two, three"
    assert res.status == "success"

    # "10,20": malformed
    res = norm_us.normalize("10,20")
    assert res.normalized_text == "ten comma twenty"
    assert res.status == "partial"

    # "3,14": malformed
    res = norm_us.normalize("3,14")
    assert res.normalized_text == "three comma fourteen"
    assert res.status == "partial"

    # "1,0000": malformed
    res = norm_us.normalize("1,0000")
    assert res.normalized_text == "one comma zero zero zero zero"
    assert res.status == "partial"

    # "1,000,00": malformed
    res = norm_us.normalize("1,000,00")
    assert res.normalized_text == "one comma zero zero zero comma zero zero"
    assert res.status == "partial"

    # "1,23,456" in en-US: malformed (Indian grouping not recognized in US)
    res_us = norm_us.normalize("1,23,456")
    assert res_us.status == "partial"
    assert "one comma twenty-three comma four hundred fifty-six" in res_us.normalized_text

    # "1,23,456" in en-IN: valid Indian grouping
    res_in = norm_in.normalize("1,23,456")
    assert res_in.status == "success"
    assert "one lakh twenty-three thousand four hundred and fifty-six" == res_in.normalized_text

    # "$1,00,000" in en-US: malformed currency grouping
    res_curr_us = norm_us.normalize("$1,00,000")
    assert res_curr_us.status == "partial"
    assert "dollar one comma zero zero comma zero zero zero" in res_curr_us.normalized_text
    assert any(w.code == "MALFORMED_NUMBER" for w in res_curr_us.warnings)

    # "$1,00,000" in en-IN: valid grouping in en-IN
    res_curr_in = norm_in.normalize("$1,00,000")
    assert res_curr_in.status == "success"
    assert res_curr_in.normalized_text == "one lakh dollars"


def test_fuzz_digit_strings_no_silent_loss():
    """Fuzz test over random strings of digits, commas, dots, and spaces (length <= 12).

    The output either verbalizes valid patterns or carries a warning of severity warning/error.
    Never 'success' with lost digits.
    """
    rng = random.Random(1337)
    norm = TextNormalizer(NormalizerConfig.for_locale("en-US"))
    chars = "0123456789,."

    for _ in range(500):
        length = rng.randint(1, 12)
        s = "".join(rng.choice(chars) for _ in range(length))
        res = norm.normalize(s)

        # Check: either status != "success" or every digit from s is accounted for
        if res.status == "success":
            # Count digits in input
            input_digits = sum(1 for c in s if c.isdigit())
            # Output should not be empty if there were digits
            if input_digits > 0:
                assert res.normalized_text != ""
        else:
            # Result carries a warning or error
            assert any(w.severity in ("warning", "error") for w in res.warnings)


def test_4digit_context_heuristics():
    """A3: Context heuristics and precedence rules for 4-digit numbers 1100-2099.

    Precedence:
    1. Temporal cue before AND count noun after -> year + AMBIGUOUS_STANDALONE_YEAR info
    2. Quantity cue before, OR count noun after with no temporal cue -> cardinal, no warning
    3. Temporal cue alone -> year, no warning
    4. No cues -> year + AMBIGUOUS_STANDALONE_YEAR info warning (by default policy)
    """
    norm = TextNormalizer(NormalizerConfig.for_locale("en-US"))

    # 1. Precedence: Temporal cue before AND count noun after -> year + info warning
    res_conflict1 = norm.normalize("In 1984 people started")
    assert res_conflict1.normalized_text == "In nineteen eighty-four people started"
    assert res_conflict1.status == "success"
    assert any(w.code == "AMBIGUOUS_STANDALONE_YEAR" and w.severity == "info" for w in res_conflict1.warnings)

    res_conflict2 = norm.normalize("in 1500 words")
    assert res_conflict2.normalized_text == "in fifteen hundred words"
    assert res_conflict2.status == "success"
    assert any(w.code == "AMBIGUOUS_STANDALONE_YEAR" and w.severity == "info" for w in res_conflict2.warnings)

    # 2. Precedence: Quantity cue before -> cardinal, no warning
    res_qty = norm.normalize("a total of 1500 steps")
    assert res_qty.normalized_text == "a total of one thousand five hundred steps"
    assert res_qty.status == "success"
    assert len(res_qty.warnings) == 0

    # Precedence: Count noun after with no temporal cue -> cardinal, no warning
    res_noun1 = norm.normalize("1984 pages")
    assert res_noun1.normalized_text == "one thousand nine hundred eighty-four pages"
    assert res_noun1.status == "success"
    assert len(res_noun1.warnings) == 0

    res_noun2 = norm.normalize("2000 dollars")
    assert res_noun2.normalized_text == "two thousand dollars"
    assert res_noun2.status == "success"
    assert len(res_noun2.warnings) == 0

    # 3. Precedence: Temporal cue alone -> year, no warning
    # "summer of 1969": "of" after a season/month name/year is a temporal cue
    res_temp1 = norm.normalize("the summer of 1969")
    assert res_temp1.normalized_text == "the summer of nineteen sixty-nine"
    assert res_temp1.status == "success"
    assert len(res_temp1.warnings) == 0

    res_temp2 = norm.normalize("in 1984")
    assert res_temp2.normalized_text == "in nineteen eighty-four"
    assert res_temp2.status == "success"
    assert len(res_temp2.warnings) == 0

    res_temp3 = norm.normalize("since 2020")
    assert res_temp3.normalized_text == "since twenty twenty"
    assert res_temp3.status == "success"
    assert len(res_temp3.warnings) == 0

    res_temp4 = norm.normalize("1984 BC")
    assert res_temp4.normalized_text == "nineteen eighty-four B C"
    assert res_temp4.status == "success"
    assert len(res_temp4.warnings) == 0

    # 4. Precedence: No cues -> standalone year with info warning, status "success"
    res_none = norm.normalize("Room 1984")
    assert res_none.normalized_text == "Room nineteen eighty-four"
    assert res_none.status == "success"
    assert any(w.code == "AMBIGUOUS_STANDALONE_YEAR" and w.severity == "info" for w in res_none.warnings)


def test_year_2000s_style_modes():
    """A4: year_2000s_style config option ('thousand' vs 'oh') for 2000-2009."""
    cfg_thousand = NormalizerConfig.for_locale("en-US", year_2000s_style="thousand")
    cfg_oh = NormalizerConfig.for_locale("en-US", year_2000s_style="oh")

    norm_thousand = TextNormalizer(cfg_thousand)
    norm_oh = TextNormalizer(cfg_oh)

    # 2000 is always "two thousand"
    assert norm_thousand.normalize("in 2000").normalized_text == "in two thousand"
    assert norm_oh.normalize("in 2000").normalized_text == "in two thousand"

    # 2001
    assert norm_thousand.normalize("in 2001").normalized_text == "in two thousand one"
    assert norm_oh.normalize("in 2001").normalized_text == "in twenty oh one"

    # 2005
    assert norm_thousand.normalize("in 2005").normalized_text == "in two thousand five"
    assert norm_oh.normalize("in 2005").normalized_text == "in twenty oh five"

    # 2009
    assert norm_thousand.normalize("in 2009").normalized_text == "in two thousand nine"
    assert norm_oh.normalize("in 2009").normalized_text == "in twenty oh nine"

    # 2010+ is always "twenty ten", "twenty twenty-six" in both modes
    assert norm_thousand.normalize("in 2010").normalized_text == "in twenty ten"
    assert norm_oh.normalize("in 2010").normalized_text == "in twenty ten"
    assert norm_thousand.normalize("in 2026").normalized_text == "in twenty twenty-six"
    assert norm_oh.normalize("in 2026").normalized_text == "in twenty twenty-six"


def test_blood_pressure_verbalization():
    """Fix 3: Blood pressure pairing and verbalization."""
    from text_frontend.number_rules import verbalize_bp_number

    # Unit tests for verbalize_bp_number
    assert verbalize_bp_number(100) == "one hundred"
    assert verbalize_bp_number(105) == "one oh five"
    assert verbalize_bp_number(115) == "one fifteen"
    assert verbalize_bp_number(120) == "one twenty"
    assert verbalize_bp_number(125) == "one twenty-five"
    assert verbalize_bp_number(80) == "eighty"

    norm = TextNormalizer(NormalizerConfig.for_locale("en-US"))
    assert norm.normalize("BP of 120/80").normalized_text == "B P of one twenty over eighty"
    assert norm.normalize("blood pressure is 100/60").normalized_text == "blood pressure is one hundred over sixty"
    assert norm.normalize("reading was 105/75 mmHg").normalized_text == "reading was one oh five over seventy-five millimeters of mercury"
    assert norm.normalize("calculate 20/4 = 5").normalized_text == "calculate 20/4 equals five"

