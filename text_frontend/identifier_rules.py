"""Identifier and phone number verbalization rules for text_frontend.

Supports:
- NANP phone numbers: (555) 123-4567, 555-123-4567, 555.123.4567, +1-555-123-4567
- +91 Indian mobile phone numbers: +91 98765 43210 (5-5 grouping)
- Extensions: ext. 123, x123, ext 123
- Toll-free area codes read as words when read_toll_free_as_words is True
- Bare 7-digit local numbers with hyphen/dot (555-0199) or after a cue ("call 555 0199")
- Product codes and technical IDs: RX-78 -> "R X seventy-eight", WD-40 -> "W D forty", COVID-19 -> "covid nineteen"
- Priority Rank 5: outranks Range (Rank 6) and Cardinal (Rank 7)
"""

from __future__ import annotations

import re
from typing import NamedTuple

from text_frontend.config import NormalizerConfig
from text_frontend.data_loader import load_airports_data, load_words_set
from text_frontend.number_rules import (
    CandidateSpan,
    ONES,
    TENS,
    verbalize_cardinal,
    verbalize_digits,
)
from text_frontend.validation import NormalizationWarning

TOLL_FREE_CODES: frozenset[str] = frozenset({
    "800", "833", "844", "855", "866", "877", "888",
})

PHONE_CUES: frozenset[str] = frozenset({
    "call", "phone", "dial", "tel", "text", "fax", "reach", "contact",
})

# Street address suffixes and map
STREET_SUFFIX_MAP: dict[str, str] = {
    "st.": "Street", "st": "Street", "street": "Street",
    "ave.": "Avenue", "ave": "Avenue", "avenue": "Avenue",
    "rd.": "Road", "rd": "Road", "road": "Road",
    "blvd.": "Boulevard", "blvd": "Boulevard", "boulevard": "Boulevard",
    "dr.": "Drive", "dr": "Drive", "drive": "Drive",
    "ln.": "Lane", "ln": "Lane", "lane": "Lane",
    "ct.": "Court", "ct": "Court", "court": "Court",
    "way": "Way",
    "pl.": "Place", "pl": "Place", "place": "Place",
    "ter.": "Terrace", "ter": "Terrace", "terrace": "Terrace",
    "pkwy.": "Parkway", "pkwy": "Parkway", "parkway": "Parkway",
    "cir.": "Circle", "cir": "Circle", "circle": "Circle",
}

STREET_ADDRESS_REGEX = re.compile(
    r"\b(\d{1,5})\s+([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,2})\s+(St\.|St|Street|Ave\.|Ave|Avenue|Rd\.|Rd|Road|Blvd\.|Blvd|Boulevard|Dr\.|Dr|Drive|Ln\.|Ln|Lane|Ct\.|Ct|Court|Way|Pl\.|Pl|Place|Ter\.|Ter|Terrace|Pkwy\.|Pkwy|Parkway|Cir\.|Cir|Circle)(?!\w)"
)

# Mixed letter-digit identifier regex (v1, item-3, user123)
MIXED_IDENTIFIER_REGEX = re.compile(
    r"\b([A-Za-z]+[-_]\d+|[a-z]+\d+|\d+[a-z]{2,})\b(?![A-Za-z0-9_-])"
)

# NANP 10-digit / 11-digit phone numbers
# e.g. +1-800-555-0199, (800) 555-0199, 800-555-0199, 800.555.0199
NANP_PHONE_REGEX = re.compile(
    r"(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?(\d{3})[-.\s](\d{4})(?:\s*(?:ext\.?|x)\s*(\d+))?",
)

# +91 Indian mobile phone numbers (5-5 grouping: +91 98765 43210 or +91-98765-43210)
INDIAN_PHONE_REGEX = re.compile(
    r"\+91[-.\s]?([6-9]\d{4})[-.\s]?(\d{5})\b"
)

# 7-digit local numbers with separator: 555-0199 or 555.0199
LOCAL_7DIGIT_SEPARATOR_REGEX = re.compile(
    r"\b([2-9]\d{2})[-.](\d{4})\b"
)

# 7-digit local numbers with space after a phone cue: "call 555 0199"
LOCAL_7DIGIT_SPACE_REGEX = re.compile(
    r"\b([2-9]\d{2})\s+(\d{4})\b"
)

# Emergency numbers: 911, 112, 999
EMERGENCY_PHONE_REGEX = re.compile(r"\b(911|112|999)\b")

# Technical IDs / Product codes: RX-78, WD-40, F-16, COVID-19
PRODUCT_CODE_REGEX = re.compile(
    r"\b([A-Za-z]{1,6})-(\d{1,4})\b"
)

# URLs & Emails
URL_REGEX = re.compile(
    r"\b(?:https?://|ftp://|www\.)[A-Za-z0-9.-]+(?::\d+)?(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]*)?",
    re.IGNORECASE,
)
EMAIL_REGEX = re.compile(
    r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)

