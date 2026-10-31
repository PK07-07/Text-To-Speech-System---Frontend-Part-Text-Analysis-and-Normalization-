"""Tests for phone numbers, extensions, toll-free codes, and technical identifiers."""

from __future__ import annotations

import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


@pytest.fixture
def normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


def test_nanp_phone_numbers(normalizer: TextNormalizer):
    res1 = normalizer.normalize("Call (555) 123-4567 today.")
    assert "five five five, one two three, four five six seven" in res1.normalized_text

    res2 = normalizer.normalize("Reach us at 555-123-4567.")
    assert "five five five, one two three, four five six seven" in res2.normalized_text

    res3 = normalizer.normalize("Phone: 555.123.4567.")
    assert "five five five, one two three, four five six seven" in res3.normalized_text

    res4 = normalizer.normalize("Support: +1-555-123-4567.")
    assert "one, five five five, one two three, four five six seven" in res4.normalized_text


def test_indian_mobile_numbers(normalizer: TextNormalizer):
    res = normalizer.normalize("Contact: +91 98765 43210.")
    assert "plus nine one, nine eight seven six five, four three two one oh" in res.normalized_text

    res2 = normalizer.normalize("Contact: +91-98765-43210.")
    assert "plus nine one, nine eight seven six five, four three two one oh" in res2.normalized_text


def test_toll_free_modes():
    # Default: digit-by-digit with spoken_leading_zeros="oh"
    norm_oh = TextNormalizer(NormalizerConfig.for_locale("en-US", read_toll_free_as_words=False, spoken_leading_zeros="oh"))
    res_oh = norm_oh.normalize("1-800-555-0199")
    assert "eight oh oh" in res_oh.normalized_text

    # Digit-by-digit with spoken_leading_zeros="zero"
    norm_zero = TextNormalizer(NormalizerConfig.for_locale("en-US", read_toll_free_as_words=False, spoken_leading_zeros="zero"))
    res_zero = norm_zero.normalize("1-800-555-0199")
    assert "eight zero zero" in res_zero.normalized_text

    # Toll-free as words
    norm_words = TextNormalizer(NormalizerConfig.for_locale("en-US", read_toll_free_as_words=True))
    res_words = norm_words.normalize("1-800-555-0199")
    assert "eight hundred" in res_words.normalized_text


def test_phone_extensions(normalizer: TextNormalizer):
    res1 = normalizer.normalize("Call 555-123-4567 ext. 123.")
    assert "five five five, one two three, four five six seven, extension one two three" in res1.normalized_text

    res2 = normalizer.normalize("Call 555-123-4567 x456.")
    assert "five five five, one two three, four five six seven, extension four five six" in res2.normalized_text


def test_spoken_leading_zeros_phone():
    cfg_zero = NormalizerConfig.for_locale("en-US", spoken_leading_zeros="zero")
    norm_zero = TextNormalizer(cfg_zero)
    res = norm_zero.normalize("Call 555-0199.")
    assert "zero one nine nine" in res.normalized_text

    cfg_oh = NormalizerConfig.for_locale("en-US", spoken_leading_zeros="oh")
    norm_oh = TextNormalizer(cfg_oh)
    res_oh = norm_oh.normalize("Call 555-0199.")
    assert "oh one nine nine" in res_oh.normalized_text


def test_bare_7digit_local_numbers(normalizer: TextNormalizer):
    # Hyphen separator expands
    res_hyphen = normalizer.normalize("Call 555-0199.")
    assert "five five five, oh one nine nine" in res_hyphen.normalized_text

    # Dot separator expands
    res_dot = normalizer.normalize("Call 555.0199.")
    assert "five five five, oh one nine nine" in res_dot.normalized_text

    # Space with cue expands
    res_cue = normalizer.normalize("Please call 555 0199.")
    assert "five five five, oh one nine nine" in res_cue.normalized_text

    # Stray space without cue does NOT expand as phone number
    res_stray = normalizer.normalize("Items 555 0199 in warehouse.")
    assert "five five five, oh one nine nine" not in res_stray.normalized_text


