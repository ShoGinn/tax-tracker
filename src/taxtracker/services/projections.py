"""Tax projections for future years based on estimated income."""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from taxtracker.core.exceptions import ProjectionError
from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest

if TYPE_CHECKING:
    from datetime import date

    from taxtracker.services.tax_calculator import TaxCalculator


@dataclass
class YearProjection:
    """Tax projection for a single year."""

    year: int
    filing_status: str

    # Income
    w2_gross: Decimal
    w2_pretax_deductions: Decimal
    w2_taxable: Decimal
    pension_gross: Decimal
    pension_pretax_deductions: Decimal
    pension_taxable: Decimal
    va_disability: Decimal
    total_taxable_income: Decimal

    # Tax calculation
    deduction_amount: Decimal
    deduction_type: str
    taxable_income: Decimal
    federal_tax_liability: Decimal
    fica_liability: Decimal
    total_tax_liability: Decimal

    # Withholding estimate
    estimated_withholding: Decimal
    estimated_refund_or_owed: Decimal

    # Effective rates
    effective_rate: Decimal
    marginal_rate: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "year": self.year,
            "filing_status": self.filing_status,
            "income": {
                "w2_gross": float(self.w2_gross),
                "w2_pretax_deductions": float(self.w2_pretax_deductions),
                "w2_taxable": float(self.w2_taxable),
                "pension_gross": float(self.pension_gross),
                "pension_pretax_deductions": float(self.pension_pretax_deductions),
                "pension_taxable": float(self.pension_taxable),
                "va_disability": float(self.va_disability),
                "total_taxable_income": float(self.total_taxable_income),
            },
            "tax_calculation": {
                "deduction_amount": float(self.deduction_amount),
                "deduction_type": self.deduction_type,
                "taxable_income": float(self.taxable_income),
                "federal_tax_liability": float(self.federal_tax_liability),
                "fica_liability": float(self.fica_liability),
                "total_tax_liability": float(self.total_tax_liability),
            },
            "withholding": {
                "estimated_withholding": float(self.estimated_withholding),
                "estimated_refund_or_owed": float(self.estimated_refund_or_owed),
            },
            "rates": {
                "effective_rate": float(self.effective_rate),
                "marginal_rate": float(self.marginal_rate),
            },
        }


def project_year(
    tax_calculator: TaxCalculator,
    *,
    year: int,
    filing_status: FilingStatus,
    num_children: int,
    # Income projections
    w2_gross: Decimal,
    w2_pretax_deductions: Decimal,
    pension_gross: Decimal,
    pension_pretax_deductions: Decimal,
    va_disability: Decimal,
    # Withholding estimate
    estimated_federal_withholding: Decimal,
    # Optional
    age_65_plus: bool = False,
    use_standard_deduction: bool = True,
    itemized_deductions: Decimal = Decimal(0),
) -> YearProjection:
    """
    Project taxes for a future year.

    Args:
        tax_calculator: TaxCalculator instance
        year: Tax year to project
        filing_status: Filing status
        num_children: Number of children
        age_65_plus: Whether to apply the additional standard deduction
        w2_gross: Projected W-2 gross income
        w2_pretax_deductions: Projected W-2 pre-tax deductions (401k, etc.)
        pension_gross: Projected pension gross
        pension_pretax_deductions: Projected pension pre-tax (SBP, etc.)
        va_disability: Projected non-taxable benefit income
        estimated_federal_withholding: Estimated federal withholding
        use_standard_deduction: Use standard or itemized
        itemized_deductions: Itemized deduction amount

    Returns:
        YearProjection with full tax calculation

    Raises:
        ProjectionError: If tax_calculator year doesn't match projection year
    """
    if tax_calculator.tax_year != year:
        msg = f"Tax calculator year ({tax_calculator.tax_year}) does not match projection year ({year})"
        raise ProjectionError(msg)

    # Calculate taxable amounts
    w2_taxable = w2_gross - w2_pretax_deductions
    pension_taxable = pension_gross - pension_pretax_deductions
    total_taxable = w2_taxable + pension_taxable

    # Calculate federal tax
    tax_request = TaxCalculationRequest(
        tax_year=year,
        filing_status=filing_status,
        w2_gross_income=w2_taxable,
        pension_gross_income=pension_taxable,
        num_children=num_children,
        age_65_plus=age_65_plus,
        use_standard_deduction=use_standard_deduction,
        itemized_deduction_amount=itemized_deductions if not use_standard_deduction else None,
    )

    tax_result = tax_calculator.calculate_taxes(tax_request)

    # Calculate FICA (only on W-2 income)
    fica_result = tax_calculator.calculate_fica(w2_gross, filing_status)

    # Total tax liability
    federal_liability = Decimal(str(tax_result.total_tax_liability))
    fica_liability = Decimal(str(fica_result["total_fica"]))
    total_liability = federal_liability + fica_liability

    # A federal refund/balance compares federal withholding with federal income
    # tax only. FICA remains visible as a separate payroll-tax liability.
    refund_or_owed = estimated_federal_withholding - federal_liability

    return YearProjection(
        year=year,
        filing_status=filing_status.value,
        w2_gross=w2_gross,
        w2_pretax_deductions=w2_pretax_deductions,
        w2_taxable=w2_taxable,
        pension_gross=pension_gross,
        pension_pretax_deductions=pension_pretax_deductions,
        pension_taxable=pension_taxable,
        va_disability=va_disability,
        total_taxable_income=total_taxable,
        deduction_amount=Decimal(str(tax_result.deduction_amount)),
        deduction_type=tax_result.deduction_type,
        taxable_income=Decimal(str(tax_result.taxable_income)),
        federal_tax_liability=federal_liability,
        fica_liability=fica_liability,
        total_tax_liability=total_liability,
        estimated_withholding=estimated_federal_withholding,
        estimated_refund_or_owed=refund_or_owed,
        effective_rate=Decimal(str(tax_result.effective_tax_rate)),
        marginal_rate=Decimal(str(tax_result.marginal_tax_rate)),
    )


