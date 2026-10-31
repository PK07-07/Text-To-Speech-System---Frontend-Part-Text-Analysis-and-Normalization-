"""Security, privacy, and scaling-ratio tests for catastrophic backtracking prevention."""

from __future__ import annotations

import time
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants


def test_scaling_ratio_no_catastrophic_backtracking(default_normalizer: TextNormalizer):
    """Verifies that processing time scales linearly with input size."""
    # Adversarial string pattern with numbers, delimiters, and potential backtracking triggers
    base_chunk = "Item #100 with $25.50 and 15% discount at https://example.com/test. "
    
    small_text = base_chunk * 10    # ~680 chars
    large_text = base_chunk * 50    # ~3400 chars (5x larger)

    # Warmup
    default_normalizer.normalize(base_chunk)

    t0 = time.perf_counter()
    res_small = default_normalizer.normalize(small_text)
    t_small = time.perf_counter() - t0

    t0 = time.perf_counter()
    res_large = default_normalizer.normalize(large_text)
    t_large = time.perf_counter() - t0

    assert res_small.status == "success"
    assert res_large.status == "success"
    assert_transformation_invariants(small_text, res_small)
    assert_transformation_invariants(large_text, res_large)

    # If catastrophic backtracking were present, t_large would be 100x+ slower.
    # Linear or near-linear scaling means t_large / max(t_small, 0.001) should comfortably be < 20x.
    if t_small > 0.0005:
        scaling_ratio = t_large / t_small
        assert scaling_ratio < 20.0, f"Scaling ratio too high ({scaling_ratio:.1f}x), possible backtracking"


def test_pathological_repeating_delimiters(default_normalizer: TextNormalizer):
    """Adversarial input with repeating punctuation and decimal dots."""
    pathological = "Test " + "..." * 500 + " 42 " + ".." * 200
    t0 = time.perf_counter()
    res = default_normalizer.normalize(pathological)
    elapsed = time.perf_counter() - t0

    # Must finish in < 250ms
    assert elapsed < 0.25, f"Pathological input took too long ({elapsed:.3f}s)"


def test_privacy_no_raw_text_in_warnings(default_normalizer: TextNormalizer):
    """Ensures that diagnostic warning messages do NOT leak raw text substrings."""
    sensitive_token = "SecretSSN9999"
    raw = f"Error with {sensitive_token} and malformed 12..34"
    res = default_normalizer.normalize(raw)

    for w in res.warnings:
        assert sensitive_token not in w.message, f"PII leakage in warning message: {w.message}"
        assert sensitive_token not in w.code
