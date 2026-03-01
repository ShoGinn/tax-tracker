"""IRS calculation verification tests — end-to-end tax calculation correctness.

Each test includes a full step-by-step audit trail showing the hand computation
so reviewers can independently verify the expected values.

These tests use the REAL data files (not mocks) to verify the full pipeline:
  data file -> TaxBrackets model -> TaxCalculator -> TaxCalculationResponse

Sources:
  2025 brackets: https://www.irs.gov/filing/federal-income-tax-rates-and-brackets
  OBBB standard deductions: https://www.irs.gov/newsroom/one-big-beautiful-bill-act-tax-deductions-for-working-americans-and-seniors
  OBBB CTC: https://www.irs.gov/newsroom/one-big-beautiful-bill-provisions-families
  FICA: https://www.ssa.gov/oact/cola/cbbdet.html
"""

from decimal import Decimal

import pytest

from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest
from taxtracker.services.data_loader import load_fica_limits_model, load_tax_brackets_model
from taxtracker.services.tax_calculator import TaxCalculator

pytestmark = pytest.mark.unit


@pytest.fixture
def calc_2025() -> TaxCalculator:
    """TaxCalculator loaded from real 2025 data files."""
    return TaxCalculator(
        2025,
        tax_brackets=load_tax_brackets_model(2025),
        fica_limits=load_fica_limits_model(2025),
    )


@pytest.fixture
def calc_2026() -> TaxCalculator:
    """TaxCalculator loaded from real 2026 data files."""
    return TaxCalculator(
        2026,
        tax_brackets=load_tax_brackets_model(2026),
        fica_limits=load_fica_limits_model(2026),
    )


class TestFederalTax2025:
    """Federal income tax calculations for 2025."""

    def test_single_50k_standard_deduction(self, calc_2025: TaxCalculator) -> None:
        """Single filer, $50k gross, standard deduction.

        Hand computation:
          Gross income:     $50,000
          Standard deduction: -$15,750  (2025 Single, OBBB Act)
          Taxable income:   $34,250

          10% on first $11,925                        = $1,192.50
          12% on ($34,250 - $11,925) = $22,325        = $2,679.00
          Total federal tax:                          = $3,871.50
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(50000),
            filing_status=FilingStatus.SINGLE,
            tax_year=2025,
        ))

        assert result.taxable_income == Decimal(34250)
        assert result.federal_tax_owed == Decimal("3871.50")
        assert result.marginal_tax_rate == Decimal("12.0")

    def test_mfj_120k_with_2_children(self, calc_2025: TaxCalculator) -> None:
        """MFJ, $120k gross, 2 children, standard deduction.

        Hand computation:
          Gross income:       $120,000
          Standard deduction: -$31,500  (2025 MFJ, OBBB Act)
          Taxable income:     $88,500

          10% on first $23,850                        = $2,385.00
          12% on ($88,500 - $23,850) = $64,650        = $7,758.00
          Federal tax before credits:                 = $10,143.00

          CTC: 2 children x $2,200 (OBBB Act)        = $4,400.00
          Federal tax after credits:                  = $5,743.00
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(120000),
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=2,
            tax_year=2025,
        ))

        assert result.taxable_income == Decimal(88500)
        assert result.federal_tax_owed == Decimal("10143.00")
        assert result.child_tax_credits == Decimal(4400)
        assert result.total_tax_liability == Decimal("5743.00")

    def test_high_earner_300k_single(self, calc_2025: TaxCalculator) -> None:
        """Single filer, $300k — spans through 24% bracket.

        Hand computation:
          Gross income:       $300,000
          Standard deduction: -$15,750
          Taxable income:     $284,250

          10% on $11,925                              = $1,192.50
          12% on ($48,475 - $11,925) = $36,550        = $4,386.00
          22% on ($103,350 - $48,475) = $54,875       = $12,072.50
          24% on ($197,300 - $103,350) = $93,950      = $22,548.00
          32% on ($250,525 - $197,300) = $53,225      = $17,032.00
          35% on ($284,250 - $250,525) = $33,725      = $11,803.75
          Total federal tax:                          = $69,034.75
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(300000),
            filing_status=FilingStatus.SINGLE,
            tax_year=2025,
        ))

        assert result.taxable_income == Decimal(284250)
        assert result.federal_tax_owed == Decimal("69034.75")
        assert result.marginal_tax_rate == Decimal("35.0")

    def test_mfj_250k_multiple_brackets(self, calc_2025: TaxCalculator) -> None:
        """MFJ $250k — verify impact of corrected 12% bracket ($96,950).

        Hand computation:
          Gross income:       $250,000
          Standard deduction: -$31,500
          Taxable income:     $218,500

          10% on $23,850                              = $2,385.00
          12% on ($96,950 - $23,850) = $73,100        = $8,772.00
          22% on ($206,700 - $96,950) = $109,750      = $24,145.00
          24% on ($218,500 - $206,700) = $11,800      = $2,832.00
          Total federal tax:                          = $38,134.00
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(250000),
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            tax_year=2025,
        ))

        assert result.taxable_income == Decimal(218500)
        assert result.federal_tax_owed == Decimal("38134.00")
        assert result.marginal_tax_rate == Decimal("24.0")


