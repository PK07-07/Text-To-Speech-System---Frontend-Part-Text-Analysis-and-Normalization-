"""Currency verbalization rules and candidate detection for text_frontend.

Supports:
- Major symbols: USD ($), GBP (£), EUR (€), INR (₹), JPY (¥)
- ISO codes: USD, GBP, EUR, INR, JPY, CAD, AUD, CHF, CNY, NZD, SGD
- Natural spoken forms ("twenty-five dollars and fifty cents")
- Negative currencies and parenthesized accounting formats: ($500) -> negative five hundred dollars
- Financial magnitudes: $5K -> five thousand dollars, $10M -> ten million dollars
- Indian numbering system: ₹1,00,00,000 -> one crore rupees, ₹1,00,000 -> one lakh rupees
"""

from __future__ import annotations

import re
from typing import NamedTuple

from text_frontend.config import NormalizerConfig
from text_frontend.number_rules import (
    CandidateSpan,
    VALID_INDIAN_GROUPING_REGEX,
    VALID_WESTERN_GROUPING_REGEX,
    verbalize_cardinal,
    verbalize_digits,
    verbalize_indian_cardinal,
    verbalize_malformed_number,
)
from text_frontend.unit_rules import is_attributive_context
from text_frontend.validation import NormalizationWarning


class CurrencyMeta(NamedTuple):
    code: str
    major_singular: str
    major_plural: str
    minor_singular: str
    minor_plural: str
    has_minor: bool = True


CURRENCY_MAP: dict[str, CurrencyMeta] = {
    "USD": CurrencyMeta("USD", "dollar", "dollars", "cent", "cents"),
    "GBP": CurrencyMeta("GBP", "pound", "pounds", "penny", "pence"),
    "EUR": CurrencyMeta("EUR", "euro", "euros", "cent", "cents"),
    "INR": CurrencyMeta("INR", "rupee", "rupees", "paisa", "paise"),
    "JPY": CurrencyMeta("JPY", "yen", "yen", "", "", has_minor=False),
    "CAD": CurrencyMeta("CAD", "Canadian dollar", "Canadian dollars", "cent", "cents"),
    "AUD": CurrencyMeta("AUD", "Australian dollar", "Australian dollars", "cent", "cents"),
    "CHF": CurrencyMeta("CHF", "Swiss franc", "Swiss francs", "rappen", "rappen"),
    "CNY": CurrencyMeta("CNY", "Chinese yuan", "Chinese yuan", "fen", "fen"),
    "NZD": CurrencyMeta("NZD", "New Zealand dollar", "New Zealand dollars", "cent", "cents"),
    "SGD": CurrencyMeta("SGD", "Singapore dollar", "Singapore dollars", "cent", "cents"),
}

SYMBOL_TO_CODE: dict[str, str] = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "₹": "INR",
    "¥": "JPY",
}

# Magnitude multipliers
MAGNITUDES: dict[str, str] = {
    "K": "thousand",
    "k": "thousand",
    "M": "million",
    "m": "million",
    "B": "billion",
    "b": "billion",
}

# Currency pattern with symbols: $25, $25.50, -$25, ($25), $5K, €10M, ₹1,00,000, ₹500/-
CURRENCY_SYMBOL_REGEX = re.compile(
    r"(?<!\w)(?:\(([-−]?)([$£€₹¥])\s*(\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)(?:/-)?\)|([-−]?)([$£€₹¥])\s*(\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)(?:/-)?)(?!\w)"
)

# Currency pattern with Indian Rs: Rs. 1,50,000, Rs 500/-, -Rs. 500, (Rs. 500)
CURRENCY_RS_REGEX = re.compile(
    r"(?<!\w)(?:\(([-−]?)(?:Rs\.?|INR)\s*([-−]?\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)(?:/-)?\)|([-−]?)(?:Rs\.?|INR)\s*([-−]?\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)(?:/-)?)(?!\w)"
)

