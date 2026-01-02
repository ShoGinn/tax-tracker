"""Tests for admin API endpoints."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestAdminAPI:
    """Integration tests for /admin endpoints."""

    def test_get_available_years(self, client: TestClient):
        """Test getting list of available tax years."""
        response = client.get("/admin/tax-data/available-years")

        assert response.status_code == 200
        data = response.json()
        assert "available_years" in data
        assert "latest_year" in data
        assert "data_directory" in data
        assert isinstance(data["available_years"], list)
        # Should have at least 2024 data
        assert 2024 in data["available_years"]

    def test_get_tax_data_2024(self, client: TestClient):
        """Test getting complete tax data for 2024."""
        response = client.get("/admin/tax-data/2024")

        assert response.status_code == 200
        data = response.json()
        assert "tax_brackets" in data
        assert "fica_limits" in data

        # Verify structure
        tax_brackets = data["tax_brackets"]
        assert "tax_year" in tax_brackets
        assert "tax_brackets" in tax_brackets
        assert "standard_deductions" in tax_brackets

        fica_limits = data["fica_limits"]
        assert "tax_year" in fica_limits
        assert "social_security" in fica_limits
        assert "medicare" in fica_limits

    def test_get_tax_data_invalid_year(self, client: TestClient):
        """Test getting tax data for non-existent year."""
        response = client.get("/admin/tax-data/2099")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_upload_tax_data_success(self, client: TestClient, temp_tax_data_dir: Path):
        """Upload valid tax bracket data and verify file is saved."""
        year = 2031
        payload = {
            "tax_year": year,
            "tax_brackets": {"single": [{"min": 0, "max": 10000, "rate": 0.1}]},
            "standard_deductions": {"single": 1000},
        }

        response = client.post(
            f"/admin/tax-data/upload/{year}",
            files={"file": ("tax_brackets.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["year"] == year
        saved_path = temp_tax_data_dir / f"tax_brackets_{year}.json"
        assert saved_path.exists()
        with open(saved_path) as f:
            saved = json.load(f)
        assert saved["tax_year"] == year
        assert "tax_brackets" in saved and "standard_deductions" in saved

    def test_upload_tax_data_year_mismatch(self, client: TestClient, temp_tax_data_dir: Path):
        """Reject tax data when file year does not match path."""
        year = 2032
        payload = {
            "tax_year": year + 1,
            "tax_brackets": {"single": [{"min": 0, "max": 10000, "rate": 0.1}]},
            "standard_deductions": {"single": 1000},
        }

        response = client.post(
            f"/admin/tax-data/upload/{year}",
            files={"file": ("tax_brackets.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 400
        assert "year in file" in response.json()["detail"].lower()
        assert not (temp_tax_data_dir / f"tax_brackets_{year}.json").exists()

    def test_upload_fica_data_success(self, client: TestClient, temp_tax_data_dir: Path):
        """Upload valid FICA limits and verify file is saved."""
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
            f"/admin/fica-data/upload/{year}",
            files={"file": ("fica_limits.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["year"] == year
        saved_path = temp_tax_data_dir / f"fica_limits_{year}.json"
        assert saved_path.exists()
        with open(saved_path) as f:
            saved = json.load(f)
        assert saved["year"] == year
        assert "social_security" in saved and "medicare" in saved

    def test_upload_fica_data_missing_fields(self, client: TestClient, temp_tax_data_dir: Path):
        """Reject FICA upload when required fields are missing."""
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
            f"/admin/fica-data/upload/{year}",
            files={"file": ("fica_limits.json", json.dumps(payload), "application/json")},
        )

        assert response.status_code == 400
        assert "missing required fields" in response.json()["detail"].lower()
        assert not (temp_tax_data_dir / f"fica_limits_{year}.json").exists()
