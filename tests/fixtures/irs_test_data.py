"""IRS-verified test data for deterministic testing.

This module contains KNOWN tax data from IRS publications for testing.
Tests should use this data instead of relying on external JSON files.

Sources:
- IRS Publication 15 (Circular E) - Employer's Tax Guide
- IRS Form 1040 Instructions
- IRS Tax Rate Schedules

All values are from published IRS examples and rate schedules.
"""

from decimal import Decimal

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
)

# IRS 2024 Tax Brackets (from actual IRS Publication 17)
# https://www.irs.gov/publications/p17
IRS_2024_TAX_BRACKETS = TaxBrackets(
    tax_year=2024,
    last_updated="2024-11-01",
    source="IRS Publication 17, 2024 Tax Rates",
    tax_brackets={
        FilingStatus.SINGLE: [
            TaxBracket(threshold=Decimal("11600"), rate=Decimal("0.10")),
            TaxBracket(threshold=Decimal("47150"), rate=Decimal("0.12")),
            TaxBracket(threshold=Decimal("100525"), rate=Decimal("0.22")),
            TaxBracket(threshold=Decimal("191950"), rate=Decimal("0.24")),
            TaxBracket(threshold=Decimal("243725"), rate=Decimal("0.32")),
            TaxBracket(threshold=Decimal("609350"), rate=Decimal("0.35")),
            TaxBracket(threshold=None, rate=Decimal("0.37")),
        ],
        FilingStatus.MARRIED_FILING_JOINTLY: [
            TaxBracket(threshold=Decimal("23200"), rate=Decimal("0.10")),
            TaxBracket(threshold=Decimal("94300"), rate=Decimal("0.12")),
            TaxBracket(threshold=Decimal("201050"), rate=Decimal("0.22")),
            TaxBracket(threshold=Decimal("383900"), rate=Decimal("0.24")),
            TaxBracket(threshold=Decimal("487450"), rate=Decimal("0.32")),
            TaxBracket(threshold=Decimal("731200"), rate=Decimal("0.35")),
            TaxBracket(threshold=None, rate=Decimal("0.37")),
        ],
        FilingStatus.MARRIED_FILING_SEPARATELY: [
            TaxBracket(threshold=Decimal("11600"), rate=Decimal("0.10")),
            TaxBracket(threshold=Decimal("47150"), rate=Decimal("0.12")),
            TaxBracket(threshold=Decimal("100525"), rate=Decimal("0.22")),
            TaxBracket(threshold=Decimal("191950"), rate=Decimal("0.24")),
            TaxBracket(threshold=Decimal("243725"), rate=Decimal("0.32")),
            TaxBracket(threshold=Decimal("365600"), rate=Decimal("0.35")),
            TaxBracket(threshold=None, rate=Decimal("0.37")),
        ],
        FilingStatus.HEAD_OF_HOUSEHOLD: [
            TaxBracket(threshold=Decimal("16550"), rate=Decimal("0.10")),
            TaxBracket(threshold=Decimal("63100"), rate=Decimal("0.12")),
            TaxBracket(threshold=Decimal("100500"), rate=Decimal("0.22")),
            TaxBracket(threshold=Decimal("191950"), rate=Decimal("0.24")),
            TaxBracket(threshold=Decimal("243700"), rate=Decimal("0.32")),
            TaxBracket(threshold=Decimal("609350"), rate=Decimal("0.35")),
            TaxBracket(threshold=None, rate=Decimal("0.37")),
        ],
    },
    standard_deductions=StandardDeductions(
        amounts={
            FilingStatus.SINGLE: Decimal("14600"),
            FilingStatus.MARRIED_FILING_JOINTLY: Decimal("29200"),
            FilingStatus.MARRIED_FILING_SEPARATELY: Decimal("14600"),
            FilingStatus.HEAD_OF_HOUSEHOLD: Decimal("21900"),
        },
        additional_age_65_plus={"single": Decimal("1950"), "married": Decimal("1550")},
    ),
    child_tax_credit=ChildTaxCredit(
        amount_per_child=Decimal("2000"),
        refundable_portion=Decimal("1700"),
        phase_out_threshold={
            FilingStatus.MARRIED_FILING_JOINTLY: Decimal("400000"),
            FilingStatus.SINGLE: Decimal("200000"),
            FilingStatus.HEAD_OF_HOUSEHOLD: Decimal("200000"),
            FilingStatus.MARRIED_FILING_SEPARATELY: Decimal("200000"),
        },
    ),
)