# Currency pattern with ISO codes: USD 50, 50 USD, EUR 10.50
ISO_CODES = "|".join(CURRENCY_MAP.keys())
CURRENCY_ISO_PREFIX_REGEX = re.compile(
    rf"(?<!\w)([-−]?)({ISO_CODES})\s*([-−]?\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)(?!\w)"
)
CURRENCY_ISO_SUFFIX_REGEX = re.compile(
    rf"(?<!\w)([-−]?\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)\s*({ISO_CODES})(?!\w)"
)

# Currency range pattern: $5-$10, £5-£10, €10 to €20, $1,000-$2,000
CURRENCY_RANGE_REGEX = re.compile(
    r"(?<!\w)([$£€₹¥])\s*(\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)\s*(?:[-–—]|\bto\b)\s*\1\s*(\d+(?:[,.\u2009\u202f\u00a0]\d+)*\s*[KkMmBb]?)(?!\w)"
)


def find_currency_candidates(
    text: str,
    config: NormalizerConfig,
) -> list[CandidateSpan]:
    """Detects candidate currency expressions in text."""
    candidates: list[CandidateSpan] = []

    # 0. Currency Ranges (Priority Rank 6: Composite numeric)
    for m in CURRENCY_RANGE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="currency",
                rule_id="curr.range",
                priority=6,
                verbalizer=verbalize_currency_range_span,
            )
        )

    # 1. Symbol Currencies (Priority Rank 6: Composite numeric)
    for m in CURRENCY_SYMBOL_REGEX.finditer(text):
        is_attr = is_attributive_context(text, m.start(), m.end())
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="currency",
                rule_id="curr.symbol",
                priority=6,
                verbalizer=lambda raw, cfg, attr=is_attr: verbalize_currency_symbol_span(
                    raw, cfg, is_attributive=attr
                ),
            )
        )

    # 1b. Indian Rs / INR Currencies: Rs. 1,50,000, Rs 500/- (Priority Rank 6)
    for m in CURRENCY_RS_REGEX.finditer(text):
        is_attr = is_attributive_context(text, m.start(), m.end())
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="currency",
                rule_id="curr.rs",
                priority=6,
                verbalizer=lambda raw, cfg, attr=is_attr: verbalize_currency_rs_span(
                    raw, cfg, is_attributive=attr
                ),
            )
        )

    # 2. ISO Prefix Currencies (Priority Rank 6)
    for m in CURRENCY_ISO_PREFIX_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="currency",
                rule_id="curr.iso_prefix",
                priority=6,
                verbalizer=verbalize_currency_iso_prefix_span,
            )
        )

    # 3. ISO Suffix Currencies (Priority Rank 6)
    for m in CURRENCY_ISO_SUFFIX_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="currency",
                rule_id="curr.iso_suffix",
                priority=6,
                verbalizer=verbalize_currency_iso_suffix_span,
            )
        )

    return candidates