# Version numbers: v2.1.3, v1.0
VERSION_REGEX = re.compile(
    r"\bv(\d+(?:\.\d+)+)\b",
    re.IGNORECASE,
)

# IPv4 Addresses: 192.168.1.1, 8.8.8.8
IPV4_REGEX = re.compile(
    r"\b(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
)

# Cryptographic and Git hashes: 6-64 hex chars with at least 1 digit and 1 letter or after cue
HASH_REGEX = re.compile(
    r"\b([0-9a-fA-F]{6,64})\b"
)
HASH_CUES: frozenset[str] = frozenset({
    "commit", "hash", "sha", "sha1", "sha256", "git",
})

# Identifier Case Splitting: camelCase, snake_case, SCREAMING_SNAKE
CAMEL_CASE_REGEX = re.compile(r"\b([a-z]+(?:[A-Z][a-z0-9]*)+)\b")
SNAKE_CASE_REGEX = re.compile(r"\b([A-Za-z]+(?:_[A-Za-z0-9]+)+)\b")

HEX_LITERAL_REGEX = re.compile(r"\b0[xX]([0-9a-fA-F]+)\b")

FLIGHT_CODE_REGEX = re.compile(
    r"\b(?:Flight\s+|flight\s+)([A-Z]{2,3})[ -]?(\d{1,4})\b|\b([A-Z]{2})\s+(\d{3,4})\b"
)

CODE_CUES: frozenset[str] = frozenset({
    "order", "ticket", "invoice", "case", "claim", "reference", "ref",
    "confirmation", "account", "policy", "member", "model", "serial",
    "part", "tracking", "sku", "pin", "otp", "code", "id", "flight",
})

AIRPORT_CUES = frozenset({
    "from", "to", "via", "at", "depart", "departs", "departing",
    "arrive", "arrives", "arriving", "flight", "airport",
})

MODEL_CODE_REGEX = re.compile(r"\b([A-Za-z0-9]+(?:-[A-Za-z0-9]+)+)\b")

CUE_CODE_REGEX = re.compile(
    r"\b(?P<cue>pincode|pin\s+code|"
    r"confirmation\s+code|confirmation|"
    r"tracking(?:\s+(?:number|no\.?|#))?|ticket|"
    r"booking\s+(?:reference\s+code|reference|code|number|no\.?|#)|"
    r"account(?:\s+(?:number|no\.?|#))?|"
    r"order(?:\s+(?:number|no\.?|#))?|"
    r"invoice(?:\s+(?:number|no\.?|#))?|"
    r"case(?:\s+(?:number|no\.?|#))?|"
    r"claim(?:\s+(?:number|no\.?|#))?|"
    r"reference(?:\s+(?:code|number|no\.?|#))?|"
    r"ref(?:\s+(?:code|number|no\.?|#))?|"
    r"(?:card\s+)?(?:ends|ending)\s+in|"
    r"last\s+(?:four|4)(?:\s+digits)?|"
    r"customer\s+(?:id|number|no\.?|#)|"
    r"policy(?:\s+(?:number|no\.?|#))?|"
    r"passcode|otp|pin|pnr|zip|"
    r"code|id"
    r")\s*(?:is|:|-|#)?\s*(?P<code>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\b",
    re.IGNORECASE,
)

INDIAN_PHONE_5_5_REGEX = re.compile(r"\b([6-9]\d{4})[ -](\d{5})\b")

ALPHANUM_DESIGNATION_REGEX = re.compile(r"\b(\d{1,2})([A-Za-z])\b|\b([A-Za-z])(\d{1,2})\b")

LEXICON_ID_EXACT: dict[str, str] = {
    "COVID-19": "covid nineteen",
    "covid-19": "covid nineteen",
    "F-16": "F sixteen",
    "f-16": "F sixteen",
    "AK-47": "A K forty-seven",
    "ak-47": "A K forty-seven",
    "MP-40": "M P forty",
    "mp-40": "M P forty",
    "WD-40": "W D forty",
    "wd-40": "W D forty",
}


