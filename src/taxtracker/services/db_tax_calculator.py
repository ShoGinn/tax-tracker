"""Calculate taxes from database income records."""

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.core.config import settings
from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest
from taxtracker.services.income_service import get_ytd_summary
from taxtracker.services.tax_calculator import TaxCalculator


class DatabaseTaxCalculation:
    """Result of tax calculation from database."""

    def __init__(
        self,
        year: int,
        filing_status: str,
        num_children: int,
        # Income breakdown
        w2_gross: Decimal,
        w2_pretax_deductions: Decimal,
        w2_taxable: Decimal,
        pension_gross: Decimal,
        pension_pretax_deductions: Decimal,
        pension_taxable: Decimal,
        va_disability: Decimal,
        # Tax calculations
        agi: Decimal,
        deduction_amount: Decimal,
        deduction_type: str,  # "Standard" or "Itemized"
        taxable_income: Decimal,
        federal_tax_before_credits: Decimal,
        child_tax_credits: Decimal,
        federal_tax_liability: Decimal,
        fica_liability: Decimal,
        total_tax_liability: Decimal,
        # Withholdings
        federal_withheld: Decimal,
        fica_withheld: Decimal,
        total_withheld: Decimal,
        # Result
        refund_or_owed: Decimal,
        overpayment_percentage: Decimal,
        # Details
        federal_tax_breakdown: list[dict[str, Any]],
        fica_breakdown: dict[str, Any],
        marginal_rate: Decimal,
        effective_rate: Decimal,
    ) -> None:
        self.year = year
        self.filing_status = filing_status
        self.num_children = num_children

        self.w2_gross = w2_gross
        self.w2_pretax_deductions = w2_pretax_deductions
        self.w2_taxable = w2_taxable
        self.pension_gross = pension_gross
        self.pension_pretax_deductions = pension_pretax_deductions
        self.pension_taxable = pension_taxable
        self.va_disability = va_disability

        self.agi = agi
        self.deduction_amount = deduction_amount
        self.deduction_type = deduction_type
        self.taxable_income = taxable_income
        self.federal_tax_before_credits = federal_tax_before_credits
        self.child_tax_credits = child_tax_credits
        self.federal_tax_liability = federal_tax_liability
        self.fica_liability = fica_liability
        self.total_tax_liability = total_tax_liability

        self.federal_withheld = federal_withheld
        self.fica_withheld = fica_withheld
        self.total_withheld = total_withheld

        self.refund_or_owed = refund_or_owed
        self.overpayment_percentage = overpayment_percentage

        self.federal_tax_breakdown = federal_tax_breakdown
        self.fica_breakdown = fica_breakdown
        self.marginal_rate = marginal_rate
        self.effective_rate = effective_rate

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "year": self.year,
            "filing_status": self.filing_status,
            "num_children": self.num_children,
            "income_summary": {
                "w2": {
                    "gross": float(self.w2_gross),
                    "pretax_deductions": float(self.w2_pretax_deductions),
                    "taxable": float(self.w2_taxable),
                },
                "pension": {
                    "gross": float(self.pension_gross),
                    "pretax_deductions": float(self.pension_pretax_deductions),
                    "taxable": float(self.pension_taxable),
                },
                "va_disability": {
                    "amount": float(self.va_disability),
                    "taxable": 0.0,
                    "note": "non-taxable benefit is not taxable",
                },
                "total_household_income": float(
                    self.w2_gross + self.pension_gross + self.va_disability
                ),
                "total_taxable_income": float(self.agi),
            },
            "tax_calculation": {
                "agi": float(self.agi),
                "deduction_amount": float(self.deduction_amount),
                "deduction_type": self.deduction_type,
                "taxable_income": float(self.taxable_income),
                "federal_tax_before_credits": float(self.federal_tax_before_credits),
                "child_tax_credits": float(self.child_tax_credits),
                "federal_tax_liability": float(self.federal_tax_liability),
                "fica_liability": float(self.fica_liability),
                "total_tax_liability": float(self.total_tax_liability),
            },
            "withholdings": {
                "federal_withheld": float(self.federal_withheld),
                "fica_withheld": float(self.fica_withheld),
                "total_withheld": float(self.total_withheld),
            },
            "result": {
                "refund_or_owed": float(self.refund_or_owed),
                "status": "REFUND"
                if self.refund_or_owed > 0
                else "OWED"
                if self.refund_or_owed < 0
                else "EVEN",
                "overpayment_percentage": float(self.overpayment_percentage),
                "message": self._get_result_message(),
            },
            "details": {
                "federal_tax_breakdown": self.federal_tax_breakdown,
                "fica_breakdown": self.fica_breakdown,
                "marginal_rate": float(self.marginal_rate),
                "effective_rate": float(self.effective_rate),
            },
        }

    def _get_result_message(self) -> str:
        """Get human-readable result message."""
        if self.refund_or_owed > settings.w4_threshold:
            pct = self.overpayment_percentage
            amt = self.refund_or_owed
            return (
                f"You overpaid by ${amt:,.2f} ({pct:.1f}%). "
                f"Consider adjusting your W-4 to reduce withholding."
            )
        if self.refund_or_owed < -settings.w4_threshold:
            amt = abs(self.refund_or_owed)
            return f"You owe ${amt:,.2f}. Consider increasing your W-4 withholding."
        return "Perfect! Your withholdings are spot-on."


