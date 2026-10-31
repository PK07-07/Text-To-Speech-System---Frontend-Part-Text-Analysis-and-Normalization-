"""Main orchestrator and public interface for text_frontend.

Implements:
- Strict encoding and validation checks
- Global deterministic greedy overlap resolver
- Single-pass output assembly with monotonic alignment generation
- Residual-NSW scan with exclusion masking
"""

from __future__ import annotations

import re
from dataclasses import replace
from dataclasses import replace
from typing import Literal

from text_frontend.abbreviation_rules import find_abbreviation_candidates
from text_frontend.config import NormalizerConfig
from text_frontend.currency_rules import find_currency_candidates
from text_frontend.date_time_rules import find_date_time_candidates
from text_frontend.identifier_rules import (
    find_identifier_candidates,
    verbalize_email_span,
    verbalize_url_span,
)
from text_frontend.markup_parser import preprocess_markup
from text_frontend.number_rules import CandidateSpan, find_number_candidates
from text_frontend.symbol_rules import find_symbol_candidates
from text_frontend.unicode_utils import (
    canonicalize_and_map,
    decode_and_validate_input,
)
from text_frontend.unit_rules import find_unit_candidates
from text_frontend.validation import (
    NormalizationResult,
    NormalizationWarning,
    PACKAGE_VERSION,
    PreprocessingEdit,
    SCHEMA_VERSION,
    Transformation,
)

# Protected span regex patterns (URLs, emails, code identifiers, SSML tags)
URL_REGEX = re.compile(
    r"\b(?:https?://|ftp://|www\.)[^\s<>\"']+", re.IGNORECASE
)
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}[.,;:!?)'\"]*", re.IGNORECASE
)
SSML_TAG_REGEX = re.compile(
    r"</?(?:speak|break|emphasis|phoneme|prosody|say-as|sub|voice|audio|mark|lang|p|s)\b[^>]*>", re.IGNORECASE
)

STRAY_SPACES = frozenset({"\u00a0", "\u2009", "\u202f"})


RESIDUAL_PATTERN = re.compile(r"(\d|[$£€₹¥])")


