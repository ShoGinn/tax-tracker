# Annual Tax Data Update Checklist

Step-by-step process for adding a new tax year's data to the system.

## Timeline

The IRS typically publishes inflation-adjusted tax parameters in **October** for the following tax year (via Revenue Procedures). SSA announces the Social Security wage base around the same time.

## Steps

### 1. Locate IRS Revenue Procedure

- Check https://www.irs.gov/pub/irs-drop/ for the new Revenue Procedure (e.g., `rp-YY-NN.pdf`)
- The IRS.gov brackets page consolidates all filing statuses: https://www.irs.gov/filing/federal-income-tax-rates-and-brackets
- Note any legislative changes (like OBBB Act) that may override standard inflation adjustments

### 2. Locate SSA Wage Base Announcement

- Check https://www.ssa.gov/oact/cola/cbbdet.html for the new contribution and benefit base
- This determines the Social Security wage base limit

### 3. Create Tax Brackets Data File

Create `src/taxtracker/data/tax_brackets_YYYY.json`:

```json
{
    "tax_year": YYYY,
    "last_updated": "YYYY-MM-DD",
    "source": "IRS Revenue Procedure YYYY-NN",
    "notes": "",
    "citations": {
        "tax_brackets": "https://www.irs.gov/filing/federal-income-tax-rates-and-brackets",
        "standard_deductions": "<IRS source URL>",
        "child_tax_credit": "<IRS source URL>",
        "revenue_procedure": "<IRS RP URL>"
    },
    "verified_date": "YYYY-MM-DD",
    "tax_brackets": {
        "married_filing_jointly": [...],
        "single": [...],
        "married_filing_separately": [...],
        "head_of_household": [...]
    },
    "standard_deductions": {
        "amounts": {...},
        "additional_age_65_plus": {...}
    },
    "child_tax_credit": {
        "amount_per_child": ...,
        "refundable_portion": ...,
        "phase_out_threshold": {...}
    }
}
```

### 4. Create FICA Limits Data File

Create `src/taxtracker/data/fica_limits_YYYY.json`:

```json
{
    "tax_year": YYYY,
    "last_updated": "YYYY-MM-DD",
    "source": "Social Security Administration + IRS Topic 751",
    "citations": {
        "social_security_wage_base": "https://www.ssa.gov/oact/cola/cbbdet.html",
        "fica_rates": "https://www.irs.gov/taxtopics/tc751",
        "additional_medicare": "https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax"
    },
    "verified_date": "YYYY-MM-DD",
    "social_security": {
        "employee_rate": 0.062,
        "employer_rate": 0.062,
        "total_rate": 0.124,
        "wage_base_limit": ...,
        "max_employee_tax": ...,
        "max_employer_tax": ...,
        "max_combined_tax": ...
    },
    "medicare": {...},
    "additional_medicare": {...},
    "combined_rates": {...}
}
```

**Compute max taxes**: `max_employee_tax = wage_base_limit * 0.062`

### 5. Cross-Verify Every Value

Check each value against:

1. **Primary**: IRS Revenue Procedure PDF (table by table)
2. **Cross-ref**: PSLmodels Tax-Calculator `policy_current_law.json` (if updated for the year)
3. **Secondary**: Tax Foundation article for the new year

Key verification checks:
- [ ] All 4 filing statuses present
- [ ] 7 brackets per status (10%, 12%, 22%, 24%, 32%, 35%, 37%)
- [ ] MFS matches Single except 35% bracket (MFS 35% = MFJ 35% / 2)
- [ ] Thresholds are monotonically increasing
- [ ] SS `max_employee_tax == wage_base_limit * employee_rate`
- [ ] SS `max_combined_tax == max_employee_tax * 2`
- [ ] Additional Medicare thresholds unchanged (not indexed for inflation)
- [ ] CTC amount matches current law

### 6. Add Validation Test Class

Add a new test class in `tests/unit/test_irs_data_validation.py`:

```python
class TestTaxBracketsYYYY:
    """Validate YYYY tax bracket data against IRS Rev. Proc. YYYY-NN."""

    @pytest.fixture(autouse=True)
    def _load_data(self) -> None:
        self.data = load_tax_brackets_model(YYYY)

    def test_mfj_10_threshold(self) -> None:
        assert self.data.tax_brackets["married_filing_jointly"][0].threshold == Decimal(...)
    # ... etc for all brackets, deductions, CTC
```

Add the year to existing parametrized structural tests in `TestDataIntegrity`.

### 7. Add Calculation Verification Scenarios

Add at least 2-3 calculation scenarios to `tests/unit/test_irs_calculation_verification.py`:
- Single filer with standard deduction
- MFJ with children
- FICA at the new wage base

### 8. Update Documentation

- Add the new year to `docs/irs_data_sources.md` with full citation tables
- Update `test_scenarios.json` if needed

### 9. Run Full Test Suite

```bash
# Validation tests (quick check)
uv run pytest tests/unit/test_irs_data_validation.py -v

# Calculation verification
uv run pytest tests/unit/test_irs_calculation_verification.py -v

# Full suite
uv run pytest

# Lint
uv run ruff check src/ tests/
```

### 10. Manual Spot-Check

Run at least one withholding scenario through the IRS Tax Withholding Estimator:
https://apps.irs.gov/app/tax-withholding-estimator

Compare the output against the system's calculation for the same inputs.

## Common Pitfalls

- **MFJ 12% bracket**: Double-check this threshold carefully. It's commonly misread from IRS tables.
- **OBBB Act overrides**: For 2025-2028, the OBBB Act modified standard deductions and CTC beyond normal inflation adjustments. Check for similar legislative overrides.
- **MFS vs Single**: MFS should match Single for all brackets EXCEPT the 35% bracket (which is half of MFJ).
- **Additional Medicare thresholds**: These are statutory ($200k/$250k/$125k) and do NOT adjust for inflation.
- **CTC refundable portion**: This is a separate amount from the total per-child credit.
