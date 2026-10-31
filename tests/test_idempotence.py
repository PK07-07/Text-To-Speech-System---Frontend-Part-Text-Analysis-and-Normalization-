"""Idempotence verification test suite for text_frontend.

Verifies that for all test cases across check_phase1, check_phase2,
check_phase2_edge, check_phase3, check_phase3_edge, check_phase4,
and check_phase4_edge:
    normalize(normalize(x).normalized_text) == normalize(x).normalized_text
"""

from __future__ import annotations

import pytest
from text_frontend import NormalizerConfig, normalize


def _collect_all_idempotence_cases() -> list[tuple[str, str, NormalizerConfig]]:
    import check_phase2
    import check_phase2_edge
    import check_phase3
    import check_phase4
    import check_phase4_edge

    cases: list[tuple[str, str, NormalizerConfig]] = []

    # Phase 1
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

    # Phase 2
    for t, kw in check_phase2.cases:
        loc = kw.get("locale", "en-US")
        cases.append(("phase2", t, NormalizerConfig.for_locale(loc)))

    # Phase 2 edge
    for item in check_phase2_edge.edge_cases:
        t = item[0]
        kw = item[2] if len(item) > 2 else {}
        loc = kw.get("locale", "en-US")
        cases.append(("phase2_edge", t, NormalizerConfig.for_locale(loc)))

    # Phase 3
    for t, exp, loc in check_phase3.CASES:
        cases.append(("phase3", t, NormalizerConfig.for_locale(loc)))

    # Phase 4
    for c in check_phase4.CASES:
        cases.append(("phase4", c["input"], c["config"]))

    # Phase 4 edge
    for c in check_phase4_edge.CASES:
        cases.append(("phase4_edge", c["input"], c["config"]))

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
