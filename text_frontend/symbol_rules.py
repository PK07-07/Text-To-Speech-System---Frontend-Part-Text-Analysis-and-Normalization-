"""Symbol verbalization rules for text_frontend.

Supports:
- @: "at" (Tickets @ $10 -> Tickets at ten dollars, @username -> at username)
- &: "and" (Rock & Roll -> Rock and Roll, Ben & Jerry's -> Ben and Jerry's, AT&T -> AT and T)
- #:
  - Before digits: #1 -> number one, #100 -> number one hundred
  - Before words (hashtags): #trending -> hashtag trending
  - Standalone #: number
- _: "underscore" (standalone or isolated underscores)
- ~:
  - Before numbers or currency: ~5 -> approximately five, ~$10 -> approximately ten dollars
  - Otherwise: tilde
- /: "slash" when between standalone words (either/or -> either slash or)
- Common typography: © -> copyright, ® -> registered, ™ -> trademark
- Non-speech brackets: [laughter], (applause), [inaudible], etc.
- Emojis & Emoticons: customizable via emoji_policy
- Math operators: +, -, *, /, =, ≠, ≤, ≥, <, >, ± in numeric context
- Dimensions: 10x20, 1920x1080, 10x20x30
- Scientific notation: 3.0 x 10^8, 6.02 × 10²³, 1e-6, 2.5E10
- Powers & Exponents: 10^5, x^2, superscripts 5², x³
- Square root: √16 -> square root of sixteen
- Greek letters & constants: α, β, π, Ω, ∞
- Chemical formulas: H2O, CO2, NaCl, etc.
- Prose dashes: —, – outside numeric ranges
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from text_frontend.config import NormalizerConfig
from text_frontend.data_loader import load_abbreviations_data, load_emoji_data
from text_frontend.number_rules import (
    CandidateSpan,
    is_arithmetic_context,
    verbalize_cardinal,
    verbalize_digits,
)
from text_frontend.validation import NormalizationWarning

LEXICON_EXACT_PRIORITY: int = 3
COMPOSITE_NUMERIC_PRIORITY: int = 6
SPECIFIC_NUMERIC_PRIORITY: int = 7
SYMBOL_PRIORITY: int = 9

# Regex for # followed by digits: #1, #100
HASH_DIGITS_REGEX = re.compile(r"#(\d+)\b")

# Regex for # followed by words (hashtags): #trending, #TTS
HASHTAG_REGEX = re.compile(r"#([A-Za-z][A-Za-z0-9_]*)\b")

# Regex for ~ followed by digits: ~5, ~100
TILDE_DIGITS_REGEX = re.compile(r"~([-−]?\d+(?:\.\d+)?)\b")

# Regex for ~ before currency: ~$10, ~£5
TILDE_CURRENCY_REGEX = re.compile(r"~(?=[$£€₹¥])")

# Regex for slash between words: either/or, input/output, yes/no
SLASH_WORDS_REGEX = re.compile(r"(?<=[A-Za-z])/(?=[A-Za-z])")

# Regex for word/word slashes: and/or, TCP/IP, either/or
WORD_SLASH_PAIR_REGEX = re.compile(r"\b([A-Za-z]+)/([A-Za-z]+)\b")

# Regex for standalone slash abbreviations: N/A, w/o, w/, c/o
STANDALONE_SLASH_ABBR_REGEX = re.compile(r"\b(N/A|n/a|w/o|w/|c/o)\b")

# Lexicon of fixed readings for word/word and abbreviation slashes
WORD_SLASHES: dict[str, str] = {
    "and/or": "and or",
    "either/or": "either or",
    "yes/no": "yes or no",
    "he/she": "he or she",
    "his/her": "his or her",
    "n/a": "not applicable",
    "w/o": "without",
    "w/": "with",
    "c/o": "care of",
}

# Regex for slash between spaces: a / b
SLASH_SPACES_REGEX = re.compile(r"(?<=\s)/(?=\s)")

# Common typographical symbols
TYPO_SYMBOLS: dict[str, str] = {
    "©": "copyright",
    "®": "registered",
    "™": "trademark",
}

# Non-speech brackets: [laughter], (applause), [inaudible], [sigh], [cough], [pause]
NON_SPEECH_REGEX = re.compile(
    r"\[(laughter|applause|inaudible|sigh|cough|pause)\]|\((laughter|applause|sigh|cough|pause)\)",
    re.IGNORECASE,
)

# Dimensions: 10x20, 1920x1080, 10x20x30 (exclude hex prefixes like 0x1F, 0xFF00)
DIMENSION_3D_REGEX = re.compile(
    r"(?<![0-9a-fA-FxX])\b([1-9]\d*(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\b"
)
DIMENSION_2D_REGEX = re.compile(
    r"(?<![0-9a-fA-FxX])\b([1-9]\d*(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\b"
)

# Multiplier speed: 3x faster -> three times faster, 2x daily -> two times daily
MULTIPLIER_SPEED_REGEX = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*[xX]\s+(faster|more|greater|higher|larger|slower|less|increase|decrease|speed|boost|growth|fold|daily|weekly|monthly|yearly)\b",
    re.IGNORECASE,
)

# Scientific notation & Powers
SCI_NOTE_EXP_REGEX = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:[xX]|×)\s*10\^([-−]?\d+)\b")
SCI_NOTE_SUP_REGEX = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:[xX]|×)\s*10([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)\b")
SCI_NOTE_E_REGEX = re.compile(r"\b(\d+(?:\.\d+)?)[eE]([-+]?\d+)\b")
EXPONENT_POW_REGEX = re.compile(r"(?<=\d|[a-zA-Z])\^([-−]?\d+(?:\.\d+)?)\b")
SQRT_REGEX = re.compile(r"√\s*(\d+(?:\.\d+)?)\b")
SUPERSCRIPT_CHAR_REGEX = re.compile(r"(\d+|[a-zA-Z])([²³⁴⁵⁶⁷⁸⁹]+)\b")

SUPERSCRIPT_DIGITS: dict[str, str] = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁺": "+", "⁻": "-",
}

ORDINAL_POWERS: dict[int, str] = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
}

# Chemical formulas
CHEMICAL_FORMULA_REGEX = re.compile(r"\b(H2O|CO2|O2|NaCl|CH4|H2SO4|NH3|NO2|SO2)\b")
CHEMICAL_FORMULAS: dict[str, str] = {
    "H2O": "H two O",
    "CO2": "C O two",
    "O2": "O two",
    "NaCl": "N a C l",
    "CH4": "C H four",
    "H2SO4": "H two S O four",
    "NH3": "N H three",
    "NO2": "N O two",
    "SO2": "S O two",
}

# Greek letters & math constants
GREEK_LETTERS_REGEX = re.compile(r"(\d+)?([αβγδεθλμπστφωΩΔΣ∞])")
GREEK_LETTERS: dict[str, str] = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
    "θ": "theta", "λ": "lambda", "μ": "mu", "π": "pi", "σ": "sigma",
    "τ": "tau", "φ": "phi", "ω": "omega", "Ω": "omega", "Δ": "delta",
    "Σ": "sigma", "∞": "infinity",
}

# Math operators in numeric context
MATH_PLUS_REGEX = re.compile(r"(?<=\d)\s+\+\s+(?=\d)")
MATH_MINUS_REGEX = re.compile(r"(?<=\d)\s+[-−]\s+(?=\d)")
MATH_TIMES_REGEX = re.compile(r"(?<=\d)\s*[×\*]\s*(?=\d)")
MATH_DIV_REGEX = re.compile(r"(?<=\d)\s+[\/÷]\s+(?=\d)")
MATH_EQUALS_REGEX = re.compile(r"(?<=[A-Za-z0-9])\s*=\s*(?=[A-Za-z0-9])")
MATH_NEQ_REGEX = re.compile(r"(?<=[A-Za-z0-9])\s*≠\s*(?=[A-Za-z0-9])")
MATH_LTE_REGEX = re.compile(r"(?<=\d)\s*(?:<=|≤)\s*(?=\d)")
MATH_GTE_REGEX = re.compile(r"(?<=\d)\s*(?:>=|≥)\s*(?=\d)")
MATH_LT_REGEX = re.compile(
    r"(?:(?<=\d)\s*<\s*(?=\d|[a-zA-Z]\b)|(?<=\b[a-zA-Z])\s*<\s*(?=\d))"
)
MATH_GT_REGEX = re.compile(
    r"(?:(?<=\d)\s*>\s*(?=\d|[a-zA-Z]\b)|(?<=\b[a-zA-Z])\s*>\s*(?=\d))"
)
MATH_PM_REGEX = re.compile(r"(?<=\d)\s*±\s*(?=\d)")
MATH_PM_STANDALONE_REGEX = re.compile(r"±\s*(?=\d)")

# En dash between words without spaces: New York–London -> New York to London
EN_DASH_WORDS_REGEX = re.compile(r"(?<=[A-Za-z])–(?=[A-Za-z])")

# Prose dashes (outside numeric ranges and word-word en dashes)
PROSE_DASH_REGEX = re.compile(r"(?<!\d)[—](?!\d)|(?<![A-Za-z\d])[–](?![A-Za-z\d])")


@lru_cache(maxsize=1)
def get_emoji_regex() -> re.Pattern:
    """Builds regex for matching emoji characters and sequences."""
    data = load_emoji_data()
    emojis = data.get("emojis", {})
    sorted_emojis = sorted(emojis.keys(), key=len, reverse=True)
    generic = (
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        r"\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF"
        r"\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
        r"\U00002600-\U000026FF\U00002700-\U000027BF\U0001F1E6-\U0001F1FF]"
    )
    if sorted_emojis:
        p = "|".join(re.escape(k) for k in sorted_emojis) + "|" + generic
    else:
        p = generic
    return re.compile(p)


@lru_cache(maxsize=1)
def get_emoticon_regex() -> re.Pattern:
    """Builds regex for matching ASCII emoticons."""
    data = load_emoji_data()
    emoticons = data.get("emoticons", {})
    sorted_emoticons = sorted(emoticons.keys(), key=len, reverse=True)
    p = r"(?:(?<=^)|(?<=\s))(" + "|".join(re.escape(k) for k in sorted_emoticons) + r")(?=[\s.,!?]|$)"
    return re.compile(p)


def _verbalize_decimal_or_cardinal(val_str: str, use_and: bool = False) -> str:
    """Helper to verbalize decimal or integer string."""
    if "." in val_str:
        int_part, dec_part = val_str.split(".", 1)
        int_sp = verbalize_cardinal(int(int_part), use_and=use_and)
        dec_sp = " ".join("zero" if d == "0" else verbalize_cardinal(int(d)) for d in dec_part)
        return f"{int_sp} point {dec_sp}"
    return verbalize_cardinal(int(val_str), use_and=use_and)


def _verbalize_power(exp_int: int, use_and: bool = False) -> str:
    """Helper to verbalize an exponent power."""
    if exp_int in ORDINAL_POWERS:
        return ORDINAL_POWERS[exp_int]
    if exp_int < 0:
        return f"the negative {verbalize_cardinal(abs(exp_int), use_and=use_and)}"
    return f"the power of {verbalize_cardinal(exp_int, use_and=use_and)}"


HASH_CUE_WORDS = frozenset({
    "order", "ticket", "invoice", "case", "claim", "reference", "ref",
    "confirmation", "account", "policy", "member",
})


def verbalize_hash_digits_span(
    raw_span: str,
    config: NormalizerConfig,
    is_cue: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes #1 -> number one, or with cue word order #49281 -> order number four nine two eight one."""
    digits = raw_span.lstrip("#")
    if is_cue:
        zero_word = config.spoken_leading_zeros or ("zero" if config.locale == "en-IN" else "oh")
        spoken = verbalize_digits(digits, zero_word=zero_word)
        return f"number {spoken}", [], False
    use_and = config.use_and_in_hundreds or False
    spoken = verbalize_cardinal(int(digits), use_and=use_and)
    return f"number {spoken}", [], False


