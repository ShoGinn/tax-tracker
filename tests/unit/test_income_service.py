"""Comprehensive tests for income_service CRUD operations."""

from datetime import date
from decimal import Decimal

import pytest
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
)
from taxtracker.services import income_service


class TestEmployerService:
    """Test employer CRUD operations."""

    def test_create_employer(self, db_session: Session):
        """Test creating an employer."""
        employer_data = EmployerCreate(
            name="Test Company",
            ein="12-3456789",
            start_date=date(2024, 1, 1),
            notes="Test employer",
        )

        employer = income_service.create_employer(db_session, employer_data)

        assert employer.id is not None
        assert employer.name == "Test Company"
        assert employer.ein == "12-3456789"
        assert employer.start_date == date(2024, 1, 1)
        assert employer.notes == "Test employer"

    def test_get_employer(self, db_session: Session):
        """Test retrieving an employer by ID."""
        # Create employer first
        employer_data = EmployerCreate(
            name="Get Test", ein="11-1111111", start_date=date(2024, 1, 1)
        )
        created = income_service.create_employer(db_session, employer_data)

        # Retrieve it
        retrieved = income_service.get_employer(db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Get Test"

    def test_get_employer_not_found(self, db_session: Session):
        """Test retrieving non-existent employer."""
        result = income_service.get_employer(db_session, 99999)
        assert result is None

    def test_get_employers(self, db_session: Session):
        """Test listing all employers."""
        # Create multiple employers
        for i in range(3):
            employer_data = EmployerCreate(
                name=f"Company {i}", ein=f"1{i}-1111111", start_date=date(2024, 1, i + 1)
            )
            income_service.create_employer(db_session, employer_data)

        employers = income_service.get_employers(db_session)

        assert len(employers) >= 3

    def test_update_employer(self, db_session: Session):
        """Test updating an employer."""
        # Create employer
        employer_data = EmployerCreate(
            name="Update Test", ein="22-2222222", start_date=date(2024, 1, 1)
        )
        created = income_service.create_employer(db_session, employer_data)

        # Update it
        update_data = EmployerUpdate(name="Updated Name", notes="Updated notes")
        updated = income_service.update_employer(db_session, created.id, update_data)

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.notes == "Updated notes"
        assert updated.ein == "22-2222222"  # Unchanged

    def test_delete_employer(self, db_session: Session):
        """Test deleting an employer."""
        # Create employer
        employer_data = EmployerCreate(
            name="Delete Test", ein="33-3333333", start_date=date(2024, 1, 1)
        )
        created = income_service.create_employer(db_session, employer_data)

        # Delete it
        result = income_service.delete_employer(db_session, created.id)
        assert result is True

        # Verify it's gone
        retrieved = income_service.get_employer(db_session, created.id)
        assert retrieved is None


class TestPaycheckService:
    """Test paycheck CRUD operations."""

    def test_create_paycheck(self, db_session: Session):
        """Test creating a paycheck."""
        # Create employer first
        employer = income_service.create_employer(
            db_session,
            EmployerCreate(name="Paycheck Test", ein="44-4444444", start_date=date(2024, 1, 1)),
        )

        paycheck_data = PaycheckCreate(
            employer_id=employer.id,
            pay_date=date(2024, 6, 15),
            gross_wages=Decimal("5000"),
            federal_withholding=Decimal("750"),
            social_security=Decimal("310"),
            medicare=Decimal("72.50"),
            state_withholding=Decimal("200"),
            net_pay=Decimal("3667.50"),
        )

        paycheck = income_service.create_paycheck(db_session, paycheck_data)

        assert paycheck.id is not None
        assert paycheck.employer_id == employer.id
        assert paycheck.gross_wages == Decimal("5000")
        assert paycheck.net_pay == Decimal("3667.50")

    def test_get_paycheck(self, db_session: Session):
        """Test retrieving a paycheck."""
        employer = income_service.create_employer(
            db_session,
            EmployerCreate(name="Get Paycheck", ein="55-5555555", start_date=date(2024, 1, 1)),
        )

        paycheck_data = PaycheckCreate(
            employer_id=employer.id,
            pay_date=date(2024, 6, 15),
            gross_wages=Decimal("4000"),
            net_pay=Decimal("3000"),
        )
        created = income_service.create_paycheck(db_session, paycheck_data)

        retrieved = income_service.get_paycheck(db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.gross_wages == Decimal("4000")

    def test_get_paychecks(self, db_session: Session):
        """Test listing paychecks."""
        employer = income_service.create_employer(
            db_session,
            EmployerCreate(name="List Test", ein="66-6666666", start_date=date(2024, 1, 1)),
        )

        # Create multiple paychecks
        for i in range(3):
            paycheck_data = PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, i + 1),
                gross_wages=Decimal("4000"),
                net_pay=Decimal("3000"),
            )
            income_service.create_paycheck(db_session, paycheck_data)

        paychecks = income_service.get_paychecks(db_session)

        assert len(paychecks) >= 3

    def test_get_paychecks_by_employer(self, db_session: Session):
        """Test filtering paychecks by employer."""
        employer1 = income_service.create_employer(
            db_session,
            EmployerCreate(name="Employer A", ein="77-7777777", start_date=date(2024, 1, 1)),
        )
        employer2 = income_service.create_employer(
            db_session,
            EmployerCreate(name="Employer B", ein="88-8888888", start_date=date(2024, 1, 1)),
        )

        # Create paychecks for employer1
        for i in range(2):
            income_service.create_paycheck(
                db_session,
                PaycheckCreate(
                    employer_id=employer1.id,
                    pay_date=date(2024, 6, i + 1),
                    gross_wages=Decimal("4000"),
                    net_pay=Decimal("3000"),
                ),
            )

        # Create paycheck for employer2
        income_service.create_paycheck(
            db_session,
            PaycheckCreate(
                employer_id=employer2.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal("5000"),
                net_pay=Decimal("4000"),
            ),
        )

        # Filter by employer1
        paychecks = income_service.get_paychecks(db_session, employer_id=employer1.id)

        assert len(paychecks) == 2
        assert all(p.employer_id == employer1.id for p in paychecks)

    def test_get_paychecks_by_year(self, db_session: Session):
        """Test filtering paychecks by year."""
        employer = income_service.create_employer(
            db_session,
            EmployerCreate(name="Year Test", ein="99-9999999", start_date=date(2024, 1, 1)),
        )

        # Create paychecks in different years
        income_service.create_paycheck(
            db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal("4000"),
                net_pay=Decimal("3000"),
            ),
        )
        income_service.create_paycheck(
            db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2025, 6, 1),
                gross_wages=Decimal("4500"),
                net_pay=Decimal("3500"),
            ),
        )

        # Filter by 2024
        paychecks_2024 = income_service.get_paychecks(db_session, year=2024)
        assert len(paychecks_2024) >= 1
        assert all(p.pay_date.year == 2024 for p in paychecks_2024)

    def test_update_paycheck(self, db_session: Session):
        """Test updating a paycheck."""
        employer = income_service.create_employer(
            db_session,
            EmployerCreate(name="Update Paycheck", ein="10-1010101", start_date=date(2024, 1, 1)),
        )

        created = income_service.create_paycheck(
            db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal("4000"),
                net_pay=Decimal("3000"),
            ),
        )

        # Update it
        update_data = PaycheckUpdate(gross_wages=Decimal("4500"), notes="Updated")
        updated = income_service.update_paycheck(db_session, created.id, update_data)

        assert updated is not None
        assert updated.gross_wages == Decimal("4500")
        assert updated.notes == "Updated"
        assert updated.net_pay == Decimal("3000")  # Unchanged

    def test_delete_paycheck(self, db_session: Session):
        """Test deleting a paycheck."""
        employer = income_service.create_employer(
            db_session,
            EmployerCreate(name="Delete Paycheck", ein="11-1212121", start_date=date(2024, 1, 1)),
        )

        created = income_service.create_paycheck(
            db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal("4000"),
                net_pay=Decimal("3000"),
            ),
        )

        result = income_service.delete_paycheck(db_session, created.id)
        assert result is True

        retrieved = income_service.get_paycheck(db_session, created.id)
        assert retrieved is None


