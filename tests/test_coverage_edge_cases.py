"""Additional edge cases to maximize test coverage across config, validation, and rules."""

from __future__ import annotations

from dataclasses import replace
import random
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer, normalize
from text_frontend.number_rules import (
    CandidateSpan,
    verbalize_bare_int_span,
    verbalize_cardinal,
    verbalize_century_span,
    verbalize_decade_span,
    verbalize_digits,
    verbalize_grouped_int_span,
    verbalize_indian_cardinal,
    verbalize_malformed_number,
    verbalize_ordinal,
    verbalize_ordinal_span,
    verbalize_triplet,
    verbalize_year,
)
from text_frontend.unicode_utils import (
    MonotonicCoordinateMapper,
    canonicalize_and_map,
    decode_and_validate_input,
    is_atomic_continuation,
)
from text_frontend.validation import NormalizationWarning
from tests.conftest import assert_transformation_invariants


def test_config_validation_errors():
    with pytest.raises(ValueError, match="Unsupported locale"):
        NormalizerConfig(locale="fr-FR")

    with pytest.raises(ValueError, match="Invalid currency code"):
        NormalizerConfig(default_currency_for_dollar="XYZ")

    with pytest.raises(ValueError, match="max_input_length must be positive"):
        NormalizerConfig(max_input_length=0)

    with pytest.raises(ValueError, match="max_expansion_ratio must be > 1.0"):
        NormalizerConfig(max_expansion_ratio=0.5)

    with pytest.raises(ValueError, match="Invalid year_2000s_style"):
        NormalizerConfig(year_2000s_style="invalid")  # type: ignore

    with pytest.raises(ValueError, match="Invalid pound_key_word"):
        NormalizerConfig(pound_key_word="invalid")  # type: ignore

    cfg_compat = NormalizerConfig.for_locale("en-US", non_speech_sound_policy="pause")
    assert cfg_compat.non_speech_policy == "pause"

    with pytest.raises(ValueError, match="Unsupported locale"):
        NormalizerConfig.for_locale("es-ES")


def test_config_content_hash_deterministic():
    cfg1 = NormalizerConfig.for_locale("en-US")
    cfg2 = NormalizerConfig.for_locale("en-US")
    assert cfg1.content_hash() == cfg2.content_hash()

    cfg_gb = NormalizerConfig.for_locale("en-GB")
    assert cfg1.content_hash() != cfg_gb.content_hash()


def test_expansion_ratio_exceeded():
    cfg = NormalizerConfig(max_expansion_ratio=2.0)
    norm = TextNormalizer(cfg)
    # A single digit '1' expanding to 'one' (3 chars) exceeds 2.0x ratio
    res = norm.normalize("1")
    assert res.status == "failed"
    assert any(w.code == "EXPANSION_RATIO_EXCEEDED" for w in res.warnings)


def test_ssml_mode_protected_tags():
    cfg = NormalizerConfig(ssml_mode=True)
    norm = TextNormalizer(cfg)
    raw = '<speak>Hello <break time="500ms"/> world with $10.</speak>'
    res = norm.normalize(raw)
    assert res.status == "success"
    assert "<speak>" in res.normalized_text
    assert '<break time="500ms"/>' in res.normalized_text
    assert "ten dollars" in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_invalid_input_type():
    res = normalize(12345)  # type: ignore
    assert res.status == "failed"
    assert any(w.code == "INVALID_INPUT_TYPE" for w in res.warnings)


def test_extreme_number_scales():
    # 10^15: quadrillion
    quad = 10**15
    assert "one quadrillion" == verbalize_cardinal(quad)

    # 10^33: decillion
    dec = 10**33
    assert "one decillion" == verbalize_cardinal(dec)

    # Ordinals
    assert "zeroth" == verbalize_ordinal(0)
    assert "eleventh" == verbalize_ordinal(11)
    assert "twelfth" == verbalize_ordinal(12)
    assert "thirteenth" == verbalize_ordinal(13)
    assert "twentieth" == verbalize_ordinal(20)
    assert "thirtieth" == verbalize_ordinal(30)
    assert "one hundredth" == verbalize_ordinal(100)
    assert "one thousandth" == verbalize_ordinal(1000)


def test_currency_edge_cases(default_normalizer: TextNormalizer):
    # Only cents
    res1 = default_normalizer.normalize("$0.50")
    assert res1.normalized_text == "fifty cents"

    # Only one cent
    res2 = default_normalizer.normalize("$0.01")
    assert res2.normalized_text == "one cent"

    # Negative ISO code prefix
    res3 = default_normalizer.normalize("USD -50")
    assert res3.normalized_text == "negative fifty dollars"

    # Negative ISO code suffix
    res4 = default_normalizer.normalize("-50 USD")
    assert res4.normalized_text == "negative fifty dollars"

    # Decimal with 3 decimal places
    res5 = default_normalizer.normalize("$10.555")
    assert res5.normalized_text == "ten point five five five dollars"


