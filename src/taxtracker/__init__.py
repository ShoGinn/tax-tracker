"""Tax Tracker - Personal tax calculation and W-4 optimization system."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

try:
    __version__ = package_version("taxtracker")
except PackageNotFoundError:
    __version__ = "0.0.0"

__author__ = "Tax Tracker Team"
