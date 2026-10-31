"""Tests for fractions, mixed fractions, ratios, number ranges, currency ranges, and disambiguation."""

from __future__ import annotations

import random
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


@pytest.fixture
def normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


def test_standard_fractions(normalizer: TextNormalizer):
    assert normalizer.normalize("Use 1/2 cup of flour.").normalized_text == "Use one half cup of flour."
    assert normalizer.normalize("Add 3/4 spoon of salt.").normalized_text == "Add three fourths spoon of salt."
    assert normalizer.normalize("Change is -1/2 point.").normalized_text == "Change is negative one half point."
    assert normalizer.normalize("A 3/16 inch socket.").normalized_text == "A three sixteenths inch socket."


def test_mixed_fractions(normalizer: TextNormalizer):
    assert normalizer.normalize("Run 2 1/3 miles.").normalized_text == "Run two and one third miles."
    assert normalizer.normalize("Loss of -2 1/3 points.").normalized_text == "Loss of negative two and one third points."
    assert normalizer.normalize("Cook for 1 ½ hours.").normalized_text == "Cook for one and one half hours."


def test_unicode_fractions(normalizer: TextNormalizer):
    assert normalizer.normalize("Pour ½ cup milk.").normalized_text == "Pour one half cup milk."
    assert normalizer.normalize("Add ¾ cup sugar.").normalized_text == "Add three fourths cup sugar."
    assert normalizer.normalize("Cut ⅓ off.").normalized_text == "Cut one third off."
    assert normalizer.normalize("Score is ⅔.").normalized_text == "Score is two thirds."


def test_ratios(normalizer: TextNormalizer):
    assert normalizer.normalize("Aspect ratio is 16:9.").normalized_text == "Aspect ratio is sixteen to nine."
    assert normalizer.normalize("Mix ratio 3:1.").normalized_text == "Mix ratio three to one."
    assert normalizer.normalize("Odds of 5:2.").normalized_text == "Odds of five to two."


def test_number_ranges(normalizer: TextNormalizer):
    assert normalizer.normalize("Ages 10-20 welcome.").normalized_text == "Ages ten to twenty welcome."
    assert normalizer.normalize("Years 1995-1999.").normalized_text == "Years nineteen ninety-five to nineteen ninety-nine."
    assert normalizer.normalize("Page 5–10.").normalized_text == "Page five to ten."


def test_currency_ranges(normalizer: TextNormalizer):
    # Same symbol merges
    assert normalizer.normalize("Costs $5-$10 per item.").normalized_text == "Costs five to ten dollars per item."
    assert normalizer.normalize("Price: £5-£10.").normalized_text == "Price: five to ten pounds."
    assert normalizer.normalize("Cost: €20 to €30.").normalized_text == "Cost: twenty to thirty euros."
    assert normalizer.normalize("Earned $5K-$10K.").normalized_text == "Earned five thousand to ten thousand dollars."

    # Decimal currency range
    res_dec = normalizer.normalize("Price: $5.50-$10.50.")
    assert "five dollars and fifty cents to ten dollars and fifty cents" in res_dec.normalized_text

    # Different currencies stay separate
    res_diff = normalizer.normalize("Exchange: $5-EUR10.")
    assert "five dollars" in res_diff.normalized_text
    assert "ten euros" in res_diff.normalized_text
    assert "to" not in res_diff.normalized_text


def test_disambiguation_overlaps(normalizer: TextNormalizer):
    # "3/4" (fraction) vs "3/4/2023" (date)
    res_date = normalizer.normalize("Event on 3/4/2023.")
    assert "March fourth, twenty twenty-three" in res_date.normalized_text
    assert "three fourths" not in res_date.normalized_text

    res_frac = normalizer.normalize("Take 3/4 dose.")
    assert "three fourths" in res_frac.normalized_text

    # "555-0199" (phone) vs range
    res_phone = normalizer.normalize("Call 555-0199 now.")
    assert "five five five, oh one nine nine" in res_phone.normalized_text
    assert "to" not in res_phone.normalized_text

    # "April 3-5" (date range) vs range
    res_drange = normalizer.normalize("Event on April 3-5.")
    assert "April third to fifth" in res_drange.normalized_text


def test_order_independent_overlap_resolution_phase2():
    cfg = NormalizerConfig.for_locale("en-US")
    norm = TextNormalizer(cfg)

    sentences = [
        "Special price $5-$10 or call 555-0199 on April 3-5 for 10-20 km trip.",
        "Take 2 1/3 doses of 3/4 solution at 14:30 EST.",
        "Model RX-78 costs $10M and weighs 50 kg.",
    ]

    for sent in sentences:
        res1 = norm.normalize(sent)
        # Normalizing repeatedly gives identical result
        for _ in range(5):
            res_repeat = norm.normalize(sent)
            assert res_repeat.normalized_text == res1.normalized_text
            assert res_repeat.transformations == res1.transformations
