"""Comprehensive tests for income_service CRUD operations."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from taxtracker.models.schemas import (
    EmployerCreate,
    EmployerUpdate,
    NonTaxableIncomeCreate,
    NonTaxableIncomeUpdate,
    PaycheckCreate,
    PaycheckUpdate,
    Retirement1099RCreate,
    Retirement1099RUpdate,
)
from taxtracker.services import income_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestEmployerService:
    """Test employer CRUD operations."""

    async def test_create_employer(self, async_db_session: AsyncSession):
        """Test creating an employer."""
        employer_data = EmployerCreate(
            name="Test Company",
            ein="12-3456789",
            start_date=date(2024, 1, 1),
            notes="Test employer",
        )

        employer = await income_service.create_employer(async_db_session, employer_data)

        assert employer.id is not None
        assert employer.name == "Test Company"
        assert employer.ein == "12-3456789"
        assert employer.start_date == date(2024, 1, 1)
        assert employer.notes == "Test employer"

    async def test_get_employer(self, async_db_session: AsyncSession):
        """Test retrieving an employer by ID."""
        # Create employer first
        employer_data = EmployerCreate(
            name="Get Test", ein="11-1111111", start_date=date(2024, 1, 1)
        )
        created = await income_service.create_employer(async_db_session, employer_data)

        # Retrieve it
        retrieved = await income_service.get_employer(async_db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Get Test"

    async def test_get_employer_not_found(self, async_db_session: AsyncSession):
        """Test retrieving non-existent employer."""
        result = await income_service.get_employer(async_db_session, 99999)
        assert result is None

    async def test_get_employers(self, async_db_session: AsyncSession):
        """Test listing all employers."""
        # Create multiple employers
        for i in range(3):
            employer_data = EmployerCreate(
                name=f"Company {i}", ein=f"1{i}-1111111", start_date=date(2024, 1, i + 1)
            )
            await income_service.create_employer(async_db_session, employer_data)

        employers = await income_service.get_employers(async_db_session)

        assert len(employers) >= 3

    async def test_update_employer(self, async_db_session: AsyncSession):
        """Test updating an employer."""
        # Create employer
        employer_data = EmployerCreate(
            name="Update Test", ein="22-2222222", start_date=date(2024, 1, 1)
        )
        created = await income_service.create_employer(async_db_session, employer_data)

        # Update it
        update_data = EmployerUpdate(name="Updated Name", notes="Updated notes")
        updated = await income_service.update_employer(async_db_session, created.id, update_data)

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.notes == "Updated notes"
        assert updated.ein == "22-2222222"  # Unchanged

    async def test_delete_employer(self, async_db_session: AsyncSession):
        """Test deleting an employer."""
        # Create employer
        employer_data = EmployerCreate(
            name="Delete Test", ein="33-3333333", start_date=date(2024, 1, 1)
        )
        created = await income_service.create_employer(async_db_session, employer_data)

        # Delete it
        result = await income_service.delete_employer(async_db_session, created.id)
        assert result is True

        # Verify it's gone
        retrieved = await income_service.get_employer(async_db_session, created.id)
        assert retrieved is None


class TestPaycheckService:
    """Test paycheck CRUD operations."""

    async def test_create_paycheck(self, async_db_session: AsyncSession):
        """Test creating a paycheck."""
        # Create employer first
        employer = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="Paycheck Test", ein="44-4444444", start_date=date(2024, 1, 1)),
        )

        paycheck_data = PaycheckCreate(
            employer_id=employer.id,
            pay_date=date(2024, 6, 15),
            gross_wages=Decimal(5000),
            federal_withholding=Decimal(750),
            social_security=Decimal(310),
            medicare=Decimal("72.50"),
            state_withholding=Decimal(200),
        )

        paycheck = await income_service.create_paycheck(async_db_session, paycheck_data)

        assert paycheck.id is not None
        assert paycheck.employer_id == employer.id
        assert paycheck.gross_wages == Decimal(5000)
        assert paycheck.net_pay == Decimal("3667.50")

    async def test_get_paycheck(self, async_db_session: AsyncSession):
        """Test retrieving a paycheck."""
        employer = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="Get Paycheck", ein="55-5555555", start_date=date(2024, 1, 1)),
        )

        paycheck_data = PaycheckCreate(
            employer_id=employer.id,
            pay_date=date(2024, 6, 15),
            gross_wages=Decimal(4000),
        )
        created = await income_service.create_paycheck(async_db_session, paycheck_data)

        retrieved = await income_service.get_paycheck(async_db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.gross_wages == Decimal(4000)

    async def test_get_paychecks(self, async_db_session: AsyncSession):
        """Test listing paychecks."""
        employer = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="List Test", ein="66-6666666", start_date=date(2024, 1, 1)),
        )

        # Create multiple paychecks
        for i in range(3):
            paycheck_data = PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, i + 1),
                gross_wages=Decimal(4000),
            )
            await income_service.create_paycheck(async_db_session, paycheck_data)

        paychecks = await income_service.get_paychecks(async_db_session)

        assert len(paychecks) >= 3

    async def test_get_paychecks_by_employer(self, async_db_session: AsyncSession):
        """Test filtering paychecks by employer."""
        employer1 = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="Employer A", ein="77-7777777", start_date=date(2024, 1, 1)),
        )
        employer2 = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="Employer B", ein="88-8888888", start_date=date(2024, 1, 1)),
        )

        # Create paychecks for employer1
        for i in range(2):
            await income_service.create_paycheck(
                async_db_session,
                PaycheckCreate(
                    employer_id=employer1.id,
                    pay_date=date(2024, 6, i + 1),
                    gross_wages=Decimal(4000),
                ),
            )

        # Create paycheck for employer2
        await income_service.create_paycheck(
            async_db_session,
            PaycheckCreate(
                employer_id=employer2.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal(5000),
            ),
        )

        # Filter by employer1
        paychecks = await income_service.get_paychecks(async_db_session, employer_id=employer1.id)

        assert len(paychecks) == 2
        assert all(p.employer_id == employer1.id for p in paychecks)

    async def test_get_paychecks_by_year(self, async_db_session: AsyncSession):
        """Test filtering paychecks by year."""
        employer = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="Year Test", ein="99-9999999", start_date=date(2024, 1, 1)),
        )

        # Create paychecks in different years
        await income_service.create_paycheck(
            async_db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal(4000),
            ),
        )
        await income_service.create_paycheck(
            async_db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2025, 6, 1),
                gross_wages=Decimal(4500),
            ),
        )

        # Filter by 2024
        paychecks_2024 = await income_service.get_paychecks(async_db_session, year=2024)
        assert len(paychecks_2024) >= 1
        assert all(p.pay_date.year == 2024 for p in paychecks_2024)

    async def test_update_paycheck(self, async_db_session: AsyncSession):
        """Test updating a paycheck."""
        employer = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="Update Paycheck", ein="10-1010101", start_date=date(2024, 1, 1)),
        )

        created = await income_service.create_paycheck(
            async_db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal(4000),
            ),
        )

        # Update it
        update_data = PaycheckUpdate(gross_wages=Decimal(4500), notes="Updated")
        updated = await income_service.update_paycheck(async_db_session, created.id, update_data)

        assert updated is not None
        assert updated.gross_wages == Decimal(4500)
        assert updated.notes == "Updated"
        assert updated.net_pay == Decimal(4500)  # Automatically computed from new gross_wages

    async def test_delete_paycheck(self, async_db_session: AsyncSession):
        """Test deleting a paycheck."""
        employer = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="Delete Paycheck", ein="11-1212121", start_date=date(2024, 1, 1)),
        )

        created = await income_service.create_paycheck(
            async_db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal(4000),
            ),
        )

        result = await income_service.delete_paycheck(async_db_session, created.id)
        assert result is True

        retrieved = await income_service.get_paycheck(async_db_session, created.id)
        assert retrieved is None


class TestRetirement1099RService:
    """Test 1099-R retirement income CRUD operations."""

    async def test_create_retirement_1099r(self, async_db_session: AsyncSession):
        """Test creating 1099-R income."""
        data = Retirement1099RCreate(
            pay_date=date(2024, 6, 1),
            gross_amount=Decimal(5000),
            pretax_deductions=Decimal(500),
            federal_withholding=Decimal(600),
            source_description="Military Pension",
        )

        retirement = await income_service.create_retirement_1099r(async_db_session, data)

        assert retirement.id is not None
        assert retirement.gross_amount == Decimal(5000)
        assert retirement.pretax_deductions == Decimal(500)
        assert retirement.taxable_amount == Decimal(4500)  # 5000 - 500

    async def test_get_retirement_1099r(self, async_db_session: AsyncSession):
        """Test retrieving 1099-R income."""
        created = await income_service.create_retirement_1099r(
            async_db_session,
            Retirement1099RCreate(pay_date=date(2024, 6, 1), gross_amount=Decimal(5000)),
        )

        retrieved = await income_service.get_retirement_1099r(async_db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    async def test_get_retirement_1099rs(self, async_db_session: AsyncSession):
        """Test listing 1099-R income."""
        for i in range(3):
            await income_service.create_retirement_1099r(
                async_db_session,
                Retirement1099RCreate(
                    pay_date=date(2024, 6, i + 1),
                    gross_amount=Decimal(5000),
                ),
            )

        entries = await income_service.get_retirement_1099rs(async_db_session)
        assert len(entries) >= 3

    async def test_get_retirement_1099rs_by_year(self, async_db_session: AsyncSession):
        """Test filtering 1099-R by year."""
        await income_service.create_retirement_1099r(
            async_db_session,
            Retirement1099RCreate(pay_date=date(2024, 6, 1), gross_amount=Decimal(5000)),
        )
        await income_service.create_retirement_1099r(
            async_db_session,
            Retirement1099RCreate(pay_date=date(2025, 6, 1), gross_amount=Decimal(5500)),
        )

        entries_2024 = await income_service.get_retirement_1099rs(async_db_session, year=2024)
        assert len(entries_2024) >= 1
        assert all(e.pay_date.year == 2024 for e in entries_2024)

    async def test_update_retirement_1099r(self, async_db_session: AsyncSession):
        """Test updating 1099-R income."""
        created = await income_service.create_retirement_1099r(
            async_db_session,
            Retirement1099RCreate(pay_date=date(2024, 6, 1), gross_amount=Decimal(5000)),
        )

        update_data = Retirement1099RUpdate(gross_amount=Decimal(5500), notes="Updated")
        updated = await income_service.update_retirement_1099r(
            async_db_session, created.id, update_data
        )

        assert updated is not None
        assert updated.gross_amount == Decimal(5500)
        assert updated.notes == "Updated"

    async def test_delete_retirement_1099r(self, async_db_session: AsyncSession):
        """Test deleting 1099-R income."""
        created = await income_service.create_retirement_1099r(
            async_db_session,
            Retirement1099RCreate(pay_date=date(2024, 6, 1), gross_amount=Decimal(5000)),
        )

        result = await income_service.delete_retirement_1099r(async_db_session, created.id)
        assert result is True

        retrieved = await income_service.get_retirement_1099r(async_db_session, created.id)
        assert retrieved is None


class TestNonTaxableIncomeService:
    """Test non-taxable income CRUD operations."""

    async def test_create_non_taxable_income(self, async_db_session: AsyncSession):
        """Test creating non-taxable income."""
        data = NonTaxableIncomeCreate(
            pay_date=date(2024, 6, 1),
            amount=Decimal(3000),
            source_type="VA Disability",
            notes="Monthly payment",
        )

        income = await income_service.create_non_taxable_payment(async_db_session, data)

        assert income.id is not None
        assert income.amount == Decimal(3000)
        assert income.source_type == "VA Disability"

    async def test_get_non_taxable_income(self, async_db_session: AsyncSession):
        """Test retrieving non-taxable income."""
        created = await income_service.create_non_taxable_payment(
            async_db_session,
            NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal(3000)),
        )

        retrieved = await income_service.get_non_taxable_payment(async_db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    async def test_get_non_taxable_payments(self, async_db_session: AsyncSession):
        """Test listing non-taxable income."""
        for i in range(3):
            await income_service.create_non_taxable_payment(
                async_db_session,
                NonTaxableIncomeCreate(pay_date=date(2024, 6, i + 1), amount=Decimal(3000)),
            )

        entries = await income_service.get_non_taxable_payments(async_db_session)
        assert len(entries) >= 3

    async def test_get_non_taxable_payments_by_year(self, async_db_session: AsyncSession):
        """Test filtering non-taxable income by year."""
        await income_service.create_non_taxable_payment(
            async_db_session,
            NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal(3000)),
        )
        await income_service.create_non_taxable_payment(
            async_db_session,
            NonTaxableIncomeCreate(pay_date=date(2025, 6, 1), amount=Decimal(3200)),
        )

        entries_2024 = await income_service.get_non_taxable_payments(async_db_session, year=2024)
        assert len(entries_2024) >= 1
        assert all(e.pay_date.year == 2024 for e in entries_2024)

    async def test_update_non_taxable_income(self, async_db_session: AsyncSession):
        """Test updating non-taxable income."""
        created = await income_service.create_non_taxable_payment(
            async_db_session,
            NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal(3000)),
        )

        update_data = NonTaxableIncomeUpdate(amount=Decimal(3200), source_type="SSA Disability")
        updated = await income_service.update_non_taxable_payment(
            async_db_session, created.id, update_data
        )

        assert updated is not None
        assert updated.amount == Decimal(3200)
        assert updated.source_type == "SSA Disability"

    async def test_delete_non_taxable_income(self, async_db_session: AsyncSession):
        """Test deleting non-taxable income."""
        created = await income_service.create_non_taxable_payment(
            async_db_session,
            NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal(3000)),
        )

        result = await income_service.delete_non_taxable_payment(async_db_session, created.id)
        assert result is True

        retrieved = await income_service.get_non_taxable_payment(async_db_session, created.id)
        assert retrieved is None


class TestYTDSummary:
    """Test YTD summary calculation."""

    async def test_ytd_summary(self, async_db_session: AsyncSession):
        """Test YTD summary with all income types."""
        # Create employer and paychecks
        employer = await income_service.create_employer(
            async_db_session,
            EmployerCreate(name="YTD Test", ein="13-1313131", start_date=date(2024, 1, 1)),
        )

        await income_service.create_paycheck(
            async_db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal(5000),
                federal_withholding=Decimal(750),
                social_security=Decimal(310),
                medicare=Decimal("72.50"),
            ),
        )

        # Create 1099-R income
        await income_service.create_retirement_1099r(
            async_db_session,
            Retirement1099RCreate(
                pay_date=date(2024, 6, 1),
                gross_amount=Decimal(4000),
                pretax_deductions=Decimal(400),
                federal_withholding=Decimal(500),
            ),
        )

        # Create non-taxable income
        await income_service.create_non_taxable_payment(
            async_db_session,
            NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal(3000)),
        )

        # Get YTD summary
        summary = await income_service.get_ytd_summary(async_db_session, 2024)

        assert summary.total_w2_gross == Decimal(5000)
        assert summary.total_pension_gross == Decimal(4000)
        assert summary.total_pension_pretax_deductions == Decimal(400)
        assert summary.total_pension_taxable == Decimal(3600)
        assert summary.total_non_taxable_income == Decimal(3000)
        assert summary.total_federal_withheld == Decimal(1250)  # 750 + 500
        assert summary.total_w2_fica_withheld == Decimal("382.50")  # 310 + 72.50
