"""Pydantic request models for W-4 and projection API endpoints."""

import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from taxtracker.models.tax_data import FilingStatus  # noqa: TC001

_CURRENT_YEAR = datetime.datetime.now(datetime.UTC).year


class _D:
    """Field description strings shared across request models."""

    year_optional = "Tax year (defaults to current)"
    filing_status = "IRS filing status"
    filing_status_w4 = "IRS filing status from W-4 Step 1"
    filing_status_full = "IRS filing status (single, married_jointly, married_separately, head_of_household)"
    filing_status_both_years = "IRS filing status (applied to both years)"
    num_children = "Number of qualifying children for child tax credit"
    pay_frequency = "Pay frequency: weekly, biweekly, semimonthly, or monthly"
    step2_checkbox = "W-4 Step 2 checkbox — check if you hold multiple jobs or spouse works"
    step3_dependents = "W-4 Step 3 dependents amount in dollars"
    step4a_other_income = "W-4 Step 4a annual other income (e.g. pension, interest)"
    step4b_deductions = "W-4 Step 4b annual deductions exceeding standard deduction"
    step4c_extra = "W-4 Step 4c additional withholding per paycheck"
    use_standard_deduction = "Use IRS standard deduction; set false to supply itemized amount"
    itemized_deductions = "Total itemized deductions; only used when use_standard_deduction is false"
    remaining_pay_periods = "Number of remaining pay periods to optimize across"
    remaining_pension_periods = "Optional remaining pension periods (e.g., monthly cadence)"
    remaining_non_taxable_periods = "Optional remaining non-taxable income periods (e.g., monthly cadence)"
    expected_remaining_pension_taxable = "Expected remaining taxable pension income (override DB extrapolation)"
    employer_id = "Employer ID from the database"
    expected_remaining_gross_per_paycheck = "Expected remaining gross per paycheck for this employer"
    as_of_date = "Optional YTD cutoff date; include only entries on or before this date"


class W4OptimizeRequest(BaseModel):
    """Request for W-4 optimization."""

    total_annual_w2_income: Decimal = Field(ge=0, description="Total W-2 income across all jobs")
    paychecks_per_year: int = Field(ge=1, description="Number of paychecks per year (e.g. 26 biweekly, 24 semimonthly)")
    filing_status: FilingStatus = Field(description=_D.filing_status_full)
    num_children: int = Field(default=0, ge=0, description=_D.num_children)
    other_annual_income: Decimal = Field(
        default=Decimal(0), ge=0, description="Annual pension or other non-W-2 taxable income"
    )
    itemized_deductions: Decimal = Field(
        default=Decimal(0), ge=0, description="Total itemized deductions; 0 uses standard deduction"
    )
    target_refund: Decimal = Field(
        default=Decimal(0), description="Target refund amount (0 = break even, negative = owed)"
    )
    year: int | None = Field(default=None, description=_D.year_optional)


class EmployerRemainingOverride(BaseModel):
    """Optional per-employer override for projected remaining income."""

    employer_id: int = Field(ge=1, description=_D.employer_id)
    expected_remaining_gross_per_paycheck: Decimal = Field(
        ge=0,
        description=_D.expected_remaining_gross_per_paycheck,
    )


class MidYearDBW4OptimizeRequest(BaseModel):
    """Request for mid-year W-4 optimization using database year-to-date data."""

    tax_year: int = Field(default=_CURRENT_YEAR, ge=2024, le=2030, description="Tax year to optimize")
    filing_status: FilingStatus = Field(description=_D.filing_status_full)
    as_of_date: datetime.date | None = Field(default=None, description=_D.as_of_date)
    remaining_pay_periods: int = Field(ge=1, description=_D.remaining_pay_periods)
    remaining_pension_periods: int | None = Field(default=None, ge=1, description=_D.remaining_pension_periods)
    remaining_non_taxable_periods: int | None = Field(
        default=None,
        ge=1,
        description=_D.remaining_non_taxable_periods,
    )
    num_children: int = Field(default=0, ge=0, description=_D.num_children)
    target_refund: Decimal = Field(
        default=Decimal(0), description="Target refund amount (0 = break even, negative = owed)"
    )
    use_standard_deduction: bool = Field(default=True, description=_D.use_standard_deduction)
    itemized_deductions: Decimal = Field(default=Decimal(0), ge=0, description=_D.itemized_deductions)
    expected_remaining_pension_taxable: Decimal | None = Field(
        default=None,
        ge=0,
        description=_D.expected_remaining_pension_taxable,
    )
    employer_overrides: list[EmployerRemainingOverride] = Field(
        default_factory=list,
        description="Optional per-employer remaining gross overrides",
    )


class MidYearPeriodSuggestionRequest(BaseModel):
    """Request for mid-year remaining-period suggestions."""

    tax_year: int = Field(default=_CURRENT_YEAR, ge=2024, le=2030, description="Tax year to inspect")
    as_of_date: datetime.date | None = Field(default=None, description=_D.as_of_date)
    w2_pay_frequency: Literal["weekly", "biweekly", "semimonthly", "monthly"] = Field(
        default="biweekly",
        description=_D.pay_frequency,
    )


