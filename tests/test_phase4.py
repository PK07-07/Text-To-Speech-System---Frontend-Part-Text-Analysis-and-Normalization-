"""Comprehensive unit and integration tests for Phase 4 (D1 - D4).

Covers:
- D1: Emoji & Emoticon handling (drop, verbalize, pause, preserve)
- D1: Non-speech brackets ([laughter], (applause), etc. with drop, keep, pause)
- D2: Math operators in numeric context (+, -, *, /, =, ≠, ≤, ≥, <, >, ±)
- D2: Dimensions (2D, 3D, display resolutions)
- D2: Scientific notation (10^exp, 10²³, E-notation)
- D2: Powers, exponents, superscripts (10^5, x^2, 5², x³)
- D2: Square root (√16, √2)
- D2: Greek letters & constants (α, β, π, Ω, ∞)
- D2: Chemical formulas (H2O, CO2, NaCl, H2SO4)
- D2: Prose safeguards ("x marks the spot", "a - b")
- D3: Ligatures (ﬁ, ﬂ, æ, œ) and monotonic coordinate tracking
- D3: Multiple punctuation (!!, ???, ...., …)
- D3: Line-break hyphenation repair (exam-\nple)
- D3: Prose dashes (—, –)
- D4: SSML mode verification (preservation vs stripping, nested tags, say-as, phoneme)
"""

from __future__ import annotations

import pytest

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants


@pytest.fixture
def default_norm() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


@pytest.fixture
def verbalize_emoji_norm() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"))


@pytest.fixture
def pause_emoji_norm() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="pause"))


@pytest.fixture
def preserve_emoji_norm() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="preserve"))


# ---------------------------------------------------------------------------
# D1: Emojis & Emoticons
# ---------------------------------------------------------------------------


def test_emoji_drop_policy(default_norm: TextNormalizer):
    """Default emoji_policy='drop' strips emojis."""
    raw = "Hello 👋 world! Nice job 👍."
    res = default_norm.normalize(raw)
    assert "👋" not in res.normalized_text
    assert "👍" not in res.normalized_text
    assert res.normalized_text == "Hello world! Nice job."
    assert res.status == "success"
    assert_transformation_invariants(raw, res)


def test_emoji_verbalize_policy(verbalize_emoji_norm: TextNormalizer):
    """emoji_policy='verbalize' translates emojis to spoken text."""
    raw = "Hello 👋 world! Party 🎉 time."
    res = verbalize_emoji_norm.normalize(raw)
    assert "waving hand" in res.normalized_text
    assert "party popper" in res.normalized_text
    assert res.status == "success"
    assert_transformation_invariants(raw, res)


def test_emoji_complex_zwj_and_skin_tones(verbalize_emoji_norm: TextNormalizer):
    """Verbalizes compound ZWJ sequences and skin-tone modified emojis."""
    raw = "Family 👨‍👩‍👧 went to the park with 👍🏻."
    res = verbalize_emoji_norm.normalize(raw)
    assert "family: man, woman, girl" in res.normalized_text
    assert "thumbs up: light skin tone" in res.normalized_text
    assert res.status == "success"
    assert_transformation_invariants(raw, res)


def test_emoji_pause_and_preserve(pause_emoji_norm: TextNormalizer, preserve_emoji_norm: TextNormalizer):
    """emoji_policy='pause' outputs comma; 'preserve' keeps glyph intact."""
    raw = "Great news 🔥 check this."
    res_pause = pause_emoji_norm.normalize(raw)
    assert "," in res_pause.normalized_text
    assert "🔥" not in res_pause.normalized_text

    res_pres = preserve_emoji_norm.normalize(raw)
    assert "🔥" in res_pres.normalized_text
    assert_transformation_invariants(raw, res_pres)


def test_emoticons_verbalize_and_boundaries(verbalize_emoji_norm: TextNormalizer):
    """Emoticons are recognized with boundary safeguards."""
    raw = "Good morning :) Have fun :D love you <3"
    res = verbalize_emoji_norm.normalize(raw)
    assert "smiling face" in res.normalized_text
    assert "grinning face" in res.normalized_text
    assert "heart" in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_emoticons_not_triggered_in_urls_or_ratios(verbalize_emoji_norm: TextNormalizer):
    """Safeguards: http:// and 3:4 are not hijacked as emoticons."""
    raw = "Visit https://example.com/test with aspect ratio 16:9."
    res = verbalize_emoji_norm.normalize(raw)
    assert "smiling" not in res.normalized_text
    assert "skeptical" not in res.normalized_text
    assert "sixteen to nine" in res.normalized_text or "sixteen by nine" in res.normalized_text