def compare_years(projections: list[YearProjection]) -> dict[str, Any]:
    """
    Compare multiple year projections.

    Args:
        projections: List of YearProjection objects

    Returns:
        Comparison data showing year-over-year changes
    """
    _min_years = 2
    if len(projections) < _min_years:
        return {"error": f"Need at least {_min_years} years to compare"}

    comparisons = []

    for i in range(1, len(projections)):
        prev = projections[i - 1]
        curr = projections[i]

        income_change = curr.total_taxable_income - prev.total_taxable_income
        income_change_pct = (
            (income_change / prev.total_taxable_income * 100) if prev.total_taxable_income > 0 else Decimal(0)
        )

        tax_change = curr.total_tax_liability - prev.total_tax_liability
        tax_change_pct = (tax_change / prev.total_tax_liability * 100) if prev.total_tax_liability > 0 else Decimal(0)

        rate_change = curr.effective_rate - prev.effective_rate

        comparisons.append(
            {
                "from_year": prev.year,
                "to_year": curr.year,
                "income_change": {
                    "amount": float(income_change),
                    "percentage": float(income_change_pct),
                },
                "tax_change": {
                    "amount": float(tax_change),
                    "percentage": float(tax_change_pct),
                },
                "effective_rate_change": {
                    "amount": float(rate_change),
                    "from": float(prev.effective_rate),
                    "to": float(curr.effective_rate),
                },
                "marginal_bracket_change": {
                    "from": float(prev.marginal_rate),
                    "to": float(curr.marginal_rate),
                    "moved_bracket": prev.marginal_rate != curr.marginal_rate,
                },
            }
        )

    return {
        "years": [p.to_dict() for p in projections],
        "comparisons": comparisons,
        "summary": {
            "total_years": len(projections),
            "income_trend": "increasing"
            if projections[-1].total_taxable_income > projections[0].total_taxable_income
            else "decreasing",
            "tax_trend": "increasing"
            if projections[-1].total_tax_liability > projections[0].total_tax_liability
            else "decreasing",
        },
    }


