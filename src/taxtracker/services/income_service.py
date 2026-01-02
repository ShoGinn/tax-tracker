"""CRUD operations for income tracking."""

from decimal import Decimal

from sqlalchemy import extract
from sqlalchemy.orm import Session

from taxtracker.models.database import Employer, NonTaxableIncome, Paycheck, Retirement1099R
from taxtracker.models.schemas import (
    EmployerCreate,
    EmployerUpdate,
    NonTaxableIncomeCreate,
    NonTaxableIncomeUpdate,
    PaycheckCreate,
    PaycheckUpdate,
    Retirement1099RCreate,
    Retirement1099RUpdate,
    YTDSummary,
)


# Employer CRUD
def create_employer(db: Session, employer: EmployerCreate) -> Employer:
    """Create a new employer."""
    db_employer = Employer(**employer.model_dump())
    db.add(db_employer)
    db.commit()
    db.refresh(db_employer)
    return db_employer


def get_employer(db: Session, employer_id: int) -> Employer | None:
    """Get employer by ID."""
    return db.query(Employer).filter(Employer.id == employer_id).first()


def get_employers(db: Session, skip: int = 0, limit: int = 100) -> list[Employer]:
    """Get all employers."""
    return db.query(Employer).offset(skip).limit(limit).all()


def update_employer(
    db: Session, employer_id: int, employer_update: EmployerUpdate
) -> Employer | None:
    """Update an employer."""
    db_employer = get_employer(db, employer_id)
    if not db_employer:
        return None

    update_data = employer_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_employer, field, value)

    db.commit()
    db.refresh(db_employer)
    return db_employer


def delete_employer(db: Session, employer_id: int) -> bool:
    """Delete an employer (and all associated paychecks)."""
    db_employer = get_employer(db, employer_id)
    if not db_employer:
        return False

    db.delete(db_employer)
    db.commit()
    return True


# Paycheck CRUD
def create_paycheck(db: Session, paycheck: PaycheckCreate) -> Paycheck:
    """Create a new paycheck."""
    db_paycheck = Paycheck(**paycheck.model_dump())
    db.add(db_paycheck)
    db.commit()
    db.refresh(db_paycheck)
    return db_paycheck


def get_paycheck(db: Session, paycheck_id: int) -> Paycheck | None:
    """Get paycheck by ID."""
    return db.query(Paycheck).filter(Paycheck.id == paycheck_id).first()


def get_paychecks(
    db: Session,
    employer_id: int | None = None,
    year: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Paycheck]:
    """Get paychecks with optional filtering."""
    query = db.query(Paycheck)

    if employer_id:
        query = query.filter(Paycheck.employer_id == employer_id)

    if year:
        query = query.filter(extract("year", Paycheck.pay_date) == year)

    return query.order_by(Paycheck.pay_date.desc()).offset(skip).limit(limit).all()


def update_paycheck(
    db: Session, paycheck_id: int, paycheck_update: PaycheckUpdate
) -> Paycheck | None:
    """Update a paycheck."""
    db_paycheck = get_paycheck(db, paycheck_id)
    if not db_paycheck:
        return None

    update_data = paycheck_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_paycheck, field, value)

    db.commit()
    db.refresh(db_paycheck)
    return db_paycheck


def delete_paycheck(db: Session, paycheck_id: int) -> bool:
    """Delete a paycheck."""
    db_paycheck = get_paycheck(db, paycheck_id)
    if not db_paycheck:
        return False

    db.delete(db_paycheck)
    db.commit()
    return True


# Pension Payment CRUD
def create_retirement_1099r(db: Session, payment: Retirement1099RCreate) -> Retirement1099R:
    """Create a new pension payment."""
    db_payment = Retirement1099R(**payment.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment


def get_retirement_1099r(db: Session, payment_id: int) -> Retirement1099R | None:
    """Get pension payment by ID."""
    return db.query(Retirement1099R).filter(Retirement1099R.id == payment_id).first()


def get_retirement_1099rs(
    db: Session, year: int | None = None, skip: int = 0, limit: int = 100
) -> list[Retirement1099R]:
    """Get pension payments with optional year filtering."""
    query = db.query(Retirement1099R)

    if year:
        query = query.filter(extract("year", Retirement1099R.pay_date) == year)

    return query.order_by(Retirement1099R.pay_date.desc()).offset(skip).limit(limit).all()


def update_retirement_1099r(
    db: Session, payment_id: int, payment_update: Retirement1099RUpdate
) -> Retirement1099R | None:
    """Update a pension payment."""
    db_payment = get_retirement_1099r(db, payment_id)
    if not db_payment:
        return None

    update_data = payment_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_payment, field, value)

    db.commit()
    db.refresh(db_payment)
    return db_payment


