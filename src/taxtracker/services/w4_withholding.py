"""W-4 Withholding Calculator - Simulates federal withholding based on W-4 settings."""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from taxtracker.services.data_loader import load_tax_brackets_model

if TYPE_CHECKING:
    from taxtracker.models.tax_data import FilingStatus, TaxBrackets

PAY_PERIODS: dict[str, int] = {
    "weekly": 52,
    "biweekly": 26,
    "semimonthly": 24,
    "monthly": 12,
}


def _calculate_progressive_tax(taxable_income: Decimal, brackets: TaxBrackets, filing_status: FilingStatus) -> Decimal:
    """Calculate progressive tax using TaxBracket models directly."""
    bracket_list = brackets.tax_brackets[filing_status]
    previous_threshold = Decimal(0)
    remaining = taxable_income
    total_tax = Decimal(0)

    for bracket in bracket_list:
        if remaining <= 0:
            break

        bracket_size = bracket.threshold - previous_threshold if bracket.threshold is not None else remaining
        taxable_in_bracket = min(remaining, bracket_size)
        total_tax += taxable_in_bracket * bracket.rate
        remaining -= taxable_in_bracket

        if bracket.threshold is not None:
            previous_threshold = bracket.threshold

    return total_tax


def calculate_withholding_per_paycheck(
    gross_pay: Decimal,
    pay_frequency: str,  # "weekly", "biweekly", "semimonthly", "monthly"
    filing_status: FilingStatus,
    # W-4 Step 2
    multiple_jobs_checkbox: bool,
    # W-4 Step 3
    dependents_amount: Decimal,
    # W-4 Step 4
    other_income_annual: Decimal,
    deductions_annual: Decimal,
    extra_withholding: Decimal,
    year: int = 2024,
) -> dict[str, Any]:
    """
    Calculate federal withholding per paycheck based on W-4 settings.

    Uses the IRS Publication 15-T percentage method with data from JSON files.

    Args:
        gross_pay: Gross pay per paycheck
        pay_frequency: "weekly", "biweekly", "semimonthly", "monthly"
        filing_status: Filing status
        multiple_jobs_checkbox: W-4 Step 2(c) checkbox
        dependents_amount: W-4 Step 3 amount (e.g., $4000 for 2 kids)
        other_income_annual: W-4 Step 4(a) - other income
        deductions_annual: W-4 Step 4(b) - extra deductions
        extra_withholding: W-4 Step 4(c) - extra per paycheck
        year: Tax year

    Returns:
        Dictionary with withholding amount and breakdown
    """
    tax_brackets_model = load_tax_brackets_model(year)

    if pay_frequency not in PAY_PERIODS:
        raise ValueError(f"Invalid pay_frequency: {pay_frequency}")

    periods_per_year = PAY_PERIODS[pay_frequency]

    # Step 1: Adjust gross pay based on Step 2(c) checkbox
    # IRS says to divide by 2 if checkbox is checked
    adjusted_gross = gross_pay / 2 if multiple_jobs_checkbox else gross_pay

    # Step 2: Calculate annual wages from this job
    annual_wages = adjusted_gross * periods_per_year

    # Step 3: Adjust for Step 4(a) other income
    annual_wages_adjusted = annual_wages + other_income_annual

    # Step 4: Get standard deduction
    standard_deduction = tax_brackets_model.standard_deductions.amounts[filing_status]

    # Step 5: Subtract deductions
    # Standard deduction + Step 4(b) extra deductions
    total_deductions = standard_deduction + deductions_annual
    annual_taxable = max(Decimal(0), annual_wages_adjusted - total_deductions)

    # Step 6: Calculate annual withholding using progressive tax brackets
    annual_tax = _calculate_progressive_tax(annual_taxable, tax_brackets_model, filing_status)

    # Step 7: Subtract dependent credits
    annual_tax = max(Decimal(0), annual_tax - dependents_amount)

    # Step 8: Calculate per-paycheck withholding
    withholding_per_paycheck = annual_tax / periods_per_year

    # Step 9: Add Step 4(c) extra withholding
    final_withholding = withholding_per_paycheck + extra_withholding

    # Annual withholding
    annual_withholding = final_withholding * periods_per_year

    return {
        "withholding_per_paycheck": float(final_withholding),
        "annual_withholding": float(annual_withholding),
        "breakdown": {
            "gross_pay_per_paycheck": float(gross_pay),
            "adjusted_gross_per_paycheck": float(adjusted_gross),
            "annual_wages": float(annual_wages),
            "annual_wages_with_other_income": float(annual_wages_adjusted),
            "standard_deduction": float(standard_deduction),
            "total_deductions": float(total_deductions),
            "annual_taxable": float(annual_taxable),
            "annual_tax_before_credits": float(annual_tax + dependents_amount),
            "dependent_credits": float(dependents_amount),
            "annual_tax_after_credits": float(annual_tax),
            "base_withholding_per_paycheck": float(withholding_per_paycheck),
            "extra_withholding_per_paycheck": float(extra_withholding),
            "final_withholding_per_paycheck": float(final_withholding),
        },
    }


def estimate_annual_withholding_from_w4(
    annual_gross: Decimal,
    pay_frequency: str,
    filing_status: FilingStatus,
    w4_step2_checkbox: bool,
    w4_step3_dependents: Decimal,
    w4_step4a_other_income: Decimal,
    w4_step4b_deductions: Decimal,
    w4_step4c_extra: Decimal,
    year: int = 2024,
) -> Decimal:
    """
    Estimate annual federal withholding from W-4 settings.

    This is a convenience wrapper around calculate_withholding_per_paycheck.

    Returns:
        Estimated annual federal withholding
    """
    periods = PAY_PERIODS.get(pay_frequency, 26)
    gross_per_paycheck = annual_gross / periods

    result = calculate_withholding_per_paycheck(
        gross_pay=gross_per_paycheck,
        pay_frequency=pay_frequency,
        filing_status=filing_status,
        multiple_jobs_checkbox=w4_step2_checkbox,
        dependents_amount=w4_step3_dependents,
        other_income_annual=w4_step4a_other_income,
        deductions_annual=w4_step4b_deductions,
        extra_withholding=w4_step4c_extra,
        year=year,
    )

    return Decimal(str(result["annual_withholding"]))