def find_identifier_candidates(
    text: str,
    config: NormalizerConfig,
) -> list[CandidateSpan]:
    """Detects phone numbers and identifier candidate spans (Priority Rank 3 for lexicon, Rank 4 for phones/IDs)."""
    candidates: list[CandidateSpan] = []

    # 0. Emergency Numbers (Priority Rank 4)
    for m in EMERGENCY_PHONE_REGEX.finditer(text):
        start_idx = m.start()
        end_idx = m.end()
        before_text = text[:start_idx].rstrip()
        before_words = re.findall(r"[A-Za-z]+", before_text)
        after_text = text[end_idx:].lstrip()
        after_words = re.findall(r"[A-Za-z]+", after_text)
        is_cue = False
        if before_words and before_words[-1].lower() in PHONE_CUES | {"emergency", "ring"}:
            is_cue = True
        elif after_words and after_words[0].lower() in {"emergency", "operator", "police", "call"}:
            is_cue = True
        if is_cue:
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="phone",
                    rule_id="id.phone.emergency",
                    priority=4,
                    verbalizer=verbalize_emergency_phone_span,
                )
            )

    # 1. NANP Phone Numbers (Priority Rank 4)
    for m in NANP_PHONE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="phone",
                rule_id="id.phone.nanp",
                priority=4,
                verbalizer=verbalize_nanp_phone_span,
            )
        )

    # 2. Indian Phone Numbers (Priority Rank 4)
    for m in INDIAN_PHONE_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="phone",
                rule_id="id.phone.india",
                priority=4,
                verbalizer=verbalize_india_phone_span,
            )
        )

    # 2b. Indian 10-digit mobile phone numbers with 5-5 grouping (Priority Rank 4)
    for m in INDIAN_PHONE_5_5_REGEX.finditer(text):
        start_idx = m.start()
        before_text = text[:start_idx].rstrip()
        before_words = re.findall(r"[A-Za-z]+", before_text)
        has_cue = bool(before_words and before_words[-1].lower() in PHONE_CUES | {"mobile", "number", "cell"})
        if config.locale == "en-IN" or has_cue:
            p1, p2 = m.group(1), m.group(2)
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="phone",
                    rule_id="id.phone.india_5_5",
                    priority=4,
                    verbalizer=lambda raw, cfg, a=p1, b=p2: (
                        f"{_verbalize_phone_digits(a, 'zero')}, {_verbalize_phone_digits(b, 'zero')}",
                        [],
                        False,
                    ),
                )
            )

    # 2c. Hex Literals: 0x1F, 0xFF00 (Priority Rank 4)
    for m in HEX_LITERAL_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.hex_literal",
                priority=4,
                verbalizer=verbalize_hex_literal_span,
            )
        )

    # 2d. Flight Codes: Flight AI 202, flight UA-402, AA 1204 (Priority Rank 4)
    words_set = load_words_set()
    from text_frontend.currency_rules import ISO_CODES
    for m in FLIGHT_CODE_REGEX.finditer(text):
        airline = (m.group(1) or m.group(3)).upper()
        fnum = m.group(2) or m.group(4)
        start_idx = m.start(1) if m.group(1) else m.start(3)
        end_idx = m.end(2) if m.group(2) else m.end(4)

        if airline in ISO_CODES or airline.lower() in words_set:
            continue

        if m.group(3):
            before_words = re.findall(r"[A-Za-z]+", text[:start_idx].rstrip(" \t"))
            if not (before_words and before_words[-1].lower() in {"flight", "fly", "flying", "on", "board"}):
                continue

        candidates.append(
            CandidateSpan(
                start=start_idx,
                end=end_idx,
                category="identifier",
                rule_id="id.flight_code",
                priority=4,
                verbalizer=lambda raw, cfg, al=airline, fn=fnum: (
                    verbalize_flight_code(al, fn),
                    [],
                    False,
                ),
            )
        )

    # 2d2. Airport codes: from JFK to LAX (Priority Rank 4)
    airports_set = load_airports_data()
    for m in re.finditer(r"\b([A-Za-z]{3})\b", text):
        code = m.group(1).upper()
        if code in airports_set:
            before_text = text[:m.start()].rstrip(" \t")
            before_words = re.findall(r"[A-Za-z]+", before_text)
            if before_words and before_words[-1].lower() in AIRPORT_CUES:
                candidates.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="identifier",
                        rule_id="id.airport_code",
                        priority=4,
                        verbalizer=lambda raw, cfg, c=code: (" ".join(c), [], False),
                    )
                )

    # 2d3. Model codes with letters, digits, and hyphens: RT-AX88U, WH-1000XM4 (Priority Rank 4)
    for m in MODEL_CODE_REGEX.finditer(text):
        tok = m.group(1)
        has_alpha = any(c.isalpha() for c in tok)
        has_digit = any(c.isdigit() for c in tok)
        if not (has_alpha and has_digit):
            continue

        # Skip scientific notation like 1e-6, 2.5E10
        if re.match(r"^\d+(?:\.\d+)?[eE][+-]?\d+$", tok):
            continue

        # Skip if preceded by currency symbol ($5-EUR10)
        if m.start() > 0 and text[m.start() - 1] in {"$", "£", "€", "₹", "¥"}:
            continue

        parts = tok.split("-")
        # If any part is an ordinary English dictionary word (e.g. 'star' in '5-star'), it's a compound word, not a model code
        if any(p.lower() in words_set for p in parts):
            continue

        # Skip if any part is or starts with a currency ISO code (EUR10, USD50, etc.)
        if any(p.upper() in ISO_CODES or (len(p) >= 4 and p[:3].upper() in ISO_CODES) for p in parts):
            continue

        if tok.islower():
            continue

        before_text = text[:m.start()].rstrip(" \t")
        before_words = re.findall(r"[A-Za-z]+", before_text)
        is_id_cue = bool(
            before_words
            and any(
                w.lower() in {
                    "id", "pin", "otp", "code", "pnr", "tracking", "order", "ticket",
                    "policy", "account", "customer", "member", "ref", "reference"
                }
                for w in before_words[-3:]
            )
        )
        if is_id_cue:
            continue
        if tok.upper() in LEXICON_ID_EXACT or tok in LEXICON_ID_EXACT:
            continue

        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.model_code",
                priority=4,
                verbalizer=verbalize_model_code_span,
            )
        )

    # 2e. Cue-word digits and codes: OTP, PIN, account number, tracking, PNR, ZIP, etc. (Priority Rank 4)
    words_set = load_words_set()
    for m in CUE_CODE_REGEX.finditer(text):
        cue = m.group("cue").strip().lower()
        code_str = m.group("code").strip()
        has_digit = any(c.isdigit() for c in code_str)
        if not has_digit:
            if code_str.lower() in words_set or not code_str.isupper() or len(code_str) < 2:
                continue
        if "zip" in cue and (len(code_str) != 5 or not code_str.isdigit()):
            continue
        if ("pincode" in cue or "pin code" in cue) and (len(code_str) != 6 or not code_str.isdigit()):
            continue

        candidates.append(
            CandidateSpan(
                start=m.start("code"),
                end=m.end("code"),
                category="identifier",
                rule_id="id.cue_code",
                priority=4,
                verbalizer=lambda raw, cfg, c_str=code_str, c_cue=cue: (
                    verbalize_cue_code(raw, cfg, c_str, c_cue),
                    [],
                    False,
                ),
            )
        )

    # 3. 7-digit local numbers with hyphen/dot separator: 555-0199 (Priority Rank 4)
    for m in LOCAL_7DIGIT_SEPARATOR_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="phone",
                rule_id="id.phone.local_separator",
                priority=4,
                verbalizer=verbalize_local_phone_span,
            )
        )

    # 4. 7-digit local numbers with space only after phone cue: "call 555 0199" (Priority Rank 4)
    for m in LOCAL_7DIGIT_SPACE_REGEX.finditer(text):
        start_idx = m.start()
        before_text = text[:start_idx].rstrip()
        before_words = re.findall(r"[A-Za-z]+", before_text)
        if before_words and before_words[-1].lower() in PHONE_CUES:
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="phone",
                    rule_id="id.phone.local_cue",
                    priority=4,
                    verbalizer=verbalize_local_phone_span,
                )
            )

    # 5. Product codes / Technical IDs (Rank 3 for exact lexicon, Rank 4 for others)
    words_set = load_words_set()
    for m in PRODUCT_CODE_REGEX.finditer(text):
        code_str = m.group(0)
        letters = m.group(1)
        is_lexicon = code_str in LEXICON_ID_EXACT or code_str.upper() in LEXICON_ID_EXACT
        if not is_lexicon:
            # If letters is a dictionary word or not all-caps, it's not a technical product code
            if letters.lower() in words_set or not letters.isupper():
                continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.lexicon" if is_lexicon else "id.product_code",
                priority=3 if is_lexicon else 4,
                verbalizer=verbalize_product_code_span,
            )
        )

    # 6. Version Numbers: v2.1.3 (Priority Rank 4)
    for m in VERSION_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.version",
                priority=4,
                verbalizer=verbalize_version_span,
            )
        )

    # 7. IPv4 Addresses: 192.168.1.1 (Priority Rank 4)
    for m in IPV4_REGEX.finditer(text):
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.ipv4",
                priority=4,
                verbalizer=verbalize_ipv4_span,
            )
        )

    # 8. Hashes: 7+ hex chars with digit+alpha or after cue (Priority Rank 4)
    words_set = load_words_set()
    for m in HASH_REGEX.finditer(text):
        h_str = m.group(0)
        is_dict_word = h_str.lower() in words_set
        before_text = text[:m.start()].rstrip()
        before_words = re.findall(r"[A-Za-z0-9]+", before_text)
        has_cue = bool(before_words and before_words[-1].lower() in HASH_CUES)

        if is_dict_word:
            is_hash = has_cue
        elif any(c.isdigit() for c in h_str) and any(c.isalpha() for c in h_str):
            is_hash = True
        elif has_cue:
            is_hash = True
        else:
            is_hash = False

        if is_hash:
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="identifier",
                    rule_id="id.hash",
                    priority=4,
                    verbalizer=verbalize_hash_span,
                )
            )

    # 8b. Street Addresses: 123 Main St., 1600 Pennsylvania Ave. (Priority Rank 4)
    for m in STREET_ADDRESS_REGEX.finditer(text):
        is_final = _is_sentence_final_id(text, m.end())
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.street_address",
                priority=4,
                verbalizer=lambda raw, cfg, fin=is_final: verbalize_street_address_span(
                    raw, cfg, is_final=fin
                ),
            )
        )

    # 8c. Mixed letter-digit tokens: v1, item-3, user123 (Priority Rank 8)
    for m in MIXED_IDENTIFIER_REGEX.finditer(text):
        tok = m.group(0)
        # Exclude ordinals
        if re.match(r"^\d+(?:st|nd|rd|th)$", tok, re.IGNORECASE):
            continue
        # Exclude decades like 1980s
        if re.match(r"^\d{4}s$", tok, re.IGNORECASE):
            continue
        # Exclude units
        if re.match(r"^\d+(?:km|m|cm|mm|mi|ft|in|kg|g|mg|lb|oz|mph|kph|fps|kb|mb|gb|tb|a|v|w|b)$", tok, re.IGNORECASE):
            continue
        # Exclude currencies and currency codes
        if re.match(r"^(?:USD|EUR|GBP|INR|JPY|CAD|AUD|CHF|CNY|NZD|SGD)\d+$", tok, re.IGNORECASE):
            continue
        # Exclude video formats
        if re.match(r"^\d+(?:p|i|g|k)$", tok, re.IGNORECASE):
            continue
        # Exclude versions with multiple dots
        if re.match(r"^v\d+(?:\.\d+)+$", tok, re.IGNORECASE):
            continue
        # Exclude pure digits or pure alpha
        if tok.isdigit() or tok.isalpha():
            continue

        # Check for number attached to a following word: e.g. 100items -> one hundred items, 3apples -> three apples
        m_glued = re.match(r"^(\d+)([a-zA-Z]{2,})$", tok)
        if m_glued:
            num_part = m_glued.group(1)
            word_part = m_glued.group(2)
            before_text = text[:m.start()].rstrip(" \t")
            before_words = re.findall(r"[A-Za-z]+", before_text)
            has_code_cue = bool(before_words and before_words[-1].lower() in CODE_CUES)
            if not has_code_cue:
                candidates.append(
                    CandidateSpan(
                        start=m.start(),
                        end=m.end(),
                        category="identifier",
                        rule_id="id.glued_number_word",
                        priority=8,
                        verbalizer=lambda raw, cfg, n=num_part, w=word_part: (
                            f"{verbalize_cardinal(int(n), use_and=cfg.use_and_in_hundreds or False)} {w}",
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
                category="identifier",
                rule_id="id.mixed_token",
                priority=8,
                verbalizer=verbalize_mixed_identifier_span,
            )
        )

    # 8d. Alphanumeric designations: 4B -> four B, 12A -> twelve A, B7 -> B seven, 14C -> fourteen C (Priority Rank 8)
    for m in ALPHANUM_DESIGNATION_REGEX.finditer(text):
        if m.group(1) is not None:
            num_str = m.group(1)
            let = m.group(2)
            if let.lower() in ("s", "x"):
                continue
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="identifier",
                    rule_id="id.alphanum_designation",
                    priority=8,
                    verbalizer=lambda raw, cfg, n=num_str, l=let: (
                        f"{verbalize_cardinal(int(n))} {l.upper()}",
                        [],
                        False,
                    ),
                )
            )
        else:
            let = m.group(3)
            num_str = m.group(4)
            if let.lower() in ("s", "x"):
                continue
            candidates.append(
                CandidateSpan(
                    start=m.start(),
                    end=m.end(),
                    category="identifier",
                    rule_id="id.alphanum_designation",
                    priority=8,
                    verbalizer=lambda raw, cfg, n=num_str, l=let: (
                        f"{l.upper()} {verbalize_cardinal(int(n))}",
                        [],
                        False,
                    ),
                )
            )

    # 9. Identifier Case Splitting (camelCase, snake_case, SCREAMING_SNAKE) (Priority Rank 4)
    for m in SNAKE_CASE_REGEX.finditer(text):
        if _is_inside_tag(text, m.start(), m.end()):
            continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.case_split",
                priority=4,
                verbalizer=verbalize_case_split_span,
            )
        )
    for m in CAMEL_CASE_REGEX.finditer(text):
        if _is_inside_tag(text, m.start(), m.end()):
            continue
        candidates.append(
            CandidateSpan(
                start=m.start(),
                end=m.end(),
                category="identifier",
                rule_id="id.case_split",
                priority=4,
                verbalizer=verbalize_case_split_span,
            )
        )

    return candidates


