"""W-4 Optimizer - Calculate optimal W-4 settings to hit target refund amount."""

import datetime  # noqa: TC003
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from taxtracker.core.config import settings
from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest
from taxtracker.services.income_service import get_non_taxable_payments, get_paychecks, get_retirement_1099rs

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from taxtracker.services.tax_calculator import TaxCalculator


@dataclass
class W4Recommendation:
    """W-4 form recommendations for a single job."""

    employer_name: str
    filing_status: str

    # Step 2: Multiple Jobs or Spouse Works
    step2_checkbox: bool
    step2_note: str

    # Step 3: Claim Dependents
    step3_amount: Decimal
    step3_explanation: str

    # Step 4(a): Other Income
    step4a_other_income: Decimal
    step4a_explanation: str

    # Step 4(b): Deductions
    step4b_deductions: Decimal
    step4b_explanation: str

    # Step 4(c): Extra Withholding
    step4c_extra_withholding: Decimal
    step4c_explanation: str

    # Expected results
    expected_annual_withholding: Decimal
    expected_paychecks_per_year: int


@dataclass
class W4OptimizationResult:
    """Complete W-4 optimization results."""

    year: int
    filing_status: str

    # Income summary
    total_w2_income: Decimal
    total_pension_income: Decimal
    total_va_income: Decimal
    total_taxable_income: Decimal

    # Tax calculation
    estimated_tax_liability: Decimal
    target_refund: Decimal
    target_total_withholding: Decimal

    # Current situation
    current_total_withholding: Decimal
    current_refund_or_owed: Decimal

    # W-4 recommendations (one per employer)
    w4_recommendations: list[W4Recommendation]

    # Summary
    adjustment_needed: Decimal
    adjustment_per_paycheck: dict[str, Decimal]  # employer_name -> amount

    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "year": self.year,
            "filing_status": self.filing_status,
            "income_summary": {
                "total_w2_income": float(self.total_w2_income),
                "total_pension_income": float(self.total_pension_income),
                "total_va_income": float(self.total_va_income),
                "total_taxable_income": float(self.total_taxable_income),
            },
            "tax_calculation": {
                "estimated_tax_liability": float(self.estimated_tax_liability),
                "target_refund": float(self.target_refund),
                "target_total_withholding": float(self.target_total_withholding),
            },
            "current_situation": {
                "current_total_withholding": float(self.current_total_withholding),
                "current_refund_or_owed": float(self.current_refund_or_owed),
                "status": "OVERPAYING"
                if self.current_refund_or_owed > settings.w4_threshold
                else "UNDERPAYING"
                if self.current_refund_or_owed < -settings.w4_threshold
                else "PERFECT",
            },
            "w4_recommendations": [
                {
                    "employer": rec.employer_name,
                    "filing_status": rec.filing_status,
                    "step_2_multiple_jobs": {
                        "checkbox": rec.step2_checkbox,
                        "note": rec.step2_note,
                    },
                    "step_3_dependents": {
                        "amount": float(rec.step3_amount),
                        "explanation": rec.step3_explanation,
                    },
                    "step_4a_other_income": {
                        "amount": float(rec.step4a_other_income),
                        "explanation": rec.step4a_explanation,
                    },
                    "step_4b_deductions": {
                        "amount": float(rec.step4b_deductions),
                        "explanation": rec.step4b_explanation,
                    },
                    "step_4c_extra_withholding": {
                        "amount": float(rec.step4c_extra_withholding),
                        "explanation": rec.step4c_explanation,
                    },
                    "expected_results": {
                        "annual_withholding": float(rec.expected_annual_withholding),
                        "paychecks_per_year": rec.expected_paychecks_per_year,
                    },
                }
                for rec in self.w4_recommendations
            ],
            "adjustment_summary": {
                "total_adjustment_needed": float(self.adjustment_needed),
                "adjustment_per_paycheck": {k: float(v) for k, v in self.adjustment_per_paycheck.items()},
            },
            "notes": self.notes,
        }


