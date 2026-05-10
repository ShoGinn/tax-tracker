"""Tests for database tax calculator service."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from taxtracker.models.database import Employer, NonTaxableIncome, Paycheck, Retirement1099R
from taxtracker.models.tax_data import (
    FilingStatus,
    TaxCalculationRequest,
    TaxReconciliationResponse,
)
from taxtracker.services.db_tax_calculator import calculate_taxes_from_database

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from taxtracker.services.tax_calculator import TaxCalculator


@pytest.mark.unit
class TestTaxReconciliationResponse:
    """Unit-level checks for the unified reconciliation model."""

    def test_refund_status_and_combined_liability(self):
        resp = TaxReconciliationResponse(
            tax_year=2030,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            gross_income=Decimal(70000),
            retirement_pretax_deductions=Decimal(0),
            adjusted_gross_income=Decimal(70000),
            deduction_amount=Decimal(15750),
            deduction_type="Standard Deduction",
            taxable_income=Decimal(54250),
            federal_tax_owed=Decimal(7000),
            child_tax_credits=Decimal(0),
            total_tax_liability=Decimal(7000),
            effective_tax_rate=Decimal(10),
            marginal_tax_rate=Decimal(22),
            breakdown_by_bracket=[],
            fica_taxes={"total_fica": Decimal(5738)},
            total_household_income=Decimal(70000),
            notes=[],
            w2_gross=Decimal(75000),
            w2_pretax_deductions=Decimal(5000),
            w2_taxable=Decimal(70000),
            pension_gross=Decimal(0),
            pension_pretax_deductions=Decimal(0),
            pension_taxable=Decimal(0),
            non_taxable_income=Decimal(0),
            total_taxable_income=Decimal(70000),
            total_federal_withheld=Decimal(7500),
            total_fica_withheld=Decimal(5738),
            total_withheld=Decimal(13238),
            combined_liability=Decimal(12738),
            refund_or_owed=Decimal(500),
            overpayment_percentage=Decimal("3.9"),
            result_status="REFUND",
        )

        assert resp.result_status == "REFUND"
        assert resp.combined_liability == Decimal(12738)
        assert resp.total_withheld - resp.combined_liability == resp.refund_or_owed


@pytest.mark.integration
class TestCalculateTaxesFromDatabase:
    """Integration tests for calculate_taxes_from_database."""

    async def test_calculate_with_w2_only(self, async_db_session: AsyncSession, test_calculator: TaxCalculator):
        """Test calculation with only W-2 income."""
        # Set up employer and paycheck
        employer = Employer(name="Test Corp", ein="12-3456789", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(
            employer_id=employer.id,
            pay_date=date(2030, 6, 15),
            gross_wages=Decimal(5000),
            deduction_401k=Decimal(500),
            federal_withholding=Decimal(600),
            social_security=Decimal(310),
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
        assert isinstance(result, TaxReconciliationResponse)
        assert result.tax_year == 2030
        assert result.filing_status == FilingStatus.SINGLE
        assert float(result.w2_gross) == 5000.0
        assert float(result.w2_pretax_deductions) == 500.0
        assert float(result.total_federal_withheld) == 600.0

    async def test_cross_check_db_vs_manual(self, async_db_session: AsyncSession, test_calculator: TaxCalculator):
        """Cross-check DB aggregation vs direct calculator+FICA for parity."""

        employer = Employer(name="Parity Corp", ein="22-3334444", start_date=date(2024, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        # Two paychecks on different dates
        for day in (1, 15):
            paycheck = Paycheck(
                employer_id=employer.id,
                pay_date=date(2024, 2, day),
                gross_wages=Decimal(5000),
                federal_withholding=Decimal(600),
                social_security=Decimal(310),
                medicare=Decimal("72.50"),
            )
            async_db_session.add(paycheck)
        await async_db_session.commit()

        # Run DB-based calc
        db_result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2024,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
            use_standard_deduction=True,
        )

        # Manual calculation with same inputs
        manual_request = TaxCalculationRequest(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            w2_gross_income=Decimal(10000),  # two paychecks, no pretax deductions
            num_children=0,
            use_standard_deduction=True,
        )
        manual_tax = test_calculator.calculate_taxes(manual_request)
        manual_fica = test_calculator.calculate_fica(Decimal(10000), FilingStatus.SINGLE)
        manual_combined = manual_tax.total_tax_liability + manual_fica["total_fica"]
        manual_total_withheld = Decimal(1200) + Decimal(765)  # 1200 federal + 765 FICA
        manual_refund = manual_total_withheld - manual_combined

        assert db_result.combined_liability == manual_combined
        assert db_result.refund_or_owed == manual_refund

    async def test_calculate_with_pension(self, async_db_session: AsyncSession, test_calculator: TaxCalculator):
        """Test calculation with pension income."""
        pension = Retirement1099R(
            pay_date=date(2030, 1, 1),
            gross_amount=Decimal(3000),
            pretax_deductions=Decimal(300),
            federal_withholding=Decimal(350),
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

    async def test_calculate_with_non_taxable_income(
        self, async_db_session: AsyncSession, test_calculator: TaxCalculator
    ):
        """Test calculation with non-taxable income."""
        # Non-taxable income alone is not taxable income, so we need some W2 income too
        employer = Employer(name="Test Corp", ein="12-3456789", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(employer_id=employer.id, pay_date=date(2030, 6, 15), gross_wages=Decimal(3000))
        async_db_session.add(paycheck)

        non_taxable_payment = NonTaxableIncome(
            pay_date=date(2030, 1, 1), amount=Decimal(2000), notes="Monthly disability"
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

        # Non-taxable income should be recorded but not taxable
        assert float(result.non_taxable_income) == 2000.0

    async def test_calculate_with_children(self, async_db_session: AsyncSession, test_calculator: TaxCalculator):
        """Test calculation with child tax credits."""
        employer = Employer(name="Family Test Corp", ein="98-7654321", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(
            employer_id=employer.id,
            pay_date=date(2030, 6, 15),
            gross_wages=Decimal(8000),
            federal_withholding=Decimal(1000),
            social_security=Decimal(496),
            medicare=Decimal(116),
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
        employer = Employer(name="High Deduction Corp", ein="11-2233445", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        paycheck = Paycheck(
            employer_id=employer.id,
            pay_date=date(2030, 6, 15),
            gross_wages=Decimal(12000),
            federal_withholding=Decimal(1800),
            social_security=Decimal(744),
            medicare=Decimal(174),
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

    async def test_calculate_multiple_paychecks(self, async_db_session: AsyncSession, test_calculator: TaxCalculator):
        """Test calculation with multiple paychecks (YTD total)."""
        employer = Employer(name="Multi Paycheck Corp", ein="55-6677889", start_date=date(2030, 1, 1))
        async_db_session.add(employer)
        await async_db_session.commit()

        # Add multiple paychecks
        for month in range(1, 7):  # Jan through June
            paycheck = Paycheck(
                employer_id=employer.id,
                pay_date=date(2030, month, 15),
                gross_wages=Decimal(5000),
                deduction_401k=Decimal(500),
                federal_withholding=Decimal(600),
                social_security=Decimal(310),
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
        assert float(result.total_federal_withheld) == 3600.0  # 6 x $600

    async def test_calculate_empty_database(self, async_db_session: AsyncSession, test_calculator: TaxCalculator):
        """Test calculation with no income records - returns zero tax."""

        result = await calculate_taxes_from_database(
            db=async_db_session,
            year=2030,
            tax_calculator=test_calculator,
            filing_status=FilingStatus.SINGLE,
            num_children=0,
        )

        # With no income, everything should be zero
        assert result.gross_income == Decimal(0)
        assert result.taxable_income == Decimal(0)
        assert result.federal_tax_owed == Decimal(0)
        assert result.total_tax_liability == Decimal(0)
