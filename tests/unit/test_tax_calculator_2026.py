"""Tests for 2026 tax calculations using production data files."""

from decimal import Decimal

import pytest

from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest
from taxtracker.services.tax_calculator import TaxCalculator


def compute_progressive_tax(
    taxable_income: Decimal, steps: list[tuple[Decimal | None, Decimal]]
) -> Decimal:
    """Manual progressive tax calculator for expected values in tests."""
    total = Decimal(0)
    previous = Decimal(0)

    for threshold, rate in steps:
        if threshold is None:
            total += (taxable_income - previous) * rate
            break

        if taxable_income <= previous:
            break

        slice_amount = min(taxable_income, threshold) - previous
        if slice_amount > 0:
            total += slice_amount * rate
        if taxable_income <= threshold:
            break
        previous = threshold

    return total


@pytest.mark.unit
def test_2026_single_filer_80k():
    """Single filer, $80k W-2, standard deduction, 2026 data file."""
    calculator = TaxCalculator(tax_year=2026)

    request = TaxCalculationRequest(
        tax_year=2026,
        filing_status=FilingStatus.SINGLE,
        w2_gross_income=Decimal(80000),
        num_children=0,
        use_standard_deduction=True,
    )

    result = calculator.calculate_taxes(request)

    # 2026 single standard deduction: 16,100
    assert result.taxable_income == Decimal(63900)

    # Manual expected tax using 2026 single thresholds
    steps = [
        (Decimal(12400), Decimal("0.10")),
        (Decimal(50400), Decimal("0.12")),
        (Decimal(105700), Decimal("0.22")),
        (Decimal(201775), Decimal("0.24")),
        (Decimal(256225), Decimal("0.32")),
        (Decimal(640600), Decimal("0.35")),
        (None, Decimal("0.37")),
    ]
    expected_tax = compute_progressive_tax(result.taxable_income, steps)

    assert abs(result.federal_tax_owed - expected_tax) < Decimal("1.00")
    assert result.marginal_tax_rate == Decimal("22.00")


@pytest.mark.unit
def test_2026_single_high_income_top_bracket():
    """High-income single filer should land in 37% bracket with correct tax."""
    calculator = TaxCalculator(tax_year=2026)

    request = TaxCalculationRequest(
        tax_year=2026,
        filing_status=FilingStatus.SINGLE,
        w2_gross_income=Decimal(700000),
        num_children=0,
        use_standard_deduction=True,
    )

    result = calculator.calculate_taxes(request)

    taxable_income = result.taxable_income
    assert taxable_income > Decimal(640600)  # Above top threshold

    steps = [
        (Decimal(12400), Decimal("0.10")),
        (Decimal(50400), Decimal("0.12")),
        (Decimal(105700), Decimal("0.22")),
        (Decimal(201775), Decimal("0.24")),
        (Decimal(256225), Decimal("0.32")),
        (Decimal(640600), Decimal("0.35")),
        (None, Decimal("0.37")),
    ]
    expected_tax = compute_progressive_tax(taxable_income, steps)

    assert abs(result.federal_tax_owed - expected_tax) < Decimal("1.00")
    assert result.marginal_tax_rate == Decimal("37.00")
