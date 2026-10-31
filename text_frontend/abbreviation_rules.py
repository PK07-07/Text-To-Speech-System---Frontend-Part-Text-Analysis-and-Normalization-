"""Abbreviation and acronym verbalization rules for text_frontend.

Supports:
- Titles and honorifics: Mr., Mrs., Ms., Dr., Prof., Sr., Jr., Rev., Capt., Sgt., Lt. -> expand to full words
- Disambiguation:
  - St. -> "Saint" before capitalized name (St. Jude); "Street" after name/number (Main St., 42nd St.)
  - Dr. -> "Doctor" before capitalized name (Dr. Smith); "Drive" after street name/number (Maple Dr.)
- End-of-sentence abbreviation handling: preserve single final period when sentence-final
- Common Latin/general abbreviations: etc., e.g., i.e., vs., approx., dept., apt., avg., misc., inc., corp., co., ltd., est.
- Initialisms spelled letter-by-letter: FBI, CIA, HTML, TTS, USA, UK, EU, UN, ATM, VIP, CEO, CTO, CFO, GPU, CPU
- Dotted initialisms: U.S.A., U.K., F.B.I., C.I.A., Ph.D., M.D.
- Name initials: J. K. Rowling -> "J K Rowling"
- Mixed forms: B2B -> "B to B", A320 -> "A three twenty", 5G -> "five G", 4K -> "four K", 1080p -> "ten eighty P"
- Pronounceable acronyms read as words: NASA, NATO, UNESCO, AIDS, PIN, OPEC, ASAP
- Priority Rank 8: Abbreviations and Acronyms
"""

from __future__ import annotations

import re
from typing import NamedTuple

from text_frontend.config import NormalizerConfig
from text_frontend.data_loader import load_abbreviations_data, load_words_set
from text_frontend.number_rules import (
    CandidateSpan,
    verbalize_cardinal,
    verbalize_ordinal,
)
from text_frontend.validation import NormalizationWarning

# Priority Rank for abbreviations
ABBREVIATION_PRIORITY: int = 8

# Load bundled data tables
_ABBR_DATA = load_abbreviations_data()

# Titles and Honorifics mapping (lowercase keys)
TITLES_EXPANSIONS: dict[str, str] = _ABBR_DATA.get("titles", {
    "mr.": "Mister",
    "mr": "Mister",
    "mrs.": "Missus",
    "mrs": "Missus",
    "ms.": "Ms",
    "ms": "Ms",
    "dr.": "Doctor",
    "dr": "Doctor",
    "prof.": "Professor",
    "prof": "Professor",
    "sr.": "Senior",
    "sr": "Senior",
    "jr.": "Junior",
    "jr": "Junior",
    "rev.": "Reverend",
    "rev": "Reverend",
    "capt.": "Captain",
    "capt": "Captain",
    "sgt.": "Sergeant",
    "sgt": "Sergeant",
    "lt.": "Lieutenant",
    "lt": "Lieutenant",
    "col.": "Colonel",
    "col": "Colonel",
    "gen.": "General",
    "gen": "General",
    "maj.": "Major",
    "maj": "Major",
    "gov.": "Governor",
    "gov": "Governor",
    "sen.": "Senator",
    "sen": "Senator",
    "rep.": "Representative",
    "rep": "Representative",
    "pres.": "President",
    "pres": "President",
})

# Common Latin and general abbreviations
COMMON_ABBREVIATIONS: dict[str, str] = _ABBR_DATA.get("common", {
    "etc.": "etcetera",
    "etc": "etcetera",
    "e.g.": "for example",
    "e.g.,": "for example,",
    "eg": "for example",
    "i.e.": "that is",
    "i.e.,": "that is,",
    "ie": "that is",
    "vs.": "versus",
    "vs": "versus",
    "v.": "versus",
    "approx.": "approximately",
    "approx": "approximately",
    "dept.": "department",
    "dept": "department",
    "apt.": "apartment",
    "apt": "apartment",
    "avg.": "average",
    "avg": "average",
    "misc.": "miscellaneous",
    "misc": "miscellaneous",
    "inc.": "incorporated",
    "inc": "incorporated",
    "corp.": "corporation",
    "corp": "corporation",
    "co.": "company",
    "co": "company",
    "ltd.": "limited",
    "ltd": "limited",
    "est.": "established",
    "est": "established",
})