def _compute_step4b_for_reduction(
    job_adjustment: Decimal,
    job: dict[str, Any],
    marginal_rate: Decimal,
    remaining_pay_periods: int | None,
) -> tuple[Decimal, str, str]:
    """Compute Step 4b, Step 4c, and their explanations when withholding needs to decrease.

    Returns:
        (step4b_deductions, step4b_explanation, step4c_explanation)
    """
    divisor = remaining_pay_periods if remaining_pay_periods is not None else job["paychecks_per_year"]
    annual_job_gap = abs(job_adjustment) * Decimal(divisor)
    full_year_periods = Decimal(job["paychecks_per_year"])
    remaining_periods_dec = Decimal(remaining_pay_periods) if remaining_pay_periods is not None else full_year_periods
    if marginal_rate > 0:
        # Scale step4b so that applying it to only the remaining periods achieves the full annual gap:
        # step4b * marginal_rate * remaining / full_year ~= annual_gap
        step4b_deductions = (annual_job_gap * full_year_periods / remaining_periods_dec) / marginal_rate
    else:
        step4b_deductions = Decimal(0)
    step4b_explanation = (
        f"Enter ${step4b_deductions:,.0f} to reduce withholding by ~${abs(job_adjustment):,.2f}/paycheck "
        f"(estimated at {float(marginal_rate):.0%} marginal rate)"
    )
    step4c_explanation = (
        f"Step 4c must be $0 or positive; use Step 4b (above) to reduce withholding instead. "
        f"Target reduction: ${abs(job_adjustment):,.2f}/paycheck."
    )
    return step4b_deductions, step4b_explanation, step4c_explanation