def test_order_independent_overlap_resolution():
    """A7: Shuffling candidate spans before greedy resolution produces identical output."""
    raw = "The 1st item costs $10.50, the 2nd is $20, and the 3rd is 25% off in 2024."
    norm = TextNormalizer()

    clean_text, mapper, _ = canonicalize_and_map(raw)
    from text_frontend.number_rules import find_number_candidates
    from text_frontend.currency_rules import find_currency_candidates

    candidates = find_currency_candidates(clean_text, norm.config) + find_number_candidates(clean_text, norm.config)

    rng = random.Random(999)
    res_baseline = norm._resolve_overlaps(list(candidates), [])

    # Shuffle candidates 10 times and assert accepted spans are identical
    for _ in range(10):
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        res_shuffled = norm._resolve_overlaps(shuffled, [])
        assert [(s.start, s.end, s.category) for s in res_baseline] == [
            (s.start, s.end, s.category) for s in res_shuffled
        ]


def test_unresolved_policy_preserve():
    """A7: unresolved_policy='preserve' keeps malformed numbers verbatim with warning."""
    cfg = NormalizerConfig(unresolved_policy="preserve")
    norm = TextNormalizer(cfg)

    res = norm.normalize("Error 12..34 detected")
    assert "12..34" in res.normalized_text
    assert res.status == "partial"
    assert any(w.code == "MALFORMED_NUMBER" for w in res.warnings)

    res2 = norm.normalize("Amount $1,00,000 invalid")
    assert "$1,00,000" in res2.normalized_text
    assert res2.status == "partial"


def test_locale_consistency_on_replace():
    """A7: dataclasses.replace(config, locale='en-GB') produces consistent resolved config."""
    cfg_us = NormalizerConfig.for_locale("en-US")
    assert cfg_us.use_and_in_hundreds is False
    assert cfg_us.numeric_date_order == "MDY"

    cfg_gb = replace(cfg_us, locale="en-GB", use_and_in_hundreds=None, numeric_date_order=None).resolve()
    assert cfg_gb.locale == "en-GB"
    assert cfg_gb.use_and_in_hundreds is True
    assert cfg_gb.numeric_date_order == "DMY"

    cfg_in = replace(cfg_us, locale="en-IN", use_and_in_hundreds=None, numeric_date_order=None).resolve()
    assert cfg_in.locale == "en-IN"
    assert cfg_in.use_and_in_hundreds is True
    assert cfg_in.numeric_date_order == "DMY"


def test_severity_to_status_mapping():
    """A7: Severity 'info' keeps status 'success', 'warning' gives 'partial', 'error' gives 'failed'."""
    norm = TextNormalizer(NormalizerConfig.for_locale("en-US"))

    # Standalone 4-digit year has info warning -> status must be 'success'
    res_info = norm.normalize("Room 1984")
    assert res_info.status == "success"
    assert any(w.severity == "info" for w in res_info.warnings)
    assert not any(w.severity in ("warning", "error") for w in res_info.warnings)

    # Malformed number has warning -> status must be 'partial'
    res_warn = norm.normalize("Code 12..34")
    assert res_warn.status == "partial"
    assert any(w.severity == "warning" for w in res_warn.warnings)

    # Invalid UTF-8 bytes has error -> status must be 'failed'
    res_err = norm.normalize(b"\xff\xfe")
    assert res_err.status == "failed"
    assert any(w.severity == "error" for w in res_err.warnings)


def test_zwj_emoji_and_regional_flags_preserved():
    """A7: ZWJ emoji sequences and regional flags are never split or corrupted."""
    norm = TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="preserve"))

    # Family emoji with ZWJ: 👨‍👩‍👧
    family_emoji = "👨\u200d👩\u200d👧"
    res1 = norm.normalize(f"{family_emoji} bought 3 tickets.")
    assert family_emoji in res1.normalized_text
    assert "three tickets" in res1.normalized_text
    assert res1.status == "success"

    # Regional indicator pair (US flag): 🇺🇸
    us_flag = "\U0001F1FA\U0001F1F8"
    res2 = norm.normalize(f"Flag {us_flag} costs $5.")
    assert us_flag in res2.normalized_text
    assert "five dollars" in res2.normalized_text
    assert res2.status == "success"


def test_parenthesized_non_negatives():
    """A7: (15% of users), ($500 per month), (2020) are NOT treated as negative numbers."""
    norm = TextNormalizer()

    res1 = norm.normalize("(15% of users)")
    assert res1.normalized_text == "(fifteen percent of users)"
    assert "negative" not in res1.normalized_text

    res2 = norm.normalize("($500 per month)")
    assert res2.normalized_text == "(five hundred dollars per month)"
    assert "negative" not in res2.normalized_text

    res3 = norm.normalize("(2020)")
    assert res3.normalized_text == "(twenty twenty)"
    assert "negative" not in res3.normalized_text


def test_unicode_utils_edge_cases():
    """Targeted coverage tests for unicode_utils branches."""
    # 1. str input starting with BOM character \ufeff via decode_and_validate_input
    text_bom = "\ufeffHello world"
    decoded, _, _ = decode_and_validate_input(text_bom, 100)
    assert decoded == "Hello world"

    # 2. MonotonicCoordinateMapper methods
    m = MonotonicCoordinateMapper.create_identity(5)
    assert m.to_raw_span(1, 4) == (1, 4)
    # empty mapper
    m_empty = MonotonicCoordinateMapper([])
    assert m_empty.to_raw_span(0, 5) == (0, 0)
    # clean_start >= clean_end
    assert m.to_raw_span(3, 2) == (3, 3)

    # 3. is_atomic_continuation checks
    assert is_atomic_continuation("\u200d") is True  # ZWJ
    assert is_atomic_continuation("\ufe0f") is True  # Variation selector
    assert is_atomic_continuation("\U0001F3FB") is True  # Fitzpatrick skin tone
    assert is_atomic_continuation("\U0001F1FA") is True  # Regional indicator
    assert is_atomic_continuation("a") is False

    # 4. Disallowed formatting controls stripped
    controls = "Text\u200bwith\u00adformatting\u2060controls\u200e\u200f\u2066\u2067\u2068\u2069here"
    c_clean, _, c_edits = canonicalize_and_map(controls)
    assert c_clean == "Textwithformattingcontrolshere"
    assert any(e.category == "strip_disallowed" for e in c_edits)


