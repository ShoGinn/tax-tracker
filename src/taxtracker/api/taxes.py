"""Tax calculation API endpoints."""

import json
from collections.abc import Callable  # noqa: TC003
from pathlib import Path as FilePath  # noqa: TC003
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from taxtracker.api.dependencies import get_db, get_tax_data
from taxtracker.core.config import settings
from taxtracker.core.exceptions import DataLoadError, TaxCalculationError
from taxtracker.models.tax_data import (  # noqa: TC001
    FICALimits,
    FilingStatus,
    TaxBrackets,
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxReconciliationResponse,
)
from taxtracker.services.data_loader import (
    get_available_years,
    validate_and_save_fica_limits,
    validate_and_save_tax_brackets,
)
from taxtracker.services.db_tax_calculator import calculate_taxes_from_database
from taxtracker.services.tax_calculator import TaxCalculator

router = APIRouter(prefix="/taxes", tags=["Taxes"])

# Reusable path parameter types for year-scoped endpoints
_TaxYearPath = Annotated[int, Path(description="Tax year (e.g. 2025, 2026)", ge=2020, le=2030)]
_UploadYearPath = Annotated[int, Path(description="Tax year this data applies to (e.g. 2025, 2026)", ge=2020, le=2030)]


@router.post(
    "/calculate",
    summary="Calculate federal taxes",
    response_description="Complete tax calculation breakdown",
    responses={400: {"description": "Invalid input or unsupported tax year"}},
)
async def calculate_taxes(
    request: TaxCalculationRequest,
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
        calculator = TaxCalculator(tax_year=request.tax_year)
        return calculator.calculate_taxes(request)
    except TaxCalculationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DataLoadError as e:
        raise HTTPException(status_code=500, detail=f"Tax calculation failed: {e!s}") from e


@router.post(
    "/calculate-from-db/{year}",
    summary="Calculate taxes from database income",
    response_description="Tax reconciliation with withholding comparison",
    responses={400: {"description": "Invalid input or unsupported tax year"}},
)
async def calculate_from_database(
    year: Annotated[int, Path(description="Tax year to calculate (e.g. 2025, 2026)", ge=2020, le=2030)],
    filing_status: Annotated[FilingStatus, Query(description="IRS filing status")],
    num_children: Annotated[int, Query(description="Number of qualifying children for child tax credit", ge=0)] = 0,
    use_standard_deduction: Annotated[
        bool,
        Query(description="Use IRS standard deduction; set false to supply itemized amount"),
    ] = True,
    itemized_deduction_amount: Annotated[
        float,
        Query(
            description="Total itemized deductions; only used when use_standard_deduction is false",
            ge=0,
        ),
    ] = 0,
    *,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaxReconciliationResponse:
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
        # Call the service function with injected calculator
        return await calculate_taxes_from_database(
            db=db,
            year=year,
            tax_calculator=TaxCalculator(tax_year=year),
            filing_status=filing_status,
            num_children=num_children,
            use_standard_deduction=use_standard_deduction,
            itemized_deductions=itemized_deduction_amount,
        )

    except TaxCalculationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DataLoadError as e:
        raise HTTPException(status_code=500, detail=f"Database tax calculation failed: {e!s}") from e


@router.get(
    "/fica/{year}",
    summary="Get FICA limits for a year",
    response_description="FICA wage bases and rates",
    responses={404: {"description": "Tax data not available for requested year"}},
)
async def get_fica_info(
    year: _TaxYearPath,  # noqa: ARG001 — path param consumed by get_tax_data dependency
    tax_data: Annotated[tuple[TaxBrackets, FICALimits], Depends(get_tax_data)],
) -> FICALimits:
    """Get FICA limits and rates for a given year.

    Args:
        year: Tax year
        tax_data: Injected tax data (brackets and FICA limits)

    Returns:
        FICA limits data
    """
    _, fica_limits = tax_data
    return fica_limits


@router.get(
    "/brackets/{year}",
    summary="Get tax brackets for a year",
    response_description="Tax brackets and standard deduction amounts",
    responses={404: {"description": "Tax data not available for requested year"}},
)
async def get_tax_brackets(
    year: _TaxYearPath,  # noqa: ARG001 — path param consumed by get_tax_data dependency
    tax_data: Annotated[tuple[TaxBrackets, FICALimits], Depends(get_tax_data)],
) -> TaxBrackets:
    """Get tax brackets for a given year.

    Args:
        year: Tax year
        tax_data: Injected tax data (brackets and FICA limits)

    Returns:
        Tax brackets and standard deductions
    """
    tax_brackets, _ = tax_data
    return tax_brackets


@router.get(
    "/tax-data/available-years",
    summary="List available tax years",
    response_description="Years with loaded tax bracket data",
)
async def list_available_years() -> dict[str, Any]:
    """Get list of years with available tax data."""
    years = get_available_years()
    return {
        "available_years": years,
        "latest_year": max(years) if years else None,
        "data_directory": str(settings.data_dir),
    }


@router.post(
    "/tax-data/upload/{year}",
    summary="Upload tax bracket data",
    response_description="Upload confirmation with saved file path",
    responses={400: {"description": "Invalid JSON or data validation failure"}},
)
async def upload_tax_data(
    year: _UploadYearPath,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """
    Upload a tax brackets JSON file for a given year.

    Replaces the stored bracket data used for all tax calculations for that year.
    The JSON must conform to the internal `TaxBrackets` schema.
    """
    return await _handle_json_upload(
        year,
        file,
        validator=validate_and_save_tax_brackets,
        success_message="Tax data for {year} uploaded successfully",
    )


@router.post(
    "/fica-data/upload/{year}",
    summary="Upload FICA limits data",
    response_description="Upload confirmation with saved file path",
    responses={400: {"description": "Invalid JSON or data validation failure"}},
)
async def upload_fica_data(
    year: _UploadYearPath,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """
    Upload a FICA limits JSON file for a given year.

    Replaces the stored FICA wage base and rate data used for Social Security
    and Medicare calculations. The JSON must conform to the internal `FICALimits` schema.
    """
    return await _handle_json_upload(
        year,
        file,
        validator=validate_and_save_fica_limits,
        success_message="FICA data for {year} uploaded successfully",
    )


async def _handle_json_upload(
    year: int,
    file: UploadFile,
    *,
    validator: Callable[[int, dict[str, Any]], FilePath],
    success_message: str,
) -> dict[str, Any]:
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be JSON")

    try:
        content = await file.read()
        data = json.loads(content)
        filepath = validator(year, data)
        return {
            "success": True,
            "year": year,
            "file": str(filepath),
            "message": success_message.format(year=year),
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    except DataLoadError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
