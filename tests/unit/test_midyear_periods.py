"""Unit tests for mid-year period suggestion helpers."""

from datetime import date
from types import SimpleNamespace

import pytest

from taxtracker.services.midyear_periods import has_recorded_entry_in_as_of_month, suggest_remaining_periods


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
