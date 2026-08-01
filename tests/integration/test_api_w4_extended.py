"""Tests for stateless W-4 endpoints."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _snapshot() -> dict:
    return {
        "employers": [{"id": 1, "name": "Browser Corp", "start_date": "2024-01-01"}],
        "paychecks": [
            {
                "id": 1,
                "employer_id": 1,
                "pay_date": "2024-01-15",
                "gross_wages": "3000",
                "federal_withholding": "320",
            },
            {
                "id": 2,
                "employer_id": 1,
                "pay_date": "2024-01-31",
                "gross_wages": "3100",
                "federal_withholding": "330",
            },
        ],
        "pensions": [],
        "non_taxable_income": [],
        "config": {
            "filing_status": "single",
            "num_children": 0,
            "use_standard_deduction": True,
            "itemized_deduction_amount": "0",
            "age_65_plus": False,
            "w2_pay_frequency": "biweekly",
        },
    }


def test_optimize_basic(client: TestClient) -> None:
    response = client.post(
        "/w4/optimize",
        json={
            "total_annual_w2_income": 60000,
            "paychecks_per_year": 26,
            "filing_status": "single",
            "year": 2024,
        },
    )
    assert response.status_code == 200
    assert response.json()["w4_recommendations"]


def test_optimize_midyear_uses_browser_snapshot(client: TestClient) -> None:
    response = client.post(
        "/w4/optimize-midyear",
        json={
            **_snapshot(),
            "tax_year": 2024,
            "filing_status": "single",
            "remaining_pay_periods": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ytd_summary"]["employers"][0]["employer_name"] == "Browser Corp"
    assert data["ytd_summary"]["employers"][0]["paychecks_recorded"] == 2


def test_suggest_periods_uses_browser_dates(client: TestClient) -> None:
    snapshot = _snapshot()
    snapshot["pensions"] = [{"id": 1, "pay_date": "2024-05-01", "gross_amount": "1000"}]
    response = client.post(
        "/w4/suggest-periods",
        json={
            **snapshot,
            "tax_year": 2024,
            "as_of_date": "2024-05-10",
            "w2_pay_frequency": "semimonthly",
        },
    )
    assert response.status_code == 200
    assert response.json()["current_month_has_pension_entry"] is True


def test_w4_optimizers_apply_age_65_plus(client: TestClient) -> None:
    full_year_request = {
        "total_annual_w2_income": 60000,
        "paychecks_per_year": 26,
        "filing_status": "single",
        "year": 2024,
    }
    full_year_under_65 = client.post("/w4/optimize", json=full_year_request)
    full_year_65_plus = client.post(
        "/w4/optimize",
        json={**full_year_request, "age_65_plus": True},
    )

    midyear_request = {
        **_snapshot(),
        "tax_year": 2024,
        "filing_status": "single",
        "remaining_pay_periods": 10,
    }
    midyear_under_65 = client.post("/w4/optimize-midyear", json=midyear_request)
    midyear_65_plus = client.post(
        "/w4/optimize-midyear",
        json={**midyear_request, "age_65_plus": True},
    )

    assert full_year_under_65.status_code == 200
    assert full_year_65_plus.status_code == 200
    assert midyear_under_65.status_code == 200
    assert midyear_65_plus.status_code == 200
    assert float(full_year_65_plus.json()["estimated_tax_liability"]) < float(
        full_year_under_65.json()["estimated_tax_liability"]
    )
    assert float(midyear_65_plus.json()["estimated_tax_liability"]) < float(
        midyear_under_65.json()["estimated_tax_liability"]
    )