def optimize_w4(
    tax_calculator: TaxCalculator,
    year: int,
    filing_status: FilingStatus,
    num_children: int,
    # Income projections
    w2_jobs: list[dict[str, Any]],  # [{"employer": "Sample Services", "annual_gross": 155000, "paychecks_per_year": 26, ...}]
    pension_taxable: Decimal,
    va_disability: Decimal,
    # Current withholding (from actual data)
    current_federal_withholding: Decimal,
    # Target
    target_refund: Decimal = Decimal(0),
    # Optional
    use_standard_deduction: bool = True,
    itemized_deductions: float = 0.0,
    # Mid-year: when set, adjustments are spread over remaining paychecks only (not total projected)
    remaining_pay_periods: int | None = None,
) -> W4OptimizationResult:
    """
    Optimize W-4 settings to hit target refund amount.

    Args:
        tax_calculator: TaxCalculator instance
        year: Tax year
        filing_status: Filing status
        num_children: Number of children
        w2_jobs: List of W-2 jobs with projections
        pension_taxable: Taxable pension income
        va_disability: non-taxable benefit (non-taxable)
        current_federal_withholding: Current year's federal withholding
        target_refund: Desired refund amount (default: $0)
        use_standard_deduction: Use standard or itemized
        itemized_deductions: Itemized deduction amount
        remaining_pay_periods: For mid-year use — number of paychecks remaining. When provided,
            per-paycheck adjustments are divided by this count rather than the full projected
            paychecks_per_year, since YTD paychecks are already locked in.

    Returns:
        W4OptimizationResult with recommendations
    """

    # Calculate total W-2 income
    total_w2_gross = sum(Decimal(str(job["annual_gross"])) for job in w2_jobs) or Decimal(0)
    total_w2_pretax = sum(Decimal(str(job.get("annual_pretax_deductions", 0))) for job in w2_jobs) or Decimal(0)
    total_w2_taxable = total_w2_gross - total_w2_pretax

    # Total taxable income
    total_taxable = total_w2_taxable + pension_taxable

    # Calculate tax liability
    tax_request = TaxCalculationRequest(
        tax_year=year,
        filing_status=filing_status,
        w2_gross_income=total_w2_taxable,
        pension_gross_income=pension_taxable,
        num_children=num_children,
        use_standard_deduction=use_standard_deduction,
        itemized_deduction_amount=Decimal(str(itemized_deductions)) if not use_standard_deduction else None,
    )

    tax_result = tax_calculator.calculate_taxes(tax_request)
    tax_liability = Decimal(str(tax_result.total_tax_liability))
    marginal_rate = Decimal(str(tax_result.marginal_tax_rate)) / Decimal(100)

    # Target withholding
    target_withholding = tax_liability + target_refund

    # Current situation
    current_refund = current_federal_withholding - tax_liability

    # Adjustment needed
    adjustment_needed = target_withholding - current_federal_withholding

    # Calculate per-paycheck adjustments for each job.
    # For mid-year, divide by remaining_pay_periods (YTD paychecks are locked in).
    # For full-year, divide by paychecks_per_year (all paychecks are in the future).
    adjustment_per_paycheck = {}
    for job in w2_jobs:
        divisor = remaining_pay_periods if remaining_pay_periods is not None else job["paychecks_per_year"]
        job_portion = Decimal(str(job["annual_gross"])) / total_w2_gross
        job_adjustment = adjustment_needed * job_portion
        adjustment_per_paycheck[job["employer"]] = job_adjustment / Decimal(divisor)

    # Generate W-4 recommendations
    w4_recommendations = []
    ctc_per_child = tax_calculator.tax_brackets.child_tax_credit.amount_per_child
    child_tax_credit_total = Decimal(num_children) * ctc_per_child

    # Determine which job should claim dependents (highest paying)
    highest_paying_job = max(w2_jobs, key=lambda x: x["annual_gross"])

    for _idx, job in enumerate(w2_jobs):
        employer = job["employer"]
        paychecks_per_year = job["paychecks_per_year"]
        is_highest_paying = job == highest_paying_job

        # Step 2: Multiple Jobs
        # New W-4: Don't check the box, use Step 4 instead for more control
        step2_checkbox = False
        step2_note = "Leave UNCHECKED. We're using Step 4 for more accurate withholding across multiple jobs."

        # Step 3: Dependents (only on highest paying job)
        step3_amount = child_tax_credit_total if is_highest_paying else Decimal(0)
        step3_explanation = (
            f"Claim {num_children} children x ${ctc_per_child:,.0f} = ${step3_amount:,.0f}"
            if is_highest_paying
            else "Already claimed on your other W-4 (claim dependents on only one job)"
        )

        # Step 4(a): Other income (only on highest paying job)
        # This is for pension that doesn't have withholding
        step4a_other_income = pension_taxable if is_highest_paying else Decimal(0)
        step4a_explanation = (
            f"Pension taxable income: ${pension_taxable:,.2f} (ensures tax is withheld for pension)"
            if is_highest_paying
            else "Other income already accounted for on your other W-4"
        )

        # Step 4(b): Deductions (if itemizing, only on highest paying job)
        if not use_standard_deduction and is_highest_paying:
            # Calculate excess over standard deduction
            standard_ded = tax_calculator.tax_brackets.standard_deductions.amounts[filing_status]
            itemized_ded = Decimal(str(itemized_deductions))
            excess = max(Decimal(0), itemized_ded - standard_ded)
            step4b_deductions = excess
            step4b_explanation = (
                f"Itemized (${itemized_ded:,.0f}) - Standard (${standard_ded:,.0f}) = ${excess:,.0f} extra deduction"
            )
        else:
            step4b_deductions = Decimal(0)
            step4b_explanation = (
                "Using standard deduction" if use_standard_deduction else "Already accounted for on your other W-4"
            )

        # Step 4(c): Extra withholding (to hit target)
        job_adjustment = adjustment_per_paycheck.get(employer, Decimal(0))
        if job_adjustment > 0:
            # Need to withhold MORE
            step4c_extra_withholding = job_adjustment
            step4c_explanation = (
                f"Withhold extra ${job_adjustment:,.2f} per paycheck to reach target ${target_refund:,.0f} refund"
            )
        elif job_adjustment < 0:
            # Need to withhold LESS. Step 4c can't be negative; Step 4b is the IRS lever.
            step4b_deductions, step4b_explanation, step4c_explanation = _compute_step4b_for_reduction(
                job_adjustment, job, marginal_rate, remaining_pay_periods
            )
            step4c_extra_withholding = Decimal(0)
        else:
            step4c_extra_withholding = Decimal(0)
            step4c_explanation = "No adjustment needed"

        # Expected withholding for this job
        # This is complex - would need to simulate paycheck calculation
        # For now, estimate based on proportion
        job_portion = Decimal(str(job["annual_gross"])) / total_w2_gross
        expected_withholding = target_withholding * job_portion

        rec = W4Recommendation(
            employer_name=employer,
            filing_status=filing_status.value,
            step2_checkbox=step2_checkbox,
            step2_note=step2_note,
            step3_amount=step3_amount,
            step3_explanation=step3_explanation,
            step4a_other_income=step4a_other_income,
            step4a_explanation=step4a_explanation,
            step4b_deductions=step4b_deductions,
            step4b_explanation=step4b_explanation,
            step4c_extra_withholding=step4c_extra_withholding,
            step4c_explanation=step4c_explanation,
            expected_annual_withholding=expected_withholding,
            expected_paychecks_per_year=paychecks_per_year,
        )

        w4_recommendations.append(rec)

    # Generate notes
    combined_step4c_extra = sum((rec.step4c_extra_withholding for rec in w4_recommendations), Decimal(0))
    combined_reduction = sum(
        (abs(v) for v in adjustment_per_paycheck.values() if v < 0),
        Decimal(0),
    )

    notes = []
    if current_refund > settings.w4_threshold:
        notes.append(
            f"⚠️ You're currently overpaying by ${current_refund:,.0f}. "
            f"These W-4 changes target about ${combined_reduction:,.2f} less withholding per pay period."
        )
    elif current_refund < -settings.w4_threshold:
        notes.append(
            f"⚠️ You're currently underpaying by ${abs(current_refund):,.0f}. "
            f"These W-4 changes will withhold about ${combined_step4c_extra:,.2f} more per pay period."
        )
    else:
        notes.append("✅ Your current withholding is close to perfect. Minor adjustments will fine-tune it.")

    notes.append("💡 Fill out a new W-4 form for each employer using the values above.")
    notes.append("📝 Submit the new W-4 to your payroll department. Changes typically take 1-2 pay periods.")
    notes.append("🔍 Check your first paycheck after the change to verify the new withholding amount.")

    if len(w2_jobs) > 1:
        notes.append(
            "👥 With multiple jobs, it's critical to fill out Step 4 accurately on your highest-paying job's W-4."
        )

    return W4OptimizationResult(
        year=year,
        filing_status=filing_status.value,
        total_w2_income=total_w2_gross,
        total_pension_income=pension_taxable,
        total_va_income=va_disability,
        total_taxable_income=total_taxable,
        estimated_tax_liability=tax_liability,
        target_refund=target_refund,
        target_total_withholding=target_withholding,
        current_total_withholding=current_federal_withholding,
        current_refund_or_owed=current_refund,
        w4_recommendations=w4_recommendations,
        adjustment_needed=adjustment_needed,
        adjustment_per_paycheck=adjustment_per_paycheck,
        notes=notes,
    )