class TestFICACalculation2025:
    """FICA calculation correctness for 2025."""

    def test_fica_below_ss_wage_base(self, calc_2025: TaxCalculator) -> None:
        """$100k wages — below SS wage base, no additional Medicare.

        Hand computation:
          SS:       $100,000 * 0.062   = $6,200.00
          Medicare: $100,000 * 0.0145  = $1,450.00
          Add'l Medicare:              = $0.00 (under $200k threshold)
          Total FICA:                  = $7,650.00
        """
        fica = calc_2025.calculate_fica(Decimal(100000), FilingStatus.SINGLE)

        assert fica["social_security_tax"] == Decimal("6200.00")
        assert fica["medicare_tax"] == Decimal("1450.00")
        assert fica["additional_medicare_tax"] == Decimal(0)
        assert fica["total_fica"] == Decimal("7650.00")

    def test_fica_at_ss_wage_base_boundary(self, calc_2025: TaxCalculator) -> None:
        """$176,100 wages — exactly at SS wage base (2025).

        Hand computation:
          SS:       $176,100 * 0.062   = $10,918.20 (max)
          Medicare: $176,100 * 0.0145  = $2,553.45
          Total FICA:                  = $13,471.65
        """
        fica = calc_2025.calculate_fica(Decimal(176100), FilingStatus.SINGLE)

        assert fica["social_security_tax"] == Decimal("10918.20")
        assert fica["ss_taxable_wages"] == Decimal(176100)
        assert fica["medicare_tax"] == Decimal("2553.45")
        assert fica["total_fica"] == Decimal("13471.65")

    def test_fica_above_ss_wage_base(self, calc_2025: TaxCalculator) -> None:
        """$200k wages — SS capped, no additional Medicare yet.

        Hand computation:
          SS:       $176,100 * 0.062   = $10,918.20 (capped)
          Medicare: $200,000 * 0.0145  = $2,900.00
          Add'l Medicare:              = $0.00 (at threshold, not over)
          Total FICA:                  = $13,818.20
        """
        fica = calc_2025.calculate_fica(Decimal(200000), FilingStatus.SINGLE)

        assert fica["social_security_tax"] == Decimal("10918.20")
        assert fica["medicare_tax"] == Decimal("2900.00")
        assert fica["additional_medicare_tax"] == Decimal(0)
        assert fica["total_fica"] == Decimal("13818.20")

    def test_additional_medicare_kicks_in(self, calc_2025: TaxCalculator) -> None:
        """$300k single wages — additional Medicare on excess over $200k.

        Hand computation:
          SS:       $176,100 * 0.062           = $10,918.20 (capped)
          Medicare: $300,000 * 0.0145          = $4,350.00
          Add'l Medicare: ($300,000 - $200,000) * 0.009 = $900.00
          Total FICA:                          = $16,168.20
        """
        fica = calc_2025.calculate_fica(Decimal(300000), FilingStatus.SINGLE)

        assert fica["social_security_tax"] == Decimal("10918.20")
        assert fica["medicare_tax"] == Decimal("4350.00")
        assert fica["additional_medicare_tax"] == Decimal("900.00")
        assert fica["total_fica"] == Decimal("16168.20")

    def test_additional_medicare_mfj_threshold(self, calc_2025: TaxCalculator) -> None:
        """$300k MFJ wages — additional Medicare threshold is $250k for MFJ.

        Hand computation:
          Add'l Medicare: ($300,000 - $250,000) * 0.009 = $450.00
        """
        fica = calc_2025.calculate_fica(Decimal(300000), FilingStatus.MARRIED_FILING_JOINTLY)

        assert fica["additional_medicare_tax"] == Decimal("450.00")


