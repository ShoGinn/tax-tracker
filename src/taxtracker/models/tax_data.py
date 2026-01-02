"""Tax data models for validation and type safety."""

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FilingStatus(str, Enum):
    """Tax filing status options."""

    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"


class TaxBracket(BaseModel):
    """Individual tax bracket definition."""

    min: Decimal = Field(..., ge=0, description="Minimum income for this bracket")
    max: Decimal | None = Field(
        None, description="Maximum income for this bracket (None for highest bracket)"
    )
    rate: Decimal = Field(..., ge=0, le=1, description="Tax rate as decimal (e.g., 0.22 for 22%)")

    @field_validator("max")
    @classmethod
    def validate_max(cls, v: Decimal | None, info: Any) -> Decimal | None:
        """Ensure max is greater than min if provided."""
        if v is not None and "min" in info.data and v <= info.data["min"]:
            raise ValueError("max must be greater than min")
        return v


class StandardDeductions(BaseModel):
    """Standard deduction amounts by filing status."""

    married_filing_jointly: Decimal
    single: Decimal
    married_filing_separately: Decimal
    head_of_household: Decimal
    additional_age_65_plus: dict[str, Decimal]


class ChildTaxCredit(BaseModel):
    """Child tax credit configuration."""

    amount_per_child: Decimal
    refundable_portion: Decimal
    phase_out_threshold: dict[str, Decimal]


class TaxBrackets(BaseModel):
    """Complete tax bracket data for a tax year."""

    tax_year: int
    last_updated: str
    source: str
    notes: str | None = None
    tax_brackets: dict[str, list[TaxBracket]]
    standard_deductions: StandardDeductions
    child_tax_credit: ChildTaxCredit


class SocialSecurityTax(BaseModel):
    """Social Security tax configuration."""

    employee_rate: Decimal
    employer_rate: Decimal
    total_rate: Decimal
    wage_base_limit: Decimal
    max_employee_tax: Decimal
    max_employer_tax: Decimal
    max_combined_tax: Decimal


class MedicareTax(BaseModel):
    """Medicare tax configuration."""

    employee_rate: Decimal
    employer_rate: Decimal
    total_rate: Decimal
    wage_base_limit: Decimal | None
    note: str


class AdditionalMedicareTax(BaseModel):
    """Additional Medicare tax for high earners."""

    rate: Decimal
    employer_match: bool
    thresholds: dict[str, Decimal]
    note: str


class FICALimits(BaseModel):
    """FICA (Social Security and Medicare) tax limits and rates."""

    tax_year: int
    last_updated: str
    source: str
    social_security: SocialSecurityTax
    medicare: MedicareTax
    additional_medicare: AdditionalMedicareTax
    combined_rates: dict[str, Decimal]


class TaxCalculationRequest(BaseModel):
    """Request model for tax calculation."""

    gross_income: Decimal = Field(..., gt=0, description="Total gross income")
    filing_status: FilingStatus
    num_children: int = Field(default=0, ge=0, description="Number of qualifying children")
    use_standard_deduction: bool = Field(
        default=True, description="Use standard deduction vs itemized"
    )
    itemized_deduction_amount: Decimal | None = Field(
        default=None, ge=0, description="Itemized deduction amount if not using standard"
    )
    retirement_pretax_deductions: Decimal = Field(
        default=Decimal(0), ge=0, description="Pre-tax deductions from retirement income"
    )
    non_taxable_income: Decimal = Field(
        default=Decimal(0), ge=0, description="Non-taxable income (non-taxable benefit, SSA, gifts, etc.)"
    )
    tax_year: int = Field(default=2025, ge=2024, le=2030, description="Tax year for calculation")


class TaxCalculationResponse(BaseModel):
    """Response model for tax calculation."""

    gross_income: Decimal
    retirement_pretax_deductions: Decimal
    adjusted_gross_income: Decimal
    deduction_amount: Decimal
    deduction_type: str
    taxable_income: Decimal
    federal_tax_owed: Decimal
    child_tax_credits: Decimal
    total_tax_liability: Decimal
    effective_tax_rate: Decimal
    marginal_tax_rate: Decimal
    breakdown_by_bracket: list[dict[str, Any]]
    fica_taxes: dict[str, Decimal]
    total_household_income: Decimal  # Including non-taxable benefit
    notes: list[str]
