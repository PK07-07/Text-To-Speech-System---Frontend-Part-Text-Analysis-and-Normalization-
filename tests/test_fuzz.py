"""Fuzz and property-based testing for text_frontend.

Runs 5,000 generated inputs using stdlib random with fixed seed 42.
Asserts:
- Never raises unhandled exceptions.
- Output transformations are monotonic and strictly non-overlapping.
- Normalization is 100% deterministic.
- No input digit is silently lost without warning/transformation.
- Expansion ratio limit is strictly respected.
- Success results have zero residual NSWs outside protected spans.
"""

from __future__ import annotations

import random
import re
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


VOCAB_WORDS = [
    "The", "item", "costs", "price", "is", "at", "meeting", "on", "call", "Dr.",
    "Mr.", "St.", "Ave.", "Jan", "Feb", "2024", "100", "1st", "2nd", "3.14",
    "25%", "$10.50", "€50", "£100", "₹5,000", "10:30am", "5kg", "10x20", "x^2",
    "H2O", "and/or", "OK", "ASAP", "#trending", "hello@example.com", "https://x.com",
    "New York–London", "bold—succeeded", "A ﬁne ﬂight", "Really??", "exam-\nple",
]

SYMBOLS = [
    "$", "£", "€", "₹", "¥", "%", "@", "#", "&", "~", "/", "-", "–", "—", "+", "=",
    "*", "<", ">", "√", "²", "³", "°C", "Ω", "µs", ":)", "<3", "👋", "🎉",
]

UNICODE_CHARS = [
    "æ", "œ", "Æ", "Œ", "ﬁ", "ﬂ", "ﬀ", "\u200b", "\ufeff", "“", "”", "‘", "’", "\u00a0",
]


def _generate_fuzz_input(rng: random.Random) -> str:
    """Generates a pseudo-random sentence from tokens and symbols."""
    mode = rng.randint(0, 7)
    if mode == 0:
        # Standard sentence with mixed tokens
        num_tokens = rng.randint(1, 10)
        tokens = [rng.choice(VOCAB_WORDS + SYMBOLS) for _ in range(num_tokens)]
        return " ".join(tokens)
    elif mode == 1:
        # Number-heavy sequence
        parts = []
        for _ in range(rng.randint(1, 5)):
            val = rng.randint(-1000000, 1000000)
            sep = rng.choice([" ", ", ", " - ", " / ", " + ", " = "])
            parts.append(str(val))
            parts.append(sep)
        return "".join(parts).strip()
    elif mode == 2:
        # Punctuation and symbol soup
        return "".join(rng.choice(SYMBOLS + UNICODE_CHARS) for _ in range(rng.randint(1, 20)))
    elif mode == 3:
        # Unicode / ligature / quote stress
        return " ".join(rng.choice(UNICODE_CHARS + VOCAB_WORDS[:5]) for _ in range(rng.randint(2, 8)))
    elif mode == 4:
        # Short strings or single characters
        return rng.choice(VOCAB_WORDS + SYMBOLS + UNICODE_CHARS + ["", " ", "   ", "\n", "\t"])
    elif mode == 5:
        # Raw alphanumeric strings
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-./"
        return "".join(rng.choice(chars) for _ in range(rng.randint(1, 30)))
    elif mode == 6:
        # Glued letter-digit and digit-letter boundaries in both directions
        w1 = rng.choice(["items", "apples", "miles", "units", "pages", "books"])
        n1 = rng.randint(1, 999)
        w2 = rng.choice(["user", "item", "code", "file", "token"])
        n2 = rng.randint(1, 999)
        return f"Process {n1}{w1} from {w2}{n2} now."
    else:
        # Date/time/currency composites
        return f"On {rng.choice(['Jan', 'Feb', 'March'])} {rng.randint(1, 31)}, {rng.randint(1900, 2030)} pay {rng.choice(['$', '€', '£'])}{rng.randint(1, 1000)}."


def test_fuzz_property_invariants_5000_inputs():
    """Runs 5,000 fuzz inputs verifying core invariant properties."""
    rng = random.Random(42)
    norm = TextNormalizer(NormalizerConfig.for_locale("en-US"))

    for iteration in range(5000):
        raw = _generate_fuzz_input(rng)

        # 1. Never raises unhandled exception
        try:
            res1 = norm.normalize(raw)
        except Exception as exc:
            pytest.fail(f"Fuzz test crashed on iteration {iteration} with input {ascii(raw)}: {exc}")

        # 2. Deterministic
        res2 = norm.normalize(raw)
        assert res1.normalized_text == res2.normalized_text, f"Non-deterministic output for input {ascii(raw)}"
        assert res1.status == res2.status, f"Non-deterministic status for input {ascii(raw)}"
        assert len(res1.warnings) == len(res2.warnings), f"Non-deterministic warning count for input {ascii(raw)}"

        # 3. Monotonic non-overlapping spans
        last_out_end = 0
        for t in res1.transformations:
            orig_s, orig_e = t.original_span
            out_s, out_e = t.output_span
            assert 0 <= orig_s <= orig_e <= len(raw), f"Transformation original_span out of bounds: {t} for raw len {len(raw)}"
            assert 0 <= out_s <= out_e <= len(res1.normalized_text), f"Transformation output_span out of bounds: {t}"
            assert out_s >= last_out_end, f"Overlapping or non-monotonic output spans: {t} vs prev end {last_out_end}"
            last_out_end = out_e

            # 3b. Transformation output never merges with adjacent alphanumeric
            if out_s < out_e:
                if res1.normalized_text[out_s].isalnum() and out_s > 0:
                    assert not res1.normalized_text[out_s - 1].isalnum(), (
                        f"Transformation output merged with predecessor alphanumeric at {out_s}: {t} in {ascii(res1.normalized_text)}"
                    )
                if res1.normalized_text[out_e - 1].isalnum() and out_e < len(res1.normalized_text):
                    assert not res1.normalized_text[out_e].isalnum(), (
                        f"Transformation output merged with successor alphanumeric at {out_e}: {t} in {ascii(res1.normalized_text)}"
                    )

        # 4. Expansion ratio respected
        max_allowed = int(len(raw) * norm.config.max_expansion_ratio)
        if len(raw) > 0 and len(res1.normalized_text) > max_allowed:
            assert res1.status == "failed", f"Expansion limit exceeded without status='failed': len {len(res1.normalized_text)} > {max_allowed}"

        # 5. Success results have zero residual NSWs outside transformations
        if res1.status == "success":
            residual_rx = re.compile(r"(\d|[$£€₹¥])")
            for m in residual_rx.finditer(res1.normalized_text):
                pos = m.start()
                is_transformed = any(t.output_span[0] <= pos < t.output_span[1] for t in res1.transformations)
                assert is_transformed, f"Residual NSW {ascii(m.group())} at pos {pos} in success result: {ascii(res1.normalized_text)}"

        # 6. No input digit silently lost (must be spoken, inside transformed/protected span, or warned)
        for idx, ch in enumerate(raw):
            if ch.isdigit():
                in_span = any(t.original_span[0] <= idx < t.original_span[1] for t in res1.transformations)
                in_output = ch in res1.normalized_text
                has_warning = bool(res1.warnings) or res1.status in ("partial", "failed")
                assert in_span or in_output or has_warning, (
                    f"Input digit {ch} at index {idx} silently lost without transformation, output presence, or warning in {ascii(raw)}"
                )

        # 7. Status valid
        assert res1.status in ("success", "partial", "failed")