def _is_inside_tag(text: str, start: int, end: int) -> bool:
    """Returns True if the character range falls inside an HTML/XML tag <...>."""
    last_open = text.rfind("<", 0, start)
    if last_open != -1:
        last_close = text.rfind(">", last_open, start)
        if last_close == -1:
            next_close = text.find(">", end)
            if next_close != -1:
                return True
    return False


def verbalize_emergency_phone_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes emergency phone numbers like 911 -> nine one one, 112 -> one one two."""
    zero_w = "zero" if config.spoken_leading_zeros == "zero" else "oh"
    spoken = _verbalize_phone_digits(raw_span.strip(), zero_w)
    return spoken, [], False


def _verbalize_phone_digits(digit_group: str, spoken_leading_zeros: str) -> str:
    """Verbalizes a digit group digit-by-digit."""
    words = []
    for d in digit_group:
        if d == "0":
            words.append(spoken_leading_zeros)
        else:
            words.append(ONES[int(d)])
    return " ".join(words)


def verbalize_nanp_phone_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes NANP phone numbers with pacing commas between groups."""
    m = NANP_PHONE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    area = m.group(1)
    prefix = m.group(2)
    line = m.group(3)
    ext = m.group(4)

    zero_w = config.spoken_leading_zeros

    # Area code verbalization
    if config.read_toll_free_as_words and area in TOLL_FREE_CODES:
        area_spoken = verbalize_cardinal(int(area))
    else:
        area_spoken = _verbalize_phone_digits(area, zero_w)

    prefix_spoken = _verbalize_phone_digits(prefix, zero_w)
    line_spoken = _verbalize_phone_digits(line, zero_w)

    has_country_code = (
        raw_span.strip().startswith("+1")
        or raw_span.strip().startswith("1-")
        or raw_span.strip().startswith("1.")
        or raw_span.strip().startswith("1 ")
    )
    country_prefix = "one, " if has_country_code else ""

    result = f"{country_prefix}{area_spoken}, {prefix_spoken}, {line_spoken}"

    if ext:
        ext_digits = _verbalize_phone_digits(ext, zero_w)
        result += f", extension {ext_digits}"

    return result, [], False


