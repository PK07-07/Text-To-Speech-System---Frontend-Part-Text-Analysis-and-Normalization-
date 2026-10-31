"""Date, time, and duration verbalization rules and candidate detection for text_frontend.

Supports:
- Numeric dates: MDY, DMY, YMD, ISO 8601 (YYYY-MM-DD)
- Written dates: "Oct 29, 2023", "29 October 2023", "July 4th", "April 3-5", with weekday & month abbreviations
- Calendar validation with datetime.date (leap days, invalid calendar dates)
- 12h and 24h times, seconds, AM/PM formatting ("A M" / "P M"), noon and midnight
- Time zones: EST -> "E S T", UTC -> "U T C", UTC offsets like "+05:30"
- Durations: "2h 30m" -> "two hours and thirty minutes", "45s" -> "forty-five seconds"
"""

from __future__ import annotations

import datetime
import re
from typing import NamedTuple

from text_frontend.config import NormalizerConfig
from text_frontend.number_rules import (
    COMMON_FRACTION_DENOMINATORS,
    CandidateSpan,
    verbalize_cardinal,
    verbalize_digits,
    verbalize_ordinal,
    verbalize_year,
)
from text_frontend.validation import NormalizationWarning

MONTH_NAMES: dict[int, str] = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

MONTH_LOOKUP: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

WEEKDAYS_MAP: dict[str, str] = {
    "mon": "Monday", "monday": "Monday",
    "tue": "Tuesday", "tues": "Tuesday", "tuesday": "Tuesday",
    "wed": "Wednesday", "wednesday": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "thursday": "Thursday",
    "fri": "Friday", "friday": "Friday",
    "sat": "Saturday", "saturday": "Saturday",
    "sun": "Sunday", "sunday": "Sunday",
}

WEEKDAY_PATTERN = r"(?:(?:Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|Thu(?:r(?:s(?:day)?)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)\.?,\s*)?"
MONTH_PATTERN = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"

# Regex patterns for Written Dates
WRITTEN_DATE_MDY_REGEX = re.compile(
    rf"\b({WEEKDAY_PATTERN})({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?\b",
    re.IGNORECASE,
)
WRITTEN_DATE_DMY_REGEX = re.compile(
    rf"\b(?:the\s+)?({WEEKDAY_PATTERN})(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s+({MONTH_PATTERN})(?:,?\s*(\d{{4}}))?\b",
    re.IGNORECASE,
)
DATE_RANGE_WRITTEN_REGEX = re.compile(
    rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:[-–—]|to)\s*(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?\b",
    re.IGNORECASE,
)
WEEKDAY_NAMES_PATTERN = r"(?:Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|Thu(?:r(?:s(?:day)?)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)\.?"
WEEKDAY_RANGE_REGEX = re.compile(
    rf"\b({WEEKDAY_NAMES_PATTERN})\s*[-–—]\s*({WEEKDAY_NAMES_PATTERN})\b",
    re.IGNORECASE,
)

# Regex patterns for Numeric Dates (e.g. 2023-10-29, 10/29/2023, 29/10/2023, 10.29.2023, 2023/10/29)
ISO_DATE_REGEX = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})\b"
)
NUMERIC_DATE_REGEX = re.compile(
    r"\b(\d{1,2})([/.-])(\d{1,2})\2(\d{4})\b"
)
NUMERIC_DATE_YMD_REGEX = re.compile(
    r"\b(\d{4})([/.-])(\d{1,2})\2(\d{1,2})\b"
)
NUMERIC_DATE_MD_REGEX = re.compile(
    r"(?<![\w/.])(\d{1,2})/(\d{1,2})(?!\w|/\d)"
)
DATE_PREP_CUES = frozenset({
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "mon", "tue", "tues", "wed", "thu", "thur", "thurs", "fri", "sat", "sun",
    "on", "by", "due", "until", "before", "after", "from", "through", "since",
    "dated", "date", "between", "deadline",
})

