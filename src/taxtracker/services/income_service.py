"""CRUD operations for income tracking."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import extract, select
from sqlalchemy.orm import selectinload

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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Employer CRUD
async def create_employer(db: AsyncSession, employer: EmployerCreate) -> Employer:
    """Create a new employer."""
    db_employer = Employer(**employer.model_dump())
    db.add(db_employer)
    await db.commit()
    await db.refresh(db_employer)
    return db_employer


async def get_employer(db: AsyncSession, employer_id: int) -> Employer | None:
    """Get employer by ID."""
    result = await db.execute(select(Employer).filter(Employer.id == employer_id))
    return result.scalar_one_or_none()


async def get_employers(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Employer]:
    """Get all employers."""
    result = await db.execute(select(Employer).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_employer(
    db: AsyncSession, employer_id: int, employer_update: EmployerUpdate
) -> Employer | None:
    """Update an employer."""
    db_employer = await get_employer(db, employer_id)
    if not db_employer:
        return None

    update_data = employer_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_employer, field, value)

    await db.commit()
    await db.refresh(db_employer)
    return db_employer


async def delete_employer(db: AsyncSession, employer_id: int) -> bool:
    """Delete an employer (and all associated paychecks)."""
    db_employer = await get_employer(db, employer_id)
    if not db_employer:
        return False

    await db.delete(db_employer)
    await db.commit()
    return True


# Paycheck CRUD
async def create_paycheck(db: AsyncSession, paycheck: PaycheckCreate) -> Paycheck:
    """Create a new paycheck."""
    db_paycheck = Paycheck(**paycheck.model_dump())
    db.add(db_paycheck)
    await db.commit()
    await db.refresh(db_paycheck)

    # Eagerly load employer relationship to avoid lazy loading issues in async
    result = await db.execute(
        select(Paycheck)
        .filter(Paycheck.id == db_paycheck.id)
        .options(selectinload(Paycheck.employer))
    )
    return result.scalar_one()


async def get_paycheck(db: AsyncSession, paycheck_id: int) -> Paycheck | None:
    """Get paycheck by ID."""
    result = await db.execute(
        select(Paycheck).filter(Paycheck.id == paycheck_id).options(selectinload(Paycheck.employer))
    )
    return result.scalar_one_or_none()


async def get_paychecks(
    db: AsyncSession,
    employer_id: int | None = None,
    year: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Paycheck]:
    """Get paychecks with optional filtering."""
    query = select(Paycheck).options(selectinload(Paycheck.employer))

    if employer_id:
        query = query.filter(Paycheck.employer_id == employer_id)

    if year:
        query = query.filter(extract("year", Paycheck.pay_date) == year)

    query = query.order_by(Paycheck.pay_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_paycheck(
    db: AsyncSession, paycheck_id: int, paycheck_update: PaycheckUpdate
) -> Paycheck | None:
    """Update a paycheck."""
    db_paycheck = await get_paycheck(db, paycheck_id)
    if not db_paycheck:
        return None

    update_data = paycheck_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_paycheck, field, value)

    await db.commit()
    await db.refresh(db_paycheck)

    # Re-load with employer relationship after refresh
    result = await db.execute(
        select(Paycheck)
        .filter(Paycheck.id == db_paycheck.id)
        .options(selectinload(Paycheck.employer))
    )
    return result.scalar_one()


async def delete_paycheck(db: AsyncSession, paycheck_id: int) -> bool:
    """Delete a paycheck."""
    db_paycheck = await get_paycheck(db, paycheck_id)
    if not db_paycheck:
        return False

    await db.delete(db_paycheck)
    await db.commit()
    return True


# Pension Payment CRUD
async def create_retirement_1099r(
    db: AsyncSession, payment: Retirement1099RCreate
) -> Retirement1099R:
    """Create a new pension payment."""
    db_payment = Retirement1099R(**payment.model_dump())
    db.add(db_payment)
    await db.commit()
    await db.refresh(db_payment)
    return db_payment


async def get_retirement_1099r(db: AsyncSession, payment_id: int) -> Retirement1099R | None:
    """Get pension payment by ID."""
    result = await db.execute(select(Retirement1099R).filter(Retirement1099R.id == payment_id))
    return result.scalar_one_or_none()


async def get_retirement_1099rs(
    db: AsyncSession, year: int | None = None, skip: int = 0, limit: int = 100
) -> list[Retirement1099R]:
    """Get pension payments with optional year filtering."""
    query = select(Retirement1099R)

    if year:
        query = query.filter(extract("year", Retirement1099R.pay_date) == year)

    query = query.order_by(Retirement1099R.pay_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_retirement_1099r(
    db: AsyncSession, payment_id: int, payment_update: Retirement1099RUpdate
) -> Retirement1099R | None:
    """Update a pension payment."""
    db_payment = await get_retirement_1099r(db, payment_id)
    if not db_payment:
        return None

    update_data = payment_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_payment, field, value)

    await db.commit()
    await db.refresh(db_payment)
    return db_payment


async def delete_retirement_1099r(db: AsyncSession, payment_id: int) -> bool:
    """Delete a pension payment."""
    db_payment = await get_retirement_1099r(db, payment_id)
    if not db_payment:
        return False

    await db.delete(db_payment)
    await db.commit()
    return True


# Non-Taxable Payment CRUD
async def create_non_taxable_payment(
    db: AsyncSession, payment: NonTaxableIncomeCreate
) -> NonTaxableIncome:
    """Create a new Non-Taxable payment."""
    db_payment = NonTaxableIncome(**payment.model_dump())
    db.add(db_payment)
    await db.commit()
    await db.refresh(db_payment)
    return db_payment


async def get_non_taxable_payment(db: AsyncSession, payment_id: int) -> NonTaxableIncome | None:
    """Get Non-Taxable payment by ID."""
    result = await db.execute(select(NonTaxableIncome).filter(NonTaxableIncome.id == payment_id))
    return result.scalar_one_or_none()


async def get_non_taxable_payments(
    db: AsyncSession, year: int | None = None, skip: int = 0, limit: int = 100
) -> list[NonTaxableIncome]:
    """Get Non-Taxable payments with optional year filtering."""
    query = select(NonTaxableIncome)

    if year:
        query = query.filter(extract("year", NonTaxableIncome.pay_date) == year)

    query = query.order_by(NonTaxableIncome.pay_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_non_taxable_payment(
    db: AsyncSession, payment_id: int, payment_update: NonTaxableIncomeUpdate
) -> NonTaxableIncome | None:
    """Update a non-taxable payment."""
    db_payment = await get_non_taxable_payment(db, payment_id)
    if not db_payment:
        return None

    update_data = payment_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_payment, field, value)

    await db.commit()
    await db.refresh(db_payment)
    return db_payment


async def delete_non_taxable_payment(db: AsyncSession, payment_id: int) -> bool:
    """Delete a non-taxable payment."""
    db_payment = await get_non_taxable_payment(db, payment_id)
    if not db_payment:
        return False

    await db.delete(db_payment)
    await db.commit()
    return True


# YTD Summary
async def get_ytd_summary(db: AsyncSession, year: int) -> YTDSummary:
    """Calculate year-to-date summary for a given year."""
    # Get all paychecks for the year
    paychecks = await get_paychecks(db, year=year, limit=10000)

    # Get all pension payments for the year
    retirement_1099rs = await get_retirement_1099rs(db, year=year, limit=10000)

    # Get all VA payments for the year
    non_taxable_payments = await get_non_taxable_payments(db, year=year, limit=10000)

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

    # Calculate non-taxable income totals
    non_taxable_income_total = sum((p.amount for p in non_taxable_payments), Decimal(0))

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
        total_non_taxable_income=non_taxable_income_total,
        total_taxable_income=w2_taxable + pension_taxable,
        total_household_income=w2_gross + pension_gross + non_taxable_income_total,
        total_federal_withheld=w2_federal + pension_federal,
        paycheck_count=len(paychecks),
        retirement_1099r_count=len(retirement_1099rs),
        non_taxable_payment_count=len(non_taxable_payments),
    )