def verbalize_india_phone_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes +91 Indian mobile phone numbers (5-5 grouping)."""
    m = INDIAN_PHONE_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False

    g1 = m.group(1)
    g2 = m.group(2)
    zero_w = config.spoken_leading_zeros

    s1 = _verbalize_phone_digits(g1, zero_w)
    s2 = _verbalize_phone_digits(g2, zero_w)

    return f"plus nine one, {s1}, {s2}", [], False


def verbalize_local_phone_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes 7-digit local phone numbers: 555-0199."""
    digits_only = re.sub(r"\D", "", raw_span)
    if len(digits_only) != 7:
        return raw_span, [], False

    p1 = digits_only[:3]
    p2 = digits_only[3:]
    zero_w = config.spoken_leading_zeros

    s1 = _verbalize_phone_digits(p1, zero_w)
    s2 = _verbalize_phone_digits(p2, zero_w)

    return f"{s1}, {s2}", [], False


def verbalize_product_code_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes product codes like RX-78 -> R X seventy-eight, WD-40 -> W D forty."""
    clean = raw_span.strip()
    if clean in LEXICON_ID_EXACT:
        return LEXICON_ID_EXACT[clean], [], False

    m = PRODUCT_CODE_REGEX.match(clean)
    if not m:
        return raw_span, [], False

    letters = m.group(1)
    digits = m.group(2)

    use_and = config.use_and_in_hundreds or False
    num_val = int(digits)
    num_spoken = verbalize_cardinal(num_val, use_and=use_and)

    # Spell letters uppercase separated by space
    letters_spoken = " ".join(letters.upper())
    return f"{letters_spoken} {num_spoken}", [], False


def verbalize_url_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes URLs in conversational, verbatim, or preserve style."""
    if config.url_reading_style == "preserve":
        return raw_span, [], False
    clean = raw_span.strip().rstrip(".,;:!?)'\"")
    if config.url_reading_style == "verbatim":
        words = []
        for ch in clean:
            if ch.isalpha():
                words.append(ch.lower())
            elif ch.isdigit():
                words.append(ONES[int(ch)])
            elif ch == ":":
                words.append("colon")
            elif ch == "/":
                words.append("slash")
            elif ch == ".":
                words.append("dot")
            elif ch == "-":
                words.append("dash")
            elif ch == "_":
                words.append("underscore")
            elif ch == "?":
                words.append("question mark")
            elif ch == "=":
                words.append("equals")
            elif ch == "&":
                words.append("and")
            elif ch == "%":
                words.append("percent")
            else:
                words.append(ch)
        return " ".join(words), [], False
    else:
        url = clean
        if "://" in url:
            url = url.split("://", 1)[1]
        if url.startswith("www."):
            url = url[4:]

        path_parts = url.split("/")
        spoken_parts = []
        for p in path_parts:
            if not p:
                continue
            p_spoken = (
                p.replace(".", " dot ")
                .replace("-", " dash ")
                .replace("_", " underscore ")
                .replace("?", " question mark ")
                .replace("=", " equals ")
                .replace("&", " and ")
            )
            tokens = p_spoken.split()
            res_tokens = []
            for t in tokens:
                if t.isdigit():
                    res_tokens.append(verbalize_cardinal(int(t)))
                elif re.search(r"\d", t) and re.search(r"[A-Za-z]", t):
                    chunks = re.findall(r"[A-Za-z]+|\d+", t)
                    res_tokens.append(" ".join(verbalize_digits(c) if c.isdigit() else c for c in chunks))
                else:
                    res_tokens.append(t)
            spoken_parts.append(" ".join(res_tokens))
        return " slash ".join(spoken_parts), [], False