# Ampersand acronyms
AMPERSAND_ACRONYMS: dict[str, str] = _ABBR_DATA.get("ampersand_acronyms", {
    "AT&T": "A T and T",
    "P&L": "P and L",
    "R&D": "R and D",
    "Q&A": "Q and A",
    "S&P": "S and P",
    "B&B": "B and B",
    "M&A": "M and A",
})

# Pronounceable acronyms read as words (do NOT spell letter-by-letter)
PRONOUNCEABLE_ACRONYMS: frozenset[str] = frozenset(_ABBR_DATA.get("pronounceable_acronyms", [
    "NASA", "NATO", "UNESCO", "AIDS", "PIN", "OPEC", "ASAP",
    "RADAR", "LASER", "SCUBA", "SONAR", "MODEM", "QUASAR",
    "POTUS", "FLOTUS", "SCOTUS", "NORAD", "DARPA", "UNICEF",
    "INTERPOL", "NAFTA", "SWAT", "COVID", "SARS", "ANSI",
    "ASCII", "BASIC", "FORTRAN", "COBOL", "GUI", "WYSIWYG",
    "PIXEL", "SIM", "RAM", "ROM", "GIF", "JPEG", "PNG", "TIFF",
    "ZIP", "BIT", "BYTE", "BIOS", "CAPTCHA", "SNAFU",
]))

# Initialisms spelled letter-by-letter
KNOWN_INITIALISMS: frozenset[str] = frozenset(_ABBR_DATA.get("initialisms", [
    "FBI", "CIA", "HTML", "TTS", "USA", "UK", "EU", "UN", "ATM",
    "VIP", "CEO", "CTO", "CFO", "GPU", "CPU", "SSD", "HDD", "USB",
    "PDF", "API", "URL", "SDK", "CLI", "OS", "IP", "DNS", "HTTP",
    "HTTPS", "FTP", "SSH", "SSL", "TLS", "FAQ", "DIY", "SOS", "PR",
    "HR", "IQ", "EQ", "DJ", "TV", "PC", "AI", "ML", "NLP", "LLM",
    "AGI", "ID", "MD", "PHD", "BA", "BS", "MA", "MS", "MBA", "ETA",
    "TBD", "TBA", "FYI", "TGIF", "RIP", "NPR", "BBC", "CNN", "NBC",
    "CBS", "ABC", "ESPN", "HBO", "MTV", "IBM", "AMD", "BMW", "KFC",
    "BLT", "POV", "RSVP", "OMG", "WTF", "IDK", "IMO", "IMHO", "TMI",
    "DM", "PM", "AM", "GMT", "PST", "EST", "CST", "MST", "UTC", "IST",
    "US", "IT", "BC", "AD", "CE", "BCE",
]))

# Mixed alphanumeric forms
MIXED_ALPHANUMERIC: dict[str, str] = {
    "B2B": "B to B",
    "b2b": "B to B",
    "B2C": "B to C",
    "b2c": "B to C",
    "C2C": "C to C",
    "c2c": "C to C",
    "P2P": "P to P",
    "p2p": "P to P",
    "A320": "A three twenty",
    "a320": "A three twenty",
    "A380": "A three eighty",
    "a380": "A three eighty",
    "B737": "B seven thirty-seven",
    "b737": "B seven thirty-seven",
    "B747": "B seven forty-seven",
    "b747": "B seven forty-seven",
    "B777": "B seven seventy-seven",
    "b777": "B seven seventy-seven",
    "B787": "B seven eighty-seven",
    "b787": "B seven eighty-seven",
    "5G": "five G",
    "5g": "five G",
    "4G": "four G",
    "4g": "four G",
    "3G": "three G",
    "3g": "three G",
    "2G": "two G",
    "2g": "two G",
    "4K": "four K",
    "4k": "four K",
    "8K": "eight K",
    "8k": "eight K",
    "1080p": "ten eighty P",
    "1080P": "ten eighty P",
    "720p": "seven twenty P",
    "720P": "seven twenty P",
    "480p": "four eighty P",
    "480P": "four eighty P",
    "240p": "two forty P",
    "240P": "two forty P",
    "1080i": "ten eighty I",
    "720i": "seven twenty I",
}

