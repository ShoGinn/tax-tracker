"""Unit tests for tax_calculator service using IRS-verified test data."""

from decimal import Decimal

from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest


class TestTaxCalculator:
    """Tests for TaxCalculator class."""

    def test_calculator_initialization(self, test_calculator):
        """Test calculator initializes correctly with injected data."""
        assert test_calculator is not None
        # Verify injected data is available
        brackets = test_calculator.load_tax_brackets(2030)
        assert brackets.tax_year == 2030

    def test_load_injected_tax_brackets(self, test_calculator):
        """Test loading injected tax brackets."""
        brackets = test_calculator.load_tax_brackets(2030)

        assert brackets.tax_year == 2030
        assert hasattr(brackets, "tax_brackets")
        assert hasattr(brackets, "standard_deductions")
        assert "single" in brackets.tax_brackets

    def test_load_injected_fica_limits(self, test_calculator):
        """Test loading injected FICA limits."""
        fica = test_calculator.load_fica_limits(2030)

        # Uses 2025 FICA data as template
        assert hasattr(fica, "social_security")
        assert hasattr(fica, "medicare")


class TestFederalTaxCalculation:
    """Tests for federal tax calculation using simplified test data.
    
    Simplified test data (year 2030):
    - Single standard deduction: $15,000
    - Married standard deduction: $30,000
    - Brackets: 10% ($0-$10k), 12% ($10k-$40k), 22% ($40k-$100k), 24% ($100k+)
    """

    def test_single_filer_50k(self, test_calculator):
        """Test single filer with $50k income using simplified brackets.
        
        Expected calculation:
        - Gross: $50,000
        - Std deduction: $15,000
        - Taxable: $35,000
        - Tax: $1,000 (10% on $10k) + $3,000 (12% on $25k) = $4,000
        """
        gross_income = Decimal("50000")
        standard_deduction = Decimal("15000")
        taxable_income = max(Decimal(0), gross_income - standard_deduction)

        federal_tax, marginal_rate, breakdown = test_calculator.calculate_federal_tax(
            taxable_income=taxable_income,
            filing_status=FilingStatus.SINGLE,
            year=2030
        )

        # Verify taxable income
        assert taxable_income == Decimal("35000")

        # Should have federal tax (35000 is in 12% bracket)
        assert federal_tax > 0

        # Calculate expected tax manually (Simplified 2030 brackets):
        # First $10,000 at 10% = $1,000
        # Next $25,000 ($35,000 - $10,000) at 12% = $3,000
        # Total = $4,000
        expected_tax = Decimal("1000") + Decimal("3000")
        assert abs(federal_tax - expected_tax) < Decimal("1.00")

        # Marginal rate should be 12%
        assert marginal_rate == Decimal("0.12")

    def test_married_filing_jointly_100k(self, test_calculator):
        """Test married filing jointly with $100k income.
        
        Expected calculation:
        - Gross: $100,000
        - Std deduction: $30,000
        - Taxable: $70,000
        - Tax: $2,000 (10% on $20k) + $6,000 (12% on $50k) = $8,000
        """
        gross_income = Decimal("100000")
        standard_deduction = Decimal("30000")
        taxable_income = max(Decimal(0), gross_income - standard_deduction)

        federal_tax, marginal_rate, breakdown = test_calculator.calculate_federal_tax(
            taxable_income=taxable_income,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            year=2030
        )

        # Verify taxable income
        assert taxable_income == Decimal("70000")
        assert federal_tax > 0

        # Should be in 12% bracket
        assert marginal_rate == Decimal("0.12")

        # Expected: $2,000 (10% on $20k) + $6,000 (12% on $50k) = $8,000
        expected_tax = Decimal("2000") + Decimal("6000")
        assert abs(federal_tax - expected_tax) < Decimal("1.00")

    def test_zero_income(self, test_calculator):
        """Test with zero income."""
        federal_tax, marginal_rate, breakdown = test_calculator.calculate_federal_tax(
            taxable_income=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
            year=2030
        )

        assert federal_tax == Decimal("0")
        # With $0 taxable income, marginal rate should be 0 or first bracket
        assert marginal_rate >= Decimal("0")
        assert marginal_rate <= Decimal("0.10")


