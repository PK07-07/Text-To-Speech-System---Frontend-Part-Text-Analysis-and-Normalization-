"""Tests for dates, times, durations, and calendar validation."""

from __future__ import annotations

import pytest
from text_frontend.config import NormalizerConfig
from text_frontend.normalizer import TextNormalizer


@pytest.fixture
def normalizer_us() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US"))


@pytest.fixture
def normalizer_gb() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-GB"))


@pytest.fixture
def normalizer_24h() -> TextNormalizer:
    return TextNormalizer(NormalizerConfig.for_locale("en-US", time_format_preference="24h"))


# 1. Dates

def test_written_dates_basic(normalizer_us: TextNormalizer):
    res1 = normalizer_us.normalize("Meeting on Oct 29, 2023 at noon.")
    assert "October twenty-ninth, twenty twenty-three" in res1.normalized_text

    res2 = normalizer_us.normalize("Independence day is July 4th.")
    assert "July fourth" in res2.normalized_text

    res3 = normalizer_us.normalize("Born on 29 October 2023.")
    assert "October twenty-ninth, twenty twenty-three" in res3.normalized_text

    res4 = normalizer_us.normalize("Event on Mon, Oct 29, 2023.")
    assert "Monday, October twenty-ninth, twenty twenty-three" in res4.normalized_text


def test_numeric_dates_locale_order(normalizer_us: TextNormalizer, normalizer_gb: TextNormalizer):
    # Unambiguous day > 12
    res_us = normalizer_us.normalize("10/29/2023")
    assert res_us.normalized_text == "October twenty-ninth, twenty twenty-three"

    res_gb = normalizer_gb.normalize("29/10/2023")
    assert res_gb.normalized_text == "October twenty-ninth, twenty twenty-three"

    # Ambiguous date: 03/04/2023
    res_amb_us = normalizer_us.normalize("03/04/2023")
    assert res_amb_us.normalized_text == "March fourth, twenty twenty-three"
    assert any(w.code == "AMBIGUOUS_DATE_ORDER" and w.severity == "info" for w in res_amb_us.warnings)

    res_amb_gb = normalizer_gb.normalize("03/04/2023")
    assert res_amb_gb.normalized_text == "April third, twenty twenty-three"
    assert any(w.code == "AMBIGUOUS_DATE_ORDER" and w.severity == "info" for w in res_amb_gb.warnings)


def test_iso_dates_and_ymd(normalizer_us: TextNormalizer):
    res_iso = normalizer_us.normalize("2023-10-29")
    assert res_iso.normalized_text == "October twenty-ninth, twenty twenty-three"

    res_ymd = normalizer_us.normalize("2023/10/29")
    assert res_ymd.normalized_text == "October twenty-ninth, twenty twenty-three"


def test_date_ranges_written(normalizer_us: TextNormalizer):
    res = normalizer_us.normalize("Conference runs April 3-5, 2024.")
    assert "April third to fifth, twenty twenty-four" in res.normalized_text

    res2 = normalizer_us.normalize("Festival from June 10 to 15.")
    assert "June tenth to fifteenth" in res2.normalized_text


def test_leap_days_and_calendar_validation(normalizer_us: TextNormalizer):
    # Valid leap day
    res_leap = normalizer_us.normalize("02/29/2024")
    assert res_leap.status == "success"
    assert "February twenty-ninth, twenty twenty-four" in res_leap.normalized_text

    # Invalid leap day in non-leap year (2023)
    res_invalid_leap = normalizer_us.normalize("02/29/2023")
    assert res_invalid_leap.status == "partial"
    assert any(w.code == "INVALID_CALENDAR_DATE" and w.severity == "warning" for w in res_invalid_leap.warnings)

    # Invalid calendar date: 02/30/2023
    res_feb30 = normalizer_us.normalize("02/30/2023")
    assert res_feb30.status == "partial"
    assert any(w.code == "INVALID_CALENDAR_DATE" for w in res_feb30.warnings)

    # Invalid written date: April 31
    res_apr31 = normalizer_us.normalize("April 31, 2023")
    assert res_apr31.status == "partial"
    assert any(w.code == "INVALID_CALENDAR_DATE" for w in res_apr31.warnings)


def test_unresolved_policy_invalid_date():
    # Preserve mode
    cfg_preserve = NormalizerConfig.for_locale("en-US", unresolved_policy="preserve")
    norm_pres = TextNormalizer(cfg_preserve)
    res_pres = norm_pres.normalize("02/30/2023")
    assert res_pres.normalized_text == "02/30/2023"
    assert res_pres.status == "partial"

    # Literal mode
    cfg_lit = NormalizerConfig.for_locale("en-US", unresolved_policy="literal")
    norm_lit = TextNormalizer(cfg_lit)
    res_lit = norm_lit.normalize("02/30/2023")
    assert "slash" in res_lit.normalized_text
    assert res_lit.status == "partial"


def test_relative_dates_never_converted(normalizer_us: TextNormalizer):
    text = "We will meet yesterday, today, and tomorrow or next Monday."
    res = normalizer_us.normalize(text)
    assert res.normalized_text == text
    assert len(res.transformations) == 0


# 2. Times & Durations

