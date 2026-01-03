"""Pytest configuration and fixtures."""

import asyncio
import json

# Import IRS test data
import sys
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fixtures.irs_test_data import (
    IRS_2024_FICA_LIMITS,
    IRS_2024_TAX_BRACKETS,
    SIMPLE_TEST_FICA_LIMITS,
    SIMPLE_TEST_TAX_BRACKETS,
    get_irs_test_data,
)
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from taxtracker.cli.app import create_app
from taxtracker.models.database import Base
from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.tax_calculator import TaxCalculator

tests_dir = Path(__file__).parent
sys.path.insert(0, str(tests_dir))


@pytest.fixture(scope="session")
def temp_tax_data_dir():
    """Create temporary directory with IRS test data JSON files.

    This allows integration tests to use the API with real file loading,
    but pointing at IRS-verified test data instead of production files.
    """
    from decimal import Decimal

    def decimal_to_float(obj):
        """Convert Decimals to float for JSON serialization."""
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: decimal_to_float(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [decimal_to_float(item) for item in obj]
        return obj

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)

        # Convert IRS 2024 data to JSON format (for year 2024)
        tax_brackets_2024 = {
            "tax_year": IRS_2024_TAX_BRACKETS.tax_year,
            "last_updated": IRS_2024_TAX_BRACKETS.last_updated,
            "source": IRS_2024_TAX_BRACKETS.source + " (Test Data)",
            "notes": "IRS-verified test data for integration tests",
            "tax_brackets": {},
            "standard_deductions": {},
            "child_tax_credit": {},
        }

        # Convert brackets
        for filing_status, brackets in IRS_2024_TAX_BRACKETS.tax_brackets.items():
            tax_brackets_2024["tax_brackets"][filing_status.value] = [
                {
                    "min": decimal_to_float(b.min),
                    "max": decimal_to_float(b.max),
                    "rate": decimal_to_float(b.rate),
                }
                for b in brackets
            ]

        # Convert standard deductions
        std_ded = IRS_2024_TAX_BRACKETS.standard_deductions
        tax_brackets_2024["standard_deductions"] = decimal_to_float(
            {status.value: std_ded.for_status(status) for status in FilingStatus}
            | {
                "additional_age_65_plus": std_ded.additional_age_65_plus,
            }
        )

        # Convert child tax credit
        ctc = IRS_2024_TAX_BRACKETS.child_tax_credit
        tax_brackets_2024["child_tax_credit"] = decimal_to_float(
            {
                "amount_per_child": ctc.amount_per_child,
                "refundable_portion": ctc.refundable_portion,
                "phase_out_threshold": {k.value: v for k, v in ctc.phase_out_threshold.items()},
            }
        )

        # Write tax brackets JSON
        with open(temp_path / "tax_brackets_2024.json", "w") as f:
            json.dump(tax_brackets_2024, f, indent=2)

        # Convert FICA data to JSON format
        fica_2024 = decimal_to_float(
            {
                "tax_year": IRS_2024_FICA_LIMITS.tax_year,
                "last_updated": IRS_2024_FICA_LIMITS.last_updated,
                "source": IRS_2024_FICA_LIMITS.source + " (Test Data)",
                "social_security": {
                    "employee_rate": IRS_2024_FICA_LIMITS.social_security.employee_rate,
                    "employer_rate": IRS_2024_FICA_LIMITS.social_security.employer_rate,
                    "total_rate": IRS_2024_FICA_LIMITS.social_security.total_rate,
                    "wage_base_limit": IRS_2024_FICA_LIMITS.social_security.wage_base_limit,
                    "max_employee_tax": IRS_2024_FICA_LIMITS.social_security.max_employee_tax,
                    "max_employer_tax": IRS_2024_FICA_LIMITS.social_security.max_employer_tax,
                    "max_combined_tax": IRS_2024_FICA_LIMITS.social_security.max_combined_tax,
                },
                "medicare": {
                    "employee_rate": IRS_2024_FICA_LIMITS.medicare.employee_rate,
                    "employer_rate": IRS_2024_FICA_LIMITS.medicare.employer_rate,
                    "total_rate": IRS_2024_FICA_LIMITS.medicare.total_rate,
                    "wage_base_limit": IRS_2024_FICA_LIMITS.medicare.wage_base_limit,
                    "note": IRS_2024_FICA_LIMITS.medicare.note,
                },
                "additional_medicare": {
                    "rate": IRS_2024_FICA_LIMITS.additional_medicare.rate,
                    "employer_match": IRS_2024_FICA_LIMITS.additional_medicare.employer_match,
                    "thresholds": dict(IRS_2024_FICA_LIMITS.additional_medicare.thresholds),
                    "note": IRS_2024_FICA_LIMITS.additional_medicare.note,
                },
                "combined_rates": dict(IRS_2024_FICA_LIMITS.combined_rates),
            }
        )

        # Write FICA JSON
        with open(temp_path / "fica_limits_2024.json", "w") as f:
            json.dump(fica_2024, f, indent=2)

        # Also create 2030 (simplified test data) for consistency
        tax_brackets_2030 = {
            "tax_year": SIMPLE_TEST_TAX_BRACKETS.tax_year,
            "last_updated": SIMPLE_TEST_TAX_BRACKETS.last_updated,
            "source": SIMPLE_TEST_TAX_BRACKETS.source,
            "notes": "Simplified test data with round numbers",
            "tax_brackets": {},
            "standard_deductions": {},
            "child_tax_credit": {},
        }

        for filing_status, brackets in SIMPLE_TEST_TAX_BRACKETS.tax_brackets.items():
            tax_brackets_2030["tax_brackets"][filing_status.value] = [
                {
                    "min": decimal_to_float(b.min),
                    "max": decimal_to_float(b.max),
                    "rate": decimal_to_float(b.rate),
                }
                for b in brackets
            ]

        std_ded = SIMPLE_TEST_TAX_BRACKETS.standard_deductions
        tax_brackets_2030["standard_deductions"] = decimal_to_float(
            {status.value: std_ded.for_status(status) for status in FilingStatus}
            | {
                "additional_age_65_plus": std_ded.additional_age_65_plus,
            }
        )

        ctc = SIMPLE_TEST_TAX_BRACKETS.child_tax_credit
        tax_brackets_2030["child_tax_credit"] = decimal_to_float(
            {
                "amount_per_child": ctc.amount_per_child,
                "refundable_portion": ctc.refundable_portion,
                "phase_out_threshold": {k.value: v for k, v in ctc.phase_out_threshold.items()},
            }
        )

        with open(temp_path / "tax_brackets_2030.json", "w") as f:
            json.dump(tax_brackets_2030, f, indent=2)

        # Use 2024 FICA for 2030 as well
        fica_2030 = fica_2024.copy()
        fica_2030["tax_year"] = 2030
        with open(temp_path / "fica_limits_2030.json", "w") as f:
            json.dump(fica_2030, f, indent=2)

        yield temp_path
        # Cleanup happens automatically when context exits


