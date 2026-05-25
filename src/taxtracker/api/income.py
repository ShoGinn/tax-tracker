"""Income tracking API endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from taxtracker.api.dependencies import get_db
from taxtracker.core.exceptions import DatabaseError, ValidationError
from taxtracker.models.schemas import (  # noqa: TC001
    EmployerCreate,
    EmployerResponse,
    NonTaxableIncomeCreate,
    NonTaxableIncomeResponse,
    PaycheckCreate,
    PaycheckResponse,
    Retirement1099RCreate,
    Retirement1099RResponse,
)
from taxtracker.services import csv_import, income_service

router = APIRouter(prefix="/income", tags=["Income"])

# Reusable query parameter type for optional year filtering
_YearQuery = Annotated[int | None, Query(description="Filter by tax year (e.g. 2025, 2026)", examples=[2026])]


# ============================================================================
# Employer Endpoints
# ============================================================================


@router.get(
    "/employers",
    summary="List employers",
    response_description="List of employer records",
)
async def list_employers(db: Annotated[AsyncSession, Depends(get_db)]) -> list[EmployerResponse]:
    """List all employer records."""
    try:
        return await income_service.get_employers(db)  # ty: ignore[invalid-return-type]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/employers",
    summary="Create employer",
    response_description="Created employer record",
    status_code=201,
    responses={400: {"description": "Validation error"}},
)
async def create_employer_entry(
    employer: EmployerCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> EmployerResponse:
    """Create a new employer record."""
    try:
        return await income_service.create_employer(db, employer)  # ty: ignore[invalid-return-type]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Paycheck Endpoints
# ============================================================================


@router.post(
    "/paychecks",
    summary="Create paycheck entry",
    response_description="Created paycheck with all computed fields",
    responses={
        400: {"description": "Validation error"},
        404: {"description": "Employer not found"},
    },
)
async def create_paycheck_entry(
    paycheck: PaycheckCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> PaycheckResponse:
    """Create a new W-2 paycheck entry with gross wages, deductions, and withholding."""
    try:
        return await income_service.create_paycheck(db, paycheck)  # ty: ignore[invalid-return-type]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except IntegrityError as e:
        raise HTTPException(status_code=404, detail="Referenced employer not found") from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/paychecks",
    summary="List paychecks",
    response_description="List of paycheck entries",
)
async def list_paychecks(
    year: _YearQuery = None,
    *,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PaycheckResponse]:
    """List all W-2 paycheck entries, optionally filtered by tax year."""
    try:
        return await income_service.get_paychecks(db, employer_id=None, year=year)  # ty: ignore[invalid-return-type]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/paychecks/{paycheck_id}",
    summary="Delete paycheck entry",
    response_description="Deletion confirmation",
    responses={
        404: {"description": "Paycheck not found"},
        400: {"description": "Validation error"},
    },
)
async def delete_paycheck_entry(
    paycheck_id: Annotated[int, Path(description="Unique paycheck record ID", ge=1)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Delete a paycheck entry by ID."""
    try:
        deleted = await income_service.delete_paycheck(db, paycheck_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Paycheck {paycheck_id} not found")
        return {"message": "Paycheck deleted successfully"}
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/paychecks/import-csv",
    summary="Import paychecks from CSV",
    response_description="Import result with success/error counts",
    responses={400: {"description": "Invalid file or CSV format"}},
)
async def import_paychecks_csv_endpoint(
    file: UploadFile, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """
    Import paychecks from a CSV file.

    CSV should have columns matching field names, e.g.:
    `employer_name,pay_date,gross_wages,bonus,federal_withholding,social_security,medicare,net_pay`

    Flexible column mapping is applied automatically. Currency symbols and multiple date formats
    are handled. Rows with errors are skipped and reported in the response.
    """
    try:
        content = await file.read()
        result = await csv_import.import_paychecks_csv(db, content.decode("utf-8"))

        # Generate appropriate message
        if result["error_count"] == 0:
            message = "Import successful"
        elif result["success_count"] == 0:
            message = "Import failed - all rows had errors"
        else:
            message = (
                f"Import partially successful - {result['success_count']} succeeded, {result['error_count']} failed"
            )

        return {
            "message": message,
            "imported": result["success_count"],
            "skipped": result["error_count"],
            "total_rows": result["total_rows"],
            "errors": result["errors"],
        }
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid file encoding: {e!s}") from e
    except (ValidationError, DatabaseError) as e:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}") from e


# ============================================================================
# Pension Endpoints
# ============================================================================


