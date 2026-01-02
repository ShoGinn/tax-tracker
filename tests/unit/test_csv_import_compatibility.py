"""Test CSV import with new field names."""

from decimal import Decimal
from io import StringIO

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.models.database import NonTaxableIncome, Retirement1099R
from taxtracker.services import csv_import


class TestCSVImportBackwardCompatibility:
    """Test that CSV import works with new field names."""

    async def test_import_1099r_with_new_fields(self, async_db_session: AsyncSession):
        """Test importing 1099-R with new simplified field names."""
        csv_content = """pay_date,gross_amount,pretax_deductions,posttax_deductions,federal_withholding,state_withholding,source_description
2024-06-01,5000.00,500.00,100.00,600.00,50.00,Retirement distribution
2024-06-15,5000.00,500.00,100.00,600.00,50.00,Retirement distribution"""

        result = await csv_import.import_pension_csv(async_db_session, csv_content)

        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert result["total_rows"] == 2

    async def test_import_1099r_missing_required_field(self, async_db_session: AsyncSession):
        """Test that invalid data causes errors."""
        csv_content = """pay_date,gross_amount
INVALID_DATE,5000.00"""

        result = await csv_import.import_pension_csv(async_db_session, csv_content)

        assert result["success_count"] == 0
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1
        assert "date" in result["errors"][0]["error"].lower()

    async def test_import_non_taxable_with_source_type(self, async_db_session: AsyncSession):
        """Test importing non-taxable income with source_type."""
        csv_content = """pay_date,amount,source_type,notes
2024-06-01,3000.00,Non-taxable benefit,Monthly payment
2024-06-15,3000.00,SSA Disability,Bi-weekly"""

        result = await csv_import.import_va_csv(async_db_session, csv_content)

        assert result["success_count"] == 2
        assert result["error_count"] == 0

        # Verify source_type was saved
        result = await async_db_session.execute(select(NonTaxableIncome))
        entries = list(result.scalars().all())
        assert len(entries) == 2
        assert entries[0].source_type == "Non-taxable benefit"
        assert entries[1].source_type == "SSA Disability"
