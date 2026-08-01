"""Calculate taxes from a browser-supplied income snapshot."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from taxtracker.models.tax_data import TaxCalculationRequest, TaxReconciliationResponse

if TYPE_CHECKING:
    from taxtracker.models.browser_records import ReconciliationSnapshot
    from taxtracker.services.tax_calculator import TaxCalculator


def calculate_taxes_from_records(
    snapshot: ReconciliationSnapshot,
    year: int,
    tax_calculator: TaxCalculator,
    *,
    include_taxability_in_breakdown: bool = False,
) -> TaxReconciliationResponse:
    """Aggregate one year's browser records and reconcile withholding."""
    paychecks = [record for record in snapshot.paychecks if record.pay_date.year == year]
    pensions = [record for record in snapshot.pensions if record.pay_date.year == year]
    non_taxable = [record for record in snapshot.non_taxable_income if record.pay_date.year == year]

    w2_gross = sum((record.gross_wages + record.bonus for record in paychecks), Decimal(0))
    w2_pretax = sum((record.total_pretax_deductions for record in paychecks), Decimal(0))
    w2_taxable = sum((record.taxable_wages for record in paychecks), Decimal(0))
    pension_gross = sum((record.gross_amount for record in pensions), Decimal(0))
    pension_pretax = sum((record.pretax_deductions for record in pensions), Decimal(0))
    pension_taxable = sum((record.taxable_amount for record in pensions), Decimal(0))
    non_taxable_total = sum((record.amount for record in non_taxable), Decimal(0))
    federal_withheld = sum((record.federal_withholding for record in paychecks), Decimal(0)) + sum(
        (record.federal_withholding for record in pensions),
        Decimal(0),
    )
    fica_withheld = sum((record.social_security + record.medicare for record in paychecks), Decimal(0))

    options = snapshot.options
    tax_result = tax_calculator.calculate_taxes(
        TaxCalculationRequest(
            tax_year=year,
            filing_status=options.filing_status,
            w2_gross_income=w2_taxable,
            pension_gross_income=pension_taxable,
            num_children=options.num_children,
            age_65_plus=options.age_65_plus,
            use_standard_deduction=options.use_standard_deduction,
            itemized_deduction_amount=(
                options.itemized_deduction_amount if not options.use_standard_deduction else None
            ),
        ),
        include_taxability_in_breakdown=include_taxability_in_breakdown,
    )
    fica_result = tax_calculator.calculate_fica(w2_gross, options.filing_status)
    combined_liability = Decimal(str(tax_result.total_tax_liability)) + Decimal(str(fica_result["total_fica"]))
    total_withheld = federal_withheld + fica_withheld
    refund_or_owed = total_withheld - combined_liability
    overpayment_pct = (refund_or_owed / combined_liability * 100) if combined_liability > 0 else Decimal(0)

    return TaxReconciliationResponse(
        tax_year=year,
        filing_status=options.filing_status,
        num_children=options.num_children,
        gross_income=tax_result.gross_income,
        retirement_pretax_deductions=tax_result.retirement_pretax_deductions,
        adjusted_gross_income=tax_result.adjusted_gross_income,
        deduction_amount=tax_result.deduction_amount,
        deduction_type=tax_result.deduction_type,
        taxable_income=tax_result.taxable_income,
        federal_tax_owed=tax_result.federal_tax_owed,
        child_tax_credits=tax_result.child_tax_credits,
        total_tax_liability=tax_result.total_tax_liability,
        effective_tax_rate=tax_result.effective_tax_rate,
        marginal_tax_rate=tax_result.marginal_tax_rate,
        breakdown_by_bracket=tax_result.breakdown_by_bracket,
        fica_taxes=fica_result,
        total_household_income=w2_gross + pension_gross + non_taxable_total,
        notes=tax_result.notes,
        w2_gross=w2_gross,
        w2_pretax_deductions=w2_pretax,
        w2_taxable=w2_taxable,
        pension_gross=pension_gross,
        pension_pretax_deductions=pension_pretax,
        pension_taxable=pension_taxable,
        non_taxable_income=non_taxable_total,
        total_taxable_income=w2_taxable + pension_taxable,
        total_federal_withheld=federal_withheld,
        total_fica_withheld=fica_withheld,
        total_withheld=total_withheld,
        combined_liability=combined_liability,
        refund_or_owed=refund_or_owed,
        overpayment_percentage=overpayment_pct,
        result_status="REFUND" if refund_or_owed > 0 else "OWED" if refund_or_owed < 0 else "EVEN",
    )