@pytest.fixture(scope="function")
def test_calculator() -> TaxCalculator:
    """Get a TaxCalculator with IRS-verified test data.

    Uses simplified test data (year 2030) with known values for easy verification.
    Tests can verify calculations without depending on external JSON files.
    """
    return TaxCalculator(
        tax_year=2030,
        tax_brackets=SIMPLE_TEST_TAX_BRACKETS,
        fica_limits=SIMPLE_TEST_FICA_LIMITS,
    )


@pytest.fixture(scope="function")
def irs_2024_calculator() -> TaxCalculator:
    """Get a TaxCalculator with actual IRS 2024 data.

    Uses real IRS Publication 17 data for integration testing.
    """
    brackets, fica = get_irs_test_data(2024)
    return TaxCalculator(tax_year=2024, tax_brackets=brackets, fica_limits=fica)


@pytest.fixture(scope="function")
def test_engine() -> Generator[Engine, None, None]:
    """Create a test database engine with proper SQLite configuration.

    Uses StaticPool to ensure the in-memory database persists across connections.
    This is critical for FastAPI's dependency injection which creates new sessions.

    NOTE: This creates a SYNC engine for unit tests. For integration tests that use
    the async routes, use the test_async_engine fixture instead.
    """
    # Use StaticPool to maintain single connection to in-memory DB
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Critical: keeps single connection alive
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_async_engine():
    """Create an async test database engine.

    Uses aiosqlite for true async SQLite support, compatible with AsyncSession.
    Uses in-memory database with check_same_thread=False for test isolation.
    """

    async def create_test_async_engine():
        # Create async engine with in-memory SQLite
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Initialize tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        return engine

    # Create the engine in the event loop
    test_engine = asyncio.run(create_test_async_engine())

    yield test_engine

    # Cleanup
    async def cleanup():
        await test_engine.dispose()

    try:
        asyncio.run(cleanup())
    except RuntimeError:
        pass


@pytest.fixture(scope="function")
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Create a test database session (SYNC - for unit tests).

    This session shares the same engine as the client, allowing tests
    to set up data that the API can see.
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()

    yield session

    session.close()

    # Clean up all data after test for isolation
    # (But don't rollback since API needs to see committed data)
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()


@pytest.fixture(scope="function")
async def async_db_session(test_async_engine):
    """Create an async test database session.

    This is for integration tests that need to set up data and then test
    it via async API routes.
    """
    from sqlalchemy.orm import sessionmaker

    AsyncSessionLocal = sessionmaker(
        test_async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with AsyncSessionLocal() as session:
        yield session

        # Clean up all data after test for isolation
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture(scope="function")
def client(test_async_engine, temp_tax_data_dir: Path) -> Generator[TestClient, None, None]:
    """Create a test client with async test database and temp IRS data files.

    The client uses:
    1. Shared async engine (test_async_engine) for database
    2. Temp directory with IRS test data (for tax calculations)

    This allows integration tests to:
    - Set up data via async_db_session fixture (same engine)
    - Make requests via client fixture
    - See the data in both places since they share the same engine
    """
    from sqlalchemy.orm import sessionmaker

    from taxtracker.core.config import settings

    # Save original settings
    original_data_dir = settings.data_dir
    settings.data_dir = temp_tax_data_dir

    try:
        # Create app with skip_db_init=True (tables already created by test_async_engine)
        app = create_app(skip_db_init=True)

        # Create AsyncSession maker using the shared test_async_engine
        AsyncTestSessionLocal = sessionmaker(
            test_async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )

        # Override get_db to use the test async session
        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            async with AsyncTestSessionLocal() as session:
                yield session

        from taxtracker.api.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        # TestClient works with async routes
        with TestClient(app) as test_client:
            yield test_client

    finally:
        # Restore original data_dir
        settings.data_dir = original_data_dir

    # Clean up
    app.dependency_overrides.clear()
