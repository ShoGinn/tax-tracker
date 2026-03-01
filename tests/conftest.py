"""Pytest configuration and fixtures."""

import asyncio
import contextlib

# Import IRS test data
import sys
from collections.abc import AsyncGenerator, Generator  # noqa: TC003
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fixtures.irs_test_data import (
    IRS_2024_FICA_LIMITS,
    IRS_2024_TAX_BRACKETS,
    get_irs_test_data,
)
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine  # noqa: TC002
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from taxtracker.api.dependencies import get_db, get_tax_data
from taxtracker.cli.app import create_app
from taxtracker.models.database import Base
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
def test_engine() -> Generator[Engine]:
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
    def set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
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

    with contextlib.suppress(RuntimeError):
        asyncio.run(cleanup())


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session]:
    """Create a test database session (SYNC - for unit tests).

    This session shares the same engine as the client, allowing tests
    to set up data that the API can see.
    """
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = _session_factory()

    yield session

    session.close()

    # Clean up all data after test for isolation
    # (But don't rollback since API needs to see committed data)
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()


@pytest.fixture
async def async_db_session(test_async_engine):
    """Create an async test database session.

    This is for integration tests that need to set up data and then test
    it via async API routes.
    """

    _async_session_factory = sessionmaker(
        test_async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with _async_session_factory() as session:
        yield session

        # Clean up all data after test for isolation
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture
def client(test_async_engine, mock_tax_data_dependency) -> Generator[TestClient]:
    """Create a test client with async test database and dependency injection.

    The client uses:
    1. Shared async engine (test_async_engine) for database
    2. Overridden get_tax_data dependency that returns static test data

    This allows integration tests to:
    - Set up data via async_db_session fixture (same engine)
    - Make requests via client fixture
    - Test full API with dependency injection (no file I/O)
    """

    # Create app with skip_db_init=True (tables already created by test_async_engine)
    app = create_app(skip_db_init=True)

    # Create AsyncSession maker using the shared test_async_engine
    _async_session_factory = sessionmaker(
        test_async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    # Override get_db to use the test async session
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        async with _async_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tax_data] = mock_tax_data_dependency

    # TestClient works with async routes
    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()
