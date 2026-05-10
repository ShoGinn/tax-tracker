"""IRS data validation tests — assert data files match IRS-published values.

Every assertion includes an inline citation to the specific IRS source URL or
document section.  If a test fails, either the data file has a typo or the IRS
published updated values.

Primary sources:
  2025 brackets: IRS Rev. Proc. 2024-40 + OBBB Act (PL 119-21)
    https://www.irs.gov/filing/federal-income-tax-rates-and-brackets
  2025 standard deductions: OBBB Act Sec. 101
    https://www.irs.gov/newsroom/one-big-beautiful-bill-act-tax-deductions-for-working-americans-and-seniors
  2025 CTC: OBBB Act Sec. 1001
    https://www.irs.gov/newsroom/one-big-beautiful-bill-provisions-families
  2026 brackets: IRS Rev. Proc. 2025-32
    https://www.irs.gov/pub/irs-drop/rp-25-32.pdf
  FICA: SSA contribution base
    https://www.ssa.gov/oact/cola/cbbdet.html

Cross-reference: PSLmodels Tax-Calculator policy_current_law.json
  https://github.com/PSLmodels/Tax-Calculator/blob/master/taxcalc/policy_current_law.json
"""

from decimal import Decimal

import pytest

from taxtracker.services.data_loader import load_fica_limits_model, load_tax_brackets_model

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 2025 Tax Brackets
# ---------------------------------------------------------------------------
class TestTaxBrackets2025:
    """Validate 2025 tax bracket data against IRS.gov published values.

    Source: https://www.irs.gov/filing/federal-income-tax-rates-and-brackets
    Modified by OBBB Act (PL 119-21) for standard deductions and CTC.
    """

    @pytest.fixture(autouse=True)
    def _load_data(self) -> None:
        self.data = load_tax_brackets_model(2025)

    # -- Married Filing Jointly ------------------------------------------------
    # IRS.gov: MFJ brackets for 2025
    def test_mfj_10_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][0].threshold == Decimal(23850)

    def test_mfj_12_threshold(self) -> None:
        # IRS.gov brackets page: $96,950 (NOT $97,050 — confirmed against IRS.gov)
        assert self.data.tax_brackets["married_filing_jointly"][1].threshold == Decimal(96950)

    def test_mfj_22_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][2].threshold == Decimal(206700)

    def test_mfj_24_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][3].threshold == Decimal(394600)

    def test_mfj_32_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][4].threshold == Decimal(501050)

    def test_mfj_35_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][5].threshold == Decimal(751600)

    def test_mfj_37_no_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][6].threshold is None
        assert self.data.tax_brackets["married_filing_jointly"][6].rate == Decimal("0.37")

    # -- Single ----------------------------------------------------------------
    # IRS.gov: Single brackets for 2025
    def test_single_10_threshold(self) -> None:
        assert self.data.tax_brackets["single"][0].threshold == Decimal(11925)

    def test_single_12_threshold(self) -> None:
        assert self.data.tax_brackets["single"][1].threshold == Decimal(48475)

    def test_single_22_threshold(self) -> None:
        assert self.data.tax_brackets["single"][2].threshold == Decimal(103350)

    def test_single_24_threshold(self) -> None:
        assert self.data.tax_brackets["single"][3].threshold == Decimal(197300)

    def test_single_32_threshold(self) -> None:
        assert self.data.tax_brackets["single"][4].threshold == Decimal(250525)

    def test_single_35_threshold(self) -> None:
        assert self.data.tax_brackets["single"][5].threshold == Decimal(626350)

    def test_single_37_no_threshold(self) -> None:
        assert self.data.tax_brackets["single"][6].threshold is None

    # -- Married Filing Separately ---------------------------------------------
    # MFS matches Single for all brackets EXCEPT the 35% bracket
    def test_mfs_matches_single_except_35(self) -> None:
        single = self.data.tax_brackets["single"]
        mfs = self.data.tax_brackets["married_filing_separately"]
        for i in range(7):
            if single[i].rate == Decimal("0.35"):
                continue  # 35% bracket differs
            assert mfs[i].threshold == single[i].threshold, f"MFS bracket {i} ({mfs[i].rate}) should match Single"

    def test_mfs_35_threshold(self) -> None:
        # MFS 35% bracket is half of MFJ 35% ($751,600 / 2 = $375,800)
        assert self.data.tax_brackets["married_filing_separately"][5].threshold == Decimal(375800)

    # -- Head of Household -----------------------------------------------------
    # IRS.gov: HoH brackets for 2025
    def test_hoh_10_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][0].threshold == Decimal(17000)

    def test_hoh_12_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][1].threshold == Decimal(64850)

    def test_hoh_22_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][2].threshold == Decimal(103350)

    def test_hoh_24_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][3].threshold == Decimal(197300)

    def test_hoh_32_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][4].threshold == Decimal(250500)

    def test_hoh_35_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][5].threshold == Decimal(626350)

    # -- Standard Deductions ---------------------------------------------------
    # OBBB Act Sec. 101 — increased standard deductions for 2025
    # https://www.irs.gov/newsroom/one-big-beautiful-bill-act-tax-deductions-for-working-americans-and-seniors
    def test_standard_deduction_mfj(self) -> None:
        assert self.data.standard_deductions.amounts["married_filing_jointly"] == Decimal(31500)

    def test_standard_deduction_single(self) -> None:
        assert self.data.standard_deductions.amounts["single"] == Decimal(15750)

    def test_standard_deduction_mfs(self) -> None:
        assert self.data.standard_deductions.amounts["married_filing_separately"] == Decimal(15750)

    def test_standard_deduction_hoh(self) -> None:
        assert self.data.standard_deductions.amounts["head_of_household"] == Decimal(23625)

    # Age 65+ additional amounts (IRS Rev. Proc. 2024-40, Sec. 3.15)
    def test_age_65_plus_single(self) -> None:
        assert self.data.standard_deductions.additional_age_65_plus["single"] == Decimal(2000)

    def test_age_65_plus_married(self) -> None:
        assert self.data.standard_deductions.additional_age_65_plus["married"] == Decimal(1600)

    # -- Child Tax Credit ------------------------------------------------------
    # OBBB Act Sec. 1001 — increased from $2,000 to $2,200 for 2025
    # https://www.irs.gov/newsroom/one-big-beautiful-bill-provisions-families
    def test_ctc_amount_per_child(self) -> None:
        assert self.data.child_tax_credit.amount_per_child == Decimal(2200)

    def test_ctc_refundable_portion(self) -> None:
        assert self.data.child_tax_credit.refundable_portion == Decimal(1700)

    def test_ctc_phase_out_mfj(self) -> None:
        assert self.data.child_tax_credit.phase_out_threshold["married_filing_jointly"] == Decimal(400000)

    def test_ctc_phase_out_single(self) -> None:
        assert self.data.child_tax_credit.phase_out_threshold["single"] == Decimal(200000)


