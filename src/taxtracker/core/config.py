"""Application configuration and settings."""

import datetime
from decimal import Decimal
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """Compute default data directory path."""
    return Path(str(files("taxtracker") / "data"))


class DataFileType(str, Enum):
    """Types of data files in the data directory."""

    TAX_BRACKETS = "tax_brackets"
    FICA_LIMITS = "fica_limits"


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Application
    app_name: str = "Tax Tracker"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database (use aiosqlite for async SQLite support)
    database_url: str = "sqlite+aiosqlite:///./tax_tracker.db"

    # Database connection pool settings (for production databases like PostgreSQL)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600  # Recycle connections after 1 hour
    db_echo: bool = False  # Set to True for SQL query logging

    # Data directory - can be overridden for testing
    data_dir: Path = Field(default_factory=_default_data_dir)

    # API
    api_host: str = "0.0.0.0"  # noqa: S104
    api_port: int = 8000

    def get_data_file(self, file_type: DataFileType, year: int) -> Path:
        """Get path to a data file for a given year.

        Args:
            file_type: Type of data file (e.g., TAX_BRACKETS, FICA_LIMITS)
            year: The tax year

        Returns:
            Path to the data file
        """
        return self.data_dir / f"{file_type.value}_{year}.json"

    w4_threshold: Decimal = Decimal("1000.00")


# Global settings instance
settings: Final[Settings] = Settings()


TAX_FILING_DEADLINE_MONTH: Final[int] = 4  # April


def current_tax_year() -> int:
    """Return the current tax year based on today's date.

    During tax filing season (Jan-Apr), returns the previous year since most
    users are filing for that year. After April, returns the current year.
    """
    today = datetime.datetime.now(tz=datetime.UTC).date()
    return today.year if today.month > TAX_FILING_DEADLINE_MONTH else today.year - 1
