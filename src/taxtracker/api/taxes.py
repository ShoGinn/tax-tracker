"""Tax calculation API endpoints."""

import json
import logging
from collections.abc import Callable  # noqa: TC003
from pathlib import Path as FilePath  # noqa: TC003
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile

from taxtracker.api.dependencies import get_tax_data
from taxtracker.api.errors import internal_server_error
from taxtracker.api.uploads import read_limited_upload
from taxtracker.core.config import settings
from taxtracker.core.exceptions import DataLoadError, TaxCalculationError
from taxtracker.models.browser_records import ReconciliationSnapshot  # noqa: TC001
from taxtracker.models.tax_data import (  # noqa: TC001
    FICALimits,
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
from taxtracker.services.record_tax_calculator import calculate_taxes_from_records
from taxtracker.services.tax_calculator import TaxCalculator

router = APIRouter(prefix="/taxes", tags=["Taxes"])
logger = logging.getLogger(__name__)

# Reusable path parameter types for year-scoped endpoints
_TaxYearPath = Annotated[int, Path(description="Tax year (e.g. 2025, 2026)", ge=2020, le=2030)]
_UploadYearPath = Annotated[int, Path(description="Tax year this data applies to (e.g. 2025, 2026)", ge=2020)]


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
        raise internal_server_error(logger, "Tax calculation data load", e) from e


@router.post(
    "/reconcile-records/{year}",
    summary="Reconcile taxes from browser records",
    response_description="Tax reconciliation with withholding comparison",
    responses={400: {"description": "Invalid input or unsupported tax year"}},
)
async def reconcile_browser_records(
    year: Annotated[int, Path(description="Tax year to calculate (e.g. 2025, 2026)", ge=2020, le=2030)],
    snapshot: ReconciliationSnapshot,
) -> TaxReconciliationResponse:
    """Calculate using a transient snapshot; personal records are never persisted."""
    try:
        return calculate_taxes_from_records(
            snapshot=snapshot,
            year=year,
            tax_calculator=TaxCalculator(tax_year=year),
        )

    except TaxCalculationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DataLoadError as e:
        raise internal_server_error(logger, "Record reconciliation data load", e) from e


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
        content = await read_limited_upload(file)
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