# Regex patterns for Times & Durations
TIME_REGEX = re.compile(
    r"\b(?:(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*(am|pm|a\.m\.|p\.m\.|AM|PM))?|(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.|AM|PM))(?:\s+(?:(UTC|GMT)?\s*([+-]\d{2}(?::?\d{2})?)|([A-Z]{3,4})))?(?!\w)"
)
TIME_24H_SPECIAL_REGEX = re.compile(
    r"\b(00:00|24:00)\b"
)
TIME_RANGE_REGEX = re.compile(
    r"\b(\d{1,2}(?::\d{2})?)\s*(am|pm|a\.m\.|p\.m\.|AM|PM)?\s*[-–—]\s*(\d{1,2}(?::\d{2})?)\s*(am|pm|a\.m\.|p\.m\.|AM|PM)(?!\w)",
    re.IGNORECASE,
)
DURATION_COMPOUND_REGEX = re.compile(
    r"\b(\d+)\s*(?:h|hr|hrs|hours?)\s*(?:and\s*)?(\d+)\s*(?:m|min|mins|minutes?)(?:\s*(?:and\s*)?(\d+)\s*(?:s|sec|secs|seconds?))?\b",
    re.IGNORECASE,
)
DURATION_SINGLE_REGEX = re.compile(
    r"(?<![a-zA-Z][+-])\b(\d+)\s*(?:h|hr|hrs|hours?|min|mins|minutes?|s|sec|secs|seconds?)\b",
    re.IGNORECASE,
)


def _validate_calendar_date(year: int, month: int, day: int) -> bool:
    """Validates calendar date using standard library datetime.date."""
    try:
        datetime.date(year, month, day)
        return True
    except (ValueError, OverflowError):
        return False


