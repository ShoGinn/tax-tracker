# Smoke Tests - Marked for Improvement

## Summary

**27 smoke tests** have been identified and marked with `@pytest.mark.skip(reason="Smoke test - needs specific assertions")`.

These tests use weak assertions like `assert response.status_code in [200, 400, 500]` which don't verify actual behavior.

## Current Test Status

```
✅ Real Tests: 152 passing (actual behavior verification)
⏭️  Smoke Tests: 27 skipped (weak assertions)
📊 Total: 179 tests
📈 Real Coverage: 79.35% (honest coverage from real tests only)
```

## Why These Are Skipped

**Smoke tests don't verify behavior, they only check "did it respond?"**

Example:
```python
@pytest.mark.skip(reason="Smoke test - needs specific assertions")
def test_import_csv_empty_content(self, client):
    files = {"file": ("test.csv", b"", "text/csv")}
    response = client.post("/income/paychecks/import-csv", files=files)
    
    # This accepts BOTH success AND error!
    assert response.status_code in [200, 400]  # ❌ MEANINGLESS
```

**Problems:**
- Would pass if endpoint returns 200 (success) OR 400 (error)
- Doesn't check what the response contains
- Doesn't verify the feature works correctly
- Gave false confidence that hid the itemized deduction bug

## Skipped Tests by File

### test_api_income.py (4 skipped)
- `test_import_csv_empty_content` - Accepts 200 or 400
- `test_import_csv_invalid_format` - Accepts 200 or 400
- `test_import_pension_csv` - Accepts 200, 400, or 422
- `test_import_va_csv` - Accepts 200, 400, or 422

### test_api_income_extended.py (3 skipped)
- `test_create_paycheck_invalid_employer` - Accepts 200 or 404
- `test_delete_nonexistent_paycheck` - Accepts 400, 404, or 422
- `test_update_paycheck_invalid_data` - Accepts 200, 400, or 422

### test_api_projections.py (6 skipped)
- `test_compare_years_with_raises` - Accepts 200, 404, or 500
- `test_project_from_database_basic` - Accepts 200, 404, or 500
- `test_project_invalid_filing_status` - Accepts 400, 422, or 500
- `test_project_negative_raises` - Accepts 400, 422, or 500
- `test_project_future_start` - Accepts 400, 422, or 500
- `test_compare_invalid_years` - Accepts 400, 422, or 500

### test_api_w4_extended.py (4 skipped)
- `test_optimize_zero_income` - Accepts 200, 400, or 422
- `test_optimize_invalid_filing_status` - Accepts 400, 422, or 500
- `test_withholding_invalid_frequency` - Accepts 200, 404, or 501
- `test_withholding_unsupported_frequency` - Accepts 200, 404, or 501

### test_api_admin.py (9 skipped)
- `test_validate_tax_brackets_endpoint` - Accepts 200, 400, 404, 405, or 501
- `test_upload_tax_data_valid` - Accepts 200, 404, 405, or 501
- `test_upload_tax_data_wrong_extension` - Accepts 200, 404, 405, or 501
- `test_upload_wrong_endpoint` - Accepts 400, 404, 405, or 501
- `test_upload_tax_data_malformed` - Accepts 400, 404, 405, 500, or 501
- `test_upload_fica_data_valid` - Accepts 200, 400, 404, 405, or 501
- `test_upload_fica_data_invalid` - Accepts 400, 422, 404, 405, or 501
- `test_validate_valid_brackets` - Accepts 200, 404, or 501
- `test_check_data_integrity` - Accepts 200, 404, or 501

### test_api_taxes.py (1 skipped)
- `test_calculate_from_database_empty` - Multi-branch logic, needs test data setup

## How to Fix These

### Option 1: Make Them Real Tests
```python
# BEFORE (smoke test)
@pytest.mark.skip(reason="Smoke test")
def test_import_csv_empty_content(self, client):
    files = {"file": ("test.csv", b"", "text/csv")}
    response = client.post("/income/paychecks/import-csv", files=files)
    assert response.status_code in [200, 400]  # ❌

# AFTER (real test)
def test_import_csv_empty_content(self, client):
    """Empty CSV should succeed with 0 rows processed."""
    files = {"file": ("test.csv", b"", "text/csv")}
    response = client.post("/income/paychecks/import-csv", files=files)
    
    assert response.status_code == 200  # ✅ Specific!
    data = response.json()
    assert data["total_rows"] == 0
    assert data["success_count"] == 0
    assert data["error_count"] == 0
    assert "successful" in data["message"].lower() or "failed" in data["message"].lower()
```

### Option 2: Delete Them
If they're not testing anything useful, just delete them:
- They don't verify behavior
- They give false confidence
- They waste test execution time
- They hide real bugs

## Next Steps

1. **Review each skipped test** - Does it test something useful?
2. **Fix or Delete** - Either make it a real test or remove it
3. **Document WHY** - If keeping it, explain what it verifies

## The Lesson

**From the Itemized Deduction Bug:**

We had smoke tests that passed but the feature was broken. The smoke tests gave false confidence and hid a critical bug.

**Better to have:**
- 152 real tests with 79% coverage
- Than 179 tests with 87% "coverage" where 27 tests don't verify anything

## Impact on Coverage

| Metric | With Smoke Tests | Without Smoke Tests | Change |
|--------|------------------|---------------------|--------|
| Tests Passing | 179 | 152 | -27 |
| Tests Skipped | 0 | 27 | +27 |
| Coverage | 87.25% | 79.35% | -7.9% |
| **Real Coverage** | **~79%** | **79.35%** | **Honest** |

The "coverage" with smoke tests was inflated. The real coverage is 79%.

## Recommendation

**Phase 1 (Now):** Skip smoke tests, be honest about coverage
**Phase 2 (Future):** Convert or delete smoke tests one by one

---

**Current Status: Smoke tests identified and skipped. Real coverage: 79.35%**
