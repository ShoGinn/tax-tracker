"""Data loader service for tax brackets and FICA limits."""

import json
from pathlib import Path
from typing import Any

from taxtracker.core.config import DataFileType, settings
from taxtracker.core.exceptions import DataLoadError


def _load_json_file(file_type: DataFileType, year: int) -> dict[str, Any]:
    """Generic function to load a JSON data file.

    Args:
        file_type: Type of data file to load
        year: Tax year

    Returns:
        Data dictionary from JSON file

    Raises:
        DataLoadError: If file not found or invalid JSON
    """
    filepath = settings.get_data_file(file_type, year)

    if not filepath.exists():
        raise DataLoadError(
            f"{file_type.value} file not found for {year}",
            details={"year": year, "expected_path": str(filepath)},
        )

    try:
        with filepath.open() as f:
            data: dict[str, Any] = json.load(f)
            return data
    except json.JSONDecodeError as e:
        raise DataLoadError(
            f"Invalid JSON in {file_type.value} file for {year}",
            details={"year": year, "error": str(e)},
        )


def _validate_and_save_json(
    file_type: DataFileType,
    year: int,
    data: dict[str, Any],
    required_fields: list[str],
    year_field: str,
) -> Path:
    """Generic function to validate and save JSON data.

    Args:
        file_type: Type of data file to save
        year: Tax year
        data: Data dictionary to save
        required_fields: List of required field names
        year_field: Name of the year field in the data

    Returns:
        Path to saved file

    Raises:
        DataLoadError: If validation fails or save fails
    """
    # Validate required fields
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise DataLoadError(
            f"Missing required fields: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields},
        )

    # Verify year matches
    if data[year_field] != year:
        raise DataLoadError(
            f"Year in file ({data[year_field]}) doesn't match expected year ({year})",
            details={"file_year": data[year_field], "expected_year": year},
        )

    # Save file
    filepath = settings.get_data_file(file_type, year)
    try:
        with filepath.open("w") as f:
            json.dump(data, f, indent=2)
        return filepath
    except Exception as e:
        raise DataLoadError(f"Failed to save {file_type.value} file: {e}", details={"year": year})


def load_tax_brackets(year: int) -> dict[str, Any]:
    """Load tax brackets for a given year.

    Args:
        year: Tax year

    Returns:
        Tax brackets data dictionary

    Raises:
        DataLoadError: If file not found or invalid
    """
    return _load_json_file(DataFileType.TAX_BRACKETS, year)


def load_fica_limits(year: int) -> dict[str, Any]:
    """Load FICA limits for a given year.

    Args:
        year: Tax year

    Returns:
        FICA limits data dictionary

    Raises:
        DataLoadError: If file not found or invalid
    """
    return _load_json_file(DataFileType.FICA_LIMITS, year)


def validate_and_save_tax_brackets(year: int, data: dict[str, Any]) -> Path:
    """Validate and save tax bracket data.

    Args:
        year: Tax year
        data: Tax brackets data dictionary

    Returns:
        Path to saved file

    Raises:
        DataLoadError: If validation fails or save fails
    """
    return _validate_and_save_json(
        file_type=DataFileType.TAX_BRACKETS,
        year=year,
        data=data,
        required_fields=["tax_year", "tax_brackets", "standard_deductions"],
        year_field="tax_year",
    )


def validate_and_save_fica_limits(year: int, data: dict[str, Any]) -> Path:
    """Validate and save FICA limits data.

    Args:
        year: Tax year
        data: FICA limits data dictionary

    Returns:
        Path to saved file

    Raises:
        DataLoadError: If validation fails or save fails
    """
    return _validate_and_save_json(
        file_type=DataFileType.FICA_LIMITS,
        year=year,
        data=data,
        required_fields=["year", "social_security", "medicare"],
        year_field="year",
    )


def get_available_years() -> list[int]:
    """Get list of years with available tax data.

    Returns:
        Sorted list of years with tax bracket files
    """
    data_dir = settings.data_dir
    tax_files = list(data_dir.glob("tax_brackets_*.json"))
    return sorted([int(f.stem.split("_")[-1]) for f in tax_files])