class TestRetirement1099RService:
    """Test 1099-R retirement income CRUD operations."""

    def test_create_retirement_1099r(self, db_session: Session):
        """Test creating 1099-R income."""
        data = Retirement1099RCreate(
            pay_date=date(2024, 6, 1),
            gross_amount=Decimal("5000"),
            pretax_deductions=Decimal("500"),
            federal_withholding=Decimal("600"),
            net_amount=Decimal("3900"),
            source_description="Military Pension",
        )

        retirement = income_service.create_retirement_1099r(db_session, data)

        assert retirement.id is not None
        assert retirement.gross_amount == Decimal("5000")
        assert retirement.pretax_deductions == Decimal("500")
        assert retirement.taxable_amount == Decimal("4500")  # 5000 - 500

    def test_get_retirement_1099r(self, db_session: Session):
        """Test retrieving 1099-R income."""
        created = income_service.create_retirement_1099r(
            db_session,
            Retirement1099RCreate(
                pay_date=date(2024, 6, 1), gross_amount=Decimal("5000"), net_amount=Decimal("4000")
            ),
        )

        retrieved = income_service.get_retirement_1099r(db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_retirement_1099rs(self, db_session: Session):
        """Test listing 1099-R income."""
        for i in range(3):
            income_service.create_retirement_1099r(
                db_session,
                Retirement1099RCreate(
                    pay_date=date(2024, 6, i + 1),
                    gross_amount=Decimal("5000"),
                    net_amount=Decimal("4000"),
                ),
            )

        entries = income_service.get_retirement_1099rs(db_session)
        assert len(entries) >= 3

    def test_get_retirement_1099rs_by_year(self, db_session: Session):
        """Test filtering 1099-R by year."""
        income_service.create_retirement_1099r(
            db_session,
            Retirement1099RCreate(
                pay_date=date(2024, 6, 1), gross_amount=Decimal("5000"), net_amount=Decimal("4000")
            ),
        )
        income_service.create_retirement_1099r(
            db_session,
            Retirement1099RCreate(
                pay_date=date(2025, 6, 1), gross_amount=Decimal("5500"), net_amount=Decimal("4500")
            ),
        )

        entries_2024 = income_service.get_retirement_1099rs(db_session, year=2024)
        assert len(entries_2024) >= 1
        assert all(e.pay_date.year == 2024 for e in entries_2024)

    def test_update_retirement_1099r(self, db_session: Session):
        """Test updating 1099-R income."""
        created = income_service.create_retirement_1099r(
            db_session,
            Retirement1099RCreate(
                pay_date=date(2024, 6, 1), gross_amount=Decimal("5000"), net_amount=Decimal("4000")
            ),
        )

        update_data = Retirement1099RUpdate(gross_amount=Decimal("5500"), notes="Updated")
        updated = income_service.update_retirement_1099r(db_session, created.id, update_data)

        assert updated is not None
        assert updated.gross_amount == Decimal("5500")
        assert updated.notes == "Updated"

    def test_delete_retirement_1099r(self, db_session: Session):
        """Test deleting 1099-R income."""
        created = income_service.create_retirement_1099r(
            db_session,
            Retirement1099RCreate(
                pay_date=date(2024, 6, 1), gross_amount=Decimal("5000"), net_amount=Decimal("4000")
            ),
        )

        result = income_service.delete_retirement_1099r(db_session, created.id)
        assert result is True

        retrieved = income_service.get_retirement_1099r(db_session, created.id)
        assert retrieved is None


class TestNonTaxableIncomeService:
    """Test non-taxable income CRUD operations."""

    def test_create_non_taxable_income(self, db_session: Session):
        """Test creating non-taxable income."""
        data = NonTaxableIncomeCreate(
            pay_date=date(2024, 6, 1),
            amount=Decimal("3000"),
            source_type="VA Disability",
            notes="Monthly payment",
        )

        income = income_service.create_non_taxable_payment(db_session, data)

        assert income.id is not None
        assert income.amount == Decimal("3000")
        assert income.source_type == "VA Disability"

    def test_get_non_taxable_income(self, db_session: Session):
        """Test retrieving non-taxable income."""
        created = income_service.create_non_taxable_payment(
            db_session, NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal("3000"))
        )

        retrieved = income_service.get_non_taxable_payment(db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_non_taxable_payments(self, db_session: Session):
        """Test listing non-taxable income."""
        for i in range(3):
            income_service.create_non_taxable_payment(
                db_session,
                NonTaxableIncomeCreate(pay_date=date(2024, 6, i + 1), amount=Decimal("3000")),
            )

        entries = income_service.get_non_taxable_payments(db_session)
        assert len(entries) >= 3

    def test_get_non_taxable_payments_by_year(self, db_session: Session):
        """Test filtering non-taxable income by year."""
        income_service.create_non_taxable_payment(
            db_session, NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal("3000"))
        )
        income_service.create_non_taxable_payment(
            db_session, NonTaxableIncomeCreate(pay_date=date(2025, 6, 1), amount=Decimal("3200"))
        )

        entries_2024 = income_service.get_non_taxable_payments(db_session, year=2024)
        assert len(entries_2024) >= 1
        assert all(e.pay_date.year == 2024 for e in entries_2024)

    def test_update_non_taxable_income(self, db_session: Session):
        """Test updating non-taxable income."""
        created = income_service.create_non_taxable_payment(
            db_session, NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal("3000"))
        )

        update_data = NonTaxableIncomeUpdate(amount=Decimal("3200"), source_type="SSA Disability")
        updated = income_service.update_non_taxable_payment(db_session, created.id, update_data)

        assert updated is not None
        assert updated.amount == Decimal("3200")
        assert updated.source_type == "SSA Disability"

    def test_delete_non_taxable_income(self, db_session: Session):
        """Test deleting non-taxable income."""
        created = income_service.create_non_taxable_payment(
            db_session, NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal("3000"))
        )

        result = income_service.delete_non_taxable_payment(db_session, created.id)
        assert result is True

        retrieved = income_service.get_non_taxable_payment(db_session, created.id)
        assert retrieved is None


