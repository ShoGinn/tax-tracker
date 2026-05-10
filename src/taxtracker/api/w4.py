"""W-4 optimization and withholding calculation endpoints."""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from taxtracker.api.dependencies import get_db
from taxtracker.core.config import current_tax_year
from taxtracker.core.exceptions import W4CalculationError
from taxtracker.models.api_requests import (  # noqa: TC001
    AnnualWithholdingRequest,
    MidYearDBW4OptimizeRequest,
    W4OptimizeRequest,
    WithholdingCalcRequest,
)
from taxtracker.services.tax_calculator import TaxCalculator
from taxtracker.services.w4_calculator import W4OptimizationResult, optimize_midyear_from_db, optimize_w4
from taxtracker.services.w4_withholding import (
    calculate_withholding_per_paycheck,
    estimate_annual_withholding_from_w4,
)

router = APIRouter(prefix="/w4", tags=["W-4"])


def _serialize_w4_result(result: W4OptimizationResult) -> dict[str, Any]:
    """Convert W4OptimizationResult dataclass into API-safe dictionary."""
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


@router.post(
    "/optimize",
    summary="Optimize W-4 settings",
    response_description="W-4 form recommendations (Steps 2, 3, 4a-c) with withholding breakdown",
    responses={400: {"description": "Invalid input or calculation error"}},
)
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

        return _serialize_w4_result(result)
    except W4CalculationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"W-4 optimization failed: {e!s}") from e


@router.post(
    "/optimize-midyear-from-db",
    summary="Optimize mid-year W-4 settings using database actuals",
    response_description="Mid-year W-4 recommendations with DB-based YTD snapshot and projection assumptions",
    responses={400: {"description": "Invalid input or calculation error"}},
)
async def optimize_midyear_w4_from_db(
    request: MidYearDBW4OptimizeRequest,
    *,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Optimize W-4 settings for remaining paychecks using database year-to-date entries."""
    try:
        override_map = {
            override.employer_id: override.expected_remaining_gross_per_paycheck
            for override in request.employer_overrides
        }

        result = await optimize_midyear_from_db(
            db=db,
            tax_calculator=TaxCalculator(tax_year=request.tax_year),
            year=request.tax_year,
            filing_status=request.filing_status,
            remaining_pay_periods=request.remaining_pay_periods,
            as_of_date=request.as_of_date,
            num_children=request.num_children,
            target_refund=request.target_refund,
            use_standard_deduction=request.use_standard_deduction,
            itemized_deductions=float(request.itemized_deductions),
            employer_overrides=override_map,
            expected_remaining_pension_taxable=request.expected_remaining_pension_taxable,
        )

        payload = _serialize_w4_result(result["optimization"])
        payload["ytd_summary"] = result["ytd_summary"]
        payload["projection_summary"] = result["projection_summary"]
        payload["assumptions"] = result["assumptions"]
        return payload

    except W4CalculationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e!s}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mid-year W-4 optimization failed: {e!s}") from e


@router.post(
    "/calculate-withholding",
    summary="Calculate per-paycheck withholding",
    response_description="Federal withholding per paycheck (IRS Publication 15-T percentage method)",
    responses={400: {"description": "Invalid input or calculation error"}},
)
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


@router.post(
    "/estimate-annual-withholding",
    summary="Estimate annual withholding",
    response_description="Estimated total federal withholding for the year",
    responses={400: {"description": "Invalid input or calculation error"}},
)
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
