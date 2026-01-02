"""Application configuration and settings."""

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

    # Database
    database_url: str = "sqlite:///./tax_tracker.db"

    # Data directory - can be overridden for testing
    data_dir: Path = Field(default_factory=_default_data_dir)

    # API
    api_host: str = "0.0.0.0"
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


# Global settings instance
settings: Final[Settings] = Settings()
