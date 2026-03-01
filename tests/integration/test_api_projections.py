"""Tests for projections API endpoints."""

from typing import TYPE_CHECKING

import pytest

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