# ---------------------------------------------------------------------------
# 2026 Tax Brackets
# ---------------------------------------------------------------------------
class TestTaxBrackets2026:
    """Validate 2026 tax bracket data against IRS Rev. Proc. 2025-32.

    Source: https://www.irs.gov/pub/irs-drop/rp-25-32.pdf
    """

    @pytest.fixture(autouse=True)
    def _load_data(self) -> None:
        self.data = load_tax_brackets_model(2026)

    # -- Married Filing Jointly ------------------------------------------------
    def test_mfj_10_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][0].threshold == Decimal(24800)

    def test_mfj_12_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][1].threshold == Decimal(100800)

    def test_mfj_22_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][2].threshold == Decimal(211400)

    def test_mfj_24_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][3].threshold == Decimal(403550)

    def test_mfj_32_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][4].threshold == Decimal(512450)

    def test_mfj_35_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][5].threshold == Decimal(768700)

    def test_mfj_37_no_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][6].threshold is None

    # -- Single ----------------------------------------------------------------
    def test_single_10_threshold(self) -> None:
        assert self.data.tax_brackets["single"][0].threshold == Decimal(12400)

    def test_single_12_threshold(self) -> None:
        assert self.data.tax_brackets["single"][1].threshold == Decimal(50400)

    def test_single_22_threshold(self) -> None:
        assert self.data.tax_brackets["single"][2].threshold == Decimal(105700)

    def test_single_24_threshold(self) -> None:
        assert self.data.tax_brackets["single"][3].threshold == Decimal(201775)

    def test_single_32_threshold(self) -> None:
        assert self.data.tax_brackets["single"][4].threshold == Decimal(256225)

    def test_single_35_threshold(self) -> None:
        assert self.data.tax_brackets["single"][5].threshold == Decimal(640600)

    # -- Head of Household -----------------------------------------------------
    def test_hoh_10_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][0].threshold == Decimal(17700)

    def test_hoh_12_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][1].threshold == Decimal(67450)

    def test_hoh_24_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][3].threshold == Decimal(201750)

    def test_hoh_32_threshold(self) -> None:
        assert self.data.tax_brackets["head_of_household"][4].threshold == Decimal(256200)

    # -- Standard Deductions (2026) --------------------------------------------
    # IRS Rev. Proc. 2025-32 + OBBB Act continuation
    def test_standard_deduction_mfj(self) -> None:
        assert self.data.standard_deductions.amounts["married_filing_jointly"] == Decimal(32200)

    def test_standard_deduction_single(self) -> None:
        assert self.data.standard_deductions.amounts["single"] == Decimal(16100)

    def test_standard_deduction_mfs(self) -> None:
        assert self.data.standard_deductions.amounts["married_filing_separately"] == Decimal(16100)

    def test_standard_deduction_hoh(self) -> None:
        assert self.data.standard_deductions.amounts["head_of_household"] == Decimal(24150)

    # Age 65+ — inflation-adjusted for 2026
    def test_age_65_plus_single(self) -> None:
        assert self.data.standard_deductions.additional_age_65_plus["single"] == Decimal(2050)

    def test_age_65_plus_married(self) -> None:
        assert self.data.standard_deductions.additional_age_65_plus["married"] == Decimal(1650)

    # -- Child Tax Credit (2026 — same as 2025 under OBBB) --------------------
    def test_ctc_amount_per_child(self) -> None:
        assert self.data.child_tax_credit.amount_per_child == Decimal(2200)

    def test_ctc_refundable_portion(self) -> None:
        assert self.data.child_tax_credit.refundable_portion == Decimal(1700)


