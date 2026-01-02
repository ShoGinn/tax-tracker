"""Integration tests for taxes API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestTaxesAPI:
    """Integration tests for /taxes endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns app info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Tax Tracker API"
        assert data["version"] == "1.0.0"

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
        assert data["year"] == 2024
        assert "tax_brackets" in data
        assert "standard_deductions" in data

    def test_get_tax_brackets_filtered(self, client: TestClient):
        """Test getting tax brackets filtered by filing status."""
        response = client.get("/taxes/brackets/2024?filing_status=single")

        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2024
        assert data["filing_status"] == "single"
        assert "brackets" in data
        assert isinstance(data["brackets"], list)

    def test_get_fica_limits_2024(self, client: TestClient):
        """Test getting FICA limits for 2024."""
        response = client.get("/taxes/fica/2024")

        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2024
        assert "social_security" in data
        assert "medicare" in data

    def test_calculate_taxes(self, client: TestClient):
        """Test POST /taxes/calculate endpoint."""
        payload = {
            "tax_year": 2024,
            "filing_status": "single",
            "gross_income": 50000,
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
            "gross_income": 100000,
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
            "gross_income": 50000,
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
            "gross_income": -1000,  # Negative income
            "num_children": 0,
        }

        response = client.post("/taxes/calculate", json=payload)

        # Should return validation error
        assert response.status_code == 422


@pytest.mark.integration
class TestTaxesDatabaseAPI:
    """Tests for database-based tax calculations."""

    def test_get_brackets_nonexistent_year(self, client: TestClient):
        """Test getting brackets for non-existent year."""
        response = client.get("/taxes/brackets/2099")

        assert response.status_code == 404

    def test_get_fica_nonexistent_year(self, client: TestClient):
        """Test getting FICA for non-existent year."""
        response = client.get("/taxes/fica/2099")

        assert response.status_code == 404


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
