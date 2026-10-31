# text_frontend

A standalone, standard-library-only Python 3.11+ English text analysis and normalization package designed specifically for text-to-speech (TTS) synthesis frontends.

---

## 1. Overview & Core Philosophy

`text_frontend` ingests arbitrary English text—including informal conversational transcripts, technical logs, financial statements, and structured markup—and deterministically converts non-standard words (NSWs) into fully verbalized, speakable English prose.

### Key Architectural Invariants
- **Zero Runtime Dependencies**: Written exclusively with Python 3.11+ standard library modules (`re`, `unicodedata`, `datetime`, `math`, `json`, `dataclasses`, `hashlib`).
- **Cluster-Level Monotonic Coordinate Mapping**: Strict character and grapheme cluster-level coordinate tracking mapping output chunks back to exact slices in the raw input text:
  $$e_i^{\mathrm{in}} \le s_{i+1}^{\mathrm{in}} \quad \text{and} \quad e_i^{\mathrm{out}} \le s_{i+1}^{\mathrm{out}}$$
  *(Guarantees monotonic non-overlapping chunk intervals: `chunk[i].original_span[1] <= chunk[i+1].original_span[0]` and `chunk[i].output_span[1] <= chunk[i+1].output_span[0]`)*
- **Deterministic Greedy Overlap Resolution**: Hierarchical precedence order resolving overlapping candidates deterministically:
  $$\mathrm{Priority}(C) = (\mathrm{len}(C), -\mathrm{rank}(C), -\mathrm{start}(C))$$
  *(Longest span match wins; equal-length ties resolve by category rank, followed by start index: `(-span_length, category_rank, start_index)`)*
- **Strict Warning & Status Contracts**:
  - `info`: Disambiguated by policy (e.g. standalone 4-digit years, date order, ambiguous units). Never downgrades status.
  - `warning` / `error`: Rule-level or schema anomalies (e.g. malformed grouping `1,00,000` in en-US, invalid dates). Downgrades status to `"partial"`.
  - `failed`: Reserved strictly for fatal Step 0 safety boundaries (invalid UTF-8 bytes, lone surrogates, input length limit, excessive expansion ratio).
  - No raw input text is ever leaked into warning codes or messages.

---

## 2. Installation

`text_frontend` has zero third-party runtime dependencies. Build and install directly via standard tooling:

```bash
# Build standalone wheel
python -m build --wheel

# Install in any Python 3.11+ environment
pip install dist/text_frontend-0.4.0-py3-none-any.whl
```

---

## 3. Quickstart & Phone Assistant Integration

### Basic Normalization
```python
from text_frontend.normalizer import TextNormalizer, normalize

# Convenience top-level normalize function
result = normalize("Dr. Smith bought 3 items for $12.50 at 2:30pm.")
print(result.normalized_text)
# -> "Doctor Smith bought three items for twelve dollars and fifty cents at two thirty P M."
```

### Integrating
```python
from text_frontend import normalize

res = normalize("Pay $150 by 10/24.")
if res.status != "failed":
    for t in res.transformations:
        print(f"{t.rule_id}: {t.original_text!r} -> {t.replacement!r}")
```

### Phone Assistant / Telephony Integration Example
In voice assistants, speech-to-text outputs or agent generation often contain messy conversational tokens, confirmation codes, street addresses, and currency. Here is a production-grade telephony integration pattern:

```python
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer

# Create conversational telephony configuration
telephony_config = NormalizerConfig.for_locale(
    "en-US",
    style="conversational",
    year_2000s_style="thousand",
    emoji_policy="verbalize",
    non_speech_sound_policy="verbalize",
    unresolved_policy="literal",
)
normalizer = TextNormalizer(telephony_config)

def prepare_tts_prompt(agent_response: str) -> str:
    """Normalize agent speech text into clean, speakable prose."""
    result = normalizer.normalize(agent_response)
    if result.status == "failed":
        # Log critical boundary failure and fallback to safe utterance
        return "I am sorry, but there was an error processing the text."
    return result.normalized_text

# Example telephony responses:
prompt1 = "Your booking #AA-104 departs at 6:45am on 11/15/2024. Total fare is $452.80."
print(prepare_tts_prompt(prompt1))
# -> "Your booking number AA-104 departs at six forty-five A M on November fifteenth, twenty twenty-four. Total fare is four hundred fifty-two dollars and eighty cents."

prompt2 = "Please call (415) 555-0199 ext. 402 between 9-5."
print(prepare_tts_prompt(prompt2))
# -> "Please call plus one four one five five five five zero one nine nine extension four hundred two between nine to five."
```

