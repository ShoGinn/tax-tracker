"""Shared API dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.models.database import AsyncSessionLocal
from taxtracker.models.tax_data import FICALimits, TaxBrackets
from taxtracker.services.data_loader import load_fica_limits_model, load_tax_brackets_model


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session.

    Yields async database session and ensures cleanup.
    Can be overridden in tests using FastAPI's dependency override.
    """
    async with AsyncSessionLocal() as session:
        yield session


def get_tax_data(year: int) -> tuple[TaxBrackets, FICALimits]:
    """Get tax brackets and FICA limits for a given year.

    This dependency loads tax data from files and returns validated models.
    Can be overridden in tests to inject test data without file I/O.

    The `year` parameter is automatically injected from the path parameter
    by FastAPI's dependency system.

    Args:
        year: Tax year (injected from path parameter)

    Returns:
        Tuple of (TaxBrackets, FICALimits) models

    Raises:
        DataLoadError: If data cannot be loaded
    """
    tax_brackets = load_tax_brackets_model(year)
    fica_limits = load_fica_limits_model(year)
    return (tax_brackets, fica_limits)
