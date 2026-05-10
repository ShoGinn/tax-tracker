"""Additional tests for W4 API endpoints."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from taxtracker.models.database import Employer, Paycheck

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
class TestW4APIOptimize:
    """Tests for W4 optimization endpoint."""

    def test_optimize_single_no_children(self, client: TestClient):
        """Test W4 optimization for single filer with no children."""
        response = client.post(
            "/w4/optimize",
            json={
                "total_annual_w2_income": 60000,
                "paychecks_per_year": 26,
                "filing_status": "single",
                "num_children": 0,
                "target_refund": 0,
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "w4_recommendations" in data
        assert len(data["w4_recommendations"]) > 0
        assert "estimated_tax_liability" in data
        assert "target_total_withholding" in data

    def test_optimize_married_with_children(self, client: TestClient):
        """Test W4 optimization for married with children."""
        response = client.post(
            "/w4/optimize",
            json={
                "total_annual_w2_income": 120000,
                "paychecks_per_year": 24,
                "filing_status": "married_filing_jointly",
                "num_children": 2,
                "target_refund": 1000,
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should have recommendations
        assert "w4_recommendations" in data
        rec = data["w4_recommendations"][0]
        assert "step3_amount" in rec
        # With 2 children, should have child credit
        assert float(rec["step3_amount"]) > 0

    def test_optimize_with_other_income(self, client: TestClient):
        """Test W4 optimization with other income."""
        response = client.post(
            "/w4/optimize",
            json={
                "total_annual_w2_income": 75000,
                "paychecks_per_year": 26,
                "filing_status": "single",
                "num_children": 0,
                "other_annual_income": 15000,  # Pension, interest, etc
                "target_refund": 0,
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should account for other income in withholding
        assert float(data["estimated_tax_liability"]) > 0

    def test_optimize_with_itemized_deductions(self, client: TestClient):
        """Test W4 optimization with itemized deductions."""
        response = client.post(
            "/w4/optimize",
            json={
                "total_annual_w2_income": 150000,
                "paychecks_per_year": 26,
                "filing_status": "married_filing_jointly",
                "num_children": 0,
                "itemized_deductions": 35000,  # Mortgage, charity, etc
                "target_refund": 0,
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Itemized deductions should affect tax liability
        assert "estimated_tax_liability" in data

    def test_optimize_high_earner(self, client: TestClient):
        """Test W4 optimization for high earner."""
        response = client.post(
            "/w4/optimize",
            json={
                "total_annual_w2_income": 300000,
                "paychecks_per_year": 26,
                "filing_status": "single",
                "num_children": 0,
                "target_refund": 0,
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # High earner should have significant withholding
        assert float(data["estimated_tax_liability"]) > 50000

    def test_optimize_target_large_refund(self, client: TestClient):
        """Test W4 optimization targeting large refund."""
        response = client.post(
            "/w4/optimize",
            json={
                "total_annual_w2_income": 80000,
                "paychecks_per_year": 26,
                "filing_status": "single",
                "num_children": 0,
                "target_refund": 5000,  # Want large refund
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should recommend extra withholding
        rec = data["w4_recommendations"][0]
        assert float(rec["step4c_extra_withholding"]) > 0

    async def test_optimize_midyear_from_db(self, client: TestClient, async_db_session):
        """Mid-year endpoint should use DB paychecks and return YTD breakdown."""
        employer = Employer(name="DB Corp", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add_all(
            [
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 1, 15),
                    gross_wages=Decimal(3000),
                    federal_withholding=Decimal(320),
                ),
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 1, 31),
                    gross_wages=Decimal(3100),
                    federal_withholding=Decimal(330),
                ),
            ]
        )
        await async_db_session.commit()

        response = client.post(
            "/w4/optimize-midyear-from-db",
            json={
                "tax_year": 2024,
                "filing_status": "single",
                "remaining_pay_periods": 10,
                "num_children": 0,
                "target_refund": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "w4_recommendations" in data
        assert "ytd_summary" in data
        assert len(data["ytd_summary"]["employers"]) == 1
        assert data["ytd_summary"]["employers"][0]["employer_name"] == "DB Corp"

    async def test_optimize_midyear_from_db_with_override(self, client: TestClient, async_db_session):
        """Employer override should drive projected remaining gross in API response."""
        employer = Employer(name="Override API Corp", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add(
            Paycheck(
                employer_id=employer.id,
                pay_date=date(2024, 2, 15),
                gross_wages=Decimal(2500),
                federal_withholding=Decimal(250),
            )
        )
        await async_db_session.commit()

        response = client.post(
            "/w4/optimize-midyear-from-db",
            json={
                "tax_year": 2024,
                "filing_status": "single",
                "remaining_pay_periods": 4,
                "num_children": 0,
                "target_refund": 0,
                "employer_overrides": [
                    {
                        "employer_id": employer.id,
                        "expected_remaining_gross_per_paycheck": 5000,
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        projected_remaining = Decimal(data["ytd_summary"]["employers"][0]["projected_remaining_gross"])
        assert projected_remaining == Decimal(20000)

    async def test_optimize_midyear_from_db_with_as_of_date(self, client: TestClient, async_db_session):
        """as_of_date should limit YTD records included in optimization."""
        employer = Employer(name="Cutoff API Corp", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add_all(
            [
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 1, 15),
                    gross_wages=Decimal(3000),
                    federal_withholding=Decimal(300),
                ),
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 3, 15),
                    gross_wages=Decimal(4000),
                    federal_withholding=Decimal(400),
                ),
            ]
        )
        await async_db_session.commit()

        response = client.post(
            "/w4/optimize-midyear-from-db",
            json={
                "tax_year": 2024,
                "as_of_date": "2024-02-01",
                "filing_status": "single",
                "remaining_pay_periods": 4,
                "target_refund": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        employer_summary = data["ytd_summary"]["employers"][0]
        assert Decimal(employer_summary["ytd_gross"]) == Decimal(3000)
        assert data["ytd_summary"]["as_of_date"] == "2024-02-01"


@pytest.mark.integration
class TestW4APIWithholding:
    """Tests for withholding calculation endpoints."""

    def test_calculate_withholding_biweekly(self, client: TestClient):
        """Test withholding calculation for biweekly paycheck."""
        response = client.post(
            "/w4/calculate-withholding",
            json={
                "gross_pay_per_paycheck": 3000,
                "pay_frequency": "biweekly",
                "filing_status": "single",
                "multiple_jobs_checkbox": False,
                "dependents_amount": 0,
                "other_income_annual": 0,
                "deductions_annual": 0,
                "extra_withholding": 0,
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "withholding_per_paycheck" in data or "federal_withholding" in data
        assert "annual_withholding" in data
        # Check that withholding is calculated
        withholding = data.get("withholding_per_paycheck") or data.get("federal_withholding")
        assert float(withholding) > 0

    def test_calculate_withholding_weekly(self, client: TestClient):
        """Test withholding calculation for weekly paycheck."""
        response = client.post(
            "/w4/calculate-withholding",
            json={
                "gross_pay_per_paycheck": 1500,
                "pay_frequency": "weekly",
                "filing_status": "married_filing_jointly",
                "multiple_jobs_checkbox": False,
                "dependents_amount": 4000,  # 2 children
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Dependents should reduce withholding
        assert "withholding_per_paycheck" in data or "federal_withholding" in data

    def test_calculate_withholding_with_extra(self, client: TestClient):
        """Test withholding with extra withholding amount."""
        response = client.post(
            "/w4/calculate-withholding",
            json={
                "gross_pay_per_paycheck": 4000,
                "pay_frequency": "biweekly",
                "filing_status": "single",
                "multiple_jobs_checkbox": False,
                "dependents_amount": 0,
                "extra_withholding": 200,  # Extra $200 per check
                "year": 2024,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should include extra withholding
        withholding = data.get("withholding_per_paycheck") or data.get("federal_withholding")
        assert float(withholding) > 200

    def test_calculate_withholding_monthly(self, client: TestClient):
        """Test withholding for monthly paycheck."""
        response = client.post(
            "/w4/calculate-withholding",
            json={
                "gross_pay_per_paycheck": 6500,
                "pay_frequency": "monthly",
                "filing_status": "married_filing_jointly",
                "multiple_jobs_checkbox": False,
                "dependents_amount": 0,
                "year": 2024,
            },
        )

        assert response.status_code == 200