def test_number_rules_additional_branches():
    """Targeted coverage tests for number_rules branches."""
    cfg = NormalizerConfig.for_locale("en-US")

    # verbalize_triplet with exact tens (rem >= 20 and unit == 0), and n == 0
    assert verbalize_triplet(0) == ""
    assert verbalize_triplet(30) == "thirty"
    assert verbalize_triplet(120) == "one hundred twenty"

    # verbalize_cardinal negative, scale words, and decillion+
    assert verbalize_cardinal(-42) == "negative forty-two"
    assert verbalize_cardinal(1_000_000) == "one million"
    assert "one" in verbalize_cardinal(10**36)

    # verbalize_ordinal negative, tens, unit, -ieth ending
    assert verbalize_ordinal(-5) == "negative fifth"
    assert verbalize_ordinal(20) == "twentieth"
    assert verbalize_ordinal(23) == "twenty-third"
    assert verbalize_ordinal(80) == "eightieth"
    assert verbalize_ordinal(100) == "one hundredth"
    assert verbalize_ordinal(105, use_and=True) == "one hundred and fifth"

    # verbalize_digits
    assert verbalize_digits("05", zero_word="zero") == "zero five"
    assert verbalize_digits("a") == "a"

    # verbalize_year negative, 2500, 1900, 1905, 2005 oh
    assert verbalize_year(-500) == "five hundred B C"
    assert verbalize_year(2500) == "two thousand five hundred"
    assert verbalize_year(1900) == "nineteen hundred"
    assert verbalize_year(1905) == "nineteen oh five"
    assert verbalize_year(2005, year_2000s_style="oh") == "twenty oh five"

    # verbalize_indian_cardinal crores, lakhs, thousands, remainder, zero
    assert verbalize_indian_cardinal(0) == "zero"
    assert verbalize_indian_cardinal(10_000_005) == "one crore five"
    assert verbalize_indian_cardinal(500_000) == "five lakh"
    assert verbalize_indian_cardinal(-100_000) == "negative one lakh"

    # verbalize_bare_int_span with leading zeros
    spoken, _, _ = verbalize_bare_int_span("007", cfg)
    assert spoken == "oh oh seven"

    # verbalize_bare_int_span with cardinal_preferred policy
    cfg_cardinal = NormalizerConfig(standalone_4digit_number_policy="cardinal_preferred")
    spoken_c, warns, _ = verbalize_bare_int_span("1984", cfg_cardinal)
    assert spoken_c == "one thousand nine hundred eighty-four"
    assert any(w.code == "AMBIGUOUS_STANDALONE_YEAR" for w in warns)

    # verbalize_grouped_int_span with decimal
    spoken_dec, _, _ = verbalize_grouped_int_span("1,250.50", cfg)
    assert spoken_dec == "one thousand two hundred fifty point five zero"

    # indian grouped int with decimal in en-IN
    cfg_in = NormalizerConfig.for_locale("en-IN")
    spoken_in_dec, _, _ = verbalize_grouped_int_span("1,00,000.50", cfg_in)
    assert spoken_in_dec == "one lakh point five zero"

    # thin space with decimal
    spoken_thin_dec, _, _ = verbalize_grouped_int_span("1\u2009250.50", cfg)
    assert spoken_thin_dec == "one thousand two hundred fifty point five zero"

    # verbalize_malformed_number negative and repeated punctuation
    mal_neg, _, _ = verbalize_malformed_number("-1,2,3", cfg)
    assert "negative" in mal_neg
    mal_punct, _, _ = verbalize_malformed_number("1,,2..3", cfg)
    assert "comma comma" in mal_punct
    mal_dash, _, _ = verbalize_malformed_number("-", cfg)
    assert "negative" in mal_dash

    # 120th -> one hundred twentieth (ends with 'y')
    assert verbalize_ordinal(120) == "one hundred twentieth"

    # decade with 00s (e.g. 1900s)
    spoken_00s, _, _ = verbalize_decade_span("1900s", cfg)
    assert spoken_00s == "nineteen hundreds"

    # malformed number with leading separator and non-digit characters
    spoken_mal_extra, _, _ = verbalize_malformed_number(",1a,2", cfg)
    assert "1a" in spoken_mal_extra


