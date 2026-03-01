"""W-4 optimization and withholding calculation endpoints."""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException

from taxtracker.core.config import current_tax_year
from taxtracker.core.exceptions import W4CalculationError
from taxtracker.models.api_requests import (  # noqa: TC001
    AnnualWithholdingRequest,
    W4OptimizeRequest,
    WithholdingCalcRequest,
)
from taxtracker.services.tax_calculator import TaxCalculator
from taxtracker.services.w4_calculator import optimize_w4
from taxtracker.services.w4_withholding import (
    calculate_withholding_per_paycheck,
    estimate_annual_withholding_from_w4,
)

router = APIRouter(prefix="/w4", tags=["W-4"])


@router.post("/optimize")
async def optimize_w4_settings(request: W4OptimizeRequest) -> dict[str, Any]:
    """
    Optimize W-4 settings to achieve target refund amount.

    Calculates optimal W-4 form values for Steps 2, 3, and 4 to ensure
    proper withholding throughout the year.
    """
    year = request.year or current_tax_year()
    try:
        w2_jobs = [
            {
                "employer": "Primary Job",
                "annual_gross": float(request.total_annual_w2_income),
                "paychecks_per_year": request.paychecks_per_year,
            }
        ]

        result = optimize_w4(
            tax_calculator=TaxCalculator(tax_year=year),
            year=year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            w2_jobs=w2_jobs,
            pension_taxable=request.other_annual_income,
            va_disability=Decimal(0),
            current_federal_withholding=Decimal(0),
            target_refund=request.target_refund,
            use_standard_deduction=request.itemized_deductions == 0,
            itemized_deductions=float(request.itemized_deductions),
        )

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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"W-4 optimization failed: {e!s}") from e


@router.post("/calculate-withholding")
async def calculate_withholding(request: WithholdingCalcRequest) -> dict[str, Any]:
    """
    Calculate federal withholding per paycheck based on W-4 settings.

    Uses IRS Publication 15-T percentage method to estimate withholding.
    """
    year = request.year or current_tax_year()
    try:
        return calculate_withholding_per_paycheck(
            gross_pay=request.gross_pay_per_paycheck,
            pay_frequency=request.pay_frequency,
            filing_status=request.filing_status,
            multiple_jobs_checkbox=request.multiple_jobs_checkbox,
            dependents_amount=request.dependents_amount,
            other_income_annual=request.other_income_annual,
            deductions_annual=request.deductions_annual,
            extra_withholding=request.extra_withholding,
            year=year,
        )
    except W4CalculationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Withholding calculation failed: {e!s}") from e


@router.post("/estimate-annual-withholding")
async def estimate_withholding(request: AnnualWithholdingRequest) -> dict[str, Any]:
    """
    Estimate total annual withholding from W-4 settings.

    Quick calculation to see how much will be withheld for the year.
    """
    year = request.year or current_tax_year()
    try:
        annual_withholding = estimate_annual_withholding_from_w4(
            annual_gross=request.annual_gross,
            pay_frequency=request.pay_frequency,
            filing_status=request.filing_status,
            w4_step2_checkbox=request.w4_step2_checkbox,
            w4_step3_dependents=request.w4_step3_dependents,
            w4_step4a_other_income=request.w4_step4a_other_income,
            w4_step4b_deductions=request.w4_step4b_deductions,
            w4_step4c_extra=request.w4_step4c_extra,
            year=year,
        )

        return {
            "annual_gross": float(request.annual_gross),
            "estimated_annual_withholding": float(annual_withholding),
            "year": year,
        }
    except W4CalculationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Withholding estimation failed: {e!s}") from e
