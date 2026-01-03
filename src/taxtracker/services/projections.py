"""Tax projections for future years based on estimated income."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest
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
    use_standard_deduction: bool = True,
    itemized_deductions: float = 0.0,
) -> YearProjection:
    """
    Project taxes for a future year.

    Args:
        tax_calculator: TaxCalculator instance
        year: Tax year to project
        filing_status: Filing status
        num_children: Number of children
        w2_gross: Projected W-2 gross income
        w2_pretax_deductions: Projected W-2 pre-tax deductions (401k, etc.)
        pension_gross: Projected pension gross
        pension_pretax_deductions: Projected pension pre-tax (SBP, etc.)
        va_disability: Projected VA disability (non-taxable)
        estimated_federal_withholding: Estimated federal withholding
        use_standard_deduction: Use standard or itemized
        itemized_deductions: Itemized deduction amount

    Returns:
        YearProjection with full tax calculation
    """
    # Calculate taxable amounts
    w2_taxable = w2_gross - w2_pretax_deductions
    pension_taxable = pension_gross - pension_pretax_deductions
    total_taxable = w2_taxable + pension_taxable

    # Calculate federal tax
    tax_request = TaxCalculationRequest(
        tax_year=year,
        filing_status=filing_status,
        gross_income=total_taxable,
        num_children=num_children,
        use_standard_deduction=use_standard_deduction,
        itemized_deduction_amount=Decimal(str(itemized_deductions))
        if not use_standard_deduction
        else None,
    )

    tax_result = tax_calculator.calculate_taxes(tax_request)

    # Calculate FICA (only on W-2 income)
    fica_result = tax_calculator.calculate_fica(w2_gross, filing_status)

    # Total tax liability
    federal_liability = Decimal(str(tax_result.total_tax_liability))
    fica_liability = Decimal(str(fica_result["total_fica"]))
    total_liability = federal_liability + fica_liability

    # Refund/owed
    refund_or_owed = estimated_federal_withholding - total_liability

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
            (income_change / prev.total_taxable_income * 100)
            if prev.total_taxable_income > 0
            else Decimal(0)
        )

        tax_change = curr.total_tax_liability - prev.total_tax_liability
        tax_change_pct = (
            (tax_change / prev.total_tax_liability * 100)
            if prev.total_tax_liability > 0
            else Decimal(0)
        )

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
