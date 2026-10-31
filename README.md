# Text Analysis & Normalization Engine (`text_frontend`)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Runtime Dependencies](https://img.shields.io/badge/dependencies-stdlib--only-brightgreen.svg)](#key-architectural-invariants)
[![Test Suite](https://img.shields.io/badge/tests-464%20passing-brightgreen.svg)](#testing--verification)
[![Code Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen.svg)](#testing--verification)
[![Architecture](https://img.shields.io/badge/architecture-monotonic%20resolver-blueviolet.svg)](#core-architecture--pipeline)


A high-performance, standard-library-only Python 3.11+ English text analysis and normalization engine designed specifically for **Text-to-Speech (TTS) synthesis frontends**.

`text_frontend` ingests arbitrary English text—including informal conversational transcripts, telephony dialogue, financial statements, medical records, and structured markup—and deterministically converts non-standard words (NSWs) into fully verbalized, speakable English prose while computing exact, invertible character coordinate mappings for downstream acoustic models.

---

## Table of Contents
- [1. Where the Frontend Fits in TTS](#1-where-the-frontend-fits-in-tts)
- [2. Key Architectural Invariants](#2-key-architectural-invariants)
- [3. Core Architecture & Pipeline](#3-core-architecture--pipeline)
- [4. Installation & Setup](#4-installation--setup)
- [5. Quickstart & Integration Recipes](#5-quickstart--integration-recipes)
  - [Basic Normalization](#basic-normalization)
  - [Consuming Alignment Spans in G2P & Duration Models](#consuming-alignment-spans-in-g2p--duration-models)
  - [Locale-Specific Normalization (en-US, en-GB, en-IN)](#locale-specific-normalization-en-us-en-gb-en-in)
  - [Conversational Telephony Pattern](#conversational-telephony-pattern)
- [6. Supported Domains & Rules](#6-supported-domains--rules)
- [7. Configuration Catalog (`NormalizerConfig`)](#7-configuration-catalog-normalizerconfig)
- [8. Structured Diagnostic Catalog](#8-structured-diagnostic-catalog)
- [9. Benchmarks & SLA Performance](#9-benchmarks--sla-performance)
- [10. Repository Structure](#10-repository-structure)
- [11. Testing & Verification](#11-testing--verification)

---

## 1. Where the Frontend Fits in TTS

Downstream phonetic algorithms (e.g. CMUDict, eSpeak-NG), acoustic models (e.g. FastSpeech 2, VITS), and neural vocoders cannot process raw textual tokens like `$12.50`, `10/28`, `120/80 mmHg`, or `Dr. Smith`. Passing unnormalized tokens causes dictionary misses, hallucinated pronunciations, or engine crashes.

`text_frontend` provides the foundational first stage of the TTS pipeline:

```
+-----------------------------------------------------------------------------------------+
|                                END-TO-END TTS PIPELINE                                  |
+-----------------------------------------------------------------------------------------+
  1. Raw User Input:    "Dr. Smith bought 5kg of apples for $12.50 on 10/28."
           |
           v
  2. [text_frontend]    <-- THIS REPOSITORY
     - Validates UTF-8 encoding and length safety boundaries
     - Performs NFC Unicode canonicalization and ligature expansion
     - Resolves overlapping NSW candidates (dates, currency, units, titles)
     - Emits spoken prose: "Doctor Smith bought five kilograms of apples for twelve dollars
                           and fifty cents on October twenty-eighth."
     - Computes monotonic coordinate maps: (original_span <-> output_span)
           |
           v
  3. [G2P / Phonemizer]
     - Converts normalized words to phonemes (IPA / ARPAbet) with lexical stress markers
           |
           v
  4. [Acoustic Model / Duration Predictor] (e.g., FastSpeech 2, VITS, Tacotron 2)
     - Predicts pitch, energy, phoneme durations; generates mel-spectrogram frames
           |
           v
  5. [Neural Vocoder] (e.g., HiFi-GAN, WaveGlow, BigVGAN)
     - Synthesizes final 24kHz/48kHz audio waveform (.wav)
+-----------------------------------------------------------------------------------------+
```

---

## 2. Key Architectural Invariants

- **Zero Runtime Dependencies**: Written exclusively with Python 3.11+ standard library modules (`re`, `unicodedata`, `datetime`, `math`, `json`, `dataclasses`, `hashlib`). Zero external C/C++ extensions or third-party wheels required at runtime.
- **Cluster-Level Monotonic Coordinate Mapping**: Strict character and grapheme cluster-level coordinate tracking mapping every output word back to exact slices in the raw input text:
  $$e_i^{\mathrm{in}} \le s_{i+1}^{\mathrm{in}} \quad \text{and} \quad e_i^{\mathrm{out}} \le s_{i+1}^{\mathrm{out}}$$
  *(Guarantees monotonic non-overlapping chunk intervals: `chunk[i].original_span[1] <= chunk[i+1].original_span[0]` and `chunk[i].output_span[1] <= chunk[i+1].output_span[0]`)*
- **Deterministic Greedy Overlap Resolution**: Hierarchical precedence order resolving overlapping candidate spans:
  $$\mathrm{Priority}(C) = (\mathrm{len}(C), -\mathrm{rank}(C), -\mathrm{start}(C))$$
  *(Longest span match wins; equal-length ties resolve by category rank, followed by start index: `(-span_length, category_rank, start_index)`)*
- **Boundary Gluing Invariants**: Single-pass assembler guarantees that normalized replacement tokens never merge with adjacent alphanumeric characters in either direction (`100items` $\to$ `one hundred items`).
- **Zero Silent Digit Loss**: Malformed number groupings (`1,00,000` in `en-US` or `1,0000`) never silently discard digits; they emit structured diagnostics and verbalize every digit explicitly with literal separators (`one comma zero zero comma zero zero zero`).
- **Strict Privacy & Warning Contracts**:
  - `info`: Disambiguated by policy (e.g., standalone 4-digit years, date order, ambiguous units). Status remains `"success"`.
  - `warning` / `error`: Rule-level or schema anomalies (e.g., malformed grouping, invalid calendar dates). Downgrades status to `"partial"`.
  - `failed`: Reserved strictly for fatal safety boundaries (invalid UTF-8 bytes, lone surrogates, length limits, excessive expansion ratio).
  - **No raw input text is ever leaked into warning codes or messages.**

---

## 3. Core Architecture & Pipeline

```
Raw Input Text
      │
      ▼
┌──────────────────────────────────────────────┐
│ Stage 1: Input Validation & Safety Bounds    │ ──► UTF-8 decoding, length limit (1M chars), surrogate check
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ Stage 2: Unicode NFC Canonicalization        │ ──► NFC normalization, ligature expansion (ﬁ -> fi), C0 strip
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ Stage 3: Markup & Protected Span Extraction  │ ──► Protects SSML (<say-as>, <phoneme>), URLs, emails, code
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ Stage 4: Multi-Rank Candidate Generation     │ ──► 10-Rank extractors (dates, times, numbers, currency, units)
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ Stage 5: Greedy Non-Overlapping Resolver     │ ──► Longest-match interval scheduling with rank tie-breaking
└──────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────┐
│ Stage 6: Single-Pass Assembler & Coordinate  │ ──► Boundary gluing, spacing invariants, monotonic coordinate maps
└──────────────────────────────────────────────┘
      │
      ▼
NormalizationResult (normalized_text, transformations, spoken_chunks, status, warnings)
```

---

## 4. Installation & Setup

### Requirements
- **Python**: 3.11 or higher
- **Runtime Dependencies**: None (Standard Library only)

### Direct Installation
```bash
# Clone the repository
git clone https://github.com/PK07-07/Text-To-Speech-System---Frontend-Part-Text-Analysis-and-Normalization-.git
cd Text-To-Speech-System---Frontend-Part-Text-Analysis-and-Normalization-

# Optional: Build standalone wheel
python -m pip install --upgrade build
python -m build --wheel

# Install the wheel in your virtual environment
pip install dist/text_frontend-0.4.3-py3-none-any.whl
```

---

## 5. Quickstart & Integration Recipes

### Basic Normalization
```python
from text_frontend import normalize

result = normalize("Dr. Smith bought 3 items for $12.50 at 2:30pm.")
print(result.normalized_text)
# -> "Doctor Smith bought three items for twelve dollars and fifty cents at two thirty P M."

print(result.status)
# -> "success"
```

### Consuming Alignment Spans in G2P & Duration Models
Downstream acoustic models (e.g. FastSpeech 2) and interactive media players require mapping synthesized speech audio back to the original text characters:

```python
from text_frontend import normalize

raw_text = "Meet Dr. Smith at 2:30pm."
res = normalize(raw_text)

# Inspect exact coordinate transformations:
for t in res.transformations:
    orig_slice = raw_text[t.original_span[0] : t.original_span[1]]
    norm_slice = res.normalized_text[t.output_span[0] : t.output_span[1]]
    print(f"[{t.category:<12}] '{orig_slice}' ({t.original_span}) -> '{norm_slice}' ({t.output_span})")

# Output:
# [abbreviation] 'Dr.'    (5, 8)   -> 'Doctor'         (5, 11)
# [time        ] '2:30pm' (18, 24) -> 'two thirty P M' (21, 35)
```

### Locale-Specific Normalization (en-US, en-GB, en-IN)
```python
from text_frontend import normalize

# en-US: MDY dates, standard Western currency
r_us = normalize("Due 3/4 with $100 fee.", locale="en-US")
print(r_us.normalized_text)
# -> "Due March fourth with one hundred dollars fee."

# en-GB: DMY dates, British pounds, 'and' in hundreds
r_gb = normalize("Due 3/4 with £150 fee.", locale="en-GB")
print(r_gb.normalized_text)
# -> "Due April third with one hundred and fifty pounds fee."

# en-IN: Indian Lakh/Crore grouping, rupee currency
r_in = normalize("Total is Rs. 1,50,000/-.", locale="en-IN")
print(r_in.normalized_text)
# -> "Total is one lakh fifty thousand rupees."
```

### Conversational Telephony Pattern
In voice bots and automated telephony agents, robust fallback handling is essential:

```python
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer

telephony_config = NormalizerConfig.for_locale(
    "en-US",
    style="conversational",
    year_2000s_style="thousand",
    emoji_policy="verbalize",
    non_speech_sound_policy="verbalize",
    unresolved_policy="literal",
)
normalizer = TextNormalizer(telephony_config)

def prepare_tts_utterance(agent_response: str) -> str:
    """Normalize agent speech text into clean, speakable prose with safe error boundaries."""
    res = normalizer.normalize(agent_response)
    if res.status == "failed":
        return "I am sorry, there was an issue processing that statement."
    return res.normalized_text

print(prepare_tts_utterance("Your booking #AA-104 departs at 6:45am. Fare is $452.80."))
# -> "Your booking number AA-104 departs at six forty-five A M. Fare is four hundred fifty-two dollars and eighty cents."
```

---

## 6. Supported Domains & Rules

| Category | Examples | Normalization Output |
| :--- | :--- | :--- |
| **Cardinals** | `0`, `42`, `-5`, `1,000,000`, `1 000 000` | `"zero"`, `"forty-two"`, `"negative five"`, `"one million"` |
| **Accounting Negatives** | `($500)`, `(15%)`, `(42)` | `"negative five hundred dollars"`, `"negative fifteen percent"` |
| **Ordinals** | `1st`, `2nd`, `3rd`, `21st`, `100th` | `"first"`, `"second"`, `"third"`, `"twenty-first"`, `"one hundredth"` |
| **Decimals** | `3.14`, `0.005`, `-0.5`, `3.50` | `"three point one four"`, `"three point five zero"` |
| **Percentages** | `25%`, `-0.5%`, `10-15%` | `"twenty-five percent"`, `"ten to fifteen percent"` |
| **Years & Decades** | `1984`, `2000`, `2026`, `the 1980s`, `the '90s` | `"nineteen eighty-four"`, `"the nineteen eighties"` |
| **Currencies** | `$10`, `£5.50`, `€100M`, `₹1,00,000`, `¥500` | `"ten dollars"`, `"five pounds fifty"`, `"one lakh rupees"` |
| **Attributive Concord** | `a $75 fee`, `10-minute walk` | `"a seventy-five dollar fee"`, `"ten-minute walk"` |
| **Dates (M/D & ISO)** | `2026-03-04`, `03/04/2026`, `due 3/4` | `"March fourth, twenty twenty-six"`, `"due March fourth"` |
| **Times & Durations** | `3:15pm`, `12:00`, `00:00`, `2h 30m` | `"three fifteen P M"`, `"noon"`, `"midnight"`, `"two hours and thirty minutes"` |
| **Fractions & Ratios** | `1/2`, `3/4 tsp`, `2 1/3`, `16:9`, `3:1` | `"one half"`, `"three fourths teaspoon"`, `"sixteen to nine"` |
| **Units of Measure** | `10kg`, `5m`, `60mph`, `100km/h`, `100Ω`, `5A` | `"ten kilograms"`, `"five meters"`, `"one hundred ohms"`, `"five amperes"` |
| **Medical / Clinical** | `120/80 mmHg`, `pulse 72 bpm` | `"one twenty over eighty millimeters of mercury"` |
| **Telephony Cues** | `order #49281`, `ends in 4390`, `PIN 4092` | `"order number four nine two eight one"`, `"four three nine oh"` |
| **Phone Numbers** | `+1 (800) 555-0199`, `(212) 555-1234` | `"plus one, eight hundred, five five five, zero one nine nine"` |
| **Technical IDs & Hashes**| `commit 4a8f9b`, `sha deadbeef` | `"commit four a eight f nine b"`, `"sha d e a d b e e f"` |
| **Lexicon & Acronyms** | `COVID-19`, `AT&T`, `R&D`, `NASA`, `FBI`, `OK` | `"covid nineteen"`, `"A T and T"`, `"R and D"`, `"NASA"`, `"F B I"`, `"okay"` |
| **All-Caps & Casing** | `PLEASE CALL ME`, `MAX_BUFFER_SIZE` | `"please call me"`, `"max buffer size"` |
| **Hashtags & Slashes** | `#TTS`, `#GoodMorning`, `and/or`, `TCP/IP` | `"hashtag T T S"`, `"hashtag Good Morning"`, `"and or"`, `"T C P slash I P"` |
| **Exponents & Powers** | `x^2`, `x^3`, `10^5`, `2⁴`, `5²` | `"x squared"`, `"x cubed"`, `"ten to the fifth power"` |
| **Math Operators** | `2 + 2 = 4`, `10 - 3 = 7`, `10 < 20` | `"two plus two equals four"`, `"ten is less than twenty"` |
| **Attached Numbers** | `100items`, `3apples`, `50miles` | `"one hundred items"`, `"three apples"`, `"fifty miles"` |
| **Zero Word Rule** | Phone/ZIP `555-0199` vs Code `1Z00192A` | `'oh one nine nine'` vs `'one Z zero zero one nine two A'` |
| **Markup & SSML** | `<p><b>Hello</b></p>`, `<break time="1s"/>` | HTML/Markdown stripped; valid SSML tags preserved verbatim |

---

## 7. Configuration Catalog (`NormalizerConfig`)

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `locale` | `str` | `"en-US"` | BCP-47 locale code (`en-US`, `en-GB`, `en-IN`, `en-CA`, `en-AU`). |
| `style` | `Literal["formal", "conversational"]` | `"formal"` | Normalization style for numbers and times. |
| `year_2000s_style` | `Literal["thousand", "oh"]` | `"thousand"` | 2000-2009 style ("two thousand five" vs "twenty oh five"). |
| `accounting_mode` | `bool` | `False` | Treat parenthesized numbers `($500)` as negative currency/numbers. |
| `ssml_mode` | `bool` | `False` | Preserve valid SSML elements and attributes verbatim. |
| `word_slash_style` | `Literal["slash", "or"]` | `"slash"` | Verbalize unlisted word/word slashes as "slash" or "or". |
| `time_seconds_style` | `Literal["spoken", "clock"]` | `"spoken"` | Style for verbalizing seconds in clock times. |
| `unresolved_policy` | `Literal["literal", "skip", "error"]` | `"literal"` | Action on unparseable / malformed non-standard words. |
| `emoji_policy` | `Literal["drop", "verbalize", "pause", "preserve"]` | `"drop"` | Handling policy for Unicode emojis and emoticons. |
| `non_speech_sound_policy` | `Literal["drop", "verbalize", "pause", "preserve"]` | `"drop"` | Handling for transcripts like `[laughter]`, `(applause)`. |
| `direction_slice_policy` | `Literal["verbalize", "literal"]` | `"verbalize"` | Handling for slice indicators like `1/2` or `3/4`. |
| `custom_overrides` | `dict[str, str]` | `{}` | User-defined verbatim string replacement dictionary. |

---

## 8. Structured Diagnostic Catalog

Warnings never leak raw user input into logs and use strict three-tier severities:

| Warning Code | Severity | Category | Description |
| :--- | :--- | :--- | :--- |
| `AMBIGUOUS_DATE_ORDER` | `info` | Date/Time | Ambiguous date format (e.g. `03/04/2023`) resolved by locale default. |
| `AMBIGUOUS_STANDALONE_YEAR` | `info` | Number | 4-digit number (1100-2099) verbalized as year due to missing quantity cues. |
| `AMBIGUOUS_UNIT_CONTEXT` | `info` | Unit | Attached single-letter unit (e.g. 'm') resolved by context cues. |
| `CODE_BLOCK_DROPPED` | `info` | Markup | Fenced code block dropped by default policy. |
| `INVALID_CALENDAR_DATE` | `warning` | Date/Time | Calendar date is out of range or semantically invalid (e.g. `2024-02-31`). |
| `MALFORMED_NUMBER` | `warning` | Number | Malformed number format or invalid digit grouping for locale. |
| `MALFORMED_TIME` | `warning` | Date/Time | Clock time components out of bounds (e.g. `25:70`). |
| `NUMBER_OUT_OF_RANGE` | `warning` | Number | Number exceeds supported magnitude range. |
| `RESIDUAL_NSW_DETECTED` | `warning` | Normalizer | Unnormalized non-standard word detected in final output text. |
| `UNACCOUNTED_DIGIT` | `warning` | Normalizer | Raw input digit was not accounted for in normalized output. |
| `UNCLOSED_SCRIPT_TAG` | `warning` | Markup | Unclosed `<script>` tag detected and stripped. |
| `INVALID_INPUT_TYPE` | `error` | Safety | Input payload is not a string or bytes. |
| `INVALID_UTF8_ENCODING` | `error` | Safety | Input string failed UTF-8 byte boundary decoding. |
| `LENGTH_LIMIT_EXCEEDED` | `error` | Safety | Input length exceeded configured maximum character limit. |
| `LONE_SURROGATES_DETECTED` | `error` | Safety | Lone Unicode surrogate code points detected in input. |
| `EXPANSION_RATIO_EXCEEDED` | `error` | Safety | Output text expansion ratio exceeded maximum limit. |

---

## 9. Benchmarks & SLA Performance

Benchmarked on a single CPU core with uninstrumented Python 3.11:

| Benchmark Metric | Measured Performance | Local SLA Target | CI Runner SLA Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Typical Sentence (< 200 chars)** | **0.48 ms** | < 5.0 ms | < 25.0 ms | Exceeded SLA |
| **Paragraph (< 2,000 chars)** | **9.30 ms** | < 50.0 ms | < 200.0 ms | Exceeded SLA |
| **Processing Throughput** | **155,383 chars/s** | > 50,000 chars/s | > 10,000 chars/s | Exceeded SLA |

---

## 10. Repository Structure

```text
├── text_frontend/                                   # Core Package (Python 3.11+ Stdlib-Only)
│   ├── __init__.py                                  # Top-level exports: normalize, TextNormalizer
│   ├── config.py                                    # NormalizerConfig, locale defaults, content hashing
│   ├── validation.py                                # Step 0: UTF-8, length, surrogate, expansion validation
│   ├── unicode_utils.py                             # 3-Pass Unicode canonicalization & coordinate tracking
│   ├── markup_parser.py                             # HTML/Markdown stripping & SSML protection
│   ├── number_rules.py                              # Cardinals, ordinals, decimals, Indian Lakh/Crore grouping
│   ├── currency_rules.py                            # ISO currencies, accounting negatives, attributive concord
│   ├── date_time_rules.py                           # ISO, MDY/DMY dates, M/D dates without year, 12h/24h timestamps
│   ├── unit_rules.py                                # SI, imperial, technical cue disambiguation (5A vs 4B)
│   ├── identifier_rules.py                          # Telephony, E.164 phones, UUIDs, git hashes, serials
│   ├── abbreviation_rules.py                        # Title/street expansions, Latin, all-caps casing
│   ├── symbol_rules.py                              # Math operators, inequalities, hashtags, emojis
│   ├── normalizer.py                                # 10-Rank greedy interval resolver & single-pass assembler
│   ├── data_loader.py                               # Lazy, thread-safe linguistic asset loader
│   └── data/                                        # Internal Linguistic Data Assets
│       ├── abbreviations.json                       # Curated abbreviation expansions and context rules
│       ├── words.txt                                # Standard English lexicon for compound & casing validation
│       ├── emoji_names.json                         # Unicode CLDR emoji names
│       └── airports.json                            # IATA airport code expansions
│
├── tests/                                           # Formal Pytest Test Suite (464 Passing Tests)
│   ├── test_numbers.py                              # Cardinals, ordinals, Western/Indian grouping
│   ├── test_currency.py                             # Currencies, ranges, accounting negatives
│   ├── test_date_time.py                            # Dates, times, ambiguous M/D resolution
│   ├── test_units.py                                # SI, imperial, single-letter unit cues
│   ├── test_identifiers.py                          # Phone numbers, git commits, PINs, UUIDs
│   ├── test_abbreviations.py                        # Titles, Latin, uppercase handling
│   ├── test_symbols.py                              # Math operators, hashtags, typography
│   ├── test_markup.py                               # HTML stripping, SSML element preservation
│   ├── test_normalizer.py                           # Single-pass assembly, boundary gluing
│   ├── test_alignment.py                            # Monotonic coordinate mapping invariants
│   ├── test_fuzz.py                                 # 5,000 property fuzzing iterations
│   ├── test_benchmarks.py                           # Latency and throughput benchmark SLA tests
│   ├── test_security.py                             # UTF-8 decoding, lone surrogates, length limits
│   └── data/                                        # Gold evaluation corpora & realistic call logs
│
├── tools/                                           # Engineering Utilities
│   ├── generate_report.py                           # Generator for teammate Word documentation (.docx)
│   └── gold_review.py                               # Corpus curation and review helper
│
├── Text_To_Speech_Frontend_Comprehensive_Guide.docx # Comprehensive Word Guide for Downstream Teammates
├── pyproject.toml                                   # Hatchling packaging configuration
├── CHANGELOG.md                                     # Detailed version history and phase milestones
├── my_sentences.txt                                 # Sample conversational sentences for batch testing
├── try_lines.py                                     # Interactive CLI utility for evaluating custom text
└── README.md                                        # This documentation
```

---

## 11. Testing & Verification

Run the complete test suite directly with `pytest`:

```bash
# Run all 464 unit, integration, and fuzz tests
pytest tests -v

# Run with test coverage report
pytest --cov=text_frontend --cov-report=term-missing tests/

# Run latency and throughput benchmarks
pytest tests/test_benchmarks.py -v -s

# Interactive testing on your own sentences:
python try_lines.py
```

---

## Technical Report for Downstream Teammates

For teammates working on G2P, acoustic duration models, or vocoders, a comprehensive standalone Word guide is included in the root directory:
- **File**: [`Text_To_Speech_Frontend_Comprehensive_Guide.docx`](Text_To_Speech_Frontend_Comprehensive_Guide.docx)
- **Topics**: Downstream pipeline architecture, alignment span consumption recipes, phoneme dictionary preparation, and error boundary patterns.
