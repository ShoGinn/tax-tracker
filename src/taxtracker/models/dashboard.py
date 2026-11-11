"""Dashboard response contract; amounts serialize as decimal strings."""

from datetime import date  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel


class DashboardYtd(BaseModel):
    """Recorded totals before projection."""

    w2_gross: Decimal
    w2_pretax_deductions: Decimal
    pension_gross: Decimal
    pension_pretax_deductions: Decimal
    va_income: Decimal
    federal_withheld: Decimal
    paycheck_count: int
    pension_count: int
    non_taxable_count: int


class DashboardProjected(BaseModel):
    """Full-year income, taxes, and federal withholding estimate."""

    w2_gross: Decimal
    w2_taxable: Decimal
    pension_gross: Decimal
    pension_taxable: Decimal
    va_income: Decimal
    total_taxable_income: Decimal
    taxable_income: Decimal
    federal_tax_liability: Decimal
    fica_liability: Decimal
    total_tax_liability: Decimal
    estimated_withholding: Decimal
    estimated_refund_or_owed: Decimal
    effective_rate: Decimal
    marginal_rate: Decimal
    deduction_type: str
    deduction_amount: Decimal


class DashboardRemainingPeriods(BaseModel):
    """Remaining payment counts for each income category."""

    w2: int
    pension: int
    non_taxable: int


class DashboardProjectionResponse(BaseModel):
    """Validated dashboard projection."""

    year: int
    as_of_date: date
    is_current_year: bool
    ytd: DashboardYtd
    remaining_periods: DashboardRemainingPeriods
    projected: DashboardProjected
