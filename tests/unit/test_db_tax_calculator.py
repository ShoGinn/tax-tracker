"""Tests for database tax calculator service."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from taxtracker.models.database import Employer, NonTaxableIncome, Paycheck, Retirement1099R
from taxtracker.models.tax_data import FilingStatus
from taxtracker.services.db_tax_calculator import (
    DatabaseTaxCalculation,
    calculate_taxes_from_database,
)
from taxtracker.services.tax_calculator import TaxCalculator


@pytest.mark.unit
class TestDatabaseTaxCalculation:
    """Tests for DatabaseTaxCalculation class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        calc = DatabaseTaxCalculation(
            year=2030,
            filing_status="single",
            num_children=0,
            w2_gross=Decimal("75000"),
            w2_pretax_deductions=Decimal("5000"),
            w2_taxable=Decimal("70000"),
            pension_gross=Decimal("0"),
            pension_pretax_deductions=Decimal("0"),
            pension_taxable=Decimal("0"),
            va_disability=Decimal("0"),
            agi=Decimal("70000"),
            deduction_amount=Decimal("15750"),
            deduction_type="Standard",
            taxable_income=Decimal("54250"),
            federal_tax_before_credits=Decimal("7000"),
            child_tax_credits=Decimal("0"),
            federal_tax_liability=Decimal("7000"),
            fica_liability=Decimal("5738"),
            total_tax_liability=Decimal("12738"),
            federal_withheld=Decimal("7500"),
            fica_withheld=Decimal("5738"),
            total_withheld=Decimal("13238"),
            refund_or_owed=Decimal("500"),
            overpayment_percentage=Decimal("3.9"),
            federal_tax_breakdown=[],
            fica_breakdown={},
            marginal_rate=Decimal("22"),
            effective_rate=Decimal("12.9"),
        )

        result = calc.to_dict()

        # Verify structure (actual keys from the implementation)
        assert "year" in result
        assert "filing_status" in result
        assert "income_summary" in result  # NOT "income"
        assert "tax_calculation" in result  # NOT "deductions" and "taxes"
        assert "withholdings" in result
        assert "result" in result
        assert "details" in result

        # Verify income_summary section
        assert "w2" in result["income_summary"]
        assert float(result["income_summary"]["w2"]["gross"]) == 75000.0
        assert float(result["income_summary"]["w2"]["taxable"]) == 70000.0

        # Verify result message exists
        assert "message" in result["result"]

    def test_result_message_overpayment(self):
        """Test result message for overpayment."""
        calc = DatabaseTaxCalculation(
            year=2030,
            filing_status="single",
            num_children=0,
            w2_gross=Decimal("75000"),
            w2_pretax_deductions=Decimal("0"),
            w2_taxable=Decimal("75000"),
            pension_gross=Decimal("0"),
            pension_pretax_deductions=Decimal("0"),
            pension_taxable=Decimal("0"),
            va_disability=Decimal("0"),
            agi=Decimal("75000"),
            deduction_amount=Decimal("15750"),
            deduction_type="Standard",
            taxable_income=Decimal("59250"),
            federal_tax_before_credits=Decimal("8000"),
            child_tax_credits=Decimal("0"),
            federal_tax_liability=Decimal("8000"),
            fica_liability=Decimal("5738"),
            total_tax_liability=Decimal("13738"),
            federal_withheld=Decimal("9000"),
            fica_withheld=Decimal("5738"),
            total_withheld=Decimal("14738"),
            refund_or_owed=Decimal("1001"),  # Overpaid by $1000
            overpayment_percentage=Decimal("7.3"),
            federal_tax_breakdown=[],
            fica_breakdown={},
            marginal_rate=Decimal("22"),
            effective_rate=Decimal("12"),
        )

        result = calc.to_dict()
        message = result["result"]["message"]

        assert "overpaid" in message.lower()
        assert "1,001" in message
        assert "7.3%" in message

    def test_result_message_underpayment(self):
        """Test result message for underpayment."""
        calc = DatabaseTaxCalculation(
            year=2030,
            filing_status="single",
            num_children=0,
            w2_gross=Decimal("75000"),
            w2_pretax_deductions=Decimal("0"),
            w2_taxable=Decimal("75000"),
            pension_gross=Decimal("0"),
            pension_pretax_deductions=Decimal("0"),
            pension_taxable=Decimal("0"),
            va_disability=Decimal("0"),
            agi=Decimal("75000"),
            deduction_amount=Decimal("15750"),
            deduction_type="Standard",
            taxable_income=Decimal("59250"),
            federal_tax_before_credits=Decimal("8000"),
            child_tax_credits=Decimal("0"),
            federal_tax_liability=Decimal("8000"),
            fica_liability=Decimal("5738"),
            total_tax_liability=Decimal("13738"),
            federal_withheld=Decimal("7000"),
            fica_withheld=Decimal("5738"),
            total_withheld=Decimal("12738"),
            refund_or_owed=Decimal("-1001"),  # Owe $1000
            overpayment_percentage=Decimal("0"),
            federal_tax_breakdown=[],
            fica_breakdown={},
            marginal_rate=Decimal("22"),
            effective_rate=Decimal("12"),
        )

        result = calc.to_dict()
        message = result["result"]["message"]

        assert "owe" in message.lower()
        assert "1,001" in message

    def test_result_message_perfect(self):
        """Test result message for perfect withholding."""
        calc = DatabaseTaxCalculation(
            year=2030,
            filing_status="single",
            num_children=0,
            w2_gross=Decimal("75000"),
            w2_pretax_deductions=Decimal("0"),
            w2_taxable=Decimal("75000"),
            pension_gross=Decimal("0"),
            pension_pretax_deductions=Decimal("0"),
            pension_taxable=Decimal("0"),
            va_disability=Decimal("0"),
            agi=Decimal("75000"),
            deduction_amount=Decimal("15750"),
            deduction_type="Standard",
            taxable_income=Decimal("59250"),
            federal_tax_before_credits=Decimal("8000"),
            child_tax_credits=Decimal("0"),
            federal_tax_liability=Decimal("8000"),
            fica_liability=Decimal("5738"),
            total_tax_liability=Decimal("13738"),
            federal_withheld=Decimal("8050"),
            fica_withheld=Decimal("5738"),
            total_withheld=Decimal("13788"),
            refund_or_owed=Decimal("50"),  # Within +/-$100
            overpayment_percentage=Decimal("0.4"),
            federal_tax_breakdown=[],
            fica_breakdown={},
            marginal_rate=Decimal("22"),
            effective_rate=Decimal("12"),
        )

        result = calc.to_dict()
        message = result["result"]["message"]

        assert "perfect" in message.lower() or "spot-on" in message.lower()