def test_12h_clock_times(normalizer_us: TextNormalizer):
    res1 = normalizer_us.normalize("Breakfast at 9:05 AM.")
    assert "nine oh five A M" in res1.normalized_text

    res2 = normalizer_us.normalize("Meeting at 9:05.")
    # No AM/PM added when not present
    assert "nine oh five" in res2.normalized_text
    assert "A M" not in res2.normalized_text

    res3 = normalizer_us.normalize("Starts at 9:00.")
    assert "nine o'clock" in res3.normalized_text

    res4 = normalizer_us.normalize("Alarm at 09:05.")
    # Leading zero implies morning in 12h
    assert "nine oh five A M" in res4.normalized_text

    res5 = normalizer_us.normalize("Flight at 14:30.")
    # Unambiguous 24h form converted to 12h
    assert "two thirty P M" in res5.normalized_text


def test_24h_clock_times(normalizer_24h: TextNormalizer):
    assert normalizer_24h.normalize("14:30").normalized_text == "fourteen thirty"
    assert normalizer_24h.normalize("14:00").normalized_text == "fourteen hundred"
    assert normalizer_24h.normalize("08:00").normalized_text == "oh eight hundred"
    assert normalizer_24h.normalize("08:05").normalized_text == "oh eight oh five"


def test_special_noon_and_midnight(normalizer_us: TextNormalizer):
    # Exactly 12:00
    assert normalizer_us.normalize("12:00").normalized_text == "noon"
    assert normalizer_us.normalize("12:00 PM").normalized_text == "noon"
    assert normalizer_us.normalize("12:00 AM").normalized_text == "midnight"
    assert normalizer_us.normalize("00:00").normalized_text == "midnight"
    assert normalizer_us.normalize("24:00").normalized_text == "midnight"

    # 12:01 PM is NOT noon
    res = normalizer_us.normalize("12:01 PM")
    assert res.normalized_text == "twelve oh one P M"


def test_times_with_seconds_and_timezones(normalizer_us: TextNormalizer):
    res1 = normalizer_us.normalize("Launch at 09:05:30 EST.")
    assert "nine oh five and thirty seconds A M E S T" in res1.normalized_text

    res2 = normalizer_us.normalize("Sync at 14:30 UTC.")
    assert "two thirty P M U T C" in res2.normalized_text

    res3 = normalizer_us.normalize("Event at 14:30 +05:30.")
    assert "two thirty P M plus five thirty" in res3.normalized_text


def test_time_ranges(normalizer_us: TextNormalizer):
    res = normalizer_us.normalize("Office hours are 2:00-4:00 PM.")
    assert "two to four P M" in res.normalized_text


def test_durations(normalizer_us: TextNormalizer):
    assert normalizer_us.normalize("Run time: 2h 30m.").normalized_text == "Run time: two hours and thirty minutes."
    assert normalizer_us.normalize("Took 45s to load.").normalized_text == "Took forty-five seconds to load."
    assert normalizer_us.normalize("Wait 1h please.").normalized_text == "Wait one hour please."
    assert normalizer_us.normalize("Timer: 15 min.").normalized_text == "Timer: fifteen minutes."


def test_month_day_numeric_dates(normalizer_us: TextNormalizer, normalizer_gb: TextNormalizer):
    # due 3/4 in en-US and en-GB with AMBIGUOUS_DATE_ORDER info warning
    res_us = normalizer_us.normalize("due 3/4")
    assert res_us.normalized_text == "due March fourth"
    assert any(w.code == "AMBIGUOUS_DATE_ORDER" and w.severity == "info" for w in res_us.warnings)

    res_gb = normalizer_gb.normalize("due 3/4")
    assert res_gb.normalized_text == "due April third"
    assert any(w.code == "AMBIGUOUS_DATE_ORDER" and w.severity == "info" for w in res_gb.warnings)

    # Date range and cues
    assert normalizer_us.normalize("from 3/4 to 3/9").normalized_text == "from March fourth to March ninth"
    assert normalizer_us.normalize("on 7/4").normalized_text == "on July fourth"
    assert normalizer_us.normalize("Monday, 10/28").normalized_text == "Monday, October twenty-eighth"
    assert normalizer_us.normalize("deadline is 5/10").normalized_text == "deadline is May tenth"

    # Resolved by calendar limits
    res_lim1 = normalizer_us.normalize("dated 15/4")
    assert res_lim1.normalized_text == "dated April fifteenth"
    assert any(w.code == "AMBIGUOUS_DATE_ORDER" for w in res_lim1.warnings)

    res_lim2 = normalizer_gb.normalize("dated 4/15")
    assert res_lim2.normalized_text == "dated April fifteenth"
    assert any(w.code == "AMBIGUOUS_DATE_ORDER" for w in res_lim2.warnings)

    # Fractions and idioms preserved
    assert normalizer_us.normalize("Add 3/4 cup").normalized_text == "Add three fourths cup"
    assert normalizer_us.normalize("1/2 cup").normalized_text == "one half cup"
    assert normalizer_us.normalize("24/7").normalized_text == "twenty-four seven"
    assert normalizer_us.normalize("Option 1 / 2").normalized_text == "Option one slash two"

    # Invalid date numbers not matching calendar
    assert normalizer_us.normalize("Ratio is 45/60 in test.").normalized_text == "Ratio is forty-five over sixty in test."

