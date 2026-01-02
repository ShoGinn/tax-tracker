"""Integration tests for income API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestIncomeAPI:
    """Integration tests for /income endpoints."""

    def test_list_paychecks_empty(self, client: TestClient):
        """Test listing paychecks when database is empty."""
        response = client.get("/income/paychecks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_1099r_empty(self, client: TestClient):
        """Test listing pension entries when database is empty."""
        response = client.get("/income/1099r")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_non_taxable_empty(self, client: TestClient):
        """Test listing non-taxable benefit entries when database is empty."""
        response = client.get("/income/non-taxable")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_delete_nonexistent_paycheck(self, client: TestClient):
        """Test deleting non-existent paycheck returns 404."""
        response = client.delete("/income/paychecks/99999")

        assert response.status_code == 404

    def test_delete_nonexistent_pension(self, client: TestClient):
        """Test deleting non-existent pension returns 404."""
        response = client.delete("/income/1099r/99999")

        assert response.status_code == 404

    def test_delete_nonexistent_va(self, client: TestClient):
        """Test deleting non-existent VA entry returns 404."""
        response = client.delete("/income/non-taxable/99999")

        assert response.status_code == 404


@pytest.mark.integration
class TestIncomeAPICreation:
    """Tests for creating income entries."""

    def test_create_paycheck_missing_employer(self, client: TestClient):
        """Test creating paycheck without employer fails."""
        payload = {
            "pay_date": "2025-01-15",
            "gross_wages": 5000,
            "federal_withholding": 750,
            "social_security": 310,
            "medicare": 72.50,
        }

        response = client.post("/income/paychecks", json=payload)

        # Should fail validation (missing employer_id)
        assert response.status_code == 422

    def test_create_1099r_invalid_date(self, client: TestClient):
        """Test creating pension with invalid date fails."""
        payload = {"pay_date": "invalid-date", "gross_amount": 2000}

        response = client.post("/income/1099r", json=payload)

        # Should fail validation
        assert response.status_code == 422

    def test_create_non_taxable_negative_amount(self, client: TestClient):
        """Test creating VA entry with negative amount fails."""
        payload = {"pay_date": "2025-01-01", "payment_amount": -1000}

        response = client.post("/income/non-taxable", json=payload)

        # Should fail validation
        assert response.status_code == 422


@pytest.mark.integration
class TestCSVImport:
    """Tests for CSV import functionality."""

    def test_import_csv_missing_file(self, client: TestClient):
        """Test CSV import without file fails."""
        response = client.post("/income/paychecks/import-csv")

        # Should require file
        assert response.status_code == 422


@pytest.mark.integration
class TestIncomeFiltering:
    """Tests for income filtering by year."""

    def test_filter_paychecks_by_year(self, client: TestClient):
        """Test filtering paychecks by year."""
        response = client.get("/income/paychecks?year=2025")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_filter_1099r_by_year(self, client: TestClient):
        """Test filtering pension by year."""
        response = client.get("/income/1099r?year=2025")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_filter_non_taxable_by_year(self, client: TestClient):
        """Test filtering non-taxable benefit by year."""
        response = client.get("/income/non-taxable?year=2025")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
