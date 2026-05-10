"""Unit tests for W-4 optimizer."""

from decimal import Decimal

import pytest

from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.tax_calculator import TaxCalculator  # noqa: TC001
from taxtracker.services.w4_calculator import optimize_w4

pytestmark = pytest.mark.unit


@pytest.fixture
def single_job() -> list[dict]:
    """A single W-2 job for optimization."""
    return [
        {
            "employer": "Acme Corp",
            "annual_gross": 80000,
            "paychecks_per_year": 26,
            "annual_pretax_deductions": 5000,
        }
    ]


@pytest.fixture
def two_jobs() -> list[dict]:
    """Two W-2 jobs for multi-job optimization."""
    return [
        {
            "employer": "Primary Inc",
            "annual_gross": 100000,
            "paychecks_per_year": 26,
            "annual_pretax_deductions": 8000,
        },
        {
            "employer": "Side Co",
            "annual_gross": 40000,
            "paychecks_per_year": 24,
            "annual_pretax_deductions": 0,
        },
    ]


class TestOptimizeW4:
    """Tests for the optimize_w4 function."""

    def test_basic_single_job(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Basic single job optimization should return valid result."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(10000),
        )

        assert result.year == 2024
        assert result.filing_status == "single"
        assert result.total_w2_income == Decimal(80000)
        assert result.estimated_tax_liability > 0
        assert len(result.w4_recommendations) == 1
        assert result.w4_recommendations[0].employer_name == "Acme Corp"

    def test_target_refund(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Target refund should increase target withholding."""
        result_zero = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(10000),
            target_refund=Decimal(0),
        )

        result_refund = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(10000),
            target_refund=Decimal(2000),
        )

        assert result_refund.target_total_withholding > result_zero.target_total_withholding
        assert result_refund.target_total_withholding - result_zero.target_total_withholding == Decimal(2000)

    def test_with_children(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Children should add Step 3 dependents amount."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=2,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(10000),
        )

        rec = result.w4_recommendations[0]
        assert rec.step3_amount == Decimal(4000)  # 2 x $2000

    def test_with_pension(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Pension should appear in Step 4a on highest-paying job."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(25000),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(15000),
        )

        rec = result.w4_recommendations[0]
        assert rec.step4a_other_income == Decimal(25000)
        assert result.total_pension_income == Decimal(25000)

    def test_multiple_jobs_distribution(self, test_calculator: TaxCalculator, two_jobs: list) -> None:
        """Multiple jobs should distribute adjustments proportionally."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=two_jobs,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(15000),
        )

        assert len(result.w4_recommendations) == 2
        assert result.total_w2_income == Decimal(140000)

        # Only highest-paying job should claim dependents/pension
        side_rec = next(r for r in result.w4_recommendations if r.employer_name == "Side Co")
        assert side_rec.step4a_other_income == Decimal(0)

    def test_multiple_jobs_notes(self, test_calculator: TaxCalculator, two_jobs: list) -> None:
        """Multiple jobs should generate a note about Step 4."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=two_jobs,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(15000),
        )

        assert any("multiple jobs" in note.lower() for note in result.notes)

    def test_overpaying_notes(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """When overpaying, notes should indicate reducing withholding."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(50000),  # Way too much
        )

        assert result.current_refund_or_owed > 0
        assert any("overpaying" in note.lower() for note in result.notes)

    def test_underpaying_notes(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """When underpaying, notes should indicate increasing withholding."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(1000),  # Way too little
        )

        assert result.current_refund_or_owed < 0
        assert any("underpaying" in note.lower() for note in result.notes)

    def test_perfect_withholding_notes(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """When withholding is close to perfect, note should say so."""
        # First calculate tax liability to know what perfect withholding is
        result_probe = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(10000),
        )
        perfect_withholding = result_probe.estimated_tax_liability

        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=perfect_withholding,
        )

        assert any("perfect" in note.lower() or "close" in note.lower() for note in result.notes)

    def test_negative_adjustment_step4c(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """When overpaying, Step 4c should be 0 (can't negative-withhold)."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(50000),
        )

        rec = result.w4_recommendations[0]
        assert rec.step4c_extra_withholding == Decimal(0)
        assert "reduce" in rec.step4c_explanation.lower()


class TestW4OptimizationResultToDict:
    """Tests for W4OptimizationResult.to_dict() serialization."""

    def test_to_dict_structure(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """to_dict should produce correct nested structure."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(10000),
        )

        d = result.to_dict()

        assert d["year"] == 2024
        assert d["filing_status"] == "single"
        assert "income_summary" in d
        assert "tax_calculation" in d
        assert "current_situation" in d
        assert "w4_recommendations" in d
        assert "adjustment_summary" in d
        assert "notes" in d

    def test_to_dict_income_summary(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Income summary should contain all income types."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(20000),
            va_disability=Decimal(3000),
            current_federal_withholding=Decimal(10000),
        )

        d = result.to_dict()
        income = d["income_summary"]
        assert income["total_w2_income"] == 80000.0
        assert income["total_pension_income"] == 20000.0
        assert income["total_va_income"] == 3000.0

    def test_to_dict_current_situation_status(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Current situation should show OVERPAYING/UNDERPAYING/PERFECT."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(50000),
        )

        d = result.to_dict()
        assert d["current_situation"]["status"] == "OVERPAYING"

    def test_to_dict_recommendations_structure(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Each recommendation should have W-4 step structure."""
        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=single_job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(10000),
        )

        d = result.to_dict()
        rec = d["w4_recommendations"][0]

        assert rec["employer"] == "Acme Corp"
        assert "step_2_multiple_jobs" in rec
        assert "step_3_dependents" in rec
        assert "step_4a_other_income" in rec
        assert "step_4b_deductions" in rec
        assert "step_4c_extra_withholding" in rec
        assert "expected_results" in rec