# ---------------------------------------------------------------------------
# D1: Non-Speech Handling
# ---------------------------------------------------------------------------


def test_non_speech_drop_policy(default_norm: TextNormalizer):
    """Default non_speech_policy='drop' strips bracketed sounds."""
    raw = "She said [laughter] that was funny [pause] indeed."
    res = default_norm.normalize(raw)
    assert "[laughter]" not in res.normalized_text
    assert "[pause]" not in res.normalized_text
    assert res.normalized_text == "She said that was funny indeed."
    assert_transformation_invariants(raw, res)


def test_non_speech_keep_and_pause_policies():
    """Tests non_speech_policy='keep' and 'pause'."""
    raw = "The audience cheered (applause) loudly."
    keep_norm = TextNormalizer(NormalizerConfig.for_locale("en-US", non_speech_policy="keep"))
    res_keep = keep_norm.normalize(raw)
    assert "(applause)" in res_keep.normalized_text

    pause_norm = TextNormalizer(NormalizerConfig.for_locale("en-US", non_speech_policy="pause"))
    res_pause = pause_norm.normalize(raw)
    assert "," in res_pause.normalized_text
    assert "(applause)" not in res_pause.normalized_text


# ---------------------------------------------------------------------------
# D2: Math & Scientific Notation
# ---------------------------------------------------------------------------


