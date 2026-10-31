"""Tests for core normalization pipeline, encoding contracts, safety limits, and overlap resolution."""

from __future__ import annotations

import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer, normalize
from text_frontend.validation import NormalizationResult
from tests.conftest import assert_transformation_invariants


def test_empty_string_input(default_normalizer: TextNormalizer):
    res = default_normalizer.normalize("")
    assert res.normalized_text == ""
    assert res.status == "success"
    assert len(res.transformations) == 0
    assert len(res.warnings) == 0


def test_whitespace_only_input(default_normalizer: TextNormalizer):
    res = default_normalizer.normalize("   \t\n  ")
    assert res.normalized_text == ""
    assert res.status == "success"
    assert len(res.transformations) == 0
    assert len(res.warnings) == 0


def test_utf8_bytes_input(default_normalizer: TextNormalizer):
    raw_bytes = "The price is $50.".encode("utf-8")
    res = default_normalizer.normalize(raw_bytes)
    assert res.status == "success"
    assert res.normalized_text == "The price is fifty dollars."
    assert res.original_text == "The price is $50."
    assert_transformation_invariants(raw_bytes, res)


def test_utf8_bom_bytes_input(default_normalizer: TextNormalizer):
    raw_bytes = b"\xef\xbb\xbfThe total is $10."
    res = default_normalizer.normalize(raw_bytes)
    assert res.status == "success"
    assert res.normalized_text == "The total is ten dollars."
    assert res.original_text == "The total is $10."
    assert_transformation_invariants(raw_bytes, res)


def test_invalid_utf8_bytes_rejected(default_normalizer: TextNormalizer):
    invalid_bytes = b"\xff\xfe\x00\x00"  # Invalid UTF-8 sequence
    res = default_normalizer.normalize(invalid_bytes)
    assert res.status == "failed"
    assert res.normalized_text == ""
    assert any(w.code == "INVALID_UTF8_ENCODING" for w in res.warnings)


def test_lone_surrogates_rejected(default_normalizer: TextNormalizer):
    lone_surrogate_text = "Bad surrogate: \ud83d test"
    res = default_normalizer.normalize(lone_surrogate_text)
    assert res.status == "failed"
    assert res.normalized_text == ""
    assert any(w.code == "LONE_SURROGATES_DETECTED" for w in res.warnings)


def test_max_input_length_exceeded():
    cfg = NormalizerConfig(max_input_length=50)
    normalizer = TextNormalizer(cfg)
    long_text = "a" * 51
    res = normalizer.normalize(long_text)
    assert res.status == "failed"
    assert res.normalized_text == ""
    assert any(w.code == "LENGTH_LIMIT_EXCEEDED" for w in res.warnings)


def test_c0_control_stripping_except_whitespace(default_normalizer: TextNormalizer):
    # Contains null byte \x00, bell \x07, but keeps \t, \n
    raw = "Line 1\x00\x07\twith 42\nLine 2"
    res = default_normalizer.normalize(raw)
    assert res.status == "success"
    assert "forty-two" in res.normalized_text
    assert "\x00" not in res.normalized_text
    assert "\x07" not in res.normalized_text
    assert any(e.category == "strip_disallowed" for e in res.edits)
    assert_transformation_invariants(raw, res)


def test_smart_quotes_and_contractions_preserved(default_normalizer: TextNormalizer):
    raw = "“She didn’t pay $20,” he said."
    res = default_normalizer.normalize(raw)
    assert res.status == "success"
    assert "didn't" in res.normalized_text
    assert "twenty dollars" in res.normalized_text
    assert '"She didn\'t pay twenty dollars," he said.' == res.normalized_text
    assert_transformation_invariants(raw, res)


def test_protected_url_not_mangled(default_normalizer: TextNormalizer):
    raw = "Go to https://example.com/item/100 and buy 2."
    res = default_normalizer.normalize(raw)
    assert res.status == "success"
    assert "example dot com slash item slash one hundred" in res.normalized_text
    assert "buy two." in res.normalized_text
    assert_transformation_invariants(raw, res)

    # With url_reading_style='preserve', URL is preserved literally
    cfg_pres = NormalizerConfig.for_locale("en-US", url_reading_style="preserve")
    res_pres = TextNormalizer(cfg_pres).normalize(raw)
    assert "https://example.com/item/100" in res_pres.normalized_text


def test_custom_overrides_priority_and_boundaries():
    cfg = NormalizerConfig(
        custom_overrides=(
            ("TTS", "text to speech"),
            ("cat", "feline"),
            ("caterpillar", "larva"),
        )
    )
    norm = TextNormalizer(cfg)

    # Word boundary test: "cat" should match "cat", not "caterpillar" or "scatter"
    res1 = norm.normalize("The cat saw a caterpillar in scatter.")
    assert "The feline saw a larva in scatter." == res1.normalized_text

    # Longest match wins between overlapping overrides
    res2 = norm.normalize("A caterpillar climbed up.")
    assert "A larva climbed up." == res2.normalized_text


def test_override_inside_protected_span_loses_unless_whole_match():
    cfg = NormalizerConfig(
        custom_overrides=(
            ("example", "sample"),
            ("https://target.com", "target website"),
        ),
        url_reading_style="preserve",
    )
    norm = TextNormalizer(cfg)

    # "example" is inside URL -> loses, URL stays intact
    res = norm.normalize("Visit https://example.com and https://target.com")
    assert "https://example.com" in res.normalized_text
    assert "target website" in res.normalized_text


def test_property_monotonic_non_overlapping_spans(default_normalizer: TextNormalizer):
    raw = "The 1st item costs $10.50, the 2nd is $20, and the 3rd is 25% off in 2024."
    res = default_normalizer.normalize(raw)
    assert res.status == "success"
    assert_transformation_invariants(raw, res)


def test_functional_convenience_normalize():
    res = normalize("Cost is $50.", locale="en-US")
    assert res.normalized_text == "Cost is fifty dollars."
    assert res.status == "success"


def test_nbsp_and_thin_space_cleanup(default_normalizer: TextNormalizer):
    """A2: After grouping decisions, convert remaining U+00A0, U+2009, U+202F to ordinary space."""
    raw = "5\u00a0apples and 10\u2009oranges and 15\u202fbananas."
    res = default_normalizer.normalize(raw)
    assert res.status == "success"
    assert res.normalized_text == "five apples and ten oranges and fifteen bananas."
    assert not any(c in res.normalized_text for c in "\u00a0\u2009\u202f")
    assert any(e.category == "normalize_space" for e in res.edits)
    assert_transformation_invariants(raw, res)
