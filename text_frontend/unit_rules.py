"""Unit expansion rules and candidate detection for text_frontend.

Supports:
- Length: mm, cm, m, km, in, ft, yd, mi
- Area: m², ft², km², sq ft, sq mi, ha, acre
- Volume: ml, l, gal, qt, pt, fl oz
- Mass: mg, g, kg, oz, lb, lbs, ton, tonne
- Speed: km/h, kph, mph, m/s, knot
- Temperature: °C, °F, K (with Kelvin context)
- Digital: B, KB, MB, GB, TB, kbps, Mbps, Gbps
- Electrical/Power: V, mV, kV, A, mA, W, kW, MW, kWh, Hz, kHz, MHz, GHz, Ω, N·m
- Plurals: exactly 1 is singular; 0, 1.0, 1.5, etc. are plural.
- Disambiguation: ambiguous symbols (in, A, B, m, K) require attached forms or context.
  "10 in the box" is never verbalized as inches.
- Unit ranges: "10-20 km" -> "ten to twenty kilometers", "5-10 km" -> "five to ten kilometers"
"""

from __future__ import annotations

import re
from typing import NamedTuple

from text_frontend.config import NormalizerConfig
from text_frontend.number_rules import (
    CandidateSpan,
    COMMON_FRACTION_DENOMINATORS,
    UNICODE_FRAC_CHARS,
    UNICODE_FRACTIONS,
    verbalize_bp_number,
    verbalize_cardinal,
    verbalize_decimal_span,
    verbalize_digits,
    verbalize_fraction,
)
from text_frontend.validation import NormalizationWarning


class UnitMeta(NamedTuple):
    symbol: str
    singular: str
    plural: str
    category: str
    is_ambiguous: bool = False
    requires_attached: bool = False


