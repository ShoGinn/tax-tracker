"""Pydantic request models for W-4 and projection API endpoints."""

from decimal import Decimal

from pydantic import BaseModel, Field

from taxtracker.models.tax_data import FilingStatus  # noqa: TC001


class W4OptimizeRequest(BaseModel):
    """Request for W-4 optimization."""

    total_annual_w2_income: Decimal = Field(ge=0, description="Total W-2 income across all jobs")
    paychecks_per_year: int = Field(ge=1, description="Number of paychecks per year")
    filing_status: FilingStatus
    num_children: int = Field(default=0, ge=0)
    other_annual_income: Decimal = Field(default=Decimal(0), ge=0)
    itemized_deductions: Decimal = Field(default=Decimal(0), ge=0)
    target_refund: Decimal = Field(default=Decimal(0))
    year: int | None = Field(default=None, description="Tax year (defaults to current)")


class WithholdingCalcRequest(BaseModel):
    """Request for per-paycheck withholding calculation."""

    gross_pay_per_paycheck: Decimal = Field(ge=0, description="Gross pay per paycheck")
    pay_frequency: str = Field(description="weekly, biweekly, semimonthly, or monthly")
    filing_status: FilingStatus
    multiple_jobs_checkbox: bool = False
    dependents_amount: Decimal = Field(default=Decimal(0), ge=0)
    other_income_annual: Decimal = Field(default=Decimal(0), ge=0)
    deductions_annual: Decimal = Field(default=Decimal(0), ge=0)
    extra_withholding: Decimal = Field(default=Decimal(0), ge=0)
    year: int | None = Field(default=None, description="Tax year (defaults to current)")


class AnnualWithholdingRequest(BaseModel):
    """Request for annual withholding estimate."""

    annual_gross: Decimal = Field(ge=0, description="Annual gross income")
    pay_frequency: str = Field(description="weekly, biweekly, semimonthly, or monthly")
    filing_status: FilingStatus
    w4_step2_checkbox: bool = False
    w4_step3_dependents: Decimal = Field(default=Decimal(0), ge=0)
    w4_step4a_other_income: Decimal = Field(default=Decimal(0), ge=0)
    w4_step4b_deductions: Decimal = Field(default=Decimal(0), ge=0)
    w4_step4c_extra: Decimal = Field(default=Decimal(0), ge=0)
    year: int | None = Field(default=None, description="Tax year (defaults to current)")


class ProjectYearRequest(BaseModel):
    """Request for single-year tax projection."""

    projection_year: int = Field(ge=2024, le=2030)
    filing_status: FilingStatus
    num_children: int = Field(default=0, ge=0)
    w2_gross: Decimal = Field(default=Decimal(0), ge=0)
    w2_pretax_deductions: Decimal = Field(default=Decimal(0), ge=0)
    pension_gross: Decimal = Field(default=Decimal(0), ge=0)
    pension_pretax_deductions: Decimal = Field(default=Decimal(0), ge=0)
    va_disability: Decimal = Field(default=Decimal(0), ge=0)
    use_standard_deduction: bool = True
    itemized_deduction_amount: Decimal = Field(default=Decimal(0), ge=0)


class CompareYearsRequest(BaseModel):
    """Request for year-over-year tax comparison."""

    base_year: int = Field(ge=2024, le=2030)
    comparison_year: int = Field(ge=2024, le=2030)
    filing_status: FilingStatus
    num_children: int = Field(default=0, ge=0)
    base_w2_gross: Decimal = Field(ge=0)
    comparison_w2_gross: Decimal = Field(ge=0)
    base_pension: Decimal = Field(default=Decimal(0), ge=0)
    comparison_pension: Decimal = Field(default=Decimal(0), ge=0)


class ProjectFromDBRequest(BaseModel):
    """Request for database-driven tax projection."""

    projection_year: int = Field(ge=2024, le=2030)
    filing_status: FilingStatus
    num_children: int = Field(default=0, ge=0)
    expected_w2_gross: Decimal = Field(ge=0)
    use_database_pension: bool = True
    use_database_va: bool = True