def test_normalizer_and_currency_extra_coverage():
    """Targeted coverage tests for normalizer and currency_rules edge cases."""
    from text_frontend.currency_rules import (
        verbalize_currency_iso_prefix_span,
        verbalize_currency_iso_suffix_span,
    )
    cfg = NormalizerConfig.for_locale("en-US")
    norm = TextNormalizer(cfg)

    # Currency with 1 decimal digit (.5) -> 50 cents
    res1 = norm.normalize("$10.5")
    assert res1.normalized_text == "ten dollars and fifty cents"

    # Currency with .00 -> ten dollars
    res2 = norm.normalize("$10.00")
    assert res2.normalized_text == "ten dollars"

    # Email protected span
    res_email = norm.normalize("Contact user@example.com for info.")
    assert "user at example dot com" in res_email.normalized_text
    cfg_email_pres = NormalizerConfig.for_locale("en-US", email_reading_style="preserve")
    res_email_pres = TextNormalizer(cfg_email_pres).normalize("Contact user@example.com for info.")
    assert "user@example.com" in res_email_pres.normalized_text

    # _validate_digits_accounted_for with unaccounted digit
    unaccounted = norm._validate_digits_accounted_for("test 123", [], [])
    assert len(unaccounted) == 3

    # Non-matching guard returns for span verbalizers
    from text_frontend.number_rules import (
        verbalize_accounting_span,
        verbalize_century_span,
        verbalize_decade_span,
        verbalize_ordinal_span,
    )
    assert verbalize_ordinal_span("bad", cfg) == ("bad", [], False)
    assert verbalize_decade_span("bad", cfg) == ("bad", [], False)
    assert verbalize_decade_span("'ba", cfg) == ("'ba", [], False)
    assert verbalize_century_span("bad", cfg) == ("bad", [], False)
    assert verbalize_accounting_span("bad", cfg) == ("bad", [], False)

    from text_frontend.currency_rules import (
        verbalize_currency_iso_prefix_span,
        verbalize_currency_iso_suffix_span,
    )
    assert verbalize_currency_iso_prefix_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_currency_iso_suffix_span("invalid", cfg) == ("invalid", [], False)

    # Status 'failed' from error in accumulated_warnings at line 298
    err_cand = CandidateSpan(
        start=0,
        end=4,
        category="error_test",
        rule_id="test.error",
        priority=7,
        verbalizer=lambda raw, cfg: (
            raw,
            [NormalizationWarning("TEST_ERR", "Critical error", "error", (0, len(raw)))],
            False,
        ),
    )
    import text_frontend.normalizer
    orig_fn = text_frontend.normalizer.find_number_candidates
    try:
        # Rule warnings with severity='error' downgrade status to 'partial', never 'failed'
        text_frontend.normalizer.find_number_candidates = lambda text, cfg: [err_cand]
        res_error_status = norm.normalize("test")
        assert res_error_status.status == "partial"
        assert any(w.severity == "error" for w in res_error_status.warnings)
    finally:
        text_frontend.normalizer.find_number_candidates = orig_fn

    # Convenience normalize functional wrapper with config + override
    cfg_base = NormalizerConfig.for_locale("en-US")
    res_func = normalize("$100", config=cfg_base, locale="en-GB", style="verbatim")
    assert res_func.status == "success"

    # _scan_residual_nsws pos >= len(indices)
    warns = norm._scan_residual_nsws("Residual $5", [], None)
    assert len(warns) > 0
    assert warns[0].original_span == (0, 0)


