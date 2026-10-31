"""Unit tests for C1: Markup Parser (HTML, Markdown, Entities, SSML)."""

from __future__ import annotations

import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants


@pytest.fixture
def normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


@pytest.fixture
def ssml_normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US", ssml_mode=True))


def test_html_allowlist_block_and_inline(normalizer: TextNormalizer):
    raw = "<p>Hello <b>bold</b> world!</p>"
    res = normalizer.normalize(raw)
    assert res.normalized_text.strip() == "Hello bold world!"
    assert_transformation_invariants(raw, res)


def test_html_break_tag(normalizer: TextNormalizer):
    raw = "Line one.<br/>Line two."
    res = normalizer.normalize(raw)
    assert res.normalized_text == "Line one. Line two."
    assert_transformation_invariants(raw, res)


def test_html_drop_script_and_style(normalizer: TextNormalizer):
    raw = "<script>alert('bad');</script>Safe <style>body{color:red;}</style>text."
    res = normalizer.normalize(raw)
    assert res.normalized_text == "Safe text."
    assert "alert" not in res.normalized_text
    assert "color:red" not in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_html_non_allowlisted_tags_preserved(normalizer: TextNormalizer):
    raw = "Formula: a < b and c > d with <customTag>value</customTag>."
    res = normalizer.normalize(raw)
    assert "a < b and c > d" in res.normalized_text
    assert "<customTag>value</customTag>" in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_html_entity_decoding(normalizer: TextNormalizer):
    raw = "Tom &amp; Jerry at &quot;home&#39;s&quot; with &gt; 5 items."
    res = normalizer.normalize(raw)
    assert res.normalized_text == 'Tom and Jerry at "home\'s" with > five items.'
    assert_transformation_invariants(raw, res)


def test_markdown_links(normalizer: TextNormalizer):
    raw = "Click [our official website](https://example.com/info) now."
    res = normalizer.normalize(raw)
    assert res.normalized_text == "Click our official website now."
    assert_transformation_invariants(raw, res)


def test_markdown_headings(normalizer: TextNormalizer):
    raw = "# Main Heading\nParagraph with Item #1."
    res = normalizer.normalize(raw)
    assert "Main Heading\nParagraph with Item number one." == res.normalized_text
    assert "# Main" not in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_markdown_emphasis(normalizer: TextNormalizer):
    raw = "This is *very important* and _extremely critical_."
    res = normalizer.normalize(raw)
    assert res.normalized_text == "This is very important and extremely critical."
    assert_transformation_invariants(raw, res)


def test_markdown_emphasis_non_triggers(normalizer: TextNormalizer):
    raw = "Math 5*10=50 and code snake_case_variable."
    res = normalizer.normalize(raw)
    assert "snake case variable" in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_ssml_mode_disabled_strips_ssml_tags(normalizer: TextNormalizer):
    raw = "<speak>Hello <prosody rate='fast'>world</prosody>!</speak>"
    res = normalizer.normalize(raw)
    assert "<speak>" not in res.normalized_text
    assert "<prosody" not in res.normalized_text
    assert "Hello world!" in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_ssml_mode_enabled_preserves_ssml_tags(ssml_normalizer: TextNormalizer):
    raw = '<speak>Hello <break time="1s"/> <prosody rate="fast">world</prosody>!</speak>'
    res = ssml_normalizer.normalize(raw)
    assert "<speak>" in res.normalized_text
    assert '<break time="1s"/>' in res.normalized_text
    assert '<prosody rate="fast">' in res.normalized_text
    assert "</prosody>" in res.normalized_text
    assert "</speak>" in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_unclosed_script_and_style_tags(normalizer: TextNormalizer):
    raw = "<script>alert('unclosed'); Keep this safe text."
    res = normalizer.normalize(raw)
    assert "Keep this safe text." in res.normalized_text
    assert "<script>" not in res.normalized_text
    assert any(w.code == "UNCLOSED_SCRIPT_TAG" for w in res.warnings)


def test_ssml_audio_and_phoneme_custom_attributes(ssml_normalizer: TextNormalizer):
    raw = '<speak><audio src="sound.mp3" clipBegin="1s">chime</audio><phoneme alphabet="ipa" ph="t&#x259;me&#x26A;to&#x28A;">tomato</phoneme></speak>'
    res = ssml_normalizer.normalize(raw)
    assert '<audio src="sound.mp3" clipBegin="1s">' in res.normalized_text
    assert '<phoneme alphabet="ipa" ph="t\u0259me\u026ato\u028a">' in res.normalized_text

