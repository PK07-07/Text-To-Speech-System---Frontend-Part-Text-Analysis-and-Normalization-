# Changelog

All notable changes to the `text_frontend` text normalization package are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.3] - 2026-10-31

### Added
- **Individual Corpus Parametrization**: Dedicated test suite `tests/test_round3_corpus.py` parametrizing all 49 cases from `check_round3.py` and all 40 calls from `tests/data/realistic_calls.json` with descriptive test IDs, expanding the test suite to 464 collected tests.
- **Unified Zero Word Rule**: One rule for all digit-by-digit readings: digit-only sequences use `spoken_leading_zeros` (default "oh" in en-US/en-GB, "zero" in en-IN); any code mixing letters and digits strictly uses "zero". Applied to phones, PINs, ZIPs, account numbers, passcodes (`passcode 839201#` -> "eight three nine two oh one pound" in en-US), order numbers, and mixed codes (`MED-90218-A` -> "M E D dash nine zero two one eight dash A").
- **Month/Day Date Cues Expansion**: Expanded `DATE_PREP_CUES` to include `deadline`, `due`, `by`, `until`, `before`, `after`, `from`, `through`, `between`, and month names within 3 words. Disambiguates `M/D` vs `D/M` dates (`due 3/4` in en-US -> "March fourth", en-GB -> "April third", with `AMBIGUOUS_DATE_ORDER` info warning; `from 3/4 to 3/9` -> "from March fourth to March ninth"). Preserves fractions (`Add 3/4 cup`, `1/2 cup`), idioms (`24/7`), and spaced slashes (`Option 1 / 2` -> "Option one slash two").
- **Boundary Gluing Invariant**: Numbers attached to following words verbalize as cardinals (`100items` -> "one hundred items", `3apples` -> "three apples", `50miles` -> "fifty miles") unless preceded by technical code cues. Added invariant assertions to 5,000 fuzz test iterations verifying letter-digit boundaries in both directions.
- **Coverage Hardening**: Reached 98% overall coverage with 100% on `unicode_utils.py`, `normalizer.py`, `number_rules.py`, `config.py`, and `data_loader.py`, 99% on `date_time_rules.py` and `symbol_rules.py`, and >95% on all remaining modules.
- **Gold Review Export**: Re-exported all unverified entries into 10 review batches (`gold_review_batch_01.csv` through `10.csv`) with decisions unverified.

---

## [0.4.2] - 2026-10-31

### Added
- **Cue `#` + Digits (Fix 1)**: `#` after cue words (`order`, `ticket`, `invoice`, `case`, `claim`, `reference`, `ref`, `confirmation`, `account`, `policy`, `member`) followed by digits reads "number" + individual digits (`order #49281` -> "order number four nine two eight one"). Bare `#1` keeps "number one".
- **Cue Words for Digits (Fix 2)**: Added `ends in`, `ending in`, `last four`, `last 4 digits` cues for reading individual digits with zero spoken as "oh" in US/GB (`routing number ends in 4390` -> "routing number ends in four three nine oh").
- **Blood Pressure & General Slash Pairs (Fix 3)**: Blood pressure expressions (`120/80 mmHg`, `BP of 135/85`) read "over" with 3-digit values paired (`one twenty over eighty millimeters of mercury`). General slash pairs read as fractions only when $A < B$ and $B \in \{2..10, 12, 16, 20, 32, 64, 100\}$, otherwise read as "over".
- **Month/Day Dates without Year (Fix 4)**: Dates formatted as `M/D` without year (`Monday, 10/28`) verbalize as month and ordinal (`Monday, October twenty-eighth`). Idiom `24/7` preserved as "twenty-four seven".
- **Boundary Gluing Invariant (Fix 5)**: Invariant enforced in assembler: transformation outputs never merge with adjacent alphanumeric characters; space automatically inserted outside transformed span preserving coordinate mapping.
- **Attributive Singular Currency & Units (Fix 6)**: Attributive position detection (preceded by article `a`, `an` or hyphen and directly preceding a noun) enforces singular forms (`a $75 fee` -> "a seventy-five dollar fee", `10-minute walk` -> "ten-minute walk", `a 50 mile drive` -> "a fifty mile drive").
- **Medical & Time Units (Fix 7)**: Added `mmHg`, `bpm`, `mg/dL`, `mcg`, `ms`, `ns`, `hr`, `hrs`, `min`, `mins`, `sec`, `secs`. Standalone `F`/`C` with temperature cues expands to `degrees Fahrenheit` / `degrees Celsius`.
- **Model Codes (Fix 8)**: Hyphenated product/model codes with uppercase letters and digits (`RT-AX88U`, `WH-1000XM4`, `RX-78`, `WD-40`) spell letter runs, cardinalize digit runs, and replace hyphens with spaces (`R T A X eighty-eight U`).
- **Airports & Flight Numbers (Fix 9)**: Packaged IATA airport database `text_frontend/data/airports.json` (top 150 IATA codes + Indian hubs). Flight numbers read in pairs (`UA-402` -> "U A four oh two", `AA 1204` -> "A A twelve oh four"). Airport codes read as individual letters after transit cues (`from JFK to LAX` -> "from J F K to L A X").
- **Address & Title Abbreviations without Periods (Fix 10)**: Street suffixes (`Ave`, `Blvd`, `Rd`, `Ln`, `Hwy`, `Pkwy`, `Ct`) expand after ordinals and proper nouns (`5th Ave between 42nd and 43rd St.` -> "fifth Avenue between forty-second and forty-third Street."). Titles without periods (`Mr Rao`, `Ms Gupta`) expand properly.
- **Round 3 Verification Script**: `check_round3.py` containing all 10 fixes with original realistic call examples plus 3-4 variants each (49 total test cases, 100% pass rate).
- **Comprehensive Test Coverage**: Statement coverage increased to 97% overall, with 100% statement and branch coverage on `number_rules.py`, `normalizer.py`, and `unicode_utils.py`.

