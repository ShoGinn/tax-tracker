"""Contract tests for browser-snapshot tax reconciliation."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from taxtracker.cli.app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def actual_client():
    """Use packaged tax data, without the general client's 2024 data override."""
    with TestClient(create_app(skip_db_init=True, serve_frontend=False)) as client:
        yield client


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


def test_reconciliation_uses_explicit_age_and_itemized_options(client: TestClient) -> None:
    snapshot = {
        "employers": [{"id": 1, "name": "Local Corp", "start_date": "2024-01-01"}],
        "paychecks": [
            {
                "id": 1,
                "employer_id": 1,
                "pay_date": "2024-01-15",
                "gross_wages": "80000",
                "federal_withholding": "10000",
            }
        ],
        "pensions": [],
        "non_taxable_income": [],
        "config": {"filing_status": "single", "age_65_plus": False},
    }
    standard = client.post(
        "/taxes/reconcile-records/2024",
        json={
            **snapshot,
            "options": {
                "filing_status": "single",
                "age_65_plus": True,
                "use_standard_deduction": True,
            },
        },
    )
    itemized = client.post(
        "/taxes/reconcile-records/2024",
        json={
            **snapshot,
            "options": {
                "filing_status": "single",
                "age_65_plus": False,
                "use_standard_deduction": False,
                "itemized_deduction_amount": "30000",
            },
        },
    )

    assert standard.status_code == 200
    assert itemized.status_code == 200
    assert float(standard.json()["deduction_amount"]) > 14600
    assert itemized.json()["deduction_amount"] == "30000"


@pytest.mark.parametrize(
    ("withheld", "expected", "status"), [("7204", "1300", "REFUND"), ("5204", "-700", "OWED"), ("5904", "0", "EVEN")]
)
def test_2026_federal_balance_excludes_payroll_taxes(
    actual_client: TestClient, withheld: str, expected: str, status: str
) -> None:
    """IRS RP 2025-32: MFJ $90,000 taxable -> $2,480 + $7,824; less two $2,200 credits."""

    response = actual_client.post(
        "/taxes/reconcile-records/2026",
        json={
            "paychecks": [
                {
                    "id": 1,
                    "employer_id": 1,
                    "pay_date": "2026-01-15",
                    "gross_wages": "110000",
                    "bonus": "12200",
                    "deduction_401k": "10000",
                    "federal_withholding": withheld,
                    "social_security": "1",
                    "medicare": "1",
                }
            ],
            "pensions": [{"id": 1, "pay_date": "2026-01-01", "gross_amount": "12000", "pretax_deductions": "2000"}],
            "non_taxable_income": [{"id": 1, "pay_date": "2026-01-01", "amount": "6000"}],
            "options": {"filing_status": "married_filing_jointly", "num_children": 2},
        },
    )
    assert response.status_code == 200
    result = response.json()
    # $122,200 + $12,000 - $10,000 - $2,000 - $32,200 = $90,000.
    assert Decimal(result["taxable_income"]) == 90000
    assert Decimal(result["federal_tax_owed"]) == 10304
    assert Decimal(result["total_tax_liability"]) == 5904
    assert Decimal(result["refund_or_owed"]) == Decimal(expected)
    assert result["result_status"] == status
    assert sum(Decimal(str(b["taxable_amount"])) for b in result["breakdown_by_bracket"]) == 90000
    assert sum(Decimal(str(b["tax_amount"])) for b in result["breakdown_by_bracket"]) == 10304
