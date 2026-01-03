"""Shared API dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.models.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session.

    Yields async database session and ensures cleanup.
    Can be overridden in tests using FastAPI's dependency override.
    """
    async with AsyncSessionLocal() as session:
        yield session