# ---------------------------------------------------------------------------
# 2025 FICA Limits
# ---------------------------------------------------------------------------
class TestFICALimits2025:
    """Validate 2025 FICA data against SSA and IRS sources.

    SS wage base: https://www.ssa.gov/oact/cola/cbbdet.html ($176,100 for 2025)
    FICA rates: https://www.irs.gov/taxtopics/tc751
    """

    @pytest.fixture(autouse=True)
    def _load_data(self) -> None:
        self.data = load_fica_limits_model(2025)

    def test_ss_employee_rate(self) -> None:
        assert self.data.social_security.employee_rate == Decimal("0.062")

    def test_ss_employer_rate(self) -> None:
        assert self.data.social_security.employer_rate == Decimal("0.062")

    def test_ss_wage_base_limit(self) -> None:
        # SSA: 2025 contribution and benefit base = $176,100
        assert self.data.social_security.wage_base_limit == Decimal(176100)

    def test_ss_max_employee_tax(self) -> None:
        # $176,100 * 0.062 = $10,918.20
        expected = Decimal(176100) * Decimal("0.062")
        assert self.data.social_security.max_employee_tax == expected

    def test_ss_max_tax_consistent(self) -> None:
        """max_employee_tax must equal wage_base_limit * employee_rate."""
        computed = self.data.social_security.wage_base_limit * self.data.social_security.employee_rate
        assert self.data.social_security.max_employee_tax == computed

    def test_medicare_employee_rate(self) -> None:
        assert self.data.medicare.employee_rate == Decimal("0.0145")

    def test_medicare_no_wage_base(self) -> None:
        assert self.data.medicare.wage_base_limit is None

    def test_additional_medicare_rate(self) -> None:
        # IRC Sec. 3101(b)(2): 0.9% additional Medicare
        assert self.data.additional_medicare.rate == Decimal("0.009")

    def test_additional_medicare_single_threshold(self) -> None:
        assert self.data.additional_medicare.thresholds["single"] == Decimal(200000)

    def test_additional_medicare_mfj_threshold(self) -> None:
        assert self.data.additional_medicare.thresholds["married_filing_jointly"] == Decimal(250000)

    def test_additional_medicare_mfs_threshold(self) -> None:
        assert self.data.additional_medicare.thresholds["married_filing_separately"] == Decimal(125000)