def find_date_time_candidates(
    text: str,
    config: NormalizerConfig,
) -> list[CandidateSpan]:
    """Detects candidate date, time, and duration expressions in text."""
    candidates: list[CandidateSpan] = []

    # 1. Dates: Priority Rank 5
    # 1.0 Weekday ranges: "Mon-Fri" -> "Monday to Friday"
    for m in WEEKDAY_RANGE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.weekday.range",
                priority=5,
                verbalizer=verbalize_weekday_range_span,
            )
        )

    # 1.1 Date ranges written: "April 3-5", "April 3 to 5"
    for m in DATE_RANGE_WRITTEN_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.range",
                priority=5,
                verbalizer=verbalize_date_range_span,
            )
        )

    # 1.2 Written dates: "Oct 29, 2023", "July 4th", "Mon, Oct 29", "the 3rd of July 2023"
    for m in WRITTEN_DATE_MDY_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.written.mdy",
                priority=5,
                verbalizer=verbalize_written_date_span,
            )
        )

    for m in WRITTEN_DATE_DMY_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.written.dmy",
                priority=5,
                verbalizer=verbalize_written_date_span,
            )
        )

    # 1.3 ISO dates: 2023-10-29
    for m in ISO_DATE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.iso",
                priority=5,
                verbalizer=verbalize_iso_date_span,
            )
        )

    # 1.4 Numeric dates: 10/29/2023, 29/10/2023
    for m in NUMERIC_DATE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.numeric",
                priority=5,
                verbalizer=verbalize_numeric_date_span,
            )
        )

    # 1.5 Numeric dates YMD: 2023/10/29, 2023.10.29
    for m in NUMERIC_DATE_YMD_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.numeric.ymd",
                priority=5,
                verbalizer=verbalize_numeric_date_ymd_span,
            )
        )

    # 1.6 Numeric dates Month/Day without year: 10/28, 3/4
    for m in NUMERIC_DATE_MD_REGEX.finditer(text):
        v1 = int(m.group(1))
        v2 = int(m.group(2))
        if (v1 == 24 and v2 == 7) or (v1 == 7 and v2 == 24):
            continue

        valid_md = (1 <= v1 <= 12 and 1 <= v2 <= 31)
        valid_dm = (1 <= v2 <= 12 and 1 <= v1 <= 31)
        if not (valid_md or valid_dm):
            continue

        before_text = text[:m.start()].rstrip(" \t")
        before_words = re.findall(r"[A-Za-z]+", before_text)
        has_cue = False
        if before_words:
            recent_words = [w.lower() for w in before_words[-3:]]
            if any(w in DATE_PREP_CUES for w in recent_words):
                has_cue = True
            elif any(w in MONTH_LOOKUP for w in recent_words):
                has_cue = True

        is_common_fraction = (v1 < v2 and v2 in COMMON_FRACTION_DENOMINATORS)
        if is_common_fraction and not has_cue:
            continue

        if not has_cue and not (1 <= v1 <= 12 and 12 < v2 <= 31):
            continue

        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="date",
                rule_id="date.numeric.md",
                priority=5,
                verbalizer=verbalize_numeric_date_md_span,
            )
        )

    # 2. Times & Durations: Priority Rank 5
    # 2.1 Time ranges: "2:00-4:00 PM", "9 a.m.-5 p.m."
    for m in TIME_RANGE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="time",
                rule_id="time.range",
                priority=5,
                verbalizer=verbalize_time_range_span,
            )
        )

    # 2.2 Special 24h: 00:00, 24:00
    for m in TIME_24H_SPECIAL_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="time",
                rule_id="time.special",
                priority=5,
                verbalizer=lambda raw, cfg: ("midnight", [], False),
            )
        )

    SCRIPTURE_CUES = frozenset({
        "chapter", "verse", "genesis", "exodus", "leviticus", "numbers", "deuteronomy",
        "joshua", "judges", "ruth", "samuel", "kings", "chronicles", "ezra", "nehemiah",
        "esther", "job", "psalm", "psalms", "proverbs", "ecclesiastes", "isaiah", "jeremiah",
        "lamentations", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah",
        "micah", "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi",
        "matthew", "mark", "luke", "john", "acts", "romans", "corinthians", "galatians",
        "ephesians", "philippians", "colossians", "thessalonians", "timothy", "titus",
        "philemon", "hebrews", "james", "peter", "jude", "revelation",
    })

    # 2.3 Times: 14:30, 9:05 AM, 09:05:30 EST, 14:30 +05:30, 3 PM IST
    for m in TIME_REGEX.finditer(text):
        h_str = m.group(1)
        m_str = m.group(2)
        ampm = m.group(4) or m.group(6)
        tz = m.group(7) or m.group(9)
        if h_str and m_str and not ampm and not tz:
            before_text = text[:m.start()].rstrip()
            before_words = re.findall(r"[A-Za-z]+", before_text)
            if before_words and before_words[-1].lower() in SCRIPTURE_CUES:
                h_val, m_val = int(h_str), int(m_str)
                candidates.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="time",
                        rule_id="time.scripture_verse",
                        priority=4,
                        verbalizer=lambda raw, cfg, c=h_val, v=m_val: (
                            f"{verbalize_cardinal(c)}, {verbalize_cardinal(v)}",
                            [],
                            False,
                        ),
                    )
                )
                continue

        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="time",
                rule_id="time.clock",
                priority=5,
                verbalizer=verbalize_time_span,
            )
        )

    # 2.4 Compound durations: "2h 30m"
    for m in DURATION_COMPOUND_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="duration",
                rule_id="time.duration.compound",
                priority=5,
                verbalizer=verbalize_compound_duration_span,
            )
        )

    # 2.5 Single duration: "45s", "2h", "30 mins"
    for m in DURATION_SINGLE_REGEX.finditer(text):
        matched_str = m.group(0)
        # Exclude 4-digit decades like 1980s
        if re.match(r"^\d{4}s$", matched_str):
            continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="duration",
                rule_id="time.duration.single",
                priority=5,
                verbalizer=verbalize_single_duration_span,
            )
        )

    return candidates


# Verbalizers for Dates

