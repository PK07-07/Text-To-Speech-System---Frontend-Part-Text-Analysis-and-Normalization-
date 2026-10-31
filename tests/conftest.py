"""Pytest fixtures and invariant assertion helpers for text_frontend tests."""

from __future__ import annotations

import re
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from text_frontend.validation import NormalizationResult


@pytest.fixture
def default_normalizer() -> TextNormalizer:
    """Provides a TextNormalizer with default en-US conversational settings."""
    return TextNormalizer(config=NormalizerConfig.for_locale("en-US"))


@pytest.fixture
def gb_normalizer() -> TextNormalizer:
    """Provides a TextNormalizer configured for en-GB."""
    return TextNormalizer(config=NormalizerConfig.for_locale("en-GB"))


def assert_transformation_invariants(raw_input: str | bytes, result: NormalizationResult) -> None:
    """Verifies strict mathematical invariants on all emitted transformations.

    1. Slicing invariant:
       original_text[orig_start:orig_end] == t.original_text
       normalized_text[out_start:out_end] == t.normalized_text
    2. Monotonic non-overlapping invariant:
       T_i.original_span[1] <= T_{i+1}.original_span[0]
       T_i.output_span[1] <= T_{i+1}.output_span[0]
    """
    orig_text = result.original_text
    norm_text = result.normalized_text

    prev_orig_end = 0
    prev_out_end = 0

    for i, t in enumerate(result.transformations):
        orig_start, orig_end = t.original_span
        out_start, out_end = t.output_span

        # Slicing invariant
        assert orig_text[orig_start:orig_end] == t.original_text, (
            f"Original span mismatch at idx {i}: expected '{t.original_text}', "
            f"got slice '{orig_text[orig_start:orig_end]}'"
        )
        assert norm_text[out_start:out_end] == t.normalized_text, (
            f"Output span mismatch at idx {i}: expected '{t.normalized_text}', "
            f"got slice '{norm_text[out_start:out_end]}'"
        )

        # Monotonic non-overlapping invariant
        assert orig_start >= prev_orig_end, (
            f"Overlapping original spans at idx {i}: current start {orig_start} < previous end {prev_orig_end}"
        )
        assert out_start >= prev_out_end, (
            f"Overlapping output spans at idx {i}: current start {out_start} < previous end {prev_out_end}"
        )

        prev_orig_end = orig_end
        prev_out_end = out_end


def normalize_oracle_words(text: str) -> str:
    """Normalizes num2words output to align with text_frontend style for fuzz testing.

    Removes commas, converts 'minus' to 'negative', and strips filler 'and'.
    """
    cleaned = text.replace(",", "").replace("-", " ")
    cleaned = re.sub(r"\bminus\b", "negative", cleaned)
    cleaned = re.sub(r"\band\b", "", cleaned)
    return " ".join(cleaned.split())
