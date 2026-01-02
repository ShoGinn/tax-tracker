"""Shared API dependencies."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from taxtracker.models.database import SessionLocal
from taxtracker.services.tax_calculator import TaxCalculator


def get_db() -> Generator[Session, None, None]:
    """Get database session.

    Yields database session and ensures cleanup.
    Can be overridden in tests using FastAPI's dependency override.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tax_calculator() -> TaxCalculator:
    """Get tax calculator instance.

    Returns a TaxCalculator with default data directory.
    Can be overridden in tests using FastAPI's dependency override.

    Example:
        # In tests
        app.dependency_overrides[get_tax_calculator] = lambda: TaxCalculator(test_dir)
    """
    return TaxCalculator()
