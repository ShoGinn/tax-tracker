"""Tax projection API endpoints."""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from taxtracker.api.dependencies import get_db
from taxtracker.core.exceptions import ProjectionError
from taxtracker.models.api_requests import (  # noqa: TC001
    CompareYearsRequest,
    ProjectFromDBRequest,
    ProjectYearRequest,
)
from taxtracker.services.income_service import get_non_taxable_payments, get_retirement_1099rs
from taxtracker.services.projections import compare_years, project_year
from taxtracker.services.tax_calculator import TaxCalculator

router = APIRouter(prefix="/projections", tags=["Projections"])


@router.post("/project-year")
async def project_future_year(request: ProjectYearRequest) -> dict[str, Any]:
    """
    Project taxes for a future year based on expected income.

    Returns:
        Tax projection with breakdown
    """
    try:
        result = project_year(
            tax_calculator=TaxCalculator(tax_year=request.projection_year),
            year=request.projection_year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            w2_gross=request.w2_gross,
            w2_pretax_deductions=request.w2_pretax_deductions,
            pension_gross=request.pension_gross,
            pension_pretax_deductions=request.pension_pretax_deductions,
            va_disability=request.va_disability,
            estimated_federal_withholding=Decimal(0),
            use_standard_deduction=request.use_standard_deduction,
            itemized_deductions=float(request.itemized_deduction_amount),
        )

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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Projection failed: {e!s}") from e


@router.post("/compare-years")
async def compare_tax_years(request: CompareYearsRequest) -> dict[str, Any]:
    """
    Compare taxes between two years.

    Shows how tax liability changes year-over-year with different income levels.
    """
    try:
        base_projection = project_year(
            tax_calculator=TaxCalculator(tax_year=request.base_year),
            year=request.base_year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            w2_gross=request.base_w2_gross,
            w2_pretax_deductions=Decimal(0),
            pension_gross=request.base_pension,
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )

        comp_projection = project_year(
            tax_calculator=TaxCalculator(tax_year=request.comparison_year),
            year=request.comparison_year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            w2_gross=request.comparison_w2_gross,
            w2_pretax_deductions=Decimal(0),
            pension_gross=request.comparison_pension,
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )

        return compare_years([base_projection, comp_projection])
    except ProjectionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e!s}") from e


@router.post("/from-database")
async def project_from_database(
    request: ProjectFromDBRequest,
    *,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Project future year using historical data from database.

    Pulls pension and VA disability averages from database automatically.
    """
    try:
        pension_avg = Decimal(0)
        va_avg = Decimal(0)

        if request.use_database_pension:
            pension_entries = await get_retirement_1099rs(db)
            if pension_entries:
                total = sum(float(p.gross_amount) for p in pension_entries)
                pension_avg = Decimal(str(total / len(pension_entries)))

        if request.use_database_va:
            va_entries = await get_non_taxable_payments(db)
            if va_entries:
                total = sum(float(v.amount) for v in va_entries)
                va_avg = Decimal(str(total / len(va_entries)))

        result = project_year(
            tax_calculator=TaxCalculator(tax_year=request.projection_year),
            year=request.projection_year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            w2_gross=request.expected_w2_gross,
            w2_pretax_deductions=Decimal(0),
            pension_gross=pension_avg * 12,
            pension_pretax_deductions=Decimal(0),
            va_disability=va_avg * 12,
            estimated_federal_withholding=Decimal(0),
            use_standard_deduction=True,
            itemized_deductions=0.0,
        )

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
                "pension": "from database average"
                if request.use_database_pension
                else "not used",
                "va": "from database average" if request.use_database_va else "not used",
                "w2": "from request",
            },
        }

    except ProjectionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database projection failed: {e!s}"
        ) from e
