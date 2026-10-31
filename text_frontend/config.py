"""Configuration policies and presets for text_frontend.

Defines immutable configuration dataclass, policy defaults, validation,
and deterministic content hashing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Literal

LEXICON_VERSION: str = "1.0.0"
SUPPORTED_LOCALES: frozenset[str] = frozenset({"en-US", "en-GB", "en-IN"})
SUPPORTED_CURRENCY_CODES: frozenset[str] = frozenset(
    {"USD", "GBP", "EUR", "INR", "JPY", "CAD", "AUD", "CHF", "CNY", "NZD", "SGD"}
)

DEFAULT_COUNT_NOUNS: tuple[str, ...] = (
    "pages", "items", "people", "users", "customers", "calories", "steps", "miles",
    "words", "points", "votes", "units", "records", "cases", "copies", "books",
    "houses", "cars", "shares", "troops", "soldiers", "men", "women", "children",
    "hours", "minutes", "seconds", "days", "feet", "meters", "kilometers",
    "dollars", "euros", "pounds", "rupees", "yen",
)


@dataclass(frozen=True, slots=True)
class NormalizerConfig:
    """Immutable configuration for TextNormalizer."""

    locale: str = "en-US"
    style: Literal["conversational", "verbatim"] = "conversational"

    # Custom plain-string overrides: tuple of (exact_string, replacement)
    custom_overrides: tuple[tuple[str, str], ...] = ()
    custom_overrides_case_sensitive: bool = True

    # Numbers & Accounting
    use_and_in_hundreds: bool | None = None
    spoken_leading_zeros: Literal["zero", "oh"] | None = None
    preserve_trailing_zeros: bool = True
    standalone_4digit_number_policy: Literal["year_preferred", "cardinal_preferred"] = "year_preferred"
    year_2000s_style: Literal["thousand", "oh"] = "thousand"
    count_nouns: tuple[str, ...] = DEFAULT_COUNT_NOUNS
    accounting_mode: bool = False

    # Currencies
    default_currency_for_dollar: str = "USD"
    currency_spoken_format: Literal["natural", "formal"] = "natural"

    # Dates & Times
    numeric_date_order: Literal["MDY", "DMY", "YMD"] | None = None
    warn_on_ambiguous_date: bool = True
    time_format_preference: Literal["12h", "24h"] = "12h"

    # Units
    expand_units_only_after_digits: bool = True

    # Identifiers & Phone Numbers
    read_toll_free_as_words: bool = False
    identifier_reading: Literal["words", "spelled"] = "words"

    # Text, Symbols & Emojis
    preserve_contractions: bool = True
    url_reading_style: Literal["conversational", "verbatim", "preserve"] = "conversational"
    email_reading_style: Literal["conversational", "verbatim", "preserve"] = "conversational"
    word_slash_style: Literal["spoken", "slash"] = "spoken"
    pound_key_word: Literal["pound", "hash"] | None = None
    emoji_policy: Literal["drop", "verbalize", "pause", "preserve"] = "drop"
    non_speech_policy: Literal["drop", "keep", "pause"] = "drop"
    code_block_policy: Literal["drop", "keep"] = "drop"

    # Unresolved Handling & SSML
    unresolved_policy: Literal["literal", "preserve"] = "literal"
    ssml_mode: bool = False

    # Safety Limits
    max_input_length: int = 100_000
    max_expansion_ratio: float = 20.0

    def __post_init__(self) -> None:
        if self.locale not in SUPPORTED_LOCALES:
            raise ValueError(
                f"Unsupported locale: '{self.locale}'. Supported locales: {sorted(SUPPORTED_LOCALES)}"
            )
        if self.default_currency_for_dollar not in SUPPORTED_CURRENCY_CODES:
            raise ValueError(
                f"Invalid currency code for dollar: '{self.default_currency_for_dollar}'. "
                f"Supported codes: {sorted(SUPPORTED_CURRENCY_CODES)}"
            )
        if self.max_input_length <= 0:
            raise ValueError(f"max_input_length must be positive, got {self.max_input_length}")
        if self.max_expansion_ratio <= 1.0:
            raise ValueError(f"max_expansion_ratio must be > 1.0, got {self.max_expansion_ratio}")
        if self.year_2000s_style not in ("thousand", "oh"):
            raise ValueError(
                f"Invalid year_2000s_style: '{self.year_2000s_style}'. Must be 'thousand' or 'oh'."
            )
        if self.spoken_leading_zeros is not None and self.spoken_leading_zeros not in ("zero", "oh"):
            raise ValueError(
                f"Invalid spoken_leading_zeros: '{self.spoken_leading_zeros}'. Must be 'zero' or 'oh'."
            )
        if self.identifier_reading not in ("words", "spelled"):
            raise ValueError(
                f"Invalid identifier_reading: '{self.identifier_reading}'. Must be 'words' or 'spelled'."
            )
        if self.word_slash_style not in ("spoken", "slash"):
            raise ValueError(
                f"Invalid word_slash_style: '{self.word_slash_style}'. Must be 'spoken' or 'slash'."
            )
        if self.code_block_policy not in ("drop", "keep"):
            raise ValueError(
                f"Invalid code_block_policy: '{self.code_block_policy}'. Must be 'drop' or 'keep'."
            )
        if self.non_speech_policy not in ("drop", "keep", "pause"):
            raise ValueError(
                f"Invalid non_speech_policy: '{self.non_speech_policy}'. Must be 'drop', 'keep', or 'pause'."
            )
        if self.pound_key_word is not None and self.pound_key_word not in ("pound", "hash"):
            raise ValueError(
                f"Invalid pound_key_word: '{self.pound_key_word}'. Must be 'pound' or 'hash'."
            )
        if self.emoji_policy not in ("drop", "verbalize", "pause", "preserve"):
            raise ValueError(
                f"Invalid emoji_policy: '{self.emoji_policy}'. Must be 'drop', 'verbalize', 'pause', or 'preserve'."
            )

    def resolve(self) -> NormalizerConfig:
        """Resolves None defaults based on locale, returning an explicit resolved config."""
        use_and = self.use_and_in_hundreds
        if use_and is None:
            use_and = True if self.locale in ("en-GB", "en-IN") else False

        date_order = self.numeric_date_order
        if date_order is None:
            date_order = "DMY" if self.locale in ("en-GB", "en-IN") else "MDY"

        zeros = self.spoken_leading_zeros
        if zeros is None:
            zeros = "zero" if self.locale == "en-IN" else "oh"

        pound = self.pound_key_word
        if pound is None:
            pound = "hash" if self.locale in ("en-GB", "en-IN") else "pound"

        return replace(
            self,
            use_and_in_hundreds=use_and,
            numeric_date_order=date_order,
            spoken_leading_zeros=zeros,
            pound_key_word=pound,
        )

    def content_hash(self) -> str:
        """Deterministic sha256 content hash of all resolved config fields and lexicon version."""
        resolved = self.resolve()
        data_dict = asdict(resolved)
        data_dict["lexicon_version"] = LEXICON_VERSION
        serialized = json.dumps(data_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:8]

    @classmethod
    def for_locale(
        cls,
        locale: str,
        style: Literal["conversational", "verbatim"] = "conversational",
        **kwargs,
    ) -> NormalizerConfig:
        """Convenience constructor that validates locale and sets locale defaults."""
        if locale not in SUPPORTED_LOCALES:
            raise ValueError(
                f"Unsupported locale: '{locale}'. Supported locales: {sorted(SUPPORTED_LOCALES)}"
            )
        if "non_speech_sound_policy" in kwargs and "non_speech_policy" not in kwargs:
            kwargs["non_speech_policy"] = kwargs.pop("non_speech_sound_policy")
        use_and = kwargs.pop("use_and_in_hundreds", True if locale in ("en-GB", "en-IN") else False)
        date_order = kwargs.pop("numeric_date_order", "DMY" if locale in ("en-GB", "en-IN") else "MDY")
        zeros = kwargs.pop("spoken_leading_zeros", "zero" if locale == "en-IN" else "oh")
        pound = kwargs.pop("pound_key_word", "hash" if locale in ("en-GB", "en-IN") else "pound")
        return cls(
            locale=locale,
            style=style,
            use_and_in_hundreds=use_and,
            numeric_date_order=date_order,
            spoken_leading_zeros=zeros,
            pound_key_word=pound,
            **kwargs,
        )