---

## [0.4.1] - 2026-10-31

### Added
- **Single-Letter Attached Disambiguation (B1)**: Numbers attached to `A`, `B`, and `K` expand as units only in sentences with technical cue words (`current`, `circuit`, `fuse`, `draw`, `breaker`, `amp`, `battery` for `A`; `storage`, `file`, `memory`, `disk`, `data`, `size` for `B`; `temperature`, `kelvin` for `K`). Otherwise verbalized as alphanumeric designations (`Apt 4B` -> "Apt four B", `Unit 12A` -> "twelve A", `Seat 14C`, `Row 5A`, `Gate B7` -> "Gate B seven", `Terminal 2A` -> "Terminal two A"; `Circuit draw is 5A.` -> "five amperes").
- **Spoken Hex Literals (B2)**: Hexadecimal literals verbalized character-by-character (`0x1F` -> "zero x one F", `0xFF00` -> "zero x F F zero zero").
- **Cue-Word Digits & Alphanumeric Codes (B3)**: Individual digit reading after cues (`otp`, `pin`, `code`, `id`, `reference`, `confirmation`, `account number`, `order number`, `ticket`, `tracking`, `zip`, `pincode`, `card ending in`); alphanumeric codes spelled (`Your OTP is 482913.`, `Your PIN is 1234.`, `Account number 12345678.`, `Tracking 1Z999AA10123456784.`, `Confirmation code 7H4K9Q.`, `Card ending in 4417.`, `ZIP 90210.`, `PNR ABC123.`, `Flight AI 202 departs at 6:45 AM.`, `Open 24x7.`, `Your total is $1,249.99.`, `Press 1 for sales, 2 for support.`).
- **en-IN Telephony & Currency Expansions (B4)**: Support for `Rs.` / `INR` currency prefixes, trailing `/-` amounts (`Rs 500/-`, `₹500/-` -> "five hundred rupees"), Indian 5-5 phone grouping (`Call 98765 43210.` -> "nine eight seven six five, four three two one zero"), Indian pincode zero reading (`Pincode 500001.` -> zeros spoken as "zero"), address abbreviations (`Flat No. 5, 2nd Floor` -> "Flat number five, second floor"), and IST timezone (`6:30 pm IST` -> "six thirty P M I S T").
- **Automated Warning Catalog Verification (B5)**: Bidirectional contract test (`test_warning_codes.py`) asserting 100% parity between code warnings and README catalog (16 emitted codes, strictly typed severities `info`/`warning`/`error`).
- **Policy Standardizations (B6)**: Standardized `H:M:S` time readings (`3:15:30` -> "three fifteen and thirty seconds" across all styles), scripture citations (`Chapter 3:16` -> "Chapter three, sixteen"), and negative currencies (`-$10` and `($10)` -> "negative ten dollars").
- **Comprehensive Phone Edge Test Suite**: `check_phone_edge.py` with 32 test cases and JSON corpus `phone_edge_corpus.json`.

### Changed
- Fuzz testing updated to assert no input digit is silently lost without being spoken or reported in a warning span.

---

## [0.4.0] - 2026-10-31