# Map of unit symbols to metadata
UNITS_MAP: dict[str, UnitMeta] = {
    # Length
    "mm": UnitMeta("mm", "millimeter", "millimeters", "length"),
    "cm": UnitMeta("cm", "centimeter", "centimeters", "length"),
    "m": UnitMeta("m", "meter", "meters", "length", is_ambiguous=True, requires_attached=True),
    "km": UnitMeta("km", "kilometer", "kilometers", "length"),
    "in": UnitMeta("in", "inch", "inches", "length", is_ambiguous=True, requires_attached=True),
    "in.": UnitMeta("in.", "inch", "inches", "length"),
    "ft": UnitMeta("ft", "foot", "feet", "length"),
    "ft.": UnitMeta("ft.", "foot", "feet", "length"),
    "yd": UnitMeta("yd", "yard", "yards", "length"),
    "yd.": UnitMeta("yd.", "yard", "yards", "length"),
    "mi": UnitMeta("mi", "mile", "miles", "length"),
    "mi.": UnitMeta("mi.", "mile", "miles", "length"),

    # Area
    "m²": UnitMeta("m²", "square meter", "square meters", "area"),
    "m2": UnitMeta("m2", "square meter", "square meters", "area"),
    "km²": UnitMeta("km²", "square kilometer", "square kilometers", "area"),
    "km2": UnitMeta("km2", "square kilometer", "square kilometers", "area"),
    "ft²": UnitMeta("ft²", "square foot", "square feet", "area"),
    "ft2": UnitMeta("ft2", "square foot", "square feet", "area"),
    "sq ft": UnitMeta("sq ft", "square foot", "square feet", "area"),
    "sq mi": UnitMeta("sq mi", "square mile", "square miles", "area"),
    "ha": UnitMeta("ha", "hectare", "hectares", "area"),
    "acre": UnitMeta("acre", "acre", "acres", "area"),
    "acres": UnitMeta("acres", "acre", "acres", "area"),

    # Cooking Volume
    "tsp": UnitMeta("tsp", "teaspoon", "teaspoons", "volume"),
    "tsp.": UnitMeta("tsp.", "teaspoon", "teaspoons", "volume"),
    "tbsp": UnitMeta("tbsp", "tablespoon", "tablespoons", "volume"),
    "tbsp.": UnitMeta("tbsp.", "tablespoon", "tablespoons", "volume"),
    "tbs": UnitMeta("tbs", "tablespoon", "tablespoons", "volume"),
    "tbs.": UnitMeta("tbs.", "tablespoon", "tablespoons", "volume"),

    # Volume
    "ml": UnitMeta("ml", "milliliter", "milliliters", "volume"),
    "mL": UnitMeta("mL", "milliliter", "milliliters", "volume"),
    "l": UnitMeta("l", "liter", "liters", "volume", is_ambiguous=True, requires_attached=True),
    "L": UnitMeta("L", "liter", "liters", "volume", is_ambiguous=True, requires_attached=True),
    "gal": UnitMeta("gal", "gallon", "gallons", "volume"),
    "qt": UnitMeta("qt", "quart", "quarts", "volume"),
    "pt": UnitMeta("pt", "pint", "pints", "volume"),
    "fl oz": UnitMeta("fl oz", "fluid ounce", "fluid ounces", "volume"),

    # Mass
    "mg": UnitMeta("mg", "milligram", "milligrams", "mass"),
    "g": UnitMeta("g", "gram", "grams", "mass", is_ambiguous=True, requires_attached=True),
    "kg": UnitMeta("kg", "kilogram", "kilograms", "mass"),
    "oz": UnitMeta("oz", "ounce", "ounces", "mass"),
    "oz.": UnitMeta("oz.", "ounce", "ounces", "mass"),
    "lb": UnitMeta("lb", "pound", "pounds", "mass"),
    "lb.": UnitMeta("lb.", "pound", "pounds", "mass"),
    "lbs": UnitMeta("lbs", "pound", "pounds", "mass"),
    "lbs.": UnitMeta("lbs.", "pound", "pounds", "mass"),
    "ton": UnitMeta("ton", "ton", "tons", "mass"),
    "tons": UnitMeta("tons", "ton", "tons", "mass"),
    "tonne": UnitMeta("tonne", "tonne", "tonnes", "mass"),
    "tonnes": UnitMeta("tonnes", "tonne", "tonnes", "mass"),

    # Speed
    "km/h": UnitMeta("km/h", "kilometer per hour", "kilometers per hour", "speed"),
    "kph": UnitMeta("kph", "kilometer per hour", "kilometers per hour", "speed"),
    "mph": UnitMeta("mph", "mile per hour", "miles per hour", "speed"),
    "m/s": UnitMeta("m/s", "meter per second", "meters per second", "speed"),
    "knot": UnitMeta("knot", "knot", "knots", "speed"),
    "knots": UnitMeta("knots", "knot", "knots", "speed"),

    # Temperature
    "°C": UnitMeta("°C", "degree Celsius", "degrees Celsius", "temperature"),
    "deg C": UnitMeta("deg C", "degree Celsius", "degrees Celsius", "temperature"),
    "degC": UnitMeta("degC", "degree Celsius", "degrees Celsius", "temperature"),
    "°F": UnitMeta("°F", "degree Fahrenheit", "degrees Fahrenheit", "temperature"),
    "deg F": UnitMeta("deg F", "degree Fahrenheit", "degrees Fahrenheit", "temperature"),
    "degF": UnitMeta("degF", "degree Fahrenheit", "degrees Fahrenheit", "temperature"),
    "F": UnitMeta("F", "degree Fahrenheit", "degrees Fahrenheit", "temperature", is_ambiguous=True),
    "C": UnitMeta("C", "degree Celsius", "degrees Celsius", "temperature", is_ambiguous=True),
    "K": UnitMeta("K", "kelvin", "kelvins", "temperature", is_ambiguous=True, requires_attached=False),

    # Medical & Chemistry
    "mmHg": UnitMeta("mmHg", "millimeter of mercury", "millimeters of mercury", "pressure"),
    "bpm": UnitMeta("bpm", "beat per minute", "beats per minute", "rate"),
    "mg/dL": UnitMeta("mg/dL", "milligram per deciliter", "milligrams per deciliter", "concentration"),
    "mg/dl": UnitMeta("mg/dl", "milligram per deciliter", "milligrams per deciliter", "concentration"),
    "mcg": UnitMeta("mcg", "microgram", "micrograms", "mass"),

    # Time units
    "ms": UnitMeta("ms", "millisecond", "milliseconds", "time"),
    "ns": UnitMeta("ns", "nanosecond", "nanoseconds", "time"),
    "hr": UnitMeta("hr", "hour", "hours", "time"),
    "hrs": UnitMeta("hrs", "hour", "hours", "time"),
    "min": UnitMeta("min", "minute", "minutes", "time"),
    "mins": UnitMeta("mins", "minute", "minutes", "time"),
    "sec": UnitMeta("sec", "second", "seconds", "time"),
    "secs": UnitMeta("secs", "second", "seconds", "time"),

    # Digital
    "B": UnitMeta("B", "byte", "bytes", "digital", is_ambiguous=True, requires_attached=True),
    "KB": UnitMeta("KB", "kilobyte", "kilobytes", "digital"),
    "MB": UnitMeta("MB", "megabyte", "megabytes", "digital"),
    "GB": UnitMeta("GB", "gigabyte", "gigabytes", "digital"),
    "TB": UnitMeta("TB", "terabyte", "terabytes", "digital"),
    "kbps": UnitMeta("kbps", "kilobit per second", "kilobits per second", "digital"),
    "Mbps": UnitMeta("Mbps", "megabit per second", "megabits per second", "digital"),
    "Gbps": UnitMeta("Gbps", "gigabit per second", "gigabits per second", "digital"),

    # Electrical & Power
    "V": UnitMeta("V", "volt", "volts", "electrical"),
    "mV": UnitMeta("mV", "millivolt", "millivolts", "electrical"),
    "kV": UnitMeta("kV", "kilovolt", "kilovolts", "electrical"),
    "A": UnitMeta("A", "ampere", "amperes", "electrical", is_ambiguous=True, requires_attached=True),
    "mA": UnitMeta("mA", "milliampere", "milliamperes", "electrical"),
    "W": UnitMeta("W", "watt", "watts", "electrical"),
    "kW": UnitMeta("kW", "kilowatt", "kilowatts", "electrical"),
    "MW": UnitMeta("MW", "megawatt", "megawatts", "electrical"),
    "kWh": UnitMeta("kWh", "kilowatt-hour", "kilowatt-hours", "electrical"),
    "Hz": UnitMeta("Hz", "hertz", "hertz", "electrical"),
    "kHz": UnitMeta("kHz", "kilohertz", "kilohertz", "electrical"),
    "MHz": UnitMeta("MHz", "megahertz", "megahertz", "electrical"),
    "GHz": UnitMeta("GHz", "gigahertz", "gigahertz", "electrical"),
    "Ω": UnitMeta("Ω", "ohm", "ohms", "electrical"),
    "ohm": UnitMeta("ohm", "ohm", "ohms", "electrical"),
    "ohms": UnitMeta("ohms", "ohm", "ohms", "electrical"),
    "µs": UnitMeta("µs", "microsecond", "microseconds", "time"),
    "μs": UnitMeta("μs", "microsecond", "microseconds", "time"),
    "µF": UnitMeta("µF", "microfarad", "microfarads", "electrical"),
    "μF": UnitMeta("μF", "microfarad", "microfarads", "electrical"),
    "µm": UnitMeta("µm", "micrometer", "micrometers", "length"),
    "μm": UnitMeta("μm", "micrometer", "micrometers", "length"),
    "N·m": UnitMeta("N·m", "newton-meter", "newton-meters", "electrical"),
    "Nm": UnitMeta("Nm", "newton-meter", "newton-meters", "electrical"),
}

