"""Unit tests for tax_calculator service using IRS-verified test data."""

from decimal import Decimal

from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest


class TestTaxCalculator:
    """Tests for TaxCalculator class."""

    def test_calculator_initialization(self, test_calculator):
        """Test calculator initializes correctly with injected data."""
        assert test_calculator is not None
        # Verify injected data is available
        assert test_calculator.tax_year == 2024
        assert test_calculator._tax_brackets is not None
        assert test_calculator._fica_limits is not None

    def test_tax_year_property(self, test_calculator):
        """Test that calculator stores tax year."""
        assert test_calculator.tax_year == 2024

    def test_tax_brackets_available(self, test_calculator):
        """Test that tax brackets are available from init."""
        brackets = test_calculator._tax_brackets

        assert brackets.tax_year == 2024
        assert hasattr(brackets, "tax_brackets")
        assert hasattr(brackets, "standard_deductions")
        assert FilingStatus.SINGLE in brackets.tax_brackets

    def test_fica_limits_available(self, test_calculator):
        """Test that FICA limits are available from init."""
        fica = test_calculator._fica_limits

        # Uses IRS 2024 FICA data
        assert hasattr(fica, "social_security")
        assert hasattr(fica, "medicare")


class TestFederalTaxCalculation:
    """Tests for federal tax calculation using IRS 2024 verified test data.

    IRS 2024 data:
    - Single standard deduction: $14,600
    - Married standard deduction: $29,200
    - Brackets (Single): 10% ($0-$11,600), 12% ($11,601-$47,150), 22% ($47,151-$100,525), etc.
    """

    def test_single_filer_50k(self, test_calculator):
        """Test single filer with $50k income using IRS 2024 brackets.

        Expected calculation:
        - Gross: $50,000
        - Std deduction: $14,600
        - Taxable: $35,400
        - Tax: 10% on $11,600 = $1,160
               12% on $23,800 ($35,400 - $11,600) = $2,856
        - Total: $4,016
        """
        gross_income = Decimal(50000)
        standard_deduction = Decimal(14600)
        taxable_income = max(Decimal(0), gross_income - standard_deduction)

        federal_tax, marginal_rate, _breakdown = test_calculator.calculate_federal_tax(
            taxable_income=taxable_income,
            filing_status=FilingStatus.SINGLE,
        )

        # Verify taxable income
        assert taxable_income == Decimal(35400)

        # Should have federal tax (35400 is in 12% bracket)
        assert federal_tax > 0

        # Calculate expected tax manually (IRS 2024 brackets):
        # First $11,600 at 10% = $1,160
        # Next $23,800 ($35,400 - $11,600) at 12% = $2,856
        # Total = $4,016
        expected_tax = Decimal(1160) + Decimal(2856)
        assert abs(federal_tax - expected_tax) < Decimal("1.00")

        # Marginal rate should be 12%
        assert marginal_rate == Decimal("0.12")

    def test_married_filing_jointly_100k(self, test_calculator):
        """Test married filing jointly with $100k income.

        Expected calculation:
        - Gross: $100,000
        - Std deduction: $29,200
        - Taxable: $70,800
        - Tax: 10% on $23,200 = $2,320
               12% on $47,600 ($70,800 - $23,200) = $5,712
        - Total: $8,032
        """
        gross_income = Decimal(100000)
        standard_deduction = Decimal(29200)
        taxable_income = max(Decimal(0), gross_income - standard_deduction)

        federal_tax, marginal_rate, _breakdown = test_calculator.calculate_federal_tax(
            taxable_income=taxable_income,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        )

        # Verify taxable income
        assert taxable_income == Decimal(70800)
        assert federal_tax > 0

        # Should be in 12% bracket
        assert marginal_rate == Decimal("0.12")

        # Expected: $2,320 (10% on $23,200) + $5,712 (12% on $47,600) = $8,032
        expected_tax = Decimal(2320) + Decimal(5712)
        assert abs(federal_tax - expected_tax) < Decimal("1.00")

    def test_zero_income(self, test_calculator):
        """Test with zero income."""
        federal_tax, marginal_rate, _breakdown = test_calculator.calculate_federal_tax(
            taxable_income=Decimal(0),
            filing_status=FilingStatus.SINGLE,
        )

        assert federal_tax == Decimal(0)
        # With $0 taxable income, marginal rate should be 0 or first bracket
        assert marginal_rate >= Decimal(0)
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
            gross_wages=Decimal(50000),
            filing_status=FilingStatus.SINGLE,
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

    def test_fica_over_ss_limit(self, irs_2024_calculator):
        """Test FICA calculation over social security limit.

        For $200,000 income:
        - SS: Capped at wage base (168,600 * 6.2% = 10,453.20 for 2024)
        - Medicare: $200,000 * 1.45% = $2,900
        - Additional Medicare: ($200,000 - $200,000) * 0.9% = $0
        """
        fica_taxes = irs_2024_calculator.calculate_fica(
            gross_wages=Decimal(200000),
            filing_status=FilingStatus.SINGLE,
        )

        ss_tax = float(fica_taxes["social_security_tax"])
        medicare_tax = float(fica_taxes["medicare_tax"])

        # SS should be capped at 2024 wage base
        assert abs(ss_tax - 10453.2) < 1

        # Medicare should not be capped
        assert abs(medicare_tax - 2900.0) < 1.0


