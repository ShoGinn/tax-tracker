"""Validated snapshots sent from the browser's IndexedDB store."""

from __future__ import annotations

from datetime import date, datetime  # noqa: TC003
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from taxtracker.models.tax_data import FilingStatus


class BrowserEmployer(BaseModel):
    """Employer metadata stored in the browser."""

    id: int = Field(ge=1)
    name: str
    ein: str | None = None
    start_date: date
    end_date: date | None = None
    notes: str | None = None


class BrowserPaycheck(BaseModel):
    """Paycheck values required by reconciliation and projection services."""

    id: int = Field(ge=1)
    employer_id: int = Field(ge=1)
    pay_date: date
    gross_wages: Decimal = Field(ge=0)
    bonus: Decimal = Field(default=Decimal(0), ge=0)
    federal_withholding: Decimal = Field(default=Decimal(0), ge=0)
    social_security: Decimal = Field(default=Decimal(0), ge=0)
    medicare: Decimal = Field(default=Decimal(0), ge=0)
    deduction_401k: Decimal = Field(default=Decimal(0), ge=0)
    deduction_403b: Decimal = Field(default=Decimal(0), ge=0)
    deduction_health_insurance: Decimal = Field(default=Decimal(0), ge=0)
    deduction_dental_insurance: Decimal = Field(default=Decimal(0), ge=0)
    deduction_vision_insurance: Decimal = Field(default=Decimal(0), ge=0)
    deduction_hsa: Decimal = Field(default=Decimal(0), ge=0)
    deduction_fsa: Decimal = Field(default=Decimal(0), ge=0)
    deduction_dependent_care_fsa: Decimal = Field(default=Decimal(0), ge=0)
    deduction_commuter: Decimal = Field(default=Decimal(0), ge=0)
    deduction_other_pretax: Decimal = Field(default=Decimal(0), ge=0)

    @property
    def total_pretax_deductions(self) -> Decimal:
        return (
            self.deduction_401k
            + self.deduction_403b
            + self.deduction_health_insurance
            + self.deduction_dental_insurance
            + self.deduction_vision_insurance
            + self.deduction_hsa
            + self.deduction_fsa
            + self.deduction_dependent_care_fsa
            + self.deduction_commuter
            + self.deduction_other_pretax
        )

    @property
    def taxable_wages(self) -> Decimal:
        return self.gross_wages + self.bonus - self.total_pretax_deductions


class BrowserPension(BaseModel):
    """1099-R payment stored in the browser."""

    id: int = Field(ge=1)
    pay_date: date
    gross_amount: Decimal = Field(ge=0)
    pretax_deductions: Decimal = Field(default=Decimal(0), ge=0)
    posttax_deductions: Decimal = Field(default=Decimal(0), ge=0)
    federal_withholding: Decimal = Field(default=Decimal(0), ge=0)
    source_description: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def taxable_amount(self) -> Decimal:
        return self.gross_amount - self.pretax_deductions


class BrowserNonTaxableIncome(BaseModel):
    """Non-taxable payment stored in the browser."""

    id: int = Field(ge=1)
    pay_date: date
    amount: Decimal = Field(ge=0)
    source_type: str | None = None
    notes: str | None = None


class BrowserConfig(BaseModel):
    """Single-browser application preferences."""

    filing_status: FilingStatus = FilingStatus.MARRIED_FILING_JOINTLY
    num_children: int = Field(default=0, ge=0)
    use_standard_deduction: bool = True
    itemized_deduction_amount: Decimal = Field(default=Decimal(0), ge=0)
    age_65_plus: bool = False
    w2_pay_frequency: Literal["weekly", "biweekly", "semimonthly", "monthly"] = "biweekly"


class BrowserSnapshot(BaseModel):
    """Complete calculation snapshot supplied by the local browser."""

    employers: list[BrowserEmployer] = Field(default_factory=list)
    paychecks: list[BrowserPaycheck] = Field(default_factory=list)
    pensions: list[BrowserPension] = Field(default_factory=list)
    non_taxable_income: list[BrowserNonTaxableIncome] = Field(default_factory=list)
    config: BrowserConfig = Field(default_factory=BrowserConfig)


class ReconciliationOptions(BaseModel):
    """User choices for a record reconciliation."""

    filing_status: FilingStatus
    num_children: int = Field(default=0, ge=0)
    use_standard_deduction: bool = True
    itemized_deduction_amount: Decimal = Field(default=Decimal(0), ge=0)


class ReconciliationSnapshot(BrowserSnapshot):
    """Browser records plus reconciliation options."""

    options: ReconciliationOptions
