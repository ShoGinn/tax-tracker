# Mid-Year W-4 Change Optimization Plan

## Purpose

Add support for W-4 optimization when withholding settings change partway through the tax year.

Current behavior assumes a single full-year withholding profile. This feature will model year-to-date actuals plus remaining-pay-period recommendations.

## Problem Statement

A full-year W-4 assumption can produce inaccurate recommendations when any of these occur during the year:

- Job change or additional job starts/stops
- Salary changes, bonus timing shifts, or pension changes
- Mid-year updates to filing status, credits, or deductions
- Delayed W-4 updates after major life events

The optimizer should answer:

- Given year-to-date actual withholding and income, what W-4 settings should be used for the remaining pay periods?
- How much additional withholding per remaining paycheck is needed to hit a target refund or balance due?

## Goals

- Support optimization from an as-of date within a tax year
- Use actual year-to-date values as fixed inputs
- Compute remaining withholding target and per-paycheck recommendation
- Return actionable W-4 step guidance and a paycheck-level withholding target
- Preserve existing full-year optimization behavior for current users

## Non-Goals (Initial Version)

- Employer-specific payroll edge cases beyond existing IRS percentage-method assumptions
- Dynamic future schedule simulation for irregular pay frequency changes
- Multi-scenario optimization UI (backend supports one request at a time)

## Definitions

- Year-to-date actuals: income, deductions, and federal withholding already realized
- Remaining horizon: pay periods from as-of date through year end
- Target outcome: desired refund amount (default 0 for break-even)

## Proposed API Design

### Option A (Recommended): Add New Endpoint

- POST /w4/optimize-midyear

Request shape:

- tax_year
- as_of_date
- filing_status and deduction preferences
- year_to_date inputs
- expected remaining income inputs
- remaining pay schedule assumptions
- target_refund

Response shape:

- projected total liability
- year-to-date withholding
- required remaining withholding total
- required withholding per remaining paycheck
- W-4 step recommendations for remaining checks
- explanatory breakdown and assumptions

Benefits:

- Keeps current endpoint behavior stable
- Clear separation of full-year and mid-year logic
- Easier to test and evolve

### Option B: Extend Existing Endpoint With Mode Flag

- POST /w4/optimize with mode = full_year or mid_year

Tradeoff:

- Smaller API surface but more conditional complexity

Recommendation: Option A for clarity during initial rollout.

## Domain Model And Schema Additions

Potential new schema models in models/schemas.py:

- MidYearW4OptimizationRequest
- YearToDateSnapshot
- RemainingPeriodAssumptions
- MidYearW4OptimizationResponse

Potential model fields:

- as_of_date
- ytd_w2_taxable_wages
- ytd_pension_taxable_income
- ytd_federal_withholding
- ytd_401k_contributions (if needed for parity with existing tax flow)
- remaining_pay_periods
- expected_taxable_wages_per_period
- expected_pension_taxable_per_period

Service additions in services/w4_calculator.py:

- optimize_midyear(...) entry point
- helper to compute remaining withholding requirement
- helper to convert remaining target into W-4 step recommendations

## Calculation Approach

1. Compute projected full-year taxable profile:
- projected_full_year = ytd_actuals + projected_remaining

2. Compute projected full-year tax liability using existing tax engine logic.

3. Compute withholding gap:
- withholding_gap = projected_tax_liability + target_refund - ytd_withholding

4. Clamp at lower bound where policy requires (for example no negative additional withholding recommendation).

5. Convert gap to remaining per-paycheck additional withholding:
- per_check_additional = withholding_gap / remaining_pay_periods

6. Map per-check recommendation into W-4 step guidance consistent with current optimizer conventions.

7. Return transparent breakdown for auditability.

## Integration Points

- services/tax_calculator.py for liability projection consistency
- services/w4_withholding.py for Publication 15-T withholding math
- api/w4.py for endpoint wiring
- tests/unit/test_w4_calculator.py and tests/unit/test_w4_withholding.py for correctness
- tests/integration/test_api_w4_extended.py for end-to-end behavior

## Validation Rules

- as_of_date must be within tax_year
- remaining_pay_periods must be >= 1
- year-to-date fields cannot be negative unless already supported by domain rules
- If remaining_pay_periods is 0, return a clear validation error
- Return assumptions and warning notes when projections rely on defaults

## Test Strategy

Add IRS-aligned and behavior-focused tests for:

- Baseline parity: mid-year at first pay period equals near full-year behavior
- Mid-year catch-up: under-withholding requires increased per-check withholding
- Mid-year over-withholding: recommendation trends toward reduced additional withholding
- Edge date cases: as_of_date near year-end
- Pension plus W-2 mixed income scenarios
- Regression tests to ensure existing full-year optimizer behavior does not change

## Delivery Plan

Phase 1: Design and schema

- Finalize endpoint contract and request/response models
- Add docs for assumptions and formulas

Phase 2: Service implementation

- Implement mid-year optimization function
- Reuse existing tax and withholding utilities where possible

Phase 3: API and tests

- Add endpoint and dependency wiring
- Add unit and integration tests with expected values

Phase 4: Documentation and examples

- Add README feature note and usage examples
- Add example payloads under docs or examples/

## Risks And Mitigations

Risk: Divergence from existing full-year formulas

- Mitigation: Reuse shared computation paths and add parity tests

Risk: User confusion about assumptions for remaining income

- Mitigation: Return explicit assumptions and provide example payloads

Risk: Insufficient edge-case coverage near year-end

- Mitigation: Add focused tests for small remaining pay-period counts

## Open Questions

- Should remaining pay schedule support variable per-period income in v1?
- Should recommendations be global or employer-specific when multiple jobs exist?
- How should bonus withholding assumptions be represented in the request model?
- Do we need separate handling for planned W-4 changes that start after the next payroll date?

## Definition Of Done For Initial Release

- New endpoint is implemented and documented
- Unit and integration tests pass with meaningful coverage
- Existing full-year W-4 optimization behavior remains stable
- README and relevant docs are updated with feature usage and limits