### Added
- **Mathematical Exponent Handling**: Exponents formatted with carets (`x^2` -> "x squared", `x^3` -> "x cubed", `10^5` -> "ten to the fifth power") and Unicode superscript digits (`2⁴` -> "two to the fourth power").
- **Context-Sensitive Arithmetic Disambiguation**: Spaced operators (`-`, `/`) distinguish between ranges/fractions/scores (`pages 10 - 20`, `Score was 3 - 2`, `Option 1 / 2`) and arithmetic expressions (`10 - 3 = 7`, `20 / 4 = 5`, `what is 10 - 3`).
- **Math Comparison Operators**: Less-than (`<`) and greater-than (`>`) verbalization restricted to numeric or single-letter operands; plain text words and HTML tags preserved. Standalone `<3` safely handled as emoticon.
- **Emoticon Boundary Rules**: Emoticons (`:)`, `:(`, `;)` etc.) strictly require start/whitespace before and whitespace/punctuation/end after, avoiding false positives in filenames, URLs, time strings, and tech specs.
- **Symbol & Unit Collision Resolution**: Disambiguated `x` in hex (`0x1F`), multipliers (`3x faster`), and dimensions (`5x5 grid`). Added verbalization for micro-units and SI symbols (`µs` -> "microseconds", `Ω` -> "ohms", `µF` -> "microfarads", `µm` -> "micrometers").
- **Dashes & Ligatures**: Em dash (`—`) verbalized as pause comma; unspaced en dash between words (`New York–London flight`) verbalized as "to". Typographic ligatures (`ﬀ`, `ﬁ`, `ﬂ`, `ﬃ`, `ﬄ`, `ﬅ`, `ﬆ`) expanded while linguistic orthographic ligatures (`æ`, `œ`) are preserved.
- **Fuzz Testing Suite**: `tests/test_fuzz.py` with 5,000 randomized Unicode inputs validating crash resistance, alignment monotonicity, and absence of raw text leaks in warnings.
- **Idempotence Verification**: `tests/test_idempotence.py` testing 208 test cases confirming zero drift on second-pass normalization.
- **Realistic Phone Assistant Corpus**: `tests/data/realistic_calls.json` containing 40 realistic telephony inputs with unverified proposed outputs.
- **Gold Review Tooling**: `tools/gold_review.py` supporting `export` (UTF-8 BOM CSV batches) and `apply` for human audit workflows.

### Changed
- Performance optimization: Inlined interval comparison, module-level precompiled regexes, and markup trigger fast-path resulting in >219,000 chars/s throughput and ~0.33 ms sentence latency.
- Clamped previous transformation output spans when stripping trailing spaces before commas, guaranteeing strict span monotonicity.

---

## [0.3.0] - 2026-10-30

### Added
- **Abbreviation & Acronym Engine**: Contextual abbreviation expansion via packaged `abbreviations.json` and `words.txt`.
- **All-Caps & Screaming Snake Handling**: Line-level context and wordlist validation for lowercase vs spelled acronyms (`PLEASE CALL ME`, `MAX_BUFFER_SIZE`).
- **Slash Verbalization**: Fixed readings for standard expressions (`and/or`, `either/or`, `yes/no`, `he/she`, `N/A`) with configurable slash reading for technical terms.
- **Hashtags & Tech Terms**: Hashtag verbalization with CamelCase splitting (`#GoodMorning` -> "hashtag Good Morning") and acronym spelling (`#TTS` -> "hashtag T T S").
- **Packaged Data Assets**: Integrated `text_frontend/data/abbreviations.json` and `text_frontend/data/words.txt` via wheel package-data.

---

## [0.2.0] - 2026-10-30

### Added
- **Date & Time Normalization**: Comprehensive parsing of US/UK date formats (`3/4/2023`, `Sept. 5, 2023`), 12h/24h times, timezone acronyms (`3 PM IST`), and relative times (`2h 45m`).
- **Units of Measurement**: Metric and imperial conversions, compound units, speeds, temperatures (`-5 to 5 degrees`), and dimensions (`5ft 10in`).
- **Phone Numbers & Identifiers**: E.164, US national, UK, and Indian phone patterns, extension numbers, IP addresses, UUIDs, hex values, and flight codes.
- **Ranges & Scores**: Numerical ranges (`9-5`, `pages 10-20`) and athletic scores (`3-2`).

---

## [0.1.0] - 2026-10-29

### Added
- **Core Normalization Pipeline**: Single-pass assembler with deterministic resolution hierarchy.
- **Unicode Canonicalization**: NFC normalization, smart quote replacement, control character stripping, and character mapping tracking.
- **Numeric Normalization**: Cardinals, ordinals, decimals, percentages, and negative numbers.
- **Currency Support**: Multi-currency verbalization (USD, GBP, EUR, INR lakhs/crores, JPY), accounting negative formats, and malformed digit grouping detection.
- **Four-Digit Year Disambiguation**: Contextual cues (temporal cues, quantity cues, count nouns) for year vs cardinal distinction.
- **Span Alignment & Tracking**: Coordinate tracking mapping raw text to normalized text with strict monotonicity and zero raw-text leakage in warnings.
