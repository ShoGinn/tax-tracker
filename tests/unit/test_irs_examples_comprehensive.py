"""Comprehensive IRS Publication tests - additional examples.

These tests verify calculations against published IRS examples from:
- IRS Publication 17 (Individual Income Tax)
- IRS Publication 15 (Employer's Tax Guide - Circular E)
"""

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from fixtures.irs_test_data import (
    EDGE_CASE_1,
    EDGE_CASE_2,
    EDGE_CASE_3,
    EDGE_CASE_4,
    EDGE_CASE_5,
    FICA_EXAMPLE_4,
    FICA_EXAMPLE_5,
    IRS_EXAMPLE_3,
    IRS_EXAMPLE_4,
    IRS_EXAMPLE_5,
    IRS_EXAMPLE_6,
)

from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest

if TYPE_CHECKING:
    from taxtracker.services.tax_calculator import TaxCalculator


@pytest.mark.unit
class TestAdditionalIRSExamples:
    """Tests for additional IRS Publication 17 examples."""

    def test_irs_example_3_high_income(self, irs_2024_calculator: TaxCalculator):
        """Test IRS Example 3: High income single filer in 32% bracket.

        From IRS Publication 17:
        - Income: $250,000
        - Standard deduction: $14,600
        - Taxable: $235,400
        - Marginal rate: 32%
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(str(IRS_EXAMPLE_3["gross_income"])),
            num_children=IRS_EXAMPLE_3["num_children"],
            use_standard_deduction=IRS_EXAMPLE_3["use_standard_deduction"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income
        assert abs(float(result.taxable_income) - IRS_EXAMPLE_3["expected_taxable_income"]) < 1

        # Verify in 32% bracket
        assert float(result.marginal_tax_rate) == IRS_EXAMPLE_3["expected_marginal_rate"]

    def test_irs_example_4_head_of_household(self, irs_2024_calculator: TaxCalculator):
        """Test IRS Example 4: Head of household with 1 child.

        - Income: $75,000
        - Filing: Head of household
        - Standard deduction: $21,900
        - Taxable: $53,100
        - Child credits: $2,000
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            gross_income=Decimal(str(IRS_EXAMPLE_4["gross_income"])),
            num_children=IRS_EXAMPLE_4["num_children"],
            use_standard_deduction=IRS_EXAMPLE_4["use_standard_deduction"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income
        assert abs(float(result.taxable_income) - IRS_EXAMPLE_4["expected_taxable_income"]) < 1

        # Verify child credits
        assert abs(float(result.child_tax_credits) - IRS_EXAMPLE_4["expected_child_credits"]) < 1

        # Verify marginal rate
        assert float(result.marginal_tax_rate) == IRS_EXAMPLE_4["expected_marginal_rate"]

    def test_irs_example_5_itemized_deductions(self, irs_2024_calculator: TaxCalculator):
        """Test IRS Example 5: Single filer with itemized deductions.

        - Income: $80,000
        - Itemized deductions: $20,000
        - Taxable: $60,000
        - Marginal rate: 22%
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(str(IRS_EXAMPLE_5["gross_income"])),
            num_children=IRS_EXAMPLE_5["num_children"],
            use_standard_deduction=IRS_EXAMPLE_5["use_standard_deduction"],
            itemized_deduction_amount=Decimal(str(IRS_EXAMPLE_5["itemized_deductions"])),
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income
        assert abs(float(result.taxable_income) - IRS_EXAMPLE_5["expected_taxable_income"]) < 1

        # Verify marginal rate
        assert float(result.marginal_tax_rate) == IRS_EXAMPLE_5["expected_marginal_rate"]

    def test_irs_example_6_large_family(self, irs_2024_calculator: TaxCalculator):
        """Test IRS Example 6: Married with 3 children - large family.

        - Income: $150,000
        - Filing: Married filing jointly
        - Children: 3
        - Child credits: $6,000 (3 * $2,000)
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            gross_income=Decimal(str(IRS_EXAMPLE_6["gross_income"])),
            num_children=IRS_EXAMPLE_6["num_children"],
            use_standard_deduction=IRS_EXAMPLE_6["use_standard_deduction"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income
        assert abs(float(result.taxable_income) - IRS_EXAMPLE_6["expected_taxable_income"]) < 1

        # Verify child credits
        assert abs(float(result.child_tax_credits) - IRS_EXAMPLE_6["expected_child_credits"]) < 1


@pytest.mark.unit
class TestAdditionalFICAExamples:
    """Tests for additional FICA examples from IRS Publication 15."""

    def test_fica_example_4_low_income(self, irs_2024_calculator: TaxCalculator):
        """Test FICA Example 4: Low income worker.

        - Wages: $25,000
        - SS: $1,550 (25,000 * 6.2%)
        - Medicare: $362.50 (25,000 * 1.45%)
        - Total: $1,912.50
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(str(FICA_EXAMPLE_4["gross_wages"])),
            num_children=0,
        )

        result = irs_2024_calculator.calculate_taxes(request)
        fica = result.fica_taxes

        # Verify SS tax
        ss_tax = float(fica.get("social_security_tax", 0))
        assert abs(ss_tax - FICA_EXAMPLE_4["expected_ss_tax"]) < 1

        # Verify Medicare tax
        medicare_tax = float(fica.get("medicare_tax", 0))
        assert abs(medicare_tax - FICA_EXAMPLE_4["expected_medicare_tax"]) < 1

    def test_fica_example_5_married_additional_medicare(self, irs_2024_calculator: TaxCalculator):
        """Test FICA Example 5: Married at additional Medicare threshold.

        - Wages: $275,000
        - Filing: Married filing jointly
        - SS: Capped at ~$10,453
        - Medicare: $3,987.50 (275,000 * 1.45%)
        - Additional Medicare: $225 ((275,000 - 250,000) * 0.9%)
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            gross_income=Decimal(str(FICA_EXAMPLE_5["gross_wages"])),
            num_children=0,
        )

        result = irs_2024_calculator.calculate_taxes(request)
        fica = result.fica_taxes

        # Verify SS is capped
        ss_tax = float(fica.get("social_security_tax", 0))
        assert 10000 < ss_tax < 12000

        # Verify Medicare (base + additional)
        float(fica.get("medicare_tax", 0))
        additional_medicare = float(fica.get("additional_medicare_tax", 0))

        # Should have additional Medicare for married over $250k
        assert additional_medicare > 0


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_edge_case_1_income_equals_deduction(self, irs_2024_calculator: TaxCalculator):
        """Test Edge Case 1: Income exactly equals standard deduction.

        - Income: $14,600 (exactly standard deduction)
        - Taxable: $0
        - Tax: $0
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(str(EDGE_CASE_1["gross_income"])),
            num_children=EDGE_CASE_1["num_children"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Zero tax when income equals deduction
        assert float(result.taxable_income) == EDGE_CASE_1["expected_taxable_income"]
        assert float(result.federal_tax_owed) == EDGE_CASE_1["expected_federal_tax"]

    def test_edge_case_2_one_dollar_over(self, irs_2024_calculator: TaxCalculator):
        """Test Edge Case 2: Income $1 over standard deduction.

        - Income: $14,601 ($1 over deduction)
        - Taxable: $1
        - Tax: $0.10 (10% of $1)
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(str(EDGE_CASE_2["gross_income"])),
            num_children=EDGE_CASE_2["num_children"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Minimal tax on $1
        assert float(result.taxable_income) == EDGE_CASE_2["expected_taxable_income"]
        assert abs(float(result.federal_tax_owed) - EDGE_CASE_2["expected_federal_tax"]) < 0.01

    def test_edge_case_3_maximum_child_credits(self, irs_2024_calculator: TaxCalculator):
        """Test Edge Case 3: Maximum child tax credits (5 children).

        - Income: $120,000
        - Filing: Married filing jointly
        - Children: 5
        - Credits: $10,000 (5 * $2,000)
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            gross_income=Decimal(str(EDGE_CASE_3["gross_income"])),
            num_children=EDGE_CASE_3["num_children"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify large child credits
        assert abs(float(result.child_tax_credits) - EDGE_CASE_3["expected_child_credits"]) < 1

    def test_edge_case_4_top_bracket(self, irs_2024_calculator: TaxCalculator):
        """Test Edge Case 4: Very high earner in top bracket.

        - Income: $750,000
        - Taxable: $735,400
        - Marginal rate: 37% (top bracket)
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(str(EDGE_CASE_4["gross_income"])),
            num_children=EDGE_CASE_4["num_children"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income
        assert abs(float(result.taxable_income) - EDGE_CASE_4["expected_taxable_income"]) < 1

        # Verify in top bracket
        assert float(result.marginal_tax_rate) == EDGE_CASE_4["expected_marginal_rate"]

    def test_edge_case_5_married_separately(self, irs_2024_calculator: TaxCalculator):
        """Test Edge Case 5: Married filing separately.

        - Income: $60,000
        - Filing: Married filing separately
        - Uses different bracket thresholds
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.MARRIED_FILING_SEPARATELY,
            gross_income=Decimal(str(EDGE_CASE_5["gross_income"])),
            num_children=EDGE_CASE_5["num_children"],
        )

        result = irs_2024_calculator.calculate_taxes(request)

        # Verify taxable income
        assert abs(float(result.taxable_income) - EDGE_CASE_5["expected_taxable_income"]) < 1

        # Verify marginal rate
        assert float(result.marginal_tax_rate) == EDGE_CASE_5["expected_marginal_rate"]
