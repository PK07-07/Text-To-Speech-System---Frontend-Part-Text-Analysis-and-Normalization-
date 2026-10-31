"""Tests for unit expansion, pluralization, disambiguation, and unit ranges."""

from __future__ import annotations

import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


@pytest.fixture
def normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


def test_unit_categories_and_expansion(normalizer: TextNormalizer):
    # Length
    assert normalizer.normalize("10mm").normalized_text == "ten millimeters"
    assert normalizer.normalize("5 km").normalized_text == "five kilometers"
    assert normalizer.normalize("3 ft").normalized_text == "three feet"
    assert normalizer.normalize("2 yd").normalized_text == "two yards"
    assert normalizer.normalize("10 mi").normalized_text == "ten miles"

    # Area
    assert normalizer.normalize("15 m²").normalized_text == "fifteen square meters"
    assert normalizer.normalize("50 sq ft").normalized_text == "fifty square feet"
    assert normalizer.normalize("2 ha").normalized_text == "two hectares"
    assert normalizer.normalize("5 acres").normalized_text == "five acres"

    # Volume
    assert normalizer.normalize("500 ml").normalized_text == "five hundred milliliters"
    assert normalizer.normalize("2 gal").normalized_text == "two gallons"
    assert normalizer.normalize("1 pt").normalized_text == "one pint"
    assert normalizer.normalize("12 fl oz").normalized_text == "twelve fluid ounces"

    # Mass
    assert normalizer.normalize("100 mg").normalized_text == "one hundred milligrams"
    assert normalizer.normalize("5 kg").normalized_text == "five kilograms"
    assert normalizer.normalize("16 oz").normalized_text == "sixteen ounces"
    assert normalizer.normalize("10 lbs").normalized_text == "ten pounds"
    assert normalizer.normalize("2 tons").normalized_text == "two tons"

    # Speed
    assert normalizer.normalize("60 km/h").normalized_text == "sixty kilometers per hour"
    assert normalizer.normalize("55 mph").normalized_text == "fifty-five miles per hour"
    assert normalizer.normalize("10 knots").normalized_text == "ten knots"

    # Temperature
    assert normalizer.normalize("25°C").normalized_text == "twenty-five degrees Celsius"
    assert normalizer.normalize("72°F").normalized_text == "seventy-two degrees Fahrenheit"

    # Digital
    assert normalizer.normalize("16 GB").normalized_text == "sixteen gigabytes"
    assert normalizer.normalize("512 MB").normalized_text == "five hundred twelve megabytes"
    assert normalizer.normalize("100 Mbps").normalized_text == "one hundred megabits per second"

    # Electrical & Power
    assert normalizer.normalize("120 V").normalized_text == "one hundred twenty volts"
    assert normalizer.normalize("60 W").normalized_text == "sixty watts"
    assert normalizer.normalize("5 kW").normalized_text == "five kilowatts"
    assert normalizer.normalize("100 kWh").normalized_text == "one hundred kilowatt-hours"
    assert normalizer.normalize("50 Hz").normalized_text == "fifty hertz"
    assert normalizer.normalize("10 Ω").normalized_text == "ten ohms"
    assert normalizer.normalize("25 N·m").normalized_text == "twenty-five newton-meters"


def test_unit_plurals_singular_vs_plural(normalizer: TextNormalizer):
    # Exactly 1 is singular
    assert normalizer.normalize("1 km").normalized_text == "one kilometer"
    assert normalizer.normalize("1 lb").normalized_text == "one pound"
    assert normalizer.normalize("1 ft").normalized_text == "one foot"
    assert normalizer.normalize("1 acre").normalized_text == "one acre"

    # 0 is plural
    assert normalizer.normalize("0 km").normalized_text == "zero kilometers"

    # 1.0 and 1.5 are plural
    assert normalizer.normalize("1.0 km").normalized_text == "one point zero kilometers"
    assert normalizer.normalize("1.5 km").normalized_text == "one point five kilometers"
    assert normalizer.normalize("0.5 km").normalized_text == "zero point five kilometers"

    # Numerator only is plural for rates
    assert normalizer.normalize("1 km/h").normalized_text == "one kilometer per hour"
    assert normalizer.normalize("2 km/h").normalized_text == "two kilometers per hour"


def test_ambiguous_units_and_attached_rule(normalizer: TextNormalizer):
    # "10 in the box" must NEVER be read as inches
    res_in_box = normalizer.normalize("There are 10 in the box.")
    assert res_in_box.normalized_text == "There are ten in the box."

    # "10in" or "10 in." is read as inches
    assert normalizer.normalize("Cut 10in of wire.").normalized_text == "Cut ten inches of wire."
    assert normalizer.normalize("Cut 10 in. of wire.").normalized_text == "Cut ten inches of wire."

    # "5 m away" vs "5m"
    res_m_away = normalizer.normalize("The car was 5 m away.")
    # Space separated ambiguous "m" without attached form is not expanded
    assert res_m_away.normalized_text == "The car was five m away."

    res_5m = normalizer.normalize("The rope was 5m long.")
    assert res_5m.normalized_text == "The rope was five meters long."

    # "64B" vs "64 B"
    assert normalizer.normalize("Memory: 64B.").normalized_text == "Memory: sixty-four bytes."
    assert normalizer.normalize("Rank 64 B grade.").normalized_text == "Rank sixty-four B grade."


def test_kelvin_context(normalizer: TextNormalizer):
    # With temperature context
    res_temp = normalizer.normalize("Water boils at 373 K temperature.")
    assert "three hundred seventy-three kelvins" in res_temp.normalized_text

    # Without temperature context
    res_no_temp = normalizer.normalize("Select option 300 K from the list.")
    assert "three hundred K" in res_no_temp.normalized_text


def test_electrical_context_for_amperes(normalizer: TextNormalizer):
    # Attached form 5A always expands
    assert normalizer.normalize("The circuit draw is 5A.").normalized_text == "The circuit draw is five amperes."

    # Space separated 5 A with electrical context
    res_ctx = normalizer.normalize("The fuse rating is 5 A.")
    assert "five amperes" in res_ctx.normalized_text

    # Space separated 5 A without electrical context
    res_no_ctx = normalizer.normalize("He scored 5 A grades.")
    assert "five A" in res_no_ctx.normalized_text


def test_unit_ranges(normalizer: TextNormalizer):
    assert normalizer.normalize("Travel 10-20 km daily.").normalized_text == "Travel ten to twenty kilometers daily."
    assert normalizer.normalize("Hike 5-10 km.").normalized_text == "Hike five to ten kilometers."
    assert normalizer.normalize("Dosage: 1-2 mg.").normalized_text == "Dosage: one to two milligrams."
