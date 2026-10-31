"""Idempotence verification test suite for text_frontend.

Verifies that for test cases across all development phases:
    normalize(normalize(x).normalized_text) == normalize(x).normalized_text
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from text_frontend import NormalizerConfig, normalize


DATA_DIR = Path(__file__).parent / "data"


def _collect_all_idempotence_cases() -> list[tuple[str, str, NormalizerConfig]]:
    cases: list[tuple[str, str, NormalizerConfig]] = []

    # Phase 1 baseline inputs
    p1_inputs = [
        "I paid $12.50.",
        "(15% of users) and ($500 per month) and (2020)",
        "1984 pages, in 1984, Room 1984",
        "1900 1905 2005 2010",
        "see https://api.example.com/v2/item-3 now",
        "1\u2009000\u2009000 units",
        "call 555 0199",
        "5\u00a0apples",
        "e\u0301 costs $3",
        "👨‍👩‍👧 paid $5",
        "$5-$10",
        "12..34",
    ]
    for t in p1_inputs:
        cases.append(("phase1", t, NormalizerConfig.for_locale("en-US")))
    cases.append(("phase1", "₹1,00,000", NormalizerConfig.for_locale("en-IN")))
    cases.append(("phase1", "1,00,000", NormalizerConfig.for_locale("en-US")))

    # Load from phase2_corpus.json
    p2_file = DATA_DIR / "phase2_corpus.json"
    if p2_file.exists():
        with open(p2_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                loc = item.get("locale", "en-US")
                cases.append(("phase2", item["input"], NormalizerConfig.for_locale(loc)))

    # Load from phase3_corpus.json
    p3_file = DATA_DIR / "phase3_corpus.json"
    if p3_file.exists():
        with open(p3_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                loc = item.get("locale", "en-US")
                cases.append(("phase3", item["input"], NormalizerConfig.for_locale(loc)))

    # Load from phase4_corpus.json
    p4_file = DATA_DIR / "phase4_corpus.json"
    if p4_file.exists():
        with open(p4_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                cfg_d = item.get("config", {})
                cfg = NormalizerConfig(**cfg_d) if cfg_d else NormalizerConfig.for_locale(item.get("locale", "en-US"))
                cases.append(("phase4", item["input"], cfg))

    # Load from realistic_calls.json
    rc_file = DATA_DIR / "realistic_calls.json"
    if rc_file.exists():
        with open(rc_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                loc = item.get("locale", "en-US")
                cases.append(("realistic_calls", item["input"], NormalizerConfig.for_locale(loc)))

    return cases


ALL_IDEMPOTENCE_CASES = _collect_all_idempotence_cases()


@pytest.mark.parametrize("suite,raw,config", ALL_IDEMPOTENCE_CASES)
def test_normalization_idempotence(suite: str, raw: str, config: NormalizerConfig):
    """Verify normalize(normalize(x).normalized_text) == normalize(x).normalized_text."""
    res1 = normalize(raw, config=config)
    t1 = res1.normalized_text

    # Skip empty input where t1 is empty
    if not t1:
        return

    res2 = normalize(t1, config=config)
    t2 = res2.normalized_text

    assert t2 == t1, (
        f"Idempotence violation in [{suite}] for raw={raw!r}:\n"
        f"  1st pass: {t1!r}\n"
        f"  2nd pass: {t2!r}"
    )