class TextNormalizer:
    """Reusable normalization engine."""

    def __init__(self, config: NormalizerConfig | None = None):
        self.config = (config or NormalizerConfig()).resolve()
        self.version = f"{PACKAGE_VERSION}+{self.config.content_hash()}"

    def normalize(self, raw_input: str | bytes) -> NormalizationResult:
        """Normalizes input text and returns structured NormalizationResult."""
        # Step 0: Decoding, lone surrogates validation, length limits
        original_text, decode_warnings, is_fatal = decode_and_validate_input(
            raw_input, self.config.max_input_length
        )
        if is_fatal:
            return NormalizationResult(
                original_text=original_text,
                normalized_text="",
                locale=self.config.locale,
                status="failed",
                warnings=decode_warnings,
                normalizer_version=self.version,
                schema_version=SCHEMA_VERSION,
                transformations=(),
                edits=(),
            )

        # Handle empty and whitespace-only input
        if not original_text:
            return NormalizationResult(
                original_text=original_text,
                normalized_text="",
                locale=self.config.locale,
                status="success",
                warnings=(),
                normalizer_version=self.version,
                schema_version=SCHEMA_VERSION,
                transformations=(),
                edits=(),
            )

        if original_text.strip() == "":
            return NormalizationResult(
                original_text=original_text,
                normalized_text="",
                locale=self.config.locale,
                status="success",
                warnings=(),
                normalizer_version=self.version,
                schema_version=SCHEMA_VERSION,
                transformations=(),
                edits=(),
            )

        # Step 1: Character Canonicalization & Monotonic Coordinate Mapping
        clean_text, mapper, edits = canonicalize_and_map(original_text)

        # Step 2: Markup Preprocessing
        preprocessed_text, mapper, markup_edits, markup_warnings = preprocess_markup(
            clean_text, mapper, ssml_mode=self.config.ssml_mode, config=self.config
        )
        all_edits: list[PreprocessingEdit] = list(edits) + list(markup_edits)

        # Step 3: Scan Protected Spans
        protected_spans: list[CandidateSpan] = []
        for m in URL_REGEX.finditer(preprocessed_text):
            end_pos = m.end()
            while end_pos > m.start() and preprocessed_text[end_pos - 1] in ".,;:!?)'\"":
                end_pos -= 1
            protected_spans.append(
                CandidateSpan(
                    start=m.start(),
                    end=end_pos,
                    category="identifier",
                    rule_id="id.url",
                    priority=2,
                    verbalizer=verbalize_url_span,
                )
            )
        for m in EMAIL_REGEX.finditer(preprocessed_text):
            end_pos = m.end()
            while end_pos > m.start() and preprocessed_text[end_pos - 1] in ".,;:!?)'\"":
                end_pos -= 1
            protected_spans.append(
                CandidateSpan(
                    start=m.start(),
                    end=end_pos,
                    category="identifier",
                    rule_id="id.email",
                    priority=2,
                    verbalizer=verbalize_email_span,
                )
            )
        if self.config.ssml_mode:
            for m in SSML_TAG_REGEX.finditer(preprocessed_text):
                protected_spans.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="ssml",
                        rule_id="markup.ssml",
                        priority=2,
                        verbalizer=lambda raw, cfg: (raw, [], False),
                    )
                )

        # Step 4: Detect Candidate Spans across all domains
        candidates: list[CandidateSpan] = []

        # 4.1 Custom Overrides (Priority Rank 1)
        if self.config.custom_overrides:
            for target, replacement in self.config.custom_overrides:
                flags = 0 if self.config.custom_overrides_case_sensitive else re.IGNORECASE
                pattern = rf"\b{re.escape(target)}\b"
                for m in re.finditer(pattern, preprocessed_text, flags):
                    candidates.append(
                        CandidateSpan(
                            start=m.start(),
                            end=m.end(),
                            category="override",
                            rule_id="override.custom",
                            priority=1,
                            verbalizer=lambda raw, cfg, repl=replacement: (repl, [], False),
                        )
                    )

        # 4.2 Protected Spans
        candidates.extend(protected_spans)

        # 4.3 Domain candidates
        # Dates (Rank 3), Times/Durations (Rank 4)
        candidates.extend(find_date_time_candidates(preprocessed_text, self.config))
        # Phone Numbers & Technical IDs (Rank 5)
        candidates.extend(find_identifier_candidates(preprocessed_text, self.config))
        # Currencies & Currency ranges (Rank 6)
        candidates.extend(find_currency_candidates(preprocessed_text, self.config))
        # Units & Unit ranges (Rank 6/7)
        candidates.extend(find_unit_candidates(preprocessed_text, self.config))
        # Numbers, Ranges, Fractions, Ratios, Percentages (Rank 6/7)
        candidates.extend(find_number_candidates(preprocessed_text, self.config))
        # Abbreviations & Acronyms (Rank 8)
        candidates.extend(find_abbreviation_candidates(preprocessed_text, self.config))
        # Symbols (Rank 9)
        candidates.extend(find_symbol_candidates(preprocessed_text, self.config))

        # Step 5: Global Deterministic Greedy Overlap Resolution
        winning_spans = self._resolve_overlaps(candidates, protected_spans)

        # Step 6 & 7: Contextual Verbalization and Single-Pass Assembly
        accumulated_warnings: list[NormalizationWarning] = list(decode_warnings) + list(markup_warnings)
        transformations: list[Transformation] = []
        output_chunks: list[str] = []
        output_clean_indices: list[int] = []
        current_pos = 0
        current_out_pos = 0

        # Sort winning spans strictly by start position
        winning_spans.sort(key=lambda s: s.start)

        for span in winning_spans:
            # Copy untransformed text between spans and clean remaining NBSP/thin-space
            if span.start > current_pos:
                untransformed_slice = preprocessed_text[current_pos : span.start]
                cleaned_slice, slice_edits = self._clean_stray_spaces(
                    untransformed_slice, current_pos, current_out_pos, mapper
                )
                all_edits.extend(slice_edits)
                if cleaned_slice and cleaned_slice[0].isalnum():
                    last_char = None
                    for chunk in reversed(output_chunks):
                        if chunk:
                            last_char = chunk[-1]
                            break
                    if last_char and last_char.isalnum():
                        output_chunks.append(" ")
                        output_clean_indices.append(-1)
                        current_out_pos += 1
                output_chunks.append(cleaned_slice)
                for c in range(current_pos, span.start):
                    output_clean_indices.append(c)
                current_out_pos += len(cleaned_slice)

            # Verbalize span
            span_clean_text = preprocessed_text[span.start : span.end]
            verbalized_str, span_warnings, is_ambiguous = span.verbalizer(
                span_clean_text, self.config
            )

            # Ensure transformation output does not merge with adjacent alphanumeric character
            if verbalized_str and verbalized_str[0].isalnum():
                last_char = None
                for chunk in reversed(output_chunks):
                    if chunk:
                        last_char = chunk[-1]
                        break
                if last_char and last_char.isalnum():
                    output_chunks.append(" ")
                    output_clean_indices.append(-1)
                    current_out_pos += 1

            # Map coordinates to original text
            raw_start, raw_end = mapper.to_raw_span(span.start, span.end)
            orig_slice = original_text[raw_start:raw_end]

            # Adjust warning span coordinates to original text
            for w in span_warnings:
                w_orig_span = mapper.to_raw_span(
                    span.start + w.original_span[0],
                    span.start + w.original_span[1],
                )
                accumulated_warnings.append(
                    NormalizationWarning(
                        code=w.code,
                        message=w.message,
                        severity=w.severity,
                        original_span=w_orig_span,
                    )
                )

            # Record transformation
            out_start = current_out_pos
            out_end = current_out_pos + len(verbalized_str)
            output_chunks.append(verbalized_str)
            for _ in range(len(verbalized_str)):
                output_clean_indices.append(-1)  # Mark transformed/protected
            current_out_pos = out_end

            # Clean whitespace before punctuation replacement (e.g. pause policy producing comma)
            if verbalized_str.startswith(",") and len(output_chunks) > 1 and output_chunks[-2].endswith(" "):
                output_chunks[-2] = output_chunks[-2][:-1]
                output_clean_indices.pop(-len(verbalized_str) - 1)
                current_out_pos -= 1
                out_start -= 1
                out_end -= 1
                if transformations:
                    prev_t = transformations[-1]
                    if prev_t.output_span[1] > out_start:
                        transformations[-1] = replace(
                            prev_t,
                            output_span=(prev_t.output_span[0], max(prev_t.output_span[0], out_start)),
                        )

            # Clean whitespace around dropped tokens (e.g. dropped emojis or non-speech)
            if verbalized_str == "":
                if span.end < len(preprocessed_text) and preprocessed_text[span.end] == " ":
                    if any(chunk.endswith(" ") for chunk in output_chunks if chunk):
                        current_pos = span.end + 1
                    else:
                        current_pos = span.end
                elif span.end < len(preprocessed_text) and preprocessed_text[span.end] in ".,;:!?":
                    for idx in range(len(output_chunks) - 1, -1, -1):
                        if output_chunks[idx]:
                            if output_chunks[idx].endswith(" "):
                                output_chunks[idx] = output_chunks[idx][:-1]
                                output_clean_indices.pop()
                                current_out_pos -= 1
                                out_start = current_out_pos
                                out_end = current_out_pos
                                if transformations:
                                    prev_t = transformations[-1]
                                    if prev_t.output_span[1] > current_out_pos:
                                        transformations[-1] = replace(
                                            prev_t,
                                            output_span=(prev_t.output_span[0], max(prev_t.output_span[0], current_out_pos)),
                                        )
                            break
                    current_pos = span.end
                else:
                    current_pos = span.end
            else:
                current_pos = span.end

            t = Transformation(
                original_span=(raw_start, raw_end),
                output_span=(out_start, out_end),
                original_text=orig_slice,
                normalized_text=verbalized_str,
                category=span.category,
                rule_id=span.rule_id,
                is_ambiguous=is_ambiguous,
            )
            transformations.append(t)

        # Copy any remaining trailing text and clean remaining NBSP/thin-space
        if current_pos < len(preprocessed_text):
            trailing_slice = preprocessed_text[current_pos:]
            cleaned_slice, slice_edits = self._clean_stray_spaces(
                trailing_slice, current_pos, current_out_pos, mapper
            )
            all_edits.extend(slice_edits)
            if cleaned_slice and cleaned_slice[0].isalnum():
                last_char = None
                for chunk in reversed(output_chunks):
                    if chunk:
                        last_char = chunk[-1]
                        break
                if last_char and last_char.isalnum():
                    output_chunks.append(" ")
                    output_clean_indices.append(-1)
                    current_out_pos += 1
            output_chunks.append(cleaned_slice)
            for c in range(current_pos, len(preprocessed_text)):
                output_clean_indices.append(c)

        normalized_text = "".join(output_chunks)

        # Step 8: Post-Validation & Residual-NSW Scan
        # 8.1 Expansion ratio check
        max_allowed_len = max(1, len(original_text)) * self.config.max_expansion_ratio
        if len(normalized_text) > max_allowed_len:
            warning = NormalizationWarning(
                code="EXPANSION_RATIO_EXCEEDED",
                message=f"Expansion ratio {len(normalized_text) / len(original_text):.1f} exceeded max {self.config.max_expansion_ratio}.",
                severity="error",
                original_span=(0, len(original_text)),
            )
            return NormalizationResult(
                original_text=original_text,
                normalized_text="",
                locale=self.config.locale,
                status="failed",
                warnings=tuple(accumulated_warnings + [warning]),
                normalizer_version=self.version,
                schema_version=SCHEMA_VERSION,
                transformations=(),
                edits=tuple(all_edits),
            )

        # 8.2 Residual-NSW Scan with exact exclusion mask
        residual_warnings = self._scan_residual_nsws(
            normalized_text, output_clean_indices, mapper
        )
        accumulated_warnings.extend(residual_warnings)

        # 8.3 Post-Validation check that every digit in original_text is accounted for
        digit_warnings = self._validate_digits_accounted_for(
            original_text, transformations, accumulated_warnings
        )
        accumulated_warnings.extend(digit_warnings)

        # Determine overall status: info does NOT downgrade status.
        # Rule-level warnings (severity 'warning' or 'error') downgrade status to 'partial'.
        # Status 'failed' comes only from Step 0 fatal failures or safety breaches, never from rule warnings.
        status: Literal["success", "partial", "failed"] = "success"
        if any(w.severity in ("warning", "error") for w in accumulated_warnings):
            status = "partial"

        return NormalizationResult(
            original_text=original_text,
            normalized_text=normalized_text,
            locale=self.config.locale,
            status=status,
            warnings=tuple(accumulated_warnings),
            normalizer_version=self.version,
            schema_version=SCHEMA_VERSION,
            transformations=tuple(transformations),
            edits=tuple(all_edits),
        )

    def _clean_stray_spaces(
        self,
        slice_text: str,
        clean_start_pos: int,
        out_start_pos: int,
        mapper,
    ) -> tuple[str, list[PreprocessingEdit]]:
        """Replaces remaining U+00A0, U+2009, U+202F with ordinary space, recording PreprocessingEdits."""
        cleaned_chars: list[str] = []
        edits: list[PreprocessingEdit] = []
        for offset, ch in enumerate(slice_text):
            if ch in STRAY_SPACES:
                cleaned_chars.append(" ")
                clean_idx = clean_start_pos + offset
                raw_s, raw_e = mapper.to_raw_span(clean_idx, clean_idx + 1)
                out_idx = out_start_pos + offset
                edits.append(
                    PreprocessingEdit(
                        original_span=(raw_s, raw_e),
                        output_span=(out_idx, out_idx + 1),
                        category="normalize_space",
                        description="Converted non-breaking or thin space to ordinary space.",
                    )
                )
            else:
                cleaned_chars.append(ch)
        return "".join(cleaned_chars), edits

    def _validate_digits_accounted_for(
        self,
        original_text: str,
        transformations: list[Transformation],
        warnings: list[NormalizationWarning],
    ) -> list[NormalizationWarning]:
        """Ensures that every digit in original_text is accounted for in an accepted transformation or warning."""
        unaccounted: list[NormalizationWarning] = []
        covered = [False] * len(original_text)
        for t in transformations:
            s, e = t.original_span
            for i in range(max(0, s), min(len(original_text), e)):
                covered[i] = True
        for w in warnings:
            if w.original_span != (0, 0):
                s, e = w.original_span
                for i in range(max(0, s), min(len(original_text), e)):
                    covered[i] = True

        for idx, ch in enumerate(original_text):
            if ch.isdigit() and not covered[idx]:
                unaccounted.append(
                    NormalizationWarning(
                        code="UNACCOUNTED_DIGIT",
                        message="Digit in input was neither verbalized nor warned.",
                        severity="warning",
                        original_span=(idx, idx + 1),
                    )
                )
        return unaccounted

    def _resolve_overlaps(
        self,
        candidates: list[CandidateSpan],
        protected_spans: list[CandidateSpan],
    ) -> list[CandidateSpan]:
        """Resolves candidate overlaps using Stage 1 mandatory claims and Stage 2 greedy acceptance."""
        # Stage 1: Mandatory Claims (Overrides and Protected Spans)
        accepted: list[CandidateSpan] = []

        # Claim Overrides (Priority 1): longest first, then earliest
        overrides = [c for c in candidates if c.priority == 1]
        overrides.sort(key=lambda c: (-(c.end - c.start), c.start))
        claimed_overrides: list[CandidateSpan] = []
        for o in overrides:
            if not any(self._overlaps(o, co) for co in claimed_overrides):
                claimed_overrides.append(o)

        # Claim Protected Spans (Priority 2): longest first, an override inside a protected span loses unless whole span matches
        sorted_protected = sorted(protected_spans, key=lambda p: (-(p.end - p.start), p.start))
        claimed_protected: list[CandidateSpan] = []
        for p in sorted_protected:
            if any(self._overlaps(p, cp) for cp in claimed_protected):
                continue
            overlapping_overrides = [o for o in claimed_overrides if self._overlaps(o, p)]
            if not overlapping_overrides:
                claimed_protected.append(p)
            else:
                if any(o.start == p.start and o.end == p.end for o in overlapping_overrides):
                    pass  # Override wins
                else:
                    for o in overlapping_overrides:
                        claimed_overrides.remove(o)
                    claimed_protected.append(p)

        accepted.extend(claimed_overrides)
        accepted.extend(claimed_protected)

        # Stage 2: Greedy acceptance for all remaining candidates
        remaining = [c for c in candidates if c.priority > 2]
        # Dominance tuple: (-length, category_rank, start_index)
        remaining.sort(key=lambda c: (-(c.end - c.start), c.priority, c.start))

        for cand in remaining:
            cs, ce = cand.start, cand.end
            if not any(cs < acc.end and acc.start < ce for acc in accepted):
                accepted.append(cand)

        return accepted

    @staticmethod
    def _overlaps(a: CandidateSpan, b: CandidateSpan) -> bool:
        """Returns True if span a and span b overlap in character coordinates."""
        return a.start < b.end and b.start < a.end

    def _scan_residual_nsws(
        self,
        normalized_text: str,
        output_clean_indices: list[int],
        mapper,
    ) -> list[NormalizationWarning]:
        """Scans normalized_text for residual digits or unexpanded symbols outside protected ranges."""
        warnings: list[NormalizationWarning] = []

        for m in RESIDUAL_PATTERN.finditer(normalized_text):
            pos = m.start()
            if pos < len(output_clean_indices):
                clean_idx = output_clean_indices[pos]
                if clean_idx == -1:
                    # Transformed or protected token: skip
                    continue
                raw_start, raw_end = mapper.to_raw_span(clean_idx, clean_idx + 1)
            else:
                raw_start, raw_end = (0, 0)

            warnings.append(
                NormalizationWarning(
                    code="RESIDUAL_NSW_DETECTED",
                    message="Unexpanded residual non-standard word detected in normalized text.",
                    severity="warning",
                    original_span=(raw_start, raw_end),
                )
            )

        return warnings


def normalize(
    raw_text: str | bytes,
    locale: str | None = None,
    style: str | None = None,
    config: NormalizerConfig | None = None,
) -> NormalizationResult:
    """Convenience functional wrapper for text normalization."""
    if config is not None:
        overrides = {}
        if locale is not None:
            overrides["locale"] = locale
        if style is not None:
            overrides["style"] = style
        effective_config = replace(config, **overrides) if overrides else config
    else:
        effective_config = NormalizerConfig.for_locale(
            locale=locale or "en-US",
            style=style or "conversational",
        )

    normalizer = TextNormalizer(config=effective_config)
    return normalizer.normalize(raw_text)
