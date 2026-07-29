"""Pytest configuration and fixtures."""

import sys
from collections.abc import Generator  # noqa: TC003
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fixtures.irs_test_data import (
    IRS_2024_FICA_LIMITS,
    IRS_2024_TAX_BRACKETS,
    get_irs_test_data,
)

from taxtracker.api.dependencies import get_tax_data
from taxtracker.cli.app import create_app
from taxtracker.services.tax_calculator import TaxCalculator

tests_dir = Path(__file__).parent
sys.path.insert(0, str(tests_dir))


@pytest.fixture
def mock_tax_data_dependency(monkeypatch):
    """Override the get_tax_data dependency and patch data loader functions.

    This fixture:
    1. Overrides the get_tax_data dependency to return static test data
    2. Patches load_tax_brackets_model and load_fica_limits_model in data_loader
       so that any direct calls (like from TaxCalculator) also get test data

    This ensures both dependency-injected and direct file loading calls work.
    """

    def override_get_tax_data(year: int) -> tuple:  # noqa: ARG001
        """Return test data for any year requested."""
        # Always return 2024 test data regardless of year
        return (IRS_2024_TAX_BRACKETS, IRS_2024_FICA_LIMITS)

    # Also patch the data loader functions so TaxCalculator can use them
    def mock_load_tax_brackets_model(year: int):  # noqa: ARG001
        return IRS_2024_TAX_BRACKETS

    def mock_load_fica_limits_model(year: int):  # noqa: ARG001
        return IRS_2024_FICA_LIMITS

    # Patch in data_loader module (where they're defined)
    monkeypatch.setattr(
        "taxtracker.services.data_loader.load_tax_brackets_model",
        mock_load_tax_brackets_model,
    )
    monkeypatch.setattr(
        "taxtracker.services.data_loader.load_fica_limits_model",
        mock_load_fica_limits_model,
    )

    # Patch in tax_calculator module (where it's imported)
    monkeypatch.setattr(
        "taxtracker.services.tax_calculator.load_tax_brackets_model",
        mock_load_tax_brackets_model,
    )
    monkeypatch.setattr(
        "taxtracker.services.tax_calculator.load_fica_limits_model",
        mock_load_fica_limits_model,
    )

    # Patch in w4_withholding module (where it's imported)
    monkeypatch.setattr(
        "taxtracker.services.w4_withholding.load_tax_brackets_model",
        mock_load_tax_brackets_model,
    )

    return override_get_tax_data


@pytest.fixture
def test_calculator() -> TaxCalculator:
    """Get a TaxCalculator with IRS-verified 2024 test data.

    Uses real IRS 2024 data for testing.
    Tests can verify calculations without depending on external JSON files.
    """
    brackets, fica = get_irs_test_data(2024)
    return TaxCalculator(tax_year=2024, tax_brackets=brackets, fica_limits=fica)


@pytest.fixture
def irs_2024_calculator() -> TaxCalculator:
    """Get a TaxCalculator with actual IRS 2024 data.

    Uses real IRS Publication 17 data for integration testing.
    """
    brackets, fica = get_irs_test_data(2024)
    return TaxCalculator(tax_year=2024, tax_brackets=brackets, fica_limits=fica)


@pytest.fixture
def client(mock_tax_data_dependency) -> Generator[TestClient]:
    """Create a stateless test client with deterministic IRS data."""
    app = create_app(skip_db_init=True, serve_frontend=False)
    app.dependency_overrides[get_tax_data] = mock_tax_data_dependency
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
