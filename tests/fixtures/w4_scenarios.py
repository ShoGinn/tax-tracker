"""Canonical W-4 test scenarios with provenance metadata.

These scenarios are shared by W-4 test modules to reduce repeated setup and
keep key numeric assumptions tied to documented IRS sources.
"""

from decimal import Decimal

from fixtures.irs_test_data import get_irs_test_data

IRS_PUB_15T_2024_METADATA = {
    "source": "IRS Publication 15-T (2024), Percentage Method",
    "source_url": "https://www.irs.gov/publications/p15t",
    "verified_date": "2026-05-10",
    "notes": "Input scenarios are canonical and expected values should derive from loaded tax models.",
}

CANONICAL_W4_OPTIMIZE_SINGLE_JOB = {
    "metadata": IRS_PUB_15T_2024_METADATA,
    "w2_jobs": [
        {
            "employer": "Acme Corp",
            "annual_gross": 80000,
            "paychecks_per_year": 26,
            "annual_pretax_deductions": 5000,
        }
    ],
}

CANONICAL_W4_OPTIMIZE_TWO_JOBS = {
    "metadata": IRS_PUB_15T_2024_METADATA,
    "w2_jobs": [
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
    ],
}

CANONICAL_W4_WITHHOLDING_SINGLE_BIWEEKLY = {
    "metadata": IRS_PUB_15T_2024_METADATA,
    "inputs": {
        "gross_pay": Decimal(3000),
        "pay_frequency": "biweekly",
        "filing_status": "single",
        "year": 2024,
    },
}

CANONICAL_W4_WITHHOLDING_MFJ_TWO_CHILDREN = {
    "metadata": IRS_PUB_15T_2024_METADATA,
    "inputs": {
        "gross_pay": Decimal(4000),
        "pay_frequency": "biweekly",
        "filing_status": "married_filing_jointly",
        "year": 2024,
    },
}


def get_single_job_scenario() -> list[dict]:
    """Return a copy of the canonical single-job W-4 optimization scenario."""
    return [dict(job) for job in CANONICAL_W4_OPTIMIZE_SINGLE_JOB["w2_jobs"]]


def get_two_job_scenario() -> list[dict]:
    """Return a copy of the canonical two-job W-4 optimization scenario."""
    return [dict(job) for job in CANONICAL_W4_OPTIMIZE_TWO_JOBS["w2_jobs"]]


def get_two_children_dependents_amount(year: int = 2024) -> Decimal:
    """Return Step 3 dependent amount for two qualifying children for a test year."""
    brackets, _ = get_irs_test_data(year)
    ctc_per_child = brackets.child_tax_credit.amount_per_child
    return ctc_per_child * Decimal(2)
