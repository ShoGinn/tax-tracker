"""Unit tests for tax projections service."""

from decimal import Decimal

import pytest

from taxtracker.core.exceptions import ProjectionError
from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.projections import YearProjection, compare_years, project_year
from taxtracker.services.tax_calculator import TaxCalculator  # noqa: TC001

pytestmark = pytest.mark.unit


@pytest.fixture
def projection_2024(test_calculator: TaxCalculator) -> YearProjection:
    """Create a basic 2024 projection for reuse."""
    return project_year(
        tax_calculator=test_calculator,
        year=2024,
        filing_status=FilingStatus.SINGLE,
        num_children=0,
        w2_gross=Decimal(75000),
        w2_pretax_deductions=Decimal(5000),
        pension_gross=Decimal(0),
        pension_pretax_deductions=Decimal(0),
        va_disability=Decimal(0),
        estimated_federal_withholding=Decimal(10000),
    )


class TestProjectYear:
    """Tests for project_year function."""

    def test_basic_single_projection(self, test_calculator: TaxCalculator) -> None:
        """Test basic single filer projection returns correct structure."""
        result = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(75000),
            w2_pretax_deductions=Decimal(5000),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(10000),
        )

        assert result.year == 2024
        assert result.filing_status == "single"
        assert result.w2_gross == Decimal(75000)
        assert result.w2_taxable == Decimal(70000)
        assert result.total_taxable_income == Decimal(70000)
        assert result.federal_tax_liability > 0
        assert result.fica_liability > 0
        assert result.total_tax_liability > 0

    def test_year_mismatch_raises_error(self, test_calculator: TaxCalculator) -> None:
        """Tax calculator year must match projection year."""
        with pytest.raises(ProjectionError, match="does not match projection year"):
            project_year(
                tax_calculator=test_calculator,
                year=2025,  # Mismatch: calculator is 2024
                filing_status=FilingStatus.SINGLE,
                num_children=0,
                w2_gross=Decimal(75000),
                w2_pretax_deductions=Decimal(0),
                pension_gross=Decimal(0),
                pension_pretax_deductions=Decimal(0),
                va_disability=Decimal(0),
                estimated_federal_withholding=Decimal(0),
            )

    def test_with_pension_income(self, test_calculator: TaxCalculator) -> None:
        """Pension income should be included in total taxable."""
        result = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=2,
            w2_gross=Decimal(100000),
            w2_pretax_deductions=Decimal(10000),
            pension_gross=Decimal(30000),
            pension_pretax_deductions=Decimal(3000),
            va_disability=Decimal(2000),
            estimated_federal_withholding=Decimal(15000),
        )

        assert result.w2_taxable == Decimal(90000)
        assert result.pension_taxable == Decimal(27000)
        assert result.total_taxable_income == Decimal(117000)
        assert result.va_disability == Decimal(2000)

    def test_itemized_deduction_preserves_decimal_precision(self, test_calculator: TaxCalculator) -> None:
        """Itemized deductions remain Decimal values throughout projection math."""
        itemized = Decimal("30000.123456789")
        result = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(75000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
            use_standard_deduction=False,
            itemized_deductions=itemized,
        )

        assert result.deduction_amount == itemized

    def test_refund_calculation(self, test_calculator: TaxCalculator) -> None:
        """Estimated federal refund/owed excludes separately reported FICA."""
        result = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(50000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(20000),
        )

        expected_refund = Decimal(20000) - result.federal_tax_liability
        assert result.estimated_refund_or_owed == expected_refund

    def test_fully_withheld_federal_tax_has_zero_balance_with_fica(self, test_calculator: TaxCalculator) -> None:
        """FICA does not create a false federal balance due."""
        initial = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(50000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )

        result = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(50000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=initial.federal_tax_liability,
        )

        assert result.fica_liability > 0
        assert result.estimated_refund_or_owed == 0


