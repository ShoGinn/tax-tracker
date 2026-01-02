"""Tax calculation API endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from taxtracker.api.dependencies import get_db, get_tax_calculator
from taxtracker.core.exceptions import TaxCalculationError
from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest, TaxCalculationResponse
from taxtracker.services.data_loader import load_fica_limits, load_tax_brackets
from taxtracker.services.db_tax_calculator import calculate_taxes_from_database
from taxtracker.services.tax_calculator import TaxCalculator

router = APIRouter(prefix="/taxes", tags=["Taxes"])


@router.post("/calculate")
def calculate_taxes(
    request: TaxCalculationRequest,
    calculator: Annotated[TaxCalculator, Depends(get_tax_calculator)],
) -> TaxCalculationResponse:
    """
    Calculate federal taxes for a given income and filing status.

    This endpoint calculates:
    - Federal income tax
    - FICA (Social Security + Medicare)
    - Child tax credits
    - Effective and marginal tax rates

    Args:
        request: Tax calculation parameters
        calculator: Tax calculator instance (injected)

    Returns:
        Complete tax calculation result

    Raises:
        HTTPException: If calculation fails
    """
    try:
        return calculator.calculate_taxes(request)
    except TaxCalculationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tax calculation failed: {e!s}")


@router.post("/calculate-from-db/{year}", response_model=dict)
def calculate_from_database(
    year: int,
    filing_status: str,
    num_children: int = 0,
    use_standard_deduction: bool = True,
    itemized_deduction_amount: float = 0,
    db: Session = Depends(get_db),
    calculator: TaxCalculator = Depends(get_tax_calculator),
) -> dict[str, Any]:
    """
    Calculate taxes using income data from database.

    Aggregates all paychecks, pension, and VA disability for the year
    and calculates total tax liability.

    Args:
        year: Tax year
        filing_status: Filing status (single, married_jointly, etc.)
        num_children: Number of qualifying children
        use_standard_deduction: Whether to use standard deduction
        itemized_deduction_amount: Itemized deduction amount if not using standard
        db: Database session
        calculator: Tax calculator instance (injected)

    Returns:
        Tax calculation with breakdown by income source
    """
    try:
        # Convert string filing status to enum
        filing_status_enum = FilingStatus(filing_status)

        # Call the service function with injected calculator
        result = calculate_taxes_from_database(
            db=db,
            year=year,
            tax_calculator=calculator,
            filing_status=filing_status_enum,
            num_children=num_children,
            use_standard_deduction=use_standard_deduction,
            itemized_deductions=itemized_deduction_amount,
        )

        # Convert to dict for API response
        return result.to_dict()
    except TaxCalculationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database tax calculation failed: {e!s}")


@router.get("/fica/{year}")
def get_fica_info(year: int) -> dict[str, Any]:
    """
    Get FICA limits and rates for a given year.

    Args:
        year: Tax year

    Returns:
        FICA rates and wage base limits
    """
    try:
        data = load_fica_limits(year)
        return {
            "year": year,
            "social_security": data["social_security"],
            "medicare": data["medicare"],
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"FICA data not found for {year}: {e!s}")


@router.get("/brackets/{year}")
def get_tax_brackets(year: int, filing_status: str | None = None) -> dict[str, Any]:
    """
    Get tax brackets for a given year.

    Args:
        year: Tax year
        filing_status: Optional filing status to filter brackets

    Returns:
        Tax brackets and standard deductions
    """
    try:
        data = load_tax_brackets(year)

        if filing_status:
            return {
                "year": year,
                "filing_status": filing_status,
                "brackets": data["tax_brackets"].get(filing_status, []),
                "standard_deduction": data["standard_deductions"].get(filing_status),
            }

        return {
            "year": year,
            "tax_brackets": data["tax_brackets"],
            "standard_deductions": data["standard_deductions"],
            "child_tax_credit": data.get("child_tax_credit"),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Tax bracket data not found for {year}: {e!s}")
