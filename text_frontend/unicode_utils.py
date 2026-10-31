"""Unicode normalization, character canonicalization, and monotonic coordinate mapping.

Handles strict UTF-8 bytes decoding, BOM removal, lone surrogate validation,
safe character stripping, space normalization, and grapheme cluster-level NFC mapping.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Sequence

from text_frontend.data_loader import load_words_set
from text_frontend.validation import NormalizationWarning, PreprocessingEdit

# Disallowed C0 controls: 0x00-0x1F and 0x7F EXCEPT \t (0x09), \n (0x0A), \r (0x0D)
DISALLOWED_C0: frozenset[str] = frozenset(
    chr(i) for i in range(32) if i not in (9, 10, 13)
) | {chr(127)}

# Disallowed formatting controls to strip (keep ZWJ \u200d and ZWNJ \u200c strictly)
DISALLOWED_CONTROLS: frozenset[str] = frozenset({
    "\u200b",  # Zero-Width Space
    "\ufeff",  # BOM / Zero-Width No-Break Space
    "\u00ad",  # Soft Hyphen
    "\u2060",  # Word Joiner
    "\u200e",  # LRM
    "\u200f",  # RLM
    "\u061c",  # ALM
    "\u202a",  # LRE
    "\u202b",  # RLE
    "\u202c",  # PDF
    "\u202d",  # LRO
    "\u202e",  # RLO
    "\u2066",  # LRI
    "\u2067",  # RLI
    "\u2068",  # FSI
    "\u2069",  # PDI
})

# Smart quotes canonicalization map
QUOTE_MAP: dict[str, str] = {
    "\u201c": '"',  # Left double quotation mark
    "\u201d": '"',  # Right double quotation mark
    "\u2018": "'",  # Left single quotation mark
    "\u2019": "'",  # Right single quotation mark (apostrophe)
    "\u201a": "'",  # Single low-9 quotation mark
    "\u201b": "'",  # Single high-reversed-9 quotation mark
    "\u201e": '"',  # Double low-9 quotation mark
    "\u201f": '"',  # Double high-reversed-9 quotation mark
    "\u00ab": '"',  # Left-pointing double angle quotation mark
    "\u00bb": '"',  # Right-pointing double angle quotation mark
}

# Grouping space characters (preserved before number grouping)
GROUPING_SPACES: frozenset[str] = frozenset({
    "\u2009",  # Thin space
    "\u202f",  # Narrow no-break space
    "\u00a0",  # Non-breaking space
})

# Typographic ligatures map to ASCII equivalents (keep æ, œ unchanged)
LIGATURE_MAP: dict[str, str] = {
    "\ufb00": "ff",   # Latin small ligature ff
    "\ufb01": "fi",   # Latin small ligature fi
    "\ufb02": "fl",   # Latin small ligature fl
    "\ufb03": "ffi",  # Latin small ligature ffi
    "\ufb04": "ffl",  # Latin small ligature ffl
    "\ufb05": "st",   # Latin small ligature long s t (ﬅ)
    "\ufb06": "st",   # Latin small ligature st (ﬆ)
}

HYPHEN_BREAK_REGEX = re.compile(r"([A-Za-z]{2,})-(?:[ \t]*\r?\n[ \t]*)([A-Za-z]{2,})")
MULT_PUNCT_REGEX = re.compile(r"(!{2,}|\?{2,}|\.{4,})")


def decode_and_validate_input(
    raw_input: str | bytes,
    max_input_length: int,
) -> tuple[str, tuple[NormalizationWarning, ...], bool]:
    """Decodes bytes (strict UTF-8, strips BOM) and validates surrogates and length.

    Returns:
        (decoded_text, warnings, is_fatal)
    """
    if isinstance(raw_input, bytes):
        try:
            # Strip UTF-8 BOM if present
            if raw_input.startswith(b"\xef\xbb\xbf"):
                raw_input = raw_input[3:]
            text = raw_input.decode("utf-8")
        except UnicodeDecodeError:
            warning = NormalizationWarning(
                code="INVALID_UTF8_ENCODING",
                message="Input bytes could not be decoded as strict UTF-8.",
                severity="error",
                original_span=(0, 0),
            )
            return "", (warning,), True
    elif isinstance(raw_input, str):
        # Strip leading BOM character if present
        if raw_input.startswith("\ufeff"):
            text = raw_input[1:]
        else:
            text = raw_input
    else:
        warning = NormalizationWarning(
            code="INVALID_INPUT_TYPE",
            message=f"Expected str or bytes, got {type(raw_input).__name__}.",
            severity="error",
            original_span=(0, 0),
        )
        return "", (warning,), True

    # Check for lone surrogates
    for idx, char in enumerate(text):
        code_point = ord(char)
        if 0xD800 <= code_point <= 0xDFFF:
            warning = NormalizationWarning(
                code="LONE_SURROGATES_DETECTED",
                message="Input text contains forbidden lone surrogate code points.",
                severity="error",
                original_span=(idx, idx + 1),
            )
            return "", (warning,), True

    # Check maximum input length
    if len(text) > max_input_length:
        warning = NormalizationWarning(
            code="LENGTH_LIMIT_EXCEEDED",
            message=f"Input length {len(text)} exceeds maximum limit {max_input_length}.",
            severity="error",
            original_span=(0, len(text)),
        )
        return "", (warning,), True

    return text, (), False


class MonotonicCoordinateMapper:
    """Tracks mapping from preprocessed text coordinates back to original text coordinates."""

    def __init__(self, raw_indices: Sequence[tuple[int, int]]):
        """raw_indices[clean_idx] is (raw_start, raw_end) in original_text."""
        self._raw_indices = list(raw_indices)

    @classmethod
    def create_identity(cls, length: int) -> MonotonicCoordinateMapper:
        return cls([(i, i + 1) for i in range(length)])

    def to_raw_span(self, clean_start: int, clean_end: int) -> tuple[int, int]:
        """Translates a slice [clean_start, clean_end) into [orig_start, orig_end)."""
        if not self._raw_indices:
            return (0, 0)
        if clean_start >= clean_end:
            idx = min(clean_start, len(self._raw_indices) - 1)
            raw_pos = self._raw_indices[idx][0]
            return (raw_pos, raw_pos)

        clamped_start = max(0, min(clean_start, len(self._raw_indices) - 1))
        clamped_end = max(0, min(clean_end - 1, len(self._raw_indices) - 1))

        raw_start = self._raw_indices[clamped_start][0]
        raw_end = self._raw_indices[clamped_end][1]
        return (raw_start, raw_end)


def is_atomic_continuation(char: str) -> bool:
    """Returns True if char must attach to the preceding character in a cluster."""
    code_point = ord(char)
    # ZWJ \u200d
    if char == "\u200d":
        return True
    # Combining mark
    if unicodedata.combining(char) > 0:
        return True
    # Variation selectors (U+FE00 - U+FE0F, U+E0100 - U+E01EF)
    if 0xFE00 <= code_point <= 0xFE0F or 0xE0100 <= code_point <= 0xE01EF:
        return True
    # Skin-tone modifiers (Fitzpatrick types 1-5: U+1F3FB - U+1F3FF)
    if 0x1F3FB <= code_point <= 0x1F3FF:
        return True
    # Regional indicator symbols (U+1F1E6 - U+1F1FF)
    if 0x1F1E6 <= code_point <= 0x1F1FF:
        return True
    return False


def _clean_tokens_step(
    text: str,
    raw_spans: list[tuple[int, int]],
    edits: list[PreprocessingEdit],
) -> tuple[str, list[tuple[int, int]]]:
    """Cleans line-break hyphenation and collapses repeated punctuation."""
    # 1. Hyphenation repair across line breaks
    words = load_words_set()
    out_chars: list[str] = []
    out_spans: list[tuple[int, int]] = []
    idx = 0
    for m in HYPHEN_BREAK_REGEX.finditer(text):
        w1, w2 = m.group(1), m.group(2)
        joined = (w1 + w2).lower()
        if joined in words:
            out_chars.extend(text[idx : m.start()])
            out_spans.extend(raw_spans[idx : m.start()])
            w1_len = len(w1)
            out_chars.extend(w1)
            out_spans.extend(raw_spans[m.start() : m.start() + w1_len])
            hyphen_start = m.start() + w1_len
            newline_end = m.end() - len(w2)
            orig_s = raw_spans[hyphen_start][0]
            orig_e = raw_spans[newline_end - 1][1]
            edits.append(
                PreprocessingEdit(
                    original_span=(orig_s, orig_e),
                    output_span=(len(out_chars), len(out_chars)),
                    category="repair_hyphenation",
                    description=f"Repaired line-break hyphenation for '{w1}{w2}'.",
                )
            )
            out_chars.extend(w2)
            out_spans.extend(raw_spans[m.end() - len(w2) : m.end()])
            idx = m.end()
    out_chars.extend(text[idx:])
    out_spans.extend(raw_spans[idx:])

    # 2. Multiple punctuation (!{2,} -> !, \?{2,} -> ?, \.{4,} -> ...)
    text2 = "".join(out_chars)
    spans2 = out_spans
    final_chars: list[str] = []
    final_spans: list[tuple[int, int]] = []
    idx = 0
    for m in MULT_PUNCT_REGEX.finditer(text2):
        final_chars.extend(text2[idx : m.start()])
        final_spans.extend(spans2[idx : m.start()])
        punct = m.group(1)
        orig_s = spans2[m.start()][0]
        orig_e = spans2[m.end() - 1][1]
        if punct.startswith("!"):
            repl = "!"
            desc = "Collapsed repeated exclamation marks."
        elif punct.startswith("?"):
            repl = "?"
            desc = "Collapsed repeated question marks."
        else:
            repl = "..."
            desc = "Collapsed repeated periods to ellipsis."
        edits.append(
            PreprocessingEdit(
                original_span=(orig_s, orig_e),
                output_span=(len(final_chars), len(final_chars) + len(repl)),
                category="normalize_punctuation",
                description=desc,
            )
        )
        for ch in repl:
            final_chars.append(ch)
            final_spans.append((orig_s, orig_e))
        idx = m.end()
    final_chars.extend(text2[idx:])
    final_spans.extend(spans2[idx:])

    return "".join(final_chars), final_spans


def canonicalize_and_map(
    raw_text: str,
) -> tuple[str, MonotonicCoordinateMapper, tuple[PreprocessingEdit, ...]]:
    """Applies Step 1 character canonicalization, selective stripping, and NFC mapping.

    Maintains strict cluster-level monotonic coordinate mapping back to raw_text.
    """
    edits: list[PreprocessingEdit] = []
    intermediate_chars: list[str] = []
    intermediate_raw_spans: list[tuple[int, int]] = []

    # Pass 1: Filter disallowed characters and standardize quotes/controls
    for idx, char in enumerate(raw_text):
        raw_span = (idx, idx + 1)

        # Disallowed C0 controls
        if char in DISALLOWED_C0:
            edits.append(
                PreprocessingEdit(
                    original_span=raw_span,
                    output_span=(len(intermediate_chars), len(intermediate_chars)),
                    category="strip_disallowed",
                    description="Stripped disallowed C0 control character.",
                )
            )
            continue

        # Disallowed formatting controls (stripping, keeping ZWJ/ZWNJ)
        if char in DISALLOWED_CONTROLS:
            edits.append(
                PreprocessingEdit(
                    original_span=raw_span,
                    output_span=(len(intermediate_chars), len(intermediate_chars)),
                    category="strip_disallowed",
                    description="Stripped disallowed formatting control character.",
                )
            )
            continue

        # Canonicalize quotation marks
        if char in QUOTE_MAP:
            replacement = QUOTE_MAP[char]
            edits.append(
                PreprocessingEdit(
                    original_span=raw_span,
                    output_span=(len(intermediate_chars), len(intermediate_chars) + 1),
                    category="canonicalize_quote",
                    description="Standardized quotation mark to ASCII.",
                )
            )
            intermediate_chars.append(replacement)
            intermediate_raw_spans.append(raw_span)
            continue

        # Typographic ligatures
        if char in LIGATURE_MAP:
            replacement = LIGATURE_MAP[char]
            edits.append(
                PreprocessingEdit(
                    original_span=raw_span,
                    output_span=(len(intermediate_chars), len(intermediate_chars) + len(replacement)),
                    category="expand_ligature",
                    description="Expanded typographic ligature to ASCII characters.",
                )
            )
            for ch in replacement:
                intermediate_chars.append(ch)
                intermediate_raw_spans.append(raw_span)
            continue

        # Canonicalize horizontal ellipsis
        if char == "\u2026":
            edits.append(
                PreprocessingEdit(
                    original_span=raw_span,
                    output_span=(len(intermediate_chars), len(intermediate_chars) + 3),
                    category="canonicalize_ellipsis",
                    description="Normalized horizontal ellipsis to three ASCII periods.",
                )
            )
            for _ in range(3):
                intermediate_chars.append(".")
                intermediate_raw_spans.append(raw_span)
            continue

        # Keep everything else (including grouping spaces U+2009, U+202F, U+00A0, and dashes)
        intermediate_chars.append(char)
        intermediate_raw_spans.append(raw_span)

    # Pass 1b: Clean line-break hyphenation and repeated punctuation
    raw_inter_text = "".join(intermediate_chars)
    intermediate_text, intermediate_raw_spans = _clean_tokens_step(
        raw_inter_text, intermediate_raw_spans, edits
    )

    # Pass 2: NFC Normalization with Cluster-Level Coordinate Tracking
    if unicodedata.is_normalized("NFC", intermediate_text):
        # Fast path: identity mapping
        final_text = intermediate_text
        final_raw_spans = intermediate_raw_spans
    else:
        # Segment into atomic clusters and normalize
        final_chars: list[str] = []
        final_raw_spans = []

        i = 0
        n = len(intermediate_text)
        while i < n:
            start_i = i
            cluster_chars = [intermediate_text[i]]
            i += 1

            # Consume attached continuation characters
            while i < n and is_atomic_continuation(intermediate_text[i]):
                cluster_chars.append(intermediate_text[i])
                i += 1

            cluster_str = "".join(cluster_chars)
            norm_cluster = unicodedata.normalize("NFC", cluster_str)

            # Raw span covering the entire input cluster
            orig_cluster_start = intermediate_raw_spans[start_i][0]
            orig_cluster_end = intermediate_raw_spans[i - 1][1]
            cluster_raw_span = (orig_cluster_start, orig_cluster_end)

            for nc in norm_cluster:
                final_chars.append(nc)
                final_raw_spans.append(cluster_raw_span)

        final_text = "".join(final_chars)

    mapper = MonotonicCoordinateMapper(final_raw_spans)
    return final_text, mapper, tuple(edits)
