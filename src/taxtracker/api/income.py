"""Income tracking API endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from taxtracker.api.dependencies import get_db
from taxtracker.core.exceptions import DatabaseError, ValidationError
from taxtracker.models.schemas import (  # noqa: TC001
    NonTaxableIncomeCreate,
    NonTaxableIncomeResponse,
    PaycheckCreate,
    PaycheckResponse,
    Retirement1099RCreate,
    Retirement1099RResponse,
)
from taxtracker.services import csv_import, income_service

router = APIRouter(prefix="/income", tags=["Income"])


# ============================================================================
# Paycheck Endpoints
# ============================================================================


@router.post("/paychecks")
async def create_paycheck_entry(
    paycheck: PaycheckCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> PaycheckResponse:
    """Create a new paycheck entry."""
    try:
        return await income_service.create_paycheck(db, paycheck)  # ty: ignore[invalid-return-type]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # Check for foreign key constraint errors
        if "FOREIGN KEY constraint failed" in str(e) or "IntegrityError" in str(type(e).__name__):
            raise HTTPException(status_code=404, detail="Referenced employer not found") from e
        if isinstance(e, DatabaseError):
            raise HTTPException(status_code=500, detail=str(e)) from e
        raise


@router.get("/paychecks")
async def list_paychecks(
    year: int | None = None, *, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[PaycheckResponse]:
    """List all paychecks, optionally filtered by year."""
    try:
        return await income_service.get_paychecks(db, employer_id=None, year=year)  # ty: ignore[invalid-return-type]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/paychecks/{paycheck_id}")
async def delete_paycheck_entry(
    paycheck_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """Delete a paycheck entry."""
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


@router.post("/paychecks/import-csv")
async def import_paychecks_csv_endpoint(
    file: UploadFile, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """
    Import paychecks from CSV file.

    CSV should have columns matching our field names, e.g.:
    employer_name,pay_date,gross_wages,bonus,federal_withholding,social_security,medicare,net_pay
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
                f"Import partially successful - "
                f"{result['success_count']} succeeded, {result['error_count']} failed"
            )

        return {
            "message": message,
            "success_count": result["success_count"],
            "error_count": result["error_count"],
            "total_rows": result["total_rows"],
            "errors": result["errors"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}") from e


# ============================================================================
# Pension Endpoints
# ============================================================================


@router.post("/1099r")
async def create_pension_entry(
    pension: Retirement1099RCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> Retirement1099RResponse:
    """Create a new pension entry."""
    try:
        return await income_service.create_retirement_1099r(db, pension)  # ty: ignore[invalid-return-type]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/1099r")
async def list_pension(
    year: int | None = None, *, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[Retirement1099RResponse]:
    """List all pension entries, optionally filtered by year."""
    try:
        return await income_service.get_retirement_1099rs(db, year)  # ty: ignore[invalid-return-type]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/1099r/{retirement_id}")
async def delete_pension_entry(
    retirement_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """Delete a pension entry."""
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


@router.post("/1099r/import-csv")
async def import_pension_csv_endpoint(
    file: UploadFile, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """Import pension entries from CSV file."""
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
                f"Import partially successful - "
                f"{result['success_count']} succeeded, {result['error_count']} failed"
            )

        return {
            "message": message,
            "success_count": result["success_count"],
            "error_count": result["error_count"],
            "total_rows": result["total_rows"],
            "errors": result.get("errors", []),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}") from e


# ============================================================================
# Non-taxable Endpoints
# ============================================================================


@router.post("/non-taxable")
async def create_va_entry(
    va: NonTaxableIncomeCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> NonTaxableIncomeResponse:
    """Create a new Non-taxable entry."""
    try:
        return await income_service.create_non_taxable_payment(db, va)  # ty: ignore[invalid-return-type]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/non-taxable")
async def list_va_disability(
    year: int | None = None, *, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[NonTaxableIncomeResponse]:
    """List all Non-taxable entries, optionally filtered by year."""
    try:
        return await income_service.get_non_taxable_payments(db, year)  # ty: ignore[invalid-return-type]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/non-taxable/{non_taxable_id}")
async def delete_va_entry(
    non_taxable_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """Delete a Non-taxable entry."""
    try:
        deleted = await income_service.delete_non_taxable_payment(db, non_taxable_id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Non-taxable entry {non_taxable_id} not found"
            )
        return {"message": "Non-taxable entry deleted successfully"}
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/non-taxable/import-csv")
async def import_va_csv_endpoint(
    file: UploadFile, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """Import non-taxable income entries from CSV file."""
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
                f"Import partially successful - "
                f"{result['success_count']} succeeded, {result['error_count']} failed"
            )

        return {
            "message": message,
            "success_count": result["success_count"],
            "error_count": result["error_count"],
            "total_rows": result["total_rows"],
            "errors": result.get("errors", []),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}") from e
