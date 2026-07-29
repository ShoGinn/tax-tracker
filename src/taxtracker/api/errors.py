"""Shared API error handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    import logging


def internal_server_error(logger: logging.Logger, operation: str, exc: Exception) -> HTTPException:
    """Log an unexpected exception and return a sanitized API error."""
    logger.error("%s failed: %s", operation, exc, exc_info=exc)
    return HTTPException(status_code=500, detail="Internal server error")
