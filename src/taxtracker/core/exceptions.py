"""Custom exceptions for taxtracker."""

from typing import Any


class TaxTrackerError(Exception):
    """Base exception for all taxtracker errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize exception with message and optional details.

        Args:
            message: Error message
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TaxCalculationError(TaxTrackerError):
    """Raised when tax calculation fails."""


class DataLoadError(TaxTrackerError):
    """Raised when loading tax data from JSON fails."""


class ValidationError(TaxTrackerError):
    """Raised when input validation fails."""


class W4CalculationError(TaxTrackerError):
    """Raised when W-4 calculation fails."""


class ProjectionError(TaxTrackerError):
    """Raised when tax projection fails."""
