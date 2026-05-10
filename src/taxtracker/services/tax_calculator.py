"""Federal tax calculation service."""

import math
from decimal import Decimal
from typing import Any

from taxtracker.models.tax_data import (
    FICALimits,
    FilingStatus,
    TaxBrackets,
    TaxCalculationRequest,
    TaxCalculationResponse,
)
from taxtracker.services.data_loader import load_fica_limits_model, load_tax_brackets_model


class TaxCalculator:
    """Calculate federal taxes and FICA based on IRS rules.

    This calculator is instantiated with a specific tax year and pre-loaded tax data,
    making it immutable and suitable for both production and testing scenarios.
    """

    def __init__(
        self,
        tax_year: int,
        tax_brackets: TaxBrackets | None = None,
        fica_limits: FICALimits | None = None,
    ) -> None:
        """Initialize tax calculator with tax year and data.

        Args:
            tax_year: Tax year for calculations
            tax_brackets: TaxBrackets object (loads from file if not provided)
            fica_limits: FICALimits object (loads from file if not provided)

        Raises:
            FileNotFoundError: If tax data files not found when not injected
        """
        self.tax_year = tax_year
        self._tax_brackets = tax_brackets or load_tax_brackets_model(tax_year)
        self._fica_limits = fica_limits or load_fica_limits_model(tax_year)

    @property
    def tax_brackets(self) -> TaxBrackets:
        """Public access to the loaded tax brackets data."""
        return self._tax_brackets

    def calculate_federal_tax(
        self,
        taxable_income: Decimal,
        filing_status: FilingStatus,
        annotate_taxability: bool = False,
    ) -> tuple[Decimal, Decimal, list[dict[str, Any]]]:
        """
        Calculate federal income tax using pre-computed cumulative tax (O(1) lookup).

        Uses the cumulative_tax optimization:
        - Find the bracket the income falls into
        - Tax = cumulative_tax + (rate * excess_income_over_bracket_floor)

        Returns:
            tuple: (total_tax, marginal_rate, breakdown_by_bracket)
        """
        brackets = self._tax_brackets.brackets_for_status(filing_status)

        if taxable_income <= 0:
            return Decimal(0), Decimal(0), []

        # Find the active bracket (the one this income falls into)
        active_bracket = None
        bracket_floor = Decimal(0)

        for bracket in brackets:
            # If this bracket's threshold is None, it's the "infinite" top bracket
            if bracket.threshold is None or taxable_income <= bracket.threshold:
                active_bracket = bracket
                break
            bracket_floor = bracket.threshold

        if active_bracket is None:
            return Decimal(0), Decimal(0), []

        # Calculate tax using cumulative helper formula
        excess_income = taxable_income - bracket_floor
        tax_in_bracket = excess_income * active_bracket.rate
        total_tax = active_bracket.cumulative_tax + tax_in_bracket

        # Build breakdown for full audit trail (all brackets up to active bracket)
        breakdown = []
        previous_threshold = Decimal(0)

        for bracket in brackets:
            if bracket == active_bracket:
                # Last entry: the active bracket with partial tax
                bracket_max = float(bracket.threshold) if bracket.threshold is not None else None
                entry = {
                    "bracket_min": float(previous_threshold),
                    "bracket_max": bracket_max,
                    "rate": float(bracket.rate),
                    "taxable_amount": float(excess_income),
                    "tax_amount": float(tax_in_bracket),
                }
                if annotate_taxability:
                    entry["taxable"] = True
                breakdown.append(entry)
                break

            # Prior brackets: fully taxed
            if bracket.threshold is not None:
                bracket_width = bracket.threshold - previous_threshold
                tax_in_full_bracket = bracket_width * bracket.rate

                entry = {
                    "bracket_min": float(previous_threshold),
                    "bracket_max": float(bracket.threshold),
                    "rate": float(bracket.rate),
                    "taxable_amount": float(bracket_width),
                    "tax_amount": float(tax_in_full_bracket),
                }
                if annotate_taxability:
                    entry["taxable"] = True
                breakdown.append(entry)
                previous_threshold = bracket.threshold

        marginal_rate = active_bracket.rate
        return total_tax, marginal_rate, breakdown

    def calculate_fica(self, gross_wages: Decimal, filing_status: FilingStatus) -> dict[str, Decimal]:
        """
        Calculate FICA taxes (Social Security and Medicare).

        Args:
            gross_wages: Total W-2 wages subject to FICA
            filing_status: Filing status for Additional Medicare threshold

        Returns:
            dict with ss_tax, medicare_tax, additional_medicare_tax, total_fica
        """
        # Social Security (capped at wage base)
        ss_taxable = min(gross_wages, self._fica_limits.social_security.wage_base_limit)
        ss_tax = ss_taxable * self._fica_limits.social_security.employee_rate

        # Regular Medicare (no cap)
        medicare_tax = gross_wages * self._fica_limits.medicare.employee_rate

        # Additional Medicare (only on wages above threshold)
        threshold_key = filing_status.value
        additional_medicare_threshold = self._fica_limits.additional_medicare.thresholds[threshold_key]
        additional_medicare_taxable = max(Decimal(0), gross_wages - additional_medicare_threshold)
        additional_medicare_tax = additional_medicare_taxable * self._fica_limits.additional_medicare.rate

        total_fica = ss_tax + medicare_tax + additional_medicare_tax

        return {
            "social_security_tax": ss_tax,
            "medicare_tax": medicare_tax,
            "additional_medicare_tax": additional_medicare_tax,
            "total_fica": total_fica,
            "ss_wage_base_limit": self._fica_limits.social_security.wage_base_limit,
            "ss_taxable_wages": ss_taxable,
        }

    def calculate_taxes(
        self,
        request: TaxCalculationRequest,
        include_taxability_in_breakdown: bool = False,
    ) -> TaxCalculationResponse:
        """
        Calculate complete tax liability based on request.

        Args:
            request: TaxCalculationRequest with income and filing info

        Returns:
            TaxCalculationResponse with detailed tax breakdown
        """
        notes = []

        # Step 1: Calculate Adjusted Gross Income (AGI)
        # Subtract SBP (pre-tax deduction from pension)
        agi = request.gross_income - request.retirement_pretax_deductions
        if request.retirement_pretax_deductions > 0:
            deduction_amt = request.retirement_pretax_deductions
            notes.append(f"Pre-tax deduction reduces AGI by ${deduction_amt:,.2f}")

        # Step 2: Determine deduction
        if request.use_standard_deduction:
            deduction = self._tax_brackets.standard_deductions.for_status_with_age(
                request.filing_status,
                age_65_plus=request.age_65_plus,
                agi=agi,
            )
            deduction_type = "Standard Deduction"
        else:
            if request.itemized_deduction_amount is None:
                raise ValueError("Must provide itemized_deduction_amount when not using standard deduction")
            deduction = request.itemized_deduction_amount
            deduction_type = "Itemized Deduction"

        # Step 3: Calculate taxable income
        taxable_income = max(Decimal(0), agi - deduction)

        # Step 4: Calculate federal income tax
        federal_tax, marginal_rate, breakdown = self.calculate_federal_tax(
            taxable_income,
            request.filing_status,
            annotate_taxability=include_taxability_in_breakdown,
        )

        # Step 5: Apply child tax credits (with IRS phase-out)
        ctc = self._tax_brackets.child_tax_credit
        child_credits = Decimal(request.num_children) * ctc.amount_per_child

        if child_credits > 0:
            # IRS phase-out: reduce by $50 per $1,000 (or fraction) of AGI over threshold
            threshold = ctc.phase_out_threshold.get(request.filing_status, ctc.phase_out_threshold[FilingStatus.SINGLE])
            if agi > threshold:
                excess = agi - threshold
                # Ceiling division: round up to next $1,000
                reduction = Decimal(math.ceil(excess / 1000)) * ctc.phase_out_rate
                child_credits = max(Decimal(0), child_credits - reduction)
                notes.append(
                    f"Child Tax Credit phase-out: AGI ${agi:,.2f} exceeds "
                    f"${threshold:,.0f} threshold, credit reduced by ${reduction:,.2f}"
                )

            if child_credits > 0:
                notes.append(f"Child Tax Credit: ${child_credits:,.2f} for {request.num_children} children")

        # Step 6: Calculate total tax liability (credits reduce tax)
        total_liability = max(Decimal(0), federal_tax - child_credits)

        # Step 7: Calculate FICA (only on W-2 wages, not pension)
        fica_taxes = self.calculate_fica(request.w2_gross_income, request.filing_status)

        # If wages exceed SS wage base, note the cap
        if request.w2_gross_income > fica_taxes["ss_wage_base_limit"]:
            excess = request.w2_gross_income - fica_taxes["ss_wage_base_limit"]
            wage_base = fica_taxes["ss_wage_base_limit"]
            notes.append(
                f"Social Security tax capped at ${wage_base:,.2f} wage base. "
                f"${excess:,.2f} of income not subject to SS tax."
            )

        # Step 8: Calculate effective rate
        effective_rate = (total_liability / request.gross_income) * 100 if request.gross_income > 0 else Decimal(0)

        # Step 9: Total household income (including non-taxable VA)
        total_household = request.gross_income + request.non_taxable_income
        if request.non_taxable_income > 0:
            notes.append(f"Non-taxable income (${request.non_taxable_income:,.2f}) is non-taxable")

        return TaxCalculationResponse(
            gross_income=request.gross_income,
            retirement_pretax_deductions=request.retirement_pretax_deductions,
            adjusted_gross_income=agi,
            deduction_amount=deduction,
            deduction_type=deduction_type,
            taxable_income=taxable_income,
            federal_tax_owed=federal_tax,
            child_tax_credits=child_credits,
            total_tax_liability=total_liability,
            effective_tax_rate=effective_rate,
            marginal_tax_rate=marginal_rate * 100,  # Convert to percentage
            breakdown_by_bracket=breakdown,
            fica_taxes=fica_taxes,
            total_household_income=total_household,
            notes=notes,
        )
