"""Verification script for telephony and phone edge cases (Section B fixes)."""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


def run_phone_edge_checks() -> int:
    norm_us = TextNormalizer(NormalizerConfig.for_locale("en-US"))
    norm_in = TextNormalizer(NormalizerConfig.for_locale("en-IN"))

    dollar = "$"

    test_cases = [
        # B1. Ambiguous single-letter units
        ("B1", norm_us, "Apt 4B", "Apt four B"),
        ("B1", norm_us, "Unit 12A", "Unit twelve A"),
        ("B1", norm_us, "Seat 14C", "Seat fourteen C"),
        ("B1", norm_us, "Row 5A", "Row five A"),
        ("B1", norm_us, "Gate B7", "Gate B seven"),
        ("B1", norm_us, "Terminal 2A", "Terminal two A"),
        ("B1", norm_us, "Circuit draw is 5A.", "Circuit draw is five amperes."),

        # B2. Hex literals
        ("B2", norm_us, "0x1F", "zero x one F"),
        ("B2", norm_us, "0xFF00", "zero x F F zero zero"),

        # B3. Cue-word digits and codes
        ("B3", norm_us, "Your OTP is 482913.", "Your O T P is four eight two nine one three."),
        ("B3", norm_us, "Your PIN is 1234.", "Your PIN is one two three four."),
        ("B3", norm_us, "Account number 12345678.", "Account number one two three four five six seven eight."),
        (
            "B3",
            norm_us,
            "Order number 100245 and tracking 1Z999AA10123456784.",
            "Order number one zero zero two four five and tracking one Z nine nine nine A A one zero one two three four five six seven eight four.",
        ),
        ("B3", norm_us, "Confirmation code 7H4K9Q.", "Confirmation code seven H four K nine Q."),
        ("B3", norm_us, "Card ending in 4417.", "Card ending in four four one seven."),
        ("B3", norm_us, "ZIP 90210.", "ZIP nine oh two one oh."),
        ("B3", norm_us, "PNR ABC123.", "P N R A B C one two three."),
        ("B3", norm_us, "Flight AI 202 departs at 6:45 AM.", "Flight A I two oh two departs at six forty-five A M."),
        ("B3", norm_us, "Open 24x7.", "Open twenty-four seven."),
        ("B3", norm_us, f"Your total is {dollar}1,249.99.", "Your total is one thousand two hundred forty-nine dollars and ninety-nine cents."),
        ("B3", norm_us, "Press 1 for sales, 2 for support.", "Press one for sales, two for support."),

        # B4. en-IN checks
        ("B4", norm_in, "Pay Rs. 1,50,000 by 5th March.", "Pay one lakh fifty thousand rupees by March fifth."),
        ("B4", norm_in, "Rs 500/-", "five hundred rupees"),
        ("B4", norm_in, "₹500/-", "five hundred rupees"),
        ("B4", norm_in, "Pincode 500001.", "Pincode five zero zero zero zero one."),
        ("B4", norm_in, "Call 98765 43210.", "Call nine eight seven six five, four three two one zero."),
        ("B4", norm_in, "Mr. Rao, Flat No. 5, 2nd Floor.", "Mister Rao, Flat number five, second floor."),
        ("B4", norm_in, "Meet at 6:30 pm IST.", "Meet at six thirty P M I S T."),

        # B6. Policy decisions
        ("B6", norm_us, "3:15:30", "three fifteen and thirty seconds"),
        ("B6", norm_us, "Chapter 3:16.", "Chapter three, sixteen."),
        ("B6", norm_us, f"-{dollar}10", "negative ten dollars"),
        ("B6", norm_us, f"({dollar}10)", "negative ten dollars"),
    ]

    print(f"Running check_phone_edge.py verification ({len(test_cases)} cases)...")
    passed = 0
    failed = 0

    for i, (cat, normalizer, inp, expected) in enumerate(test_cases, 1):
        res = normalizer.normalize(inp)
        actual = res.normalized_text
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"[{i:02d}/{len(test_cases)}] {cat}: {inp}")
        print(f"  Input:    {inp}")
        print(f"  Expected: {expected}")
        print(f"  Actual:   {actual}")
        print(f"  Status:   {status}")
        if status == "FAIL":
            print(f"  DIFFERENCE: expected != actual")
        print()

    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} cases.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_phone_edge_checks())