def test_phone_outranks_range(normalizer: TextNormalizer):
    # 555-0199 MUST NOT be verbalized as a range
    res = normalizer.normalize("Dial 555-0199.")
    assert "five hundred fifty-five to" not in res.normalized_text
    assert "five five five, oh one nine nine" in res.normalized_text


def test_product_codes_and_technical_ids(normalizer: TextNormalizer):
    # Generic product codes
    assert normalizer.normalize("Model RX-78 online.").normalized_text == "Model R X seventy-eight online."
    assert normalizer.normalize("Use WD-40 spray.").normalized_text == "Use W D forty spray."

    # Lexicon exact matches
    assert normalizer.normalize("The COVID-19 pandemic.").normalized_text == "The covid nineteen pandemic."
    assert normalizer.normalize("Fighter jet F-16.").normalized_text == "Fighter jet F sixteen."


def test_telephony_and_cue_digits_hardening(normalizer: TextNormalizer):
    norm_in = TextNormalizer(NormalizerConfig.for_locale("en-IN"))

    # Hex literals
    assert normalizer.normalize("Value is 0x1F.").normalized_text == "Value is zero x one F."
    assert normalizer.normalize("Memory at 0xFF00.").normalized_text == "Memory at zero x F F zero zero."

    # Flight codes (3-digit and 4-digit)
    assert normalizer.normalize("Flight AI 202 departs.").normalized_text == "Flight A I two oh two departs."
    assert normalizer.normalize("Flight UA 1204 departs.").normalized_text == "Flight U A twelve oh four departs."
    assert normalizer.normalize("Flight DL 54 departs.").normalized_text == "Flight D L fifty-four departs."

    # Cue-word digits and codes
    assert normalizer.normalize("Your OTP is 482913.").normalized_text == "Your O T P is four eight two nine one three."
    assert normalizer.normalize("Your PIN is 1234.").normalized_text == "Your PIN is one two three four."
    assert normalizer.normalize("Account number 12345678.").normalized_text == "Account number one two three four five six seven eight."
    assert normalizer.normalize("Order number 100245.").normalized_text == "Order number one oh oh two four five."
    assert normalizer.normalize("Confirmation code 7H4K9Q.").normalized_text == "Confirmation code seven H four K nine Q."
    assert normalizer.normalize("Card ending in 4417.").normalized_text == "Card ending in four four one seven."
    assert normalizer.normalize("ZIP 90210.").normalized_text == "ZIP nine oh two one oh."
    assert normalizer.normalize("PNR ABC123.").normalized_text == "P N R A B C one two three."
    assert norm_in.normalize("Pincode 500001.").normalized_text == "Pincode five zero zero zero zero one."

    # Alphanumeric designations
    assert normalizer.normalize("Apt 4B").normalized_text == "Apt four B"
    assert normalizer.normalize("Unit 12A").normalized_text == "Unit twelve A"
    assert normalizer.normalize("Seat 14C").normalized_text == "Seat fourteen C"
    assert normalizer.normalize("Row 5A").normalized_text == "Row five A"
    assert normalizer.normalize("Gate B7").normalized_text == "Gate B seven"
    assert normalizer.normalize("Terminal 2A").normalized_text == "Terminal two A"

    # Indian 5-5 grouping
    assert norm_in.normalize("Call 98765 43210.").normalized_text == "Call nine eight seven six five, four three two one zero."
    assert normalizer.normalize("Call mobile 98765 43210.").normalized_text == "Call mobile nine eight seven six five, four three two one zero."

    # Additional flight numbers and airport codes
    assert normalizer.normalize("Flight UA 300 departs.").normalized_text == "Flight U A three hundred departs."
    assert normalizer.normalize("Flight UA 325 departs.").normalized_text == "Flight U A three twenty-five departs."
    assert normalizer.normalize("Flight UA 1200 departs.").normalized_text == "Flight U A one thousand two hundred departs."
    assert normalizer.normalize("Flight UA 1234 departs.").normalized_text == "Flight U A twelve thirty-four departs."
    assert normalizer.normalize("Flight UA-402 from JFK to LAX.").normalized_text == "Flight U A four oh two from J F K to L A X."
    assert normalizer.normalize("My customer ID is CUST-88392.").normalized_text == "My customer I D is C U S T dash eight eight three nine two."


