"""Tax data models for validation and type safety."""

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator, model_validator

if TYPE_CHECKING:
    from collections.abc import Callable


class FilingStatus(StrEnum):
    """Tax filing status options."""

    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"


class TaxBracket(BaseModel):
    """Individual tax bracket definition.

    Represents a single step in the progressive tax schedule.
    The threshold is the upper limit of this bracket (the income level where the rate applies up to)
    The rate applies to all income from the previous bracket's
    threshold up to this bracket's threshold
    For the highest bracket, threshold should be None.

    The cumulative_tax field is pre-computed and represents the total tax owed on all income
    up to the start of this bracket. This enables O(1) tax lookups instead of O(N) loops.
    """

    threshold: Decimal | None = Field(
        None, description="Upper limit of this bracket (None for highest/infinite bracket)"
    )
    rate: Decimal = Field(..., ge=0, le=1, description="Tax rate as decimal (e.g., 0.22 for 22%)")
    cumulative_tax: Decimal = Field(
        default=Decimal(0),
        description="Pre-computed tax on all income up to this bracket's threshold",
    )


class StandardDeductions(BaseModel):
    """Standard deduction amounts by filing status."""

    amounts: dict[FilingStatus, Decimal]
    additional_age_65_plus: dict[str, Decimal]

    @field_validator("amounts", mode="after")
    @classmethod
    def validate_amount_keys(cls, value: dict[FilingStatus, Decimal]) -> dict[FilingStatus, Decimal]:
        """Ensure every filing status has a standard deduction."""

        missing_statuses = [status for status in FilingStatus if status not in value]
        if missing_statuses:
            missing_labels = ", ".join(status.value for status in missing_statuses)
            raise ValueError(f"Missing standard deductions for filing statuses: {missing_labels}")
        return value

    def for_status(self, filing_status: FilingStatus) -> Decimal:
        """Return the standard deduction for the given status."""

        return self.amounts[filing_status]

    def for_status_with_age(
        self,
        filing_status: FilingStatus,
        age_65_plus: bool = False,
        agi: Decimal | None = None,
        phase_out_fn: Callable[..., Decimal] | None = None,
    ) -> Decimal:
        """Return deduction including age 65+ extra with optional phase-out.

        The phase_out_fn hook allows future law changes (e.g., 2026 OBBB senior
        deduction phase-outs) without altering callers. When provided, it should
        accept (base, extra, agi, filing_status) and return the adjusted extra.
        """

        base = self.for_status(filing_status)
        if not age_65_plus:
            return base

        # Map filing status to the appropriate age-based key
        age_key = (
            "married"
            if filing_status
            in (
                FilingStatus.MARRIED_FILING_JOINTLY,
                FilingStatus.MARRIED_FILING_SEPARATELY,
            )
            else "single"
        )
        extra = self.additional_age_65_plus.get(age_key, Decimal(0))

        adjusted_extra = extra
        if phase_out_fn and agi is not None:
            adjusted_extra = phase_out_fn(base=base, extra=extra, agi=agi, filing_status=filing_status)

        return base + adjusted_extra