def test_phase2_edge_cases_and_branch_coverage():
    """Targeted coverage tests for Phase 2 date/time, unit, identifier, and range branches."""
    from text_frontend.date_time_rules import (
        verbalize_compound_duration_span,
        verbalize_date_range_span,
        verbalize_iso_date_span,
        verbalize_numeric_date_span,
        verbalize_numeric_date_ymd_span,
        verbalize_single_duration_span,
        verbalize_time_range_span,
        verbalize_time_span,
        verbalize_written_date_span,
    )
    from text_frontend.identifier_rules import (
        verbalize_india_phone_span,
        verbalize_local_phone_span,
        verbalize_nanp_phone_span,
        verbalize_product_code_span,
    )
    from text_frontend.unit_rules import (
        verbalize_unit_range_span,
        verbalize_unit_span,
    )
    from text_frontend.currency_rules import verbalize_currency_range_span
    from text_frontend.number_rules import (
        verbalize_fraction,
        verbalize_fraction_span,
        verbalize_mixed_fraction_span,
        verbalize_number_range_span,
        verbalize_ratio_span,
        verbalize_unicode_fraction_span,
    )

    cfg = NormalizerConfig.for_locale("en-US")
    cfg_pres = NormalizerConfig.for_locale("en-US", unresolved_policy="preserve")
    cfg_24h = NormalizerConfig.for_locale("en-US", time_format_preference="24h")

    # Date & Time fallbacks and branches
    assert verbalize_date_range_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_iso_date_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_numeric_date_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_numeric_date_ymd_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_time_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_time_range_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_compound_duration_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_single_duration_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_single_duration_span("45x", cfg) == ("45x", [], False)
    assert verbalize_written_date_span("invalid", cfg) == ("invalid", [], False)

    # Single duration units
    assert verbalize_single_duration_span("1 hr", cfg)[0] == "one hour"
    assert verbalize_single_duration_span("2 hrs", cfg)[0] == "two hours"
    assert verbalize_single_duration_span("1 sec", cfg)[0] == "one second"
    assert verbalize_single_duration_span("2 secs", cfg)[0] == "two seconds"
    assert verbalize_single_duration_span("1 min", cfg)[0] == "one minute"
    assert verbalize_single_duration_span("2 mins", cfg)[0] == "two minutes"

    # Compound duration with seconds
    c_dur, _, _ = verbalize_compound_duration_span("2h 30m 15s", cfg)
    assert "and fifteen seconds" in c_dur

    # Invalid dates in preserve vs literal
    iso_pres, w_iso_p, _ = verbalize_iso_date_span("2023-02-30", cfg_pres)
    assert iso_pres == "2023-02-30"
    iso_lit, w_iso_l, _ = verbalize_iso_date_span("2023-02-30", cfg)
    assert "dash" in iso_lit

    dr_pres, _, _ = verbalize_date_range_span("April 31-32, 2023", cfg_pres)
    assert dr_pres == "April 31-32, 2023"
    dr_lit, _, _ = verbalize_date_range_span("April 31-32, 2023", cfg)
    assert "to" in dr_lit

    ymd_pres, _, _ = verbalize_numeric_date_ymd_span("2023/02/30", cfg_pres)
    assert ymd_pres == "2023/02/30"
    ymd_lit, _, _ = verbalize_numeric_date_ymd_span("2023/02/30", cfg)
    assert "slash" in ymd_lit

    # Malformed time
    t_bad, w_t, _ = verbalize_time_span("25:00", cfg)
    assert any(w.code == "MALFORMED_TIME" for w in w_t)

    # Time zones and UTC offsets
    t_off1, _, _ = verbalize_time_span("14:30 -05:00", cfg)
    assert "minus five hours" in t_off1
    t_off2, _, _ = verbalize_time_span("14:30 +00:00", cfg)
    assert "plus zero" in t_off2
    t_off3, _, _ = verbalize_time_span("14:30 UTC+05:30", cfg)
    assert "U T C plus five thirty" in t_off3

    # 24h mode hour 00:15
    t_24h, _, _ = verbalize_time_span("00:15", cfg_24h)
    assert "zero zero fifteen" in t_24h

    # Written date without year
    wd_noyear, _, _ = verbalize_written_date_span("Oct 29", cfg)
    assert wd_noyear == "October twenty-ninth"

    # Identifier rules fallbacks
    assert verbalize_nanp_phone_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_india_phone_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_local_phone_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_product_code_span("invalid", cfg) == ("invalid", [], False)

    # Unit rules fallbacks & ranges
    assert verbalize_unit_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_unit_range_span("invalid", cfg) == ("invalid", [], False)
    u_dec, _, _ = verbalize_unit_range_span("0.5-1.5 km", cfg)
    assert u_dec == "zero point five to one point five kilometers"
    u_one, _, _ = verbalize_unit_range_span("10-1 km", cfg)
    assert u_one == "ten to one kilometer"

    # Currency range fallback
    assert verbalize_currency_range_span("invalid", cfg) == ("invalid", [], False)

    # Number rules fractions / ranges fallbacks
    assert verbalize_fraction(1, 0) == "one over zero"
    assert verbalize_fraction_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_mixed_fraction_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_unicode_fraction_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_ratio_span("invalid", cfg) == ("invalid", [], False)
    assert verbalize_number_range_span("invalid", cfg) == ("invalid", [], False)