# ---------------------------------------------------------------------------
# 2026 FICA Limits
# ---------------------------------------------------------------------------
class TestFICALimits2026:
    """Validate 2026 FICA data against SSA and IRS sources.

    SS wage base: https://www.ssa.gov/oact/cola/cbbdet.html ($184,500 for 2026)
    """

    @pytest.fixture(autouse=True)
    def _load_data(self) -> None:
        self.data = load_fica_limits_model(2026)

    def test_ss_wage_base_limit(self) -> None:
        # SSA: 2026 contribution and benefit base = $184,500
        assert self.data.social_security.wage_base_limit == Decimal(184500)

    def test_ss_max_employee_tax(self) -> None:
        # $184,500 * 0.062 = $11,439.00
        expected = Decimal(184500) * Decimal("0.062")
        assert self.data.social_security.max_employee_tax == expected

    def test_ss_max_tax_consistent(self) -> None:
        computed = self.data.social_security.wage_base_limit * self.data.social_security.employee_rate
        assert self.data.social_security.max_employee_tax == computed

    def test_medicare_rate_unchanged(self) -> None:
        assert self.data.medicare.employee_rate == Decimal("0.0145")

    def test_additional_medicare_rate_unchanged(self) -> None:
        assert self.data.additional_medicare.rate == Decimal("0.009")

    def test_additional_medicare_thresholds_unchanged(self) -> None:
        # Additional Medicare thresholds are NOT indexed for inflation
        assert self.data.additional_medicare.thresholds["single"] == Decimal(200000)
        assert self.data.additional_medicare.thresholds["married_filing_jointly"] == Decimal(250000)


# ---------------------------------------------------------------------------
# Structural Integrity
# ---------------------------------------------------------------------------
class TestDataIntegrity:
    """Verify structural properties that must hold for all tax years."""

    @pytest.fixture(autouse=True)
    def _load_all(self) -> None:
        self.brackets_2025 = load_tax_brackets_model(2025)
        self.brackets_2026 = load_tax_brackets_model(2026)
        self.fica_2025 = load_fica_limits_model(2025)
        self.fica_2026 = load_fica_limits_model(2026)

    @pytest.mark.parametrize("year_attr", ["brackets_2025", "brackets_2026"])
    def test_all_four_statuses_present(self, year_attr: str) -> None:
        data = getattr(self, year_attr)
        expected = {
            "single",
            "married_filing_jointly",
            "married_filing_separately",
            "head_of_household",
        }
        assert set(data.tax_brackets.keys()) == expected

    @pytest.mark.parametrize("year_attr", ["brackets_2025", "brackets_2026"])
    def test_seven_brackets_per_status(self, year_attr: str) -> None:
        data = getattr(self, year_attr)
        for status, brackets in data.tax_brackets.items():
            assert len(brackets) == 7, f"{status} should have 7 brackets"

    @pytest.mark.parametrize("year_attr", ["brackets_2025", "brackets_2026"])
    def test_rates_are_standard(self, year_attr: str) -> None:
        """All filing statuses use the same 7 rate tiers."""
        expected_rates = [
            Decimal("0.10"),
            Decimal("0.12"),
            Decimal("0.22"),
            Decimal("0.24"),
            Decimal("0.32"),
            Decimal("0.35"),
            Decimal("0.37"),
        ]
        data = getattr(self, year_attr)
        for status, brackets in data.tax_brackets.items():
            rates = [b.rate for b in brackets]
            assert rates == expected_rates, f"{status} has unexpected rates"

    @pytest.mark.parametrize("year_attr", ["brackets_2025", "brackets_2026"])
    def test_thresholds_monotonically_increasing(self, year_attr: str) -> None:
        data = getattr(self, year_attr)
        for status, brackets in data.tax_brackets.items():
            thresholds = [b.threshold for b in brackets if b.threshold is not None]
            for i in range(1, len(thresholds)):
                assert thresholds[i] > thresholds[i - 1], (
                    f"{status}: threshold {thresholds[i]} not > {thresholds[i - 1]}"
                )

    @pytest.mark.parametrize("year_attr", ["brackets_2025", "brackets_2026"])
    def test_last_bracket_has_no_threshold(self, year_attr: str) -> None:
        data = getattr(self, year_attr)
        for status, brackets in data.tax_brackets.items():
            assert brackets[-1].threshold is None, f"{status}: last bracket must have no threshold"

    @pytest.mark.parametrize("year_attr", ["fica_2025", "fica_2026"])
    def test_ss_max_tax_equals_rate_times_base(self, year_attr: str) -> None:
        data = getattr(self, year_attr)
        expected = data.social_security.wage_base_limit * data.social_security.employee_rate
        assert data.social_security.max_employee_tax == expected

    @pytest.mark.parametrize("year_attr", ["fica_2025", "fica_2026"])
    def test_combined_max_is_double_employee(self, year_attr: str) -> None:
        data = getattr(self, year_attr)
        assert data.social_security.max_combined_tax == data.social_security.max_employee_tax * 2