class ChildTaxCredit(BaseModel):
    """Child tax credit configuration.

    IRS phase-out: credit is reduced by $50 for every $1,000 (or fraction thereof)
    of AGI over the phase-out threshold for the filing status.
    """

    amount_per_child: Decimal
    refundable_portion: Decimal
    phase_out_threshold: dict[FilingStatus, Decimal]
    phase_out_rate: Decimal = Field(
        default=Decimal(50),
        description="Reduction per $1,000 of AGI over threshold",
    )


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
    def validate_bracket_keys(cls, value: dict[FilingStatus, list[TaxBracket]]) -> dict[FilingStatus, list[TaxBracket]]:
        """Ensure every filing status has a bracket set."""

        missing_statuses = [status for status in FilingStatus if status not in value]
        if missing_statuses:
            missing_labels = ", ".join(status.value for status in missing_statuses)
            raise ValueError(f"Missing tax brackets for filing statuses: {missing_labels}")
        return value

    @model_validator(mode="after")
    def precompute_cumulative_tax(self) -> TaxBrackets:
        """Pre-compute cumulative tax for each bracket.

        This enables O(1) tax lookups: Tax = cumulative_tax + (rate * excess_income)
        Instead of iterating through all brackets every calculation.

        The cumulative_tax of each bracket is the total tax owed on all income
        up to the start of that bracket.
        """
        for status in FilingStatus:
            brackets = self.tax_brackets[status]
            total_prior_tax = Decimal(0)
            prev_threshold = Decimal(0)

            for bracket in brackets:
                # Set this bracket's cumulative tax (tax on all prior brackets)
                bracket.cumulative_tax = total_prior_tax

                # If this bracket has a threshold, add its full tax to the running total
                if bracket.threshold is not None:
                    bracket_width = bracket.threshold - prev_threshold
                    total_prior_tax += bracket_width * bracket.rate
                    prev_threshold = bracket.threshold

        return self

    def brackets_for_status(self, filing_status: FilingStatus) -> list[TaxBracket]:
        """Return tax brackets for a given filing status."""

        try:
            return self.tax_brackets[filing_status]
        except KeyError as exc:  # pragma: no cover - guardrail for bad data
            raise KeyError(f"No tax brackets found for filing status '{filing_status.value}'") from exc


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
    """Request model for tax calculation.

    Separates W-2 and pension income because they have different FICA treatment:
    - W-2 wages are subject to FICA (Social Security + Medicare)
    - 1099-R pension income is NOT subject to FICA
    """

    w2_gross_income: Decimal = Field(default=Decimal(0), ge=0, description="W-2 gross wages (subject to FICA)")
    pension_gross_income: Decimal = Field(default=Decimal(0), ge=0, description="1099-R pension gross income (no FICA)")
    filing_status: FilingStatus
    age_65_plus: bool = Field(default=False, description="Whether taxpayer is 65 or older")
    num_children: int = Field(default=0, ge=0, description="Number of qualifying children")
    use_standard_deduction: bool = Field(default=True, description="Use standard deduction vs itemized")
    itemized_deduction_amount: Decimal | None = Field(
        default=None, ge=0, description="Itemized deduction amount if not using standard"
    )
    retirement_pretax_deductions: Decimal = Field(
        default=Decimal(0), ge=0, description="Pre-tax deductions from retirement income"
    )
    non_taxable_income: Decimal = Field(
        default=Decimal(0), ge=0, description="Non-taxable income (VA disability, SSA, gifts, etc.)"
    )
    tax_year: int = Field(default=2025, ge=2024, le=2030, description="Tax year for calculation")

    @property
    def gross_income(self) -> Decimal:
        """Total gross income (W-2 + pension)."""
        return self.w2_gross_income + self.pension_gross_income


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
    total_household_income: Decimal  # Including VA disability
    notes: list[str]


class TaxReconciliationResponse(TaxCalculationResponse):
    """Tax calculation plus withholding and YTD income context."""

    # Context
    tax_year: int
    filing_status: FilingStatus
    num_children: int

    # Income details
    w2_gross: Decimal
    w2_pretax_deductions: Decimal
    w2_taxable: Decimal
    pension_gross: Decimal
    pension_pretax_deductions: Decimal
    pension_taxable: Decimal
    non_taxable_income: Decimal
    total_taxable_income: Decimal

    # Withholding and reconciliation
    total_federal_withheld: Decimal
    total_fica_withheld: Decimal
    total_withheld: Decimal

    # Combined tax picture
    combined_liability: Decimal  # federal (after credits) + fica
    refund_or_owed: Decimal
    overpayment_percentage: Decimal
    result_status: str  # REFUND | OWED | EVEN
