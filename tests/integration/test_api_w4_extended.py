"""Additional tests for W4 API endpoints."""

from typing import TYPE_CHECKING

import pytest

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
