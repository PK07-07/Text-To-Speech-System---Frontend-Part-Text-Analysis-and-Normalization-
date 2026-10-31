"""Number verbalization rules and candidate span detection for text_frontend.

Supports:
- Cardinals (-10^33 to +10^33) with pure Python standard library verbalizer
- Thin-space grouping (U+2009, U+202F, U+00A0) and comma grouping
- Ordinals (1st, 2nd, 23rd, 100th, etc.)
- Decimals with trailing zero preservation ("3.50" -> "three point five zero")
- Percentages ("25%" -> "twenty-five percent")
- Years ("1984" -> "nineteen eighty-four", "2026" -> "twenty twenty-six")
- Parenthesized negatives with percentages or in accounting mode
- Literal fallback verbalizer for malformed numeric expressions
"""

from __future__ import annotations

import re
from typing import Callable, NamedTuple

from text_frontend.config import NormalizerConfig
from text_frontend.validation import NormalizationWarning

# Number words vocabulary
ONES: tuple[str, ...] = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)

TENS: tuple[str, ...] = (
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
)

SCALE_WORDS: tuple[str, ...] = (
    "",
    "thousand",
    "million",
    "billion",
    "trillion",
    "quadrillion",
    "quintillion",
    "sextillion",
    "septillion",
    "octillion",
    "nonillion",
    "decillion",
)

# Common ordinal exceptions
ORDINAL_ONES: dict[int, str] = {
    0: "zeroth",
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
    11: "eleventh",
    12: "twelfth",
    13: "thirteenth",
    14: "fourteenth",
    15: "fifteenth",
    16: "sixteenth",
    17: "seventeenth",
    18: "eighteenth",
    19: "nineteenth",
}

ORDINAL_TENS: dict[int, str] = {
    20: "twentieth",
    30: "thirtieth",
    40: "fortieth",
    50: "fiftieth",
    60: "sixtieth",
    70: "seventieth",
    80: "eightieth",
    90: "ninetieth",
}

DECADE_NAMES: dict[int, str] = {
    20: "twenties",
    30: "thirties",
    40: "forties",
    50: "fifties",
    60: "sixties",
    70: "seventies",
    80: "eighties",
    90: "nineties",
}

# Context heuristics word lists for 4-digit numbers (1100-2099)
TEMPORAL_CUE_WORDS: frozenset[str] = frozenset({
    "in", "since", "by", "until", "during", "circa", "from", "before", "after", "year",
})
SEASONS_AND_MONTHS: frozenset[str] = frozenset({
    "spring", "summer", "autumn", "fall", "winter",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "year",
})
QUANTITY_CUES_SINGLE: frozenset[str] = frozenset({
    "about", "over", "around", "roughly", "only", "exactly", "approximately", "nearly", "almost",
})
YEAR_SUFFIXES: frozenset[str] = frozenset({
    "bc", "ad", "ce", "bce", "b.c.", "a.d.", "c.e.", "b.c.e.",
})


def verbalize_triplet(n: int, use_and: bool = False) -> str:
    """Verbalizes an integer between 0 and 999."""
    if n == 0:
        return ""
    parts: list[str] = []
    hundreds = n // 100
    rem = n % 100

    if hundreds > 0:
        parts.append(f"{ONES[hundreds]} hundred")
        if rem > 0 and use_and:
            parts.append("and")

    if rem > 0:
        if rem < 20:
            parts.append(ONES[rem])
        else:
            ten = rem // 10
            unit = rem % 10
            if unit > 0:
                parts.append(f"{TENS[ten]}-{ONES[unit]}")
            else:
                parts.append(TENS[ten])

    return " ".join(parts)


def verbalize_cardinal(n: int, use_and: bool = False) -> str:
    """Verbalizes any integer from -10^33 to +10^33."""
    if n == 0:
        return "zero"

    prefix = ""
    if n < 0:
        prefix = "negative "
        n = abs(n)

    if n >= 10**36:
        # Exceeds standard decillion scale table -> spell digit by digit
        return prefix + " ".join(ONES[int(d)] for d in str(n))

    # Split into 3-digit groups from right to left
    groups: list[int] = []
    temp = n
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    parts: list[str] = []
    num_groups = len(groups)
    for idx in range(num_groups - 1, -1, -1):
        grp_val = groups[idx]
        if grp_val == 0:
            continue
        scale_name = SCALE_WORDS[idx]
        grp_str = verbalize_triplet(grp_val, use_and=use_and)
        if scale_name:
            parts.append(f"{grp_str} {scale_name}")
        else:
            if idx == 0 and num_groups > 1 and grp_val < 100 and use_and:
                parts.append(f"and {grp_str}")
            else:
                parts.append(grp_str)

    return prefix + " ".join(parts)