class TestYTDSummary:
    """Test YTD summary calculation."""

    def test_ytd_summary(self, db_session: Session):
        """Test YTD summary with all income types."""
        # Create employer and paychecks
        employer = income_service.create_employer(
            db_session,
            EmployerCreate(name="YTD Test", ein="13-1313131", start_date=date(2024, 1, 1)),
        )

        income_service.create_paycheck(
            db_session,
            PaycheckCreate(
                employer_id=employer.id,
                pay_date=date(2024, 6, 1),
                gross_wages=Decimal("5000"),
                federal_withholding=Decimal("750"),
                social_security=Decimal("310"),
                medicare=Decimal("72.50"),
                net_pay=Decimal("3867.50"),
            ),
        )

        # Create 1099-R income
        income_service.create_retirement_1099r(
            db_session,
            Retirement1099RCreate(
                pay_date=date(2024, 6, 1),
                gross_amount=Decimal("4000"),
                pretax_deductions=Decimal("400"),
                federal_withholding=Decimal("500"),
                net_amount=Decimal("3100"),
            ),
        )

        # Create non-taxable income
        income_service.create_non_taxable_payment(
            db_session, NonTaxableIncomeCreate(pay_date=date(2024, 6, 1), amount=Decimal("3000"))
        )

        # Get YTD summary
        summary = income_service.get_ytd_summary(db_session, 2024)

        assert summary.total_w2_gross == Decimal("5000")
        assert summary.total_pension_gross == Decimal("4000")
        assert summary.total_pension_pretax_deductions == Decimal("400")
        assert summary.total_pension_taxable == Decimal("3600")
        assert summary.total_va_disability == Decimal("3000")
        assert summary.total_federal_withheld == Decimal("1250")  # 750 + 500
        assert summary.total_w2_fica_withheld == Decimal("382.50")  # 310 + 72.50