class WithholdingCalcRequest(BaseModel):
    """Request for per-paycheck withholding calculation."""

    gross_pay_per_paycheck: Decimal = Field(ge=0, description="Gross pay per paycheck")
    pay_frequency: str = Field(description=_D.pay_frequency)
    filing_status: FilingStatus = Field(description=_D.filing_status_w4)
    multiple_jobs_checkbox: bool = Field(default=False, description=_D.step2_checkbox)
    dependents_amount: Decimal = Field(default=Decimal(0), ge=0, description=_D.step3_dependents)
    other_income_annual: Decimal = Field(default=Decimal(0), ge=0, description=_D.step4a_other_income)
    deductions_annual: Decimal = Field(default=Decimal(0), ge=0, description=_D.step4b_deductions)
    extra_withholding: Decimal = Field(default=Decimal(0), ge=0, description=_D.step4c_extra)
    year: int | None = Field(default=None, description=_D.year_optional)


class AnnualWithholdingRequest(BaseModel):
    """Request for annual withholding estimate."""

    annual_gross: Decimal = Field(ge=0, description="Annual gross income")
    pay_frequency: str = Field(description=_D.pay_frequency)
    filing_status: FilingStatus = Field(description=_D.filing_status_w4)
    w4_step2_checkbox: bool = Field(default=False, description=_D.step2_checkbox)
    w4_step3_dependents: Decimal = Field(default=Decimal(0), ge=0, description=_D.step3_dependents)
    w4_step4a_other_income: Decimal = Field(default=Decimal(0), ge=0, description=_D.step4a_other_income)
    w4_step4b_deductions: Decimal = Field(default=Decimal(0), ge=0, description=_D.step4b_deductions)
    w4_step4c_extra: Decimal = Field(default=Decimal(0), ge=0, description=_D.step4c_extra)
    year: int | None = Field(default=None, description=_D.year_optional)


class ProjectYearRequest(BaseModel):
    """Request for single-year tax projection."""

    projection_year: int = Field(default=_CURRENT_YEAR, ge=2024, le=2030, description="Year to project taxes for")
    filing_status: FilingStatus = Field(description=_D.filing_status)
    num_children: int = Field(default=0, ge=0, description=_D.num_children)
    w2_gross: Decimal = Field(default=Decimal(0), ge=0, description="Expected annual W-2 gross wages")
    w2_pretax_deductions: Decimal = Field(
        default=Decimal(0), ge=0, description="Expected annual W-2 pre-tax deductions (401k, HSA, etc.)"
    )
    pension_gross: Decimal = Field(default=Decimal(0), ge=0, description="Expected annual 1099-R gross distribution")
    pension_pretax_deductions: Decimal = Field(
        default=Decimal(0), ge=0, description="Expected annual pension pre-tax deductions (SBP, insurance)"
    )
    va_disability: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Expected annual VA disability income (non-taxable, tracked for household totals)",
    )
    use_standard_deduction: bool = Field(default=True, description=_D.use_standard_deduction)
    itemized_deduction_amount: Decimal = Field(default=Decimal(0), ge=0, description=_D.itemized_deductions)


class CompareYearsRequest(BaseModel):
    """Request for year-over-year tax comparison."""

    base_year: int = Field(default=_CURRENT_YEAR, ge=2024, le=2030, description="Base tax year to compare from")
    comparison_year: int = Field(
        default=_CURRENT_YEAR,
        ge=2024,
        le=2030,
        description="Comparison tax year to compare to",
    )
    filing_status: FilingStatus = Field(description=_D.filing_status_both_years)
    num_children: int = Field(default=0, ge=0, description=_D.num_children)
    base_w2_gross: Decimal = Field(ge=0, description="Expected W-2 gross wages for the base year")
    comparison_w2_gross: Decimal = Field(ge=0, description="Expected W-2 gross wages for the comparison year")
    base_pension: Decimal = Field(default=Decimal(0), ge=0, description="Expected pension gross for the base year")
    comparison_pension: Decimal = Field(
        default=Decimal(0), ge=0, description="Expected pension gross for the comparison year"
    )


class ProjectFromDBRequest(BaseModel):
    """Request for database-driven tax projection."""

    projection_year: int = Field(default=_CURRENT_YEAR, ge=2024, le=2030, description="Year to project taxes for")
    filing_status: FilingStatus = Field(description=_D.filing_status)
    num_children: int = Field(default=0, ge=0, description=_D.num_children)
    expected_w2_gross: Decimal = Field(ge=0, description="Expected annual W-2 gross wages")
    use_database_pension: bool = Field(
        default=True, description="Use average of historical 1099-R pension entries from database"
    )
    use_database_va: bool = Field(
        default=True, description="Use average of historical VA disability entries from database"
    )
