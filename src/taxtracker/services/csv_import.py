"""CSV import service for bulk loading income data."""

import csv
from collections.abc import Awaitable, Callable
from io import StringIO
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from taxtracker.models.database import Employer
from taxtracker.models.schemas import (
    EmployerCreate,
    NonTaxableIncomeCreate,
    PaycheckCreate,
    Retirement1099RCreate,
)
from taxtracker.services import income_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _friendly_error(e: Exception) -> str:
    """Convert technical exceptions to user-friendly messages."""
    if isinstance(e, IntegrityError):
        orig = str(getattr(e, "orig", ""))
        if "UNIQUE constraint failed" in orig:
            return "Duplicate entry — this record already exists and was skipped"
        return "Database error — record could not be saved"
    return str(e)


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


def _setup_reader(
    csv_content: str, column_mapping: dict[str, str] | None
) -> tuple[csv.DictReader[str], dict[str, str]] | None:
    """Set up a CSV reader with a column mapping.

    If column_mapping is None/empty, builds an identity mapping from the CSV headers.
    Returns None when the CSV contains no data rows (empty or header-only).
    """
    reader: csv.DictReader[str] = csv.DictReader(StringIO(csv_content))
    if not column_mapping:
        first_row = next(reader, None)
        if first_row is None:
            return None
        column_mapping = {col: col for col in first_row}
        reader = csv.DictReader(StringIO(csv_content))
    return reader, column_mapping


_RowHandler = Callable[[dict[str, Any]], Awaitable[None]]


async def _process_rows(
    db: AsyncSession,
    reader: csv.DictReader[str],
    column_mapping: dict[str, str],
    result: CSVImportResult,
    handler: _RowHandler,
) -> None:
    """Iterate CSV rows, invoke handler for each, and accumulate success/error counts."""
    for row_num, row in enumerate(reader, start=2):
        raw_row = dict(row)
        try:
            mapped_data = _prepare_row_for_schema(raw_row, column_mapping)
            await handler(mapped_data)
            result.add_success()
        except Exception as e:
            await db.rollback()
            result.add_error(row_num, _friendly_error(e), raw_row)


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
    setup = _setup_reader(csv_content, column_mapping)
    if setup is None:
        return result.to_dict()
    reader, mapping = setup

    async def handler(mapped_data: dict[str, Any]) -> None:
        if "employer_id" in mapped_data and mapped_data["employer_id"].strip():
            employer_id = int(mapped_data["employer_id"])
        elif "employer_name" in mapped_data and mapped_data["employer_name"].strip():
            employer_name = mapped_data["employer_name"].strip()
            result_query = await db.execute(select(Employer).filter(Employer.name == employer_name))
            employer = result_query.scalar_one_or_none()
            if not employer:
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
            raise ValueError(f"Must provide either employer_id or employer_name. Got: {mapped_data}")

        paycheck_data = {k: v for k, v in mapped_data.items() if k not in ("employer_name", "employer_id")}
        paycheck_data["employer_id"] = employer_id
        await income_service.create_paycheck(db, PaycheckCreate(**paycheck_data))

    await _process_rows(db, reader, mapping, result, handler)
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
    setup = _setup_reader(csv_content, column_mapping)
    if setup is None:
        return result.to_dict()
    reader, mapping = setup

    async def handler(mapped_data: dict[str, Any]) -> None:
        await income_service.create_retirement_1099r(db, Retirement1099RCreate(**mapped_data))

    await _process_rows(db, reader, mapping, result, handler)
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
    setup = _setup_reader(csv_content, column_mapping)
    if setup is None:
        return result.to_dict()
    reader, mapping = setup

    async def handler(mapped_data: dict[str, Any]) -> None:
        payment = NonTaxableIncomeCreate(
            pay_date=mapped_data.get("pay_date", ""),
            amount=mapped_data.get("amount", "0"),
            source_type=mapped_data.get("source_type"),
            notes=mapped_data.get("notes"),
        )
        await income_service.create_non_taxable_payment(db, payment)

    await _process_rows(db, reader, mapping, result, handler)
    return result.to_dict()