# Regex for titles before a name: Mr., Mrs., Dr., etc.
TITLE_BEFORE_REGEX = re.compile(
    r"\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Rev\.|Capt\.|Sgt\.|Lt\.|Col\.|Gen\.|Maj\.|Gov\.|Sen\.|Rep\.|Pres\.|Mr|Mrs|Ms|Dr|Prof|Rev)(?!\w)(?:\s+(?=[A-Z]))",
)

# Regex for suffixes after a name: Jr., Sr.
SUFFIX_AFTER_REGEX = re.compile(
    r"(?<=[A-Za-z],\s)\b(Jr\.|Sr\.|Jr|Sr)(?!\w)|(?<=[A-Za-z]\s)\b(Jr\.|Sr\.|Jr|Sr)(?!\w)"
)

# Regex for common abbreviations
COMMON_ABBR_REGEX = re.compile(
    r"\b(etc\.|etc|e\.g\.,|e\.g\.|eg|i\.e\.,|i\.e\.|ie|vs\.|vs|v\.|approx\.|dept\.|apt\.|avg\.|misc\.|inc\.|corp\.|co\.|ltd\.|est\.)(?!\w)",
    re.IGNORECASE,
)

# Regex for St. disambiguation: Saint vs Street
ST_REGEX = re.compile(r"\b(St\.|St)(?!\w)")

# Regex for Dr. disambiguation: Doctor vs Drive
DR_REGEX = re.compile(r"\b(Dr\.|Dr)(?!\w)")

# Street address suffixes without periods or with periods after name/ordinal
STREET_SUFFIX_MAP: dict[str, str] = {
    "ave": "Avenue",
    "blvd": "Boulevard",
    "rd": "Road",
    "ln": "Lane",
    "hwy": "Highway",
    "pkwy": "Parkway",
    "ct": "Court",
}
STREET_SUFFIX_REGEX = re.compile(
    r"\b(Ave\.|Ave|Blvd\.|Blvd|Rd\.|Rd|Ln\.|Ln|Hwy\.|Hwy|Pkwy\.|Pkwy|Ct\.|Ct)\b"
)

# Regex for name initials: J. K. Rowling, F. Scott, George R. R. Martin
NAME_INITIALS_REGEX = re.compile(
    r"\b([A-Z]\.(?:\s*[A-Z]\.)*)\s+(?=[A-Z][a-z]+)"
)

# Regex for dotted initialisms: U.S.A., U.K., F.B.I., C.I.A., Ph.D.
DOTTED_INITIALISM_REGEX = re.compile(
    r"\b(?:[A-Za-z]\.){2,}(?!\w)"
)

# Regex for ampersand acronyms: AT&T, P&L, R&D, Q&A, S&P
AMPERSAND_ACRONYM_REGEX = re.compile(r"\b([A-Za-z]{1,3}&[A-Za-z]{1,3}(?:&[A-Za-z]{1,3})?)\b")

# Regex for OK
OK_REGEX = re.compile(r"\b(OK|Ok)\b")

# Regex for plural and possessive initialisms: CEOs, FBI's
INITIALISM_PLURAL_POSS_REGEX = re.compile(r"\b([A-Z]{2,6})('s|s)\b")

# Regex for all-caps words (2+ letters)
ALL_CAPS_REGEX = re.compile(r"\b([A-Z]{2,})\b")

# Regex for mixed forms (B2B, 5G, 4K, 1080p, etc.)
MIXED_ALPHANUM_REGEX = re.compile(
    r"\b([A-Za-z]\d[A-Za-z]|\d+[GgKk]|\d{3,4}[pPiI]|[A-Za-z]\d{3,4})\b"
)


COMPANY_SUFFIXES: frozenset[str] = frozenset({
    "ltd", "ltd.", "inc", "inc.", "corp", "corp.", "co", "co.", "llc", "llc.",
})


def _is_sentence_final(text: str, end: int) -> bool:
    """Returns True if the span ending at `end` is followed by sentence-final context."""
    rest = text[end:].lstrip(" \t")
    if not rest:
        return True
    if rest.startswith("\n"):
        return True
    # If followed by another company abbreviation, not sentence final
    words = rest.split()
    if words:
        first_clean = words[0].lower().rstrip(".,;:!?")
        if first_clean in COMPANY_SUFFIXES:
            return False
    if rest[0].isupper():
        return True
    return False