@router.post(
    "/1099r",
    summary="Create 1099-R pension entry",
    response_description="Created 1099-R pension entry",
    responses={400: {"description": "Validation error"}},
)
async def create_pension_entry(
    pension: Retirement1099RCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> Retirement1099RResponse:
    """Create a new 1099-R pension/retirement income entry with gross distribution and withholding."""
    try:
        return await income_service.create_retirement_1099r(db, pension)  # ty: ignore[invalid-return-type]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/1099r",
    summary="List 1099-R pension entries",
    response_description="List of 1099-R pension entries",
)
async def list_pension(
    year: _YearQuery = None,
    *,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Retirement1099RResponse]:
    """List all 1099-R pension/retirement income entries, optionally filtered by tax year."""
    try:
        return await income_service.get_retirement_1099rs(db, year)  # ty: ignore[invalid-return-type]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/1099r/{retirement_id}",
    summary="Delete 1099-R pension entry",
    response_description="Deletion confirmation",
    responses={
        404: {"description": "Pension entry not found"},
        400: {"description": "Validation error"},
    },
)
async def delete_pension_entry(
    retirement_id: Annotated[int, Path(description="Unique 1099-R record ID", ge=1)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Delete a 1099-R pension entry by ID."""
    try:
        deleted = await income_service.delete_retirement_1099r(db, retirement_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Pension entry {retirement_id} not found")
        return {"message": "Pension entry deleted successfully"}
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/1099r/import-csv",
    summary="Import 1099-R pensions from CSV",
    response_description="Import result with success/error counts",
    responses={400: {"description": "Invalid file or CSV format"}},
)
async def import_pension_csv_endpoint(file: UploadFile, db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    """
    Import 1099-R pension entries from a CSV file.

    Flexible column mapping is applied automatically. Currency symbols and multiple date formats
    are handled. Rows with errors are skipped and reported in the response.
    """
    try:
        content = await file.read()
        result = await csv_import.import_pension_csv(db, content.decode("utf-8"))

        # Generate appropriate message
        if result["error_count"] == 0:
            message = "Import successful"
        elif result["success_count"] == 0:
            message = "Import failed - all rows had errors"
        else:
            message = (
                f"Import partially successful - {result['success_count']} succeeded, {result['error_count']} failed"
            )

        return {
            "message": message,
            "imported": result["success_count"],
            "skipped": result["error_count"],
            "total_rows": result["total_rows"],
            "errors": result.get("errors", []),
        }
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid file encoding: {e!s}") from e
    except (ValidationError, DatabaseError) as e:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}") from e


# ============================================================================
# Non-taxable Endpoints
# ============================================================================


@router.post(
    "/non-taxable",
    summary="Create non-taxable income entry",
    response_description="Created non-taxable income entry",
    responses={400: {"description": "Validation error"}},
)
async def create_va_entry(
    va: NonTaxableIncomeCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> NonTaxableIncomeResponse:
    """Create a new non-taxable income entry (VA disability, SSA disability, gifts, etc.)."""
    try:
        return await income_service.create_non_taxable_payment(db, va)  # ty: ignore[invalid-return-type]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/non-taxable",
    summary="List non-taxable income entries",
    response_description="List of non-taxable income entries",
)
async def list_va_disability(
    year: _YearQuery = None,
    *,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[NonTaxableIncomeResponse]:
    """List all non-taxable income entries (VA disability, SSA disability, gifts),
    optionally filtered by tax year.
    """
    try:
        return await income_service.get_non_taxable_payments(db, year)  # ty: ignore[invalid-return-type]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/non-taxable/{non_taxable_id}",
    summary="Delete non-taxable income entry",
    response_description="Deletion confirmation",
    responses={
        404: {"description": "Non-taxable entry not found"},
        400: {"description": "Validation error"},
    },
)
async def delete_va_entry(
    non_taxable_id: Annotated[int, Path(description="Unique non-taxable income record ID", ge=1)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Delete a non-taxable income entry by ID."""
    try:
        deleted = await income_service.delete_non_taxable_payment(db, non_taxable_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Non-taxable entry {non_taxable_id} not found")
        return {"message": "Non-taxable entry deleted successfully"}
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/non-taxable/import-csv",
    summary="Import non-taxable income from CSV",
    response_description="Import result with success/error counts",
    responses={400: {"description": "Invalid file or CSV format"}},
)
async def import_va_csv_endpoint(file: UploadFile, db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, Any]:
    """
    Import non-taxable income entries from a CSV file.

    Flexible column mapping is applied automatically. Currency symbols and multiple date formats
    are handled. Rows with errors are skipped and reported in the response.
    """
    try:
        content = await file.read()
        result = await csv_import.import_va_csv(db, content.decode("utf-8"))

        # Generate appropriate message
        if result["error_count"] == 0:
            message = "Import successful"
        elif result["success_count"] == 0:
            message = "Import failed - all rows had errors"
        else:
            message = (
                f"Import partially successful - {result['success_count']} succeeded, {result['error_count']} failed"
            )

        return {
            "message": message,
            "imported": result["success_count"],
            "skipped": result["error_count"],
            "total_rows": result["total_rows"],
            "errors": result.get("errors", []),
        }
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid file encoding: {e!s}") from e
    except (ValidationError, DatabaseError) as e:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}") from e
