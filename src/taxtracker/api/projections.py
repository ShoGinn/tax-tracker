"""Tax projection API endpoints."""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taxtracker.api.dependencies import get_db, get_tax_calculator
from taxtracker.core.exceptions import ProjectionError
from taxtracker.services.projections import compare_years, project_year
from taxtracker.services.tax_calculator import TaxCalculator

router = APIRouter(prefix="/projections", tags=["Projections"])


@router.post("/project-year")
def project_future_year(
    projection_year: int,
    filing_status: str,
    num_children: int,
    w2_gross: float,
    w2_pretax_deductions: float = 0,
    pension_gross: float = 0,
    pension_pretax_deductions: float = 0,
    va_disability: float = 0,
    use_standard_deduction: bool = True,
    itemized_deduction_amount: float = 0,
    calculator: TaxCalculator = Depends(get_tax_calculator),
) -> dict[str, Any]:
    """
    Project taxes for a future year based on expected income.

    Args:
        projection_year: Year to project
        filing_status: Filing status
        num_children: Number of qualifying children
        w2_gross: Expected W-2 gross income
        w2_pretax_deductions: W-2 pre-tax deductions (401k, etc.)
        pension_gross: Expected pension income
        pension_pretax_deductions: Pension pre-tax deductions
        va_disability: non-taxable benefit income (non-taxable)
        use_standard_deduction: Whether to use standard deduction
        itemized_deduction_amount: Itemized deduction amount if not using standard

    Returns:
        Tax projection with breakdown
    """
    try:
        from taxtracker.models.tax_data import FilingStatus

        # Create calculator instance

        # Convert filing status string to enum
        filing_status_enum = FilingStatus(filing_status)

        # Estimate withholding (roughly 15% of gross for initial projection)
        estimated_withholding = Decimal(str(w2_gross)) * Decimal("0.15")

        # Call service with correct parameters
        result = project_year(
            tax_calculator=calculator,
            year=projection_year,
            filing_status=filing_status_enum,
            num_children=num_children,
            w2_gross=Decimal(str(w2_gross)),
            w2_pretax_deductions=Decimal(str(w2_pretax_deductions)),
            pension_gross=Decimal(str(pension_gross)),
            pension_pretax_deductions=Decimal(str(pension_pretax_deductions)),
            va_disability=Decimal(str(va_disability)),
            estimated_federal_withholding=estimated_withholding,
            use_standard_deduction=use_standard_deduction,
            itemized_deductions=float(itemized_deduction_amount),
        )

        # Convert YearProjection to dict
        return {
            "year": result.year,
            "filing_status": result.filing_status,
            "w2_gross": str(result.w2_gross),
            "w2_taxable": str(result.w2_taxable),
            "pension_taxable": str(result.pension_taxable),
            "total_taxable_income": str(result.total_taxable_income),
            "taxable_income": str(result.taxable_income),
            "federal_tax_liability": str(result.federal_tax_liability),
            "fica_liability": str(result.fica_liability),
            "total_tax_liability": str(result.total_tax_liability),
            "estimated_withholding": str(result.estimated_withholding),
            "estimated_refund_or_owed": str(result.estimated_refund_or_owed),
            "effective_rate": str(result.effective_rate),
            "marginal_rate": str(result.marginal_rate),
        }
    except ProjectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Projection failed: {e!s}")