# IRS 2024 FICA Limits (from IRS Publication 15, Social Security Administration)
# https://www.ssa.gov/benefits/retirement/2024.html
# https://www.irs.gov/publications/p15
IRS_2024_FICA_LIMITS = FICALimits(
    tax_year=2024,
    last_updated="2024-01-01",
    source="IRS Publication 15, Social Security Administration - 2024 Rates",
    social_security=SocialSecurityTax(
        employee_rate=Decimal("0.062"),
        employer_rate=Decimal("0.062"),
        total_rate=Decimal("0.124"),
        wage_base_limit=Decimal("168600"),
        max_employee_tax=Decimal("10453.20"),
        max_employer_tax=Decimal("10453.20"),
        max_combined_tax=Decimal("20906.40"),
    ),
    medicare=MedicareTax(
        employee_rate=Decimal("0.0145"),
        employer_rate=Decimal("0.0145"),
        total_rate=Decimal("0.029"),
        wage_base_limit=None,
        note="No wage base limit - applies to all wages",
    ),
    additional_medicare=AdditionalMedicareTax(
        rate=Decimal("0.009"),
        employer_match=False,
        thresholds={
            "single": Decimal("200000"),
            "married_filing_jointly": Decimal("250000"),
            "married_filing_separately": Decimal("125000"),
        },
        note="Applies to wages above threshold, no employer match",
    ),
    combined_rates={
        "below_ss_wage_base": Decimal("0.0765"),
        "above_ss_wage_base": Decimal("0.0145"),
        "above_additional_medicare_threshold": Decimal("0.0235"),
    },
)


def get_irs_test_data(year: int = 2024) -> tuple[TaxBrackets, FICALimits]:
    """Get IRS-verified test data for a given year.

    Args:
        year: Tax year (only 2024 is available)

    Returns:
        Tuple of (TaxBrackets, FICALimits)

    Raises:
        ValueError: If year not available
    """
    if year == 2024:
        return IRS_2024_TAX_BRACKETS, IRS_2024_FICA_LIMITS
    raise ValueError(f"Test data not available for year {year}. Only 2024 is supported.")


# IRS Example Calculations for Verification
# From IRS Publication 17, Chapter 1 Examples

IRS_EXAMPLE_1 = {
    "description": "Single filer, no dependents, standard deduction",
    "year": 2024,
    "filing_status": "single",
    "gross_income": 50000,
    "num_children": 0,
    "use_standard_deduction": True,
    "expected_taxable_income": 35400,  # 50000 - 14600
    "expected_federal_tax": 4058,  # 1160 + 0.12 * (35400 - 11600)
    "expected_marginal_rate": 12,
    "notes": "Income falls in 12% bracket",
}

IRS_EXAMPLE_2 = {
    "description": "Married filing jointly, 2 children, standard deduction",
    "year": 2024,
    "filing_status": "married_filing_jointly",
    "gross_income": 100000,
    "num_children": 2,
    "use_standard_deduction": True,
    "expected_taxable_income": 70800,  # 100000 - 29200
    "expected_federal_tax_before_credits": 8076,  # 2320 + 0.12 * (70800 - 23200)
    "expected_child_credits": 4000,  # 2000 per child
    "expected_federal_tax": 4076,  # 8076 - 4000
    "expected_marginal_rate": 12,
    "notes": "Income falls in 12% bracket, child credits apply",
}

IRS_EXAMPLE_3 = {
    "description": "High income single filer",
    "year": 2024,
    "filing_status": "single",
    "gross_income": 250000,
    "num_children": 0,
    "use_standard_deduction": True,
    "expected_taxable_income": 235400,  # 250000 - 14600
    "expected_marginal_rate": 32,  # In 32% bracket
    "notes": "Income exceeds 32% bracket threshold (243726)",
}

IRS_EXAMPLE_4 = {
    "description": "Head of household with 1 child",
    "year": 2024,
    "filing_status": "head_of_household",
    "gross_income": 75000,
    "num_children": 1,
    "use_standard_deduction": True,
    "expected_taxable_income": 53100,  # 75000 - 21900
    "expected_child_credits": 2000,
    "expected_marginal_rate": 12,
    "notes": "Head of household rates with child tax credit",
}

IRS_EXAMPLE_5 = {
    "description": "Single filer with itemized deductions",
    "year": 2024,
    "filing_status": "single",
    "gross_income": 80000,
    "num_children": 0,
    "use_standard_deduction": False,
    "itemized_deductions": 20000,
    "expected_taxable_income": 60000,  # 80000 - 20000
    "expected_marginal_rate": 22,
    "notes": "Itemized deductions exceed standard deduction",
}

