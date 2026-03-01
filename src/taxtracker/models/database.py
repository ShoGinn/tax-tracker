"""Database models using SQLAlchemy ORM."""

from datetime import date, datetime  # noqa: TC003
from decimal import Decimal

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from taxtracker.core.config import settings


class Base(DeclarativeBase):
    """Base class for all models."""


class Employer(Base):
    """Employer information."""

    __tablename__ = "employers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    ein: Mapped[str | None] = mapped_column(String(20), nullable=True)
    start_date: Mapped[date]
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    paychecks: Mapped[list[Paycheck]] = relationship(
        back_populates="employer", cascade="all, delete-orphan"
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Employer(name={self.name}, start={self.start_date})>"


class Paycheck(Base):
    """W-2 paycheck from employer."""

    __tablename__ = "paychecks"
    __table_args__ = ({"comment": "W-2 paycheck records"},)

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"), index=True)
    pay_date: Mapped[date] = mapped_column(index=True)

    # Gross income
    gross_wages: Mapped[Decimal] = mapped_column()
    bonus: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Taxable benefits (W-2 Box 12 Code C - increases taxable income but not received as cash)
    # Examples: Group term life insurance over $50k, personal use of company car, moving expenses
    taxable_benefit: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Pre-tax deductions (reduce taxable income)
    deduction_401k: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_403b: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_health_insurance: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_dental_insurance: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_vision_insurance: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_hsa: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_fsa: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_dependent_care_fsa: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_commuter: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_other_pretax: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Post-tax deductions (don't reduce taxable income)
    deduction_roth_401k: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_roth_403b: Mapped[Decimal] = mapped_column(default=Decimal(0))
    deduction_other_posttax: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Taxes withheld
    federal_withholding: Mapped[Decimal] = mapped_column(default=Decimal(0))
    social_security: Mapped[Decimal] = mapped_column(default=Decimal(0))
    medicare: Mapped[Decimal] = mapped_column(default=Decimal(0))
    state_withholding: Mapped[Decimal] = mapped_column(default=Decimal(0))
    local_withholding: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pay_period_start: Mapped[date | None] = mapped_column(nullable=True)
    pay_period_end: Mapped[date | None] = mapped_column(nullable=True)

    # Relationships
    employer: Mapped[Employer] = relationship(back_populates="paychecks")

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @property
    def total_pretax_deductions(self) -> Decimal:
        """Calculate total pre-tax deductions."""
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
    def total_posttax_deductions(self) -> Decimal:
        """Calculate total post-tax deductions."""
        return self.deduction_roth_401k + self.deduction_roth_403b + self.deduction_other_posttax

    @property
    def total_taxes_withheld(self) -> Decimal:
        """Calculate total taxes withheld."""
        return (
            self.federal_withholding
            + self.social_security
            + self.medicare
            + self.state_withholding
            + self.local_withholding
        )

    @property
    def taxable_wages(self) -> Decimal:
        """Calculate taxable wages (gross + bonus + taxable benefits - pre-tax deductions)."""
        return self.gross_wages + self.bonus + self.taxable_benefit - self.total_pretax_deductions

    @property
    def net_pay(self) -> Decimal:
        """
        Calculate net pay (take-home) based on deductions and taxes.
        Note: taxable_benefit is NOT included because it's imputed income (not actually received).
        """
        return (
            self.gross_wages
            + self.bonus
            # taxable_benefit is NOT added here - it's imputed income, not received as cash
            - self.total_pretax_deductions
            - self.total_taxes_withheld
            - self.total_posttax_deductions
        )

    def __repr__(self) -> str:
        return f"<Paycheck(date={self.pay_date}, gross=${self.gross_wages})>"


class Retirement1099R(Base):
    """1099-R retirement income (pensions, annuities, IRA distributions).

    No FICA taxes (Social Security/Medicare) apply to 1099-R income.
    Federal taxes apply unless explicitly exempt (Roth distributions, etc).
    """

    __tablename__ = "retirement_1099r"
    __table_args__ = ({"comment": "1099-R retirement income records"},)

    id: Mapped[int] = mapped_column(primary_key=True)
    pay_date: Mapped[date] = mapped_column(index=True)

    # Gross amount (Box 1 on 1099-R)
    gross_amount: Mapped[Decimal] = mapped_column()

    # Pre-tax deductions (reduce taxable amount - Box 2a calculation)
    # Examples: insurance premiums, survivor benefit plan, etc.
    pretax_deductions: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Post-tax deductions (do NOT reduce taxable amount)
    # Examples: allotments, voluntary withholdings
    posttax_deductions: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Taxes withheld (Box 4 on 1099-R for federal)
    federal_withholding: Mapped[Decimal] = mapped_column(default=Decimal(0))
    state_withholding: Mapped[Decimal] = mapped_column(default=Decimal(0))

    # Source description (e.g., "Retirement distribution", "401k Distribution")
    source_description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @property
    def taxable_amount(self) -> Decimal:
        """Calculate taxable amount (Box 2a on 1099-R).

        Gross amount minus pre-tax deductions.
        This is what gets reported as taxable retirement income.
        """
        return self.gross_amount - self.pretax_deductions

    @property
    def total_taxes_withheld(self) -> Decimal:
        """Calculate total taxes withheld."""
        return self.federal_withholding + self.state_withholding

    @property
    def net_amount(self) -> Decimal:
        """Calculate net payment received based on deductions and taxes."""
        return (
            self.gross_amount
            - self.pretax_deductions
            - self.total_taxes_withheld
            - self.posttax_deductions
        )

    def __repr__(self) -> str:
        return (
            f"<Retirement1099R(date={self.pay_date}, "
            f"gross=${self.gross_amount}, taxable=${self.taxable_amount})>"
        )


class NonTaxableIncome(Base):
    """Non-taxable income (non-taxable benefit, SSA disability, child support, gifts).

    This income is:
    - NOT subject to federal income tax
    - NOT subject to FICA (Social Security/Medicare)
    - Tracked for household income purposes only
    """

    __tablename__ = "non_taxable_income"
    __table_args__ = ({"comment": "Non-taxable income records (VA, SSA, etc.)"},)

    id: Mapped[int] = mapped_column(primary_key=True)
    pay_date: Mapped[date] = mapped_column(index=True)

    # Amount received (non-taxable)
    amount: Mapped[Decimal] = mapped_column()

    # Source description for categorization
    # Example values: "Non-taxable benefit", "SSA Disability", "Child Support"
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        source = f" ({self.source_type})" if self.source_type else ""
        return f"<NonTaxableIncome(date={self.pay_date}, amount=${self.amount}{source})>"


# Database setup - async engine and session factory
def create_async_session_factory(
    database_url: str | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the given database URL.

    Args:
        database_url: Database URL. If None, uses settings.database_url

    Returns:
        Async session factory
    """
    url = database_url or settings.database_url
    eng = create_async_engine(url, echo=False)
    return async_sessionmaker(
        eng, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
    )


# Default async engine and session factory
# For SQLite: pool settings are ignored (uses NullPool)
# For PostgreSQL/MySQL: these settings optimize connection handling
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
)
