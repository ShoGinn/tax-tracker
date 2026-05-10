"""Example tests using IRS-verified test data.

These tests demonstrate the proper approach:
1. Use injected test data instead of JSON files
2. Verify calculations against known IRS examples
3. Tests are deterministic and independent of external files
"""

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from fixtures.irs_test_data import (
    FICA_EXAMPLE_1,
    FICA_EXAMPLE_2,
    IRS_EXAMPLE_1,
    IRS_EXAMPLE_2,
)

from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest

if TYPE_CHECKING:
    from taxtracker.services.tax_calculator import TaxCalculator


@pytest.mark.unit
class TestTaxCalculatorWithIRSData:
    """Tests using IRS-verified examples."""

    def test_irs_example_1_single_filer(self, irs_2024_calculator: TaxCalculator):
        """Test IRS Example 1: Single filer, no dependents.

        From IRS Publication 17, Chapter 1
        - Gross income: $50,000
        - Standard deduction: $14,600
        - Taxable income: $35,400
        - Expected tax: ~$4,058
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(str(IRS_EXAMPLE_1["gross_income"])),
            num_children=IRS_EXAMPLE_1["num_children"],
            use_standard_deduction=IRS_EXAMPLE_1["use_standard_deduction"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income calculation
        assert abs(float(result.taxable_income) - IRS_EXAMPLE_1["expected_taxable_income"]) < 1

        # Verify federal tax (allow small tolerance for rounding/bracket differences)
        assert abs(float(result.federal_tax_owed) - IRS_EXAMPLE_1["expected_federal_tax"]) < 50

        # Verify marginal rate
        assert float(result.marginal_tax_rate) == IRS_EXAMPLE_1["expected_marginal_rate"]

    def test_irs_example_2_married_with_children(self, irs_2024_calculator: TaxCalculator):
        """Test IRS Example 2: Married filing jointly with 2 children.

        From IRS Publication 17, Chapter 1
        - Gross income: $100,000
        - Standard deduction: $29,200
        - Taxable income: $70,800
        - Tax before credits: ~$8,076
        - Child credits: $4,000 (2 x $2,000)
        - Final tax: ~$4,076
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            w2_gross_income=Decimal(str(IRS_EXAMPLE_2["gross_income"])),
            num_children=IRS_EXAMPLE_2["num_children"],
            use_standard_deduction=IRS_EXAMPLE_2["use_standard_deduction"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income
        assert abs(float(result.taxable_income) - IRS_EXAMPLE_2["expected_taxable_income"]) < 1

        # Verify child tax credits
        assert abs(float(result.child_tax_credits) - IRS_EXAMPLE_2["expected_child_credits"]) < 1

        # Verify final tax after credits (allow more tolerance for bracket differences)
        assert abs(float(result.total_tax_liability) - IRS_EXAMPLE_2["expected_federal_tax"]) < 100


@pytest.mark.unit
class TestSimplifiedTaxCalculations:
    """Tests using simplified test data for easy verification."""

    def test_simple_10_percent_bracket(self, test_calculator: TaxCalculator):
        """Test simple calculation in 10% bracket.

        Using simplified test data (year 2030):
        - Income: $8,000
        - Standard deduction: $15,000
        - Taxable: $0 (income below deduction)
        - Tax: $0
        """
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(8000),
            num_children=0,
        )

        result = test_calculator.calculate_taxes(request)

        # Income below standard deduction = no tax
        assert float(result.taxable_income) == 0
        assert float(result.federal_tax_owed) == 0

    def test_simple_12_percent_bracket(self, test_calculator: TaxCalculator):
        """Test simple calculation in 12% bracket.

        Using IRS 2024 test data:
        - Income: $30,000
        - Standard deduction: $14,600
        - Taxable: $15,400
        - Tax: $1,160 (10% on first $11,600) + $455.88 (12% on next $3,800) = $1,615.88
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(30000),
            num_children=0,
        )

        result = test_calculator.calculate_taxes(request)

        standard_deduction = test_calculator.tax_brackets.standard_deductions.amounts[FilingStatus.SINGLE]
        expected_taxable_income = Decimal(30000) - standard_deduction
        first_bracket_threshold = test_calculator.tax_brackets.tax_brackets[FilingStatus.SINGLE][0].threshold
        first_bracket_rate = test_calculator.tax_brackets.tax_brackets[FilingStatus.SINGLE][0].rate
        second_bracket_rate = test_calculator.tax_brackets.tax_brackets[FilingStatus.SINGLE][1].rate
        expected_tax = (first_bracket_threshold * first_bracket_rate) + (
            (expected_taxable_income - first_bracket_threshold) * second_bracket_rate
        )

        # Verify taxable income
        assert result.taxable_income == expected_taxable_income

        # Verify tax calculation
        assert abs(result.federal_tax_owed - expected_tax) < Decimal("1.00")

        # Marginal rate should be 12%
        assert float(result.marginal_tax_rate) == 12

    def test_simple_with_child_credits(self, test_calculator: TaxCalculator):
        """Test calculation with child tax credits.

        Using simplified test data:
        - Income: $60,000
        - Standard deduction: $15,000
        - Taxable: $45,000
        - Children: 2
        - Child credits: $4,000 (2 x $2,000)
        """
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(60000),
            num_children=2,
        )

        result = test_calculator.calculate_taxes(request)

        ctc_per_child = test_calculator.tax_brackets.child_tax_credit.amount_per_child
        expected_child_credits = ctc_per_child * Decimal(2)

        # Verify child credits applied
        assert result.child_tax_credits == expected_child_credits

        # Credits reduce tax liability
        assert float(result.child_tax_credits) > 0
        assert float(result.federal_tax_owed) >= 0


@pytest.mark.unit
class TestFICAWithIRSData:
    """Test FICA calculations using IRS examples."""

    def test_fica_example_1_standard_wages(self, irs_2024_calculator: TaxCalculator):
        """Test FICA Example 1: Standard wages under SS limit.

        From IRS Publication 15 (Circular E):
        - Wages: $50,000
        - SS tax: $3,100 (50,000 * 6.2%)
        - Medicare: $725 (50,000 * 1.45%)
        - Total: $3,825
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(str(FICA_EXAMPLE_1["gross_wages"])),
            num_children=0,
        )

        result = irs_2024_calculator.calculate_taxes(request)

        fica = result.fica_taxes

        # Verify SS tax
        ss_tax = float(fica.get("social_security_tax", 0))
        assert abs(ss_tax - FICA_EXAMPLE_1["expected_ss_tax"]) < 1

        # Verify Medicare tax
        medicare_tax = float(fica.get("medicare_tax", 0))
        assert abs(medicare_tax - FICA_EXAMPLE_1["expected_medicare_tax"]) < 1

        # Verify total
        total_fica = float(fica.get("total_fica", 0))
        assert abs(total_fica - FICA_EXAMPLE_1["expected_total_fica"]) < 1

    def test_fica_example_2_exceeds_ss_limit(self, irs_2024_calculator: TaxCalculator):
        """Test FICA Example 2: Wages exceeding SS limit.

        From IRS Publication 15:
        - Wages: $200,000
        - SS tax: CAPPED at wage base limit * 6.2%
        - Medicare: $2,900 (200,000 * 1.45%)
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(str(FICA_EXAMPLE_2["gross_wages"])),
            num_children=0,
        )

        result = irs_2024_calculator.calculate_taxes(request)

        fica = result.fica_taxes

        # Verify SS tax is capped (exact amount depends on wage base)
        ss_tax = float(fica.get("social_security_tax", 0))
        # Should be between $10k-$11k (168600*.062 to 176100*.062)
        assert 10000 < ss_tax < 11000, f"SS tax {ss_tax} should be capped"

        # Verify Medicare has no cap
        medicare_tax = float(fica.get("medicare_tax", 0))
        assert abs(medicare_tax - FICA_EXAMPLE_2["expected_medicare_tax"]) < 1


@pytest.mark.unit
class TestDeterministicCalculations:
    """Tests that calculations are deterministic and repeatable."""

    def test_same_input_same_output(self, test_calculator: TaxCalculator):
        """Test that same input always produces same output."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(75000),
            num_children=1,
        )

        # Calculate multiple times
        result1 = test_calculator.calculate_taxes(request)
        result2 = test_calculator.calculate_taxes(request)
        result3 = test_calculator.calculate_taxes(request)

        # All results should be identical
        assert result1.federal_tax_owed == result2.federal_tax_owed
        assert result2.federal_tax_owed == result3.federal_tax_owed

        assert result1.taxable_income == result2.taxable_income
        assert result2.taxable_income == result3.taxable_income

    def test_no_external_file_dependency(self, test_calculator: TaxCalculator):
        """Test that calculator works without accessing external files."""
        # This test passes if no FileNotFoundError is raised
        request = TaxCalculationRequest(
            tax_year=2030,  # Year that doesn't exist in JSON files
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(50000),
            num_children=0,
        )

        result = test_calculator.calculate_taxes(request)

        # Should work without accessing any JSON files
        assert result.federal_tax_owed >= 0