def verbalize_title_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes title abbreviations like Mr. -> Mister, Dr. -> Doctor."""
    clean = raw_span.strip().lower()
    expanded = TITLES_EXPANSIONS.get(clean, raw_span.strip())
    return expanded, [], False


NON_SENTENCE_FINAL_ABBRS: frozenset[str] = frozenset({
    "vs.", "vs", "v.", "mr.", "mrs.", "ms.", "dr.", "prof.", "rev.",
    "capt.", "sgt.", "lt.", "col.", "gen.", "maj.", "gov.", "sen.", "rep.", "pres.",
})


def verbalize_common_abbr_span(
    raw_span: str,
    config: NormalizerConfig,
    is_final: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes common abbreviations like etc. -> etcetera."""
    clean = raw_span.strip().lower()
    expanded = COMMON_ABBREVIATIONS.get(clean, raw_span.strip())
    # Match title case if input started with uppercase
    if raw_span.strip() and raw_span.strip()[0].isupper():
        expanded = expanded[0].upper() + expanded[1:]
    # If the raw span ended with a dot and was sentence-final, preserve the period
    # except for connectors like vs. that connect words
    if is_final and clean not in NON_SENTENCE_FINAL_ABBRS and raw_span.strip().endswith(".") and not expanded.endswith("."):
        expanded += "."
    return expanded, [], False


def verbalize_saint_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes St. as Saint."""
    return "Saint", [], False


def verbalize_street_span(
    raw_span: str,
    config: NormalizerConfig,
    is_final: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes St. as Street."""
    expanded = "Street"
    if is_final and raw_span.strip().endswith("."):
        expanded += "."
    return expanded, [], False