---

## 4. Configuration Catalog (`NormalizerConfig`)

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `locale` | `str` | `"en-US"` | BCP-47 locale code (`en-US`, `en-GB`, `en-IN`, etc.). |
| `style` | `Literal["formal", "conversational"]` | `"formal"` | Normalization style for numbers and times. |
| `year_2000s_style` | `Literal["thousand", "oh"]` | `"thousand"` | 2000-2009 year style ("two thousand five" vs "twenty oh five"). |
| `accounting_mode` | `bool` | `False` | Treat parenthesized numbers `($500)` as negative currency/numbers. |
| `ssml_mode` | `bool` | `False` | Preserve valid SSML elements and attributes verbatim. |
| `word_slash_style` | `Literal["slash", "or"]` | `"slash"` | Verbalize unlisted word/word slashes as "slash" or "or". |
| `time_seconds_style` | `Literal["spoken", "clock"]` | `"spoken"` | Style for verbalizing seconds in clock times. |
| `unresolved_policy` | `Literal["literal", "skip", "error"]` | `"literal"` | Action on unparseable / malformed non-standard words. |
| `emoji_policy` | `Literal["drop", "verbalize", "pause", "preserve"]` | `"drop"` | Handling policy for Unicode emojis and emoticons. |
| `non_speech_sound_policy` | `Literal["drop", "verbalize", "pause", "preserve"]` | `"drop"` | Handling for transcripts like `[laughter]`, `(applause)`. |
| `direction_slice_policy` | `Literal["verbalize", "literal"]` | `"verbalize"` | Handling for slice indicators like `1/2` or `3/4`. |
| `custom_overrides` | `dict[str, str]` | `{}` | User-defined verbatim string replacement dictionary. |

All configuration fields are hashed into an immutable 8-character identifier via `config.content_hash()`.

---

## 5. Warning Code Catalog

Warnings are emitted during normalization without halting execution. All warnings strictly omit raw input text.

| Warning Code | Severity | Category | Description |
| :--- | :--- | :--- | :--- |
| `AMBIGUOUS_DATE_ORDER` | `info` | Date/Time | Ambiguous date format (e.g. `03/04/2023`) resolved by locale default. |
| `AMBIGUOUS_STANDALONE_YEAR` | `info` | Number | 4-digit number (1100-2099) verbalized as year due to missing quantity cues. |
| `AMBIGUOUS_UNIT_CONTEXT` | `info` | Unit | Attached single-letter unit (e.g. 'm') resolved by context cues. |
| `CODE_BLOCK_DROPPED` | `info` | Markup | Fenced code block dropped by default policy. |
| `EXPANSION_RATIO_EXCEEDED` | `error` | Safety Boundary | Output text expansion ratio exceeded maximum limit. |
| `INVALID_CALENDAR_DATE` | `warning` | Date/Time | Calendar date is out of range or semantically invalid (e.g. `2024-02-31`). |
| `INVALID_INPUT_TYPE` | `error` | Safety Boundary | Input payload is not a string or bytes. |
| `INVALID_UTF8_ENCODING` | `error` | Safety Boundary | Input string failed UTF-8 byte boundary decoding. |
| `LENGTH_LIMIT_EXCEEDED` | `error` | Safety Boundary | Input length exceeded configured maximum character limit. |
| `LONE_SURROGATES_DETECTED` | `error` | Safety Boundary | Lone Unicode surrogate code points detected in input. |
| `MALFORMED_NUMBER` | `warning` | Number | Malformed number format or invalid digit grouping for locale. |
| `MALFORMED_TIME` | `warning` | Date/Time | Clock time components out of bounds (e.g. `25:70`). |
| `NUMBER_OUT_OF_RANGE` | `warning` | Number | Number exceeds supported magnitude range. |
| `RESIDUAL_NSW_DETECTED` | `warning` | Normalizer | Unnormalized non-standard word detected in final output text. |
| `UNACCOUNTED_DIGIT` | `warning` | Normalizer | Raw input digit was not accounted for in normalized output. |
| `UNCLOSED_SCRIPT_TAG` | `warning` | Markup | Unclosed `<script>` tag detected and stripped. |