@router.post("/compare-years")
def compare_tax_years(
    base_year: int,
    comparison_year: int,
    filing_status: str,
    num_children: int,
    base_w2_gross: float,
    comparison_w2_gross: float,
    base_pension: float = 0,
    comparison_pension: float = 0,
    calculator: TaxCalculator = Depends(get_tax_calculator),
) -> dict[str, Any]:
    """
    Compare taxes between two years.

    Shows how tax liability changes year-over-year with different income levels.

    Args:
        base_year: Base year for comparison
        comparison_year: Year to compare against
        filing_status: Filing status
        num_children: Number of qualifying children
        base_w2_gross: W-2 income in base year
        comparison_w2_gross: W-2 income in comparison year
        base_pension: Pension income in base year
        comparison_pension: Pension income in comparison year

    Returns:
        Year-over-year comparison with differences
    """
    try:
        from taxtracker.models.tax_data import FilingStatus

        # Create calculator instance
        filing_status_enum = FilingStatus(filing_status)

        # Project base year
        base_withholding = Decimal(str(base_w2_gross)) * Decimal("0.15")
        base_projection = project_year(
            tax_calculator=calculator,
            year=base_year,
            filing_status=filing_status_enum,
            num_children=num_children,
            w2_gross=Decimal(str(base_w2_gross)),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(str(base_pension)),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=base_withholding,
        )

        # Project comparison year
        comp_withholding = Decimal(str(comparison_w2_gross)) * Decimal("0.15")
        comp_projection = project_year(
            tax_calculator=calculator,
            year=comparison_year,
            filing_status=filing_status_enum,
            num_children=num_children,
            w2_gross=Decimal(str(comparison_w2_gross)),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(str(comparison_pension)),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=comp_withholding,
        )

        # Compare the projections
        return compare_years([base_projection, comp_projection])
    except ProjectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e!s}")


@router.post("/from-database")
def project_from_database(
    projection_year: int,
    filing_status: str,
    num_children: int,
    expected_w2_gross: float,
    paychecks_per_year: int = 26,
    use_database_pension: bool = True,
    use_database_va: bool = True,
    db: Session = Depends(get_db),
    calculator: TaxCalculator = Depends(get_tax_calculator),
) -> dict[str, Any]:
    """
    Project future year using historical data from database.

    Pulls pension and non-taxable benefit averages from database automatically.

    Args:
        projection_year: Year to project
        filing_status: Filing status
        num_children: Number of qualifying children
        expected_w2_gross: Expected W-2 income
        paychecks_per_year: Number of paychecks per year
        use_database_pension: Auto-pull pension from database
        use_database_va: Auto-pull non-taxable benefit from database
        db: Database session

    Returns:
        Tax projection with data sources noted
    """
    try:
        # Get averages from database
        pension_avg = Decimal("0")
        va_avg = Decimal("0")

        if use_database_pension:
            from taxtracker.services.income_service import get_retirement_1099rs

            pension_entries = get_retirement_1099rs(db)
            if pension_entries:
                total = sum(float(p.gross_amount) for p in pension_entries)
                pension_avg = Decimal(str(total / len(pension_entries)))

        if use_database_va:
            from taxtracker.services.income_service import get_non_taxable_payments

            va_entries = get_non_taxable_payments(db)
            if va_entries:
                total = sum(float(v.amount) for v in va_entries)
                va_avg = Decimal(str(total / len(va_entries)))

        from taxtracker.models.tax_data import FilingStatus

        filing_status_enum = FilingStatus(filing_status)
        estimated_withholding = Decimal(str(expected_w2_gross)) * Decimal("0.15")

        result = project_year(
            tax_calculator=calculator,
            year=projection_year,
            filing_status=filing_status_enum,
            num_children=num_children,
            w2_gross=Decimal(str(expected_w2_gross)),
            w2_pretax_deductions=Decimal("0"),
            pension_gross=pension_avg * 12,  # Monthly to annual
            pension_pretax_deductions=Decimal("0"),
            va_disability=va_avg * 12,  # Monthly to annual
            estimated_federal_withholding=estimated_withholding,
            use_standard_deduction=True,
            itemized_deductions=0.0,
        )

        # Convert to dict and add data sources
        return {
            "year": result.year,
            "filing_status": result.filing_status,
            "w2_gross": str(result.w2_gross),
            "w2_taxable": str(result.w2_taxable),
            "pension_taxable": str(result.pension_taxable),
            "total_taxable_income": str(result.total_taxable_income),
            "taxable_income": str(result.taxable_income),
            "federal_tax_liability": str(result.federal_tax_liability),
            "fica_liability": str(result.fica_liability),
            "total_tax_liability": str(result.total_tax_liability),
            "estimated_withholding": str(result.estimated_withholding),
            "estimated_refund_or_owed": str(result.estimated_refund_or_owed),
            "effective_rate": str(result.effective_rate),
            "marginal_rate": str(result.marginal_rate),
            "data_sources": {
                "pension": "from database average" if use_database_pension else "not used",
                "va": "from database average" if use_database_va else "not used",
                "w2": "from request",
            },
        }

    except ProjectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database projection failed: {e!s}")