def verbalize_drive_span(
    raw_span: str,
    config: NormalizerConfig,
    is_final: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes Dr. as Drive."""
    expanded = "Drive"
    if is_final and raw_span.strip().endswith("."):
        expanded += "."
    return expanded, [], False


def verbalize_initials_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes name initials: J. K. -> J K."""
    letters = re.findall(r"[A-Za-z]", raw_span)
    return " ".join(letters), [], False


def verbalize_initialism_span(
    raw_span: str,
    config: NormalizerConfig,
    is_final: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes initialisms letter-by-letter: FBI -> F B I, U.S.A. -> U S A."""
    letters = re.findall(r"[A-Za-z]", raw_span)
    res = " ".join(l.upper() for l in letters)
    if is_final and raw_span.strip().endswith("."):
        res += "."
    return res, [], False


def verbalize_mixed_alphanum_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes mixed alphanumeric forms: B2B -> B to B, 5G -> five G, 1080p -> ten eighty P."""
    clean = raw_span.strip()
    if clean in MIXED_ALPHANUMERIC:
        return MIXED_ALPHANUMERIC[clean], [], False
    if clean.upper() in MIXED_ALPHANUMERIC:
        return MIXED_ALPHANUMERIC[clean.upper()], [], False

    # Check <num>G or <num>K
    m_gk = re.match(r"^(\d+)([GgKk])$", clean)
    if m_gk:
        n = int(m_gk.group(1))
        unit = m_gk.group(2).upper()
        return f"{verbalize_cardinal(n)} {unit}", [], False

    # Check <num>p or <num>i (video resolution)
    m_p = re.match(r"^(\d+)([pPiI])$", clean)
    if m_p:
        n_str = m_p.group(1)
        suffix = m_p.group(2).upper()
        n = int(n_str)
        # For 1080, 720, 1440, verbalize naturally: 1080 -> ten eighty, 720 -> seven twenty
        if len(n_str) == 4 and n_str.endswith("0"):
            top = int(n_str[:2])
            bot = int(n_str[2:])
            if bot == 0:
                spoken = verbalize_cardinal(n)
            else:
                spoken = f"{verbalize_cardinal(top)} {verbalize_cardinal(bot)}"
        elif len(n_str) == 3 and n_str.endswith("0"):
            top = int(n_str[0])
            bot = int(n_str[1:])
            if bot == 0:
                spoken = verbalize_cardinal(n)
            else:
                spoken = f"{verbalize_cardinal(top)} {verbalize_cardinal(bot)}"
        else:
            spoken = verbalize_cardinal(n)
        return f"{spoken} {suffix}", [], False

    # Check <letter><num> (e.g. A320 -> A three twenty)
    m_ln = re.match(r"^([A-Za-z])(\d{3,4})$", clean)
    if m_ln:
        letter = m_ln.group(1).upper()
        digits = m_ln.group(2)
        top = int(digits[: len(digits) - 2])
        bot = int(digits[len(digits) - 2 :])
        top_sp = verbalize_cardinal(top)
        bot_sp = verbalize_cardinal(bot) if bot != 0 else "hundred"
        return f"{letter} {top_sp} {bot_sp}", [], False

    return raw_span, [], False


def find_abbreviation_candidates(
    text: str,
    config: NormalizerConfig,
) -> list[CandidateSpan]:
    """Scans text for abbreviations, acronyms, and initialisms."""
    candidates: list[CandidateSpan] = []

    # 1. Titles before names: Mr., Mrs., Dr., etc.
    for m in TITLE_BEFORE_REGEX.finditer(text):
        token = m.group(1)
        span_end = m.start() + len(token)
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=span_end,
                category="abbreviation",
                rule_id="abbr.title",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=verbalize_title_span,
            )
        )

    # 2. Suffixes after names: Jr., Sr.
    for m in SUFFIX_AFTER_REGEX.finditer(text):
        token = m.group(1) or m.group(2)
        start_idx = m.start(1) if m.group(1) else m.start(2)
        end_idx = start_idx + len(token)
        is_final = _is_sentence_final(text, end_idx)
        candidates.append(
            CandidateSpan(
                start=start_idx,
                end=end_idx,
                category="abbreviation",
                rule_id="abbr.suffix",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=lambda raw, cfg, fin=is_final: (
                    TITLES_EXPANSIONS.get(raw.strip().lower(), raw.strip())
                    + ("." if fin and raw.strip().endswith(".") else ""),
                    [],
                    False,
                ),
            )
        )

    # 3. Disambiguation for St. / St (Saint vs Street)
    for m in ST_REGEX.finditer(text):
        st_start = m.start()
        st_end = m.end()

        # Check what follows
        after_text = text[st_end:].lstrip(" \t")
        is_followed_by_capital = bool(after_text and after_text[0].isupper())

        # Check what precedes
        before_text = text[:st_start].rstrip(" \t")
        before_words = re.findall(r"[A-Za-z0-9]+(?:st|nd|rd|th)?", before_text)
        has_preceding_word = bool(before_words)

        is_final = _is_sentence_final(text, st_end)

        # Decision rule:
        # If preceded by street name or number/ordinal (e.g. 42nd St., Main St., Wall St.)
        # and NOT at the start of sentence: it is Street
        if has_preceding_word and not is_followed_by_capital:
            candidates.append(
                CandidateSpan(
                    start=st_start,
                    end=st_end,
                    category="abbreviation",
                    rule_id="abbr.disambiguation.street",
                    priority=ABBREVIATION_PRIORITY,
                    verbalizer=lambda raw, cfg, fin=is_final: verbalize_street_span(
                        raw, cfg, is_final=fin
                    ),
                )
            )
        elif is_followed_by_capital:
            # Saint before capitalized name (St. Jude, St. Patrick)
            candidates.append(
                CandidateSpan(
                    start=st_start,
                    end=st_end,
                    category="abbreviation",
                    rule_id="abbr.disambiguation.saint",
                    priority=ABBREVIATION_PRIORITY,
                    verbalizer=verbalize_saint_span,
                )
            )
        else:
            # Default Street if preceded by word/number
            candidates.append(
                CandidateSpan(
                    start=st_start,
                    end=st_end,
                    category="abbreviation",
                    rule_id="abbr.disambiguation.street",
                    priority=ABBREVIATION_PRIORITY,
                    verbalizer=lambda raw, cfg, fin=is_final: verbalize_street_span(
                        raw, cfg, is_final=fin
                    ),
                )
            )

    # 4. Disambiguation for Dr. / Dr (Doctor vs Drive)
    for m in DR_REGEX.finditer(text):
        dr_start = m.start()
        dr_end = m.end()

        # Check what follows
        after_text = text[dr_end:].lstrip(" \t")
        is_followed_by_capital = bool(after_text and after_text[0].isupper())

        # Check what precedes
        before_text = text[:dr_start].rstrip(" \t")
        before_words = re.findall(r"[A-Za-z0-9]+", before_text)
        has_preceding_word = bool(before_words)

        is_final = _is_sentence_final(text, dr_end)

        # Preceded by a street word/number and NOT followed by capitalized name -> Drive
        if has_preceding_word and (not is_followed_by_capital or is_final):
            # Check if preceding word is title-cased or number (e.g. Maple Dr., Sunset Dr., 42nd Dr.)
            last_word = before_words[-1]
            if last_word[0].isupper() or last_word.isdigit():
                candidates.append(
                    CandidateSpan(
                        start=dr_start,
                        end=dr_end,
                        category="abbreviation",
                        rule_id="abbr.disambiguation.drive",
                        priority=ABBREVIATION_PRIORITY,
                        verbalizer=lambda raw, cfg, fin=is_final: verbalize_drive_span(
                            raw, cfg, is_final=fin
                        ),
                    )
                )
                continue

        # Otherwise Doctor
        candidates.append(
            CandidateSpan(
                start=dr_start,
                end=dr_end,
                category="abbreviation",
                rule_id="abbr.disambiguation.doctor",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=verbalize_title_span,
            )
        )

    # 4b. Street suffixes without period after name/ordinal: 5th Ave, Sunset Blvd, Michigan Ave
    for m in STREET_SUFFIX_REGEX.finditer(text):
        token = m.group(1)
        clean = token.rstrip(".").lower()
        expansion = STREET_SUFFIX_MAP.get(clean)
        if not expansion:
            continue

        before_text = text[:m.start()].rstrip(" \t")
        before_words = re.findall(r"[A-Za-z0-9]+(?:st|nd|rd|th)?", before_text)
        if not before_words:
            continue
        prev_word = before_words[-1]
        is_ordinal_or_num = any(c.isdigit() for c in prev_word) or prev_word.lower() in ("first", "second", "third", "fourth", "fifth")
        is_name = prev_word[0].isupper()
        if not (is_ordinal_or_num or is_name):
            continue

        is_final = _is_sentence_final(text, m.end())
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="abbreviation",
                rule_id="abbr.street_suffix",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=lambda raw, cfg, exp=expansion, fin=is_final: (
                    exp + ("." if fin and raw.endswith(".") else ""),
                    [],
                    False,
                ),
            )
        )

    # 5. Common Latin and general abbreviations (etc., e.g., i.e., vs., etc.)
    for m in COMMON_ABBR_REGEX.finditer(text):
        token = m.group(1)
        is_final = _is_sentence_final(text, m.end())
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="abbreviation",
                rule_id="abbr.common",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=lambda raw, cfg, fin=is_final: verbalize_common_abbr_span(
                    raw, cfg, is_final=fin
                ),
            )
        )

    # 5b. Number abbreviation: No. 5, Flat No. 5 -> number 5
    for m in re.finditer(r"\bNo\.?\s+(?=\d+)", text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="abbreviation",
                rule_id="abbr.number",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=lambda raw, cfg: ("number ", [], False),
            )
        )

    # 5c. Building floor designation: 2nd Floor -> second floor
    for m in re.finditer(r"\b(\d+)(st|nd|rd|th)\s+Floor\b", text):
        val = int(m.group(1))
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="abbreviation",
                rule_id="abbr.floor",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=lambda raw, cfg, v=val: (f"{verbalize_ordinal(v)} floor", [], False),
            )
        )

    # 6. Name Initials: J. K. Rowling, F. Scott, George R. R. Martin
    for m in NAME_INITIALS_REGEX.finditer(text):
        initials_group = m.group(1)
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.start() + len(initials_group),
                category="abbreviation",
                rule_id="abbr.initials",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=verbalize_initials_span,
            )
        )

    # 7. Dotted Initialisms: U.S.A., U.K., F.B.I., C.I.A., Ph.D.
    for m in DOTTED_INITIALISM_REGEX.finditer(text):
        is_final = _is_sentence_final(text, m.end())
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="abbreviation",
                rule_id="abbr.dotted_initialism",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=lambda raw, cfg, fin=is_final: verbalize_initialism_span(
                    raw, cfg, is_final=fin
                ),
            )
        )

    # 8. Mixed alphanumeric forms: B2B, A320, 5G, 4K, 1080p
    for m in MIXED_ALPHANUM_REGEX.finditer(text):
        token = m.group(1)
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="abbreviation",
                rule_id="abbr.mixed",
                priority=ABBREVIATION_PRIORITY,
                verbalizer=verbalize_mixed_alphanum_span,
            )
        )

    # 9. Ampersand Acronyms: AT&T, P&L, R&D, Q&A, S&P (Priority Rank 3: Lexicon)
    for m in AMPERSAND_ACRONYM_REGEX.finditer(text):
        token = m.group(1)
        token_upper = token.upper()
        if token in AMPERSAND_ACRONYMS or token_upper in AMPERSAND_ACRONYMS:
            exp = AMPERSAND_ACRONYMS.get(token, AMPERSAND_ACRONYMS.get(token_upper, token))
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="abbreviation",
                    rule_id="abbr.ampersand_acronym",
                    priority=3,
                    verbalizer=lambda raw, cfg, e=exp: (e, [], False),
                )
            )

    # 10. OK -> okay (Priority Rank 3: Lexicon)
    for m in OK_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="abbreviation",
                rule_id="abbr.ok_lexicon",
                priority=3,
                verbalizer=lambda raw, cfg: ("okay", [], False),
            )
        )

    # 11. Plural and Possessive Initialisms: CEOs -> C E Os, FBI's -> F B I's
    for m in INITIALISM_PLURAL_POSS_REGEX.finditer(text):
        base = m.group(1)
        suffix = m.group(2)
        if base in KNOWN_INITIALISMS or base not in PRONOUNCEABLE_ACRONYMS:
            spoken_letters = " ".join(base)
            spoken = f"{spoken_letters}{suffix}"
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="abbreviation",
                    rule_id="abbr.initialism_plural_possessive",
                    priority=ABBREVIATION_PRIORITY,
                    verbalizer=lambda raw, cfg, sp=spoken: (sp, [], False),
                )
            )

    # 12. All-caps words: Acronym lexicon runs first; lowercase only when whole line is all caps or in words.txt
    words_set = load_words_set()
    for m in ALL_CAPS_REGEX.finditer(text):
        token = m.group(1)
        # Acronym lexicon runs first:
        # Pronounceable acronyms (e.g. UNICEF, NASA, NATO) stay untouched as words
        if token in PRONOUNCEABLE_ACRONYMS:
            continue
        if token in ("OK", "Ok"):
            continue

        # Known initialisms (e.g. US, IT, FBI, CIA, HTML) -> spell letter-by-letter
        if token in KNOWN_INITIALISMS:
            is_final = _is_sentence_final(text, m.end())
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="abbreviation",
                    rule_id="abbr.initialism",
                    priority=ABBREVIATION_PRIORITY,
                    verbalizer=lambda raw, cfg, fin=is_final: verbalize_initialism_span(
                        raw, cfg, is_final=fin
                    ),
                )
            )
            continue

        # Check if whole line is all caps
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]
        letters_in_line = [c for c in line if c.isalpha()]
        is_whole_line_all_caps = bool(letters_in_line and all(c.isupper() for c in letters_in_line))

        is_dict_word = token.lower() in words_set

        if is_whole_line_all_caps or is_dict_word:
            # Lowercase an all-caps word only when its whole line is all caps or it is in words.txt
            lowered = token.lower()
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="abbreviation",
                    rule_id="abbr.all_caps_lowercased",
                    priority=ABBREVIATION_PRIORITY,
                    verbalizer=lambda raw, cfg, low=lowered: (low, [], False),
                )
            )
        else:
            # Not in words.txt and not all-caps line (e.g. XYZ in XYZ Corp):
            # If consonant-only, spell as initialism; otherwise keep as is
            is_consonant_only = not any(c in "AEIOU" for c in token)
            if is_consonant_only and token not in ("XYZ",):
                candidates.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="abbreviation",
                        rule_id="abbr.initialism",
                        priority=ABBREVIATION_PRIORITY,
                        verbalizer=verbalize_initialism_span,
                    )
                )

    return candidates
