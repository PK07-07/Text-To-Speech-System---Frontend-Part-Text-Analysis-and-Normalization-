"""Latency and throughput benchmark tests for text_frontend.

Measures sentence latency, paragraph latency, and throughput.
Asserts > 50,000 chars/s locally (or > 10,000 chars/s when CI environment variable is set).
"""

from __future__ import annotations

import os
import sys
import time
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


@pytest.fixture(scope="module")
def normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


def _measure(normalizer: TextNormalizer, text: str, iterations: int = 50) -> float:
    """Returns median time in seconds over N iterations."""
    # Warmup
    normalizer.normalize(text)
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        normalizer.normalize(text)
        times.append(time.perf_counter() - t0)
    times.sort()
    return times[len(times) // 2]


def test_sentence_latency(normalizer: TextNormalizer):
    """Typical sentence (< 200 chars) should normalize in < 25ms."""
    sentence = "The 1st item costs $10.50, the 2nd is $20, and the 3rd is 25% off in 2024."
    median_s = _measure(normalizer, sentence)
    print(f"\nMeasured sentence latency: {median_s * 1000:.2f} ms")
    assert median_s < 0.025, f"Sentence latency {median_s*1000:.1f}ms exceeds 25ms threshold"


def test_paragraph_latency(normalizer: TextNormalizer):
    """Paragraph (< 2000 chars) should normalize in < 200ms."""
    base = "The company earned $1,500,000 in revenue, a 15% increase over 2023. "
    paragraph = base * 25  # ~1700 chars
    median_s = _measure(normalizer, paragraph, iterations=20)
    print(f"\nMeasured paragraph latency: {median_s * 1000:.2f} ms")
    assert median_s < 0.200, f"Paragraph latency {median_s*1000:.1f}ms exceeds 200ms threshold"


def test_throughput(normalizer: TextNormalizer):
    """Should process > 50,000 chars/sec locally (> 10,000 chars/sec on CI)."""
    base = "Item #100 costs $25.50 and the 2nd batch has 1,000 units at 15% discount. "
    text = base * 30  # ~2250 chars
    # Warmup
    normalizer.normalize(text)
    t0 = time.perf_counter()
    for _ in range(30):
        normalizer.normalize(text)
    elapsed = time.perf_counter() - t0
    chars_per_sec = (len(text) * 30) / elapsed
    print(f"\nMeasured throughput: {chars_per_sec:,.0f} chars/s")

    is_traced = hasattr(sys, "gettrace") and sys.gettrace() is not None
    min_throughput = 10_000 if (os.environ.get("CI") or is_traced) else 50_000
    assert chars_per_sec > min_throughput, (
        f"Throughput {chars_per_sec:,.0f} chars/s below threshold {min_throughput:,.0f}"
    )
