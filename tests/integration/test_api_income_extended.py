"""Additional tests for income API endpoints."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from taxtracker.models.database import Employer, Paycheck, Retirement1099R


@pytest.mark.integration
class TestIncomeAPICreate:
    """Tests for creating income entries."""

    async def test_create_paycheck_minimal(self, client: TestClient, async_db_session):
        """Test creating paycheck with minimal data."""

        # Create employer first
        employer = Employer(name="Test Corp", ein="12-3456789", start_date=date(2025, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        response = client.post(
            "/income/paychecks",
            json={
                "employer_id": employer.id,
                "pay_date": "2025-01-15",
                "gross_wages": 5000.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert float(data["gross_wages"]) == 5000.0
        assert data["employer_id"] == employer.id

    async def test_create_paycheck_full(self, client: TestClient, async_db_session):
        """Test creating paycheck with all fields."""

        employer = Employer(name="Full Test Corp", ein="98-7654321", start_date=date(2025, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        response = client.post(
            "/income/paychecks",
            json={
                "employer_id": employer.id,
                "pay_date": "2025-01-31",
                "gross_wages": 6000.0,
                "bonus": 1000.0,
                "deduction_401k": 500.0,
                "deduction_health_insurance": 200.0,
                "federal_withholding": 800.0,
                "social_security": 372.0,
                "medicare": 87.0,
                "notes": "Test paycheck with all fields",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert float(data["bonus"]) == 1000.0
        assert float(data["deduction_401k"]) == 500.0
        assert data["notes"] == "Test paycheck with all fields"

    def test_create_retirement_1099r(self, client: TestClient):
        """Test creating pension payment."""
        response = client.post(
            "/income/1099r",
            json={
                "pay_date": "2025-01-01",
                "gross_amount": 3500.0,
                "pretax_deductions": 350.0,
                "federal_withholding": 400.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert float(data["gross_amount"]) == 3500.0
        assert float(data["pretax_deductions"]) == 350.0

    def test_create_non_taxable_disability(self, client: TestClient):
        """Test creating non-taxable benefit payment."""
        response = client.post(
            "/income/non-taxable",
            json={"pay_date": "2025-01-01", "amount": 3500.0, "notes": "Monthly non-taxable benefit"},
        )

        assert response.status_code == 200
        data = response.json()
        assert float(data["amount"]) == 3500.0
        assert data["notes"] == "Monthly non-taxable benefit"


@pytest.mark.integration
class TestIncomeAPIFiltering:
    """Tests for filtering income entries."""

    async def test_filter_paychecks_by_year(self, client: TestClient, async_db_session):
        """Test filtering paychecks by year."""

        # Create employer
        employer = Employer(name="Filter Test Corp", ein="11-2233445", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        # Create paychecks in different years
        paycheck_2024 = Paycheck(
            employer_id=employer.id,
            pay_date=date(2024, 6, 15),
            gross_wages=Decimal("5000"),
        )
        paycheck_2025 = Paycheck(
            employer_id=employer.id,
            pay_date=date(2025, 1, 15),
            gross_wages=Decimal("5500"),
        )
        async_db_session.add_all([paycheck_2024, paycheck_2025])
        await async_db_session.commit()

        # Filter for 2025
        response = client.get("/income/paychecks?year=2025")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["pay_date"] == "2025-01-15"

    async def test_filter_1099r_by_year(self, client: TestClient, async_db_session):
        """Test filtering pension by year."""

        # Create pension payments
        pension_2024 = Retirement1099R(pay_date=date(2024, 12, 1), gross_amount=Decimal("3000"))
        pension_2025 = Retirement1099R(pay_date=date(2025, 1, 1), gross_amount=Decimal("3200"))
        async_db_session.add_all([pension_2024, pension_2025])
        await async_db_session.commit()

        # Filter for 2025
        response = client.get("/income/1099r?year=2025")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert float(data[0]["gross_amount"]) == 3200.0


@pytest.mark.integration
class TestIncomeAPIValidation:
    """Tests for input validation."""

    def test_create_paycheck_invalid_date(self, client: TestClient, db_session):
        """Test creating paycheck with invalid date."""

        employer = Employer(name="Date Test Corp", ein="33-4455667", start_date=date(2025, 1, 1))
        db_session.add(employer)
        db_session.commit()

        response = client.post(
            "/income/paychecks",
            json={
                "employer_id": employer.id,
                "pay_date": "invalid-date",
                "gross_wages": 5000.0,
            },
        )

        # Should return validation error
        assert response.status_code == 422