def verbalize_weekday_range_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes weekday ranges like Mon-Fri -> Monday to Friday."""
    m = WEEKDAY_RANGE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    w1 = m.group(1).rstrip(".").lower()
    w2 = m.group(2).rstrip(".").lower()
    day1 = WEEKDAYS_MAP.get(w1, w1.capitalize())
    day2 = WEEKDAYS_MAP.get(w2, w2.capitalize())
    return f"{day1} to {day2}", [], False


def verbalize_written_date_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes written dates like 'Oct 29, 2023', '29 October 2023', 'July 4th'."""
    clean = raw_span.strip()
    m_mdy = WRITTEN_DATE_MDY_REGEX.match(clean)
    m_dmy = WRITTEN_DATE_DMY_REGEX.match(clean)

    weekday_spoken = ""
    is_dmy = False
    if m_mdy:
        wk_raw = m_mdy.group(1).rstrip(", .").lower() if m_mdy.group(1) else ""
        if wk_raw in WEEKDAYS_MAP:
            weekday_spoken = f"{WEEKDAYS_MAP[wk_raw]}, "
        month_str = m_mdy.group(2).rstrip(".").lower()
        day_str = m_mdy.group(3)
        year_str = m_mdy.group(4)
    elif m_dmy:
        is_dmy = True
        wk_raw = m_dmy.group(1).rstrip(", .").lower() if m_dmy.group(1) else ""
        if wk_raw in WEEKDAYS_MAP:
            weekday_spoken = f"{WEEKDAYS_MAP[wk_raw]}, "
        day_str = m_dmy.group(2)
        month_str = m_dmy.group(3).rstrip(".").lower()
        year_str = m_dmy.group(4)
    else:
        return raw_span, [], False

    month = MONTH_LOOKUP.get(month_str, 1)
    day = int(day_str)
    year = int(year_str) if year_str else 2024  # Default reference leap year if year omitted

    if not _validate_calendar_date(year, month, day):
        warning = NormalizationWarning(
            code="INVALID_CALENDAR_DATE",
            message="Invalid calendar date encountered.",
            severity="warning",
            original_span=(0, len(raw_span)),
        )
        if config.unresolved_policy == "preserve":
            return raw_span, [warning], True
        else:
            # Literal fallback
            month_name = MONTH_NAMES.get(month, month_str.capitalize())
            day_card = verbalize_cardinal(day)
            if year_str:
                year_spoken = verbalize_year(int(year_str), year_2000s_style=config.year_2000s_style)
                return f"{weekday_spoken}{month_name} {day_card}, {year_spoken}", [warning], True
            return f"{weekday_spoken}{month_name} {day_card}", [warning], True

    month_name = MONTH_NAMES[month]
    day_ord = verbalize_ordinal(day)

    spoken_year = verbalize_year(int(year_str), year_2000s_style=config.year_2000s_style) if year_str else ""

    if is_dmy and ("of" in clean.lower() or clean.lower().startswith("the ")):
        spoken_date = f"the {day_ord} of {month_name}"
        if spoken_year:
            spoken_date += f", {spoken_year}"
        return f"{weekday_spoken}{spoken_date}", [], False
    else:
        if spoken_year:
            return f"{weekday_spoken}{month_name} {day_ord}, {spoken_year}", [], False
        else:
            return f"{weekday_spoken}{month_name} {day_ord}", [], False


def verbalize_date_range_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes date ranges like 'April 3-5' -> 'April third to fifth'."""
    m = DATE_RANGE_WRITTEN_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    month_str = m.group(1).rstrip(".").lower()
    day1_str = m.group(2)
    day2_str = m.group(3)
    year_str = m.group(4)

    month = MONTH_LOOKUP.get(month_str, 1)
    day1 = int(day1_str)
    day2 = int(day2_str)
    year = int(year_str) if year_str else 2024

    if not (_validate_calendar_date(year, month, day1) and _validate_calendar_date(year, month, day2)):
        warning = NormalizationWarning(
            code="INVALID_CALENDAR_DATE",
            message="Invalid calendar date in date range.",
            severity="warning",
            original_span=(0, len(raw_span)),
        )
        if config.unresolved_policy == "preserve":
            return raw_span, [warning], True
        else:
            month_name = MONTH_NAMES.get(month, month_str.capitalize())
            return f"{month_name} {verbalize_cardinal(day1)} to {verbalize_cardinal(day2)}", [warning], True

    month_name = MONTH_NAMES[month]
    d1_ord = verbalize_ordinal(day1)
    d2_ord = verbalize_ordinal(day2)

    if year_str:
        year_val = int(year_str)
        spoken_year = verbalize_year(year_val, year_2000s_style=config.year_2000s_style)
        return f"{month_name} {d1_ord} to {d2_ord}, {spoken_year}", [], False
    else:
        return f"{month_name} {d1_ord} to {d2_ord}", [], False


def verbalize_iso_date_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes ISO dates like 2023-10-29 -> October twenty-ninth, twenty twenty-three."""
    m = ISO_DATE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))

    if not _validate_calendar_date(year, month, day):
        warning = NormalizationWarning(
            code="INVALID_CALENDAR_DATE",
            message="Invalid calendar date in ISO date.",
            severity="warning",
            original_span=(0, len(raw_span)),
        )
        if config.unresolved_policy == "preserve":
            return raw_span, [warning], True
        else:
            y_sp = verbalize_year(year, year_2000s_style=config.year_2000s_style)
            m_sp = verbalize_digits(m.group(2), zero_word=config.spoken_leading_zeros)
            d_sp = verbalize_digits(m.group(3), zero_word=config.spoken_leading_zeros)
            return f"{y_sp} dash {m_sp} dash {d_sp}", [warning], True

    month_name = MONTH_NAMES.get(month, "")
    day_ord = verbalize_ordinal(day)
    spoken_year = verbalize_year(year, year_2000s_style=config.year_2000s_style)
    return f"{month_name} {day_ord}, {spoken_year}", [], False


