"""Unit tests for symbols (@, &, #, _, ~, /, typography) (Phase 3 C4)."""

from __future__ import annotations

import pytest

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants


@pytest.fixture(scope="module")
def normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


def test_at_symbol(normalizer: TextNormalizer):
    cases = [
        ("Tickets @ $10 each.", "Tickets at ten dollars each."),
        ("Follow @alice on twitter.", "Follow at alice on twitter."),
        ("Meet @ noon today.", "Meet at noon today."),
        ("Price @ 25 percent off.", "Price at twenty-five percent off."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_ampersand_symbol(normalizer: TextNormalizer):
    cases = [
        ("Rock & Roll music.", "Rock and Roll music."),
        ("Ben & Jerry's ice cream.", "Ben and Jerry's ice cream."),
        ("Listening to R&B tonight.", "Listening to R and B tonight."),
        ("Questions & Answers.", "Questions and Answers."),
        ("Procter & Gamble products.", "Procter and Gamble products."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_24x7_and_dimensions(normalizer: TextNormalizer):
    assert normalizer.normalize("Open 24x7.").normalized_text == "Open twenty-four seven."
    assert normalizer.normalize("Available 24X7 daily.").normalized_text == "Available twenty-four seven daily."


def test_telephony_keypad_symbols(normalizer: TextNormalizer):
    norm_gb = TextNormalizer(NormalizerConfig.for_locale("en-GB"))

    # *67 star code
    assert normalizer.normalize("Dial *67 to block caller ID.").normalized_text == "Dial star six seven to block caller I D."

    # Telephony commands: press/dial/enter/hit/key * or #
    assert normalizer.normalize("Press * for operator.").normalized_text == "Press star for operator."
    assert normalizer.normalize("Press # to save.").normalized_text == "Press pound to save."
    assert norm_gb.normalize("Dial # to confirm.").normalized_text == "Dial hash to confirm."

    # Telephony sequences: * then #, * or #, # or *, # then *
    assert normalizer.normalize("Press * then # on phone.").normalized_text == "Press star then pound on phone."
    assert normalizer.normalize("Dial # or * to cancel.").normalized_text == "Dial pound or star to cancel."
    assert normalizer.normalize("Hit * or * again.").normalized_text == "Hit star or star again."
    assert normalizer.normalize("Key # then #.").normalized_text == "Key pound then pound."

    # Exponents: 2^5
    assert normalizer.normalize("The result is 2^5.").normalized_text == "The result is two to the fifth power."



def test_hash_symbol(normalizer: TextNormalizer):
    cases = [
        ("Winner is #1 always.", "Winner is number one always."),
        ("Order #100 was shipped.", "Order number one oh oh was shipped."),
        ("Question #42 answered.", "Question number forty-two answered."),
        ("Check out #trending topics.", "Check out hashtag trending topics."),
        ("Track # in the album.", "Track number in the album."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_24x7_and_dimensions(normalizer: TextNormalizer):
    assert normalizer.normalize("Open 24x7.").normalized_text == "Open twenty-four seven."
    assert normalizer.normalize("Available 24X7 daily.").normalized_text == "Available twenty-four seven daily."


def test_telephony_keypad_symbols(normalizer: TextNormalizer):
    norm_gb = TextNormalizer(NormalizerConfig.for_locale("en-GB"))

    # *67 star code
    assert normalizer.normalize("Dial *67 to block caller ID.").normalized_text == "Dial star six seven to block caller I D."

    # Telephony commands: press/dial/enter/hit/key * or #
    assert normalizer.normalize("Press * for operator.").normalized_text == "Press star for operator."
    assert normalizer.normalize("Press # to save.").normalized_text == "Press pound to save."
    assert norm_gb.normalize("Dial # to confirm.").normalized_text == "Dial hash to confirm."

    # Telephony sequences: * then #, * or #, # or *, # then *
    assert normalizer.normalize("Press * then # on phone.").normalized_text == "Press star then pound on phone."
    assert normalizer.normalize("Dial # or * to cancel.").normalized_text == "Dial pound or star to cancel."
    assert normalizer.normalize("Hit * or * again.").normalized_text == "Hit star or star again."
    assert normalizer.normalize("Key # then #.").normalized_text == "Key pound then pound."

    # Exponents: 2^5
    assert normalizer.normalize("The result is 2^5.").normalized_text == "The result is two to the fifth power."



def test_tilde_symbol(normalizer: TextNormalizer):
    cases = [
        ("It takes ~5 minutes.", "It takes approximately five minutes."),
        ("Costs ~$10 total.", "Costs approximately ten dollars total."),
        ("About ~100 people came.", "About approximately one hundred people came."),
        ("Approximately ~3.5 miles.", "Approximately approximately three point five miles."),
        ("Symbol ~ is a tilde.", "Symbol tilde is a tilde."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_slash_between_words(normalizer: TextNormalizer):
    cases = [
        ("Choose either/or option.", "Choose either or option."),
        ("Check input/output streams.", "Check input slash output streams."),
        ("Simple yes/no question.", "Simple yes or no question."),
        ("Answer true/false here.", "Answer true slash false here."),
        ("Option A / B available.", "Option A slash B available."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)

    # Test word_slash_style="slash"
    slash_norm = TextNormalizer(NormalizerConfig.for_locale("en-US", word_slash_style="slash"))
    assert slash_norm.normalize("Choose either/or option.").normalized_text == "Choose either slash or option."


def test_underscore_and_typography(normalizer: TextNormalizer):
    cases = [
        ("Press _ key.", "Press underscore key."),
        ("Acme Corp. © 2024.", "Acme Corporation copyright twenty twenty-four."),
        ("Python® language.", "Python registered language."),
        ("CoolTech™ brand.", "CoolTech trademark brand."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_24x7_and_dimensions(normalizer: TextNormalizer):
    assert normalizer.normalize("Open 24x7.").normalized_text == "Open twenty-four seven."
    assert normalizer.normalize("Available 24X7 daily.").normalized_text == "Available twenty-four seven daily."


def test_telephony_keypad_symbols(normalizer: TextNormalizer):
    norm_gb = TextNormalizer(NormalizerConfig.for_locale("en-GB"))

    # *67 star code
    assert normalizer.normalize("Dial *67 to block caller ID.").normalized_text == "Dial star six seven to block caller I D."

    # Telephony commands: press/dial/enter/hit/key * or #
    assert normalizer.normalize("Press * for operator.").normalized_text == "Press star for operator."
    assert normalizer.normalize("Press # to save.").normalized_text == "Press pound to save."
    assert norm_gb.normalize("Dial # to confirm.").normalized_text == "Dial hash to confirm."

    # Telephony sequences: * then #, * or #, # or *, # then *
    assert normalizer.normalize("Press * then # on phone.").normalized_text == "Press star then pound on phone."
    assert normalizer.normalize("Dial # or * to cancel.").normalized_text == "Dial pound or star to cancel."
    assert normalizer.normalize("Hit * or * again.").normalized_text == "Hit star or star again."
    assert normalizer.normalize("Key # then #.").normalized_text == "Key pound then pound."

    # Exponents: 2^5
    assert normalizer.normalize("The result is 2^5.").normalized_text == "The result is two to the fifth power."

