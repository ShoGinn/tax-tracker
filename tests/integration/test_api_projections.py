"""Tests for stateless projection endpoints."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _snapshot() -> dict:
    return {
        "employers": [{"id": 1, "name": "Test Corp", "start_date": "2024-01-01"}],
        "paychecks": [
            {
                "id": 1,
                "employer_id": 1,
                "pay_date": "2024-01-15",
                "gross_wages": "5000",
                "federal_withholding": "600",
            }
        ],
        "pensions": [{"id": 1, "pay_date": "2024-01-01", "gross_amount": "2000", "pretax_deductions": "100"}],
        "non_taxable_income": [{"id": 1, "pay_date": "2024-01-01", "amount": "1500"}],
        "config": {
            "filing_status": "single",
            "num_children": 0,
            "use_standard_deduction": True,
            "itemized_deduction_amount": "0",
            "age_65_plus": False,
            "w2_pay_frequency": "monthly",
        },
    }


def test_project_year_basic(client: TestClient) -> None:
    response = client.post(
        "/projections/project-year",
        json={"projection_year": 2024, "filing_status": "single", "w2_gross": 75000},
    )
    assert response.status_code == 200
    assert float(response.json()["federal_tax_liability"]) > 0


def test_dashboard_uses_transient_snapshot(client: TestClient) -> None:
    response = client.post("/projections/dashboard/2024", json=_snapshot())
    assert response.status_code == 200
    data = response.json()
    assert data["ytd"]["paycheck_count"] == 1
    assert data["ytd"]["w2_gross"] == "5000"
    assert data["ytd"]["pension_gross"] == "2000"
    assert data["ytd"]["va_income"] == "1500"


def test_dashboard_does_not_expose_get_persistence_route(client: TestClient) -> None:
    assert client.get("/projections/dashboard/2024").status_code == 405


def test_compare_years_honors_age_and_itemized_deductions(client: TestClient) -> None:
    base_request = {
        "base_year": 2024,
        "comparison_year": 2025,
        "filing_status": "single",
        "base_w2_gross": "90000",
        "comparison_w2_gross": "90000",
    }
    standard = client.post("/projections/compare-years", json=base_request)
    itemized = client.post(
        "/projections/compare-years",
        json={
            **base_request,
            "num_children": 1,
            "age_65_plus": True,
            "use_standard_deduction": False,
            "itemized_deduction_amount": "30000",
        },
    )

    assert standard.status_code == 200
    assert itemized.status_code == 200
    standard_tax = float(standard.json()["years"][0]["tax_calculation"]["federal_tax_liability"])
    itemized_tax = float(itemized.json()["years"][0]["tax_calculation"]["federal_tax_liability"])
    assert itemized_tax < standard_tax
