"""Unit tests for abbreviations, acronyms, and initialisms (Phase 3 C3)."""

from __future__ import annotations

import pytest

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer
from tests.conftest import assert_transformation_invariants


@pytest.fixture(scope="module")
def normalizer() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


def test_titles_and_honorifics(normalizer: TextNormalizer):
    cases = [
        ("Mr. Smith arrived.", "Mister Smith arrived."),
        ("Mrs. Robinson called.", "Missus Robinson called."),
        ("Ms. Davis spoke.", "Ms Davis spoke."),
        ("Dr. Jekyll visited.", "Doctor Jekyll visited."),
        ("Prof. Oak teaches.", "Professor Oak teaches."),
        ("Rev. Martin led the service.", "Reverend Martin led the service."),
        ("Capt. Kirk in command.", "Captain Kirk in command."),
        ("Sgt. Pepper taught the band.", "Sergeant Pepper taught the band."),
        ("Lt. Dan listened.", "Lieutenant Dan listened."),
        ("Col. Sanders cooking.", "Colonel Sanders cooking."),
        ("Gen. Washington led.", "General Washington led."),
        ("Maj. Tom reported.", "Major Tom reported."),
        ("Gov. Brown announced.", "Governor Brown announced."),
        ("Sen. Collins voted.", "Senator Collins voted."),
        ("Rep. Lewis spoke.", "Representative Lewis spoke."),
        ("Pres. Lincoln delivered.", "President Lincoln delivered."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_undotted_titles_and_suffixes(normalizer: TextNormalizer):
    cases = [
        ("Mr Smith arrived.", "Mister Smith arrived."),
        ("Dr Watson helped.", "Doctor Watson helped."),
        ("Prof Plum played.", "Professor Plum played."),
        ("John Smith Jr. arrived.", "John Smith Junior arrived."),
        ("Robert Downey Jr is an actor.", "Robert Downey Junior is an actor."),
        ("Martin Luther King Jr. was a leader.", "Martin Luther King Junior was a leader."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_disambiguation_saint_vs_street(normalizer: TextNormalizer):
    # St. before a capitalized name -> Saint
    res_saint1 = normalizer.normalize("St. Jude Hospital")
    assert res_saint1.normalized_text == "Saint Jude Hospital"
    assert_transformation_invariants("St. Jude Hospital", res_saint1)

    res_saint2 = normalizer.normalize("Visiting St. Patrick Cathedral.")
    assert res_saint2.normalized_text == "Visiting Saint Patrick Cathedral."
    assert_transformation_invariants("Visiting St. Patrick Cathedral.", res_saint2)

    # St. after a street name or number -> Street
    res_street1 = normalizer.normalize("Meet me on 42nd St.")
    assert res_street1.normalized_text == "Meet me on forty-second Street."
    assert_transformation_invariants("Meet me on 42nd St.", res_street1)

    res_street2 = normalizer.normalize("Walk down Main St. please.")
    assert res_street2.normalized_text == "Walk down Main Street please."
    assert_transformation_invariants("Walk down Main St. please.", res_street2)

    res_street3 = normalizer.normalize("Headquarters on Wall St.")
    assert res_street3.normalized_text == "Headquarters on Wall Street."
    assert_transformation_invariants("Headquarters on Wall St.", res_street3)


def test_disambiguation_doctor_vs_drive(normalizer: TextNormalizer):
    # Dr. before capitalized name -> Doctor
    res_doc = normalizer.normalize("Call Dr. Jekyll now.")
    assert res_doc.normalized_text == "Call Doctor Jekyll now."
    assert_transformation_invariants("Call Dr. Jekyll now.", res_doc)

    # Dr. after a street name -> Drive
    res_dr1 = normalizer.normalize("He lives on Maple Dr.")
    assert res_dr1.normalized_text == "He lives on Maple Drive."
    assert_transformation_invariants("He lives on Maple Dr.", res_dr1)

    res_dr2 = normalizer.normalize("Turn onto Sunset Dr. and stop.")
    assert res_dr2.normalized_text == "Turn onto Sunset Drive and stop."
    assert_transformation_invariants("Turn onto Sunset Dr. and stop.", res_dr2)


def test_end_of_sentence_abbreviation_period(normalizer: TextNormalizer):
    # End of sentence: the period on etc. is preserved
    res_etc = normalizer.normalize("I bought apples, oranges, etc.")
    assert res_etc.normalized_text == "I bought apples, oranges, etcetera."
    assert_transformation_invariants("I bought apples, oranges, etc.", res_etc)

    # Followed by capital letter (new sentence)
    res_etc2 = normalizer.normalize("We bought books, pens, etc. Then we left.")
    assert res_etc2.normalized_text == "We bought books, pens, etcetera. Then we left."
    assert_transformation_invariants("We bought books, pens, etc. Then we left.", res_etc2)

    # Middle of sentence (followed by lowercase)
    res_etc3 = normalizer.normalize("Apples, oranges, etc. are tasty.")
    assert res_etc3.normalized_text == "Apples, oranges, etcetera are tasty."
    assert_transformation_invariants("Apples, oranges, etc. are tasty.", res_etc3)

    # Title before a name does NOT duplicate periods
    res_title = normalizer.normalize("He visited Dr. Smith.")
    assert res_title.normalized_text == "He visited Doctor Smith."
    assert_transformation_invariants("He visited Dr. Smith.", res_title)


def test_common_latin_abbreviations(normalizer: TextNormalizer):
    cases = [
        ("We provide fruit, e.g., apples and pears.", "We provide fruit, for example, apples and pears."),
        ("The main tool, i.e., the hammer.", "The main tool, that is, the hammer."),
        ("Ali vs. Frazier was legendary.", "Ali versus Frazier was legendary."),
        ("Ali vs Frazier in the ring.", "Ali versus Frazier in the ring."),
        ("It costs approx. 50 dollars.", "It costs approximately fifty dollars."),
        ("Contact the sales dept. today.", "Contact the sales department today."),
        ("Living in apt. 4.", "Living in apartment four."),
        ("The avg. score was high.", "The average score was high."),
        ("Acme Corp. was founded in 1990.", "Acme Corporation was founded in nineteen ninety."),
        ("XYZ Co. is growing.", "XYZ Company is growing."),
        ("Widget Inc. went public.", "Widget Incorporated went public."),
        ("Smith & Co. Ltd. expanded.", "Smith and Company Limited expanded."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_name_initials(normalizer: TextNormalizer):
    cases = [
        ("Books by J. K. Rowling are popular.", "Books by J K Rowling are popular."),
        ("Novel by F. Scott Fitzgerald.", "Novel by F Scott Fitzgerald."),
        ("Stories by George R. R. Martin.", "Stories by George R R Martin."),
        ("President John F. Kennedy gave a speech.", "President John F Kennedy gave a speech."),
        ("Essays by E. B. White.", "Essays by E B White."),
        ("Tales by H. G. Wells.", "Tales by H G Wells."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_initialisms_vs_acronyms(normalizer: TextNormalizer):
    # Initialisms spelled letter-by-letter
    cases_initialisms = [
        ("FBI headquarters", "F B I headquarters"),
        ("CIA operative", "C I A operative"),
        ("Write HTML code", "Write H T M L code"),
        ("Modern TTS system", "Modern T T S system"),
        ("Living in the USA", "Living in the U S A"),
        ("Visiting the UK", "Visiting the U K"),
        ("Member of the EU", "Member of the E U"),
        ("General Assembly of the UN", "General Assembly of the U N"),
        ("Cash from the ATM", "Cash from the A T M"),
        ("She is a VIP guest", "She is a V I P guest"),
        ("Meeting with the CEO", "Meeting with the C E O"),
        ("Discussion with the CTO", "Discussion with the C T O"),
        ("Report from the CFO", "Report from the C F O"),
        ("High-end GPU computing", "High-end G P U computing"),
        ("Multi-core CPU performance", "Multi-core C P U performance"),
    ]
    for raw, expected in cases_initialisms:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)

    # Dotted initialisms
    cases_dotted = [
        ("He lives in the U.S.A.", "He lives in the U S A."),
        ("Based in the U.K.", "Based in the U K."),
        ("Agent of the F.B.I.", "Agent of the F B I."),
        ("Working at the C.I.A.", "Working at the C I A."),
    ]
    for raw, expected in cases_dotted:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)

    # Pronounceable acronyms read as words (NOT spelled letter-by-letter)
    cases_acronyms = [
        ("NASA launched a rocket.", "NASA launched a rocket."),
        ("NATO allies met.", "NATO allies met."),
        ("UNESCO world heritage.", "UNESCO world heritage."),
        ("Research on AIDS treatments.", "Research on AIDS treatments."),
        ("Enter your secret PIN.", "Enter your secret PIN."),
        ("OPEC oil production.", "OPEC oil production."),
        ("Send the report ASAP.", "Send the report ASAP."),
    ]
    for raw, expected in cases_acronyms:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)


def test_mixed_alphanumeric_forms(normalizer: TextNormalizer):
    cases = [
        ("Focus on B2B marketing.", "Focus on B to B marketing."),
        ("The B2C platform grew.", "The B to C platform grew."),
        ("Decentralized P2P network.", "Decentralized P to P network."),
        ("Flying on an A320 today.", "Flying on an A three twenty today."),
        ("Boarding the B737 flight.", "Boarding the B seven thirty-seven flight."),
        ("Connected to 5G network.", "Connected to five G network."),
        ("Old 4G connection.", "Old four G connection."),
        ("Watch on a 4K display.", "Watch on a four K display."),
        ("Crisp 8K video resolution.", "Crisp eight K video resolution."),
        ("Streaming in 1080p quality.", "Streaming in ten eighty P quality."),
        ("Watch in 720p resolution.", "Watch in seven twenty P resolution."),
        ("Standard 480p format.", "Standard four eighty P format."),
    ]
    for raw, expected in cases:
        res = normalizer.normalize(raw)
        assert res.normalized_text == expected
        assert res.status == "success"
        assert_transformation_invariants(raw, res)