# Regex building: sorted by longest symbol first
UNIT_SYMBOLS_ESCAPED = sorted([re.escape(k) for k in UNITS_MAP.keys()], key=len, reverse=True)
UNITS_REGEX_STR = "|".join(UNIT_SYMBOLS_ESCAPED)

# Pattern matches number + optional space + unit symbol
UNIT_SPAN_REGEX = re.compile(
    rf"(?<![\w/.])([-−]?(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)|[{UNICODE_FRAC_CHARS}])\s*({UNITS_REGEX_STR})(?!\w)",
)

# Pattern matches unit range: "10-20 km", "5-10 km"
UNIT_RANGE_SPAN_REGEX = re.compile(
    rf"(?<![\w/.])([-−]?\d+(?:\.\d+)?)\s*[-–—]\s*([-−]?\d+(?:\.\d+)?)\s*({UNITS_REGEX_STR})(?!\w)",
)

UNIT_A_CUES = frozenset({
    "current", "circuit", "fuse", "draw", "breaker", "amp", "amps", "battery",
})

UNIT_B_CUES = frozenset({
    "storage", "file", "memory", "disk", "data", "size",
})

UNIT_K_CUES = frozenset({
    "temperature", "kelvin",
})

TEMP_CUES = frozenset({
    "temp", "temperature", "fever", "degrees", "degree", "body",
    "forecast", "weather", "oven", "climate", "heat", "cold",
})