def verbalize_indian_cardinal(n: int, use_and: bool = False) -> str:
    """Verbalizes an integer using Indian numbering scale (lakh, crore)."""
    if n == 0:
        return "zero"
    if n < 0:
        return f"negative {verbalize_indian_cardinal(abs(n), use_and)}"
    if n < 1000:
        return verbalize_cardinal(n, use_and)

    parts: list[str] = []
    # Crores: >= 10^7
    if n >= 10_000_000:
        crores = n // 10_000_000
        n %= 10_000_000
        parts.append(f"{verbalize_indian_cardinal(crores, use_and)} crore")
    # Lakhs: >= 10^5
    if n >= 100_000:
        lakhs = n // 100_000
        n %= 100_000
        parts.append(f"{verbalize_cardinal(lakhs, use_and)} lakh")
    # Thousands: >= 10^3
    if n >= 1_000:
        thousands = n // 1_000
        n %= 1_000
        parts.append(f"{verbalize_cardinal(thousands, use_and)} thousand")
    # Remaining hundreds / tens / units
    if n > 0:
        parts.append(verbalize_cardinal(n, use_and))

    return " ".join(parts)


def verbalize_ordinal(n: int, use_and: bool = False) -> str:
    """Verbalizes ordinal numbers like 1st -> first, 23rd -> twenty-third."""
    if n < 0:
        return "negative " + verbalize_ordinal(abs(n), use_and)

    if n < 20:
        return ORDINAL_ONES[n]
    if n < 100 and n % 10 == 0:
        return ORDINAL_TENS[n]

    rem = n % 100
    if 0 < rem < 20:
        base = n - rem
        base_cardinal = verbalize_cardinal(base, use_and=use_and)
        return f"{base_cardinal} and {ORDINAL_ONES[rem]}" if use_and else f"{base_cardinal} {ORDINAL_ONES[rem]}"
    elif rem >= 20 and rem % 10 != 0:
        base = n - (rem % 10)
        base_cardinal = verbalize_cardinal(base, use_and=use_and)
        return f"{base_cardinal}-{ORDINAL_ONES[rem % 10]}"
    else:
        card = verbalize_cardinal(n, use_and=use_and)
        if card.endswith("y"):
            return card[:-1] + "ieth"
        return card + "th"


def verbalize_digits(digit_str: str, zero_word: str = "zero") -> str:
    """Verbalizes a sequence of digits one-by-one."""
    words = []
    for d in digit_str:
        if d == "0":
            words.append(zero_word)
        elif d.isdigit():
            words.append(ONES[int(d)])
        else:
            words.append(d)
    return " ".join(words)


def verbalize_year(year: int, year_2000s_style: str = "thousand") -> str:
    """Verbalizes 4-digit years naturally (e.g. 1984 -> nineteen eighty-four, 2026 -> twenty twenty-six).

    Args:
        year: The year integer.
        year_2000s_style: "thousand" or "oh" for years 2001-2009.
            "thousand": 2001 -> "two thousand one"
            "oh": 2001 -> "twenty oh one"
            2010+ is always "twenty ten", "twenty eleven", etc.
    """
    if year < 0:
        return f"{verbalize_year(abs(year), year_2000s_style)} B C"

    if 1000 <= year <= 2099:
        century = year // 100
        decade = year % 100

        if century == 20:
            if decade == 0:
                return "two thousand"
            if decade < 10:
                if year_2000s_style == "thousand":
                    return f"two thousand {ONES[decade]}"
                else:
                    return f"twenty oh {ONES[decade]}"
            return f"twenty {verbalize_cardinal(decade)}"

        # 1100 - 1999
        century_words = verbalize_cardinal(century)
        if decade == 0:
            return f"{century_words} hundred"
        if decade < 10:
            return f"{century_words} oh {ONES[decade]}"
        return f"{century_words} {verbalize_cardinal(decade)}"

    # Outside standard 4-digit span, fallback to cardinal
    return verbalize_cardinal(year)


