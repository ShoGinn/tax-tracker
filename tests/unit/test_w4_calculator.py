"""Unit tests for W-4 optimizer."""

from datetime import date
from decimal import Decimal

import pytest
from fixtures.w4_scenarios import get_single_job_scenario, get_two_job_scenario

from taxtracker.models.database import Employer, NonTaxableIncome, Paycheck, Retirement1099R
from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.tax_calculator import TaxCalculator  # noqa: TC001
from taxtracker.services.w4_calculator import optimize_midyear_from_db, optimize_w4

pytestmark = pytest.mark.unit


@pytest.fixture
def single_job() -> list[dict]:
    """A single W-2 job for optimization."""
    return get_single_job_scenario()


@pytest.fixture
def two_jobs() -> list[dict]:
    """Two W-2 jobs for multi-job optimization."""
    return get_two_job_scenario()


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
        ctc_per_child = test_calculator.tax_brackets.child_tax_credit.amount_per_child

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
        assert rec.step3_amount == ctc_per_child * Decimal(2)

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
        expected_amount = f"${result.w4_recommendations[0].step4c_extra_withholding:,.2f}"
        assert any(expected_amount in note for note in result.notes)

    def test_overpaying_note_uses_adjustment_per_period(self, test_calculator: TaxCalculator, single_job: list) -> None:
        """Overpaying note should report reduction per period from adjustment math, not a fixed divisor."""
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

        expected_reduction = sum((abs(v) for v in result.adjustment_per_paycheck.values() if v < 0), Decimal(0))
        expected_amount = f"${expected_reduction:,.2f}"
        assert any(expected_amount in note for note in result.notes)

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


class TestMidYearOptimizeFromDB:
    """Tests for DB-backed mid-year optimization workflow."""

    async def test_extrapolates_remaining_income(self, async_db_session, test_calculator: TaxCalculator) -> None:
        """Should extrapolate remaining gross from YTD average when no override is provided."""
        employer = Employer(name="Acme", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add_all(
            [
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 1, 15),
                    gross_wages=Decimal(2000),
                    federal_withholding=Decimal(200),
                ),
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 1, 31),
                    gross_wages=Decimal(3000),
                    federal_withholding=Decimal(300),
                ),
            ]
        )
        await async_db_session.commit()

        result = await optimize_midyear_from_db(
            db=async_db_session,
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            remaining_pay_periods=2,
        )

        employer_summary = result["ytd_summary"]["employers"][0]
        # Avg gross is (2000 + 3000) / 2 = 2500; projected remaining = 2500 * 2 = 5000
        assert Decimal(employer_summary["projected_remaining_gross"]) == Decimal(5000)

    async def test_employer_override_replaces_extrapolation(
        self, async_db_session, test_calculator: TaxCalculator
    ) -> None:
        """Override should replace YTD-average extrapolation for the specified employer."""
        employer = Employer(name="Override Co", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add(
            Paycheck(
                employer_id=employer.id,
                pay_date=date(2024, 2, 15),
                gross_wages=Decimal(2500),
                federal_withholding=Decimal(200),
            )
        )
        await async_db_session.commit()

        result = await optimize_midyear_from_db(
            db=async_db_session,
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            remaining_pay_periods=3,
            employer_overrides={employer.id: Decimal(4000)},
        )

        employer_summary = result["ytd_summary"]["employers"][0]
        assert Decimal(employer_summary["projected_remaining_gross"]) == Decimal(12000)
        assert any("Used override" in note for note in result["assumptions"])

    async def test_requires_paychecks_for_year(self, async_db_session, test_calculator: TaxCalculator) -> None:
        """Should fail with clear error when no paychecks are available for the requested year."""
        async_db_session.add(
            Retirement1099R(
                pay_date=date(2024, 1, 1),
                gross_amount=Decimal(3000),
                federal_withholding=Decimal(300),
            )
        )
        await async_db_session.commit()

        with pytest.raises(ValueError, match="No paychecks found"):
            await optimize_midyear_from_db(
                db=async_db_session,
                tax_calculator=test_calculator,
                year=2024,
                filing_status=FilingStatus.SINGLE,
                remaining_pay_periods=2,
            )

    async def test_as_of_date_filters_ytd_records(self, async_db_session, test_calculator: TaxCalculator) -> None:
        """as_of_date should only include paycheck records up to that date."""
        employer = Employer(name="Cutoff Co", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add_all(
            [
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 1, 15),
                    gross_wages=Decimal(2000),
                    federal_withholding=Decimal(200),
                ),
                Paycheck(
                    employer_id=employer.id,
                    pay_date=date(2024, 3, 15),
                    gross_wages=Decimal(5000),
                    federal_withholding=Decimal(500),
                ),
            ]
        )
        await async_db_session.commit()

        result = await optimize_midyear_from_db(
            db=async_db_session,
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            remaining_pay_periods=2,
            as_of_date=date(2024, 2, 1),
        )

        employer_summary = result["ytd_summary"]["employers"][0]
        assert Decimal(employer_summary["ytd_gross"]) == Decimal(2000)
        assert result["ytd_summary"]["as_of_date"] == "2024-02-01"
        assert any("as_of_date cutoff" in note for note in result["assumptions"])

    async def test_split_remaining_periods_for_mixed_cadence(
        self,
        async_db_session,
        test_calculator: TaxCalculator,
    ) -> None:
        """W-2, pension, and non-taxable projections should honor separate remaining period counts."""
        employer = Employer(name="Mixed Cadence Co", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        async_db_session.add(
            Paycheck(
                employer_id=employer.id,
                pay_date=date(2024, 4, 15),
                gross_wages=Decimal(3000),
                federal_withholding=Decimal(300),
            )
        )
        async_db_session.add(
            Retirement1099R(
                pay_date=date(2024, 4, 1),
                gross_amount=Decimal(1000),
                federal_withholding=Decimal(100),
            )
        )
        async_db_session.add(
            NonTaxableIncome(
                pay_date=date(2024, 4, 1),
                amount=Decimal(500),
                source_type="VA Disability",
            )
        )
        await async_db_session.commit()

        result = await optimize_midyear_from_db(
            db=async_db_session,
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            remaining_pay_periods=10,
            remaining_pension_periods=5,
            remaining_non_taxable_periods=4,
        )

        assert result["ytd_summary"]["remaining_w2_pay_periods"] == 10
        assert result["ytd_summary"]["remaining_pension_periods"] == 5
        assert result["ytd_summary"]["remaining_non_taxable_periods"] == 4
        assert Decimal(result["projection_summary"]["projected_remaining_pension_taxable"]) == Decimal(5000)
        assert Decimal(result["projection_summary"]["projected_full_year_non_taxable_income"]) == Decimal(2500)
        assert result["optimization"].current_total_withholding == Decimal(
            result["projection_summary"]["projected_annual_total_withholding"]
        )
