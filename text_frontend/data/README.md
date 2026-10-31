# text_frontend Bundled Runtime Data

This directory contains standalone, bundled static data tables required for offline text analysis and normalization in `text_frontend`. All files in this directory are bundled with the wheel package distribution.

## Contents & Licensing

1. **`abbreviations.json`**
   - **Version**: 1.0.0
   - **Description**: Curated dictionary of English abbreviations, titles, honorifics, street suffixes, company forms, initialisms, and pronounceable acronyms.
   - **Source**: Curated for `text_frontend` from standard English orthographic and speech conventions.
   - **License**: MIT License (included in package root).

2. **`words.txt`**
   - **Version**: 1.0.0
   - **Description**: Standard English lexicon used for dictionary verification, all-caps normalization, and line-break hyphenation repair.
   - **Source**: Derived from public-domain English wordlists (SCOWL / WordNet public domain collections).
   - **License**: Public Domain / MIT License.

3. **`emoji_names.json`**
   - **Version**: 1.0.0
   - **Description**: Mapping of Unicode emoji sequences, flags, skin-tone modifiers, and common ASCII emoticons to standardized spoken English verbalizations.
   - **Source**: Based on Unicode Common Locale Data Repository (CLDR) emoji annotations.
   - **License**: Unicode Terms of Use / MIT License.

4. **`airports.json`**
   - **Version**: 1.0.0
   - **Description**: Top 150+ international IATA airport codes plus Indian regional hubs for TTS spelling disambiguation after flight cues.
   - **Source**: IATA standard airport coding tables and open flight schedules.
   - **License**: Public Domain / CC0.
