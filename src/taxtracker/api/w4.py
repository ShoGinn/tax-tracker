"""W-4 optimization and withholding calculation endpoints."""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from taxtracker.api.dependencies import get_tax_calculator
from taxtracker.core.exceptions import W4CalculationError
from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.tax_calculator import TaxCalculator
from taxtracker.services.w4_calculator import optimize_w4
from taxtracker.services.w4_withholding import (
    calculate_withholding_per_paycheck,
    estimate_annual_withholding_from_w4,
)

router = APIRouter(prefix="/w4", tags=["W-4"])


@router.post("/optimize")
def optimize_w4_settings(
    total_annual_w2_income: float,
    paychecks_per_year: int,
    filing_status: str,
    num_children: int = 0,
    other_annual_income: float = 0,
    itemized_deductions: float = 0,
    target_refund: float = 0,
    year: int = 2024,
    calculator: TaxCalculator = Depends(get_tax_calculator),
) -> dict[str, Any]:
    """
    Optimize W-4 settings to achieve target refund amount.

    Calculates optimal W-4 form values for Steps 2, 3, and 4 to ensure
    proper withholding throughout the year.

    Args:
        total_annual_w2_income: Total W-2 income across all jobs
        paychecks_per_year: Number of paychecks per year
        filing_status: Filing status
        num_children: Number of qualifying children
        other_annual_income: Other income (pension, interest, etc.)
        itemized_deductions: Itemized deductions if not using standard
        target_refund: Desired refund amount (0 to break even)
        year: Tax year

    Returns:
        Optimized W-4 settings with instructions
    """
    try:
        # Convert simplified API parameters to w4_calculator format
        w2_jobs = [
            {
                "employer": "Primary Job",
                "annual_gross": total_annual_w2_income,
                "paychecks_per_year": paychecks_per_year,
            }
        ]

        # Call the service function with proper parameters
        result = optimize_w4(
            tax_calculator=calculator,
            year=year,
            filing_status=FilingStatus(filing_status),
            num_children=num_children,
            w2_jobs=w2_jobs,
            pension_taxable=Decimal(str(other_annual_income)),
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(0),  # We'll calculate optimal
            target_refund=Decimal(str(target_refund)),
            use_standard_deduction=itemized_deductions == 0,
            itemized_deductions=float(itemized_deductions),
        )

        # Convert dataclass to dict for API response
        return {
            "year": result.year,
            "filing_status": result.filing_status,
            "total_w2_income": str(result.total_w2_income),
            "total_pension_income": str(result.total_pension_income),
            "total_va_income": str(result.total_va_income),
            "total_taxable_income": str(result.total_taxable_income),
            "estimated_tax_liability": str(result.estimated_tax_liability),
            "target_refund": str(result.target_refund),
            "target_total_withholding": str(result.target_total_withholding),
            "current_total_withholding": str(result.current_total_withholding),
            "current_refund_or_owed": str(result.current_refund_or_owed),
            "adjustment_needed": str(result.adjustment_needed),
            "w4_recommendations": [
                {
                    "employer_name": rec.employer_name,
                    "filing_status": rec.filing_status,
                    "step2_checkbox": rec.step2_checkbox,
                    "step2_note": rec.step2_note,
                    "step3_amount": str(rec.step3_amount),
                    "step3_explanation": rec.step3_explanation,
                    "step4a_other_income": str(rec.step4a_other_income),
                    "step4a_explanation": rec.step4a_explanation,
                    "step4b_deductions": str(rec.step4b_deductions),
                    "step4b_explanation": rec.step4b_explanation,
                    "step4c_extra_withholding": str(rec.step4c_extra_withholding),
                    "step4c_explanation": rec.step4c_explanation,
                    "expected_annual_withholding": str(rec.expected_annual_withholding),
                    "expected_paychecks_per_year": rec.expected_paychecks_per_year,
                }
                for rec in result.w4_recommendations
            ],
            "notes": result.notes,
        }
    except W4CalculationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"W-4 optimization failed: {e!s}")


@router.post("/calculate-withholding")
def calculate_withholding(
    gross_pay_per_paycheck: float,
    pay_frequency: str,
    filing_status: str,
    multiple_jobs_checkbox: bool = False,
    dependents_amount: float = 0,
    other_income_annual: float = 0,
    deductions_annual: float = 0,
    extra_withholding: float = 0,
    year: int = 2024,
) -> dict[str, Any]:
    """
    Calculate federal withholding per paycheck based on W-4 settings.

    Uses IRS Publication 15-T percentage method to estimate withholding.

    Args:
        gross_pay_per_paycheck: Gross pay per paycheck
        pay_frequency: Pay frequency (weekly, biweekly, semimonthly, monthly)
        filing_status: Filing status
        multiple_jobs_checkbox: W-4 Step 2(c) checkbox
        dependents_amount: W-4 Step 3 amount
        other_income_annual: W-4 Step 4(a) other income
        deductions_annual: W-4 Step 4(b) deductions
        extra_withholding: W-4 Step 4(c) extra withholding
        year: Tax year

    Returns:
        Withholding per paycheck and annual withholding
    """
    try:
        result = calculate_withholding_per_paycheck(
            gross_pay=Decimal(str(gross_pay_per_paycheck)),
            pay_frequency=pay_frequency,
            filing_status=FilingStatus(filing_status),
            multiple_jobs_checkbox=multiple_jobs_checkbox,
            dependents_amount=Decimal(str(dependents_amount)),
            other_income_annual=Decimal(str(other_income_annual)),
            deductions_annual=Decimal(str(deductions_annual)),
            extra_withholding=Decimal(str(extra_withholding)),
            year=year,
        )
        return result
    except W4CalculationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Withholding calculation failed: {e!s}")


@router.post("/estimate-annual-withholding")
def estimate_withholding(
    annual_gross: float,
    pay_frequency: str,
    filing_status: str,
    w4_step2_checkbox: bool = False,
    w4_step3_dependents: float = 0,
    w4_step4a_other_income: float = 0,
    w4_step4b_deductions: float = 0,
    w4_step4c_extra: float = 0,
    year: int = 2024,
) -> dict[str, float]:
    """
    Estimate total annual withholding from W-4 settings.

    Quick calculation to see how much will be withheld for the year.

    Args:
        annual_gross: Annual gross income
        pay_frequency: Pay frequency
        filing_status: Filing status
        w4_step2_checkbox: Multiple jobs checkbox
        w4_step3_dependents: Dependents amount
        w4_step4a_other_income: Other income
        w4_step4b_deductions: Deductions
        w4_step4c_extra: Extra withholding
        year: Tax year

    Returns:
        Estimated annual withholding
    """
    try:
        annual_withholding = estimate_annual_withholding_from_w4(
            annual_gross=Decimal(str(annual_gross)),
            pay_frequency=pay_frequency,
            filing_status=FilingStatus(filing_status),
            w4_step2_checkbox=w4_step2_checkbox,
            w4_step3_dependents=Decimal(str(w4_step3_dependents)),
            w4_step4a_other_income=Decimal(str(w4_step4a_other_income)),
            w4_step4b_deductions=Decimal(str(w4_step4b_deductions)),
            w4_step4c_extra=Decimal(str(w4_step4c_extra)),
            year=year,
        )

        return {
            "annual_gross": annual_gross,
            "estimated_annual_withholding": float(annual_withholding),
            "year": year,
        }
    except W4CalculationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Withholding estimation failed: {e!s}")
