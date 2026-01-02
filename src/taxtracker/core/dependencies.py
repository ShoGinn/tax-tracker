"""Dependency injection for testability.

This module provides factories for creating service instances with
proper dependency injection, making everything easily testable.
"""

from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from taxtracker.core.config import settings
from taxtracker.models.database import Base
from taxtracker.services.tax_calculator import TaxCalculator

# ============================================================================
# Protocols for type safety
# ============================================================================


class TaxCalculatorProtocol(Protocol):
    """Protocol for tax calculator dependency."""

    def calculate_taxes(self, request: Any) -> Any:  # noqa: ANN401
        """Calculate taxes."""
        ...

    def load_tax_brackets(self, year: int) -> Any:  # noqa: ANN401
        """Load tax brackets."""
        ...

    def load_fica_limits(self, year: int) -> Any:  # noqa: ANN401
        """Load FICA limits."""
        ...


# ============================================================================
# Dependency Factories
# ============================================================================


def get_tax_calculator(data_dir: Path | None = None) -> "TaxCalculator":
    """Get a TaxCalculator instance.

    Args:
        data_dir: Optional data directory. If None, uses default.

    Returns:
        TaxCalculator instance

    Example:
        # Production
        calculator = get_tax_calculator()

        # Testing with mock data
        test_dir = Path("tests/fixtures/data")
        calculator = get_tax_calculator(test_dir)
    """

    return TaxCalculator(data_dir=data_dir)


def get_database_session(database_url: str | None = None) -> Session:
    """Get a database session.

    Args:
        database_url: Optional database URL. If None, uses settings.

    Returns:
        Database session

    Example:
        # Production
        db = get_database_session()

        # Testing with in-memory DB
        db = get_database_session("sqlite:///:memory:")
    """
    url = database_url or settings.database_url
    engine = create_engine(url, echo=False)
    _sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _sessionmaker()


def get_test_session() -> Session:
    """Get an in-memory database session for testing.

    Returns:
        In-memory database session with tables created

    Example:
        def test_something():
            db = get_test_session()
            # Use db for testing
            db.close()
    """

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    _sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _sessionmaker()


# ============================================================================
# Dependency Override for Testing
# ============================================================================


class DependencyOverrides:
    """Container for dependency overrides during testing.

    Example:
        # In test setup
        overrides = DependencyOverrides()
        overrides.tax_calculator = get_tax_calculator(test_data_dir)
        overrides.db_session = get_test_session()

        # In production
        overrides = DependencyOverrides()  # Uses defaults
    """

    def __init__(self) -> None:
        """Initialize with default (production) dependencies."""
        self._tax_calculator: TaxCalculatorProtocol | None = None
        self._db_session: Session | None = None

    @property
    def tax_calculator(self) -> "TaxCalculator":
        """Get tax calculator instance."""
        if self._tax_calculator is None:
            self._tax_calculator = get_tax_calculator()
        return self._tax_calculator  # type: ignore[return-value]

    @tax_calculator.setter
    def tax_calculator(self, calculator: "TaxCalculator") -> None:
        """Override tax calculator for testing."""
        self._tax_calculator = calculator

    @property
    def db_session(self) -> Session:
        """Get database session."""
        if self._db_session is None:
            self._db_session = get_database_session()
        return self._db_session

    @db_session.setter
    def db_session(self, session: Session) -> None:
        """Override database session for testing."""
        self._db_session = session


# Global dependency container (can be overridden in tests)
dependencies = DependencyOverrides()


# ============================================================================
# Helper functions for common patterns
# ============================================================================


def with_test_dependencies(**kwargs: Any) -> DependencyOverrides:  # noqa: ANN401
    """Create dependency container with test overrides.

    Args:
        **kwargs: Dependency overrides (tax_calculator, db_session, etc.)

    Returns:
        DependencyOverrides with test dependencies

    Example:
        def test_calculation():
            test_calc = get_tax_calculator(test_data_dir)
            deps = with_test_dependencies(tax_calculator=test_calc)

            # Use deps.tax_calculator in tests
    """
    deps = DependencyOverrides()

    if "tax_calculator" in kwargs:
        deps.tax_calculator = kwargs["tax_calculator"]
    if "db_session" in kwargs:
        deps.db_session = kwargs["db_session"]

    return deps
