"""Application configuration API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from taxtracker.api.dependencies import get_db
from taxtracker.models.schemas import AppConfigResponse, AppConfigUpdate
from taxtracker.services.config_service import get_config, update_config

router = APIRouter(prefix="/config", tags=["Config"])


@router.get(
    "",
    summary="Get application configuration",
    response_description="Current application-wide tax configuration (filing status, dependents, deduction settings)",
)
async def read_config(db: Annotated[AsyncSession, Depends(get_db)]) -> AppConfigResponse:
    """Return the current application configuration."""
    config = await get_config(db)
    return AppConfigResponse.model_validate(config)


@router.put(
    "",
    summary="Update application configuration",
    response_description="Updated application-wide tax configuration",
)
async def write_config(
    update: AppConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppConfigResponse:
    """Update application configuration fields (partial update — only provided fields are changed)."""
    config = await update_config(db, update)
    return AppConfigResponse.model_validate(config)
