"""FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from taxtracker.api.income import router as income_router
from taxtracker.api.projections import router as projections_router
from taxtracker.api.taxes import router as taxes_router
from taxtracker.api.w4 import router as w4_router
from taxtracker.core.config import settings
from taxtracker.models.database import Base, async_engine

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def create_app(skip_db_init: bool = False) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        skip_db_init: If True, skip database initialization (for tests)
    """

    # Create lifespan with conditional DB init
    @asynccontextmanager
    async def app_lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        """Application lifespan manager."""
        # Startup

        if not skip_db_init:
            # Initialize database tables asynchronously

            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            pass

        yield

        # Shutdown - properly dispose of the engine and close connections
        await async_engine.dispose()

    app = FastAPI(
        title="Tax Tracker API",
        description="Personal federal tax calculation and W-4 optimization system. "
        "Tracks W-2 paychecks, 1099-R pension income, and non-taxable income (VA disability, etc.) "
        "to calculate federal tax liability, reconcile withholding, and optimize W-4 settings.",
        version="1.0.0",
        lifespan=app_lifespan,
        openapi_tags=[
            {
                "name": "Income",
                "description": "Create, list, and delete W-2 paychecks, 1099-R pension entries, "
                "and non-taxable income (VA disability, SSA, gifts). Supports CSV bulk import.",
            },
            {
                "name": "Taxes",
                "description": "Calculate federal tax liability directly or from database income. "
                "Retrieve IRS tax brackets and FICA limits. Upload custom tax data files.",
            },
            {
                "name": "W-4",
                "description": "Optimize W-4 form settings to hit a target refund, calculate "
                "per-paycheck withholding (IRS Publication 15-T), and estimate annual withholding.",
            },
            {
                "name": "Projections",
                "description": "Project future-year tax liability from expected income, "
                "compare taxes year-over-year, or use historical database averages.",
            },
        ],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Include routers (no /api prefix!)
    app.include_router(taxes_router)
    app.include_router(w4_router)
    app.include_router(income_router)
    app.include_router(projections_router)

    @app.get("/")
    def root() -> dict[str, str]:
        """Root endpoint."""
        return {
            "name": "Tax Tracker API",
            "version": "1.0.0",
            "status": "active",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint with database connectivity test."""
        try:
            # Test database connectivity
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
        except Exception as e:
            return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

    return app


# Create app instance
app = create_app()


def main() -> None:
    """CLI entry point."""

    uvicorn.run(
        "taxtracker.cli.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
