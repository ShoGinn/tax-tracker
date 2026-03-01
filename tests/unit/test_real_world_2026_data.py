from decimal import Decimal

import pytest

from taxtracker.models.tax_data import (
    AdditionalMedicareTax,
    ChildTaxCredit,
    FICALimits,
    FilingStatus,
    MedicareTax,
    SocialSecurityTax,
    StandardDeductions,
    TaxBracket,
    TaxBrackets,
    TaxCalculationRequest,
)
from taxtracker.services.tax_calculator import TaxCalculator

# --- FIXTURES FOR DATA MOCKING ---


@pytest.fixture
def mock_tax_brackets_2026():
    """Returns a mock TaxBrackets model with ALL filing statuses to satisfy Pydantic."""
    # Shared 2026 Rates
    r10, r12, r22, r24, r32, r35, r37 = (
        Decimal("0.10"),
        Decimal("0.12"),
        Decimal("0.22"),
        Decimal("0.24"),
        Decimal("0.32"),
        Decimal("0.35"),
        Decimal("0.37"),
    )

    return TaxBrackets(
        tax_year=2026,
        last_updated="2026-01-01",
        source="OBBB Act 2025 / Rev. Proc. 2025-32",
        tax_brackets={
            FilingStatus.MARRIED_FILING_JOINTLY: [
                TaxBracket(threshold=Decimal(24800), rate=r10),
                TaxBracket(threshold=Decimal(100800), rate=r12),
                TaxBracket(threshold=Decimal(211400), rate=r22),
                TaxBracket(threshold=Decimal(403550), rate=r24),
                TaxBracket(threshold=Decimal(512450), rate=r32),
                TaxBracket(threshold=Decimal(768700), rate=r35),
                TaxBracket(threshold=None, rate=r37),
            ],
            FilingStatus.SINGLE: [
                TaxBracket(threshold=Decimal(12400), rate=r10),
                TaxBracket(threshold=Decimal(50400), rate=r12),
                TaxBracket(threshold=Decimal(105700), rate=r22),
                TaxBracket(threshold=Decimal(201775), rate=r24),
                TaxBracket(threshold=Decimal(256225), rate=r32),
                TaxBracket(threshold=Decimal(640600), rate=r35),
                TaxBracket(threshold=None, rate=r37),
            ],
            FilingStatus.MARRIED_FILING_SEPARATELY: [
                TaxBracket(threshold=Decimal(12400), rate=r10),
                TaxBracket(threshold=Decimal(50400), rate=r12),
                TaxBracket(threshold=Decimal(105700), rate=r22),
                TaxBracket(threshold=Decimal(201775), rate=r24),
                TaxBracket(threshold=Decimal(256225), rate=r32),
                TaxBracket(threshold=Decimal(384350), rate=r35),
                TaxBracket(threshold=None, rate=r37),
            ],
            FilingStatus.HEAD_OF_HOUSEHOLD: [
                TaxBracket(threshold=Decimal(17700), rate=r10),
                TaxBracket(threshold=Decimal(67450), rate=r12),
                TaxBracket(threshold=Decimal(105700), rate=r22),
                TaxBracket(threshold=Decimal(201750), rate=r24),
                TaxBracket(threshold=Decimal(256200), rate=r32),
                TaxBracket(threshold=Decimal(640600), rate=r35),
                TaxBracket(threshold=None, rate=r37),
            ],
        },
        standard_deductions=StandardDeductions(
            amounts={
                FilingStatus.MARRIED_FILING_JOINTLY: Decimal(32200),
                FilingStatus.SINGLE: Decimal(16100),
                FilingStatus.MARRIED_FILING_SEPARATELY: Decimal(16100),
                FilingStatus.HEAD_OF_HOUSEHOLD: Decimal(24150),
            },
            additional_age_65_plus={"single": Decimal(2000), "married": Decimal(1600)},
        ),
        child_tax_credit=ChildTaxCredit(
            amount_per_child=Decimal(2200),
            refundable_portion=Decimal(1700),
            phase_out_threshold={
                FilingStatus.MARRIED_FILING_JOINTLY: Decimal(400000),
                FilingStatus.SINGLE: Decimal(200000),
                FilingStatus.MARRIED_FILING_SEPARATELY: Decimal(200000),
                FilingStatus.HEAD_OF_HOUSEHOLD: Decimal(200000),
            },
        ),
    )


