"""Parametrized test suite for all Round 3 corpus cases and realistic calls.

Ensures every single test case from check_round3.py (10 fixes + variants) and
every entry from realistic_calls.json (40 telephony calls) has its own unique,
descriptive test ID in pytest.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer, normalize


# 1. All 49 test cases from check_round3.py
ROUND3_CASES = [
    # Fix 1: '#' after cue word reads 'number' + individual digits; bare #1 keeps 'number one'
    ("fix01_call_004_order_num", "I am calling about order #49281 placed on Sept. 12.", "I am calling about order number four nine two eight one placed on September twelfth.", "en-US"),
    ("fix01_ticket_num", "Please check ticket #10294 today.", "Please check ticket number one oh two nine four today.", "en-US"),
    ("fix01_invoice_num", "Invoice #8831 is now overdue.", "Invoice number eight eight three one is now overdue.", "en-US"),
    ("fix01_reference_num", "Reference #5019 confirmed.", "Reference number five oh one nine confirmed.", "en-US"),
    ("fix01_bare_num_one", "Winner is #1 always.", "Winner is number one always.", "en-US"),

    # Fix 2: Digits following endings/last four read individual digits with 'oh' in en-US
    ("fix02_call_007_routing_ends_in", "My routing number ends in 4390 and routing is 021000021.", "My routing number ends in four three nine oh and routing is oh two one oh oh oh oh two one.", "en-US"),
    ("fix02_card_ending_in", "The card ending in 8105 was charged.", "The card ending in eight one oh five was charged.", "en-US"),
    ("fix02_last_four_digits", "Please verify your last four digits: 9021.", "Please verify your last four digits: nine oh two one.", "en-US"),
    ("fix02_account_ends_in", "Account ends in 0042.", "Account ends in oh oh four two.", "en-US"),

    # Fix 3: Blood Pressure, Ratios, and Fractions
    ("fix03_call_011_bp_mmhg", "My blood pressure reading was 120/80 mmHg this morning.", "My blood pressure reading was one twenty over eighty millimeters of mercury this morning.", "en-US"),
    ("fix03_bp_abbrev", "Recorded BP of 135/85 today.", "Recorded B P of one thirty-five over eighty-five today.", "en-US"),
    ("fix03_bp_spelled", "Patient blood pressure is 110/70.", "Patient blood pressure is one ten over seventy.", "en-US"),
    ("fix03_ratio_cue", "The ratio was 15/28 in the test.", "The ratio was fifteen over twenty-eight in the test.", "en-US"),
    ("fix03_fraction_preserved", "Add 3/4 cup flour.", "Add three fourths cup flour.", "en-US"),

    # Fix 4: Month/Day Dates without Year
    ("fix04_call_015_meet_md", "Let us meet on Monday, 10/28 from 9-5 at HQ room 302.", "Let us meet on Monday, October twenty-eighth from nine to five at H Q room three hundred two.", "en-US"),
    ("fix04_prep_on_md", "Event is on 11/15 next week.", "Event is on November fifteenth next week.", "en-US"),
    ("fix04_dated_cue", "Report dated 12/05 received.", "Report dated December fifth received.", "en-US"),
    ("fix04_weekday_cue", "Deliver by Friday, 4/18.", "Deliver by Friday, April eighteenth.", "en-US"),
    ("fix04_idiom_24_7", "Store is open 24/7 daily.", "Store is open twenty-four seven daily.", "en-US"),

    # Fix 5: Boundary Gluing Invariant (numbers attached to words read as cardinals unless code cue applies)
    ("fix05_call_018_units_boundary", "Batch 54units.", "Batch fifty-four units.", "en-US"),
    ("fix05_items_boundary", "Val 100items.", "Val one hundred items.", "en-US"),
    ("fix05_steps_boundary", "A total of 1500steps.", "A total of one thousand five hundred steps.", "en-US"),
    ("fix05_pts_boundary", "Score 10-20pts.", "Score ten-twenty pts.", "en-US"),

    # Fix 6: Attributive Singular Currency and Units
    ("fix06_call_021_fee_attributive", "Is baggage over 50 lbs subject to a $75 fee?", "Is baggage over fifty pounds subject to a seventy-five dollar fee?", "en-US"),
    ("fix06_minute_walk", "We went on a 10-minute walk.", "We went on a ten-minute walk.", "en-US"),
    ("fix06_mile_drive", "He took a 50 mile drive.", "He took a fifty mile drive.", "en-US"),
    ("fix06_dollar_bill", "She handed me a 20 dollar bill.", "She handed me a twenty dollar bill.", "en-US"),
    ("fix06_predicate_plural", "The fee was $75 in total.", "The fee was seventy-five dollars in total.", "en-US"),

    # Fix 7: Medical and Time Units
    ("fix07_call_024_temp_fahrenheit", "Patient body temp was 99.4°F, down from 101.2 F yesterday.", "Patient body temp was ninety-nine point four degrees Fahrenheit, down from one hundred one point two degrees Fahrenheit yesterday.", "en-US"),
    ("fix07_call_025_speed_latency", "Download speed is 450 Mbps, but latency is 85 ms.", "Download speed is four hundred fifty megabits per second, but latency is eighty-five milliseconds.", "en-US"),
    ("fix07_call_026_mins_away", "Delivery driver called from 555-0199 saying he is 10 mins away.", "Delivery driver called from five five five, oh one nine nine saying he is ten minutes away.", "en-US"),
    ("fix07_celsius_unit", "Fever measured 38.5 C this evening.", "Fever measured thirty-eight point five degrees Celsius this evening.", "en-US"),
    ("fix07_bpm_unit", "Pulse rate is 72 bpm.", "Pulse rate is seventy-two beats per minute.", "en-US"),
    ("fix07_sec_unit", "Wait 45 sec please.", "Wait forty-five seconds please.", "en-US"),
    ("fix07_hrs_unit", "Flight duration was 3 hrs.", "Flight duration was three hours.", "en-US"),

    # Fix 8: Model Codes
    ("fix08_call_028_router_model", "My router model is RT-AX88U running firmware v3.0.0.4.", "My router model is R T A X eighty-eight U running firmware version three point zero point zero point four.", "en-US"),
    ("fix08_headphones_model", "Bought headphones model WH-1000XM4 today.", "Bought headphones model W H one thousand X M four today.", "en-US"),
    ("fix08_robot_model", "Using old robot model RX-78.", "Using old robot model R X seventy-eight.", "en-US"),
    ("fix08_spray_model", "Apply WD-40 spray evenly.", "Apply W D forty spray evenly.", "en-US"),

    # Fix 9: Flight Numbers and Airport Codes
    ("fix09_call_030_flight_airports", "I need a seat change for flight UA-402 from JFK to LAX.", "I need a seat change for flight U A four oh two from J F K to L A X.", "en-US"),
    ("fix09_call_031_flight_dep", "Flight AA 1204 is departing at 6:45am on 11/15/2024.", "Flight A A twelve oh four is departing at six forty-five A M on November fifteenth, twenty twenty-four.", "en-US"),
    ("fix09_airports_sfo_ord", "Departing from SFO to ORD.", "Departing from S F O to O R D.", "en-US"),
    ("fix09_airports_del_bom", "Arrived at DEL via BOM.", "Arrived at D E L via B O M.", "en-IN"),
    ("fix09_flight_short_num", "Booked flight DL 54 to ATL.", "Booked flight D L fifty-four to A T L.", "en-US"),

    # Fix 10: Address & Title Abbreviations without Periods
    ("fix10_call_033_ave_st", "I live on 5th Ave between 42nd and 43rd St.", "I live on fifth Avenue between forty-second and forty-third Street.", "en-US"),
    ("fix10_blvd_rd", "Turn left on Sunset Blvd near 8th Rd.", "Turn left on Sunset Boulevard near eighth Road.", "en-US"),
    ("fix10_hwy_ln", "Located at 100 Lincoln Hwy near Oak Ln.", "Located at one hundred Lincoln Highway near Oak Lane.", "en-US"),
    ("fix10_honorifics_pkwy", "Meet Mr Rao and Ms Gupta at 200 Park Pkwy.", "Meet Mister Rao and Ms Gupta at two hundred Park Parkway.", "en-US"),
    ("fix10_ct_abbr", "House at 12 Elm Ct.", "House at twelve Elm Court.", "en-US"),
]

# 2. Load all 40 calls from realistic_calls.json
DATA_FILE = Path(__file__).parent / "data" / "realistic_calls.json"
REALISTIC_CALLS = json.loads(DATA_FILE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("test_id", "input_text", "expected", "locale"),
    ROUND3_CASES,
    ids=[c[0] for c in ROUND3_CASES],
)
def test_round3_fix_corpus(test_id: str, input_text: str, expected: str, locale: str):
    """Verifies each Round 3 hardening test case individually."""
    res = normalize(input_text, locale=locale)
    assert res.normalized_text == expected, f"Failed {test_id} in {locale}"


@pytest.mark.parametrize(
    "call",
    REALISTIC_CALLS,
    ids=[c["id"] for c in REALISTIC_CALLS],
)
def test_realistic_calls_corpus(call: dict):
    """Verifies each realistic telephony call input individually."""
    cid = call["id"]
    inp = call["input"]
    exp = call["proposed_output"]
    loc = call.get("locale", "en-US")
    res = normalize(inp, locale=loc)
    assert res.normalized_text == exp, f"Failed {cid}: {inp} -> {res.normalized_text} != {exp}"
