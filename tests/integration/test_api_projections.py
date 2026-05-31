"""Tests for projections API endpoints."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from taxtracker.models.database import Employer, NonTaxableIncome, Paycheck, Retirement1099R

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
class TestProjectionsAPI:
    """Integration tests for /projections endpoints."""

    def test_project_year_basic(self, client: TestClient):
        """Test basic year projection."""
        response = client.post(
            "/projections/project-year",
            json={
                "projection_year": 2024,
                "filing_status": "single",
                "num_children": 0,
                "w2_gross": 75000,
                "w2_pretax_deductions": 0,
                "pension_gross": 0,
                "pension_pretax_deductions": 0,
                "va_disability": 0,
                "use_standard_deduction": True,
                "itemized_deduction_amount": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify projection structure
        assert "year" in data
        assert "filing_status" in data
        assert "total_taxable_income" in data
        assert "federal_tax_liability" in data
        assert "fica_liability" in data
        assert "total_tax_liability" in data

        # Verify calculations are reasonable
        assert float(data["total_taxable_income"]) > 0
        assert float(data["federal_tax_liability"]) > 0
        assert float(data["fica_liability"]) > 0

    def test_project_year_with_children(self, client: TestClient):
        """Test projection with child tax credits."""
        response = client.post(
            "/projections/project-year",
            json={
                "projection_year": 2024,
                "filing_status": "married_filing_jointly",
                "num_children": 2,
                "w2_gross": 100000,
                "use_standard_deduction": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should include child tax credit effects
        assert "total_tax_liability" in data
        assert float(data["total_tax_liability"]) > 0

    def test_project_year_with_pension(self, client: TestClient):
        """Test projection with pension income."""
        response = client.post(
            "/projections/project-year",
            json={
                "projection_year": 2024,
                "filing_status": "single",
                "num_children": 0,
                "w2_gross": 50000,
                "pension_gross": 25000,
                "pension_pretax_deductions": 2500,
                "use_standard_deduction": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should include both W2 and pension
        assert float(data["total_taxable_income"]) > 50000

    def test_project_year_itemized_deductions(self, client: TestClient):
        """Test projection with itemized deductions."""
        response = client.post(
            "/projections/project-year",
            json={
                "projection_year": 2024,
                "filing_status": "single",
                "num_children": 0,
                "w2_gross": 100000,
                "use_standard_deduction": False,
                "itemized_deduction_amount": 25000,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Taxable income should be reduced by itemized deductions
        assert float(data["taxable_income"]) < 100000

    def test_project_high_income(self, client: TestClient):
        """Test projection with high income."""
        response = client.post(
            "/projections/project-year",
            json={
                "projection_year": 2024,
                "filing_status": "single",
                "num_children": 0,
                "w2_gross": 500000,
                "use_standard_deduction": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should handle high income correctly
        assert float(data["federal_tax_liability"]) > 100000

    def test_project_low_income(self, client: TestClient):
        """Test projection with low income."""
        response = client.post(
            "/projections/project-year",
            json={
                "projection_year": 2024,
                "filing_status": "single",
                "num_children": 0,
                "w2_gross": 15000,
                "use_standard_deduction": True,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Low income might have no federal tax
        assert float(data["federal_tax_liability"]) >= 0


@pytest.mark.integration
class TestDashboardProjectionAPI:
    """Integration tests for GET /projections/dashboard/{year}."""

    def test_dashboard_projection_empty_db_returns_zeros(self, client: TestClient) -> None:
        """With no income records, projected amounts should all be zero (or close to it)."""
        response = client.get("/projections/dashboard/2025")
        assert response.status_code == 200
        data = response.json()

        assert data["year"] == 2025
        assert "ytd" in data
        assert "projected" in data
        assert "remaining_periods" in data
        assert float(data["ytd"]["w2_gross"]) == 0.0
        assert float(data["projected"]["w2_gross"]) == 0.0

    def test_dashboard_projection_unsupported_year_returns_error(self, client: TestClient) -> None:
        """Years without bracket data should return a non-200 status."""
        response = client.get("/projections/dashboard/2020")
        assert response.status_code in (400, 500)

    def test_dashboard_projection_structure(self, client: TestClient) -> None:
        """Response should include expected top-level keys."""
        response = client.get("/projections/dashboard/2025")
        assert response.status_code == 200
        data = response.json()

        assert "year" in data
        assert "is_current_year" in data
        assert "as_of_date" in data
        assert "ytd" in data
        assert "projected" in data
        assert "remaining_periods" in data
        assert isinstance(data["remaining_periods"], dict)

    @pytest.mark.asyncio
    async def test_dashboard_projection_with_w2_income(self, client: TestClient, async_db_session) -> None:
        """Current-year projection with recorded paychecks should extrapolate remaining periods."""

        current_year = datetime.now(UTC).year

        employer = Employer(name="Test Corp", start_date=date(current_year, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add_all(
            [
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(current_year, 1, 15),
                    gross_wages=Decimal(5000),
                    federal_withholding=Decimal(600),
                ),
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(current_year, 2, 15),
                    gross_wages=Decimal(5000),
                    federal_withholding=Decimal(600),
                ),
            ]
        )
        await async_db_session.commit()

        response = client.get(f"/projections/dashboard/{current_year}")
        assert response.status_code == 200
        data = response.json()

        assert data["is_current_year"] is True
        assert data["ytd"]["paycheck_count"] == 2
        assert float(data["ytd"]["w2_gross"]) == 10000.0
        # Projected should be >= YTD since there are remaining periods
        assert float(data["projected"]["w2_gross"]) >= float(data["ytd"]["w2_gross"])
        assert float(data["projected"]["total_tax_liability"]) > 0

    @pytest.mark.asyncio
    async def test_dashboard_projection_current_period_entry_reduces_remaining(
        self, client: TestClient, async_db_session
    ) -> None:
        """If a paycheck exists in the current period, remaining_pay_periods is reduced by 1.

        This verifies that entering a paycheck today (monthly frequency) does not
        double-count the current month as a "remaining" period.
        """

        current_year = datetime.now(UTC).year
        today = datetime.now(UTC).date()

        employer = Employer(name="Period Corp", start_date=date(current_year, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add(
            Paycheck(
                employer_id=employer.id,
                pay_date=today,
                gross_wages=Decimal(3000),
                federal_withholding=Decimal(400),
            )
        )
        await async_db_session.commit()

        # Set pay frequency to monthly
        client.put("/config", json={"w2_pay_frequency": "monthly"})

        response = client.get(f"/projections/dashboard/{current_year}")
        assert response.status_code == 200
        data = response.json()

        assert data["is_current_year"] is True
        remaining_w2 = data["remaining_periods"]["w2"]
        # Current period is covered — remaining should be <= months left minus current month
        months_left_naive = 12 - today.month + 1
        assert remaining_w2 <= months_left_naive - 1

    @pytest.mark.asyncio
    async def test_dashboard_projection_with_pension_and_va(self, client: TestClient, async_db_session) -> None:
        """Pension and VA income should be projected with their own remaining period counts."""

        current_year = datetime.now(UTC).year

        async_db_session.add_all(
            [
                Retirement1099R(
                    pay_date=date(current_year, 1, 1),
                    gross_amount=Decimal(2000),
                    pretax_deductions=Decimal(100),
                    federal_withholding=Decimal(200),
                ),
                NonTaxableIncome(
                    pay_date=date(current_year, 1, 1),
                    amount=Decimal(1500),
                    source_type="VA Disability",
                ),
            ]
        )
        await async_db_session.commit()

        response = client.get(f"/projections/dashboard/{current_year}")
        assert response.status_code == 200
        data = response.json()

        assert float(data["ytd"]["pension_gross"]) == 2000.0
        assert float(data["ytd"]["va_income"]) == 1500.0
        assert float(data["projected"]["pension_gross"]) >= float(data["ytd"]["pension_gross"])