def delete_retirement_1099r(db: Session, payment_id: int) -> bool:
    """Delete a pension payment."""
    db_payment = get_retirement_1099r(db, payment_id)
    if not db_payment:
        return False

    db.delete(db_payment)
    db.commit()
    return True


# Non-taxable benefit Payment CRUD
def create_non_taxable_payment(db: Session, payment: NonTaxableIncomeCreate) -> NonTaxableIncome:
    """Create a new non-taxable benefit payment."""
    db_payment = NonTaxableIncome(**payment.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment


def get_non_taxable_payment(db: Session, payment_id: int) -> NonTaxableIncome | None:
    """Get VA payment by ID."""
    return db.query(NonTaxableIncome).filter(NonTaxableIncome.id == payment_id).first()


def get_non_taxable_payments(
    db: Session, year: int | None = None, skip: int = 0, limit: int = 100
) -> list[NonTaxableIncome]:
    """Get VA payments with optional year filtering."""
    query = db.query(NonTaxableIncome)

    if year:
        query = query.filter(extract("year", NonTaxableIncome.pay_date) == year)

    return query.order_by(NonTaxableIncome.pay_date.desc()).offset(skip).limit(limit).all()


def update_non_taxable_payment(
    db: Session, payment_id: int, payment_update: NonTaxableIncomeUpdate
) -> NonTaxableIncome | None:
    """Update a VA payment."""
    db_payment = get_non_taxable_payment(db, payment_id)
    if not db_payment:
        return None

    update_data = payment_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_payment, field, value)

    db.commit()
    db.refresh(db_payment)
    return db_payment


def delete_non_taxable_payment(db: Session, payment_id: int) -> bool:
    """Delete a VA payment."""
    db_payment = get_non_taxable_payment(db, payment_id)
    if not db_payment:
        return False

    db.delete(db_payment)
    db.commit()
    return True


# YTD Summary
def get_ytd_summary(db: Session, year: int) -> YTDSummary:
    """Calculate year-to-date summary for a given year."""
    # Get all paychecks for the year
    paychecks = get_paychecks(db, year=year, limit=10000)

    # Get all pension payments for the year
    retirement_1099rs = get_retirement_1099rs(db, year=year, limit=10000)

    # Get all VA payments for the year
    non_taxable_payments = get_non_taxable_payments(db, year=year, limit=10000)

    # Calculate W-2 totals
    w2_gross = sum((p.gross_wages + p.bonus for p in paychecks), Decimal(0))
    w2_pretax = sum((p.total_pretax_deductions for p in paychecks), Decimal(0))
    w2_taxable = sum((p.taxable_wages for p in paychecks), Decimal(0))
    w2_federal = sum((p.federal_withholding for p in paychecks), Decimal(0))
    w2_fica = sum((p.social_security + p.medicare for p in paychecks), Decimal(0))

    # Calculate pension totals
    pension_gross = sum((p.gross_amount for p in retirement_1099rs), Decimal(0))
    pension_pretax = sum((p.pretax_deductions for p in retirement_1099rs), Decimal(0))
    pension_taxable = sum((p.taxable_amount for p in retirement_1099rs), Decimal(0))
    pension_federal = sum((p.federal_withholding for p in retirement_1099rs), Decimal(0))

    # Calculate VA totals (non-taxable)
    va_total = sum((p.amount for p in non_taxable_payments), Decimal(0))

    return YTDSummary(
        year=year,
        total_w2_gross=w2_gross,
        total_w2_pretax_deductions=w2_pretax,
        total_w2_taxable_wages=w2_taxable,
        total_w2_federal_withheld=w2_federal,
        total_w2_fica_withheld=w2_fica,
        total_pension_gross=pension_gross,
        total_pension_pretax_deductions=pension_pretax,
        total_pension_taxable=pension_taxable,
        total_pension_federal_withheld=pension_federal,
        total_va_disability=va_total,
        total_taxable_income=w2_taxable + pension_taxable,
        total_household_income=w2_gross + pension_gross + va_total,
        total_federal_withheld=w2_federal + pension_federal,
        paycheck_count=len(paychecks),
        retirement_1099r_count=len(retirement_1099rs),
        non_taxable_payment_count=len(non_taxable_payments),
    )
