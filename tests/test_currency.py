"""Unit tests for currency rules: USD, GBP, EUR, INR, JPY, ISO codes, magnitudes, and accounting formats."""

from __future__ import annotations

import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants


def test_usd_basic(default_normalizer: TextNormalizer):
    cases = [
        ("$25", "twenty-five dollars"),
        ("$1", "one dollar"),
        ("$25.50", "twenty-five dollars and fifty cents"),
        ("$1.01", "one dollar and one cent"),
        ("$0.75", "seventy-five cents"),
        ("$0.05", "five cents"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_gbp(gb_normalizer: TextNormalizer):
    cases = [
        ("£1", "one pound"),
        ("£10", "ten pounds"),
        ("£1.50", "one pound and fifty pence"),
        ("£0.25", "twenty-five pence"),
    ]
    for inp, exp in cases:
        res = gb_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_eur(default_normalizer: TextNormalizer):
    cases = [
        ("€1", "one euro"),
        ("€2", "two euros"),
        ("€2.75", "two euros and seventy-five cents"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_inr_and_indian_numbering():
    norm = TextNormalizer(NormalizerConfig.for_locale("en-IN"))
    cases = [
        ("₹500", "five hundred rupees"),
        ("₹1,00,000", "one lakh rupees"),
        ("₹1,00,00,000", "one crore rupees"),
        ("₹25,50,000", "twenty-five lakh fifty thousand rupees"),
    ]
    for inp, exp in cases:
        res = norm.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_jpy(default_normalizer: TextNormalizer):
    cases = [
        ("¥1", "one yen"),
        ("¥1000", "one thousand yen"),
        ("¥50000", "fifty thousand yen"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_iso_codes(default_normalizer: TextNormalizer):
    cases = [
        ("USD 50", "fifty dollars"),
        ("50 USD", "fifty dollars"),
        ("EUR 100", "one hundred euros"),
        ("100 EUR", "one hundred euros"),
        ("GBP 20", "twenty pounds"),
        ("CAD 75", "seventy-five Canadian dollars"),
        ("AUD 10", "ten Australian dollars"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_currency_financial_magnitudes(default_normalizer: TextNormalizer):
    cases = [
        ("$5K", "five thousand dollars"),
        ("$10M", "ten million dollars"),
        ("£2.5B", "two point five billion pounds"),
        ("€100M", "one hundred million euros"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_negative_and_parenthesized_currencies(default_normalizer: TextNormalizer):
    cases = [
        ("-$50", "negative fifty dollars"),
        ("($500)", "negative five hundred dollars"),
        ("($50.25)", "negative fifty dollars and twenty-five cents"),
    ]
    for inp, exp in cases:
        res = default_normalizer.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
        assert_transformation_invariants(inp, res)


def test_indian_rs_currency():
    norm_in = TextNormalizer(NormalizerConfig.for_locale("en-IN"))
    cases = [
        ("Pay Rs. 1,50,000 by 5th March.", "Pay one lakh fifty thousand rupees by March fifth."),
        ("Cost is Rs 500/-.", "Cost is five hundred rupees."),
        ("Balance is -Rs. 500.", "Balance is negative five hundred rupees."),
        ("Cost is ₹500/-.", "Cost is five hundred rupees."),
    ]
    for inp, exp in cases:
        res = norm_in.normalize(inp)
        assert res.normalized_text == exp
        assert res.status == "success"