ELECTRICAL_CONTEXT_WORDS = frozenset({
    "current", "voltage", "power", "circuit", "fuse", "breaker",
    "adapter", "draw", "amp", "amps", "charge", "charger", "supply",
    "load", "rating", "battery", "dc", "ac",
})

TEMPORAL_DURATION_WORDS = frozenset({
    "wait", "stay", "delay", "duration", "timer", "time", "min", "minute",
    "minutes", "hour", "hours", "second", "seconds", "ago", "pause", "break",
})

DISTANCE_UNIT_WORDS = frozenset({
    "run", "sprint", "sprints", "walk", "race", "meter", "meters", "dash",
    "distance", "long", "high", "wide", "tall", "deep", "throw", "jump",
})


def _get_sentence_words(text: str, pos: int) -> set[str]:
    """Extracts lowercase words in the sentence enclosing the character position."""
    start = 0
    for m in re.finditer(r"(?:^|[\n]|(?<!\d)[.!?]+(?:\s+|$))", text[:pos]):
        start = m.end()
    end = len(text)
    m = re.search(r"(?:[\n]|(?<!\d)[.!?]+(?:\s+|$))", text[pos:])
    if m:
        end = pos + m.start()
    return set(re.findall(r"[a-z]+", text[start:end].lower()))


