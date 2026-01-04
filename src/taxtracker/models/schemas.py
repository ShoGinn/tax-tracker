"""Pydantic schemas for paycheck and income API endpoints."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from dateutil import parser
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _validate_flexible_date(value: date | str | int | datetime) -> date:
    """Validate and parse date from various formats.

    Supports: YYYY-MM-DD, MM/DD/YYYY, MM/DD/YY, YYYY/MM/DD, MM-DD-YYYY
    Uses dateutil.parser for flexible parsing.
    """
    if isinstance(value, date):
        return value
    if not value or str(value).strip() == "":
        raise ValueError("Date cannot be empty")
    # dateutil.parser is the industry standard for flexible date parsing
    return parser.parse(str(value)).date()


def _validate_clean_decimal(value: Decimal | str | float) -> Decimal:
    """Validate and clean decimal values, handling currency symbols and commas.

    Removes: $, commas, and whitespace before conversion.
    """
    if isinstance(value, Decimal):
        return value
    if not value or str(value).strip() == "":
        return Decimal(0)
    # Clean currency symbols, commas, and whitespace
    cleaned = str(value).strip().replace("$", "").replace(",", "").strip()
    if not cleaned:
        return Decimal(0)
    return Decimal(cleaned)


# Reusable custom types
FlexibleDate = Annotated[date, BeforeValidator(_validate_flexible_date)]
CleanDecimal = Annotated[Decimal, BeforeValidator(_validate_clean_decimal)]


# Employer Schemas
class EmployerBase(BaseModel):
    """Base employer fields."""

    name: str = Field(..., min_length=1, max_length=200)
    ein: str | None = Field(
        default=None, max_length=20, description="Employer Identification Number"
    )
    start_date: FlexibleDate
    end_date: FlexibleDate | None = None
    notes: str | None = None


class EmployerCreate(EmployerBase):
    """Schema for creating an employer."""


class EmployerUpdate(BaseModel):
    """Schema for updating an employer (all fields optional)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    ein: str | None = Field(default=None, max_length=20)
    start_date: FlexibleDate | None = None
    end_date: FlexibleDate | None = None
    notes: str | None = None


class EmployerResponse(EmployerBase):
    """Schema for employer response."""

    id: int

    model_config = ConfigDict(from_attributes=True)


# Paycheck Schemas
class PaycheckBase(BaseModel):
    """Base paycheck fields."""

    employer_id: int
    pay_date: FlexibleDate

    gross_wages: CleanDecimal = Field(..., ge=0)
    bonus: CleanDecimal = Field(default=Decimal(0), ge=0)

    # Taxable benefits (W-2 Box 12 Code C) - increases taxable wages but not received as cash
    taxable_benefit: CleanDecimal = Field(
        default=Decimal(0),
        ge=0,
        description="Taxable fringe benefits like GTL over $50k, personal use of company car, etc.",
    )

    # Pre-tax deductions
    deduction_401k: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_403b: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_health_insurance: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_dental_insurance: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_vision_insurance: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_hsa: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_fsa: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_dependent_care_fsa: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_commuter: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_other_pretax: CleanDecimal = Field(default=Decimal(0), ge=0)

    # Post-tax deductions
    deduction_roth_401k: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_roth_403b: CleanDecimal = Field(default=Decimal(0), ge=0)
    deduction_other_posttax: CleanDecimal = Field(default=Decimal(0), ge=0)

    # Taxes withheld
    federal_withholding: CleanDecimal = Field(default=Decimal(0), ge=0)
    social_security: CleanDecimal = Field(default=Decimal(0), ge=0)
    medicare: CleanDecimal = Field(default=Decimal(0), ge=0)
    state_withholding: CleanDecimal = Field(default=Decimal(0), ge=0)
    local_withholding: CleanDecimal = Field(default=Decimal(0), ge=0)

    notes: str | None = None
    pay_period_start: FlexibleDate | None = None
    pay_period_end: FlexibleDate | None = None


class PaycheckCreate(PaycheckBase):
    """Schema for creating a paycheck."""


class PaycheckUpdate(BaseModel):
    """Schema for updating a paycheck (all fields optional)."""

    pay_date: FlexibleDate | None = None
    gross_wages: CleanDecimal | None = Field(default=None, ge=0)
    bonus: CleanDecimal | None = Field(default=None, ge=0)
    taxable_benefit: CleanDecimal | None = Field(default=None, ge=0)

    deduction_401k: CleanDecimal | None = Field(default=None, ge=0)
    deduction_403b: CleanDecimal | None = Field(default=None, ge=0)
    deduction_health_insurance: CleanDecimal | None = Field(default=None, ge=0)
    deduction_dental_insurance: CleanDecimal | None = Field(default=None, ge=0)
    deduction_vision_insurance: CleanDecimal | None = Field(default=None, ge=0)
    deduction_hsa: CleanDecimal | None = Field(default=None, ge=0)
    deduction_fsa: CleanDecimal | None = Field(default=None, ge=0)
    deduction_dependent_care_fsa: CleanDecimal | None = Field(default=None, ge=0)
    deduction_commuter: CleanDecimal | None = Field(default=None, ge=0)
    deduction_other_pretax: CleanDecimal | None = Field(default=None, ge=0)

    deduction_roth_401k: CleanDecimal | None = Field(default=None, ge=0)
    deduction_roth_403b: CleanDecimal | None = Field(default=None, ge=0)
    deduction_other_posttax: CleanDecimal | None = Field(default=None, ge=0)

    federal_withholding: CleanDecimal | None = Field(default=None, ge=0)
    social_security: CleanDecimal | None = Field(default=None, ge=0)
    medicare: CleanDecimal | None = Field(default=None, ge=0)
    state_withholding: CleanDecimal | None = Field(default=None, ge=0)
    local_withholding: CleanDecimal | None = Field(default=None, ge=0)

    notes: str | None = None
    pay_period_start: FlexibleDate | None = None
    pay_period_end: FlexibleDate | None = None