def _filter_records_by_as_of_date(records: list[Any], as_of_date: datetime.date | None) -> list[Any]:
    """Return records constrained to pay_date <= as_of_date when provided."""
    if not as_of_date:
        return records
    return [record for record in records if record.pay_date <= as_of_date]


def _project_remaining_pension(
    retirement_1099rs: list[Any],
    ytd_pension_taxable: Decimal,
    remaining_pension_periods: int,
    expected_remaining_pension_taxable: Decimal | None,
) -> tuple[Decimal, str]:
    """Project remaining pension taxable income and return an assumptions note."""
    if expected_remaining_pension_taxable is not None:
        return (
            expected_remaining_pension_taxable,
            f"Used provided remaining pension taxable income: ${expected_remaining_pension_taxable:,.2f}.",
        )

    if retirement_1099rs:
        avg_pension_taxable = ytd_pension_taxable / len(retirement_1099rs)
        projected_remaining_pension = avg_pension_taxable * remaining_pension_periods
        return (
            projected_remaining_pension,
            "Extrapolated remaining pension taxable income using "
            f"YTD average ${avg_pension_taxable:,.2f} for {remaining_pension_periods} remaining periods.",
        )

    return (Decimal(0), "No pension records found in DB; projected remaining pension taxable income as $0.00.")


def _project_remaining_non_taxable(
    non_taxable_payments: list[Any],
    ytd_va_income: Decimal,
    remaining_non_taxable_periods: int,
) -> tuple[Decimal, str | None]:
    """Project remaining non-taxable income and optional assumptions note."""
    if not non_taxable_payments:
        return (Decimal(0), None)

    avg_va = ytd_va_income / len(non_taxable_payments)
    projected_va_remaining = avg_va * remaining_non_taxable_periods
    return (
        projected_va_remaining,
        "Extrapolated non-taxable income using "
        f"YTD average ${avg_va:,.2f} for {remaining_non_taxable_periods} periods.",
    )


