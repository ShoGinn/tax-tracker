"""Integration tests for taxes API endpoints."""

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from taxtracker import __version__
from taxtracker.core.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.fixture
def temp_upload_dir():
    """Create a temporary directory for testing file uploads.

    Only used by admin tests that actually test file upload functionality.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.integration
class TestAdminAPI:
    """Integration tests for /admin endpoints."""

    def test_get_available_years(self, client: TestClient):
        """Test getting list of available tax years."""
        response = client.get("/taxes/tax-data/available-years")

        assert response.status_code == 200
        data = response.json()
        assert "available_years" in data
        assert "latest_year" in data
        assert "data_directory" in data
        assert isinstance(data["available_years"], list)
        # Should have at least 2025 data
        assert 2025 in data["available_years"]

    def test_get_tax_data_invalid_year(self, client: TestClient):
        """Test getting tax data for non-existent year."""
        response = client.get("/taxes/tax-data/2099")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_upload_tax_data_success(self, client: TestClient, temp_upload_dir: Path, monkeypatch):
        """Upload valid tax bracket data and verify file is saved."""

        # Point settings to temp dir for this test only
        monkeypatch.setattr(settings, "data_dir", temp_upload_dir)

        year = 2031
        payload = {
            "tax_year": year,
            "tax_brackets": {"single": [{"min": 0, "max": 10000, "rate": 0.1}]},
            "standard_deductions": {"single": 1000},
        }

        response = client.post(
            f"/taxes/tax-data/upload/{year}",
            files={"file": ("tax_brackets.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["year"] == year
        saved_path = temp_upload_dir / f"tax_brackets_{year}.json"
        assert saved_path.exists()
        with saved_path.open() as f:
            saved = json.load(f)
        assert saved["tax_year"] == year
        assert "tax_brackets" in saved
        assert "standard_deductions" in saved

    def test_upload_tax_data_year_mismatch(self, client: TestClient, temp_upload_dir: Path, monkeypatch):
        """Reject tax data when file year does not match path."""

        # Point settings to temp dir for this test only
        monkeypatch.setattr(settings, "data_dir", temp_upload_dir)

        year = 2032
        payload = {
            "tax_year": year + 1,
            "tax_brackets": {"single": [{"min": 0, "max": 10000, "rate": 0.1}]},
            "standard_deductions": {"single": 1000},
        }

        response = client.post(
            f"/taxes/tax-data/upload/{year}",
            files={"file": ("tax_brackets.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 400
        assert "year in file" in response.json()["detail"].lower()
        assert not (temp_upload_dir / f"tax_brackets_{year}.json").exists()

    def test_upload_fica_data_success(self, client: TestClient, temp_upload_dir: Path, monkeypatch):
        """Upload valid FICA limits and verify file is saved."""

        # Point settings to temp dir for this test only
        monkeypatch.setattr(settings, "data_dir", temp_upload_dir)

        year = 2033
        payload = {
            "year": year,
            "social_security": {
                "employee_rate": 0.05,
                "employer_rate": 0.05,
                "total_rate": 0.10,
                "wage_base_limit": 150000,
                "max_employee_tax": 7500,
                "max_employer_tax": 7500,
                "max_combined_tax": 15000,
            },
            "medicare": {
                "employee_rate": 0.02,
                "employer_rate": 0.02,
                "total_rate": 0.04,
                "wage_base_limit": None,
                "note": "Applies to all wages",
            },
        }

        response = client.post(
            f"/taxes/fica-data/upload/{year}",
            files={"file": ("fica_limits.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["year"] == year
        saved_path = temp_upload_dir / f"fica_limits_{year}.json"
        assert saved_path.exists()
        with saved_path.open() as f:
            saved = json.load(f)
        assert saved["year"] == year
        assert "social_security" in saved
        assert "medicare" in saved

    def test_upload_fica_data_missing_fields(self, client: TestClient, temp_upload_dir: Path, monkeypatch):
        """Reject FICA upload when required fields are missing."""

        # Point settings to temp dir for this test only
        monkeypatch.setattr(settings, "data_dir", temp_upload_dir)

        year = 2034
        payload = {
            "year": year,
            "medicare": {
                "employee_rate": 0.02,
                "employer_rate": 0.02,
                "total_rate": 0.04,
            },
        }

        response = client.post(
            f"/taxes/fica-data/upload/{year}",
            files={"file": ("fica_limits.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 400
        assert "missing required fields" in response.json()["detail"].lower()
        assert not (temp_upload_dir / f"fica_limits_{year}.json").exists()


@pytest.mark.integration
class TestTaxesAPI:
    """Integration tests for /taxes endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns app info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Tax Tracker API"
        assert data["version"] == __version__

    def test_health_endpoint(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_tax_brackets_2024(self, client: TestClient):
        """Test getting tax brackets for 2024."""
        response = client.get("/taxes/brackets/2024")

        assert response.status_code == 200
        data = response.json()
        assert data["tax_year"] == 2024
        assert "tax_brackets" in data
        assert "standard_deductions" in data

    def test_get_tax_brackets_filtered(self, client: TestClient):
        """Test getting tax brackets with filing status parameter."""
        response = client.get("/taxes/brackets/2024?filing_status=single")

        assert response.status_code == 200
        data = response.json()
        assert data["tax_year"] == 2024
        assert "tax_brackets" in data

    def test_get_fica_limits_2024(self, client: TestClient):
        """Test getting FICA limits for 2024."""
        response = client.get("/taxes/fica/2024")

        assert response.status_code == 200
        data = response.json()
        assert data["tax_year"] == 2024
        assert "social_security" in data
        assert "medicare" in data

    def test_calculate_taxes(self, client: TestClient):
        """Test POST /taxes/calculate endpoint."""
        payload = {
            "tax_year": 2024,
            "filing_status": "single",
            "w2_gross_income": 50000,
            "num_children": 0,
            "use_standard_deduction": True,
        }

        response = client.post("/taxes/calculate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "taxable_income" in data
        assert "federal_tax_owed" in data
        assert "fica_taxes" in data  # Changed from fica_tax
        assert "total_tax_liability" in data
        assert float(data["taxable_income"]) > 0
        assert float(data["federal_tax_owed"]) > 0

    def test_calculate_taxes_with_children(self, client: TestClient):
        """Test tax calculation with child tax credits."""
        payload = {
            "tax_year": 2024,
            "filing_status": "married_filing_jointly",
            "w2_gross_income": 100000,
            "num_children": 2,
            "use_standard_deduction": True,
        }

        response = client.post("/taxes/calculate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert float(data["child_tax_credits"]) > 0  # Changed from child_tax_credit
        # Credits should reduce total liability
        # Note: fica_taxes is a dict, need to access total_fica
        fica_total = float(data["fica_taxes"]["total_fica"])
        assert float(data["total_tax_liability"]) < float(data["federal_tax_owed"]) + fica_total

    def test_calculate_taxes_invalid_year(self, client: TestClient):
        """Test calculation with invalid year returns validation error."""
        payload = {
            "tax_year": 2099,
            "filing_status": "single",
            "w2_gross_income": 50000,
            "num_children": 0,
        }

        response = client.post("/taxes/calculate", json=payload)

        # Should return 422 validation error - year out of range or not supported
        assert response.status_code == 422
        # Validation errors have detail array
        data = response.json()
        assert "detail" in data

    def test_calculate_taxes_invalid_input(self, client: TestClient):
        """Test calculation with invalid input returns error."""
        payload = {
            "tax_year": 2024,
            "filing_status": "invalid_status",
            "w2_gross_income": -1000,  # Negative income
            "num_children": 0,
        }

        response = client.post("/taxes/calculate", json=payload)

        # Should return validation error
        assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.integration
class TestTaxesAPIDocs:
    """Test API documentation is accessible."""

    def test_openapi_schema(self, client: TestClient):
        """Test OpenAPI schema is accessible."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "/taxes/calculate" in schema["paths"]

    def test_docs_endpoint(self, client: TestClient):
        """Test Swagger UI docs endpoint."""
        response = client.get("/docs")

        assert response.status_code == 200
        assert b"swagger" in response.content.lower()