class PaycheckResponse(PaycheckBase):
    """Schema for paycheck response."""

    id: int
    employer: "EmployerResponse"

    total_pretax_deductions: CleanDecimal
    total_posttax_deductions: CleanDecimal
    total_taxes_withheld: CleanDecimal
    taxable_wages: CleanDecimal
    net_pay: CleanDecimal  # Always computed from deductions and taxes

    model_config = ConfigDict(from_attributes=True)


# Pension Payment Schemas
class Retirement1099RBase(BaseModel):
    """Base 1099-R retirement income fields."""

    pay_date: FlexibleDate
    gross_amount: CleanDecimal = Field(..., ge=0, description="Gross distribution amount (Box 1)")

    # Pre-tax deductions (reduce taxable amount)
    pretax_deductions: CleanDecimal = Field(
        default=Decimal(0),
        ge=0,
        description="Pre-tax deductions (insurance, survivor benefits, etc.)",
    )

    # Post-tax deductions (do NOT reduce taxable amount)
    posttax_deductions: CleanDecimal = Field(
        default=Decimal(0),
        ge=0,
        description="Post-tax deductions (allotments, voluntary withholdings)",
    )

    # Taxes withheld
    federal_withholding: CleanDecimal = Field(
        default=Decimal(0), ge=0, description="Federal tax withheld (Box 4)"
    )
    state_withholding: CleanDecimal = Field(default=Decimal(0), ge=0)

    # Optional categorization
    source_description: str | None = Field(
        default=None, description="Source of income (e.g., 'Military Pension', '401k Distribution')"
    )
    notes: str | None = None


class Retirement1099RCreate(Retirement1099RBase):
    """Create new 1099-R income record."""


class Retirement1099RUpdate(BaseModel):
    """Update existing 1099-R income record."""

    pay_date: FlexibleDate | None = None
    gross_amount: CleanDecimal | None = Field(default=None, ge=0)
    pretax_deductions: CleanDecimal | None = Field(default=None, ge=0)
    posttax_deductions: CleanDecimal | None = Field(default=None, ge=0)
    federal_withholding: CleanDecimal | None = Field(default=None, ge=0)
    state_withholding: CleanDecimal | None = Field(default=None, ge=0)
    source_description: str | None = None
    notes: str | None = None


class Retirement1099RResponse(Retirement1099RBase):
    """1099-R income response with calculated fields."""

    id: int
    taxable_amount: CleanDecimal = Field(description="Taxable amount (Box 2a)")
    net_amount: CleanDecimal = Field(description="Net payment received (computed)")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Non-Taxable Income Schemas
class NonTaxableIncomeBase(BaseModel):
    """Base non-taxable income fields."""

    pay_date: FlexibleDate
    amount: CleanDecimal = Field(..., ge=0)
    source_type: str | None = Field(
        default=None, description="Income source (e.g., 'VA Disability', 'SSA Disability')"
    )
    notes: str | None = None


class NonTaxableIncomeCreate(NonTaxableIncomeBase):
    """Schema for creating non-taxable income payment."""


class NonTaxableIncomeUpdate(BaseModel):
    """Schema for updating non-taxable income."""

    pay_date: FlexibleDate | None = None
    amount: CleanDecimal | None = Field(default=None, ge=0)
    source_type: str | None = None
    notes: str | None = None


class NonTaxableIncomeResponse(NonTaxableIncomeBase):
    """Schema for non-taxable income payment response."""

    id: int

    model_config = ConfigDict(from_attributes=True)


# Year-to-Date Summary
class YTDSummary(BaseModel):
    """Year-to-date income and tax summary."""

    year: int

    # W-2 Income
    total_w2_gross: CleanDecimal
    total_w2_pretax_deductions: CleanDecimal
    total_w2_taxable_wages: CleanDecimal
    total_w2_federal_withheld: CleanDecimal
    total_w2_fica_withheld: CleanDecimal

    # Pension Income
    total_pension_gross: CleanDecimal
    total_pension_pretax_deductions: CleanDecimal
    total_pension_taxable: CleanDecimal
    total_pension_federal_withheld: CleanDecimal

    # Non-Taxable Income
    total_non_taxable_income: CleanDecimal

    # Combined
    total_taxable_income: CleanDecimal
    total_household_income: CleanDecimal
    total_federal_withheld: CleanDecimal

    # Counts
    paycheck_count: int
    retirement_1099r_count: int
    non_taxable_payment_count: int