class TestCombinedScenarios2025:
    """Full tax calculation scenarios combining income tax + FICA."""

    def test_military_retiree(self, calc_2025: TaxCalculator) -> None:
        """W-2 job + military pension + VA disability.

        Hand computation:
          W-2 gross:  $100,000
          Pension:    $30,000
          VA (non-taxable): $20,000

          AGI = $100,000 + $30,000 = $130,000
          Standard deduction MFJ: -$31,500
          Taxable income: $98,500

          10% on $23,850                              = $2,385.00
          12% on ($96,950 - $23,850) = $73,100        = $8,772.00
          22% on ($98,500 - $96,950) = $1,550         = $341.00
          Federal tax before credits:                 = $11,498.00

          CTC: 2 x $2,200                            = $4,400.00
          Federal tax liability:                      = $7,098.00

          FICA (on W-2 only):
          SS:       $100,000 * 0.062  = $6,200.00
          Medicare: $100,000 * 0.0145 = $1,450.00
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(100000),
            pension_gross_income=Decimal(30000),
            non_taxable_income=Decimal(20000),
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=2,
            tax_year=2025,
        ))

        assert result.adjusted_gross_income == Decimal(130000)
        assert result.taxable_income == Decimal(98500)
        assert result.federal_tax_owed == Decimal("11498.00")
        assert result.child_tax_credits == Decimal(4400)
        assert result.total_tax_liability == Decimal("7098.00")
        # FICA only on W-2 wages
        assert result.fica_taxes["social_security_tax"] == Decimal("6200.00")
        assert result.fica_taxes["medicare_tax"] == Decimal("1450.00")
        # VA disability tracked but not taxed
        assert result.total_household_income == Decimal(150000)

    def test_pension_with_pretax_deductions(self, calc_2025: TaxCalculator) -> None:
        """Pension with SBP deduction reduces AGI.

        Hand computation:
          Pension gross:    $45,000
          SBP deduction:    -$3,000
          AGI:              $42,000
          Standard deduction MFJ: -$31,500
          Taxable income:   $10,500

          10% on $10,500 = $1,050.00
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            pension_gross_income=Decimal(45000),
            retirement_pretax_deductions=Decimal(3000),
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            tax_year=2025,
        ))

        assert result.adjusted_gross_income == Decimal(42000)
        assert result.taxable_income == Decimal(10500)
        assert result.federal_tax_owed == Decimal("1050.00")
        # No W-2 wages => no FICA
        assert result.fica_taxes["total_fica"] == Decimal(0)

    def test_itemized_deductions(self, calc_2025: TaxCalculator) -> None:
        """Single filer with itemized deductions exceeding standard.

        Hand computation:
          Gross income:       $80,000
          Itemized deduction: -$20,000 (> $15,750 standard)
          Taxable income:     $60,000

          10% on $11,925                              = $1,192.50
          12% on ($48,475 - $11,925) = $36,550        = $4,386.00
          22% on ($60,000 - $48,475) = $11,525        = $2,535.50
          Total federal tax:                          = $8,114.00
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(80000),
            filing_status=FilingStatus.SINGLE,
            use_standard_deduction=False,
            itemized_deduction_amount=Decimal(20000),
            tax_year=2025,
        ))

        assert result.deduction_type == "Itemized Deduction"
        assert result.deduction_amount == Decimal(20000)
        assert result.taxable_income == Decimal(60000)
        assert result.federal_tax_owed == Decimal("8114.00")


class TestEdgeCases:
    """Edge case calculations."""

    def test_income_equals_standard_deduction(self, calc_2025: TaxCalculator) -> None:
        """Income exactly equal to standard deduction => zero tax."""
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(15750),
            filing_status=FilingStatus.SINGLE,
            tax_year=2025,
        ))

        assert result.taxable_income == Decimal(0)
        assert result.federal_tax_owed == Decimal(0)

    def test_ctc_cannot_go_below_zero(self, calc_2025: TaxCalculator) -> None:
        """CTC exceeds tax liability — liability floors at $0.

        Gross: $40,000 MFJ, 3 children
        Taxable: $40,000 - $31,500 = $8,500
        Tax: 10% of $8,500 = $850.00
        CTC: 3 x $2,200 = $6,600
        Liability: max($0, $850 - $6,600) = $0
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(40000),
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=3,
            tax_year=2025,
        ))

        assert result.federal_tax_owed == Decimal("850.00")
        assert result.child_tax_credits == Decimal(6600)
        assert result.total_tax_liability == Decimal(0)

    def test_hoh_bracket_thresholds(self, calc_2025: TaxCalculator) -> None:
        """Head of household with income spanning 12% bracket.

        Gross: $75,000 HoH, 1 child
        Standard deduction HoH: $23,625
        Taxable: $51,375

        10% on $17,000                               = $1,700.00
        12% on ($51,375 - $17,000) = $34,375         = $4,125.00
        Federal tax before credits:                   = $5,825.00
        CTC: 1 x $2,200                              = $2,200.00
        Federal tax after credits:                    = $3,625.00
        """
        result = calc_2025.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(75000),
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            num_children=1,
            tax_year=2025,
        ))

        assert result.taxable_income == Decimal(51375)
        assert result.federal_tax_owed == Decimal("5825.00")
        assert result.total_tax_liability == Decimal("3625.00")