def verbalize_malformed_number(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Fallback verbalizer for malformed numeric expressions preserving all digits and separators."""
    warning = NormalizationWarning(
        code="MALFORMED_NUMBER",
        message="Malformed numeric expression encountered.",
        severity="warning",
        original_span=(0, len(raw_span)),
    )
    if config.unresolved_policy == "preserve":
        return raw_span, [warning], True

    # Literal fallback: keep every digit and separator
    # e.g. "1,00,000" -> "one comma zero zero comma zero zero zero"
    # "12..34" -> "twelve dot dot thirty-four"
    tokens = re.split(r"([,.\s\u2009\u202f\u00a0]+)", raw_span.strip())
    parts: list[str] = []
    for t in tokens:
        if not t:
            continue
        if t.startswith("-") or t.startswith("−"):
            parts.append("negative")
            t = t[1:]
            if not t:
                continue
        if t == ",":
            parts.append("comma")
        elif "," in t:
            parts.extend(["comma"] * t.count(","))
        elif "." in t:
            parts.extend(["dot"] * t.count("."))
        elif t.isdigit():
            if len(t) > 1 and t.startswith("0"):
                parts.append(verbalize_digits(t, zero_word="zero"))
            else:
                parts.append(verbalize_cardinal(int(t)))
        else:
            parts.append(t)

    return " ".join(parts), [warning], True


class CandidateSpan(NamedTuple):
    start: int
    end: int
    category: str
    rule_id: str
    priority: int
    verbalizer: Callable[[str, NormalizerConfig], tuple[str, list[NormalizationWarning], bool]]


# Regex Patterns for Phase 1 NSWs

# Comma-grouped numbers, optionally with decimal: matches any comma-separated digit sequence
GROUPED_INT_COMMA_REGEX = re.compile(
    r"(?<![\w/.])[-−]?\d+(?:,\d+)+(?:\.\d+)?(?!\w|\.\d|/\d)"
)
# Thin space, narrow no-break space, NBSP grouped numbers:
GROUPED_INT_SPACE_REGEX = re.compile(
    r"(?<![\w/.])[-−]?\d{1,3}(?:[\u2009\u202f\u00a0]\d{3})+(?:\.\d+)?(?!\w|\.\d|/\d)"
)

# Valid Western grouping: e.g. 1,000 or 1,000,000 or 1,000.50
VALID_WESTERN_GROUPING_REGEX = re.compile(r"^[-−]?\d{1,3}(,\d{3})*(\.\d+)?$")
# Valid Indian grouping: e.g. 1,00,000 or 1,00,00,000 or 1,00,000.50
VALID_INDIAN_GROUPING_REGEX = re.compile(r"^[-−]?\d{1,2}(,\d{2})*,\d{3}(\.\d+)?$")

# Standard bare integers: 123, -45 (prevents matching inside decimals or fractions while allowing trailing sentence punctuation)
BARE_INT_REGEX = re.compile(
    r"(?<![\w/.])[-−]?\d+(?!\w|\.\d|/\d)"
)

# Ordinals: 1st, 2nd, 3rd, 4th, 21st, 100th
ORDINAL_REGEX = re.compile(
    r"(?<!\w)(\d+)(st|nd|rd|th)\b", re.IGNORECASE
)

# Decimals: 3.14, 0.05, -0.001
DECIMAL_REGEX = re.compile(
    r"(?<![\w/.])[-−]?\d+\.\d+(?!\w|\.\d|/\d)"
)

# Percentages: 25%, -4.5%, (15%)
PERCENT_REGEX = re.compile(
    r"(?<![\w/.])(?:\([-−]?\d+(?:\.\d+)?%\)|[-−]?\d+(?:\.\d+)?%)(?!\w)"
)

# Decades: 1980s, '90s
DECADE_REGEX = re.compile(
    r"(?<!\w)(?:(\d{4})s|'(\d{2})s)\b"
)

# Century: 21st century
CENTURY_REGEX = re.compile(
    r"\b(\d+)(?:st|nd|rd|th)\s+century\b", re.IGNORECASE
)

# Malformed numbers with repeated dots: 12..34, 1.2.3
MALFORMED_NUM_REGEX = re.compile(
    r"(?<![\w/])\d+(?:\.\.+\d+|\.\d+\.\d+)+(?![\w/])"
)

# Parenthesized accounting numbers: (42)
ACCOUNTING_INT_REGEX = re.compile(
    r"(?<!\w)\((\d+)\)(?!\w)"
)

# Unicode fractions lookup
UNICODE_FRACTIONS: dict[str, tuple[int, int]] = {
    "½": (1, 2), "⅓": (1, 3), "⅔": (2, 3), "¼": (1, 4), "¾": (3, 4),
    "⅕": (1, 5), "⅖": (2, 5), "⅗": (3, 5), "⅘": (4, 5), "⅙": (1, 6),
    "⅚": (5, 6), "⅛": (1, 8), "⅜": (3, 8), "⅝": (5, 8), "⅞": (7, 8),
}
UNICODE_FRAC_CHARS = "".join(UNICODE_FRACTIONS.keys())

# Mixed fractions: 2 1/3 or 1 ½
MIXED_FRACTION_REGEX = re.compile(
    rf"(?<![\w/.])([-−]?\d+)\s+(\d+/\d+|[{UNICODE_FRAC_CHARS}])(?!\w|/\d)"
)

# Standard fractions: 1/2, 3/4, -1/2 (no spaces around slash; spaced slashes like Option 1 / 2 are preserved/verbalized as slash)
FRACTION_REGEX = re.compile(
    r"(?<![\w/.])([-−]?\d+)/(\d+)(?!\w|/\d|(?:\s*=))"
)

# Unicode standalone fractions: ½, ¾
UNICODE_FRACTION_REGEX = re.compile(
    rf"(?<![\w/.])([{UNICODE_FRAC_CHARS}])(?!\w)"
)

# Ratios: 3:1, 16:9
RATIO_REGEX = re.compile(
    r"(?<![\w/.])(\d+):(\d+)(?!\w|:\d)"
)

# Number ranges: 10-20, 1995-1999 (Priority Rank 6)
NUMBER_RANGE_REGEX = re.compile(
    r"(?<![\w/.])(\d{1,4})\s*[-–—]\s*(\d{1,4})(?!\w|\.\d|/\d|(?:\s*=))"
)

COMMON_FRACTION_DENOMINATORS = frozenset({2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 20, 32, 64, 100})

FRACTION_DENOMINATORS: dict[int, tuple[str, str]] = {
    2: ("half", "halves"),
    3: ("third", "thirds"),
    4: ("fourth", "fourths"),
    5: ("fifth", "fifths"),
    6: ("sixth", "sixths"),
    7: ("seventh", "sevenths"),
    8: ("eighth", "eighths"),
    9: ("ninth", "ninths"),
    10: ("tenth", "tenths"),
    12: ("twelfth", "twelfths"),
    16: ("sixteenth", "sixteenths"),
    20: ("twentieth", "twentieths"),
    32: ("thirty-second", "thirty-seconds"),
    64: ("sixty-fourth", "sixty-fourths"),
    100: ("hundredth", "hundredths"),
}


def verbalize_bp_number(n: int) -> str:
    """Pairs 3-digit blood pressure values (120 -> one twenty, 100 -> one hundred)."""
    if 100 <= n <= 999:
        hundred = n // 100
        rem = n % 100
        if rem == 0:
            return f"{ONES[hundred]} hundred"
        elif rem < 10:
            return f"{ONES[hundred]} oh {ONES[rem]}"
        elif rem < 20:
            return f"{ONES[hundred]} {ONES[rem]}"
        else:
            tens_str = TENS[rem // 10]
            ones_part = f"-{ONES[rem % 10]}" if rem % 10 != 0 else ""
            return f"{ONES[hundred]} {tens_str}{ones_part}"
    return verbalize_cardinal(n)


def _detect_4digit_context(
    text: str, start: int, end: int, count_nouns: tuple[str, ...]
) -> tuple[bool, bool, bool, bool]:
    """Returns (has_temporal_cue, has_year_suffix, has_quantity_cue, has_count_noun)."""
    # 1. Words before
    before_slice = text[:start].rstrip()
    tokens_before = re.findall(r"[A-Za-z]+|\.", before_slice)
    has_temporal_cue = False
    has_quantity_cue = False

    if tokens_before:
        last1 = tokens_before[-1].lower()
        if last1 in TEMPORAL_CUE_WORDS:
            has_temporal_cue = True
        elif last1 == "of" and len(tokens_before) >= 2:
            prev_token = tokens_before[-2].lower()
            if prev_token in SEASONS_AND_MONTHS:
                has_temporal_cue = True

        # Check multi-word quantity cues: "total of", "number of"
        if len(tokens_before) >= 2:
            last2 = f"{tokens_before[-2].lower()} {tokens_before[-1].lower()}"
            if last2 in ("total of", "number of"):
                has_quantity_cue = True

        if last1 in QUANTITY_CUES_SINGLE:
            has_quantity_cue = True

    # 2. Words after
    after_slice = text[end:].lstrip()
    tokens_after = re.findall(r"[A-Za-z]+|\.", after_slice)
    has_year_suffix = False
    has_count_noun = False

    if tokens_after:
        first1 = tokens_after[0].lower()
        # Also check dotted abbreviations like b.c.
        if len(tokens_after) >= 4 and tokens_after[1] == "." and tokens_after[3] == ".":
            dotted = f"{tokens_after[0].lower()}.{tokens_after[2].lower()}."
            if dotted in YEAR_SUFFIXES:
                has_year_suffix = True

        if first1 in YEAR_SUFFIXES:
            has_year_suffix = True
        if first1 in count_nouns:
            has_count_noun = True

    return has_temporal_cue, has_year_suffix, has_quantity_cue, has_count_noun


ARITHMETIC_CONTEXT_REGEX = re.compile(
    r"\b(what\s+is|calculate|solve|evaluate|compute|equals?|how\s+much\s+is)\b",
    re.IGNORECASE,
)


def is_arithmetic_context(text: str, start: int, end: int) -> bool:
    """Checks if expression has an '=' following it or is preceded by arithmetic cues."""
    # Check if '=' follows in the same expression/sentence
    after_text = text[end:]
    sentence_end = len(after_text)
    for p in (".\n", "\n", ";", ". "):
        pos = after_text.find(p)
        if pos != -1 and pos < sentence_end:
            sentence_end = pos
    clause_after = after_text[:sentence_end]
    if "=" in clause_after:
        return True

    # Check if arithmetic cue precedes the expression
    before_text = text[:start]
    sentence_start = 0
    for p in (".\n", "\n", ";", ". "):
        pos = before_text.rfind(p)
        if pos != -1 and pos + len(p) > sentence_start:
            sentence_start = pos + len(p)
    clause_before = before_text[sentence_start:]
    if ARITHMETIC_CONTEXT_REGEX.search(clause_before):
        return True

    return False


def find_number_candidates(
    text: str,
    config: NormalizerConfig,
) -> list[CandidateSpan]:
    """Scans text and returns candidate spans for numeric expressions."""
    candidates: list[CandidateSpan] = []

    # 1. Number ranges (Priority Rank 6: Composite numeric)
    for m in NUMBER_RANGE_REGEX.finditer(text):
        if is_arithmetic_context(text, m.start(), m.end()):
            continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="range",
                rule_id="num.range",
                priority=6,
                verbalizer=verbalize_number_range_span,
            )
        )

    # 2. Mixed fractions: 2 1/3, 1 ½ (Priority Rank 7)
    for m in MIXED_FRACTION_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="fraction",
                rule_id="num.fraction.mixed",
                priority=7,
                verbalizer=verbalize_mixed_fraction_span,
            )
        )

    # 3. Standard fractions, blood pressure, or slash pairs (Priority Rank 7, BP Rank 6)
    for m in FRACTION_REGEX.finditer(text):
        if is_arithmetic_context(text, m.start(), m.end()):
            continue
        num_v = int(m.group(1).replace("−", "-"))
        den_v = int(m.group(2))

        # Check blood pressure: followed by mmHg or preceded by "blood pressure" or "BP"
        after_text = text[m.end():].lstrip(" \t")
        before_text = text[:m.start()].lower()
        is_bp = (
            bool(re.match(r"^mm\s*Hg\b", after_text, re.IGNORECASE))
            or "blood pressure" in before_text[-40:]
            or bool(re.search(r"\bBP\b", text[:m.start()][-20:]))
        )

        if is_bp:
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="number",
                    rule_id="num.blood_pressure",
                    priority=6,
                    verbalizer=lambda raw, cfg, n1=num_v, n2=den_v: (
                        f"{verbalize_bp_number(n1)} over {verbalize_bp_number(n2)}",
                        [],
                        False,
                    ),
                )
            )
            continue

        # General slash pair: fraction ONLY when numerator < denominator and denominator in COMMON_FRACTION_DENOMINATORS
        is_common_fraction = (abs(num_v) < den_v and den_v in COMMON_FRACTION_DENOMINATORS)
        is_24_7 = (abs(num_v) == 24 and den_v == 7)

        if is_common_fraction or is_24_7:
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="fraction",
                    rule_id="num.fraction",
                    priority=7,
                    verbalizer=verbalize_fraction_span,
                )
            )
        else:
            # Reads "over" (if not claimed by date rules at priority 5)
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="number",
                    rule_id="num.slash_over",
                    priority=7,
                    verbalizer=lambda raw, cfg, n1=num_v, n2=den_v: (
                        f"{verbalize_cardinal(n1, use_and=cfg.use_and_in_hundreds or False)} over {verbalize_cardinal(n2, use_and=cfg.use_and_in_hundreds or False)}",
                        [],
                        False,
                    ),
                )
            )

    # 4. Unicode standalone fractions: ½, ¾ (Priority Rank 7)
    for m in UNICODE_FRACTION_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="fraction",
                rule_id="num.fraction.unicode",
                priority=7,
                verbalizer=verbalize_unicode_fraction_span,
            )
        )

    # 5. Ratios: 3:1, 16:9 (Priority Rank 7)
    for m in RATIO_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="ratio",
                rule_id="num.ratio",
                priority=7,
                verbalizer=verbalize_ratio_span,
            )
        )

    # 6. Percentages (Priority Rank 7)
    for m in PERCENT_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="percentage",
                rule_id="num.percentage",
                priority=7,
                verbalizer=verbalize_percent_span,
            )
        )

    # 2. Centuries (Priority Rank 7)
    for m in CENTURY_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="century",
                rule_id="num.century",
                priority=7,
                verbalizer=verbalize_century_span,
            )
        )

    # 3. Decades (Priority Rank 7)
    for m in DECADE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="decade",
                rule_id="num.decade",
                priority=7,
                verbalizer=verbalize_decade_span,
            )
        )

    # 4. Ordinals (Priority Rank 7)
    for m in ORDINAL_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="ordinal",
                rule_id="num.ordinal",
                priority=7,
                verbalizer=verbalize_ordinal_span,
            )
        )

    # 5. Decimals (Priority Rank 7)
    for m in DECIMAL_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="decimal",
                rule_id="num.decimal",
                priority=7,
                verbalizer=verbalize_decimal_span,
            )
        )

    # 6. Grouped integers with comma (Priority Rank 7)
    for m in GROUPED_INT_COMMA_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="cardinal",
                rule_id="num.cardinal.grouped_comma",
                priority=7,
                verbalizer=verbalize_grouped_int_span,
            )
        )

    # 7. Grouped integers with thin space / narrow no-break space / NBSP (Priority Rank 7)
    for m in GROUPED_INT_SPACE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="cardinal",
                rule_id="num.cardinal.grouped_space",
                priority=7,
                verbalizer=verbalize_grouped_int_span,
            )
        )

    # 8. Bare integers and potential years (Priority Rank 7)
    for m in BARE_INT_REGEX.finditer(text):
        raw_match = m.group(0)
        # Check for 4-digit standalone numbers 1100-2099 without minus sign
        if len(raw_match) == 4 and raw_match.isdigit() and 1100 <= int(raw_match) <= 2099:
            has_temporal_cue, has_year_suffix, has_quantity_cue, has_count_noun = (
                _detect_4digit_context(text, m.start(), m.end(), config.count_nouns)
            )
            has_temporal = has_temporal_cue or has_year_suffix
            val = int(raw_match)

            # Precedence 1: temporal cue before AND count noun after -> year + AMBIGUOUS_STANDALONE_YEAR info
            if has_temporal and has_count_noun:
                candidates.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="year",
                        rule_id="num.year.context_conflict",
                        priority=7,
                        verbalizer=lambda raw, cfg, v=val: (
                            verbalize_year(v, year_2000s_style=cfg.year_2000s_style),
                            [
                                NormalizationWarning(
                                    code="AMBIGUOUS_STANDALONE_YEAR",
                                    message="Standalone 4-digit number with conflicting cues verbalized as year by precedence.",
                                    severity="info",
                                    original_span=(0, len(raw)),
                                )
                            ],
                            True,
                        ),
                    )
                )
                continue

            # Precedence 2: quantity cue before, OR count noun after with no temporal cue -> cardinal, no warning
            elif has_quantity_cue or (has_count_noun and not has_temporal):
                candidates.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="cardinal",
                        rule_id="num.cardinal.context",
                        priority=7,
                        verbalizer=lambda raw, cfg, v=val: (
                            verbalize_cardinal(v, use_and=cfg.use_and_in_hundreds or False),
                            [],
                            False,
                        ),
                    )
                )
                continue

            # Precedence 3: temporal cue alone -> year, no warning
            elif has_temporal and not has_count_noun:
                candidates.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="year",
                        rule_id="num.year.context",
                        priority=7,
                        verbalizer=lambda raw, cfg, v=val: (
                            verbalize_year(v, year_2000s_style=cfg.year_2000s_style),
                            [],
                            False,
                        ),
                    )
                )
                continue

            # Precedence 4: no cue -> fall through to verbalize_bare_int_span below

        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="cardinal",
                rule_id="num.cardinal",
                priority=7,
                verbalizer=verbalize_bare_int_span,
            )
        )

    # 9. Malformed numbers with repeated dots (Priority Rank 7)
    for m in MALFORMED_NUM_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="cardinal",
                rule_id="num.malformed",
                priority=7,
                verbalizer=verbalize_malformed_span,
            )
        )

    # 10. Parenthesized accounting numbers: (42)
    if config.accounting_mode:
        for m in ACCOUNTING_INT_REGEX.finditer(text):
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="cardinal",
                    rule_id="num.accounting",
                    priority=7,
                    verbalizer=verbalize_accounting_span,
                )
            )

    return candidates


# Verbalizers for Candidate Spans

def verbalize_percent_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    clean = raw_span.strip()
    is_paren_negative = clean.startswith("(") and clean.endswith(")")
    if is_paren_negative:
        clean = clean[1:-1].strip()

    num_part = clean.rstrip("%").replace("−", "-").replace(",", "")
    is_neg = num_part.startswith("-") or is_paren_negative
    if num_part.startswith("-"):
        num_part = num_part[1:]

    prefix = "negative " if is_neg else ""
    if "." in num_part:
        int_p, dec_p = num_part.split(".", 1)
        int_val = int(int_p) if int_p else 0
        int_str = verbalize_cardinal(int_val, use_and=config.use_and_in_hundreds or False)
        dec_str = verbalize_digits(dec_p, zero_word="zero")
        return f"{prefix}{int_str} point {dec_str} percent", [], False
    else:
        int_val = int(num_part)
        int_str = verbalize_cardinal(int_val, use_and=config.use_and_in_hundreds or False)
        return f"{prefix}{int_str} percent", [], False


def verbalize_ordinal_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = re.match(r"^(\d+)(?:st|nd|rd|th)$", raw_span.strip(), re.IGNORECASE)
    if not m:
        return raw_span, [], False
    n = int(m.group(1))
    return verbalize_ordinal(n, use_and=config.use_and_in_hundreds or False), [], False


def verbalize_decimal_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    clean = raw_span.strip().replace("−", "-")
    is_neg = clean.startswith("-")
    if is_neg:
        clean = clean[1:]

    int_p, dec_p = clean.split(".", 1)
    int_val = int(int_p) if int_p else 0
    int_str = verbalize_cardinal(int_val, use_and=config.use_and_in_hundreds or False)
    dec_str = verbalize_digits(dec_p, zero_word="zero")

    prefix = "negative " if is_neg else ""
    return f"{prefix}{int_str} point {dec_str}", [], False


def verbalize_grouped_int_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    clean = raw_span.strip()
    is_neg = clean.startswith("-") or clean.startswith("−")
    prefix = "negative " if is_neg else ""
    unsigned = clean[1:] if is_neg else clean

    # Check if it's comma-grouped
    if "," in unsigned:
        is_western_valid = bool(VALID_WESTERN_GROUPING_REGEX.match(clean))
        is_indian_valid = bool(VALID_INDIAN_GROUPING_REGEX.match(clean))

        if config.locale == "en-IN":
            valid = is_western_valid or is_indian_valid
        else:
            valid = is_western_valid

        if not valid:
            return verbalize_malformed_number(raw_span, config)

        use_and = config.use_and_in_hundreds or False
        if "." in unsigned:
            int_p, dec_p = unsigned.split(".", 1)
            int_clean = int_p.replace(",", "")
            int_val = int(int_clean) if int_clean else 0
            if config.locale == "en-IN" and is_indian_valid:
                int_str = verbalize_indian_cardinal(int_val, use_and)
            else:
                int_str = verbalize_cardinal(int_val, use_and)
            dec_str = verbalize_digits(dec_p, zero_word="zero")
            return f"{prefix}{int_str} point {dec_str}", [], False
        else:
            int_clean = unsigned.replace(",", "")
            int_val = int(int_clean)
            if config.locale == "en-IN" and is_indian_valid:
                int_str = verbalize_indian_cardinal(int_val, use_and)
            else:
                int_str = verbalize_cardinal(int_val, use_and)
            return f"{prefix}{int_str}", [], False

    else:
        # Thin space, narrow no-break space, NBSP grouping
        clean_no_space = re.sub(r"[\u2009\u202f\u00a0]", "", unsigned)
        use_and = config.use_and_in_hundreds or False
        if "." in clean_no_space:
            int_p, dec_p = clean_no_space.split(".", 1)
            int_val = int(int_p) if int_p else 0
            int_str = verbalize_cardinal(int_val, use_and)
            dec_str = verbalize_digits(dec_p, zero_word="zero")
            return f"{prefix}{int_str} point {dec_str}", [], False
        else:
            int_val = int(clean_no_space)
            return f"{prefix}{verbalize_cardinal(int_val, use_and)}", [], False


def verbalize_bare_int_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    clean = raw_span.strip().replace("−", "-")
    is_neg = clean.startswith("-")
    digits = clean[1:] if is_neg else clean

    # Check for leading zeros: e.g. "007"
    if len(digits) > 1 and digits.startswith("0"):
        prefix = "negative " if is_neg else ""
        return prefix + verbalize_digits(digits, zero_word=config.spoken_leading_zeros), [], False

    val = int(clean)

    # 4-digit numbers 1100-2099 without minus sign: Year candidate check when no context applied
    if not is_neg and 1100 <= val <= 2099 and len(clean) == 4:
        if config.standalone_4digit_number_policy == "year_preferred":
            spoken_year = verbalize_year(val, year_2000s_style=config.year_2000s_style)
            warning = NormalizationWarning(
                code="AMBIGUOUS_STANDALONE_YEAR",
                message="Standalone 4-digit number verbalized as year by policy.",
                severity="info",
                original_span=(0, len(raw_span)),
            )
            return spoken_year, [warning], True
        else:
            spoken_card = verbalize_cardinal(val, use_and=config.use_and_in_hundreds or False)
            warning = NormalizationWarning(
                code="AMBIGUOUS_STANDALONE_YEAR",
                message="Standalone 4-digit number verbalized as cardinal by policy.",
                severity="info",
                original_span=(0, len(raw_span)),
            )
            return spoken_card, [warning], True

    # Check for numbers exceeding 10^33
    if abs(val) >= 10**36:
        warning = NormalizationWarning(
            code="NUMBER_OUT_OF_RANGE",
            message="Number exceeds decillion (10^33); verbalized digit-by-digit.",
            severity="warning",
            original_span=(0, len(raw_span)),
        )
        prefix = "negative " if is_neg else ""
        return prefix + verbalize_digits(digits, zero_word=config.spoken_leading_zeros), [warning], False

    return verbalize_cardinal(val, use_and=config.use_and_in_hundreds or False), [], False


def verbalize_decade_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    clean = raw_span.strip()
    if clean.startswith("'"):
        # e.g. '90s
        m_dec = re.match(r"^'(\d{2})s$", clean)
        if not m_dec:
            return raw_span, [], False
        decade_num = int(m_dec.group(1))
        decade_key = (decade_num // 10) * 10
        dec_word = DECADE_NAMES.get(decade_key, f"{clean}s")
        return dec_word, [], False
    else:
        # e.g. 1980s
        m_dec4 = re.match(r"^(\d{4})s$", clean)
        if not m_dec4:
            return raw_span, [], False
        year = int(m_dec4.group(1))
        century = year // 100
        decade = year % 100
        century_words = verbalize_cardinal(century)
        if decade == 0:
            return f"{century_words} hundreds", [], False
        decade_key = (decade // 10) * 10
        dec_word = DECADE_NAMES.get(decade_key, f"{decade}s")
        return f"{century_words} {dec_word}", [], False


def verbalize_century_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = re.match(r"^(\d+)(?:st|nd|rd|th)\s+century$", raw_span.strip(), re.IGNORECASE)
    if not m:
        return raw_span, [], False
    n = int(m.group(1))
    ord_str = verbalize_ordinal(n, use_and=config.use_and_in_hundreds or False)
    return f"{ord_str} century", [], False


def verbalize_accounting_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = re.match(r"^\((\d+)\)$", raw_span.strip())
    if not m:
        return raw_span, [], False
    val = int(m.group(1))
    return f"negative {verbalize_cardinal(val, use_and=config.use_and_in_hundreds or False)}", [], False


def verbalize_malformed_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    return verbalize_malformed_number(raw_span, config)


def verbalize_fraction(num: int, den: int, is_neg: bool = False, use_and: bool = False) -> str:
    """Verbalizes a fraction (num/den) with pluralized denominators."""
    prefix = "negative " if is_neg else ""
    num_val = abs(num)
    if num_val == 24 and den == 7:
        return f"{prefix}twenty-four seven"
    if den == 0:
        return f"{prefix}{verbalize_cardinal(num_val)} over zero"

    num_words = verbalize_cardinal(num_val, use_and=use_and)
    if den in FRACTION_DENOMINATORS:
        den_words = FRACTION_DENOMINATORS[den][0] if num_val == 1 else FRACTION_DENOMINATORS[den][1]
    else:
        den_ord = verbalize_ordinal(den, use_and=use_and)
        den_words = den_ord if num_val == 1 else f"{den_ord}s"

    return f"{prefix}{num_words} {den_words}"


def verbalize_fraction_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = FRACTION_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    num_str = m.group(1).replace("−", "-")
    is_neg = num_str.startswith("-")
    num = abs(int(num_str))
    den = int(m.group(2))
    use_and = config.use_and_in_hundreds or False
    return verbalize_fraction(num, den, is_neg=is_neg, use_and=use_and), [], False


def verbalize_mixed_fraction_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = MIXED_FRACTION_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    whole_str = m.group(1).replace("−", "-")
    frac_str = m.group(2)
    is_neg = whole_str.startswith("-")
    whole_val = abs(int(whole_str))
    use_and = config.use_and_in_hundreds or False
    whole_words = verbalize_cardinal(whole_val, use_and=use_and)
    prefix = "negative " if is_neg else ""

    if frac_str in UNICODE_FRACTIONS:
        num, den = UNICODE_FRACTIONS[frac_str]
        frac_words = verbalize_fraction(num, den, is_neg=False, use_and=use_and)
    else:
        num_p, den_p = frac_str.split("/", 1)
        frac_words = verbalize_fraction(int(num_p), int(den_p), is_neg=False, use_and=use_and)

    return f"{prefix}{whole_words} and {frac_words}", [], False


def verbalize_unicode_fraction_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    clean = raw_span.strip()
    if clean in UNICODE_FRACTIONS:
        num, den = UNICODE_FRACTIONS[clean]
        use_and = config.use_and_in_hundreds or False
        return verbalize_fraction(num, den, is_neg=False, use_and=use_and), [], False
    return raw_span, [], False


def verbalize_ratio_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = RATIO_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    left = int(m.group(1))
    right = int(m.group(2))
    use_and = config.use_and_in_hundreds or False
    return f"{verbalize_cardinal(left, use_and)} to {verbalize_cardinal(right, use_and)}", [], False


def verbalize_number_range_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    m = NUMBER_RANGE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    p1 = int(m.group(1))
    p2 = int(m.group(2))

    # Check if both endpoints are 4-digit years (1100-2099)
    if 1100 <= p1 <= 2099 and 1100 <= p2 <= 2099 and len(m.group(1)) == 4 and len(m.group(2)) == 4:
        y1_str = verbalize_year(p1, year_2000s_style=config.year_2000s_style)
        y2_str = verbalize_year(p2, year_2000s_style=config.year_2000s_style)
        return f"{y1_str} to {y2_str}", [], False

    # Otherwise cardinals
    use_and = config.use_and_in_hundreds or False
    c1_str = verbalize_cardinal(p1, use_and=use_and)
    c2_str = verbalize_cardinal(p2, use_and=use_and)
    return f"{c1_str} to {c2_str}", [], False