def project_from_ytd(
    tax_calculator: TaxCalculator,
    *,
    year: int,
    filing_status: FilingStatus,
    num_children: int,
    age_65_plus: bool,
    use_standard_deduction: bool,
    itemized_deduction_amount: Decimal,
    # YTD actuals
    ytd_w2_gross: Decimal,
    ytd_w2_pretax: Decimal,
    ytd_pension_gross: Decimal,
    ytd_pension_pretax: Decimal,
    ytd_va_income: Decimal,
    ytd_w2_federal_withheld: Decimal,
    ytd_pension_federal_withheld: Decimal,
    paycheck_count: int,
    pension_count: int,
    non_taxable_count: int,
    # Remaining periods (0 = past/complete year)
    remaining_pay_periods: int,
    remaining_pension_periods: int,
    remaining_non_taxable_periods: int,
    is_current_year: bool,
    as_of_date: date,
) -> dict[str, Any]:
    """Project full-year income and tax liability from YTD actuals plus remaining periods.

    For past/non-current years (is_current_year=False), remaining periods are 0 and the
    projection equals the YTD actuals exactly.

    For the current year, remaining periods drive the extrapolation:
    - W-2: avg gross per paycheck * remaining_pay_periods
    - Pension: avg per pension * remaining_pension_periods
    - VA/non-taxable: avg per period * remaining_non_taxable_periods
    """
    if is_current_year and paycheck_count > 0:
        avg_w2_gross = ytd_w2_gross / Decimal(paycheck_count)
        avg_w2_pretax = ytd_w2_pretax / Decimal(paycheck_count)
        proj_remaining_w2_gross = avg_w2_gross * Decimal(remaining_pay_periods)
        proj_remaining_w2_pretax = avg_w2_pretax * Decimal(remaining_pay_periods)
    else:
        proj_remaining_w2_gross = Decimal(0)
        proj_remaining_w2_pretax = Decimal(0)

    if is_current_year and pension_count > 0:
        avg_pension_gross = ytd_pension_gross / Decimal(pension_count)
        avg_pension_pretax = ytd_pension_pretax / Decimal(pension_count)
        proj_remaining_pension_gross = avg_pension_gross * Decimal(remaining_pension_periods)
        proj_remaining_pension_pretax = avg_pension_pretax * Decimal(remaining_pension_periods)
    else:
        proj_remaining_pension_gross = Decimal(0)
        proj_remaining_pension_pretax = Decimal(0)

    if is_current_year and non_taxable_count > 0:
        avg_va = ytd_va_income / Decimal(non_taxable_count)
        proj_remaining_va = avg_va * Decimal(remaining_non_taxable_periods)
    else:
        proj_remaining_va = Decimal(0)

    proj_w2_gross = ytd_w2_gross + proj_remaining_w2_gross
    proj_w2_pretax = ytd_w2_pretax + proj_remaining_w2_pretax
    proj_pension_gross = ytd_pension_gross + proj_remaining_pension_gross
    proj_pension_pretax = ytd_pension_pretax + proj_remaining_pension_pretax
    proj_va = ytd_va_income + proj_remaining_va

    projection = project_year(
        tax_calculator=tax_calculator,
        year=year,
        filing_status=filing_status,
        num_children=num_children,
        age_65_plus=age_65_plus,
        w2_gross=proj_w2_gross,
        w2_pretax_deductions=proj_w2_pretax,
        pension_gross=proj_pension_gross,
        pension_pretax_deductions=proj_pension_pretax,
        va_disability=proj_va,
        estimated_federal_withholding=ytd_w2_federal_withheld + ytd_pension_federal_withheld,
        use_standard_deduction=use_standard_deduction,
        itemized_deductions=itemized_deduction_amount,
    )

    return {
        "year": year,
        "as_of_date": as_of_date.isoformat(),
        "is_current_year": is_current_year,
        "ytd": {
            "w2_gross": str(ytd_w2_gross),
            "w2_pretax_deductions": str(ytd_w2_pretax),
            "pension_gross": str(ytd_pension_gross),
            "pension_pretax_deductions": str(ytd_pension_pretax),
            "va_income": str(ytd_va_income),
            "federal_withheld": str(ytd_w2_federal_withheld + ytd_pension_federal_withheld),
            "paycheck_count": paycheck_count,
            "pension_count": pension_count,
            "non_taxable_count": non_taxable_count,
        },
        "remaining_periods": {
            "w2": remaining_pay_periods if is_current_year else 0,
            "pension": remaining_pension_periods if is_current_year else 0,
            "non_taxable": remaining_non_taxable_periods if is_current_year else 0,
        },
        "projected": {
            "w2_gross": str(proj_w2_gross),
            "w2_taxable": str(projection.w2_taxable),
            "pension_gross": str(proj_pension_gross),
            "pension_taxable": str(projection.pension_taxable),
            "va_income": str(proj_va),
            "total_taxable_income": str(projection.total_taxable_income),
            "taxable_income": str(projection.taxable_income),
            "federal_tax_liability": str(projection.federal_tax_liability),
            "fica_liability": str(projection.fica_liability),
            "total_tax_liability": str(projection.total_tax_liability),
            "estimated_withholding": str(projection.estimated_withholding),
            "estimated_refund_or_owed": str(projection.estimated_refund_or_owed),
            "effective_rate": str(projection.effective_rate),
            "marginal_rate": str(projection.marginal_rate),
            "deduction_type": projection.deduction_type,
            "deduction_amount": str(projection.deduction_amount),
        },
    }
