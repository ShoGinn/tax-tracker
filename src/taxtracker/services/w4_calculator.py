"""W-4 Optimizer - Calculate optimal W-4 settings to hit target refund amount."""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from taxtracker.core.config import settings
from taxtracker.models.tax_data import FilingStatus, TaxCalculationRequest

if TYPE_CHECKING:
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
                "adjustment_per_paycheck": {
                    k: float(v) for k, v in self.adjustment_per_paycheck.items()
                },
            },
            "notes": self.notes,
        }


def optimize_w4(
    tax_calculator: TaxCalculator,
    year: int,
    filing_status: FilingStatus,
    num_children: int,
    # Income projections
    w2_jobs: list[
        dict[str, Any]
    ],  # [{"employer": "Sample Services", "annual_gross": 155000, "paychecks_per_year": 26, ...}]
    pension_taxable: Decimal,
    va_disability: Decimal,
    # Current withholding (from actual data)
    current_federal_withholding: Decimal,
    # Target
    target_refund: Decimal = Decimal(0),
    # Optional
    use_standard_deduction: bool = True,
    itemized_deductions: float = 0.0,
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

    Returns:
        W4OptimizationResult with recommendations
    """

    # Calculate total W-2 income
    total_w2_gross = sum(Decimal(str(job["annual_gross"])) for job in w2_jobs) or Decimal(0)
    total_w2_pretax = sum(
        Decimal(str(job.get("annual_pretax_deductions", 0))) for job in w2_jobs
    ) or Decimal(0)
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
        itemized_deduction_amount=Decimal(str(itemized_deductions))
        if not use_standard_deduction
        else None,
    )

    tax_result = tax_calculator.calculate_taxes(tax_request)
    tax_liability = Decimal(str(tax_result.total_tax_liability))

    # Target withholding
    target_withholding = tax_liability + target_refund

    # Current situation
    current_refund = current_federal_withholding - tax_liability

    # Adjustment needed
    adjustment_needed = target_withholding - current_federal_withholding

    # Calculate per-paycheck adjustments for each job
    adjustment_per_paycheck = {}
    for job in w2_jobs:
        paychecks = job["paychecks_per_year"]
        # Distribute adjustment proportionally by income
        job_portion = Decimal(str(job["annual_gross"])) / total_w2_gross
        job_adjustment = adjustment_needed * job_portion
        adjustment_per_paycheck[job["employer"]] = job_adjustment / paychecks

    # Generate W-4 recommendations
    w4_recommendations = []
    child_tax_credit_total = Decimal(num_children * 2000)  # $2000 per child for 2025

    # Determine which job should claim dependents (highest paying)
    highest_paying_job = max(w2_jobs, key=lambda x: x["annual_gross"])

    for _idx, job in enumerate(w2_jobs):
        employer = job["employer"]
        paychecks_per_year = job["paychecks_per_year"]
        is_highest_paying = job == highest_paying_job

        # Step 2: Multiple Jobs
        # New W-4: Don't check the box, use Step 4 instead for more control
        step2_checkbox = False
        step2_note = (
            "Leave UNCHECKED. We're using Step 4 for more accurate "
            "withholding across multiple jobs."
        )

        # Step 3: Dependents (only on highest paying job)
        step3_amount = child_tax_credit_total if is_highest_paying else Decimal(0)
        step3_explanation = (
            f"Claim {num_children} children x $2,000 = ${step3_amount:,.0f}"
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
            standard_ded = (
                Decimal(str(tax_result.deduction_amount))
                if use_standard_deduction
                else Decimal(31500)
            )  # 2025 MFJ
            itemized_ded = Decimal(str(itemized_deductions))
            excess = max(Decimal(0), itemized_ded - standard_ded)
            step4b_deductions = excess
            step4b_explanation = (
                f"Itemized (${itemized_ded:,.0f}) - "
                f"Standard (${standard_ded:,.0f}) = "
                f"${excess:,.0f} extra deduction"
            )
        else:
            step4b_deductions = Decimal(0)
            step4b_explanation = (
                "Using standard deduction"
                if use_standard_deduction
                else "Already accounted for on your other W-4"
            )

        # Step 4(c): Extra withholding (to hit target)
        job_adjustment = adjustment_per_paycheck.get(employer, Decimal(0))
        if job_adjustment > 0:
            # Need to withhold MORE
            step4c_extra_withholding = job_adjustment
            step4c_explanation = (
                f"Withhold extra ${job_adjustment:,.2f} per paycheck "
                f"to reach target ${target_refund:,.0f} refund"
            )
        elif job_adjustment < 0:
            # Need to withhold LESS (can't do with extra withholding)
            step4c_extra_withholding = Decimal(0)
            step4c_explanation = (
                f"Reduce withholding by ${abs(job_adjustment):,.2f} per paycheck "
                f"(adjust Steps 3-4b above)"
            )
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
    notes = []
    if current_refund > settings.w4_threshold:
        per_check = abs(adjustment_needed / 26)
        notes.append(
            f"⚠️ You're currently overpaying by ${current_refund:,.0f}. "
            f"These W-4 changes will give you ${per_check:,.2f} more per paycheck."
        )
    elif current_refund < -settings.w4_threshold:
        per_check = adjustment_needed / 26
        notes.append(
            f"⚠️ You're currently underpaying by ${abs(current_refund):,.0f}. "
            f"These W-4 changes will withhold ${per_check:,.2f} more per paycheck."
        )
    else:
        notes.append(
            "✅ Your current withholding is close to perfect. Minor adjustments will fine-tune it."
        )

    notes.append("💡 Fill out a new W-4 form for each employer using the values above.")
    notes.append(
        "📝 Submit the new W-4 to your payroll department. Changes typically take 1-2 pay periods."
    )
    notes.append(
        "🔍 Check your first paycheck after the change to verify the new withholding amount."
    )

    if len(w2_jobs) > 1:
        notes.append(
            "👥 With multiple jobs, it's critical to fill out Step 4 accurately "
            "on your highest-paying job's W-4."
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