class TestYearProjectionToDict:
    """Tests for YearProjection.to_dict() serialization."""

    def test_to_dict_structure(self, projection_2024: YearProjection) -> None:
        """to_dict should return nested dict with expected keys."""
        d = projection_2024.to_dict()

        assert d["year"] == 2024
        assert d["filing_status"] == "single"
        assert "income" in d
        assert "tax_calculation" in d
        assert "withholding" in d
        assert "rates" in d

    def test_to_dict_income_section(self, projection_2024: YearProjection) -> None:
        """Income section should have all expected fields as floats."""
        income = projection_2024.to_dict()["income"]

        assert income["w2_gross"] == 75000.0
        assert income["w2_pretax_deductions"] == 5000.0
        assert income["w2_taxable"] == 70000.0
        assert isinstance(income["total_taxable_income"], float)

    def test_to_dict_tax_section(self, projection_2024: YearProjection) -> None:
        """Tax calculation section should have liability and deduction info."""
        tax = projection_2024.to_dict()["tax_calculation"]

        assert "deduction_amount" in tax
        assert "deduction_type" in tax
        assert "taxable_income" in tax
        assert "federal_tax_liability" in tax
        assert "fica_liability" in tax
        assert "total_tax_liability" in tax
        assert isinstance(tax["federal_tax_liability"], float)

    def test_to_dict_withholding_section(self, projection_2024: YearProjection) -> None:
        """Withholding section should show estimate and refund/owed."""
        withholding = projection_2024.to_dict()["withholding"]

        assert withholding["estimated_withholding"] == 10000.0
        assert isinstance(withholding["estimated_refund_or_owed"], float)

    def test_to_dict_rates_section(self, projection_2024: YearProjection) -> None:
        """Rates section should show effective and marginal rates."""
        rates = projection_2024.to_dict()["rates"]

        assert isinstance(rates["effective_rate"], float)
        assert isinstance(rates["marginal_rate"], float)


class TestCompareYears:
    """Tests for compare_years function."""

    def test_compare_two_years(self, test_calculator: TaxCalculator) -> None:
        """Compare two projections shows income and tax changes."""
        proj1 = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(75000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )

        proj2 = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(85000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )
        # Manually set year for comparison purposes
        proj2.year = 2025

        result = compare_years([proj1, proj2])

        assert "comparisons" in result
        assert "years" in result
        assert "summary" in result
        assert len(result["comparisons"]) == 1

        comp = result["comparisons"][0]
        assert comp["from_year"] == 2024
        assert comp["to_year"] == 2025
        assert comp["income_change"]["amount"] == 10000.0
        assert comp["income_change"]["percentage"] > 0
        assert comp["tax_change"]["amount"] > 0

    def test_compare_fewer_than_two_years(self, projection_2024: YearProjection) -> None:
        """Need at least 2 years to compare."""
        result = compare_years([projection_2024])
        assert "error" in result

    def test_compare_summary_increasing(self, test_calculator: TaxCalculator) -> None:
        """Summary should identify increasing trends."""
        proj_low = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(50000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )

        proj_high = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(100000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )
        proj_high.year = 2025

        result = compare_years([proj_low, proj_high])

        assert result["summary"]["income_trend"] == "increasing"
        assert result["summary"]["tax_trend"] == "increasing"
        assert result["summary"]["total_years"] == 2

    def test_compare_marginal_bracket_change(self, test_calculator: TaxCalculator) -> None:
        """Should detect when marginal bracket changes between years."""
        # Low income -> 10% bracket
        proj1 = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(20000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )

        # High income -> higher bracket
        proj2 = project_year(
            tax_calculator=test_calculator,
            year=2024,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            w2_gross=Decimal(200000),
            w2_pretax_deductions=Decimal(0),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
        )
        proj2.year = 2025

        result = compare_years([proj1, proj2])
        comp = result["comparisons"][0]
        assert comp["marginal_bracket_change"]["moved_bracket"] is True