def verbalize_numeric_date_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes numeric dates like 10/29/2023 or 29/10/2023 according to locale date order."""
    m = NUMERIC_DATE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    p1_str = m.group(1)
    sep = m.group(2)
    p2_str = m.group(3)
    year_str = m.group(4)

    p1 = int(p1_str)
    p2 = int(p2_str)
    year = int(year_str)

    order = config.numeric_date_order or ("DMY" if config.locale in ("en-GB", "en-IN") else "MDY")
    warnings: list[NormalizationWarning] = []

    # Check for ambiguity: when both p1 and p2 <= 12 and distinct
    is_ambiguous = (1 <= p1 <= 12 and 1 <= p2 <= 12 and p1 != p2)
    if is_ambiguous and config.warn_on_ambiguous_date:
        warnings.append(
            NormalizationWarning(
                code="AMBIGUOUS_DATE_ORDER",
                message="Numeric date order resolved by locale configuration.",
                severity="info",
                original_span=(0, len(raw_span)),
            )
        )

    if order == "DMY":
        day, month = p1, p2
    else:  # MDY
        month, day = p1, p2

    if not _validate_calendar_date(year, month, day):
        warning = NormalizationWarning(
            code="INVALID_CALENDAR_DATE",
            message="Invalid calendar date in numeric date expression.",
            severity="warning",
            original_span=(0, len(raw_span)),
        )
        warnings.append(warning)
        if config.unresolved_policy == "preserve":
            return raw_span, warnings, True
        else:
            # Literal fallback: verbalize each digit group with separator name
            sep_name = "slash" if sep == "/" else ("dash" if sep == "-" else "dot")
            p1_sp = verbalize_digits(p1_str, zero_word=config.spoken_leading_zeros) if len(p1_str) > 1 and p1_str.startswith("0") else verbalize_cardinal(p1)
            p2_sp = verbalize_digits(p2_str, zero_word=config.spoken_leading_zeros) if len(p2_str) > 1 and p2_str.startswith("0") else verbalize_cardinal(p2)
            y_sp = verbalize_year(year, year_2000s_style=config.year_2000s_style)
            return f"{p1_sp} {sep_name} {p2_sp} {sep_name} {y_sp}", warnings, True

    month_name = MONTH_NAMES[month]
    day_ord = verbalize_ordinal(day)
    spoken_year = verbalize_year(year, year_2000s_style=config.year_2000s_style)
    return f"{month_name} {day_ord}, {spoken_year}", warnings, is_ambiguous


def verbalize_numeric_date_ymd_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes YMD dates like 2023/10/29 or 2023.10.29."""
    m = NUMERIC_DATE_YMD_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    year = int(m.group(1))
    sep = m.group(2)
    month = int(m.group(3))
    day = int(m.group(4))

    warnings: list[NormalizationWarning] = []
    if not _validate_calendar_date(year, month, day):
        warning = NormalizationWarning(
            code="INVALID_CALENDAR_DATE",
            message="Invalid calendar date in YMD numeric date.",
            severity="warning",
            original_span=(0, len(raw_span)),
        )
        warnings.append(warning)
        if config.unresolved_policy == "preserve":
            return raw_span, warnings, True
        else:
            sep_name = "slash" if sep == "/" else ("dash" if sep == "-" else "dot")
            y_sp = verbalize_year(year, year_2000s_style=config.year_2000s_style)
            m_sp = verbalize_cardinal(month)
            d_sp = verbalize_cardinal(day)
            return f"{y_sp} {sep_name} {m_sp} {sep_name} {d_sp}", warnings, True

    month_name = MONTH_NAMES.get(month, "")
    day_ord = verbalize_ordinal(day)
    spoken_year = verbalize_year(year, year_2000s_style=config.year_2000s_style)
    return f"{month_name} {day_ord}, {spoken_year}", warnings, False


