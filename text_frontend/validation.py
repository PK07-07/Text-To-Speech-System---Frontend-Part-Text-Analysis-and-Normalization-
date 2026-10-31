"""Validation schemas, result containers, and diagnostics for text_frontend.

All data structures are immutable frozen dataclasses using slots and tuples.
Text payloads use repr=False to avoid accidental PII exposure in logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SCHEMA_VERSION: str = "1.0.0"
PACKAGE_VERSION: str = "0.1.0"


@dataclass(frozen=True, slots=True)
class PreprocessingEdit:
    """Records an early character-level modification in Step 1 or Step 2."""

    original_span: tuple[int, int]
    output_span: tuple[int, int]
    category: str
    description: str


@dataclass(frozen=True, slots=True)
class NormalizationWarning:
    """Diagnostic warning emitted during text normalization.

    Contains machine-readable code, generic description (NO raw text),
    severity level, and span coordinates in the original text.
    """

    code: str
    message: str
    severity: Literal["info", "warning", "error"]
    original_span: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Transformation:
    """Details of a single non-standard word (NSW) normalized span."""

    original_span: tuple[int, int]
    output_span: tuple[int, int]
    original_text: str = field(repr=False)
    normalized_text: str = field(repr=False)
    category: str
    rule_id: str
    is_ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Final output container of the text frontend pipeline."""

    original_text: str = field(repr=False)
    normalized_text: str = field(repr=False)
    locale: str
    status: Literal["success", "partial", "failed"]
    warnings: tuple[NormalizationWarning, ...]
    normalizer_version: str
    schema_version: str
    transformations: tuple[Transformation, ...]
    edits: tuple[PreprocessingEdit, ...] = ()