async def calculate_taxes_from_database(
    db: AsyncSession,
    year: int,
    tax_calculator: TaxCalculator,
    filing_status: FilingStatus = FilingStatus.MARRIED_FILING_JOINTLY,
    num_children: int = 0,
    use_standard_deduction: bool = True,
    itemized_deductions: float = 0.0,
    age_65_plus: bool = False,
    include_taxability_in_breakdown: bool = False,
) -> DatabaseTaxCalculation:
    """
    Calculate taxes from database records.

    Args:
        db: Async database session
        year: Tax year
        tax_calculator: TaxCalculator instance
        filing_status: Filing status (default: married filing jointly)
        num_children: Number of children for child tax credit
        use_standard_deduction: If True, use standard deduction. If False, use itemized_deductions
        itemized_deductions: Total itemized deductions (only used if use_standard_deduction=False)

    Returns:
        DatabaseTaxCalculation with full breakdown
    """
    # Get YTD summary from database
    ytd = await get_ytd_summary(db, year)

    # Calculate AGI (W-2 taxable + pension taxable)
    # Note: Pre-tax deductions already removed from these amounts
    agi = ytd.total_w2_taxable_wages + ytd.total_pension_taxable

    # Use the existing tax calculator
    tax_request = TaxCalculationRequest(
        tax_year=year,
        filing_status=filing_status,
        gross_income=agi,  # This is already AGI (after pre-tax deductions)
        num_children=num_children,
        age_65_plus=age_65_plus,
        use_standard_deduction=use_standard_deduction,
        itemized_deduction_amount=Decimal(str(itemized_deductions))
        if not use_standard_deduction
        else None,
    )

    tax_result = tax_calculator.calculate_taxes(
        tax_request,
        include_taxability_in_breakdown=include_taxability_in_breakdown,
    )

    # Calculate FICA separately for W-2 income only
    # Pension doesn't pay FICA (already paid during active service)
    fica_result = tax_calculator.calculate_fica(ytd.total_w2_gross, filing_status)

    # Total tax liability
    total_liability = Decimal(str(tax_result.total_tax_liability)) + Decimal(
        str(fica_result["total_fica"])
    )

    # Total withheld
    total_withheld = ytd.total_federal_withheld + ytd.total_w2_fica_withheld

    # Refund or owed
    refund_or_owed = total_withheld - total_liability

    # Overpayment percentage
    overpayment_pct = (
        (refund_or_owed / total_liability * 100) if total_liability > 0 else Decimal(0)
    )

    return DatabaseTaxCalculation(
        year=year,
        filing_status=filing_status.value,
        num_children=num_children,
        # Income
        w2_gross=ytd.total_w2_gross,
        w2_pretax_deductions=ytd.total_w2_pretax_deductions,
        w2_taxable=ytd.total_w2_taxable_wages,
        pension_gross=ytd.total_pension_gross,
        pension_pretax_deductions=ytd.total_pension_pretax_deductions,
        pension_taxable=ytd.total_pension_taxable,
        va_disability=ytd.total_va_disability,
        # Tax calculation
        agi=agi,
        deduction_amount=Decimal(str(tax_result.deduction_amount)),
        deduction_type=tax_result.deduction_type,
        taxable_income=Decimal(str(tax_result.taxable_income)),
        federal_tax_before_credits=Decimal(str(tax_result.federal_tax_owed)),
        child_tax_credits=Decimal(str(tax_result.child_tax_credits)),
        federal_tax_liability=Decimal(str(tax_result.total_tax_liability)),
        fica_liability=Decimal(str(fica_result["total_fica"])),
        total_tax_liability=total_liability,
        # Withholdings
        federal_withheld=ytd.total_federal_withheld,
        fica_withheld=ytd.total_w2_fica_withheld,
        total_withheld=total_withheld,
        # Result
        refund_or_owed=refund_or_owed,
        overpayment_percentage=overpayment_pct,
        # Details
        federal_tax_breakdown=tax_result.breakdown_by_bracket,
        fica_breakdown=fica_result,
        marginal_rate=Decimal(str(tax_result.marginal_tax_rate)),
        effective_rate=Decimal(str(tax_result.effective_tax_rate)),
    )