class TestFullTaxCalculation:
    """Tests for complete tax calculation using TaxCalculationRequest."""

    def test_simple_single_calculation(self, test_calculator):
        """Test complete calculation for single filer."""
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(75000),
            num_children=0,
            use_standard_deduction=True,
        )

        result = test_calculator.calculate_taxes(request)

        # Verify response structure
        assert result.gross_income == Decimal(75000)
        assert result.adjusted_gross_income == Decimal(75000)
        assert result.taxable_income > 0
        assert result.federal_tax_owed > 0
        assert result.total_tax_liability > 0

        # Taxable income should be gross - standard deduction ($14,600)
        assert result.taxable_income == Decimal(60400)

    def test_married_with_children(self, test_calculator):
        """Test calculation with child tax credits."""
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            gross_income=Decimal(100000),
            num_children=2,
            use_standard_deduction=True,
        )

        result = test_calculator.calculate_taxes(request)

        # Should have child tax credits
        assert result.child_tax_credits > 0
        # 2 children * $2,000 = $4,000
        assert result.child_tax_credits == Decimal(4000)

        # Credits should reduce total tax
        assert result.total_tax_liability < result.federal_tax_owed + result.child_tax_credits

    def test_itemized_deductions(self, test_calculator):
        """Test with itemized deductions."""
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(80000),
            num_children=0,
            use_standard_deduction=False,
            itemized_deduction_amount=Decimal(25000),
        )

        result = test_calculator.calculate_taxes(request)

        # Should use itemized deduction
        assert result.deduction_type == "Itemized Deduction"
        assert result.deduction_amount == Decimal(25000)

        # Taxable income should be gross - itemized ($25k)
        assert result.taxable_income == Decimal(55000)


class TestTaxCalculatorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_income_at_bracket_boundary(self, test_calculator):
        """Test income exactly at first bracket boundary.

        $14,600 is the standard deduction for single in 2024.
        """
        # Income at standard deduction means small taxable amount
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(15000),
            num_children=0,
        )

        result = test_calculator.calculate_taxes(request)

        # Should have small taxable income ($15,000 - $14,600 = $400)
        assert result.taxable_income == Decimal(400)
        # Tax on $400 at 10% = $40
        assert result.federal_tax_owed == Decimal("40.00")

    def test_very_high_income(self, test_calculator):
        """Test very high income in top bracket.

        With IRS 2024 brackets, $500k should be in 35% bracket for single filers.
        """
        request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(500000),
            num_children=0,
        )

        result = test_calculator.calculate_taxes(request)

        # Should be in 35% bracket (Single: $243,726-$609,350)
        assert result.marginal_tax_rate == Decimal("35.00")

        # Should have substantial tax liability
        assert result.federal_tax_owed > Decimal(100000)

    def test_pension_deduction(self, test_calculator):
        """Test with pension SBP deduction."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(50000),
            retirement_pretax_deductions=Decimal(5000),
            num_children=0,
        )

        result = test_calculator.calculate_taxes(request)

        # AGI should be reduced by pension deduction
        assert result.adjusted_gross_income == Decimal(45000)
        assert result.retirement_pretax_deductions == Decimal(5000)

    def test_va_disability_tracking(self, test_calculator):
        """Test non-taxable benefit income tracking (non-taxable)."""
        request = TaxCalculationRequest(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            gross_income=Decimal(50000),
            non_taxable_income=Decimal(20000),
            num_children=0,
        )

        result = test_calculator.calculate_taxes(request)

        # Total household income includes VA
        assert result.total_household_income == Decimal(70000)

        # But VA doesn't affect AGI or taxable income
        assert result.adjusted_gross_income == Decimal(50000)