def verbalize_hashtag_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes #trending -> hashtag trending, #TTS -> hashtag T T S, #GoodMorning -> hashtag Good Morning."""
    tag = raw_span.lstrip("#")
    if re.search(r"[a-z][A-Z]", tag):
        split_tag = re.sub(r"([a-z])([A-Z])", r"\1 \2", tag)
        return f"hashtag {split_tag}", [], False
    if tag.isupper() and len(tag) >= 2:
        abbr_data = load_abbreviations_data()
        pronounceable = frozenset(abbr_data.get("pronounceable_acronyms", []))
        if tag not in pronounceable:
            spelled = " ".join(tag)
            return f"hashtag {spelled}", [], False
    return f"hashtag {tag}", [], False


def verbalize_word_slash_pair(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes word/word slashes: and/or -> and or, TCP/IP -> T C P slash I P."""
    clean = raw_span.strip().lower()
    if config.word_slash_style == "spoken" and clean in WORD_SLASHES:
        return WORD_SLASHES[clean], [], False

    m = re.match(r"^([A-Za-z]+)/([A-Za-z]+)$", raw_span.strip())
    if m:
        w1, w2 = m.group(1), m.group(2)
        abbr_data = load_abbreviations_data()
        pronounceable = frozenset(abbr_data.get("pronounceable_acronyms", []))

        if w1.isupper() and len(w1) >= 2 and w1 not in pronounceable:
            w1_sp = " ".join(w1)
        else:
            w1_sp = w1

        if w2.isupper() and len(w2) >= 2 and w2 not in pronounceable:
            w2_sp = " ".join(w2)
        else:
            w2_sp = w2

        return f"{w1_sp} slash {w2_sp}", [], False

    return raw_span, [], False


def verbalize_standalone_slash_abbr(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes standalone slash abbreviations: N/A -> not applicable, w/o -> without."""
    clean = raw_span.strip().lower()
    if config.word_slash_style == "spoken" and clean in WORD_SLASHES:
        return WORD_SLASHES[clean], [], False
    return raw_span, [], False


def verbalize_tilde_digits_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes ~5 -> approximately five."""
    num_str = raw_span.lstrip("~")
    use_and = config.use_and_in_hundreds or False
    if "." in num_str:
        parts = num_str.split(".", 1)
        int_sp = verbalize_cardinal(int(parts[0]), use_and=use_and)
        dec_sp = " ".join(["zero" if d == "0" else verbalize_cardinal(int(d)) for d in parts[1]])
        return f"approximately {int_sp} point {dec_sp}", [], False
    else:
        spoken = verbalize_cardinal(int(num_str), use_and=use_and)
        return f"approximately {spoken}", [], False


def verbalize_tilde_currency_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes ~ before currency: ~$10 -> approximately ten dollars."""
    return "approximately ", [], False


def verbalize_ampersand_span(
    text: str,
    start: int,
    end: int,
) -> str:
    """Verbalizes & with appropriate surrounding spacing."""
    lead = " " if start > 0 and text[start - 1] not in " \t\n" else ""
    trail = " " if end < len(text) and text[end] not in " \t\n" else ""
    return f"{lead}and{trail}"


def verbalize_at_span(
    text: str,
    start: int,
    end: int,
) -> str:
    """Verbalizes @ with appropriate spacing."""
    lead = " " if start > 0 and text[start - 1] not in " \t\n" else ""
    trail = " " if end < len(text) and text[end] not in " \t\n" else ""
    return f"{lead}at{trail}"


def verbalize_underscore_span(
    text: str,
    start: int,
    end: int,
) -> str:
    """Verbalizes isolated underscore."""
    lead = " " if start > 0 and text[start - 1] not in " \t\n" else ""
    trail = " " if end < len(text) and text[end] not in " \t\n" else ""
    return f"{lead}underscore{trail}"


def verbalize_typo_symbol_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes typographical symbols: © -> copyright, ® -> registered, ™ -> trademark."""
    clean = raw_span.strip()
    return TYPO_SYMBOLS.get(clean, clean), [], False


def verbalize_non_speech_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes non-speech brackets: [laughter], (applause), etc."""
    if config.non_speech_policy == "drop":
        return "", [], False
    elif config.non_speech_policy == "pause":
        return ",", [], False
    return raw_span, [], False


def verbalize_emoji_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes or drops emoji characters based on emoji_policy."""
    if config.emoji_policy == "drop":
        return "", [], False
    elif config.emoji_policy == "pause":
        return ",", [], False
    elif config.emoji_policy == "preserve":
        return raw_span, [], False

    data = load_emoji_data()
    emojis = data.get("emojis", {})
    if raw_span in emojis:
        return emojis[raw_span], [], False

    try:
        name = unicodedata.name(raw_span, "").lower()
        if name:
            return name, [], False
    except Exception:
        pass
    return "emoji", [], False


def verbalize_emoticon_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes or drops ASCII emoticons based on emoji_policy."""
    if config.emoji_policy == "drop":
        return "", [], False
    elif config.emoji_policy == "pause":
        return ",", [], False
    elif config.emoji_policy == "preserve":
        return raw_span, [], False

    data = load_emoji_data()
    emoticons = data.get("emoticons", {})
    clean = raw_span.strip()
    if clean in emoticons:
        return emoticons[clean], [], False
    return raw_span, [], False


def verbalize_dimension_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes dimensions: 10x20 -> ten by twenty, 1920x1080 -> nineteen twenty by ten eighty."""
    use_and = config.use_and_in_hundreds or False
    m3 = DIMENSION_3D_REGEX.match(raw_span.strip())
    if m3:
        d1, d2, d3 = m3.group(1), m3.group(2), m3.group(3)
        sp1 = _verbalize_decimal_or_cardinal(d1, use_and)
        sp2 = _verbalize_decimal_or_cardinal(d2, use_and)
        sp3 = _verbalize_decimal_or_cardinal(d3, use_and)
        return f"{sp1} by {sp2} by {sp3}", [], False

    m2 = DIMENSION_2D_REGEX.match(raw_span.strip())
    if m2:
        d1, d2 = m2.group(1), m2.group(2)
        if d1 == "24" and d2 == "7":
            return "twenty-four seven", [], False
        if d1 == "1920" and d2 == "1080":
            return "nineteen twenty by ten eighty", [], False
        sp1 = _verbalize_decimal_or_cardinal(d1, use_and)
        sp2 = _verbalize_decimal_or_cardinal(d2, use_and)
        return f"{sp1} by {sp2}", [], False

    return raw_span, [], False


def verbalize_sci_note_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes scientific notation: 3.0 x 10^8, 6.02 × 10²³, 1e-6, 2.5E10."""
    use_and = config.use_and_in_hundreds or False
    clean = raw_span.strip()

    me = SCI_NOTE_E_REGEX.match(clean)
    if me:
        base, exp = me.group(1), int(me.group(2).replace("+", ""))
        base_sp = _verbalize_decimal_or_cardinal(base, use_and)
        pow_sp = _verbalize_power(exp, use_and)
        if exp in ORDINAL_POWERS:
            return f"{base_sp} times ten to the {pow_sp}", [], False
        return f"{base_sp} times ten to {pow_sp}", [], False

    mexp = SCI_NOTE_EXP_REGEX.match(clean)
    if mexp:
        base, exp = mexp.group(1), int(mexp.group(2).replace("−", "-"))
        base_sp = _verbalize_decimal_or_cardinal(base, use_and)
        pow_sp = _verbalize_power(exp, use_and)
        if exp in ORDINAL_POWERS:
            return f"{base_sp} times ten to the {pow_sp}", [], False
        return f"{base_sp} times ten to {pow_sp}", [], False

    msup = SCI_NOTE_SUP_REGEX.match(clean)
    if msup:
        base = msup.group(1)
        exp_digits = "".join(SUPERSCRIPT_DIGITS.get(c, c) for c in msup.group(2))
        exp = int(exp_digits.replace("−", "-").replace("+", ""))
        base_sp = _verbalize_decimal_or_cardinal(base, use_and)
        pow_sp = _verbalize_power(exp, use_and)
        if exp in ORDINAL_POWERS:
            return f"{base_sp} times ten to the {pow_sp}", [], False
        return f"{base_sp} times ten to {pow_sp}", [], False

    return raw_span, [], False


def verbalize_multiplier_speed_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes multiplier speed: 3x faster -> three times faster."""
    use_and = config.use_and_in_hundreds or False
    m = MULTIPLIER_SPEED_REGEX.match(raw_span.strip())
    if m:
        num, word = m.group(1), m.group(2)
        sp = _verbalize_decimal_or_cardinal(num, use_and)
        return f"{sp} times {word}", [], False
    return raw_span, [], False


def verbalize_exponent_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes powers and exponents: 10^5, x^2."""
    use_and = config.use_and_in_hundreds or False
    parts = raw_span.split("^", 1)
    if len(parts) == 2:
        base, exp = parts[0], parts[1]
        if base.isdigit():
            base_sp = verbalize_cardinal(int(base), use_and=use_and)
        else:
            base_sp = base
        clean_exp = exp.replace("−", "-")
        if clean_exp.lstrip("-").isdigit():
            exp_int = int(clean_exp)
            if exp_int == 2:
                return f"{base_sp} squared", [], False
            elif exp_int == 3:
                return f"{base_sp} cubed", [], False
            pow_sp = _verbalize_power(exp_int, use_and)
            if exp_int in ORDINAL_POWERS:
                return f"{base_sp} to the {pow_sp} power", [], False
            return f"{base_sp} to {pow_sp}", [], False
    return raw_span, [], False


def verbalize_superscript_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes superscript powers: 5² -> five squared, x³ -> x cubed."""
    use_and = config.use_and_in_hundreds or False
    m = re.match(r"^(\d+|[a-zA-Z])([²³⁴⁵⁶⁷⁸⁹]+)$", raw_span.strip())
    if m:
        base, sups = m.group(1), m.group(2)
        if base.isdigit():
            base_sp = verbalize_cardinal(int(base), use_and=use_and)
        else:
            base_sp = base

        if sups == "²":
            return f"{base_sp} squared", [], False
        elif sups == "³":
            return f"{base_sp} cubed", [], False

        exp_digits = "".join(SUPERSCRIPT_DIGITS.get(c, c) for c in sups)
        if exp_digits.isdigit():
            exp_int = int(exp_digits)
            pow_sp = _verbalize_power(exp_int, use_and)
            if exp_int in ORDINAL_POWERS:
                return f"{base_sp} to the {pow_sp} power", [], False
            return f"{base_sp} to {pow_sp}", [], False
    return raw_span, [], False


def verbalize_sqrt_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes square root: √16 -> square root of sixteen."""
    use_and = config.use_and_in_hundreds or False
    num_part = raw_span.lstrip("√").strip()
    if num_part:
        sp = _verbalize_decimal_or_cardinal(num_part, use_and)
        return f"square root of {sp}", [], False
    return "square root", [], False


def verbalize_chemical_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes chemical formulas: H2O -> H two O, CO2 -> C O two."""
    return CHEMICAL_FORMULAS.get(raw_span, raw_span), [], False


def verbalize_greek_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes Greek letters and math constants: α -> alpha, π -> pi, Ω -> omega."""
    clean = raw_span.strip()
    return GREEK_LETTERS.get(clean, clean), [], False


def find_symbol_candidates(
    text: str,
    config: NormalizerConfig,
) -> list[CandidateSpan]:
    """Scans text for symbols, non-speech, math, dimensions, emojis, and typography."""
    candidates: list[CandidateSpan] = []

    # 1. Chemical formulas (Priority Rank 3: Lexicon Exact Matches)
    for m in CHEMICAL_FORMULA_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="lexicon",
                rule_id="lexicon.chemical",
                priority=LEXICON_EXACT_PRIORITY,
                verbalizer=verbalize_chemical_span,
            )
        )

    # 2. Dimensions (Priority Rank 6: Composite Numeric)
    for m in DIMENSION_3D_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.dimension",
                priority=COMPOSITE_NUMERIC_PRIORITY,
                verbalizer=verbalize_dimension_span,
            )
        )
    for m in DIMENSION_2D_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.dimension",
                priority=COMPOSITE_NUMERIC_PRIORITY,
                verbalizer=verbalize_dimension_span,
            )
        )

    # 2b. Multiplier speed: 3x faster -> three times faster (Priority Rank 6: Composite Numeric)
    for m in MULTIPLIER_SPEED_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.multiplier_speed",
                priority=COMPOSITE_NUMERIC_PRIORITY,
                verbalizer=verbalize_multiplier_speed_span,
            )
        )

    # 3. Scientific notation (Priority Rank 6: Composite Numeric)
    for m in SCI_NOTE_EXP_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.scientific",
                priority=COMPOSITE_NUMERIC_PRIORITY,
                verbalizer=verbalize_sci_note_span,
            )
        )
    for m in SCI_NOTE_SUP_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.scientific",
                priority=COMPOSITE_NUMERIC_PRIORITY,
                verbalizer=verbalize_sci_note_span,
            )
        )
    for m in SCI_NOTE_E_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.scientific",
                priority=COMPOSITE_NUMERIC_PRIORITY,
                verbalizer=verbalize_sci_note_span,
            )
        )

    # 4. Powers & Exponents (Priority Rank 7: Specific Numeric)
    for m in EXPONENT_POW_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.exponent",
                priority=SPECIFIC_NUMERIC_PRIORITY,
                verbalizer=verbalize_exponent_span,
            )
        )
    for m in SUPERSCRIPT_CHAR_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.superscript",
                priority=SPECIFIC_NUMERIC_PRIORITY,
                verbalizer=verbalize_superscript_span,
            )
        )
    for m in SQRT_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="numeric",
                rule_id="numeric.sqrt",
                priority=SPECIFIC_NUMERIC_PRIORITY,
                verbalizer=verbalize_sqrt_span,
            )
        )

    # 5. # followed by digits: #1, #100, order #49281 (Priority Rank 9)
    for m in HASH_DIGITS_REGEX.finditer(text):
        before_text = text[:m.start()].rstrip(" \t")
        before_words = re.findall(r"[A-Za-z]+", before_text)
        is_cue = bool(before_words and before_words[-1].lower() in HASH_CUE_WORDS)
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.hash_number",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, cue_flag=is_cue: verbalize_hash_digits_span(
                    raw, cfg, is_cue=cue_flag
                ),
            )
        )

    # 5b. Telephony * and # symbols: *67, passcode 839201#, press * then #
    for m in re.finditer(r"(?<![*0-9a-zA-Z])\*(\d{2,4})(?![*0-9a-zA-Z])", text):
        digits = m.group(1)
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.star_code",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, d=digits: (
                    f"star {verbalize_digits(d, zero_word='zero' if cfg.locale == 'en-IN' else 'oh')}",
                    [],
                    False,
                ),
            )
        )

    # Telephony commands: press/dial/enter/hit/key * or #
    for m in re.finditer(r"\b(?:press|dial|enter|hit|key)\s+([*#])", text, re.IGNORECASE):
        sym = m.group(1)
        s_idx, e_idx = m.start(1), m.end(1)
        if sym == "*":
            candidates.append(
                CandidateSpan(
                    start=s_idx,
                    end=e_idx,
                    category="symbol",
                    rule_id="symbol.star_key",
                    priority=SYMBOL_PRIORITY,
                    verbalizer=lambda raw, cfg: ("star", [], False),
                )
            )
        else:
            candidates.append(
                CandidateSpan(
                    start=s_idx,
                    end=e_idx,
                    category="symbol",
                    rule_id="symbol.pound_key",
                    priority=SYMBOL_PRIORITY,
                    verbalizer=lambda raw, cfg: (
                        cfg.pound_key_word or ("hash" if cfg.locale in ("en-GB", "en-IN") else "pound"),
                        [],
                        False,
                    ),
                )
            )

    # Telephony sequences: "* then #", "* or #", "# or *", "# then *"
    for m in re.finditer(r"([*#])\s+(?:then\s+|or\s+)([*#])", text, re.IGNORECASE):
        for g in (1, 2):
            sym = m.group(g)
            s_idx, e_idx = m.start(g), m.end(g)
            if sym == "*":
                candidates.append(
                    CandidateSpan(
                        start=s_idx,
                        end=e_idx,
                        category="symbol",
                        rule_id="symbol.star_key",
                        priority=SYMBOL_PRIORITY,
                        verbalizer=lambda raw, cfg: ("star", [], False),
                    )
                )
            else:
                candidates.append(
                    CandidateSpan(
                        start=s_idx,
                        end=e_idx,
                        category="symbol",
                        rule_id="symbol.pound_key",
                        priority=SYMBOL_PRIORITY,
                        verbalizer=lambda raw, cfg: (
                            cfg.pound_key_word or ("hash" if cfg.locale in ("en-GB", "en-IN") else "pound"),
                            [],
                            False,
                        ),
                    )
                )


    # Pound directly after digits: e.g. passcode 839201#
    for m in re.finditer(r"(?<=\d)#", text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.pound_key",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (
                    cfg.pound_key_word or ("hash" if cfg.locale in ("en-GB", "en-IN") else "pound"),
                    [],
                    False,
                ),
            )
        )

    # 6. # followed by words: #trending (Priority Rank 9)
    for m in HASHTAG_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.hashtag",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_hashtag_span,
            )
        )

    # 7. Standalone #
    for m in re.finditer(r"#(?!\w)", text):
        pos = m.start()
        is_after_digit = bool(pos > 0 and text[pos - 1].isdigit())
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.hash_bare",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, after_d=is_after_digit: (
                    (cfg.pound_key_word or ("hash" if cfg.locale in ("en-GB", "en-IN") else "pound"))
                    if after_d
                    else "number",
                    [],
                    False,
                ),
            )
        )

    # 8. ~ followed by digits: ~5, ~100
    for m in TILDE_DIGITS_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.tilde_number",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_tilde_digits_span,
            )
        )

    # 9. ~ followed by currency: ~$10
    for m in TILDE_CURRENCY_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.tilde_currency",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_tilde_currency_span,
            )
        )

    # 10. Standalone ~
    for m in re.finditer(r"~", text):
        s = m.start()
        e = m.end()
        rest = text[e:].lstrip(" \t")
        is_num = bool(rest and (rest[0].isdigit() or rest[0] in "-−$£€₹¥"))
        if is_num:
            has_trail = (e < len(text) and text[e] not in " \t\n")
            repl = "approximately " if has_trail else "approximately"
        else:
            repl = "tilde"
        candidates.append(
            CandidateSpan(
                start=s,
                end=e,
                category="symbol",
                rule_id="symbol.tilde_bare",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, r=repl: (r, [], False),
            )
        )

    # 11. Ampersand (&)
    for m in re.finditer(r"&", text):
        s, e = m.start(), m.end()
        repl = verbalize_ampersand_span(text, s, e)
        candidates.append(
            CandidateSpan(
                start=s,
                end=e,
                category="symbol",
                rule_id="symbol.ampersand",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, r=repl: (r, [], False),
            )
        )

    # 12. At symbol (@)
    for m in re.finditer(r"@", text):
        s, e = m.start(), m.end()
        repl = verbalize_at_span(text, s, e)
        candidates.append(
            CandidateSpan(
                start=s,
                end=e,
                category="symbol",
                rule_id="symbol.at",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, r=repl: (r, [], False),
            )
        )

    # 13. Underscore (_)
    for m in re.finditer(r"_", text):
        s, e = m.start(), m.end()
        repl = verbalize_underscore_span(text, s, e)
        candidates.append(
            CandidateSpan(
                start=s,
                end=e,
                category="symbol",
                rule_id="symbol.underscore",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, r=repl: (r, [], False),
            )
        )

    # 14. Word/word slashes: and/or, TCP/IP, either/or
    for m in WORD_SLASH_PAIR_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.word_slash_pair",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_word_slash_pair,
            )
        )

    # 14b. Standalone slash abbreviations: N/A, w/o, w/, c/o
    for m in STANDALONE_SLASH_ABBR_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.slash_abbr",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_standalone_slash_abbr,
            )
        )

    # 14c. Isolated slash between words
    for m in SLASH_WORDS_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.slash_words",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" slash ", [], False),
            )
        )

    # 15. Slash surrounded by spaces: a / b
    for m in SLASH_SPACES_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.slash_spaces",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: ("slash", [], False),
            )
        )

    # 16. Typographical symbols: ©, ®, ™
    for m in re.finditer(r"[©®™]", text):
        s, e = m.start(), m.end()
        lead = " " if s > 0 and text[s - 1] not in " \t\n" else ""
        trail = " " if e < len(text) and text[e] not in " \t\n" else ""
        repl = f"{lead}{TYPO_SYMBOLS.get(m.group(0), m.group(0))}{trail}"
        candidates.append(
            CandidateSpan(
                start=s,
                end=e,
                category="symbol",
                rule_id="symbol.typography",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, r=repl: (r, [], False),
            )
        )

    # 17. Non-speech brackets: [laughter], (applause), etc.
    for m in NON_SPEECH_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.non_speech",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_non_speech_span,
            )
        )

    # 18. Emojis
    emoji_rx = get_emoji_regex()
    for m in emoji_rx.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.emoji",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_emoji_span,
            )
        )

    # 19. Emoticons
    emoticon_rx = get_emoticon_regex()
    for m in emoticon_rx.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.emoticon",
                priority=SYMBOL_PRIORITY,
                verbalizer=verbalize_emoticon_span,
            )
        )

    # 20. Greek letters & Math constants
    for m in GREEK_LETTERS_REGEX.finditer(text):
        s, e = m.start(), m.end()
        digits = m.group(1)
        g_char = m.group(2)
        g_name = GREEK_LETTERS.get(g_char, g_char)
        if digits:
            digits_sp = verbalize_cardinal(int(digits), use_and=config.use_and_in_hundreds or False)
            spoken = f"{digits_sp} {g_name}"
        else:
            spoken = g_name
        lead = " " if s > 0 and text[s - 1].isalnum() and not digits else ""
        trail = " " if e < len(text) and text[e].isalnum() else ""
        repl = f"{lead}{spoken}{trail}"
        candidates.append(
            CandidateSpan(
                start=s,
                end=e,
                category="symbol",
                rule_id="symbol.greek",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, r=repl: (r, [], False),
            )
        )

    # 21. Math operators in numeric context
    for m in MATH_PLUS_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_plus",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" plus ", [], False),
            )
        )
    for m in MATH_MINUS_REGEX.finditer(text):
        if not is_arithmetic_context(text, m.start(), m.end()):
            continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_minus",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" minus ", [], False),
            )
        )
    for m in MATH_TIMES_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_times",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" times ", [], False),
            )
        )
    for m in MATH_DIV_REGEX.finditer(text):
        if not is_arithmetic_context(text, m.start(), m.end()):
            continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_div",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" divided by ", [], False),
            )
        )
    for m in MATH_EQUALS_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_equals",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" equals ", [], False),
            )
        )
    for m in MATH_NEQ_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_neq",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" does not equal ", [], False),
            )
        )
    for m in MATH_LTE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_lte",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" is less than or equal to ", [], False),
            )
        )
    for m in MATH_GTE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_gte",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" is greater than or equal to ", [], False),
            )
        )
    for m in MATH_LT_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_lt",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" is less than ", [], False),
            )
        )
    for m in MATH_GT_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_gt",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" is greater than ", [], False),
            )
        )
    for m in MATH_PM_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_pm",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" plus or minus ", [], False),
            )
        )
    for m in MATH_PM_STANDALONE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.math_pm_standalone",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: ("plus or minus ", [], False),
            )
        )

    # 22. Prose dashes: —, – (outside numeric ranges)
    for m in PROSE_DASH_REGEX.finditer(text):
        s, e = m.start(), m.end()
        trail = " " if e < len(text) and text[e] not in " \t\n" else ""
        repl = f",{trail}"
        candidates.append(
            CandidateSpan(
                start=s,
                end=e,
                category="symbol",
                rule_id="symbol.prose_dash",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg, r=repl: (r, [], False),
            )
        )

    # 23. En dash between words without spaces: New York–London -> New York to London
    for m in EN_DASH_WORDS_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="symbol",
                rule_id="symbol.en_dash_words",
                priority=SYMBOL_PRIORITY,
                verbalizer=lambda raw, cfg: (" to ", [], False),
            )
        )

    return candidates