def verbalize_numeric_date_md_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes numeric month/day dates like 10/28 -> October twenty-eighth."""
    parts = raw_span.strip().split("/")
    v1 = int(parts[0])
    v2 = int(parts[1])

    valid_md = (1 <= v1 <= 12 and 1 <= v2 <= 31)
    valid_dm = (1 <= v2 <= 12 and 1 <= v1 <= 31)

    warnings: list[NormalizationWarning] = []
    if valid_md and not valid_dm:
        month = v1
        day = v2
        warnings.append(
            NormalizationWarning(
                code="AMBIGUOUS_DATE_ORDER",
                message="Numeric date order resolved by calendar limits.",
                severity="info",
                original_span=(0, len(raw_span)),
            )
        )
    elif valid_dm and not valid_md:
        day = v1
        month = v2
        warnings.append(
            NormalizationWarning(
                code="AMBIGUOUS_DATE_ORDER",
                message="Numeric date order resolved by calendar limits.",
                severity="info",
                original_span=(0, len(raw_span)),
            )
        )
    else:
        order = config.numeric_date_order or ("DMY" if config.locale in ("en-GB", "en-IN") else "MDY")
        if order == "DMY":
            day = v1
            month = v2
        else:
            month = v1
            day = v2
        if config.warn_on_ambiguous_date:
            warnings.append(
                NormalizationWarning(
                    code="AMBIGUOUS_DATE_ORDER",
                    message="Numeric date order resolved by locale configuration.",
                    severity="info",
                    original_span=(0, len(raw_span)),
                )
            )

    month_name = MONTH_NAMES.get(month, "")
    day_ord = verbalize_ordinal(day)
    return f"{month_name} {day_ord}", warnings, False


# Verbalizers for Times & Durations

def verbalize_time_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes 12h/24h clock times, noon/midnight, and time zones."""
    m = TIME_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    if m.group(1) is not None:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) is not None else 0
        second_str = m.group(3)
        ampm_raw = m.group(4)
    else:
        hour = int(m.group(5))
        minute = 0
        second_str = None
        ampm_raw = m.group(6)

    utc_prefix = m.group(7)
    offset_raw = m.group(8)
    tz_named = m.group(9)

    if not (0 <= hour <= 24 and 0 <= minute <= 59):
        warning = NormalizationWarning(
            code="MALFORMED_TIME",
            message="Time values out of valid 24-hour range.",
            severity="warning",
            original_span=(0, len(raw_span)),
        )
        return raw_span, [warning], True

    # Check exact noon and midnight
    is_exact_noon = (hour == 12 and minute == 0 and not second_str and (not ampm_raw or ampm_raw.lower() in ("pm", "p.m.")))
    is_exact_midnight = ((hour == 0 or hour == 24) and minute == 0 and not second_str) or (
        hour == 12 and minute == 0 and not second_str and ampm_raw and ampm_raw.lower() in ("am", "a.m.")
    )

    # Format time zone string
    tz_spoken = ""
    if tz_named:
        tz_spoken = " " + " ".join(tz_named.upper())
    elif offset_raw:
        # e.g. +05:30 or -04:00
        sign = "plus" if offset_raw.startswith("+") else "minus"
        clean_off = offset_raw.lstrip("+-").replace(":", "")
        off_h = int(clean_off[:2])
        off_m = int(clean_off[2:]) if len(clean_off) >= 4 else 0
        h_words = verbalize_cardinal(off_h)
        if off_m > 0:
            m_words = verbalize_cardinal(off_m)
            off_str = f"{sign} {h_words} {m_words}"
        else:
            off_str = f"{sign} {h_words} hours" if off_h > 0 else f"{sign} zero"
        if utc_prefix:
            tz_spoken = f" {' '.join(utc_prefix.upper())} {off_str}"
        else:
            tz_spoken = f" {off_str}"

    if is_exact_noon:
        return f"noon{tz_spoken}", [], False
    if is_exact_midnight:
        return f"midnight{tz_spoken}", [], False

    # Determine 12h vs 24h
    pref = config.time_format_preference

    # 1. Spoken AM/PM string if present
    spoken_ampm = ""
    if ampm_raw:
        spoken_ampm = " A M" if "a" in ampm_raw.lower() else " P M"

    # Seconds string
    spoken_sec = ""
    if second_str:
        s_val = int(second_str)
        s_card = verbalize_cardinal(s_val)
        s_unit = "second" if s_val == 1 else "seconds"
        spoken_sec = f" and {s_card} {s_unit}"

    if pref == "24h" and not ampm_raw:
        # 24h mode: 14:30 -> "fourteen thirty", 14:00 -> "fourteen hundred", 08:00 -> "oh eight hundred"
        if hour == 0:
            h_spoken = "zero zero"
        elif hour < 10 and raw_span.strip().startswith("0"):
            h_spoken = f"oh {verbalize_cardinal(hour)}"
        else:
            h_spoken = verbalize_cardinal(hour)

        if minute == 0:
            m_spoken = "hundred"
        elif minute < 10:
            m_spoken = f"oh {verbalize_cardinal(minute)}"
        else:
            m_spoken = verbalize_cardinal(minute)

        return f"{h_spoken} {m_spoken}{spoken_sec}{tz_spoken}", [], False

    else:
        # 12h mode (default)
        # Unambiguous 24h conversion: hour >= 13, 00:xx, or leading zero
        if hour >= 13:
            hour -= 12
            if not ampm_raw:
                spoken_ampm = " P M"
        elif hour == 0:
            hour = 12
            if not ampm_raw:
                spoken_ampm = " A M"
        elif hour < 10 and raw_span.strip().startswith("0") and not ampm_raw:
            spoken_ampm = " A M"

        h_spoken = verbalize_cardinal(hour)
        if minute == 0:
            if not spoken_ampm:
                m_spoken = "o'clock"
            else:
                m_spoken = ""
        elif minute < 10:
            m_spoken = f"oh {verbalize_cardinal(minute)}"
        else:
            m_spoken = verbalize_cardinal(minute)

        time_core = f"{h_spoken} {m_spoken}".strip()
        return f"{time_core}{spoken_sec}{spoken_ampm}{tz_spoken}", [], False


