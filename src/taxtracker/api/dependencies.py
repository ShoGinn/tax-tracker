"""Shared API dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.models.database import AsyncSessionLocal
from taxtracker.services.tax_calculator import TaxCalculator


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session.

    Yields async database session and ensures cleanup.
    Can be overridden in tests using FastAPI's dependency override.
    """
    async with AsyncSessionLocal() as session:
        yield session


def get_tax_calculator() -> TaxCalculator:
    """Get tax calculator instance.

    Returns a TaxCalculator with default data directory.
    Can be overridden in tests using FastAPI's dependency override.

    Example:
        # In tests
        app.dependency_overrides[get_tax_calculator] = lambda: TaxCalculator(test_dir)
    """
    return TaxCalculator()