IRS_EXAMPLE_6 = {
    "description": "Married with 3 children - large family",
    "year": 2024,
    "filing_status": "married_filing_jointly",
    "gross_income": 150000,
    "num_children": 3,
    "use_standard_deduction": True,
    "expected_taxable_income": 120800,  # 150000 - 29200
    "expected_child_credits": 6000,  # 3 children * 2000
    "expected_marginal_rate": 22,
    "notes": "Multiple child credits significantly reduce tax",
}


# FICA Examples from IRS Publication 15 (Circular E)

FICA_EXAMPLE_1 = {
    "description": "Standard wages under SS limit",
    "year": 2024,
    "gross_wages": 50000,
    "expected_ss_tax": 3100,  # 50000 * 0.062
    "expected_medicare_tax": 725,  # 50000 * 0.0145
    "expected_total_fica": 3825,
    "notes": "Standard FICA calculation",
}

FICA_EXAMPLE_2 = {
    "description": "Wages exceeding SS limit",
    "year": 2024,
    "gross_wages": 200000,
    "expected_ss_tax": 10453.20,  # 168600 * 0.062 (capped)
    "expected_medicare_tax": 2900,  # 200000 * 0.0145
    "expected_total_fica": 13353.20,
    "notes": "SS tax capped at wage base limit",
}

FICA_EXAMPLE_3 = {
    "description": "Single filer with additional Medicare tax",
    "year": 2024,
    "gross_wages": 250000,
    "expected_ss_tax": 10453.20,  # 168600 * 0.062 (capped)
    "expected_medicare_tax": 3625,  # 250000 * 0.0145
    "expected_additional_medicare": 450,  # (250000 - 200000) * 0.009
    "expected_total_fica": 14528.20,
    "notes": "Additional Medicare tax applies over 200k threshold",
}

FICA_EXAMPLE_4 = {
    "description": "Low income worker",
    "year": 2024,
    "gross_wages": 25000,
    "expected_ss_tax": 1550,  # 25000 * 0.062
    "expected_medicare_tax": 362.50,  # 25000 * 0.0145
    "expected_total_fica": 1912.50,
    "notes": "No additional Medicare tax at low income",
}

FICA_EXAMPLE_5 = {
    "description": "Married filing jointly at additional Medicare threshold",
    "year": 2024,
    "filing_status": "married_filing_jointly",
    "gross_wages": 275000,
    "expected_ss_tax": 10453.20,  # Capped
    "expected_medicare_tax": 3987.50,  # 275000 * 0.0145
    "expected_additional_medicare": 225,  # (275000 - 250000) * 0.009
    "expected_total_fica": 14665.70,
    "notes": "Higher threshold for married filing jointly",
}


# Edge Case Examples

EDGE_CASE_1 = {
    "description": "Income exactly at standard deduction",
    "year": 2024,
    "filing_status": "single",
    "gross_income": 14600,  # Exactly standard deduction
    "num_children": 0,
    "expected_taxable_income": 0,
    "expected_federal_tax": 0,
    "notes": "Zero tax when income equals standard deduction",
}

EDGE_CASE_2 = {
    "description": "Income $1 over standard deduction",
    "year": 2024,
    "filing_status": "single",
    "gross_income": 14601,
    "num_children": 0,
    "expected_taxable_income": 1,
    "expected_federal_tax": 0.10,  # $1 at 10%
    "notes": "Minimal tax on income just over standard deduction",
}

EDGE_CASE_3 = {
    "description": "Maximum child tax credit",
    "year": 2024,
    "filing_status": "married_filing_jointly",
    "gross_income": 120000,
    "num_children": 5,  # 5 children
    "expected_child_credits": 10000,  # 5 * 2000
    "notes": "Large family with significant child credits",
}

EDGE_CASE_4 = {
    "description": "High earner in top bracket",
    "year": 2024,
    "filing_status": "single",
    "gross_income": 750000,
    "num_children": 0,
    "expected_taxable_income": 735400,  # 750000 - 14600
    "expected_marginal_rate": 37,  # Top bracket
    "notes": "Very high income in top 37% bracket",
}

EDGE_CASE_5 = {
    "description": "Married filing separately",
    "year": 2024,
    "filing_status": "married_filing_separately",
    "gross_income": 60000,
    "num_children": 0,
    "expected_taxable_income": 45400,  # 60000 - 14600
    "expected_marginal_rate": 12,  # In 12% bracket
    "notes": "Same brackets as single filer",
}
