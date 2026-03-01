"""Unit tests for W-4 withholding calculator."""

from decimal import Decimal

import pytest

from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.w4_withholding import (
    calculate_withholding_per_paycheck,
    estimate_annual_withholding_from_w4,
)

pytestmark = pytest.mark.unit


@pytest.mark.usefixtures("mock_tax_data_dependency")
class TestWithholdingCalculation:
    """Tests for calculate_withholding_per_paycheck."""

    def test_basic_single_biweekly(self) -> None:
        """Basic withholding for single filer, biweekly pay."""
        result = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        assert result["withholding_per_paycheck"] > 0
        assert result["annual_withholding"] > 0
        assert "breakdown" in result
        # Annual = per-paycheck * 26
        assert abs(result["annual_withholding"] - result["withholding_per_paycheck"] * 26) < 0.01

    def test_married_filing_jointly(self) -> None:
        """Married filing jointly should have lower withholding than single."""
        single = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        married = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        # MFJ has larger standard deduction -> lower tax
        assert married["withholding_per_paycheck"] < single["withholding_per_paycheck"]

    def test_step2_checkbox_halves_gross(self) -> None:
        """Step 2 checkbox divides gross by 2 for withholding calculation."""
        without_checkbox = calculate_withholding_per_paycheck(
            gross_pay=Decimal(4000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        with_checkbox = calculate_withholding_per_paycheck(
            gross_pay=Decimal(4000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=True,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        # Halving gross should reduce withholding
        assert with_checkbox["withholding_per_paycheck"] < without_checkbox["withholding_per_paycheck"]
        # Verify breakdown shows adjusted gross
        assert with_checkbox["breakdown"]["adjusted_gross_per_paycheck"] == 2000.0

    def test_all_pay_frequencies(self) -> None:
        """All pay frequencies should produce valid results."""
        for frequency in ["weekly", "biweekly", "semimonthly", "monthly"]:
            result = calculate_withholding_per_paycheck(
                gross_pay=Decimal(3000),
                pay_frequency=frequency,
                filing_status=FilingStatus.SINGLE,
                multiple_jobs_checkbox=False,
                dependents_amount=Decimal(0),
                other_income_annual=Decimal(0),
                deductions_annual=Decimal(0),
                extra_withholding=Decimal(0),
                year=2024,
            )
            assert result["withholding_per_paycheck"] >= 0, f"Failed for {frequency}"

    def test_invalid_pay_frequency(self) -> None:
        """Invalid pay frequency should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid pay_frequency"):
            calculate_withholding_per_paycheck(
                gross_pay=Decimal(3000),
                pay_frequency="quarterly",
                filing_status=FilingStatus.SINGLE,
                multiple_jobs_checkbox=False,
                dependents_amount=Decimal(0),
                other_income_annual=Decimal(0),
                deductions_annual=Decimal(0),
                extra_withholding=Decimal(0),
                year=2024,
            )

    def test_with_dependents(self) -> None:
        """Dependents reduce withholding (Step 3 credit)."""
        no_deps = calculate_withholding_per_paycheck(
            gross_pay=Decimal(4000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        with_deps = calculate_withholding_per_paycheck(
            gross_pay=Decimal(4000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(4000),  # 2 children x $2000
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        assert with_deps["withholding_per_paycheck"] < no_deps["withholding_per_paycheck"]

    def test_with_other_income(self) -> None:
        """Other income (Step 4a) increases withholding."""
        base = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        with_other = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(20000),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        assert with_other["withholding_per_paycheck"] > base["withholding_per_paycheck"]

    def test_extra_withholding(self) -> None:
        """Extra withholding (Step 4c) is added per paycheck."""
        base = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        with_extra = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(200),
            year=2024,
        )

        # Extra withholding should increase by exactly $200
        assert abs(
            with_extra["withholding_per_paycheck"] - base["withholding_per_paycheck"] - 200.0
        ) < 0.01

    def test_extra_deductions_reduce_withholding(self) -> None:
        """Extra deductions (Step 4b) reduce withholding."""
        base = calculate_withholding_per_paycheck(
            gross_pay=Decimal(5000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        with_deductions = calculate_withholding_per_paycheck(
            gross_pay=Decimal(5000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(10000),
            extra_withholding=Decimal(0),
            year=2024,
        )

        assert with_deductions["withholding_per_paycheck"] < base["withholding_per_paycheck"]

    def test_high_income_hits_top_bracket(self) -> None:
        """Very high income should reach the top (unbounded) bracket."""
        result = calculate_withholding_per_paycheck(
            gross_pay=Decimal(30000),  # $780k annually biweekly
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        # Should have significant withholding
        assert result["withholding_per_paycheck"] > 5000
        assert result["annual_withholding"] > 100000

    def test_zero_income(self) -> None:
        """Zero gross pay should result in zero withholding."""
        result = calculate_withholding_per_paycheck(
            gross_pay=Decimal(0),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        assert result["withholding_per_paycheck"] == 0
        assert result["annual_withholding"] == 0

    def test_breakdown_fields(self) -> None:
        """Breakdown should contain all expected audit trail fields."""
        result = calculate_withholding_per_paycheck(
            gross_pay=Decimal(3000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        breakdown = result["breakdown"]
        expected_fields = [
            "gross_pay_per_paycheck",
            "adjusted_gross_per_paycheck",
            "annual_wages",
            "standard_deduction",
            "total_deductions",
            "annual_taxable",
            "annual_tax_before_credits",
            "dependent_credits",
            "annual_tax_after_credits",
            "base_withholding_per_paycheck",
            "extra_withholding_per_paycheck",
            "final_withholding_per_paycheck",
        ]
        for field in expected_fields:
            assert field in breakdown, f"Missing breakdown field: {field}"


@pytest.mark.usefixtures("mock_tax_data_dependency")
class TestEstimateAnnualWithholding:
    """Tests for estimate_annual_withholding_from_w4 wrapper."""

    def test_basic_estimation(self) -> None:
        """Wrapper should return Decimal annual withholding."""
        result = estimate_annual_withholding_from_w4(
            annual_gross=Decimal(78000),
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            w4_step2_checkbox=False,
            w4_step3_dependents=Decimal(0),
            w4_step4a_other_income=Decimal(0),
            w4_step4b_deductions=Decimal(0),
            w4_step4c_extra=Decimal(0),
            year=2024,
        )

        assert isinstance(result, Decimal)
        assert result > 0

    def test_matches_per_paycheck_calculation(self) -> None:
        """Wrapper result should match manual per-paycheck * periods calculation."""
        annual_gross = Decimal(78000)
        per_paycheck = calculate_withholding_per_paycheck(
            gross_pay=annual_gross / 26,
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            multiple_jobs_checkbox=False,
            dependents_amount=Decimal(0),
            other_income_annual=Decimal(0),
            deductions_annual=Decimal(0),
            extra_withholding=Decimal(0),
            year=2024,
        )

        estimated = estimate_annual_withholding_from_w4(
            annual_gross=annual_gross,
            pay_frequency="biweekly",
            filing_status=FilingStatus.SINGLE,
            w4_step2_checkbox=False,
            w4_step3_dependents=Decimal(0),
            w4_step4a_other_income=Decimal(0),
            w4_step4b_deductions=Decimal(0),
            w4_step4c_extra=Decimal(0),
            year=2024,
        )

        expected = Decimal(str(per_paycheck["annual_withholding"]))
        assert estimated == expected

    def test_monthly_frequency(self) -> None:
        """Monthly frequency should work correctly."""
        result = estimate_annual_withholding_from_w4(
            annual_gross=Decimal(120000),
            pay_frequency="monthly",
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            w4_step2_checkbox=False,
            w4_step3_dependents=Decimal(4000),
            w4_step4a_other_income=Decimal(0),
            w4_step4b_deductions=Decimal(0),
            w4_step4c_extra=Decimal(0),
            year=2024,
        )

        assert isinstance(result, Decimal)
        assert result > 0
