"""Mid-year period suggestion helpers for W-4 optimization."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Protocol

from taxtracker.models.schemas import MidYearPeriodSuggestionResponse
from taxtracker.services.income_service import get_non_taxable_payments, get_retirement_1099rs

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

    retirement_1099rs = await get_retirement_1099rs(db, year=tax_year, limit=None)
    non_taxable_payments = await get_non_taxable_payments(db, year=tax_year, limit=None)

    current_month_has_pension_entry = has_recorded_entry_in_as_of_month(retirement_1099rs, effective_date)
    current_month_has_non_taxable_entry = has_recorded_entry_in_as_of_month(non_taxable_payments, effective_date)

    remaining_pension_periods = max(1, monthly_baseline_periods - (1 if current_month_has_pension_entry else 0))
    remaining_non_taxable_periods = max(1, monthly_baseline_periods - (1 if current_month_has_non_taxable_entry else 0))

    notes = [
        f"W-2 cadence suggestion based on {w2_pay_frequency} frequency.",
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
        current_month_has_pension_entry=current_month_has_pension_entry,
        current_month_has_non_taxable_entry=current_month_has_non_taxable_entry,
        notes=notes,
    )
