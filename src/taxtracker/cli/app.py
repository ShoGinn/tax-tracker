"""FastAPI application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from taxtracker.api.admin import router as admin_router
from taxtracker.api.income import router as income_router
from taxtracker.api.projections import router as projections_router
from taxtracker.api.taxes import router as taxes_router
from taxtracker.api.w4 import router as w4_router
from taxtracker.core.config import settings
from taxtracker.models.database import Base, engine


def create_app(skip_db_init: bool = False) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        skip_db_init: If True, skip database initialization (for tests)
    """

    # Create lifespan with conditional DB init
    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan manager."""
        # Startup
        print("🚀 Tax Tracker starting up...")

        if not skip_db_init:
            # Initialize database tables

            Base.metadata.create_all(bind=engine)
            print("✅ Database initialized")
        else:
            print("⏭️  Skipping database initialization (test mode)")

        yield

        # Shutdown
        print("👋 Tax Tracker shutting down...")

    app = FastAPI(
        title="Tax Tracker API",
        description="Personal tax calculation and W-4 optimization system",
        version="1.0.0",
        lifespan=app_lifespan,
    )

    # Include routers (no /api prefix!)
    app.include_router(taxes_router)
    app.include_router(w4_router)
    app.include_router(income_router)
    app.include_router(projections_router)
    app.include_router(admin_router)

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
    def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

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