def verbalize_email_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes email addresses: user@example.com -> user at example dot com."""
    if config.email_reading_style == "preserve":
        return raw_span, [], False
    clean = raw_span.strip().rstrip(".,;:!?)'\"")
    if "@" not in clean:
        return raw_span, [], False
    local, domain = clean.split("@", 1)

    local_clean = (
        local.replace(".", " dot ")
        .replace("+", " plus ")
        .replace("_", " underscore ")
        .replace("-", " dash ")
    )
    local_tokens = []
    for t in local_clean.split():
        if t.isdigit():
            local_tokens.append(verbalize_digits(t))
        elif re.search(r"\d", t) and re.search(r"[A-Za-z]", t):
            chunks = re.findall(r"[A-Za-z]+|\d+", t)
            local_tokens.append(" ".join(verbalize_digits(c) if c.isdigit() else c for c in chunks))
        else:
            local_tokens.append(t)

    domain_clean = domain.replace(".", " dot ").replace("-", " dash ")
    return f"{' '.join(local_tokens)} at {domain_clean}", [], False


def verbalize_version_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes version strings: v2.1.3 -> version two point one point three."""
    clean = raw_span.strip()
    m = re.match(r"^v(\d+(?:\.\d+)+)$", clean, re.IGNORECASE)
    if not m:
        return raw_span, [], False
    num_parts = m.group(1).split(".")
    spoken_nums = [verbalize_cardinal(int(p)) for p in num_parts]
    return f"version {' point '.join(spoken_nums)}", [], False


