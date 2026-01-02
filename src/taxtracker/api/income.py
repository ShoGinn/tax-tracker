"""Income tracking API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from taxtracker.api.dependencies import get_db
from taxtracker.core.exceptions import DatabaseError, ValidationError
from taxtracker.models.schemas import (
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


@router.post("/paychecks", response_model=PaycheckResponse)
def create_paycheck_entry(
    paycheck: PaycheckCreate, db: Session = Depends(get_db)
) -> PaycheckResponse:
    """Create a new paycheck entry."""
    try:
        return income_service.create_paycheck(db, paycheck)  # type: ignore[return-value]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Check for foreign key constraint errors
        if "FOREIGN KEY constraint failed" in str(e) or "IntegrityError" in str(type(e).__name__):
            raise HTTPException(status_code=404, detail="Referenced employer not found")
        if isinstance(e, DatabaseError):
            raise HTTPException(status_code=500, detail=str(e))
        raise


@router.get("/paychecks", response_model=list[PaycheckResponse])
def list_paychecks(
    year: int | None = None, db: Session = Depends(get_db)
) -> list[PaycheckResponse]:
    """List all paychecks, optionally filtered by year."""
    try:
        return income_service.get_paychecks(db, employer_id=None, year=year)  # type: ignore[return-value]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/paychecks/{paycheck_id}")
def delete_paycheck_entry(paycheck_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Delete a paycheck entry."""
    try:
        deleted = income_service.delete_paycheck(db, paycheck_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Paycheck {paycheck_id} not found")
        return {"message": "Paycheck deleted successfully"}
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/paychecks/import-csv")
async def import_paychecks_csv_endpoint(
    file: UploadFile, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Import paychecks from CSV file.

    CSV should have columns matching our field names, e.g.:
    employer_name,pay_date,gross_wages,bonus,federal_withholding,social_security,medicare,net_pay
    """
    try:
        content = await file.read()
        result = csv_import.import_paychecks_csv(db, content.decode("utf-8"))

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
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}")


# ============================================================================
# Pension Endpoints
# ============================================================================


@router.post("/1099r", response_model=Retirement1099RResponse)
def create_pension_entry(
    pension: Retirement1099RCreate, db: Session = Depends(get_db)
) -> Retirement1099RResponse:
    """Create a new pension entry."""
    try:
        return income_service.create_retirement_1099r(db, pension)  # type: ignore[return-value]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/1099r", response_model=list[Retirement1099RResponse])
def list_pension(
    year: int | None = None, db: Session = Depends(get_db)
) -> list[Retirement1099RResponse]:
    """List all pension entries, optionally filtered by year."""
    try:
        return income_service.get_retirement_1099rs(db, year)  # type: ignore[return-value]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/1099r/{retirement_id}")
def delete_pension_entry(retirement_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Delete a pension entry."""
    try:
        deleted = income_service.delete_retirement_1099r(db, retirement_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Pension entry {retirement_id} not found")
        return {"message": "Pension entry deleted successfully"}
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/1099r/import-csv")
async def import_pension_csv_endpoint(
    file: UploadFile, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Import pension entries from CSV file."""
    try:
        content = await file.read()
        result = csv_import.import_pension_csv(db, content.decode("utf-8"))

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
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}")


# ============================================================================
# VA Disability Endpoints
# ============================================================================


@router.post("/non-taxable", response_model=NonTaxableIncomeResponse)
def create_va_entry(
    va: NonTaxableIncomeCreate, db: Session = Depends(get_db)
) -> NonTaxableIncomeResponse:
    """Create a new VA disability entry."""
    try:
        return income_service.create_non_taxable_payment(db, va)  # type: ignore[return-value]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/non-taxable", response_model=list[NonTaxableIncomeResponse])
def list_va_disability(
    year: int | None = None, db: Session = Depends(get_db)
) -> list[NonTaxableIncomeResponse]:
    """List all VA disability entries, optionally filtered by year."""
    try:
        return income_service.get_non_taxable_payments(db, year)  # type: ignore[return-value]
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/non-taxable/{non_taxable_id}")
def delete_va_entry(non_taxable_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Delete a VA disability entry."""
    try:
        deleted = income_service.delete_non_taxable_payment(db, non_taxable_id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Non-taxable entry {non_taxable_id} not found"
            )
        return {"message": "VA disability entry deleted successfully"}
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/non-taxable/import-csv")
async def import_va_csv_endpoint(file: UploadFile, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Import non-taxable income entries from CSV file."""
    try:
        content = await file.read()
        result = csv_import.import_va_csv(db, content.decode("utf-8"))

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
        raise HTTPException(status_code=400, detail=f"CSV import failed: {e!s}")
