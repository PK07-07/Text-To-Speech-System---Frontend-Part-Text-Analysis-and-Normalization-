"""Verification script for Round 3 hardening in text_frontend.

Checks all 10 fixes:
For each fix: original realistic call example + 3-4 variants.
Prints input -> expected -> actual -> [PASS/FAIL].
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer

norm_us = TextNormalizer(NormalizerConfig.for_locale("en-US"))
norm_in = TextNormalizer(NormalizerConfig.for_locale("en-IN"))

CASES = [
    # Fix 1: '#' after cue word reads 'number' + individual digits; bare #1 keeps 'number one'
    (
        "Fix 1",
        "I am calling about order #49281 placed on Sept. 12.",
        "I am calling about order number four nine two eight one placed on September twelfth.",
        norm_us,
    ),
    (
        "Fix 1",
        "Please check ticket #10294 today.",
        "Please check ticket number one oh two nine four today.",
        norm_us,
    ),
    (
        "Fix 1",
        "Invoice #8831 is now overdue.",
        "Invoice number eight eight three one is now overdue.",
        norm_us,
    ),
    (
        "Fix 1",
        "Reference #5019 confirmed.",
        "Reference number five oh one nine confirmed.",
        norm_us,
    ),
    (
        "Fix 1",
        "Winner is #1 always.",
        "Winner is number one always.",
        norm_us,
    ),

    # Fix 2: Digits following endings/last four read individual digits with 'oh' in en-US
    (
        "Fix 2",
        "My routing number ends in 4390 and routing is 021000021.",
        "My routing number ends in four three nine oh and routing is oh two one oh oh oh oh two one.",
        norm_us,
    ),
    (
        "Fix 2",
        "The card ending in 8105 was charged.",
        "The card ending in eight one oh five was charged.",
        norm_us,
    ),
    (
        "Fix 2",
        "Please verify your last four digits: 9021.",
        "Please verify your last four digits: nine oh two one.",
        norm_us,
    ),
    (
        "Fix 2",
        "Account ends in 0042.",
        "Account ends in oh oh four two.",
        norm_us,
    ),

    # Fix 3: Blood Pressure & General Slash Pairs
    (
        "Fix 3",
        "My blood pressure reading was 120/80 mmHg this morning.",
        "My blood pressure reading was one twenty over eighty millimeters of mercury this morning.",
        norm_us,
    ),
    (
        "Fix 3",
        "Recorded BP of 135/85 today.",
        "Recorded B P of one thirty-five over eighty-five today.",
        norm_us,
    ),
    (
        "Fix 3",
        "Patient blood pressure is 110/70.",
        "Patient blood pressure is one ten over seventy.",
        norm_us,
    ),
    (
        "Fix 3",
        "The ratio was 15/28 in the test.",
        "The ratio was fifteen over twenty-eight in the test.",
        norm_us,
    ),
    (
        "Fix 3",
        "Add 3/4 cup flour.",
        "Add three fourths cup flour.",
        norm_us,
    ),

    # Fix 4: Month/Day without year & 24/7 idiom
    (
        "Fix 4",
        "Let us meet on Monday, 10/28 from 9-5 at HQ room 302.",
        "Let us meet on Monday, October twenty-eighth from nine to five at H Q room three hundred two.",
        norm_us,
    ),
    (
        "Fix 4",
        "Event is on 11/15 next week.",
        "Event is on November fifteenth next week.",
        norm_us,
    ),
    (
        "Fix 4",
        "Report dated 12/05 received.",
        "Report dated December fifth received.",
        norm_us,
    ),
    (
        "Fix 4",
        "Deliver by Friday, 4/18.",
        "Deliver by Friday, April eighteenth.",
        norm_us,
    ),
    (
        "Fix 4",
        "Store is open 24/7 daily.",
        "Store is open twenty-four seven daily.",
        norm_us,
    ),

    # Fix 5: Boundary Gluing Invariant (numbers attached to words read as cardinals unless code cue applies)
    (
        "Fix 5",
        "Batch 54units.",
        "Batch fifty-four units.",
        norm_us,
    ),
    (
        "Fix 5",
        "Val 100items.",
        "Val one hundred items.",
        norm_us,
    ),
    (
        "Fix 5",
        "A total of 1500steps.",
        "A total of one thousand five hundred steps.",
        norm_us,
    ),
    (
        "Fix 5",
        "Score 10-20pts.",
        "Score ten-twenty pts.",
        norm_us,
    ),

    # Fix 6: Attributive Singular Currency and Units
    (
        "Fix 6",
        "Is baggage over 50 lbs subject to a $75 fee?",
        "Is baggage over fifty pounds subject to a seventy-five dollar fee?",
        norm_us,
    ),
    (
        "Fix 6",
        "We went on a 10-minute walk.",
        "We went on a ten-minute walk.",
        norm_us,
    ),
    (
        "Fix 6",
        "He took a 50 mile drive.",
        "He took a fifty mile drive.",
        norm_us,
    ),
    (
        "Fix 6",
        "She handed me a 20 dollar bill.",
        "She handed me a twenty dollar bill.",
        norm_us,
    ),
    (
        "Fix 6",
        "The fee was $75 in total.",
        "The fee was seventy-five dollars in total.",
        norm_us,
    ),

    # Fix 7: Medical and Time Units
    (
        "Fix 7",
        "Patient body temp was 99.4°F, down from 101.2 F yesterday.",
        "Patient body temp was ninety-nine point four degrees Fahrenheit, down from one hundred one point two degrees Fahrenheit yesterday.",
        norm_us,
    ),
    (
        "Fix 7",
        "Download speed is 450 Mbps, but latency is 85 ms.",
        "Download speed is four hundred fifty megabits per second, but latency is eighty-five milliseconds.",
        norm_us,
    ),
    (
        "Fix 7",
        "Delivery driver called from 555-0199 saying he is 10 mins away.",
        "Delivery driver called from five five five, oh one nine nine saying he is ten minutes away.",
        norm_us,
    ),
    (
        "Fix 7",
        "Fever measured 38.5 C this evening.",
        "Fever measured thirty-eight point five degrees Celsius this evening.",
        norm_us,
    ),
    (
        "Fix 7",
        "Pulse rate is 72 bpm.",
        "Pulse rate is seventy-two beats per minute.",
        norm_us,
    ),
    (
        "Fix 7",
        "Wait 45 sec please.",
        "Wait forty-five seconds please.",
        norm_us,
    ),
    (
        "Fix 7",
        "Flight duration was 3 hrs.",
        "Flight duration was three hours.",
        norm_us,
    ),

    # Fix 8: Model Codes (letters spelled, digit runs cardinalized, hyphens spaces)
    (
        "Fix 8",
        "My router model is RT-AX88U running firmware v3.0.0.4.",
        "My router model is R T A X eighty-eight U running firmware version three point zero point zero point four.",
        norm_us,
    ),
    (
        "Fix 8",
        "Bought headphones model WH-1000XM4 today.",
        "Bought headphones model W H one thousand X M four today.",
        norm_us,
    ),
    (
        "Fix 8",
        "Using old robot model RX-78.",
        "Using old robot model R X seventy-eight.",
        norm_us,
    ),
    (
        "Fix 8",
        "Apply WD-40 spray evenly.",
        "Apply W D forty spray evenly.",
        norm_us,
    ),

    # Fix 9: Flight Numbers and Airport Codes
    (
        "Fix 9",
        "I need a seat change for flight UA-402 from JFK to LAX.",
        "I need a seat change for flight U A four oh two from J F K to L A X.",
        norm_us,
    ),
    (
        "Fix 9",
        "Flight AA 1204 is departing at 6:45am on 11/15/2024.",
        "Flight A A twelve oh four is departing at six forty-five A M on November fifteenth, twenty twenty-four.",
        norm_us,
    ),
    (
        "Fix 9",
        "Departing from SFO to ORD.",
        "Departing from S F O to O R D.",
        norm_us,
    ),
    (
        "Fix 9",
        "Arrived at DEL via BOM.",
        "Arrived at D E L via B O M.",
        norm_in,
    ),
    (
        "Fix 9",
        "Booked flight DL 54 to ATL.",
        "Booked flight D L fifty-four to A T L.",
        norm_us,
    ),

    # Fix 10: Address & Title Abbreviations without Periods
    (
        "Fix 10",
        "I live on 5th Ave between 42nd and 43rd St.",
        "I live on fifth Avenue between forty-second and forty-third Street.",
        norm_us,
    ),
    (
        "Fix 10",
        "Turn left on Sunset Blvd near 8th Rd.",
        "Turn left on Sunset Boulevard near eighth Road.",
        norm_us,
    ),
    (
        "Fix 10",
        "Located at 100 Lincoln Hwy near Oak Ln.",
        "Located at one hundred Lincoln Highway near Oak Lane.",
        norm_us,
    ),
    (
        "Fix 10",
        "Meet Mr Rao and Ms Gupta at 200 Park Pkwy.",
        "Meet Mister Rao and Ms Gupta at two hundred Park Parkway.",
        norm_us,
    ),
    (
        "Fix 10",
        "House at 12 Elm Ct.",
        "House at twelve Elm Court.",
        norm_us,
    ),
]

passed = 0
failed = 0

print("=== Check Round 3 Hardening Verification ===")
for fix_tag, inp, expected, normalizer in CASES:
    res = normalizer.normalize(inp)
    actual = res.normalized_text
    ok = (actual == expected)
    status_str = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"[{fix_tag}] Input:    {inp}")
    print(f"       Expected: {expected}")
    print(f"       Actual:   {actual}")
    print(f"       Status:   {status_str}\n")
    assert ok, f"Mismatch in {fix_tag}:\nInput:    {inp}\nExpected: {expected}\nActual:   {actual}"

print(f"Summary: {passed} passed, {failed} failed out of {len(CASES)} cases.")