def test_amendment_coverage_gaps():
    from text_frontend.number_rules import verbalize_fraction
    from text_frontend.date_time_rules import (
        verbalize_time_span,
        verbalize_weekday_range_span,
        verbalize_written_date_span,
    )
    from text_frontend.identifier_rules import verbalize_emergency_phone_span
    from text_frontend.unit_rules import (
        verbalize_unit_range_span,
        verbalize_unit_span,
    )

    # 1. Config spoken_leading_zeros validation
    with pytest.raises(ValueError, match="Invalid spoken_leading_zeros"):
        NormalizerConfig(spoken_leading_zeros="invalid")  # type: ignore

    cfg_plain = NormalizerConfig.for_locale("en-US")

    # 2. Number rules dotted year suffix (b.c.) and non-suffix dotted (e.g.)
    res_bc = normalize("Built in 1984 b.c. by soldiers.")
    assert "nineteen eighty-four B C" in res_bc.normalized_text
    res_eg = normalize("In 1984 e.g. someone said.")
    assert "nineteen eighty-four for example" in res_eg.normalized_text

    # 3. Number rules standalone 4-digit cardinal_preferred policy
    cfg_card = NormalizerConfig(standalone_4digit_number_policy="cardinal_preferred")
    res_card = normalize("Room 1984.", config=cfg_card)
    assert "one thousand nine hundred eighty-four" in res_card.normalized_text

    # 4. Fractions with non-standard denominator
    assert verbalize_fraction(1, 17) == "one seventeenth"
    assert verbalize_fraction(3, 17) == "three seventeenths"

    # 5. Normalizer unaccounted digits warning with (0, 0) span
    norm = TextNormalizer()
    warns = norm._validate_digits_accounted_for(
        "123", [], [NormalizationWarning(code="TEST", message="test", severity="info", original_span=(0, 0))]
    )
    assert len(warns) == 3

    # 6. Normalizer overlapping overrides
    cfg_overrides = NormalizerConfig(
        custom_overrides=(("foo bar", "long override"), ("foo", "short override"))
    )
    res_over = normalize("foo bar", config=cfg_overrides)
    assert res_over.normalized_text == "long override"

    # 7. Normalizer functional wrapper with config only
    res_plain = normalize("hello", config=cfg_plain)
    assert res_plain.normalized_text == "hello"

    # 8. Date/time weekday range fallback
    assert verbalize_weekday_range_span("invalid", cfg_plain) == ("invalid", [], False)

    # 9. Written date DMY with weekday
    res_dmy_wk = normalize("Mon, 29 October 2023", locale="en-GB")
    assert "Monday, October twenty-ninth, twenty twenty-three" in res_dmy_wk.normalized_text

    # 10. Written date invalid with preserve policy
    cfg_pres = NormalizerConfig(unresolved_policy="preserve")
    res_pres = normalize("Meeting on Feb 30, 2023.", config=cfg_pres)
    assert "Feb 30, 2023" in res_pres.normalized_text

    # 11. Written date invalid without year
    res_inv_noyear = normalize("Meeting on Feb 30.", locale="en-US")
    assert "February thirty" in res_inv_noyear.normalized_text

    # 12. Written date DMY without year
    res_dmy_noyear = normalize("the 3rd of July", locale="en-US")
    assert "the third of July" in res_dmy_noyear.normalized_text

    # 13. Time 24h with ampm and 00:xx in 12h mode
    t_24h_ampm, _, _ = verbalize_time_span("14:30 PM", cfg_plain)
    assert "two thirty P M" in t_24h_ampm
    t_00_12h, _, _ = verbalize_time_span("00:15", cfg_plain)
    assert "twelve fifteen A M" in t_00_12h
    t_00_ampm, _, _ = verbalize_time_span("00:15 AM", cfg_plain)
    assert "twelve fifteen A M" in t_00_ampm

    # 14. Emergency phone following operator cue without before cue
    res_op = normalize("The 911 operator answered.")
    assert "The nine one one operator answered." == res_op.normalized_text
    assert verbalize_emergency_phone_span("911", cfg_plain)[0] == "nine one one"

    # 15. Unit rules mixed fractions and negative mixed fractions
    res_mixed_u = normalize("Add 1 1/2 kg and -1 1/2 kg flour.")
    assert "one and one half kilograms" in res_mixed_u.normalized_text
    assert "negative one and one half kilograms" in res_mixed_u.normalized_text

    # 16. Unit rules unicode fraction
    res_u_frac = normalize("Pour ½ kg sugar.")
    assert "one half kilogram sugar" in res_u_frac.normalized_text

    # 17. Unit rules invalid fallback
    assert verbalize_unit_span("10 badunit", cfg_plain) == ("10 badunit", [], False)
    assert verbalize_unit_range_span("10-20 badunit", cfg_plain) == ("10-20 badunit", [], False)
    import text_frontend.unit_rules as ur
    orig_map = ur.UNITS_MAP
    try:
        ur.UNITS_MAP = {}
        assert verbalize_unit_span("10 km", cfg_plain) == ("10 km", [], False)
        assert verbalize_unit_range_span("10-20 km", cfg_plain) == ("10-20 km", [], False)
    finally:
        ur.UNITS_MAP = orig_map

    # 18. Phone numbers zero: en-IN reads zero, en-US reads oh
    res_us_ph = normalize("Call 555-0199.", locale="en-US")
    assert "five five five, oh one nine nine" in res_us_ph.normalized_text
    res_in_ph = normalize("Call 555-0199.", locale="en-IN")
    assert "five five five, zero one nine nine" in res_in_ph.normalized_text

    # 19. Phase 3: Identifiers coverage
    # URL verbatim mode
    cfg_verb = NormalizerConfig(url_reading_style="verbatim")
    res_verb = normalize("https://example.com/api?v=1&q=test%20_dash-", config=cfg_verb)
    assert "colon" in res_verb.normalized_text
    assert "slash" in res_verb.normalized_text
    assert "dot" in res_verb.normalized_text
    assert "question mark" in res_verb.normalized_text
    assert "equals" in res_verb.normalized_text
    assert "and" in res_verb.normalized_text
    assert "percent" in res_verb.normalized_text
    assert "underscore" in res_verb.normalized_text
    assert "dash" in res_verb.normalized_text

    # URL conversational with www.
    res_www = normalize("Visit www.example.com/home today.")
    assert "example dot com slash home" in res_www.normalized_text

    # URL preserve
    cfg_pres = NormalizerConfig(url_reading_style="preserve")
    res_pres = normalize("Visit https://example.com/preserve now.", config=cfg_pres)
    assert "https://example.com/preserve" in res_pres.normalized_text

    # Versions
    res_ver = normalize("Upgrade to v2.1.3 immediately.")
    assert "version two point one point three" in res_ver.normalized_text

    # IPv4
    res_ip = normalize("Server at 192.168.1.1 is active.")
    assert "one nine two dot one six eight dot one dot one" in res_ip.normalized_text

    # Hashes: digit+alpha and after cue
    res_hash1 = normalize("Git hash 4b825dc was merged.")
    assert "four b eight two five d c" in res_hash1.normalized_text
    res_hash2 = normalize("commit a1b2c3d was checked.")
    assert "a one b two c three d" in res_hash2.normalized_text

    # Case split: camelCase and SCREAMING_SNAKE
    res_camel = normalize("Call getUserName function.")
    assert "get User Name" in res_camel.normalized_text
    res_snake = normalize("Constant MAX_BUFFER_SIZE reached.")
    assert "max buffer size" in res_snake.normalized_text
    cfg_spelled = NormalizerConfig(identifier_reading="spelled")
    res_spelled = normalize("Variable myVar set.", config=cfg_spelled)
    assert "m y V a r" in res_spelled.normalized_text

    # Inside tag case split check
    res_tag = normalize("<customTag attr='val'>Content</customTag>")
    assert "customTag" not in res_tag.normalized_text or "custom Tag" not in res_tag.normalized_text

    # Email with digits, trailing punctuation, preserve
    res_email_dig = normalize("Email user.123@example.com.")
    assert "user dot one two three at example dot com." in res_email_dig.normalized_text
    cfg_em_pres = NormalizerConfig(email_reading_style="preserve")
    res_em_pres = normalize("Contact support@example.com now.", config=cfg_em_pres)
    assert "support@example.com" in res_em_pres.normalized_text

    # 20. Phase 3: Abbreviations coverage
    from text_frontend.abbreviation_rules import verbalize_mixed_alphanum_span
    # Newline after abbreviation
    res_nl_abbr = normalize("Apples, etc.\nTomorrow we go.")
    assert "etcetera." in res_nl_abbr.normalized_text

    # Mixed forms: 6G, 16K, 1440p, 500p, 360p, 1080i, A300, A350
    res_6g = normalize("Future 6G wireless.")
    assert "six G" in res_6g.normalized_text
    res_16k = normalize("Ultra 16K screen.")
    assert "sixteen K" in res_16k.normalized_text
    res_1440p = normalize("Render in 1440p mode.")
    assert "fourteen forty P" in res_1440p.normalized_text
    res_500p = normalize("Format 500p video.")
    assert "five hundred P" in res_500p.normalized_text
    res_360p = normalize("Stream in 360p mode.")
    assert "three sixty P" in res_360p.normalized_text
    res_1080i = normalize("Broadcast in 1080i signal.")
    assert "ten eighty I" in res_1080i.normalized_text
    res_a300 = normalize("Boarding plane A300 soon.")
    assert "A three hundred" in res_a300.normalized_text
    res_a350 = normalize("Boarding plane A350 soon.")
    assert "A three fifty" in res_a350.normalized_text
    assert verbalize_mixed_alphanum_span("unknown_code", cfg_plain) == ("unknown_code", [], False)

    # Standalone St. without preceding word
    res_st_bare = normalize("St. is an abbreviation.")
    assert "Street is an abbreviation." in res_st_bare.normalized_text

    # Suffix sentence final
    res_jr_fin = normalize("He is John Smith Jr.")
    assert "John Smith Junior." in res_jr_fin.normalized_text

    # 21. Phase 3: Markup parser edge coverage
    # Headings and emphasis at exact start and end of string
    res_h_edge = normalize("# Title")
    assert "Title" == res_h_edge.normalized_text
    res_ast_edge = normalize("*bold*")
    assert "bold" == res_ast_edge.normalized_text
    res_und_edge = normalize("_italic_")
    assert "italic" == res_und_edge.normalized_text
    res_tag_edge = normalize("<b>bold</b>")
    assert "bold" == res_tag_edge.normalized_text
    res_ent_edge = normalize("&amp;")
    assert "and" == res_ent_edge.normalized_text

    # 22. Phase 3: Symbols edge coverage
    from text_frontend.symbol_rules import verbalize_typo_symbol_span
    assert verbalize_typo_symbol_span("©", cfg_plain) == ("copyright", [], False)
    res_tilde_neg = normalize("Temps ~ -5 degrees.")
    assert "approximately negative five degrees" in res_tilde_neg.normalized_text

    # 23. Direct function edge cases for 100% coverage
    from text_frontend.identifier_rules import (
        verbalize_email_span,
        verbalize_version_span,
        verbalize_hash_span,
    )
    assert verbalize_email_span("invalid_email", cfg_plain) == ("invalid_email", [], False)
    assert verbalize_version_span("not_version", cfg_plain) == ("not_version", [], False)
    res_zero_hash = normalize("commit 0a1b2c3d merged.")
    assert "oh a one b two c three d" in res_zero_hash.normalized_text or "zero a one b two c three d" in res_zero_hash.normalized_text
    res_excl_email = normalize("Write to test@example.com!")
    assert "test at example dot com!" in res_excl_email.normalized_text
    res_verb_tilde = normalize("https://example.com/~alice", config=cfg_verb)
    assert "~" in res_verb_tilde.normalized_text or "tilde" in res_verb_tilde.normalized_text

    # Mixed forms branches: 2000p (bot=0), 12345p (fallback), c2c (upper match)
    res_2000p = normalize("Render in 2000p quality.")
    assert "two thousand P" in res_2000p.normalized_text
    assert verbalize_mixed_alphanum_span("12345p", cfg_plain)[0] == "twelve thousand three hundred forty-five P"
    res_c2c = normalize("Model for c2c commerce.")
    assert "C to C" in res_c2c.normalized_text
    res_head_mid = normalize("Intro line.\n# Heading\nBody.")
    assert "Intro line.\nHeading\nBody." == res_head_mid.normalized_text

    # 24. Full config validations
    with pytest.raises(ValueError, match="Invalid identifier_reading"):
        NormalizerConfig(identifier_reading="invalid")  # type: ignore
    with pytest.raises(ValueError, match="Invalid word_slash_style"):
        NormalizerConfig(word_slash_style="invalid")  # type: ignore
    with pytest.raises(ValueError, match="Invalid code_block_policy"):
        NormalizerConfig(code_block_policy="invalid")  # type: ignore
    with pytest.raises(ValueError, match="Invalid non_speech_policy"):
        NormalizerConfig(non_speech_policy="invalid")  # type: ignore
    with pytest.raises(ValueError, match="Invalid emoji_policy"):
        NormalizerConfig(emoji_policy="invalid")  # type: ignore

    # 25. Data loader emoji data
    from text_frontend.data_loader import load_emoji_data
    emoji_dict = load_emoji_data()
    assert isinstance(emoji_dict, dict)

    # 26. Unit rules defensive guards 198 and 218
    import text_frontend.unit_rules as ur
    orig_map = ur.UNITS_MAP
    try:
        ur.UNITS_MAP = {}
        cands_range = ur.find_unit_candidates("10-20 km", cfg_plain)
        assert len(cands_range) == 0
        cands_single = ur.find_unit_candidates("10 km", cfg_plain)
        assert len(cands_single) == 0
    finally:
        ur.UNITS_MAP = orig_map

    # 27. Address number verbalizer variations (3-digit, 4-digit, 5-digit)
    from text_frontend.identifier_rules import (
        verbalize_address_number,
        verbalize_street_address_span,
        verbalize_mixed_identifier_span,
    )
    assert verbalize_address_number("500") == "five hundred"
    assert verbalize_address_number("505") == "five oh five"
    assert verbalize_address_number("1600") == "sixteen hundred"
    assert verbalize_address_number("1605") == "sixteen oh five"
    assert verbalize_address_number("12345") == "one twenty-three forty-five"
    assert verbalize_street_address_span("invalid address", cfg_plain) == ("invalid address", [], False)
    assert verbalize_mixed_identifier_span("foo_bar-1", cfg_plain)[0] == "foo underscore bar dash one"

    # 28. Symbol rules slash verbalizers
    from text_frontend.symbol_rules import (
        verbalize_word_slash_pair,
        verbalize_standalone_slash_abbr,
        verbalize_hashtag_span,
        verbalize_emoticon_span,
        verbalize_exponent_span,
        verbalize_superscript_span,
        verbalize_multiplier_speed_span,
        verbalize_greek_span,
    )
    assert verbalize_standalone_slash_abbr("w/o", cfg_plain)[0] == "without"
    assert verbalize_standalone_slash_abbr("bad_slash", cfg_plain) == ("bad_slash", [], False)
    assert verbalize_word_slash_pair("TCP/IP", cfg_plain)[0] == "T C P slash I P"
    assert verbalize_word_slash_pair("bad_pair", cfg_plain) == ("bad_pair", [], False)
    assert verbalize_hashtag_span("#NASA", cfg_plain)[0] == "hashtag NASA"
    assert verbalize_emoticon_span(":)", NormalizerConfig.for_locale("en-US", emoji_policy="preserve"))[0] == ":)"
    assert verbalize_exponent_span("10^5", cfg_plain)[0] == "ten to the fifth power"
    assert verbalize_exponent_span("x^bad", cfg_plain) == ("x^bad", [], False)
    assert verbalize_exponent_span("bad", cfg_plain) == ("bad", [], False)
    assert verbalize_superscript_span("bad", cfg_plain) == ("bad", [], False)
    assert verbalize_superscript_span("x⁴", cfg_plain)[0] == "x to the fourth power"
    assert verbalize_multiplier_speed_span("bad", cfg_plain) == ("bad", [], False)
    assert verbalize_greek_span("bad", cfg_plain) == ("bad", [], False)

    # 29. Final 100% target coverage closures (unicode_utils, normalizer, number_rules)
    norm_drop = TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="drop", non_speech_policy="pause"))
    norm_drop.normalize("Unrecognized non-\nword hyphenation here.")
    norm_drop.normalize("First sentence.\nwhat is 10 - 3")
    norm_drop.normalize("calculate 20 / 4 = 5")
    norm_drop.normalize("what is 1 / 2")
    norm_drop.normalize(" [pause] hello")
    norm_drop.normalize("👋 world")
    norm_drop.normalize("Hello 👋.")
    norm_drop.normalize("Hello👋.")
    norm_drop.normalize("👋.")
    norm_drop.normalize("Hello 👋")

    # 30. DataLoader emoji_names.json and airports.json not found fallback coverage
    from unittest.mock import patch
    import text_frontend.data_loader as dl
    import text_frontend.symbol_rules as sr

    with patch.object(dl.Path, "exists", return_value=False):
        dl.load_emoji_data.cache_clear()
        sr.get_emoji_regex.cache_clear()
        assert dl.load_emoji_data.__wrapped__() == {}
        assert dl.load_airports_data.__wrapped__() == frozenset()
        assert sr.get_emoji_regex().pattern

    dl.load_emoji_data.cache_clear()
    sr.get_emoji_regex.cache_clear()

    import unicodedata
    with patch.object(unicodedata, "name", side_effect=Exception("boom")):
        assert sr.verbalize_emoji_span("\U0001f999", NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"))[0] == "emoji"




