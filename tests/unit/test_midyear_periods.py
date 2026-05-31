"""Unit tests for mid-year period suggestion helpers."""

from datetime import date
from types import SimpleNamespace

import pytest

from taxtracker.services.midyear_periods import (
    has_recorded_entry_in_as_of_month,
    has_w2_entry_in_current_period,
    suggest_remaining_periods,
)


@pytest.mark.unit
class TestSuggestRemainingPeriods:
    def test_weekly_and_biweekly_periods(self) -> None:
        as_of = date(2026, 5, 10)

        assert suggest_remaining_periods(as_of, "weekly") == 34
        assert suggest_remaining_periods(as_of, "biweekly") == 17

    def test_monthly_and_semimonthly_periods(self) -> None:
        as_of = date(2026, 5, 10)

        assert suggest_remaining_periods(as_of, "monthly") == 8
        assert suggest_remaining_periods(as_of, "semimonthly") == 16

    def test_semimonthly_after_midmonth_reduces_one(self) -> None:
        as_of = date(2026, 5, 20)

        assert suggest_remaining_periods(as_of, "semimonthly") == 15


@pytest.mark.unit
class TestHasRecordedEntryInAsOfMonth:
    def test_detects_entry_on_or_before_as_of_date(self) -> None:
        entries = [SimpleNamespace(pay_date="2026-05-03"), SimpleNamespace(pay_date="2026-06-01")]

        assert has_recorded_entry_in_as_of_month(entries, date(2026, 5, 10)) is True

    def test_ignores_entries_after_as_of_date(self) -> None:
        entries = [SimpleNamespace(pay_date="2026-05-20")]

        assert has_recorded_entry_in_as_of_month(entries, date(2026, 5, 10)) is False


@pytest.mark.unit
class TestHasW2EntryInCurrentPeriod:
    """Tests for the W-2 current-period detection helper."""

    # --- monthly ---

    def test_monthly_detects_entry_same_month(self) -> None:
        entries = [SimpleNamespace(pay_date=date(2026, 5, 15))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "monthly") is True

    def test_monthly_no_entry_same_month(self) -> None:
        entries = [SimpleNamespace(pay_date=date(2026, 4, 30))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "monthly") is False

    def test_monthly_empty_entries(self) -> None:
        assert has_w2_entry_in_current_period([], date(2026, 5, 31), "monthly") is False

    # --- semimonthly ---

    def test_semimonthly_entry_in_first_half_detected(self) -> None:
        # as_of is May 10 (first half); paycheck on May 5 is in the same period
        entries = [SimpleNamespace(pay_date=date(2026, 5, 5))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 10), "semimonthly") is True

    def test_semimonthly_entry_in_second_half_detected(self) -> None:
        # as_of is May 30 (second half); paycheck on May 30 is in the same period
        entries = [SimpleNamespace(pay_date=date(2026, 5, 30))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "semimonthly") is True

    def test_semimonthly_first_half_entry_not_in_second_half_period(self) -> None:
        # as_of is May 31 (second half); paycheck on May 5 (first half) is a different period
        entries = [SimpleNamespace(pay_date=date(2026, 5, 5))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "semimonthly") is False

    def test_semimonthly_no_entry_in_current_half(self) -> None:
        entries = [SimpleNamespace(pay_date=date(2026, 4, 30))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "semimonthly") is False

    # --- biweekly ---

    def test_biweekly_entry_within_14_days(self) -> None:
        # as_of May 31; paycheck May 25 (6 days ago) → within 14-day window
        entries = [SimpleNamespace(pay_date=date(2026, 5, 25))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "biweekly") is True

    def test_biweekly_entry_exactly_13_days_ago(self) -> None:
        # as_of May 31; window_start = May 18; paycheck May 18 is on the edge
        entries = [SimpleNamespace(pay_date=date(2026, 5, 18))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "biweekly") is True

    def test_biweekly_entry_14_days_ago_excluded(self) -> None:
        # as_of May 31; window_start = May 18; paycheck May 17 (14 days ago) is outside window
        entries = [SimpleNamespace(pay_date=date(2026, 5, 17))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "biweekly") is False

    # --- weekly ---

    def test_weekly_entry_within_7_days(self) -> None:
        entries = [SimpleNamespace(pay_date=date(2026, 5, 28))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "weekly") is True

    def test_weekly_entry_outside_7_days(self) -> None:
        # as_of May 31; window_start = May 25; paycheck May 24 is outside
        entries = [SimpleNamespace(pay_date=date(2026, 5, 24))]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "weekly") is False

    # --- string vs date pay_date ---

    def test_handles_string_pay_date(self) -> None:
        entries = [SimpleNamespace(pay_date="2026-05-30")]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "semimonthly") is True

    def test_handles_none_pay_date(self) -> None:
        entries = [SimpleNamespace(pay_date=None)]
        assert has_w2_entry_in_current_period(entries, date(2026, 5, 31), "monthly") is False

    # --- unknown frequency ---

    def test_raises_on_unknown_frequency(self) -> None:
        with pytest.raises(ValueError, match="Unsupported pay frequency"):
            has_w2_entry_in_current_period([], date(2026, 5, 31), "quarterly")
