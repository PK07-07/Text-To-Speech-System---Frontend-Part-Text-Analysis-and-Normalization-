"""Tests for strict span alignment, monotonic offset mapping, and corpus verification."""

from __future__ import annotations

import json
from pathlib import Path
import unicodedata
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants

DATA_DIR = Path(__file__).parent / "data"


def test_complex_sentence_alignment(default_normalizer: TextNormalizer):
    raw = "On July 4, 1984, the company paid $12.50 to the 1st employee, representing 25% of the $50 budget."
    res = default_normalizer.normalize(raw)
    assert res.status == "success"
    assert_transformation_invariants(raw, res)

    # Verify specific transformations
    texts = [t.original_text for t in res.transformations]
    assert "July 4, 1984" in texts
    assert "$12.50" in texts
    assert "1st" in texts
    assert "25%" in texts
    assert "$50" in texts


def test_decomposed_nfd_unicode_alignment(default_normalizer: TextNormalizer):
    # Decomposed NFD: "e" + combining acute "\u0301" = "é"
    nfd_char = unicodedata.normalize("NFD", "é")
    raw = f"Caf{nfd_char} bill: $15.50 for 2 coffees."
    res = default_normalizer.normalize(raw)
    assert res.status == "success"
    assert "fifteen dollars and fifty cents" in res.normalized_text
    assert "two coffees" in res.normalized_text
    assert_transformation_invariants(raw, res)


def test_phase1_corpus_verification():
    corpus_file = DATA_DIR / "phase1_corpus.json"
    with open(corpus_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        raw = case["input"]
        expected = case["expected"]
        locale = case.get("locale", "en-US")
        norm = TextNormalizer(NormalizerConfig.for_locale(locale))
        res = norm.normalize(raw)
        assert res.normalized_text == expected, (
            f"Corpus failure for input '{raw}': expected '{expected}', got '{res.normalized_text}'"
        )
        assert res.status == case["status"]
        assert_transformation_invariants(raw, res)


def test_phase2_corpus_verification():
    corpus_file = DATA_DIR / "phase2_corpus.json"
    with open(corpus_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        raw = case["input"]
        expected = case["expected"]
        locale = case.get("locale", "en-US")
        norm = TextNormalizer(NormalizerConfig.for_locale(locale))
        res = norm.normalize(raw)
        assert res.normalized_text == expected, (
            f"Phase 2 corpus failure for input '{raw}': expected '{expected}', got '{res.normalized_text}'"
        )
        assert res.status == case["status"]
        assert_transformation_invariants(raw, res)


def test_phase3_corpus_verification():
    corpus_file = DATA_DIR / "phase3_corpus.json"
    with open(corpus_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        raw = case["input"]
        expected = case["expected"]
        locale = case.get("locale", "en-US")
        norm = TextNormalizer(NormalizerConfig.for_locale(locale))
        res = norm.normalize(raw)
        assert res.normalized_text == expected, (
            f"Phase 3 corpus failure for input '{raw}': expected '{expected}', got '{res.normalized_text}'"
        )
        assert res.status == case["status"]
        assert_transformation_invariants(raw, res)


def test_gold_corpus_verification():
    """Verifies gold corpus entries that have been explicitly confirmed by user (verified: true)."""
    gold_file = DATA_DIR / "gold_inputs.json"
    with open(gold_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    verified_cases = [c for c in cases if c.get("verified") is True]
    for case in verified_cases:
        raw = case["input"]
        expected = case["proposed_output"]
        locale = case.get("locale", "en-US")
        norm = TextNormalizer(NormalizerConfig.for_locale(locale))
        res = norm.normalize(raw)
        assert res.normalized_text == expected, (
            f"Gold test {case['id']} failure for input '{raw}': "
            f"expected '{expected}', got '{res.normalized_text}'"
        )
        assert_transformation_invariants(raw, res)