def test_dimensions_2d_and_3d(default_norm: TextNormalizer):
    """Verbalizes 2D, 3D, and display dimensions."""
    cases = [
        ("Room is 10x20 feet.", "Room is ten by twenty feet."),
        ("Box is 4 x 6 x 8 inches.", "Box is four by six by eight inches."),
        ("Display is 1920x1080 resolution.", "Display is nineteen twenty by ten eighty resolution."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_dimension_prose_safeguard(default_norm: TextNormalizer):
    """'x marks the spot' is never treated as a dimension."""
    raw = "Remember that x marks the spot."
    res = default_norm.normalize(raw)
    assert res.normalized_text == "Remember that x marks the spot."
    assert "by" not in res.normalized_text


def test_scientific_notation(default_norm: TextNormalizer):
    """Verbalizes 10^exp, superscript exponents, and E-notation."""
    cases = [
        ("Speed of light is 3.0 x 10^8 meters per second.", "Speed of light is three point zero times ten to the eighth meters per second."),
        ("Constant is 6.02 × 10²³ atoms.", "Constant is six point zero two times ten to the power of twenty-three atoms."),
        ("Small value 1e-6 seconds.", "Small value one times ten to the negative six seconds."),
        ("Distance 2.5E10 meters.", "Distance two point five times ten to the tenth meters."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_exponents_and_superscripts(default_norm: TextNormalizer):
    """Verbalizes powers and superscripts: 10^5, x^2, 5², x³."""
    cases = [
        ("Compute 10^5 now.", "Compute ten to the fifth power now."),
        ("Solve for x^2 equals zero.", "Solve for x squared equals zero."),
        ("Value is 5² units.", "Value is five squared units."),
        ("Volume is x³.", "Volume is x cubed."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_square_root(default_norm: TextNormalizer):
    """Verbalizes √16 -> square root of sixteen."""
    cases = [
        ("Calculate √16 easily.", "Calculate square root of sixteen easily."),
        ("Value is √2 approximately.", "Value is square root of two approximately."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_chemical_formulas(default_norm: TextNormalizer):
    """Verbalizes exact chemical formulas."""
    cases = [
        ("Drink H2O daily.", "Drink H two O daily."),
        ("High levels of CO2 and SO2.", "High levels of C O two and S O two."),
        ("Formula for salt is NaCl.", "Formula for salt is N a C l."),
        ("Acid is H2SO4.", "Acid is H two S O four."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_greek_letters(default_norm: TextNormalizer):
    """Verbalizes Greek letters and constants outside units."""
    cases = [
        ("Angle α and angle β sum to γ.", "Angle alpha and angle beta sum to gamma."),
        ("Circumference is 2π times r.", "Circumference is two pi times r."),
        ("Impedance is Ω in theory.", "Impedance is omega in theory."),
        ("Limit goes to ∞.", "Limit goes to infinity."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_math_operators_in_numeric_context(default_norm: TextNormalizer):
    """Verbalizes +, -, *, /, =, ≠, ≤, ≥, <, >, ± in numeric context."""
    cases = [
        ("Equation: 2 + 2 = 4.", "Equation: two plus two equals four."),
        ("Result: 10 - 3 = 7.", "Result: ten minus three equals seven."),
        ("Product: 5 * 6 = 30.", "Product: five times six equals thirty."),
        ("Division: 20 / 4 = 5.", "Division: twenty divided by four equals five."),
        ("Logic: 5 ≠ 10.", "Logic: five does not equal ten."),
        ("Compare: 10 < 20 and 50 > 30.", "Compare: ten is less than twenty and fifty is greater than thirty."),
        ("Bounds: 5 <= 10 and 20 >= 10.", "Bounds: five is less than or equal to ten and twenty is greater than or equal to ten."),
        ("Tolerance is ±5 mm.", "Tolerance is plus or minus five millimeters."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_math_prose_safeguard(default_norm: TextNormalizer):
    """Letters with dashes (a - b) are not hijacked as subtraction."""
    raw = "Choose between option a - b today."
    res = default_norm.normalize(raw)
    assert "minus" not in res.normalized_text


# ---------------------------------------------------------------------------
# D3: Punctuation, Ligatures & Hyphenation
# ---------------------------------------------------------------------------


def test_ligatures_expansion_and_coordinates(default_norm: TextNormalizer):
    """Typographic ligatures expand to ASCII while æ and œ remain intact."""
    raw = "A ﬁne ﬂight with ﬅyle and Cæsar œvre."
    res = default_norm.normalize(raw)
    assert res.normalized_text == "A fine flight with style and Cæsar œvre."
    assert any(e.category == "expand_ligature" for e in res.edits)
    assert_transformation_invariants(raw, res)


def test_multiple_punctuation_normalization(default_norm: TextNormalizer):
    """Repeated !!, ???, ...., and … are normalized."""
    raw = "Really?? Yes!! It happened.... Wait… now."
    res = default_norm.normalize(raw)
    assert res.normalized_text == "Really? Yes! It happened... Wait... now."
    assert any(e.category in ("normalize_punctuation", "canonicalize_ellipsis") for e in res.edits)
    assert_transformation_invariants(raw, res)


def test_line_break_hyphenation_repair(default_norm: TextNormalizer):
    """Hyphenation across newlines is repaired if joined word is in lexicon."""
    raw = "This is a great exam-\nple of hyphen repair."
    res = default_norm.normalize(raw)
    assert "example" in res.normalized_text
    assert "exam-ple" not in res.normalized_text
    assert any(e.category == "repair_hyphenation" for e in res.edits)
    assert_transformation_invariants(raw, res)


def test_prose_dashes(default_norm: TextNormalizer):
    """Em/en dashes outside numeric ranges provide clause boundaries."""
    raw = "The strategy—which was bold—succeeded."
    res = default_norm.normalize(raw)
    assert "The strategy, which was bold, succeeded." == res.normalized_text
    assert_transformation_invariants(raw, res)


# ---------------------------------------------------------------------------
# D4: SSML Verification
# ---------------------------------------------------------------------------


def test_ssml_mode_detailed_verification():
    """Full SSML tags (say-as, phoneme, sub, emphasis, audio) are preserved in ssml_mode=True."""
    ssml_text = (
        '<speak>'
        '<emphasis level="strong">Caution</emphasis>: '
        '<say-as interpret-as="cardinal">12345</say-as> items. '
        '<phoneme alphabet="ipa" ph="tə\'meɪtoʊ">tomato</phoneme> '
        '<sub alias="World Wide Web">WWW</sub>. '
        '<audio src="https://example.com/beep.mp3"/>'
        '</speak>'
    )
    norm = TextNormalizer(NormalizerConfig.for_locale("en-US", ssml_mode=True))
    res = norm.normalize(ssml_text)
    assert '<speak>' in res.normalized_text
    assert '<emphasis level="strong">' in res.normalized_text
    assert '<say-as interpret-as="cardinal">' in res.normalized_text
    assert 'twelve thousand three hundred forty-five' in res.normalized_text
    assert '</say-as>' in res.normalized_text
    assert '<phoneme alphabet="ipa" ph="tə\'meɪtoʊ">tomato</phoneme>' in res.normalized_text
    assert '<sub alias="World Wide Web">' in res.normalized_text
    assert '</sub>' in res.normalized_text
    assert '<audio src="https://example.com/beep.mp3"/>' in res.normalized_text
    assert res.status == "success"
    assert_transformation_invariants(ssml_text, res)


def test_ssml_mode_false_strips_all_ssml_tags():
    """In ssml_mode=False, SSML tags are cleanly stripped, leaving speech text."""
    ssml_text = (
        '<speak>'
        '<emphasis level="strong">Caution</emphasis>: '
        '<say-as interpret-as="cardinal">12345</say-as> items. '
        '</speak>'
    )
    norm = TextNormalizer(NormalizerConfig.for_locale("en-US", ssml_mode=False))
    res = norm.normalize(ssml_text)
    assert '<speak>' not in res.normalized_text
    assert '<emphasis' not in res.normalized_text
    assert '<say-as' not in res.normalized_text
    assert res.normalized_text.strip() == "Caution: twelve thousand three hundred forty-five items."
    assert res.status == "success"
    assert_transformation_invariants(ssml_text, res)


# ---------------------------------------------------------------------------
# Additional Edge Cases for 100% Branch Coverage
# ---------------------------------------------------------------------------


def test_unlisted_emoji_and_emoticon_policies():
    """Tests unlisted emoji fallback to unicodedata and emoticon policies."""
    # Unlisted emoji: 🦄 (UNICORN)
    norm_verb = TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="verbalize"))
    res_verb = norm_verb.normalize("A 🦄 appeared.")
    assert "unicorn" in res_verb.normalized_text

    # Emoticon policies: drop, pause, preserve
    norm_drop = TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="drop"))
    assert norm_drop.normalize("Hello :) world.").normalized_text == "Hello world."

    norm_pause = TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="pause"))
    assert "," in norm_pause.normalize("Hello :) world.").normalized_text

    norm_pres = TextNormalizer(NormalizerConfig.for_locale("en-US", emoji_policy="preserve"))
    assert ":)" in norm_pres.normalize("Hello :) world.").normalized_text


def test_scientific_and_exponent_variations(default_norm: TextNormalizer):
    """Tests large powers, superscript ordinals, and math operators."""
    cases = [
        ("Mass is 1.5 x 10^15 kilograms.", "Mass is one point five times ten to the power of fifteen kilograms."),
        ("Value is 2.0 × 10⁸ units.", "Value is two point zero times ten to the eighth units."),
        ("Variable x^12.", "Variable x to the power of twelve."),
        ("Calculate 2⁴ now.", "Calculate two to the fourth power now."),
        ("Power x⁵.", "Power x to the fifth power."),
        ("Compare 10 ± 2 mm.", "Compare ten plus or minus two millimeters."),
        ("Logic 5 ≠ 10.", "Logic five does not equal ten."),
    ]
    for raw, expected in cases:
        res = default_norm.normalize(raw)
        assert res.normalized_text == expected
        assert_transformation_invariants(raw, res)


def test_symbol_verbalizer_fallbacks(default_norm: TextNormalizer):
    """Directly verifies fallback paths in symbol verbalizers."""
    from text_frontend.symbol_rules import (
        verbalize_dimension_span,
        verbalize_emoticon_span,
        verbalize_exponent_span,
        verbalize_sci_note_span,
        verbalize_sqrt_span,
        verbalize_superscript_span,
    )

    cfg = NormalizerConfig.for_locale("en-US")
    assert verbalize_dimension_span("invalid", cfg)[0] == "invalid"
    assert verbalize_sci_note_span("invalid", cfg)[0] == "invalid"
    cfg_verb = NormalizerConfig.for_locale("en-US", emoji_policy="verbalize")
    assert verbalize_emoticon_span("invalid", cfg_verb)[0] == "invalid"
    assert verbalize_exponent_span("invalid", cfg)[0] == "invalid"
    assert verbalize_superscript_span("invalid", cfg)[0] == "invalid"
    assert verbalize_sqrt_span("√", cfg)[0] == "square root"