def find_unit_candidates(
    text: str,
    config: NormalizerConfig,
) -> list[CandidateSpan]:
    """Detects unit candidate spans (Priority Rank 7, Unit Ranges Rank 6)."""
    candidates: list[CandidateSpan] = []

    # 1. Unit Ranges: "10-20 km" (Priority Rank 6: Composite numeric)
    for m in UNIT_RANGE_SPAN_REGEX.finditer(text):
        unit_str = m.group(3)
        meta = UNITS_MAP.get(unit_str)
        if not meta:
            continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="unit",
                rule_id="unit.range",
                priority=6,
                verbalizer=verbalize_unit_range_span,
            )
        )

    # 2. Single Units: "5km", "10 kg", "1.5 m²", "50°C", "3/4 tsp" (Priority Rank 7)
    for m in UNIT_SPAN_REGEX.finditer(text):
        num_str = m.group(1)
        unit_str = m.group(2)
        full_match = m.group(0)

        meta = UNITS_MAP.get(unit_str)
        if not meta:
            continue

        is_attached = not (f"{num_str} {unit_str}" in full_match or f"{num_str}  {unit_str}" in full_match)

        # Disambiguate single-letter units A, B, K (expand as unit only with technical cue in same sentence)
        if unit_str in ("A", "B", "K"):
            sentence_words = _get_sentence_words(text, m.start())
            if unit_str == "A" and not (sentence_words & UNIT_A_CUES):
                continue
            if unit_str == "B" and not (sentence_words & UNIT_B_CUES):
                continue
            if unit_str == "K" and not (sentence_words & UNIT_K_CUES):
                continue

        # Disambiguate standalone F and C (expand as degrees Fahrenheit/Celsius only with temperature cue in same sentence)
        if unit_str in ("F", "C"):
            sentence_words = _get_sentence_words(text, m.start())
            if not (sentence_words & TEMP_CUES):
                continue

        # Check ambiguous symbols requiring attached form (e.g. "10 in the box", "5 m away")
        if meta.requires_attached and not is_attached:
            if unit_str not in ("A", "B", "K", "F", "C"):
                continue

        # Check if in attributive position (e.g. "a 10 mile trip", "a 5 kilogram bag", "10-minute walk")
        is_attr = is_attributive_context(text, m.start(), m.end())

        # Disambiguate attached "m": minutes vs meters
        forced_names = None
        extra_warns = []
        if unit_str == "m" and is_attached:
            surrounding = text[max(0, m.start() - 35) : min(len(text), m.end() + 35)].lower()
            words_near = set(re.findall(r"[a-z]+", surrounding))
            if words_near & TEMPORAL_DURATION_WORDS:
                forced_names = ("minute", "minutes")
            elif words_near & DISTANCE_UNIT_WORDS:
                forced_names = ("meter", "meters")
            else:
                # Ambiguous without clear cue: default to meters with info warning
                forced_names = ("meter", "meters")
                extra_warns.append(
                    NormalizationWarning(
                        code="AMBIGUOUS_UNIT_CONTEXT",
                        message="Attached 'm' resolved to meters by default.",
                        severity="info",
                        original_span=(0, len(m.group(0))),
                    )
                )

        v_func = (
            (lambda raw, cfg, fn=forced_names, ew=extra_warns, attr=is_attr: verbalize_unit_span(
                raw, cfg, forced_unit_names=fn, extra_warnings=ew, is_attributive=attr
            ))
        )

        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="unit",
                rule_id=f"unit.{meta.category}",
                priority=7,
                verbalizer=v_func,
            )
        )

    return candidates


def is_attributive_context(text: str, start: int, end: int) -> bool:
    """Checks if an amount/unit expression is in attributive position (before a noun)."""
    # Range hyphens like $5-$10 or 10-20 are not attributive
    if re.match(r"^-(?:[$€£₹¥]|\d)", text[end:]):
        return False

    before_text = text[:start].rstrip(" \t")
    before_words = re.findall(r"[A-Za-z]+", before_text)
    has_article = bool(before_words and before_words[-1].lower() in ("a", "an"))

    after_text = text[end:].lstrip(" \t")
    has_hyphen = bool(re.match(r"^-[A-Za-z]", text[end:]))

    if not has_article and not has_hyphen:
        return False

    after_words = re.findall(r"[A-Za-z]+", after_text.lstrip("- \t"))
    if not after_words:
        return False
    next_word = after_words[0].lower()

    # Currency ISO codes are not nouns
    if next_word.upper() in {"USD", "GBP", "EUR", "INR", "JPY", "CAD", "AUD", "CHF", "CNY", "NZD", "SGD"}:
        return False

    NON_NOUNS = {
        "is", "was", "are", "were", "and", "or", "but", "in", "on", "at", "to",
        "for", "from", "with", "by", "of", "than", "that", "this", "it", "they",
        "he", "she", "we", "you", "i", "per", "each", "ago", "old", "long",
        "wide", "tall", "high", "deep", "away", "later", "earlier",
    }
    return next_word not in NON_NOUNS