def verbalize_ipv4_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes IPv4 addresses: 192.168.1.1 -> one nine two dot one six eight dot one dot one."""
    clean = raw_span.strip()
    octets = clean.split(".")
    zero_w = "zero" if config.spoken_leading_zeros == "zero" else "oh"
    spoken_octets = []
    for octet in octets:
        spoken_octets.append(_verbalize_phone_digits(octet, zero_w))
    return " dot ".join(spoken_octets), [], False


def verbalize_hash_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes cryptographic/git hashes character by character."""
    clean = raw_span.strip()
    zero_w = "zero" if config.spoken_leading_zeros == "zero" else "oh"
    words = []
    for ch in clean:
        if ch == "0":
            words.append(zero_w)
        elif ch.isdigit():
            words.append(ONES[int(ch)])
        else:
            words.append(ch.lower())
    return " ".join(words), [], False


def verbalize_case_split_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes camelCase, snake_case, and SCREAMING_SNAKE identifiers."""
    clean = raw_span.strip()
    if config.identifier_reading == "spelled":
        return " ".join(clean), [], False
    if clean.isupper() and "_" in clean:
        words = clean.lower().split("_")
        return " ".join(words), [], False
    if "_" in clean:
        words = clean.split("_")
        return " ".join(words), [], False
    else:
        split_words = re.sub(r"([a-z])([A-Z])", r"\1 \2", clean)
        return split_words, [], False


def verbalize_address_number(num_str: str) -> str:
    """Verbalizes house/street address numbers in spoken pairs."""
    n = int(num_str)
    if len(num_str) <= 2:
        return verbalize_cardinal(n)
    if len(num_str) == 3:
        d1 = int(num_str[0])
        d23 = int(num_str[1:])
        if d23 == 0:
            return f"{verbalize_cardinal(d1)} hundred"
        elif num_str[1] == "0":
            return f"{verbalize_cardinal(d1)} oh {verbalize_cardinal(int(num_str[2]))}"
        else:
            return f"{verbalize_cardinal(d1)} {verbalize_cardinal(d23)}"
    if len(num_str) == 4:
        p1 = int(num_str[:2])
        p2 = int(num_str[2:])
        if p2 == 0:
            return f"{verbalize_cardinal(p1)} hundred"
        elif num_str[2] == "0":
            return f"{verbalize_cardinal(p1)} oh {verbalize_cardinal(int(num_str[3]))}"
        else:
            return f"{verbalize_cardinal(p1)} {verbalize_cardinal(p2)}"
    if len(num_str) == 5:
        d1 = int(num_str[0])
        p2 = int(num_str[1:3])
        p3 = int(num_str[3:])
        return f"{verbalize_cardinal(d1)} {verbalize_cardinal(p2)} {verbalize_cardinal(p3)}"
    return verbalize_cardinal(n)


def _is_sentence_final_id(text: str, end: int) -> bool:
    """Checks whether an identifier span ends at a sentence boundary."""
    rest = text[end:].lstrip(" \t")
    if not rest or rest.startswith("\n") or rest[0].isupper():
        return True
    return False


def verbalize_street_address_span(
    raw_span: str,
    config: NormalizerConfig,
    is_final: bool = False,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes street addresses: 123 Main St. -> one twenty-three Main Street."""
    m = STREET_ADDRESS_REGEX.match(raw_span.strip())
    if not m:
        return raw_span, [], False
    num_str = m.group(1)
    street_name = m.group(2)
    suffix_str = m.group(3)
    num_spoken = verbalize_address_number(num_str)
    suffix_clean = suffix_str.lower()
    suffix_spoken = STREET_SUFFIX_MAP.get(suffix_clean, suffix_str)
    res = f"{num_spoken} {street_name} {suffix_spoken}"
    if is_final and raw_span.strip().endswith("."):
        res += "."
    return res, [], False


