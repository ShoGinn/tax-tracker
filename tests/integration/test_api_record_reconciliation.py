"""Contract tests for browser-snapshot tax reconciliation."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def test_reconciles_transient_browser_records(client: TestClient) -> None:
    response = client.post(
        "/taxes/reconcile-records/2024",
        json={
            "employers": [{"id": 1, "name": "Local Corp", "start_date": "2024-01-01"}],
            "paychecks": [
                {
                    "id": 1,
                    "employer_id": 1,
                    "pay_date": "2024-01-15",
                    "gross_wages": "50000",
                    "deduction_401k": "5000",
                    "federal_withholding": "5000",
                    "social_security": "3100",
                    "medicare": "725",
                }
            ],
            "pensions": [
                {
                    "id": 1,
                    "pay_date": "2024-01-01",
                    "gross_amount": "12000",
                    "pretax_deductions": "1000",
                    "federal_withholding": "1000",
                }
            ],
            "non_taxable_income": [{"id": 1, "pay_date": "2024-01-01", "amount": "6000"}],
            "config": {"filing_status": "single", "age_65_plus": False},
            "options": {
                "filing_status": "single",
                "num_children": 0,
                "use_standard_deduction": True,
                "itemized_deduction_amount": "0",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["w2_gross"] == "50000"
    assert data["w2_pretax_deductions"] == "5000"
    assert data["pension_taxable"] == "11000"
    assert data["non_taxable_income"] == "6000"
    assert data["total_federal_withheld"] == "6000"


def test_legacy_database_route_is_removed(client: TestClient) -> None:
    response = client.get(
        "/taxes/calculate-from-db/2024",
        params={"filing_status": "single"},
    )
    assert response.status_code == 404