@pytest.mark.integration
class TestCalculateTaxesFromDatabase:
    """Integration tests for calculate_taxes_from_database."""

    async def test_calculate_with_w2_only(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with only W-2 income."""
        # Set up employer and paycheck
        employer = Employer(name="Test Corp", ein="12-3456789", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(
            employer_id=employer.id,
            pay_date=date(2030, 6, 15),
            gross_wages=Decimal("5000"),
            deduction_401k=Decimal("500"),
            federal_withholding=Decimal("600"),
            social_security=Decimal("310"),
            medicare=Decimal("72.50"),
        )
        async_db_session.add(paycheck)
        await async_db_session.commit()

        # Calculate taxes
        # Use test_calculator fixture
        result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2030,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            use_standard_deduction=True,
        )

        # Verify result
        assert isinstance(result, DatabaseTaxCalculation)
        assert result.year == 2030
        assert result.filing_status == "single"
        assert float(result.w2_gross) == 5000.0
        assert float(result.w2_pretax_deductions) == 500.0
        assert float(result.federal_withheld) == 600.0

        # Verify has to_dict
        result_dict = result.to_dict()
        assert "income_summary" in result_dict
        assert "tax_calculation" in result_dict

    async def test_calculate_with_pension(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with pension income."""
        pension = Retirement1099R(
            pay_date=date(2030, 1, 1),
            gross_amount=Decimal("3000"),
            pretax_deductions=Decimal("300"),
            federal_withholding=Decimal("350"),
        )
        async_db_session.add(pension)
        await async_db_session.commit()

        # Use test_calculator fixture
        result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2030,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=0,
        )

        assert float(result.pension_gross) == 3000.0
        assert float(result.pension_pretax_deductions) == 300.0
        assert float(result.pension_taxable) == 2700.0

    async def test_calculate_with_va_disability(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with VA disability (non-taxable)."""
        # VA disability alone is not taxable income, so we need some W2 income too
        employer = Employer(name="Test Corp", ein="12-3456789", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(
            employer_id=employer.id, pay_date=date(2030, 6, 15), gross_wages=Decimal("3000")
        )
        async_db_session.add(paycheck)

        non_taxable_payment = NonTaxableIncome(
            pay_date=date(2030, 1, 1), amount=Decimal("2000"), notes="Monthly disability"
        )
        async_db_session.add(non_taxable_payment)
        await async_db_session.commit()

        # Use test_calculator fixture
        result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2030,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
        )

        # VA disability should be recorded but not taxable
        assert float(result.va_disability) == 2000.0

    async def test_calculate_with_children(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with child tax credits."""
        employer = Employer(name="Family Test Corp", ein="98-7654321", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(
            employer_id=employer.id,
            pay_date=date(2030, 6, 15),
            gross_wages=Decimal("8000"),
            federal_withholding=Decimal("1000"),
            social_security=Decimal("496"),
            medicare=Decimal("116"),
        )
        async_db_session.add(paycheck)
        await async_db_session.commit()

        # Use test_calculator fixture
        result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2030,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
            num_children=2,  # 2 children
        )

        # Should have child tax credits
        assert result.num_children == 2
        assert float(result.child_tax_credits) > 0

    async def test_calculate_with_itemized_deductions(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with itemized deductions."""
        employer = Employer(
            name="High Deduction Corp", ein="11-2233445", start_date=date(2030, 1, 1)
        )
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(
            employer_id=employer.id,
            pay_date=date(2030, 6, 15),
            gross_wages=Decimal("12000"),
            federal_withholding=Decimal("1800"),
            social_security=Decimal("744"),
            medicare=Decimal("174"),
        )
        async_db_session.add(paycheck)
        await async_db_session.commit()

        # Use test_calculator fixture
        result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2030,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            use_standard_deduction=False,
            itemized_deductions=25000.0,  # High itemized deductions
        )

        # Should use itemized deductions
        assert "Itemized" in result.deduction_type
        assert float(result.deduction_amount) == 25000.0

    async def test_calculate_multiple_paychecks(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with multiple paychecks (YTD total)."""
        employer = Employer(
            name="Multi Paycheck Corp", ein="55-6677889", start_date=date(2030, 1, 1)
        )
        async_db_session.add(employer)
        await async_db_session.commit()

        # Add multiple paychecks
        for month in range(1, 7):  # Jan through June
            paycheck = Paycheck(
                employer_id=employer.id,
                pay_date=date(2030, month, 15),
                gross_wages=Decimal("5000"),
                deduction_401k=Decimal("500"),
                federal_withholding=Decimal("600"),
                social_security=Decimal("310"),
                medicare=Decimal("72.50"),
            )
            async_db_session.add(paycheck)
        await async_db_session.commit()

        # Use test_calculator fixture
        result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2030,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
        )

        # Should sum all paychecks
        assert float(result.w2_gross) == 30000.0  # 6 x $5000
        assert float(result.w2_pretax_deductions) == 3000.0  # 6 x $500
        assert float(result.federal_withheld) == 3600.0  # 6 x $600

    async def test_calculate_empty_database(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with no income records - should fail validation."""
        from pydantic import ValidationError

        # Use test_calculator fixture

        # Should raise validation error because gross_income must be > 0
        with pytest.raises(ValidationError) as exc_info:
            await calculate_taxes_from_database(
                db=async_db_session,
                year=2030,
                tax_calculator=test_calculator,
                filing_status=FilingStatus.SINGLE,
                num_children=0,
            )

        # Verify it's the gross_income validation
        assert "gross_income" in str(exc_info.value)
