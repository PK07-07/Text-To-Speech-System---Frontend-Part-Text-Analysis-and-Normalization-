"""Dev-only automated cross-check oracle comparing custom verbalizer against num2words."""

from __future__ import annotations

import random
from num2words import num2words
from text_frontend.number_rules import verbalize_cardinal
from tests.conftest import normalize_oracle_words


def test_oracle_cardinal_cross_check():
    """Fuzzes 10,000 integers against num2words across varied orders of magnitude with fixed seed."""
    rng = random.Random(42)  # Deterministic seed for reproducible tests

    # 1. Exact boundary values around 10^3, 10^6, 10^9, 10^12
    boundary_values: list[int] = [0, 1, -1]
    for p in (3, 6, 9, 12):
        base = 10**p
        for offset in (-2, -1, 0, 1, 2):
            val = base + offset
            boundary_values.append(val)
            boundary_values.append(-val)

    # 2. Structured range samples:
    # 0 - 999: 1000 samples
    samples_0_999 = [rng.randint(0, 999) for _ in range(1000)]
    # Negatives 0 to -999: 1000 samples
    samples_neg_999 = [rng.randint(-999, -1) for _ in range(1000)]
    # 1,000 - 999,999: 3000 samples
    samples_thousands = [rng.randint(1_000, 999_999) for _ in range(3000)]
    # 1,000,000 - 999,999,999: 3000 samples
    samples_millions = [rng.randint(1_000_000, 999_999_999) for _ in range(3000)]
    # 10^9 - 10^12: 2000 samples
    samples_billions = [rng.randint(10**9, 10**12) for _ in range(2000)]

    all_test_values = (
        boundary_values
        + samples_0_999
        + samples_neg_999
        + samples_thousands
        + samples_millions
        + samples_billions
    )

    # Track normalized differences adapter resolves
    normalized_away_counts: dict[str, int] = {
        "hyphen_removed (e.g. 'twenty-five' -> 'twenty five')": 0,
        "and_removed (e.g. 'one hundred and five' -> 'one hundred five')": 0,
        "minus_mapped_to_negative (e.g. 'minus five' -> 'negative five')": 0,
        "comma_removed (e.g. 'one million, five' -> 'one million five')": 0,
    }

    for val in all_test_values:
        custom_spoken = verbalize_cardinal(val, use_and=False)
        oracle_spoken = num2words(val, lang="en")

        # Track differences before normalization
        if "-" in oracle_spoken or "-" in custom_spoken:
            normalized_away_counts["hyphen_removed (e.g. 'twenty-five' -> 'twenty five')"] += 1
        if " and " in f" {oracle_spoken} ":
            normalized_away_counts["and_removed (e.g. 'one hundred and five' -> 'one hundred five')"] += 1
        if oracle_spoken.startswith("minus ") or " minus " in oracle_spoken:
            normalized_away_counts["minus_mapped_to_negative (e.g. 'minus five' -> 'negative five')"] += 1
        if "," in oracle_spoken:
            normalized_away_counts["comma_removed (e.g. 'one million, five' -> 'one million five')"] += 1

        norm_custom = normalize_oracle_words(custom_spoken)
        norm_oracle = normalize_oracle_words(oracle_spoken)

        assert norm_custom == norm_oracle, (
            f"Oracle mismatch for {val}: custom='{custom_spoken}' -> '{norm_custom}', "
            f"oracle='{oracle_spoken}' -> '{norm_oracle}'"
        )

    print(f"\nOracle adapter normalizations applied across {len(all_test_values):,} comparisons:")
    for norm_type, count in normalized_away_counts.items():
        print(f"  - {norm_type}: {count:,} / {len(all_test_values):,} comparisons affected")

    assert normalized_away_counts["hyphen_removed (e.g. 'twenty-five' -> 'twenty five')"] > 0
    assert normalized_away_counts["and_removed (e.g. 'one hundred and five' -> 'one hundred five')"] > 0
    assert len(all_test_values) >= 10_000