async def optimize_midyear_from_db(
    db: AsyncSession,
    tax_calculator: TaxCalculator,
    year: int,
    filing_status: FilingStatus,
    remaining_pay_periods: int,
    remaining_pension_periods: int | None = None,
    remaining_non_taxable_periods: int | None = None,
    as_of_date: datetime.date | None = None,
    num_children: int = 0,
    target_refund: Decimal = Decimal(0),
    use_standard_deduction: bool = True,
    itemized_deductions: float = 0.0,
    employer_overrides: dict[int, Decimal] | None = None,
    expected_remaining_pension_taxable: Decimal | None = None,
) -> dict[str, Any]:
    """Optimize W-4 settings mid-year using already-entered database records.

    This projects full-year income from year-to-date actuals plus remaining-period assumptions,
    then reuses the existing full-year optimizer to produce W-4 recommendations.
    """

    if as_of_date and as_of_date.year != year:
        raise ValueError("as_of_date must be within the requested tax_year")

    paychecks = _filter_records_by_as_of_date(await get_paychecks(db, year=year, limit=None), as_of_date)

    if not paychecks:
        cutoff_note = f" on or before {as_of_date.isoformat()}" if as_of_date else ""
        raise ValueError(f"No paychecks found in database for tax year {year}{cutoff_note}")

    retirement_1099rs = _filter_records_by_as_of_date(
        await get_retirement_1099rs(db, year=year, limit=None),
        as_of_date,
    )
    non_taxable_payments = _filter_records_by_as_of_date(
        await get_non_taxable_payments(db, year=year, limit=None),
        as_of_date,
    )

    overrides = employer_overrides or {}
    pension_periods = remaining_pension_periods or remaining_pay_periods
    non_taxable_periods = remaining_non_taxable_periods or remaining_pay_periods
    employer_stats: dict[int, dict[str, Any]] = {}
    assumptions: list[str] = []
    assumptions.append(
        f"Using as_of_date cutoff: included records with pay_date <= {as_of_date.isoformat()}."
        if as_of_date
        else "No as_of_date provided: included all records in the tax year as YTD."
    )
    assumptions.append(
        "Remaining period assumptions: "
        f"W-2={remaining_pay_periods}, Pension={pension_periods}, Non-taxable={non_taxable_periods}."
    )

    for paycheck in paychecks:
        employer_name = paycheck.employer.name if paycheck.employer else f"Employer {paycheck.employer_id}"
        stats = employer_stats.setdefault(
            paycheck.employer_id,
            {
                "employer_name": employer_name,
                "paycheck_count": 0,
                "ytd_gross": Decimal(0),
                "ytd_pretax": Decimal(0),
                "ytd_federal_withholding": Decimal(0),
            },
        )
        stats["paycheck_count"] += 1
        stats["ytd_gross"] += paycheck.gross_wages + paycheck.bonus + paycheck.taxable_benefit
        stats["ytd_pretax"] += paycheck.total_pretax_deductions
        stats["ytd_federal_withholding"] += paycheck.federal_withholding

    w2_jobs: list[dict[str, Any]] = []
    employer_breakdown: list[dict[str, Any]] = []

    for employer_id, stats in employer_stats.items():
        paycheck_count = stats["paycheck_count"]
        ytd_gross = stats["ytd_gross"]
        ytd_pretax = stats["ytd_pretax"]
        ytd_withholding = stats["ytd_federal_withholding"]
        avg_gross = ytd_gross / paycheck_count
        avg_pretax = ytd_pretax / paycheck_count

        if employer_id in overrides:
            remaining_gross_per_paycheck = overrides[employer_id]
            assumptions.append(
                f"Used override for {stats['employer_name']}: "
                f"${remaining_gross_per_paycheck:,.2f} per remaining paycheck."
            )
        else:
            remaining_gross_per_paycheck = avg_gross
            assumptions.append(
                f"Extrapolated {stats['employer_name']} remaining gross using "
                f"YTD average ${avg_gross:,.2f} per paycheck."
            )

        projected_remaining_gross = remaining_gross_per_paycheck * remaining_pay_periods
        projected_remaining_pretax = avg_pretax * remaining_pay_periods
        projected_annual_gross = ytd_gross + projected_remaining_gross
        projected_annual_pretax = ytd_pretax + projected_remaining_pretax
        projected_paychecks = paycheck_count + remaining_pay_periods

        w2_jobs.append(
            {
                "employer": stats["employer_name"],
                "annual_gross": projected_annual_gross,
                "annual_pretax_deductions": projected_annual_pretax,
                "paychecks_per_year": projected_paychecks,
            }
        )
        employer_breakdown.append(
            {
                "employer_id": employer_id,
                "employer_name": stats["employer_name"],
                "paychecks_recorded": paycheck_count,
                "ytd_gross": str(ytd_gross),
                "ytd_pretax_deductions": str(ytd_pretax),
                "ytd_federal_withholding": str(ytd_withholding),
                "projected_remaining_gross": str(projected_remaining_gross),
                "projected_annual_gross": str(projected_annual_gross),
            }
        )

    ytd_pension_taxable = sum((p.taxable_amount for p in retirement_1099rs), Decimal(0))
    ytd_pension_withholding = sum((p.federal_withholding for p in retirement_1099rs), Decimal(0))
    ytd_va_income = sum((p.amount for p in non_taxable_payments), Decimal(0))

    projected_remaining_pension, pension_note = _project_remaining_pension(
        retirement_1099rs,
        ytd_pension_taxable,
        pension_periods,
        expected_remaining_pension_taxable,
    )
    assumptions.append(pension_note)

    projected_va_remaining, non_taxable_note = _project_remaining_non_taxable(
        non_taxable_payments,
        ytd_va_income,
        non_taxable_periods,
    )
    if non_taxable_note:
        assumptions.append(non_taxable_note)

    projected_pension_taxable = ytd_pension_taxable + projected_remaining_pension
    projected_va_income = ytd_va_income + projected_va_remaining
    ytd_total_federal_withholding = (
        sum(
            (stats["ytd_federal_withholding"] for stats in employer_stats.values()),
            Decimal(0),
        )
        + ytd_pension_withholding
    )

    # Calculate projected federal withholding for remaining periods
    ytd_w2_withholding = sum(
        (stats["ytd_federal_withholding"] for stats in employer_stats.values()),
        Decimal(0),
    )
    ytd_w2_paychecks = sum(
        (stats["paycheck_count"] for stats in employer_stats.values()),
        0,
    )
    projected_remaining_w2_withholding = Decimal(0)
    if ytd_w2_paychecks > 0:
        per_paycheck_withholding = ytd_w2_withholding / Decimal(ytd_w2_paychecks)
        projected_remaining_w2_withholding = per_paycheck_withholding * Decimal(remaining_pay_periods)

    projected_remaining_pension_withholding = Decimal(0)
    if len(retirement_1099rs) > 0 and ytd_pension_withholding > 0:
        per_pension_withholding = ytd_pension_withholding / Decimal(len(retirement_1099rs))
        projected_remaining_pension_withholding = per_pension_withholding * Decimal(pension_periods)

    projected_annual_w2_withholding = ytd_w2_withholding + projected_remaining_w2_withholding
    projected_annual_pension_withholding = ytd_pension_withholding + projected_remaining_pension_withholding
    projected_annual_total_withholding = projected_annual_w2_withholding + projected_annual_pension_withholding

    optimization = optimize_w4(
        tax_calculator=tax_calculator,
        year=year,
        filing_status=filing_status,
        num_children=num_children,
        w2_jobs=w2_jobs,
        pension_taxable=projected_pension_taxable,
        va_disability=projected_va_income,
        current_federal_withholding=projected_annual_total_withholding,
        target_refund=target_refund,
        use_standard_deduction=use_standard_deduction,
        itemized_deductions=itemized_deductions,
        remaining_pay_periods=remaining_pay_periods,
    )

    return {
        "optimization": optimization,
        "ytd_summary": {
            "tax_year": year,
            "as_of_date": as_of_date.isoformat() if as_of_date else None,
            "remaining_pay_periods": remaining_pay_periods,
            "remaining_w2_pay_periods": remaining_pay_periods,
            "remaining_pension_periods": pension_periods,
            "remaining_non_taxable_periods": non_taxable_periods,
            "employers": employer_breakdown,
            "ytd_pension_taxable": str(ytd_pension_taxable),
            "ytd_pension_federal_withholding": str(ytd_pension_withholding),
            "ytd_non_taxable_income": str(ytd_va_income),
            "ytd_total_federal_withholding": str(ytd_total_federal_withholding),
        },
        "projection_summary": {
            "projected_remaining_pension_taxable": str(projected_remaining_pension),
            "projected_full_year_pension_taxable": str(projected_pension_taxable),
            "projected_full_year_non_taxable_income": str(projected_va_income),
            "projected_remaining_w2_withholding": str(projected_remaining_w2_withholding),
            "projected_remaining_pension_withholding": str(projected_remaining_pension_withholding),
            "projected_annual_w2_withholding": str(projected_annual_w2_withholding),
            "projected_annual_pension_withholding": str(projected_annual_pension_withholding),
            "projected_annual_total_withholding": str(projected_annual_total_withholding),
        },
        "assumptions": assumptions,
    }