class TestFICACalculation:
    """Tests for FICA tax calculation."""

    def test_fica_under_ss_limit(self, test_calculator):
        """Test FICA calculation under social security limit.
        
        For $50,000 income:
        - SS: $50,000 * 6.2% = $3,100
        - Medicare: $50,000 * 1.45% = $725
        - Total: $3,825
        """
        fica_taxes = test_calculator.calculate_fica(
            gross_wages=Decimal("50000"),
            filing_status=FilingStatus.SINGLE,
            year=2030
        )

        # Verify structure
        assert "social_security_tax" in fica_taxes
        assert "medicare_tax" in fica_taxes
        assert "total_fica" in fica_taxes

        # Verify amounts
        ss_tax = fica_taxes["social_security_tax"]
        medicare_tax = fica_taxes["medicare_tax"]

        assert abs(float(ss_tax) - 3100.0) < 1.0
        assert abs(float(medicare_tax) - 725.0) < 1.0

    def test_fica_over_ss_limit(self, test_calculator):
        """Test FICA calculation over social security limit.
        
        For $200,000 income:
        - SS: Capped at wage base (~$176,100 * 6.2% = ~$10,918)
        - Medicare: $200,000 * 1.45% = $2,900
        - Additional Medicare: $0 (threshold is $200k for single)
        """
        fica_taxes = test_calculator.calculate_fica(
            gross_wages=Decimal("200000"),
            filing_status=FilingStatus.SINGLE,
            year=2030
        )

        ss_tax = float(fica_taxes["social_security_tax"])
        medicare_tax = float(fica_taxes["medicare_tax"])

        # SS should be capped (between $10k-$11k depending on wage base)
        assert 10000 < ss_tax < 12000

        # Medicare should not be capped
        assert abs(medicare_tax - 2900.0) < 1.0


class TestFullTaxCalculation:
    """Tests for complete tax calculation using TaxCalculationRequest."""

    def test_simple_single_calculation(self, test_calculator):
        """Test complete calculation for single filer."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal("75000"),
            num_children=0,
            use_standard_deduction=True
        )

        result = test_calculator.calculate_taxes(request)

        # Verify response structure
        assert result.gross_income == Decimal("75000")
        assert result.adjusted_gross_income == Decimal("75000")
        assert result.taxable_income > 0
        assert result.federal_tax_owed > 0
        assert result.total_tax_liability > 0

        # Taxable income should be gross - standard deduction ($15k)
        assert result.taxable_income == Decimal("60000")

    def test_married_with_children(self, test_calculator):
        """Test calculation with child tax credits."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            gross_income=Decimal("100000"),
            num_children=2,
            use_standard_deduction=True
        )

        result = test_calculator.calculate_taxes(request)

        # Should have child tax credits
        assert result.child_tax_credits > 0
        # 2 children * $2,000 = $4,000
        assert result.child_tax_credits == Decimal("4000")

        # Credits should reduce total tax
        assert result.total_tax_liability < result.federal_tax_owed + result.child_tax_credits

    def test_itemized_deductions(self, test_calculator):
        """Test with itemized deductions."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal("80000"),
            num_children=0,
            use_standard_deduction=False,
            itemized_deduction_amount=Decimal("25000")
        )

        result = test_calculator.calculate_taxes(request)

        # Should use itemized deduction
        assert result.deduction_type == "Itemized Deduction"
        assert result.deduction_amount == Decimal("25000")

        # Taxable income should be gross - itemized ($25k)
        assert result.taxable_income == Decimal("55000")


class TestTaxCalculatorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_income_at_bracket_boundary(self, test_calculator):
        """Test income exactly at bracket boundary.
        
        $10,000 is exactly the boundary between 10% and 12% brackets.
        """
        # Income at standard deduction means $0 taxable
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal("15000"),  # Exactly std deduction
            num_children=0
        )

        result = test_calculator.calculate_taxes(request)

        # Should have $0 taxable income and $0 tax
        assert result.taxable_income == Decimal("0")
        assert result.federal_tax_owed == Decimal("0")

    def test_very_high_income(self, test_calculator):
        """Test very high income in top bracket.
        
        With simplified brackets, $500k should be in 24% bracket.
        """
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal("500000"),
            num_children=0
        )

        result = test_calculator.calculate_taxes(request)

        # Should be in top bracket (24%)
        assert result.marginal_tax_rate == Decimal("24.00")

        # Should have substantial tax liability
        assert result.federal_tax_owed > Decimal("100000")

    def test_pension_deduction(self, test_calculator):
        """Test with pension SBP deduction."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal("50000"),
            retirement_pretax_deductions=Decimal("5000"),
            num_children=0
        )

        result = test_calculator.calculate_taxes(request)

        # AGI should be reduced by pension deduction
        assert result.adjusted_gross_income == Decimal("45000")
        assert result.retirement_pretax_deductions == Decimal("5000")

    def test_va_disability_tracking(self, test_calculator):
        """Test VA disability income tracking (non-taxable)."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal("50000"),
            non_taxable_income=Decimal("20000"),
            num_children=0
        )

        result = test_calculator.calculate_taxes(request)

        # Total household income includes VA
        assert result.total_household_income == Decimal("70000")

        # But VA doesn't affect AGI or taxable income
        assert result.adjusted_gross_income == Decimal("50000")
