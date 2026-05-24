"""Application-wide configuration service."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from taxtracker.models.database import AppConfig
from taxtracker.models.tax_data import FilingStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from taxtracker.models.schemas import AppConfigUpdate

_SINGLETON_ID = 1

_DEFAULTS = {
    "filing_status": FilingStatus.MARRIED_FILING_JOINTLY,
    "num_children": 0,
    "use_standard_deduction": True,
    "itemized_deduction_amount": Decimal(0),
    "age_65_plus": False,
}


async def get_config(db: AsyncSession) -> AppConfig:
    """Return the singleton app config, creating it with defaults if absent."""
    result = await db.execute(select(AppConfig).where(AppConfig.id == _SINGLETON_ID))
    config = result.scalar_one_or_none()
    if config is None:
        config = AppConfig(id=_SINGLETON_ID, **_DEFAULTS)
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config


async def update_config(db: AsyncSession, update: AppConfigUpdate) -> AppConfig:
    """Update the singleton app config (upsert)."""
    result = await db.execute(select(AppConfig).where(AppConfig.id == _SINGLETON_ID))
    config = result.scalar_one_or_none()
    if config is None:
        config = AppConfig(id=_SINGLETON_ID, **_DEFAULTS)
        db.add(config)

    patch = update.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return config