---

## 6. Overlap Resolution Hierarchy

When candidate rules produce overlapping spans, ties are broken strictly by **length** (longest span wins). Equal-length ties are resolved by category priority rank:

1. **Explicit Overrides** (Rank 1): Exact string replacements from `custom_overrides`.
2. **Protected Spans & SSML Tags** (Rank 2): Verbatim passthrough of URLs, email addresses, and SSML elements.
3. **Exact Lexicon Matches** (Rank 3): Domain terminology (`COVID-19`, `F-16`, `H2O`, `AT&T`, `P&L`, `R&D`, `Q&A`).
4. **Phone Numbers & Identifiers** (Rank 4): International phones, UUIDs, git commit hashes, product codes.
5. **Dates & Times** (Rank 5): Calendar dates, 12h/24h timestamps, durations.
6. **Composite Numeric** (Rank 6): Ranges (`10-20`), currencies (`$5-$10`), dimensions (`10x20`), scientific notation (`3.0 x 10^8`), unit combos.
7. **Specific Numeric** (Rank 7): Decimals, percentages, years, ordinals, bare integers, exponents, roots.
8. **Lexical** (Rank 8): Acronyms, abbreviations, title expansions, mixed letter-digit tokens.
9. **Symbols, Emojis & Operators** (Rank 9): Math operators (`+`, `-`, `*`, `/`, `=`), hashtags, typography, non-speech.
10. **Fallback** (Rank 10): Residual character handling.

---

## 7. Supported Domains & Rules