def test_zero_word_rule_en_us_and_en_in(normalizer: TextNormalizer):
    norm_in = TextNormalizer(NormalizerConfig.for_locale("en-IN"))

    # 1. Phones: digit-only -> oh in US, zero in IN
    assert normalizer.normalize("Call 555-0199 today.").normalized_text == "Call five five five, oh one nine nine today."
    assert norm_in.normalize("Call 555-0199 today.").normalized_text == "Call five five five, zero one nine nine today."

    # 2. PINs: digit-only -> oh in US, zero in IN
    assert normalizer.normalize("Your PIN is 4092.").normalized_text == "Your PIN is four oh nine two."
    assert norm_in.normalize("Your PIN is 4092.").normalized_text == "Your PIN is four zero nine two."

    # 3. ZIPs: digit-only -> oh in US, zero in IN
    assert normalizer.normalize("ZIP 90210.").normalized_text == "ZIP nine oh two one oh."
    assert norm_in.normalize("ZIP 90210.").normalized_text == "ZIP nine zero two one zero."

    # 4. Account numbers: digit-only -> oh in US, zero in IN
    assert normalizer.normalize("Account number 40921.").normalized_text == "Account number four oh nine two one."
    assert norm_in.normalize("Account number 40921.").normalized_text == "Account number four zero nine two one."

    # 5. Passcodes with #: digit-only -> oh in US, zero in IN
    assert normalizer.normalize("Enter passcode 839201# now.").normalized_text == "Enter passcode eight three nine two oh one pound now."
    assert norm_in.normalize("Enter passcode 839201# now.").normalized_text == "Enter passcode eight three nine two zero one hash now."

    # 6. Order numbers: digit-only -> oh in US, zero in IN
    assert normalizer.normalize("Order #4092 confirmed.").normalized_text == "Order number four oh nine two confirmed."
    assert norm_in.normalize("Order #4092 confirmed.").normalized_text == "Order number four zero nine two confirmed."

    # 7. Mixed codes: mixed letters and digits -> ALWAYS 'zero' in both locales
    assert normalizer.normalize("Order MED-90218-A shipped.").normalized_text == "Order M E D dash nine zero two one eight dash A shipped."
    assert norm_in.normalize("Order MED-90218-A shipped.").normalized_text == "Order M E D dash nine zero two one eight dash A shipped."
    assert normalizer.normalize("Tracking 1Z00192A.").normalized_text == "Tracking one Z zero zero one nine two A."
    assert norm_in.normalize("Tracking 1Z00192A.").normalized_text == "Tracking one Z zero zero one nine two A."


def test_boundary_gluing_numbers_and_words(normalizer: TextNormalizer):
    # Attached number to word reads as cardinal unless code cue applies
    assert normalizer.normalize("Val 100items.").normalized_text == "Val one hundred items."
    assert normalizer.normalize("There are 3apples.").normalized_text == "There are three apples."
    assert normalizer.normalize("Walked 50miles today.").normalized_text == "Walked fifty miles today."
    assert normalizer.normalize("Read 25pages.").normalized_text == "Read twenty-five pages."
    assert normalizer.normalize("order 100items").normalized_text == "order one zero zero I T E M S"

    # Flight codes and addresses edge coverage
    assert normalizer.normalize("Flight AA 100 departs.").normalized_text == "Flight A A one hundred departs."
    assert normalizer.normalize("Flight AA 1000 departs.").normalized_text == "Flight A A one thousand departs."
    assert normalizer.normalize("I saw AA 101 yesterday.").normalized_text == "I saw AA one hundred one yesterday."
    assert normalizer.normalize("Live at 1200 Main St.").normalized_text == "Live at twelve hundred Main Street."
    assert normalizer.normalize("Live at 12000 Main St.").normalized_text == "Live at one twenty zero Main Street."


