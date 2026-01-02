"""Tax data models for validation and type safety."""

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


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
    def validate_max(cls, v: Decimal | None, info: ValidationInfo) -> Decimal | None:
        """Ensure max is greater than min if provided."""
        if v is not None and "min" in info.data and v <= info.data["min"]:
            raise ValueError("max must be greater than min")
        return v


class StandardDeductions(BaseModel):
    """Standard deduction amounts by filing status."""

    amounts: dict[FilingStatus, Decimal]
    additional_age_65_plus: dict[str, Decimal]

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Allow legacy flat dicts by folding into amounts."""

        if "amounts" not in value:
            amounts = {k: v for k, v in value.items() if k != "additional_age_65_plus"}
            return {
                "amounts": amounts,
                "additional_age_65_plus": value.get("additional_age_65_plus", {}),
            }
        return value

    @field_validator("amounts", mode="after")
    @classmethod
    def validate_amount_keys(
        cls, value: dict[FilingStatus, Decimal]
    ) -> dict[FilingStatus, Decimal]:
        """Ensure every filing status has a standard deduction."""

        missing_statuses = [status for status in FilingStatus if status not in value]
        if missing_statuses:
            missing_labels = ", ".join(status.value for status in missing_statuses)
            raise ValueError(f"Missing standard deductions for filing statuses: {missing_labels}")
        return value

    def for_status(self, filing_status: FilingStatus) -> Decimal:
        """Return the standard deduction for the given status."""

        return self.amounts[filing_status]


class ChildTaxCredit(BaseModel):
    """Child tax credit configuration."""

    amount_per_child: Decimal
    refundable_portion: Decimal
    phase_out_threshold: dict[FilingStatus, Decimal]

    @model_validator(mode="before")
    @classmethod
    def normalize_thresholds(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Allow legacy string-keyed thresholds."""

        if "phase_out_threshold" in value:
            thresholds = value.get("phase_out_threshold", {})
            value = {**value, "phase_out_threshold": thresholds}
        return value


class TaxBrackets(BaseModel):
    """Complete tax bracket data for a tax year."""

    tax_year: int
    last_updated: str
    source: str
    notes: str | None = None
    tax_brackets: dict[FilingStatus, list[TaxBracket]]
    standard_deductions: StandardDeductions
    child_tax_credit: ChildTaxCredit

    @field_validator("tax_brackets", mode="after")
    @classmethod
    def validate_bracket_keys(
        cls, value: dict[FilingStatus, list[TaxBracket]]
    ) -> dict[FilingStatus, list[TaxBracket]]:
        """Ensure every filing status has a bracket set."""

        missing_statuses = [status for status in FilingStatus if status not in value]
        if missing_statuses:
            missing_labels = ", ".join(status.value for status in missing_statuses)
            raise ValueError(f"Missing tax brackets for filing statuses: {missing_labels}")
        return value

    def brackets_for_status(self, filing_status: FilingStatus) -> list[TaxBracket]:
        """Return tax brackets for a given filing status."""

        try:
            return self.tax_brackets[filing_status]
        except KeyError as exc:  # pragma: no cover - guardrail for bad data
            raise KeyError(
                f"No tax brackets found for filing status '{filing_status.value}'"
            ) from exc


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
