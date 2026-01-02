"""CSV import service for bulk loading income data."""

import csv
from io import StringIO
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.models.database import Employer
from taxtracker.models.schemas import (
    EmployerCreate,
    NonTaxableIncomeCreate,
    PaycheckCreate,
    Retirement1099RCreate,
)
from taxtracker.services import income_service


class CSVImportResult:
    """Result of CSV import operation."""

    def __init__(self) -> None:
        self.success_count: int = 0
        self.error_count: int = 0
        self.errors: list[dict[str, Any]] = []

    def add_success(self) -> None:
        self.success_count += 1

    def add_error(self, row_num: int, error: str, row_data: dict[str, Any]) -> None:
        self.error_count += 1
        self.errors.append({"row": row_num, "error": error, "data": row_data})

    def to_dict(self) -> dict[str, Any]:
        return {
            "success_count": self.success_count,
            "error_count": self.error_count,
            "errors": self.errors,
            "total_rows": self.success_count + self.error_count,
        }


def _prepare_row_for_schema(row: dict[str, Any], column_mapping: dict[str, str]) -> dict[str, Any]:
    """Map CSV row data, letting Pydantic handle type conversions and cleaning."""
    mapped_data = {}
    for our_field, csv_column in column_mapping.items():
        value = row.get(csv_column, "")
        if value is None:
            mapped_data[our_field] = ""
        else:
            value_str = value.strip() if isinstance(value, str) else str(value)
            mapped_data[our_field] = value_str
    return mapped_data


async def import_paychecks_csv(
    db: AsyncSession, csv_content: str, column_mapping: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Import paychecks from CSV.

    Args:
        db: Async database session
        csv_content: CSV file content as string
        column_mapping: Optional mapping of CSV column names to our field names.
            If None or empty, uses CSV column names as-is (identity mapping).

            Example CSV with default columns (no mapping needed):
            employer_name,pay_date,gross_wages,bonus,federal_withholding,social_security,medicare,net_pay
            Legion,2025-01-15,5000,0,750,310,72.50,3867.50

    Returns:
        CSVImportResult with success/error counts
    """
    result = CSVImportResult()
    reader = csv.DictReader(StringIO(csv_content))

    # If no mapping provided, use identity mapping (CSV columns = our field names)
    if not column_mapping:
        # Use the CSV's actual column names as-is
        first_row_peek = next(reader, None)
        if first_row_peek is None:
            return result.to_dict()  # Empty CSV

        # Create identity mapping for all columns in the CSV
        column_mapping = {col: col for col in first_row_peek}

        # Reset reader to start from beginning
        reader = csv.DictReader(StringIO(csv_content))

    for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
        try:
            # Prepare cleaned data for Pydantic
            mapped_data = _prepare_row_for_schema(row, column_mapping)

            # Handle employer (by ID or name)
            if "employer_id" in mapped_data and mapped_data["employer_id"].strip():
                employer_id = int(mapped_data["employer_id"])
            elif "employer_name" in mapped_data and mapped_data["employer_name"].strip():
                # Find or create employer by name
                employer_name = mapped_data["employer_name"].strip()
                result_query = await db.execute(
                    select(Employer).filter(Employer.name == employer_name)
                )
                employer = result_query.scalar_one_or_none()
                if not employer:
                    # Create employer with start date from first paycheck
                    employer = await income_service.create_employer(
                        db,
                        EmployerCreate(
                            name=employer_name,
                            ein=None,
                            start_date=mapped_data["pay_date"],
                        ),
                    )
                employer_id = employer.id
            else:
                raise ValueError(
                    f"Must provide either employer_id or employer_name. Got: {mapped_data}"
                )

            # Remove employer_name/id from data before passing to PaycheckCreate
            paycheck_data = {
                k: v for k, v in mapped_data.items() if k not in ("employer_name", "employer_id")
            }
            paycheck_data["employer_id"] = employer_id

            # Let Pydantic handle all type conversions (date, Decimal, etc.)
            paycheck = PaycheckCreate(**paycheck_data)
            await income_service.create_paycheck(db, paycheck)
            result.add_success()

        except Exception as e:
            result.add_error(row_num, str(e), row)

    return result.to_dict()


async def import_pension_csv(
    db: AsyncSession, csv_content: str, column_mapping: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Import 1099-R retirement income from CSV.

    Args:
        db: Async database session
        csv_content: CSV file content as string
        column_mapping: Maps CSV column names to our field names.
            If empty, assumes CSV uses our exact field names (no mapping needed).

            Required fields:
            - pay_date
            - gross_amount
            - net_amount

            Optional fields:
            - pretax_deductions (replaces old sbp_deduction fields)
            - posttax_deductions (replaces old allotment fields)
            - federal_withholding
            - state_withholding
            - source_description
            - notes

    Returns:
        CSVImportResult with success/error counts
    """
    result = CSVImportResult()
    reader = csv.DictReader(StringIO(csv_content))

    # If no mapping provided, use identity mapping
    if not column_mapping:
        first_row_peek = next(reader, None)
        if first_row_peek is None:
            return result.to_dict()
        column_mapping = {col: col for col in first_row_peek}
        reader = csv.DictReader(StringIO(csv_content))

    for row_num, row in enumerate(reader, start=2):
        try:
            mapped_data = _prepare_row_for_schema(row, column_mapping)

            # Let Pydantic handle all type conversions
            payment = Retirement1099RCreate(**mapped_data)
            await income_service.create_retirement_1099r(db, payment)
            result.add_success()

        except Exception as e:
            result.add_error(row_num, str(e), row)

    return result.to_dict()


async def import_va_csv(
    db: AsyncSession, csv_content: str, column_mapping: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Import VA disability payments from CSV.

    Args:
        db: Async database session
        csv_content: CSV file content as string
        column_mapping: Maps CSV column names to our field names.
            If empty, assumes CSV uses our exact field names (no mapping needed).

            Required fields:
            - pay_date
            - amount

    Returns:
        CSVImportResult with success/error counts
    """
    result = CSVImportResult()
    reader = csv.DictReader(StringIO(csv_content))

    # If no mapping provided, use identity mapping
    if not column_mapping:
        first_row_peek = next(reader, None)
        if first_row_peek is None:
            return result.to_dict()
        column_mapping = {col: col for col in first_row_peek}
        reader = csv.DictReader(StringIO(csv_content))

    for row_num, row in enumerate(reader, start=2):
        try:
            mapped_data = _prepare_row_for_schema(row, column_mapping)

            payment = NonTaxableIncomeCreate(
                pay_date=mapped_data.get("pay_date", ""),
                amount=mapped_data.get("amount", "0"),
                source_type=mapped_data.get("source_type"),
                notes=mapped_data.get("notes"),
            )

            await income_service.create_non_taxable_payment(db, payment)
            result.add_success()

        except Exception as e:
            result.add_error(row_num, str(e), row)

    return result.to_dict()
