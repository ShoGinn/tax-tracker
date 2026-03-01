"""Unit tests for CSV import service."""

import pytest

from taxtracker.services.csv_import import (
    import_paychecks_csv,
    import_pension_csv,
    import_va_csv,
)

pytestmark = pytest.mark.unit


class TestPaycheckCSVImport:
    """Tests for import_paychecks_csv."""

    @pytest.mark.anyio
    async def test_empty_csv(self, async_db_session) -> None:
        """Empty CSV (header only) should return zero counts."""
        csv_content = "employer_name,pay_date,gross_wages,net_pay\n"
        result = await import_paychecks_csv(async_db_session, csv_content)

        assert result["success_count"] == 0
        assert result["error_count"] == 0
        assert result["total_rows"] == 0

    @pytest.mark.anyio
    async def test_empty_csv_no_header(self, async_db_session) -> None:
        """Completely empty CSV should return zero counts."""
        result = await import_paychecks_csv(async_db_session, "")
        assert result["total_rows"] == 0

    @pytest.mark.anyio
    async def test_import_with_identity_mapping(self, async_db_session) -> None:
        """Import using default column names (no explicit mapping)."""
        csv_content = (
            "employer_name,pay_date,gross_wages,federal_withholding,"
            "social_security,medicare,net_pay\n"
            "Test Corp,2024-01-15,5000.00,750.00,310.00,72.50,3867.50\n"
        )
        result = await import_paychecks_csv(async_db_session, csv_content)

        assert result["success_count"] == 1
        assert result["error_count"] == 0

    @pytest.mark.anyio
    async def test_import_auto_creates_employer(self, async_db_session) -> None:
        """Import should auto-create employer from name if not found."""
        csv_content = (
            "employer_name,pay_date,gross_wages,federal_withholding,"
            "social_security,medicare,net_pay\n"
            "New Employer LLC,2024-02-01,6000.00,900.00,372.00,87.00,4641.00\n"
        )
        result = await import_paychecks_csv(async_db_session, csv_content)

        assert result["success_count"] == 1
        assert result["error_count"] == 0

    @pytest.mark.anyio
    async def test_import_with_custom_mapping(self, async_db_session) -> None:
        """Import using custom column mapping."""
        csv_content = (
            "company,date,gross,fed_tax,ss_tax,med_tax,take_home\n"
            "Mapped Corp,2024-03-01,7000.00,1050.00,434.00,101.50,5413.50\n"
        )
        mapping = {
            "employer_name": "company",
            "pay_date": "date",
            "gross_wages": "gross",
            "federal_withholding": "fed_tax",
            "social_security": "ss_tax",
            "medicare": "med_tax",
            "net_pay": "take_home",
        }
        result = await import_paychecks_csv(async_db_session, csv_content, column_mapping=mapping)

        assert result["success_count"] == 1
        assert result["error_count"] == 0

    @pytest.mark.anyio
    async def test_import_row_error_handling(self, async_db_session) -> None:
        """Invalid rows should be tracked as errors."""
        csv_content = (
            "employer_name,pay_date,gross_wages,net_pay\nTest Corp,not-a-date,5000.00,4000.00\n"
        )
        result = await import_paychecks_csv(async_db_session, csv_content)

        assert result["error_count"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["row"] == 2

    @pytest.mark.anyio
    async def test_import_missing_employer(self, async_db_session) -> None:
        """Row without employer_name or employer_id should fail."""
        csv_content = "pay_date,gross_wages,net_pay\n2024-01-15,5000.00,4000.00\n"
        result = await import_paychecks_csv(async_db_session, csv_content)

        assert result["error_count"] == 1

    @pytest.mark.anyio
    async def test_import_partial_success(self, async_db_session) -> None:
        """Mix of valid and invalid rows."""
        csv_content = (
            "employer_name,pay_date,gross_wages,federal_withholding,"
            "social_security,medicare,net_pay\n"
            "Good Corp,2024-01-15,5000.00,750.00,310.00,72.50,3867.50\n"
            "Bad Corp,invalid-date,abc,0,0,0,0\n"
        )
        result = await import_paychecks_csv(async_db_session, csv_content)

        assert result["success_count"] == 1
        assert result["error_count"] == 1
        assert result["total_rows"] == 2


class TestPensionCSVImport:
    """Tests for import_pension_csv."""

    @pytest.mark.anyio
    async def test_empty_csv(self, async_db_session) -> None:
        """Empty CSV should return zero counts."""
        csv_content = "pay_date,gross_amount,net_amount\n"
        result = await import_pension_csv(async_db_session, csv_content)

        assert result["total_rows"] == 0

    @pytest.mark.anyio
    async def test_basic_import(self, async_db_session) -> None:
        """Basic pension CSV import."""
        csv_content = (
            "pay_date,gross_amount,net_amount,federal_withholding\n"
            "2024-01-01,3000.00,2700.00,300.00\n"
        )
        result = await import_pension_csv(async_db_session, csv_content)

        assert result["success_count"] == 1
        assert result["error_count"] == 0

    @pytest.mark.anyio
    async def test_import_error_handling(self, async_db_session) -> None:
        """Invalid pension rows should be tracked as errors."""
        csv_content = "pay_date,gross_amount,net_amount\nnot-a-date,abc,def\n"
        result = await import_pension_csv(async_db_session, csv_content)

        assert result["error_count"] == 1


class TestVACSVImport:
    """Tests for import_va_csv."""

    @pytest.mark.anyio
    async def test_empty_csv(self, async_db_session) -> None:
        """Empty CSV should return zero counts."""
        csv_content = "pay_date,amount\n"
        result = await import_va_csv(async_db_session, csv_content)

        assert result["total_rows"] == 0

    @pytest.mark.anyio
    async def test_basic_import(self, async_db_session) -> None:
        """Basic VA disability CSV import."""
        csv_content = "pay_date,amount,source_type\n2024-01-01,2000.00,va_disability\n"
        result = await import_va_csv(async_db_session, csv_content)

        assert result["success_count"] == 1
        assert result["error_count"] == 0

    @pytest.mark.anyio
    async def test_import_error_handling(self, async_db_session) -> None:
        """Invalid VA rows should be tracked as errors."""
        csv_content = "pay_date,amount\nnot-a-date,abc\n"
        result = await import_va_csv(async_db_session, csv_content)

        assert result["error_count"] == 1
        assert len(result["errors"]) == 1

    @pytest.mark.anyio
    async def test_multiple_rows(self, async_db_session) -> None:
        """Multiple valid rows should all import."""
        csv_content = (
            "pay_date,amount,source_type\n"
            "2024-01-01,2000.00,va_disability\n"
            "2024-02-01,2000.00,va_disability\n"
            "2024-03-01,2000.00,va_disability\n"
        )
        result = await import_va_csv(async_db_session, csv_content)

        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert result["total_rows"] == 3