| Category | Examples | Normalization |
| :--- | :--- | :--- |
| **Cardinals** | `0`, `42`, `-5`, `1,000,000`, `1 000 000` | `"zero"`, `"forty-two"`, `"negative five"`, `"one million"` |
| **Accounting Negatives** | `($500)`, `(15%)`, `(42)` | `"negative five hundred dollars"`, `"negative fifteen percent"` |
| **Ordinals** | `1st`, `2nd`, `3rd`, `21st`, `100th` | `"first"`, `"second"`, `"third"`, `"twenty-first"`, `"one hundredth"` |
| **Decimals** | `3.14`, `0.005`, `-0.5`, `3.50` | `"three point one four"`, `"three point five zero"` |
| **Percentages** | `25%`, `-0.5%`, `10-15%` | `"twenty-five percent"`, `"ten to fifteen percent"` |
| **Years & Decades** | `1984`, `2000`, `2026`, `the 1980s`, `the '90s` | `"nineteen eighty-four"`, `"the nineteen eighties"` |
| **Currencies** | `$10`, `£5.50`, `€100M`, `₹1,00,000`, `¥500` | `"ten dollars"`, `"five pounds fifty"`, `"one lakh rupees"` |
| **Dates** | `2026-03-04`, `03/04/2026`, `Sept. 5, 2023` | `"March fourth, twenty twenty-six"`, `"September fifth, twenty twenty-three"` |
| **Times & Durations** | `3:15pm`, `12:00`, `00:00`, `2h 30m` | `"three fifteen P M"`, `"noon"`, `"midnight"`, `"two hours and thirty minutes"` |
| **Fractions & Ratios** | `1/2`, `3/4 tsp`, `2 1/3`, `16:9`, `3:1` | `"one half"`, `"three fourths teaspoon"`, `"sixteen to nine"` |
| **Units of Measure** | `10kg`, `5m`, `60mph`, `100km/h`, `100Ω`, `5A` | `"ten kilograms"`, `"five meters"`, `"one hundred ohms"`, `"five amperes"` |
| **Addresses & Tech IDs**| `123 Main St.`, `1600 Pennsylvania Ave.` | `"one twenty-three Main Street."`, `"sixteen hundred Pennsylvania Avenue."` |
| **Phone Numbers** | `+1 (800) 555-0199`, `(212) 555-1234` | `"plus one, eight hundred, five five five, zero one nine nine"` |
| **Git & Hashes** | `commit 4a8f9b`, `sha deadbeef` | `"commit four a eight f nine b"`, `"sha d e a d b e e f"` |
| **Lexicon & Acronyms** | `COVID-19`, `AT&T`, `R&D`, `NASA`, `FBI`, `OK` | `"covid nineteen"`, `"A T and T"`, `"R and D"`, `"NASA"`, `"F B I"`, `"okay"` |
| **All-Caps & Snake** | `PLEASE CALL ME`, `MAX_BUFFER_SIZE` | `"please call me"`, `"max buffer size"` |
| **Hashtags & Slashes** | `#TTS`, `#GoodMorning`, `and/or`, `TCP/IP` | `"hashtag T T S"`, `"hashtag Good Morning"`, `"and or"`, `"T C P slash I P"` |
| **Exponents & Powers** | `x^2`, `x^3`, `10^5`, `2⁴`, `5²` | `"x squared"`, `"x cubed"`, `"ten to the fifth power"`, `"two to the fourth power"` |
| **Math Arithmetic** | `2 + 2 = 4`, `10 - 3 = 7`, `20 / 4 = 5` | `"two plus two equals four"`, `"ten minus three equals seven"`, `"twenty divided by four equals five"` |
| **Math Inequalities** | `10 < 20`, `50 > 30`, `5 ≠ 10`, `±5` | `"ten is less than twenty"`, `"fifty is greater than thirty"` |
| **Ligatures & Dashes** | `A ﬁne ﬂight with æsthetic œvre`, `plan—bold` | `"A fine flight with aesthetic oeuvre"`, `"plan, bold"` |
| **Emojis & Emoticons** | `:)`, `:(`, `👋`, `👨‍👩‍👧` | Configurable: drop, verbalize, pause, or preserve |
| **Markup & SSML** | `<p><b>Hello</b></p>`, `<break time="1s"/>` | HTML/Markdown cleanly stripped; SSML preserved when `ssml_mode=True` |

---

## 8. Benchmarks & Latency

Performance measured on a single CPU core with uninstrumented Python 3.11:

| Metric | Target (Local) | Target (CI) | Measured Performance |
| :--- | :--- | :--- | :--- |
| **Sentence Latency (< 200 chars)** | < 5.0 ms | < 25.0 ms | **0.327 ms** |
| **Paragraph Latency (< 2,000 chars)** | < 50.0 ms | < 200.0 ms | **6.919 ms** |
| **Throughput** | > 50,000 chars/s | > 10,000 chars/s | **219,184 chars/s** |

---

## 9. Known Limitations & Scope Boundaries

1. **No Syntactic Parser / Part-of-Speech Tagger**: `text_frontend` deliberately operates without large neural POS taggers or syntactic parsers to remain strictly lightweight, stdlib-only, and fast.
2. **Polysemous Words Disambiguated by Context Cues**: Words such as `Dr.` (Doctor vs Drive) or `St.` (Saint vs Street) use deterministic surrounding keyword cues rather than full dependency parsing.
3. **English Locales Only**: Supported locales include `en-US`, `en-GB`, `en-CA`, `en-AU`, and `en-IN`. Multi-lingual non-English normalization is out of scope.
4. **No Grapheme-to-Phoneme (G2P) / Audio Synthesis**: This package normalizes non-standard words into standard English words. Phonemic transcription, IPA generation, acoustic modeling, and audio synthesis belong to downstream TTS stages.
5. **No Telephony Protocol / Audio Codec Code**: Focuses purely on textual speech frontend preprocessing.