class TestFederalTax2026:
    """Cross-year verification using 2026 data."""

    def test_single_50k_2026(self, calc_2026: TaxCalculator) -> None:
        """Same scenario as 2025 but with 2026 brackets.

        Hand computation:
          Gross: $50,000
          Standard deduction: -$16,100 (2026 Single)
          Taxable income: $33,900

          10% on $12,400                              = $1,240.00
          12% on ($33,900 - $12,400) = $21,500        = $2,580.00
          Total federal tax:                          = $3,820.00
        """
        result = calc_2026.calculate_taxes(TaxCalculationRequest(
            w2_gross_income=Decimal(50000),
            filing_status=FilingStatus.SINGLE,
            tax_year=2026,
        ))

        assert result.taxable_income == Decimal(33900)
        assert result.federal_tax_owed == Decimal("3820.00")

    def test_fica_2026_ss_cap(self, calc_2026: TaxCalculator) -> None:
        """2026 SS wage base is $184,500.

        $250k wages:
          SS: $184,500 * 0.062 = $11,439.00 (capped)
        """
        fica = calc_2026.calculate_fica(Decimal(250000), FilingStatus.SINGLE)

        assert fica["social_security_tax"] == Decimal("11439.00")
        assert fica["ss_taxable_wages"] == Decimal(184500)
