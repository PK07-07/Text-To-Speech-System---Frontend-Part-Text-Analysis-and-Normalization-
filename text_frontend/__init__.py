"""Text Analysis and Normalization for English Text-to-Speech (TTS).

Provides clean, unambiguous, spoken-form English words with exact monotonic
span alignments and structured diagnostics.
"""

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer, normalize
from text_frontend.validation import (
    NormalizationResult,
    NormalizationWarning,
    PreprocessingEdit,
    Transformation,
)

__version__ = "0.4.3"

__all__ = [
    "__version__",
    "normalize",
    "TextNormalizer",
    "NormalizerConfig",
    "NormalizationResult",
    "Transformation",
    "NormalizationWarning",
    "PreprocessingEdit",
]