def verbalize_time_range_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes time ranges like 2:00-4:00 PM -> two to four P M."""
    m = TIME_RANGE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    t1_raw = m.group(1)
    ampm1 = m.group(2)
    t2_raw = m.group(3)
    ampm2 = m.group(4)

    t1_norm, _, _ = verbalize_time_span(f"{t1_raw} {ampm1}" if ampm1 else t1_raw, config)
    t2_norm, _, _ = verbalize_time_span(f"{t2_raw} {ampm2}", config)

    # Clean up duplicate 'o'clock' if present in range
    t1_norm = t1_norm.replace(" o'clock", "")
    t2_norm = t2_norm.replace(" o'clock", "")

    result = f"{t1_norm} to {t2_norm}"
    if raw_span.strip().endswith("."):
        result += "."
    return result, [], False


def verbalize_compound_duration_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes durations like '2h 30m' -> 'two hours and thirty minutes'."""
    m = DURATION_COMPOUND_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    hours = int(m.group(1))
    minutes = int(m.group(2))
    seconds_str = m.group(3)

    h_card = verbalize_cardinal(hours)
    h_unit = "hour" if hours == 1 else "hours"
    m_card = verbalize_cardinal(minutes)
    m_unit = "minute" if minutes == 1 else "minutes"

    parts = [f"{h_card} {h_unit} and {m_card} {m_unit}"]
    if seconds_str:
        sec = int(seconds_str)
        s_card = verbalize_cardinal(sec)
        s_unit = "second" if sec == 1 else "seconds"
        parts.append(f"and {s_card} {s_unit}")

    return " ".join(parts), [], False


def verbalize_single_duration_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes single durations like '45s' -> 'forty-five seconds', '1h' -> 'one hour'."""
    clean = raw_span.strip()
    m = re.match(r"^(\d+)\s*([a-zA-Z]+)$", clean)
    if not m:
        return raw_span, [], False

    val = int(m.group(1))
    unit_raw = m.group(2).lower()
    val_card = verbalize_cardinal(val)

    if unit_raw in ("h", "hr", "hrs", "hour", "hours"):
        unit_name = "hour" if val == 1 else "hours"
    elif unit_raw in ("m", "min", "mins", "minute", "minutes"):
        unit_name = "minute" if val == 1 else "minutes"
    elif unit_raw in ("s", "sec", "secs", "second", "seconds"):
        unit_name = "second" if val == 1 else "seconds"
    else:
        return raw_span, [], False

    return f"{val_card} {unit_name}", [], False
