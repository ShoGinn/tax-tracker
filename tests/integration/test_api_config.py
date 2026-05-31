"""Integration tests for the /config application configuration API."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
class TestConfigAPI:
    """Integration tests for GET /config and PUT /config."""

    def test_get_config_returns_defaults(self, client: TestClient) -> None:
        """GET /config returns default values when no config exists yet."""
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert data["filing_status"] == "married_filing_jointly"
        assert data["num_children"] == 0
        assert data["use_standard_deduction"] is True
        assert float(data["itemized_deduction_amount"]) == 0.0
        assert data["age_65_plus"] is False
        assert data["w2_pay_frequency"] == "monthly"

    def test_put_config_updates_filing_status(self, client: TestClient) -> None:
        """PUT /config updates filing status and GET returns the new value."""
        put_response = client.put("/config", json={"filing_status": "single"})
        assert put_response.status_code == 200
        assert put_response.json()["filing_status"] == "single"

        get_response = client.get("/config")
        assert get_response.status_code == 200
        assert get_response.json()["filing_status"] == "single"

    def test_put_config_partial_update(self, client: TestClient) -> None:
        """PUT /config with partial payload only changes the specified fields."""
        # Set a baseline
        client.put("/config", json={"filing_status": "married_filing_jointly", "num_children": 2})

        # Partial update — only change num_children
        response = client.put("/config", json={"num_children": 3})
        assert response.status_code == 200
        data = response.json()
        assert data["num_children"] == 3
        assert data["filing_status"] == "married_filing_jointly"

    def test_put_config_standard_deduction_flag(self, client: TestClient) -> None:
        """PUT /config can switch to itemized deduction."""
        response = client.put(
            "/config",
            json={"use_standard_deduction": False, "itemized_deduction_amount": "25000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["use_standard_deduction"] is False
        assert float(data["itemized_deduction_amount"]) == 25000.0

    def test_put_config_age_65_plus(self, client: TestClient) -> None:
        """PUT /config sets age_65_plus flag."""
        response = client.put("/config", json={"age_65_plus": True})
        assert response.status_code == 200
        assert response.json()["age_65_plus"] is True

    def test_put_config_w2_pay_frequency(self, client: TestClient) -> None:
        """PUT /config updates w2_pay_frequency and GET returns the new value."""
        for freq in ("weekly", "biweekly", "semimonthly", "monthly"):
            resp = client.put("/config", json={"w2_pay_frequency": freq})
            assert resp.status_code == 200
            assert resp.json()["w2_pay_frequency"] == freq

    def test_put_config_invalid_w2_pay_frequency(self, client: TestClient) -> None:
        """PUT /config rejects unknown pay frequency values."""
        response = client.put("/config", json={"w2_pay_frequency": "quarterly"})
        assert response.status_code == 422

    def test_put_config_is_idempotent(self, client: TestClient) -> None:
        """Calling PUT /config twice with same data returns same result."""
        payload = {"filing_status": "head_of_household", "num_children": 1}
        r1 = client.put("/config", json=payload)
        r2 = client.put("/config", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json() == r2.json()

    def test_put_config_invalid_num_children(self, client: TestClient) -> None:
        """PUT /config rejects negative num_children."""
        response = client.put("/config", json={"num_children": -1})
        assert response.status_code == 422