def verbalize_mixed_identifier_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes mixed letter-digit tokens: v1 -> v one, item-3 -> item dash three, user123 -> user one two three."""
    clean = raw_span.strip()
    tokens = re.findall(r"[A-Za-z]+|\d+|-|_", clean)
    spoken_tokens = []
    for t in tokens:
        if t == "-":
            spoken_tokens.append("dash")
        elif t == "_":
            spoken_tokens.append("underscore")
        elif t.isdigit():
            spoken_tokens.append(verbalize_digits(t, zero_word="zero"))
        else:
            spoken_tokens.append(t)
    return " ".join(spoken_tokens), [], False


def verbalize_hex_literal_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes hex literals: 0x1F -> zero x one F, 0xFF00 -> zero x F F zero zero."""
    clean = raw_span.strip()
    digits = clean[2:]
    spoken: list[str] = []
    for ch in digits:
        if ch == "0":
            spoken.append("zero")
        elif ch.isdigit():
            spoken.append(ONES[int(ch)])
        else:
            spoken.append(ch.upper())
    return f"zero x {' '.join(spoken)}", [], False


def verbalize_flight_code(airline: str, fnum: str) -> str:
    """Verbalizes flight codes: Flight AI 202 -> Flight A I two oh two, UA-402 -> U A four oh two."""
    al_spoken = " ".join(airline.upper())
    n = int(fnum)
    if len(fnum) == 3:
        if fnum[1] == "0" and fnum[2] != "0":
            num_spoken = f"{ONES[int(fnum[0])]} oh {ONES[int(fnum[2])]}"
        elif n % 100 == 0:
            num_spoken = f"{ONES[int(fnum[0])]} hundred"
        else:
            first = ONES[int(fnum[0])]
            rem = int(fnum[1:])
            num_spoken = f"{first} {verbalize_cardinal(rem)}"
    elif len(fnum) == 4:
        if fnum[2] == "0" and fnum[3] != "0":
            num_spoken = f"{verbalize_cardinal(int(fnum[:2]))} oh {ONES[int(fnum[3])]}"
        elif n % 100 == 0:
            num_spoken = verbalize_cardinal(n)
        else:
            p1 = verbalize_cardinal(int(fnum[:2]))
            p2 = verbalize_cardinal(int(fnum[2:]))
            num_spoken = f"{p1} {p2}"
    else:
        num_spoken = verbalize_cardinal(n)
    return f"{al_spoken} {num_spoken}"


def verbalize_model_code_span(
    raw_span: str,
    config: NormalizerConfig,
) -> tuple[str, list[NormalizationWarning], bool]:
    """Verbalizes model codes: RT-AX88U -> R T A X eighty-eight U, WH-1000XM4 -> W H one thousand X M four."""
    clean = raw_span.strip()
    parts = clean.split("-")
    spoken_parts: list[str] = []
    use_and = config.use_and_in_hundreds or False

    for part in parts:
        chunks = re.findall(r"[A-Za-z]+|\d+", part)
        part_spoken: list[str] = []
        for chunk in chunks:
            if chunk.isdigit():
                part_spoken.append(verbalize_cardinal(int(chunk), use_and=use_and))
            else:
                part_spoken.append(" ".join(chunk.upper()))
        spoken_parts.append(" ".join(part_spoken))

    return " ".join(spoken_parts), [], False


def verbalize_cue_code(
    raw: str,
    cfg: NormalizerConfig,
    code_str: str,
    cue: str,
) -> str:
    """Verbalizes codes/digits following cues like OTP, PIN, ZIP, tracking, etc."""
    has_alpha = any(c.isalpha() for c in code_str)
    zero_word = "zero" if has_alpha else (cfg.spoken_leading_zeros or ("zero" if cfg.locale == "en-IN" else "oh"))

    parts: list[str] = []
    for ch in code_str:
        if ch in ("-", "_"):
            parts.append("dash")
        elif ch == "0":
            parts.append(zero_word)
        elif ch.isdigit():
            parts.append(ONES[int(ch)])
        else:
            parts.append(ch.upper())
    return " ".join(parts)
