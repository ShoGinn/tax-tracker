"""Admin API endpoints for data management."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from taxtracker.core.config import settings
from taxtracker.core.exceptions import DataLoadError
from taxtracker.services.data_loader import (
    get_available_years,
    load_fica_limits,
    load_tax_brackets,
    validate_and_save_fica_limits,
    validate_and_save_tax_brackets,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/tax-data/available-years")
async def list_available_years() -> dict[str, Any]:
    """Get list of years with available tax data."""
    years = get_available_years()
    return {
        "available_years": years,
        "latest_year": max(years) if years else None,
        "data_directory": str(settings.data_dir),
    }


@router.get("/tax-data/{year}")
async def get_tax_data(year: int) -> dict[str, Any]:
    """Get complete tax data for a specific year."""
    try:
        tax_data = load_tax_brackets(year)
        fica_data = load_fica_limits(year)
        return {"tax_brackets": tax_data, "fica_limits": fica_data}
    except DataLoadError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/tax-data/upload/{year}")
async def upload_tax_data(year: int, file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    return await _handle_json_upload(
        year,
        file,
        validator=validate_and_save_tax_brackets,
        success_message="Tax data for {year} uploaded successfully",
    )


@router.post("/fica-data/upload/{year}")
async def upload_fica_data(year: int, file: Annotated[UploadFile, File()]) -> dict[str, Any]:
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
    validator: Callable[[int, dict[str, Any]], Path],
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
