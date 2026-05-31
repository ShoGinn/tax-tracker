"""Mid-year period suggestion helpers for W-4 optimization."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from taxtracker.models.schemas import MidYearPeriodSuggestionResponse
from taxtracker.services.income_service import get_non_taxable_payments, get_paychecks, get_retirement_1099rs

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession


class _HasPayDate(Protocol):
    pay_date: date


_SEMIMONTHLY_MID_MONTH_CUTOFF = 15


def suggest_remaining_periods(as_of_date: date, frequency: str) -> int:
    """Suggest remaining periods in the year for a given cadence."""
    year_end = date(as_of_date.year, 12, 31)
    diff_days = max(0, (year_end - as_of_date).days)

    if frequency == "weekly":
        return max(1, -(-diff_days // 7))
    if frequency == "biweekly":
        return max(1, -(-diff_days // 14))
    if frequency == "monthly":
        return max(1, 12 - as_of_date.month + 1)
    if frequency == "semimonthly":
        months_remaining = 12 - as_of_date.month + 1
        return max(1, months_remaining * 2 - (1 if as_of_date.day > _SEMIMONTHLY_MID_MONTH_CUTOFF else 0))

    raise ValueError(f"Unsupported pay frequency: {frequency}")


def has_recorded_entry_in_as_of_month(entries: Iterable[_HasPayDate], as_of_date: date) -> bool:
    """Return whether any entry exists in the same month on or before the as-of day."""

    for entry in entries:
        pay_date = getattr(entry, "pay_date", None)
        if pay_date is None:
            continue

        entry_date = pay_date if isinstance(pay_date, date) else date.fromisoformat(str(pay_date)[:10])

        if (
            entry_date.year == as_of_date.year
            and entry_date.month == as_of_date.month
            and entry_date.day <= as_of_date.day
        ):
            return True

    return False


def _any_entry_in_window(entries: list[_HasPayDate], window_start: date, window_end: date) -> bool:
    """Return True if any entry has a pay_date within [window_start, window_end]."""
    for entry in entries:
        pay_date = getattr(entry, "pay_date", None)
        if pay_date is None:
            continue
        entry_date = pay_date if isinstance(pay_date, date) else date.fromisoformat(str(pay_date)[:10])
        if window_start <= entry_date <= window_end:
            return True
    return False


def has_w2_entry_in_current_period(
    paychecks: Iterable[_HasPayDate],
    as_of_date: date,
    frequency: str,
) -> bool:
    """Return whether any W-2 paycheck falls within the current pay period on or before as_of_date.

    - monthly: any paycheck this calendar month
    - semimonthly: any paycheck in the current half-month (1-15 or 16-end)
    - biweekly: any paycheck within the last 14 days
    - weekly: any paycheck within the last 7 days
    """
    entries = list(paychecks)

    if frequency == "monthly":
        return has_recorded_entry_in_as_of_month(entries, as_of_date)

    if frequency == "semimonthly":
        period_start_day = 1 if as_of_date.day <= _SEMIMONTHLY_MID_MONTH_CUTOFF else _SEMIMONTHLY_MID_MONTH_CUTOFF + 1
        period_start = date(as_of_date.year, as_of_date.month, period_start_day)
        return _any_entry_in_window(entries, period_start, as_of_date)

    if frequency == "biweekly":
        return _any_entry_in_window(entries, as_of_date - timedelta(days=13), as_of_date)

    if frequency == "weekly":
        return _any_entry_in_window(entries, as_of_date - timedelta(days=6), as_of_date)

    raise ValueError(f"Unsupported pay frequency: {frequency}")


async def suggest_midyear_periods(
    db: AsyncSession,
    *,
    tax_year: int,
    as_of_date: date | None,
    w2_pay_frequency: str,
) -> MidYearPeriodSuggestionResponse:
    """Build remaining-period suggestions using DB records for pension and non-taxable income."""

    effective_date = as_of_date or datetime.now(UTC).date()
    remaining_pay_periods = suggest_remaining_periods(effective_date, w2_pay_frequency)
    monthly_baseline_periods = suggest_remaining_periods(effective_date, "monthly")

    paychecks = await get_paychecks(db, year=tax_year, limit=None)
    retirement_1099rs = await get_retirement_1099rs(db, year=tax_year, limit=None)
    non_taxable_payments = await get_non_taxable_payments(db, year=tax_year, limit=None)

    current_period_has_w2_entry = has_w2_entry_in_current_period(paychecks, effective_date, w2_pay_frequency)
    current_month_has_pension_entry = has_recorded_entry_in_as_of_month(retirement_1099rs, effective_date)
    current_month_has_non_taxable_entry = has_recorded_entry_in_as_of_month(non_taxable_payments, effective_date)

    if current_period_has_w2_entry:
        remaining_pay_periods = max(1, remaining_pay_periods - 1)

    remaining_pension_periods = max(1, monthly_baseline_periods - (1 if current_month_has_pension_entry else 0))
    remaining_non_taxable_periods = max(1, monthly_baseline_periods - (1 if current_month_has_non_taxable_entry else 0))

    notes = [
        f"W-2 cadence suggestion based on {w2_pay_frequency} frequency.",
        (
            "W-2 remaining periods reduced by one when a paycheck exists in the current pay period "
            "on or before the as-of date."
        ),
        (
            "Monthly pension and non-taxable suggestions subtract one when a current-month entry exists "
            "on or before the as-of date."
        ),
    ]

    return MidYearPeriodSuggestionResponse(
        tax_year=tax_year,
        as_of_date=effective_date,
        w2_pay_frequency=w2_pay_frequency,
        remaining_pay_periods=remaining_pay_periods,
        remaining_pension_periods=remaining_pension_periods,
        remaining_non_taxable_periods=remaining_non_taxable_periods,
        monthly_baseline_periods=monthly_baseline_periods,
        current_period_has_w2_entry=current_period_has_w2_entry,
        current_month_has_pension_entry=current_month_has_pension_entry,
        current_month_has_non_taxable_entry=current_month_has_non_taxable_entry,
        notes=notes,
    )