@pytest.fixture
def mock_fica_limits_2026():
    """Returns mock FICA limits for 2026."""
    return FICALimits(
        tax_year=2026,
        last_updated="2026-01-01",
        source="Social Security Administration",
        social_security=SocialSecurityTax(
            employee_rate=Decimal("0.062"),
            employer_rate=Decimal("0.062"),
            total_rate=Decimal("0.124"),
            wage_base_limit=Decimal(176100),
            max_employee_tax=Decimal("10918.20"),
            max_employer_tax=Decimal("10918.20"),
            max_combined_tax=Decimal("21836.40"),
        ),
        medicare=MedicareTax(
            employee_rate=Decimal("0.0145"),
            employer_rate=Decimal("0.0145"),
            total_rate=Decimal("0.029"),
            wage_base_limit=None,
            note="No cap on Medicare",
        ),
        additional_medicare=AdditionalMedicareTax(
            rate=Decimal("0.009"),
            employer_match=False,
            thresholds={"single": Decimal(200000), "married_filing_jointly": Decimal(250000)},
            note="Applies to wages over threshold",
        ),
        combined_rates={"total": Decimal("0.0765")},
    )


# --- THE TEST SUITE ---


def test_synthetic_mixed_income_scenario(mock_tax_brackets_2026, mock_fica_limits_2026):
    """
    Scenario: Synthetic household with taxable wages and non-taxable income.
    AGI: $42,000 | Std Deduction: $32,200 | Taxable: $9,800
    """
    calc = TaxCalculator(2026, mock_tax_brackets_2026, mock_fica_limits_2026)
    request = TaxCalculationRequest(
        gross_income=Decimal(45000),
        retirement_pretax_deductions=Decimal(3000),
        non_taxable_income=Decimal(48000),
        filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        tax_year=2026,
    )
    response = calc.calculate_taxes(request)

    assert response.adjusted_gross_income == Decimal(42000)
    # Correct 2026 math: 42000 - 32200 = 9800
    assert response.taxable_income == Decimal(9800)
    # 10% of 9800 = 980
    assert response.federal_tax_owed == Decimal("980.00")


def test_high_earner_fica_cap(mock_tax_brackets_2026, mock_fica_limits_2026):
    """
    Scenario: AI Startup employee earning $250k.
    Tests Social Security cap and Additional Medicare tax.
    """
    calc = TaxCalculator(2026, mock_tax_brackets_2026, mock_fica_limits_2026)

    request = TaxCalculationRequest(
        gross_income=Decimal(250000), filing_status=FilingStatus.SINGLE, tax_year=2026
    )

    response = calc.calculate_taxes(request)

    fica = response.fica_taxes
    # SS Tax should be capped at 176100 * 0.062 = 10918.20
    assert fica["social_security_tax"] == Decimal("10918.20")
    # Additional Medicare on (250,000 - 200,000) * 0.009 = 450.00
    assert fica["additional_medicare_tax"] == Decimal("450.00")


def test_bracket_edge_case_exact_threshold(mock_tax_brackets_2026, mock_fica_limits_2026):
    """
    Scenario: Income exactly at a point that tests bracket boundaries.
    Gross: $128,550 | Std Deduction: $32,200 | Taxable: $96,350
    """
    calc = TaxCalculator(2026, mock_tax_brackets_2026, mock_fica_limits_2026)
    request = TaxCalculationRequest(
        gross_income=Decimal(128550),
        filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        tax_year=2026,
    )
    response = calc.calculate_taxes(request)

    # 2026 Math:
    # 10% of $24,800 = $2,480.00
    # 12% of ($96,350 - $24,800) = $8,586.00
    # Total = $11,066.00
    assert response.federal_tax_owed == Decimal("11066.00")
    assert response.marginal_tax_rate == Decimal("12.0")


def test_child_tax_credit_limit(mock_tax_brackets_2026, mock_fica_limits_2026):
    """
    Scenario: Low income, many kids.
    Ensures total tax liability doesn't go below $0 (unless checking for refundability).
    """
    calc = TaxCalculator(2026, mock_tax_brackets_2026, mock_fica_limits_2026)

    request = TaxCalculationRequest(
        gross_income=Decimal(40000),
        filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        num_children=3,  # $6,600 in credits
        tax_year=2026,
    )

    response = calc.calculate_taxes(request)

    # Taxable income = 40000 - 31500 = 8500
    # Tax = 850
    # Credits = 6600
    # Liability should be clamped to 0
    assert response.total_tax_liability == Decimal(0)
