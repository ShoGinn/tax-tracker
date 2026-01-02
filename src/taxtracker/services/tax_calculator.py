"""Federal tax calculation service."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from taxtracker.core.config import DataFileType, settings
from taxtracker.models.tax_data import (
    FICALimits,
    FilingStatus,
    TaxBrackets,
    TaxCalculationRequest,
    TaxCalculationResponse,
)


class TaxCalculator:
    """Calculate federal taxes and FICA based on IRS rules."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize with path to data directory."""
        self._tax_brackets_cache: dict[int, TaxBrackets] = {}
        self._fica_cache: dict[int, FICALimits] = {}

    def set_test_data(self, year: int, tax_brackets: TaxBrackets, fica_limits: FICALimits) -> None:
        """Inject test data directly (for testing purposes).

        This allows tests to provide known IRS data without relying on JSON files.

        Args:
            year: Tax year
            tax_brackets: TaxBrackets object with known test data
            fica_limits: FICALimits object with known test data
        """
        self._tax_brackets_cache[year] = tax_brackets
        self._fica_cache[year] = fica_limits

    def load_tax_brackets(self, year: int) -> TaxBrackets:
        """Load tax brackets for a given year."""
        if year in self._tax_brackets_cache:
            return self._tax_brackets_cache[year]

        brackets_file = settings.get_data_file(DataFileType.TAX_BRACKETS, year)
        if not brackets_file.exists():
            raise FileNotFoundError(f"Tax brackets file not found for year {year}")

        with brackets_file.open() as f:
            data = json.load(f)

        tax_brackets = TaxBrackets(**data)
        self._tax_brackets_cache[year] = tax_brackets
        return tax_brackets

    def load_fica_limits(self, year: int) -> FICALimits:
        """Load FICA limits for a given year."""
        if year in self._fica_cache:
            return self._fica_cache[year]

        fica_file = settings.get_data_file(DataFileType.FICA_LIMITS, year)
        if not fica_file.exists():
            raise FileNotFoundError(f"FICA limits file not found for year {year}")

        with fica_file.open() as f:
            data = json.load(f)

        fica_limits = FICALimits(**data)
        self._fica_cache[year] = fica_limits
        return fica_limits

    def calculate_federal_tax(
        self, taxable_income: Decimal, filing_status: FilingStatus, year: int
    ) -> tuple[Decimal, Decimal, list[dict[str, Any]]]:
        """
        Calculate federal income tax based on tax brackets.

        Returns:
            tuple: (total_tax, marginal_rate, breakdown_by_bracket)
        """
        tax_data = self.load_tax_brackets(year)
        brackets = tax_data.tax_brackets[filing_status.value]

        total_tax = Decimal(0)
        marginal_rate = Decimal(0)
        breakdown = []

        for bracket in brackets:
            bracket_min = bracket.min
            bracket_max = bracket.max if bracket.max is not None else Decimal("inf")

            if taxable_income <= bracket_min:
                # Haven't reached this bracket yet
                continue

            # Calculate taxable amount in this bracket
            taxable_in_bracket = min(taxable_income, bracket_max) - bracket_min
            if taxable_in_bracket <= 0:
                continue

            tax_in_bracket = taxable_in_bracket * bracket.rate
            total_tax += tax_in_bracket
            marginal_rate = bracket.rate

            breakdown.append(
                {
                    "bracket_min": float(bracket_min),
                    "bracket_max": float(bracket_max) if bracket.max is not None else None,
                    "rate": float(bracket.rate),
                    "taxable_amount": float(taxable_in_bracket),
                    "tax_amount": float(tax_in_bracket),
                }
            )

        return total_tax, marginal_rate, breakdown

    def calculate_fica(
        self, gross_wages: Decimal, filing_status: FilingStatus, year: int
    ) -> dict[str, Decimal]:
        """
        Calculate FICA taxes (Social Security and Medicare).

        Args:
            gross_wages: Total W-2 wages subject to FICA
            filing_status: Filing status for Additional Medicare threshold
            year: Tax year

        Returns:
            dict with ss_tax, medicare_tax, additional_medicare_tax, total_fica
        """
        fica_data = self.load_fica_limits(year)

        # Social Security (capped at wage base)
        ss_taxable = min(gross_wages, fica_data.social_security.wage_base_limit)
        ss_tax = ss_taxable * fica_data.social_security.employee_rate

        # Regular Medicare (no cap)
        medicare_tax = gross_wages * fica_data.medicare.employee_rate

        # Additional Medicare (only on wages above threshold)
        threshold_key = filing_status.value
        if threshold_key not in fica_data.additional_medicare.thresholds:
            threshold_key = "single"  # Default to single if not found

        additional_medicare_threshold = fica_data.additional_medicare.thresholds[threshold_key]
        additional_medicare_taxable = max(Decimal(0), gross_wages - additional_medicare_threshold)
        additional_medicare_tax = additional_medicare_taxable * fica_data.additional_medicare.rate

        total_fica = ss_tax + medicare_tax + additional_medicare_tax

        return {
            "social_security_tax": ss_tax,
            "medicare_tax": medicare_tax,
            "additional_medicare_tax": additional_medicare_tax,
            "total_fica": total_fica,
            "ss_wage_base_limit": fica_data.social_security.wage_base_limit,
            "ss_taxable_wages": ss_taxable,
        }

    def calculate_taxes(self, request: TaxCalculationRequest) -> TaxCalculationResponse:
        """
        Calculate complete tax liability based on request.

        Args:
            request: TaxCalculationRequest with income and filing info

        Returns:
            TaxCalculationResponse with detailed tax breakdown
        """
        tax_data = self.load_tax_brackets(request.tax_year)
        notes = []

        # Step 1: Calculate Adjusted Gross Income (AGI)
        # Subtract SBP (pre-tax deduction from pension)
        agi = request.gross_income - request.retirement_pretax_deductions
        if request.retirement_pretax_deductions > 0:
            deduction_amt = request.retirement_pretax_deductions
            notes.append(f"Pre-tax deduction reduces AGI by ${deduction_amt:,.2f}")

        # Step 2: Determine deduction
        if request.use_standard_deduction:
            deduction = tax_data.standard_deductions.__dict__[request.filing_status.value]
            deduction_type = "Standard Deduction"
        else:
            if request.itemized_deduction_amount is None:
                raise ValueError(
                    "Must provide itemized_deduction_amount when not using standard deduction"
                )
            deduction = request.itemized_deduction_amount
            deduction_type = "Itemized Deduction"

        # Step 3: Calculate taxable income
        taxable_income = max(Decimal(0), agi - deduction)

        # Step 4: Calculate federal income tax
        federal_tax, marginal_rate, breakdown = self.calculate_federal_tax(
            taxable_income, request.filing_status, request.tax_year
        )

        # Step 5: Apply child tax credits
        child_credits = Decimal(request.num_children) * tax_data.child_tax_credit.amount_per_child
        if child_credits > 0:
            notes.append(
                f"Child Tax Credit: ${child_credits:,.2f} for {request.num_children} children"
            )

        # Step 6: Calculate total tax liability (credits reduce tax)
        total_liability = max(Decimal(0), federal_tax - child_credits)

        # Step 7: Calculate FICA (only on W-2 wages, not pension)
        # For multi-employer situations, FICA is calculated on combined wages
        fica_taxes = self.calculate_fica(
            request.gross_income, request.filing_status, request.tax_year
        )

        # If wages exceed SS wage base, note the cap
        if request.gross_income > fica_taxes["ss_wage_base_limit"]:
            excess = request.gross_income - fica_taxes["ss_wage_base_limit"]
            wage_base = fica_taxes["ss_wage_base_limit"]
            notes.append(
                f"Social Security tax capped at ${wage_base:,.2f} wage base. "
                f"${excess:,.2f} of income not subject to SS tax."
            )

        # Step 8: Calculate effective rate
        effective_rate = (
            (total_liability / request.gross_income) * 100
            if request.gross_income > 0
            else Decimal(0)
        )

        # Step 9: Total household income (including non-taxable VA)
        total_household = request.gross_income + request.non_taxable_income
        if request.non_taxable_income > 0:
            notes.append(
                f"non-taxable benefit income (${request.non_taxable_income:,.2f}) is non-taxable"
            )

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
