"""Tax projection API endpoints."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException

from taxtracker.api.errors import internal_server_error
from taxtracker.core.exceptions import DataLoadError, ProjectionError
from taxtracker.models.api_requests import (  # noqa: TC001
    CompareYearsRequest,
    ProjectYearRequest,
)
from taxtracker.models.browser_records import BrowserSnapshot  # noqa: TC001
from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.midyear_periods import suggest_midyear_periods
from taxtracker.services.projections import compare_years, project_from_ytd, project_year
from taxtracker.services.tax_calculator import TaxCalculator

router = APIRouter(prefix="/projections", tags=["Projections"])
logger = logging.getLogger(__name__)


@router.post(
    "/project-year",
    summary="Project taxes for a future year",
    response_description="Tax projection with income breakdown and estimated liability",
    responses={400: {"description": "Invalid input or unsupported tax year"}},
)
async def project_future_year(request: ProjectYearRequest) -> dict[str, Any]:
    """
    Project taxes for a future year based on expected income.

    Returns:
        Tax projection with breakdown
    """
    try:
        result = project_year(
            tax_calculator=TaxCalculator(tax_year=request.projection_year),
            year=request.projection_year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            age_65_plus=request.age_65_plus,
            w2_gross=request.w2_gross,
            w2_pretax_deductions=request.w2_pretax_deductions,
            pension_gross=request.pension_gross,
            pension_pretax_deductions=request.pension_pretax_deductions,
            va_disability=request.va_disability,
            estimated_federal_withholding=Decimal(0),
            use_standard_deduction=request.use_standard_deduction,
            itemized_deductions=request.itemized_deduction_amount,
        )

        return {
            "year": result.year,
            "filing_status": result.filing_status,
            "w2_gross": str(result.w2_gross),
            "w2_taxable": str(result.w2_taxable),
            "pension_taxable": str(result.pension_taxable),
            "total_taxable_income": str(result.total_taxable_income),
            "taxable_income": str(result.taxable_income),
            "federal_tax_liability": str(result.federal_tax_liability),
            "fica_liability": str(result.fica_liability),
            "total_tax_liability": str(result.total_tax_liability),
            "estimated_withholding": str(result.estimated_withholding),
            "estimated_refund_or_owed": str(result.estimated_refund_or_owed),
            "effective_rate": str(result.effective_rate),
            "marginal_rate": str(result.marginal_rate),
        }
    except ProjectionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise internal_server_error(logger, "Projection", e) from e


@router.post(
    "/compare-years",
    summary="Compare taxes across two years",
    response_description="Year-over-year tax comparison with income and liability deltas",
    responses={400: {"description": "Invalid input or unsupported tax year"}},
)
async def compare_tax_years(request: CompareYearsRequest) -> dict[str, Any]:
    """
    Compare taxes between two years.

    Shows how tax liability changes year-over-year with different income levels.
    """
    try:
        base_projection = project_year(
            tax_calculator=TaxCalculator(tax_year=request.base_year),
            year=request.base_year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            age_65_plus=request.age_65_plus,
            w2_gross=request.base_w2_gross,
            w2_pretax_deductions=Decimal(0),
            pension_gross=request.base_pension,
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
            use_standard_deduction=request.use_standard_deduction,
            itemized_deductions=request.itemized_deduction_amount,
        )

        comp_projection = project_year(
            tax_calculator=TaxCalculator(tax_year=request.comparison_year),
            year=request.comparison_year,
            filing_status=request.filing_status,
            num_children=request.num_children,
            age_65_plus=request.age_65_plus,
            w2_gross=request.comparison_w2_gross,
            w2_pretax_deductions=Decimal(0),
            pension_gross=request.comparison_pension,
            pension_pretax_deductions=Decimal(0),
            va_disability=Decimal(0),
            estimated_federal_withholding=Decimal(0),
            use_standard_deduction=request.use_standard_deduction,
            itemized_deductions=request.itemized_deduction_amount,
        )

        return compare_years([base_projection, comp_projection])
    except ProjectionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise internal_server_error(logger, "Year comparison", e) from e


@router.post(
    "/dashboard/{year}",
    summary="Project full-year taxes using transient browser records",
    response_description=(
        "YTD actuals plus remaining-period projection with tax liability. "
        "For past years, remaining periods are 0 and projected equals actual."
    ),
    responses={400: {"description": "Invalid input or unsupported tax year"}},
)
async def dashboard_projection(
    year: int,
    snapshot: BrowserSnapshot,
) -> dict[str, Any]:
    """Project full-year income and tax from browser records.

    Uses the stored app config (filing status, pay frequency, deduction preference) to
    drive remaining-period calculations. For the current calendar year the endpoint
    fetches remaining periods via the mid-year period suggestion logic, accounting for
    whether the current pay period already has an entry in the browser snapshot. For past years
    it returns YTD actuals with no extrapolation.
    """
    try:
        config = snapshot.config
        current_year = datetime.now(UTC).year
        is_current_year = year == current_year

        paychecks = [record for record in snapshot.paychecks if record.pay_date.year == year]
        retirement_1099rs = [record for record in snapshot.pensions if record.pay_date.year == year]
        non_taxable_payments = [record for record in snapshot.non_taxable_income if record.pay_date.year == year]

        ytd_w2_gross = sum((p.gross_wages + p.bonus for p in paychecks), Decimal(0))
        ytd_w2_pretax = sum((p.total_pretax_deductions for p in paychecks), Decimal(0))
        ytd_w2_federal = sum((p.federal_withholding for p in paychecks), Decimal(0))
        ytd_pension_gross = sum((p.gross_amount for p in retirement_1099rs), Decimal(0))
        ytd_pension_pretax = sum((p.pretax_deductions for p in retirement_1099rs), Decimal(0))
        ytd_pension_federal = sum((p.federal_withholding for p in retirement_1099rs), Decimal(0))
        ytd_va = sum((p.amount for p in non_taxable_payments), Decimal(0))

        if is_current_year:
            periods = suggest_midyear_periods(
                paychecks,
                retirement_1099rs,
                non_taxable_payments,
                tax_year=year,
                as_of_date=None,
                w2_pay_frequency=config.w2_pay_frequency,
            )
            remaining_pay_periods = periods.remaining_pay_periods
            remaining_pension_periods = periods.remaining_pension_periods
            remaining_non_taxable_periods = periods.remaining_non_taxable_periods
        else:
            remaining_pay_periods = 0
            remaining_pension_periods = 0
            remaining_non_taxable_periods = 0

        filing_status = FilingStatus(config.filing_status)
        itemized_amount = config.itemized_deduction_amount if not config.use_standard_deduction else Decimal(0)

        return project_from_ytd(
            tax_calculator=TaxCalculator(tax_year=year),
            year=year,
            filing_status=filing_status,
            num_children=config.num_children,
            age_65_plus=config.age_65_plus,
            use_standard_deduction=config.use_standard_deduction,
            itemized_deduction_amount=itemized_amount,
            ytd_w2_gross=ytd_w2_gross,
            ytd_w2_pretax=ytd_w2_pretax,
            ytd_pension_gross=ytd_pension_gross,
            ytd_pension_pretax=ytd_pension_pretax,
            ytd_va_income=ytd_va,
            ytd_w2_federal_withheld=ytd_w2_federal,
            ytd_pension_federal_withheld=ytd_pension_federal,
            paycheck_count=len(paychecks),
            pension_count=len(retirement_1099rs),
            non_taxable_count=len(non_taxable_payments),
            remaining_pay_periods=remaining_pay_periods,
            remaining_pension_periods=remaining_pension_periods,
            remaining_non_taxable_periods=remaining_non_taxable_periods,
            is_current_year=is_current_year,
            as_of_date=datetime.now(UTC).date(),
        )

    except (ProjectionError, DataLoadError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise internal_server_error(logger, "Dashboard projection", e) from e
