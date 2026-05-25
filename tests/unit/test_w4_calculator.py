"""Unit tests for W-4 optimizer."""

from datetime import date
from decimal import Decimal

import pytest
from fixtures.w4_scenarios import get_single_job_scenario, get_two_job_scenario

from taxtracker.models.database import Employer, NonTaxableIncome, Paycheck, Retirement1099R
from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.data_loader import load_fica_limits_model, load_tax_brackets_model
from taxtracker.services.tax_calculator import TaxCalculator
from taxtracker.services.w4_calculator import _compute_irs_formula_ppc, optimize_midyear_from_db, optimize_w4

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
        """When overpaying, Step 4c must be $0 and Step 4b is the IRS lever to reduce withholding.

        The single_job fixture has a $5,000 annual pre-tax deduction (e.g., 401k). Because the
        IRS formula operates on gross pay (before pre-tax deductions), but tax liability is
        computed on taxable wages (after pre-tax deductions), the IRS formula would over-withhold
        by the tax effect of the pre-tax deduction. Step 4b corrects this by declaring the
        pre-tax deduction as an extra deduction — reducing the formula's effective income to match.
        """
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
        # Step 4c must be $0 — it can't be negative; Step 4b is the IRS lever for reduction
        assert rec.step4c_extra_withholding == Decimal(0)
        # Step 4b accounts for the $5,000 pre-tax deduction (IRS formula uses gross, not taxable wages)
        assert rec.step4b_deductions > Decimal(0)
        assert "$" in rec.step4b_explanation

    def test_remaining_pay_periods_divides_correctly(self, test_calculator: TaxCalculator) -> None:
        """remaining_pay_periods should override paychecks_per_year for per-paycheck adjustment."""
        job = [{"employer": "Mid Co", "annual_gross": 100000, "paychecks_per_year": 20}]
        # Overpaying — needs reduction
        result_remaining = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(50000),
            remaining_pay_periods=10,
        )
        result_full = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(50000),
        )

        # With remaining=10 out of 20, per-paycheck adjustment should be double the full-year version
        adj_remaining = abs(result_remaining.adjustment_per_paycheck["Mid Co"])
        adj_full = abs(result_full.adjustment_per_paycheck["Mid Co"])
        assert abs(adj_remaining - adj_full * 2) < Decimal("0.01")

    def test_remaining_pay_periods_step4b_scaled(self, test_calculator: TaxCalculator) -> None:
        """Step 4b for reduction should be scaled up when W-4 applies only to remaining periods."""
        job = [{"employer": "Mid Co", "annual_gross": 100000, "paychecks_per_year": 20}]
        result_remaining = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(50000),
            remaining_pay_periods=10,
        )
        result_full = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=job,
            pension_taxable=Decimal(0),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(50000),
        )

        rec_remaining = result_remaining.w4_recommendations[0]
        rec_full = result_full.w4_recommendations[0]
        # Mid-year Step 4b should be larger than full-year (scaled up because fewer paychecks apply)
        assert rec_remaining.step4b_deductions > rec_full.step4b_deductions


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
                source_type="Non-taxable benefit",
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


