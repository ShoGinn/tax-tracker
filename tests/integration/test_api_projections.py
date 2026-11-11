"""Tests for stateless projection endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

import taxtracker.api.projections as routes

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


def test_completed_year_does_not_extrapolate_withholding(client: TestClient) -> None:

    result = client.post("/projections/dashboard/2024", json=_snapshot()).json()
    assert result["remaining_periods"] == {"w2": 0, "pension": 0, "non_taxable": 0}
    assert Decimal(result["projected"]["estimated_withholding"]) == 600
    assert Decimal(result["projected"]["estimated_refund_or_owed"]) == 600
    assert Decimal(result["projected"]["fica_liability"]) == Decimal("382.50")


def test_current_year_projects_each_withholding_stream(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:

    year = datetime.now(UTC).year
    snapshot = _snapshot()
    for key in ("paychecks", "pensions", "non_taxable_income"):
        for record in snapshot[key]:
            record["pay_date"] = f"{year}-01-15"
    snapshot["pensions"][0]["federal_withholding"] = "100"
    monkeypatch.setattr(
        routes,
        "suggest_midyear_periods",
        lambda *_args, **_kwargs: SimpleNamespace(
            remaining_pay_periods=3, remaining_pension_periods=2, remaining_non_taxable_periods=1
        ),
    )
    response = client.post(f"/projections/dashboard/{year}", json=snapshot)
    assert response.status_code == 200
    result = response.json()
    assert Decimal(result["ytd"]["federal_withheld"]) == 700
    assert Decimal(result["projected"]["estimated_withholding"]) == 2700
    assert Decimal(result["projected"]["w2_gross"]) == 20000
    assert Decimal(result["projected"]["pension_gross"]) == 6000
    assert Decimal(result["projected"]["estimated_refund_or_owed"]) == 2700 - Decimal(
        result["projected"]["federal_tax_liability"]
    )


def test_pension_only_has_no_fica(client: TestClient) -> None:

    snapshot = _snapshot()
    snapshot["paychecks"] = []
    snapshot["pensions"][0]["gross_amount"] = "60000"
    snapshot["pensions"][0]["federal_withholding"] = "8000"
    response = client.post("/projections/dashboard/2024", json=snapshot)
    assert response.status_code == 200
    projected = response.json()["projected"]
    assert Decimal(projected["fica_liability"]) == 0
    assert Decimal(projected["pension_taxable"]) == 59900


def test_future_records_are_not_projected_a_second_time(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    year = datetime.now(UTC).year
    snapshot = _snapshot()
    for key in ("paychecks", "pensions", "non_taxable_income"):
        for record in snapshot[key]:
            record["pay_date"] = f"{year}-12-31"
    monkeypatch.setattr(
        routes,
        "suggest_midyear_periods",
        lambda *_args, **_kwargs: SimpleNamespace(
            remaining_pay_periods=1,
            remaining_pension_periods=1,
            remaining_non_taxable_periods=1,
        ),
    )
    response = client.post(f"/projections/dashboard/{year}", json=snapshot)
    assert response.status_code == 200
    result = response.json()
    assert result["remaining_periods"] == {"w2": 0, "pension": 0, "non_taxable": 0}
    assert Decimal(result["projected"]["w2_gross"]) == 5000
    assert Decimal(result["projected"]["estimated_withholding"]) == 600
