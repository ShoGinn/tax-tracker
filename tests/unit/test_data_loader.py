"""Unit tests for data_loader service."""

from decimal import Decimal

import pytest

from taxtracker.core.exceptions import DataLoadError
from taxtracker.services.data_loader import load_fica_limits, load_tax_brackets


class TestLoadTaxBrackets:
    """Tests for load_tax_brackets function."""

    def test_load_2025_brackets(self):
        """Test loading 2025 tax brackets."""
        data = load_tax_brackets(2025)

        assert data["tax_year"] == 2025
        assert "tax_brackets" in data
        assert "standard_deductions" in data
        assert "married_filing_jointly" in data["tax_brackets"]
        assert "single" in data["tax_brackets"]

    def test_load_2026_brackets(self):
        """Test loading 2026 tax brackets."""
        data = load_tax_brackets(2026)

        assert data["tax_year"] == 2026
        assert "tax_brackets" in data
        assert "standard_deductions" in data

    def test_load_nonexistent_year(self):
        """Test loading non-existent year raises error."""
        with pytest.raises(DataLoadError) as exc_info:
            load_tax_brackets(2099)

        assert "2099" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()

    def test_bracket_structure(self):
        """Test tax bracket structure is correct."""
        data = load_tax_brackets(2025)
        brackets = data["tax_brackets"]["single"]

        # Should have 7 brackets
        assert len(brackets) == 7

        # First bracket
        first = brackets[0]
        assert "min" in first
        assert "max" in first
        assert "rate" in first
        assert first["rate"] == 0.10

        # Last bracket has no max
        last = brackets[-1]
        assert last["max"] is None
        assert last["rate"] == 0.37


class TestLoadFICALimits:
    """Tests for load_fica_limits function."""

    def test_load_2025_fica(self):
        """Test loading 2025 FICA limits."""
        data = load_fica_limits(2025)

        assert data["tax_year"] == 2025
        assert "social_security" in data
        assert "medicare" in data

    def test_social_security_structure(self):
        """Test Social Security data structure."""
        data = load_fica_limits(2025)
        ss = data["social_security"]

        assert "employee_rate" in ss
        assert "wage_base_limit" in ss
        assert "max_employee_tax" in ss
        assert ss["employee_rate"] == 0.062
        assert ss["wage_base_limit"] == 176100  # 2025 IRS limit

    def test_medicare_structure(self):
        """Test Medicare data structure."""
        data = load_fica_limits(2025)
        medicare = data["medicare"]

        assert "employee_rate" in medicare
        assert medicare["employee_rate"] == 0.0145  # 1.45%

        # Check additional Medicare
        additional = data["additional_medicare"]
        assert "rate" in additional
        assert additional["rate"] == 0.009  # 0.9%
        assert "thresholds" in additional

    def test_load_nonexistent_year(self):
        """Test loading non-existent year raises error."""
        with pytest.raises(DataLoadError):
            load_fica_limits(2099)


@pytest.mark.unit
class TestDataLoaderIntegration:
    """Integration tests for data loading."""

    def test_both_files_for_same_year(self):
        """Test loading both tax brackets and FICA for same year."""
        year = 2025

        tax_data = load_tax_brackets(year)
        fica_data = load_fica_limits(year)

        assert tax_data["tax_year"] == year
        assert fica_data["tax_year"] == year

    def test_standard_deduction_amounts(self):
        """Test standard deduction amounts are reasonable."""
        data = load_tax_brackets(2025)
        deductions = data["standard_deductions"]

        # Married should be roughly 2x single
        married = deductions["married_filing_jointly"]
        single = deductions["single"]

        assert married > single
        assert married / single < 2.5  # Roughly 2x
        assert married / single > 1.5