class TestStep4bIRSFormulaRoundTrip:
    """Verify that the step4b reduction recommendation round-trips correctly through the IRS formula.

    These tests guard against the regression where _compute_step4b_for_reduction computed
    the deduction amount against actual withholding history instead of the IRS formula baseline,
    producing a wildly inflated step4b that barely changed per-paycheck withholding.

    The round-trip assertion: feeding rec.step4b_deductions back into the IRS Pub 15-T formula
    simulator (_compute_irs_formula_ppc) must produce the target per-paycheck amount.
    """

    @pytest.fixture
    def tax_calculator_2026(self) -> TaxCalculator:
        """TaxCalculator loaded with 2026 IRS data."""
        return TaxCalculator(
            tax_year=2026,
            tax_brackets=load_tax_brackets_model(2026),
            fica_limits=load_fica_limits_model(2026),
        )

    def _expected_ppc(
        self,
        current_federal_withholding: Decimal,
        paychecks_per_year: int,
        remaining: int,
        target_withholding: Decimal,
    ) -> Decimal:
        """Compute the target per-paycheck amount the IRS formula must produce.

        For mid-year: the formula runs for `remaining` more paychecks. YTD withholding
        (estimated at the current projected rate) is already locked in.
        """
        current_ppc = current_federal_withholding / Decimal(paychecks_per_year)
        ytd_paychecks = paychecks_per_year - remaining
        ytd_withholding = current_ppc * Decimal(ytd_paychecks)
        remaining_needed = target_withholding - ytd_withholding
        return remaining_needed / Decimal(remaining)

    def test_step4b_roundtrip_midyear_single_with_pension(self, test_calculator: TaxCalculator) -> None:
        """Mid-year, single, W-2 + pension: step4b must produce the exact target per-paycheck.

        Scenario: 10 paychecks left out of 26, single, $60k W-2 + $20k pension, overpaying.
        The IRS formula baseline (with pension in step4a) is above target_ppc because the
        per-paycheck target is set to recover over just 10 remaining periods.
        """
        job = [{"employer": "Acme Corp", "annual_gross": 60000, "paychecks_per_year": 26}]
        current_federal_withholding = Decimal(15000)
        remaining = 10
        paychecks_per_year = 26
        pension_taxable = Decimal(20000)

        result = optimize_w4(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_jobs=job,
            pension_taxable=pension_taxable,
            va_disability=Decimal(0),
            current_federal_withholding=current_federal_withholding,
            remaining_pay_periods=remaining,
        )

        rec = result.w4_recommendations[0]
        # step4b must be non-zero: the IRS formula baseline (which includes pension in step4a)
        # produces more per-paycheck than needed since we're catching up over fewer periods
        assert rec.step4b_deductions > Decimal(0), "Expected non-zero step4b for mid-year overpaying with pension"

        # Round-trip: feed step4b back through IRS formula and verify it produces the target ppc
        brackets = test_calculator.tax_brackets.brackets_for_status(FilingStatus.SINGLE)
        std_ded = test_calculator.tax_brackets.standard_deductions.amounts[FilingStatus.SINGLE]
        gross_per_paycheck = Decimal(60000) / Decimal(paychecks_per_year)

        verify_ppc = _compute_irs_formula_ppc(
            gross_per_paycheck=gross_per_paycheck,
            periods=paychecks_per_year,
            step3_amount=rec.step3_amount,
            step4a_amount=rec.step4a_other_income,
            step4b_amount=rec.step4b_deductions,
            std_ded=std_ded,
            brackets=brackets,
        )

        expected_ppc = self._expected_ppc(
            current_federal_withholding, paychecks_per_year, remaining, result.target_total_withholding
        )
        assert abs(verify_ppc - expected_ppc) < Decimal("0.10"), (
            f"IRS formula produced {verify_ppc:.4f}/paycheck but expected {expected_ppc:.4f}; "
            f"step4b={rec.step4b_deductions}"
        )

    def test_step4b_roundtrip_mfj_2026_reported_bug(self, tax_calculator_2026: TaxCalculator) -> None:
        """MFJ 2026 mid-year: the original reported bug scenario must produce correct step4b.

        The original bug computed step4b against ACTUAL withholding history ($2,047/paycheck)
        instead of the IRS formula BASELINE ($1,267/paycheck), producing a wildly inflated
        step4b (~$127,726) that caused the formula to withhold ~$59/paycheck instead of ~$877.

        With the fix, step4b is derived by inverting the IRS formula so it produces exactly
        the required target_ppc, giving ~$42,565 and ~$877/paycheck.

        Inputs from the curl report (projected annual from YTD actuals + override):
          - MFJ, semimonthly (24 pay periods), $208,999.92/year projected
          - 2 children, $29,482.32 pension, remaining=16 out of 24
          - Current projected annual withholding: $49,134.66
          - Expected total: ~$30,406 (target refund = $0)
        """
        job = [
            {
                "employer": "Yurts",
                "annual_gross": 208999.92,  # YTD actuals + override, from curl report
                "paychecks_per_year": 24,
            }
        ]
        current_federal_withholding = Decimal("49134.66")
        remaining = 16
        paychecks_per_year = 24
        pension_taxable = Decimal("29482.32")
        num_children = 2

        result = optimize_w4(
            tax_calculator=tax_calculator_2026,
            year=2026,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=num_children,
            w2_jobs=job,
            pension_taxable=pension_taxable,
            va_disability=Decimal(0),
            current_federal_withholding=current_federal_withholding,
            remaining_pay_periods=remaining,
        )

        rec = result.w4_recommendations[0]

        # step4b must be non-zero and dramatically smaller than the old buggy ~$127,726
        assert rec.step4b_deductions > Decimal(0), "Expected non-zero step4b for mid-year overpaying with pension"
        assert rec.step4b_deductions < Decimal(100000), (
            f"step4b={rec.step4b_deductions:.0f} exceeds $100k threshold; old buggy algorithm produced ~$127,726"
        )

        # Round-trip: verify the recommended step4b produces the correct per-paycheck withholding
        brackets = tax_calculator_2026.tax_brackets.brackets_for_status(FilingStatus.MARRIED_FILING_JOINTLY)
        std_ded = tax_calculator_2026.tax_brackets.standard_deductions.amounts[FilingStatus.MARRIED_FILING_JOINTLY]
        gross_per_paycheck = Decimal("208999.92") / Decimal(paychecks_per_year)

        verify_ppc = _compute_irs_formula_ppc(
            gross_per_paycheck=gross_per_paycheck,
            periods=paychecks_per_year,
            step3_amount=rec.step3_amount,
            step4a_amount=rec.step4a_other_income,
            step4b_amount=rec.step4b_deductions,
            std_ded=std_ded,
            brackets=brackets,
        )

        expected_ppc = self._expected_ppc(
            current_federal_withholding, paychecks_per_year, remaining, result.target_total_withholding
        )
        assert abs(verify_ppc - expected_ppc) < Decimal("0.10"), (
            f"IRS formula produced {verify_ppc:.4f}/paycheck but expected {expected_ppc:.4f}; "
            f"step4b={rec.step4b_deductions:.2f} (old buggy value was ~$127,726)"
        )

        # Verify total annual withholding round-trip: ytd + remaining * ppc ~= target
        current_ppc = current_federal_withholding / Decimal(paychecks_per_year)
        ytd_withholding = current_ppc * Decimal(paychecks_per_year - remaining)
        total_projected = ytd_withholding + verify_ppc * Decimal(remaining)
        assert abs(total_projected - result.target_total_withholding) < Decimal("1.00"), (
            f"Total projected withholding {total_projected:.2f} does not match "
            f"target {result.target_total_withholding:.2f}"
        )