def verbalize_currency_amount(
    amount_str: str,
    currency_code: str,
    is_negative: bool,
    config: NormalizerConfig,
    raw_span: str = "",
    is_attributive: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Core verbalizer for a parsed numeric currency amount and currency code."""
    meta = CURRENCY_MAP.get(currency_code, CURRENCY_MAP["USD"])
    prefix = "negative " if is_negative else ""
    use_and = config.use_and_in_hundreds or False
    clean_amount = amount_str.strip()

    # Check for magnitude suffix (K, M, B)
    last_char = clean_amount[-1] if clean_amount else ""
    if last_char in MAGNITUDES:
        mag_word = MAGNITUDES[last_char]
        num_str = clean_amount[:-1].strip().replace("−", "-")
        if "." in num_str:
            int_p, dec_p = num_str.split(".", 1)
            int_v = int(int_p) if int_p else 0
            int_w = verbalize_cardinal(int_v, use_and=use_and)
            dec_w = verbalize_digits(dec_p, zero_word="zero")
            spoken_num = f"{int_w} point {dec_w} {mag_word}"
        else:
            int_v = int(num_str)
            spoken_num = f"{verbalize_cardinal(int_v, use_and=use_and)} {mag_word}"

        curr_unit = meta.major_singular if is_attributive else meta.major_plural
        return f"{prefix}{spoken_num} {curr_unit}", [], False

    # Validate numeric grouping if commas exist
    if "," in clean_amount:
        is_western = bool(VALID_WESTERN_GROUPING_REGEX.match(clean_amount))
        is_indian = bool(VALID_INDIAN_GROUPING_REGEX.match(clean_amount))
        if config.locale == "en-IN":
            valid = is_western or is_indian
        else:
            valid = is_western

        if not valid:
            warning = NormalizationWarning(
                code="MALFORMED_NUMBER",
                message="Malformed currency numeric grouping encountered.",
                severity="warning",
                original_span=(0, len(raw_span or amount_str)),
            )
            if config.unresolved_policy == "preserve":
                return raw_span or amount_str, [warning], True
            else:
                spoken_digits, _, _ = verbalize_malformed_number(clean_amount, config)
                return f"{prefix}{meta.major_singular} {spoken_digits}", [warning], True

    raw_number = clean_amount.replace("−", "-")
    # Check if Indian numbering scale should be used
    is_indian = (config.locale == "en-IN" or currency_code == "INR") and bool(
        VALID_INDIAN_GROUPING_REGEX.match(raw_number)
    )

    # Standardize string: remove grouping commas and spaces
    normalized_num = re.sub(r"[, \u2009\u202f\u00a0]", "", raw_number)

    # Major and minor split
    if "." in normalized_num:
        parts = normalized_num.split(".", 1)
        major_val = int(parts[0]) if parts[0] else 0
        minor_str = parts[1]

        if len(minor_str) == 1:
            minor_val = int(minor_str) * 10
        elif len(minor_str) == 2:
            minor_val = int(minor_str)
        else:
            # More than 2 decimal places: verbalize as point digits
            dec_spoken = verbalize_digits(minor_str, zero_word="zero")
            major_spoken = (
                verbalize_indian_cardinal(major_val, use_and)
                if is_indian
                else verbalize_cardinal(major_val, use_and)
            )
            unit_name = meta.major_singular if major_val == 1 else meta.major_plural
            return f"{prefix}{major_spoken} point {dec_spoken} {unit_name}", [], False

        major_spoken = (
            verbalize_indian_cardinal(major_val, use_and)
            if is_indian
            else verbalize_cardinal(major_val, use_and)
        )
        major_unit = meta.major_singular if major_val == 1 else meta.major_plural

        minor_spoken = verbalize_cardinal(minor_val, use_and)
        minor_unit = meta.minor_singular if minor_val == 1 else meta.minor_plural

        if major_val == 0 and minor_val > 0:
            return f"{prefix}{minor_spoken} {minor_unit}", [], False
        elif minor_val == 0:
            return f"{prefix}{major_spoken} {major_unit}", [], False
        else:
            return f"{prefix}{major_spoken} {major_unit} and {minor_spoken} {minor_unit}", [], False
    else:
        # Integer currency amount
        major_val = int(normalized_num)
        major_spoken = (
            verbalize_indian_cardinal(major_val, use_and)
            if is_indian
            else verbalize_cardinal(major_val, use_and)
        )
        major_unit = meta.major_singular if (major_val == 1 or is_attributive) else meta.major_plural
        return f"{prefix}{major_spoken} {major_unit}", [], False


def verbalize_currency_symbol_span(
    raw_span: str,
    config: NormalizerConfig,
    is_attributive: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    clean = raw_span.strip()
    is_paren_negative = clean.startswith("(") and clean.endswith(")")
    if is_paren_negative:
        clean = clean[1:-1].strip()

    is_neg = is_paren_negative or clean.startswith("-") or clean.startswith("−")
    clean = clean.lstrip("-−").strip()

    symbol = clean[0]
    amount = clean[1:].strip().removesuffix("/-").strip()

    if symbol == "$":
        code = config.default_currency_for_dollar
    else:
        code = SYMBOL_TO_CODE.get(symbol, "USD")

    return verbalize_currency_amount(amount, code, is_neg, config, raw_span=raw_span, is_attributive=is_attributive)


def verbalize_currency_rs_span(
    raw_span: str,
    config: NormalizerConfig,
    is_attributive: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = CURRENCY_RS_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    is_paren = raw_span.strip().startswith("(") and raw_span.strip().endswith(")")
    if is_paren:
        neg = m.group(1)
        amount_str = m.group(2)
    else:
        neg = m.group(3)
        amount_str = m.group(4)

    amount_str = (amount_str or "").strip().removesuffix("/-").strip().replace("−", "-")
    is_neg = bool(neg) or amount_str.startswith("-") or (is_paren and config.accounting_parentheses)
    if amount_str.startswith("-"):
        amount_str = amount_str[1:].strip()
    return verbalize_currency_amount(
        amount_str, "INR", is_neg, config, raw_span=raw_span, is_attributive=is_attributive
    )


def verbalize_currency_iso_prefix_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = CURRENCY_ISO_PREFIX_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    neg = m.group(1)
    code = m.group(2).upper()
    amount_str = m.group(3).strip().replace("−", "-")
    is_neg = bool(neg) or amount_str.startswith("-")
    if amount_str.startswith("-"):
        amount_str = amount_str[1:].strip()
    return verbalize_currency_amount(amount_str, code, is_neg, config, raw_span=raw_span)


def verbalize_currency_iso_suffix_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = CURRENCY_ISO_SUFFIX_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    amount_str = m.group(1).strip().replace("−", "-")
    code = m.group(2).upper()
    is_neg = amount_str.startswith("-")
    if is_neg:
        amount_str = amount_str[1:].strip()
    return verbalize_currency_amount(amount_str, code, is_neg, config, raw_span=raw_span)


def verbalize_currency_range_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes currency ranges: $5-$10 -> five to ten dollars."""
    m = CURRENCY_RANGE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    symbol = m.group(1)
    amt1_str = m.group(2).strip()
    amt2_str = m.group(3).strip()

    if symbol == "$":
        code = config.default_currency_for_dollar
    else:
        code = SYMBOL_TO_CODE.get(symbol, "USD")

    meta = CURRENCY_MAP.get(code, CURRENCY_MAP["USD"])
    use_and = config.use_and_in_hundreds or False

    # Check if both are plain integers without magnitude or decimals
    has_decimal = "." in amt1_str or "." in amt2_str
    has_mag = (amt1_str and amt1_str[-1].upper() in MAGNITUDES) or (amt2_str and amt2_str[-1].upper() in MAGNITUDES)

    if not has_decimal and not has_mag:
        clean1 = re.sub(r"[, \u2009\u202f\u00a0]", "", amt1_str)
        clean2 = re.sub(r"[, \u2009\u202f\u00a0]", "", amt2_str)
        val1 = int(clean1)
        val2 = int(clean2)
        c1 = verbalize_cardinal(val1, use_and=use_and)
        c2 = verbalize_cardinal(val2, use_and=use_and)
        unit = meta.major_singular if val2 == 1 else meta.major_plural
        return f"{c1} to {c2} {unit}", [], False

    if has_mag and not has_decimal:
        def _speak_mag(amt: str) -> str:
            mag_char = amt[-1].upper()
            mag_w = MAGNITUDES[mag_char]
            n_str = amt[:-1]
            n_val = int(n_str)
            return f"{verbalize_cardinal(n_val, use_and=use_and)} {mag_w}"

        s1_mag = _speak_mag(amt1_str) if amt1_str[-1].upper() in MAGNITUDES else verbalize_cardinal(int(amt1_str), use_and=use_and)
        s2_mag = _speak_mag(amt2_str) if amt2_str[-1].upper() in MAGNITUDES else verbalize_cardinal(int(amt2_str), use_and=use_and)
        return f"{s1_mag} to {s2_mag} {meta.major_plural}", [], False

    # If decimals or magnitudes present, verbalize each amount
    s1, w1, a1 = verbalize_currency_amount(amt1_str, code, False, config, raw_span=amt1_str)
    s2, w2, a2 = verbalize_currency_amount(amt2_str, code, False, config, raw_span=amt2_str)
    return f"{s1} to {s2}", w1 + w2, a1 or a2