def verbalize_unit_span(
    raw_span: str,
    config: NormalizerConfig,
    forced_unit_names: tuple[str, str] | None = None,
    extra_warnings: list[NormalizationWarning] | None = None,
    is_attributive: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes a combined numeric value and unit symbol."""
    m = UNIT_SPAN_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    num_str = m.group(1).strip()
    unit_str = m.group(2)
    meta = UNITS_MAP.get(unit_str)
    if not meta:
        return raw_span, [], False

    use_and = config.use_and_in_hundreds or False
    warnings = list(extra_warnings or [])

    # Verbalize number part
    if "/" in num_str:
        if " " in num_str:
            whole, frac = num_str.split(" ", 1)
            w_val = int(whole.replace("−", "-"))
            n_val, d_val = map(int, frac.split("/"))
            spoken_num = f"{verbalize_cardinal(abs(w_val), use_and=use_and)} and {verbalize_fraction(n_val, d_val, use_and=use_and)}"
            if w_val < 0:
                spoken_num = "negative " + spoken_num
            is_singular = False
        else:
            n_str = num_str.replace("−", "-")
            n_val, d_val = map(int, n_str.split("/"))
            if unit_str == "mmHg":
                spoken_num = f"{verbalize_bp_number(n_val)} over {verbalize_bp_number(d_val)}"
                is_singular = False
            elif abs(n_val) < d_val and d_val in COMMON_FRACTION_DENOMINATORS:
                spoken_num = verbalize_fraction(n_val, d_val, is_neg=(n_val < 0), use_and=use_and)
                is_singular = True
            else:
                spoken_num = f"{verbalize_cardinal(n_val, use_and=use_and)} over {verbalize_cardinal(d_val, use_and=use_and)}"
                is_singular = False
    elif num_str in UNICODE_FRACTIONS:
        n_val, d_val = UNICODE_FRACTIONS[num_str]
        spoken_num = verbalize_fraction(n_val, d_val, use_and=use_and)
        # Units after pure unicode fraction (< 1) take the singular
        is_singular = True
    elif "." in num_str:
        spoken_num, _, _ = verbalize_decimal_span(num_str, config)
        is_singular = False
    else:
        val = int(num_str.replace("−", "-"))
        spoken_num = verbalize_cardinal(val, use_and=use_and)
        is_singular = (abs(val) == 1)

    if is_attributive:
        unit_name = meta.singular
    elif forced_unit_names:
        unit_name = forced_unit_names[0] if is_singular else forced_unit_names[1]
    else:
        unit_name = meta.singular if is_singular else meta.plural

    return f"{spoken_num} {unit_name}", warnings, bool(warnings)


def verbalize_unit_range_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes unit ranges: 10-20 km -> ten to twenty kilometers."""
    m = UNIT_RANGE_SPAN_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    n1_str = m.group(1)
    n2_str = m.group(2)
    unit_str = m.group(3)
    meta = UNITS_MAP.get(unit_str)
    if not meta:
        return raw_span, [], False

    use_and = config.use_and_in_hundreds or False

    if "." in n1_str:
        s1, _, _ = verbalize_decimal_span(n1_str, config)
    else:
        v1 = int(n1_str.replace("−", "-"))
        s1 = verbalize_cardinal(v1, use_and=use_and)

    if "." in n2_str:
        s2, _, _ = verbalize_decimal_span(n2_str, config)
        is_singular = False
    else:
        v2 = int(n2_str.replace("−", "-"))
        s2 = verbalize_cardinal(v2, use_and=use_and)
        is_singular = (abs(v2) == 1)

    unit_name = meta.singular if is_singular else meta.plural
    return f"{s1} to {s2} {unit_name}", [], False
