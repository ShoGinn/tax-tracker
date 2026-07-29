"""Shared API dependencies."""

from taxtracker.models.tax_data import FICALimits, TaxBrackets  # noqa: TC001
from taxtracker.services.data_loader import load_fica_limits_model, load_tax_brackets_model


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
