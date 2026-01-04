"""Calculate taxes from database income records."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.models.tax_data import (
    FilingStatus,
    TaxCalculationRequest,
    TaxReconciliationResponse,
)
from taxtracker.services.income_service import get_ytd_summary
from taxtracker.services.tax_calculator import TaxCalculator


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
) -> TaxReconciliationResponse:
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
        TaxReconciliationResponse with full breakdown
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

    # Combined liability: federal (after credits) + FICA
    combined_liability = Decimal(str(tax_result.total_tax_liability)) + Decimal(
        str(fica_result["total_fica"])
    )

    # Total withheld (federal + FICA actually withheld)
    total_withheld = ytd.total_federal_withheld + ytd.total_w2_fica_withheld

    # Refund or owed
    refund_or_owed = total_withheld - combined_liability

    # Overpayment percentage (guard divide-by-zero)
    overpayment_pct = (
        (refund_or_owed / combined_liability * 100) if combined_liability > 0 else Decimal(0)
    )

    # Harmonize response for UI/clients
    return TaxReconciliationResponse(
        tax_year=year,
        filing_status=filing_status,
        num_children=num_children,
        # Base tax calc fields (federal only, post-credits)
        gross_income=tax_result.gross_income,
        retirement_pretax_deductions=tax_result.retirement_pretax_deductions,
        adjusted_gross_income=tax_result.adjusted_gross_income,
        deduction_amount=tax_result.deduction_amount,
        deduction_type=tax_result.deduction_type,
        taxable_income=tax_result.taxable_income,
        federal_tax_owed=tax_result.federal_tax_owed,
        child_tax_credits=tax_result.child_tax_credits,
        total_tax_liability=tax_result.total_tax_liability,
        effective_tax_rate=tax_result.effective_tax_rate,
        marginal_tax_rate=tax_result.marginal_tax_rate,
        breakdown_by_bracket=tax_result.breakdown_by_bracket,
        fica_taxes=fica_result,
        total_household_income=ytd.total_household_income,
        notes=tax_result.notes,
        # Income context
        w2_gross=ytd.total_w2_gross,
        w2_pretax_deductions=ytd.total_w2_pretax_deductions,
        w2_taxable=ytd.total_w2_taxable_wages,
        pension_gross=ytd.total_pension_gross,
        pension_pretax_deductions=ytd.total_pension_pretax_deductions,
        pension_taxable=ytd.total_pension_taxable,
        non_taxable_income=ytd.total_non_taxable_income,
        total_taxable_income=ytd.total_taxable_income,
        # Withholding / reconciliation
        total_federal_withheld=ytd.total_federal_withheld,
        total_fica_withheld=ytd.total_w2_fica_withheld,
        total_withheld=total_withheld,
        combined_liability=combined_liability,
        refund_or_owed=refund_or_owed,
        overpayment_percentage=overpayment_pct,
        result_status="REFUND" if refund_or_owed > 0 else "OWED" if refund_or_owed < 0 else "EVEN",
    )
