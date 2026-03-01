# Tax Tracker

Personal federal tax calculation and W-4 optimization system. FastAPI backend with SQLAlchemy/SQLite. Tracks W-2 paychecks, 1099-R pension income, and non-taxable income (non-taxable benefit, etc.) to calculate federal tax liability, reconcile withholding, and optimize W-4 settings.

## Development Phase

This project is in initial development (pre-v1.0). Until we reach a stable release:
- **No backward compatibility required.** APIs, models, schemas, and data formats can be freely restructured.
- **Prefer clean design over compatibility shims.** If a better approach exists, refactor — don't add adapters or legacy wrappers.
- **Breaking changes are expected.** There are no external consumers of this API.
- Remove dead code, legacy validators, and format converters when found rather than maintaining them.

## Project Direction

- **Frontend UI** planned (tech stack TBD)
- **Multi-user** with data segregation (auth approach TBD)
- **New tax years** added annually — this is the primary ongoing expansion
- **State taxes are out of scope** — federal only

## Features

### Income Tracking (three data entry modes)

1. **Detailed paycheck entry** — enter each paycheck with full breakdowns (gross, all pre-tax deductions, post-tax deductions, each tax withheld). System computes taxable wages, net pay, and all totals automatically.
2. **Direct/summary calculation** — skip the database entirely. Enter gross income, filing status, and deduction info to `POST /taxes/calculate` for an instant tax liability result.
3. **CSV bulk import** — upload CSV files for paychecks, pensions, or VA income. Flexible column mapping, auto-employer creation, handles currency symbols and multiple date formats.

### Income types
- **W-2 Paychecks** — full deduction modeling (401k, HSA, FSA, health/dental/vision, commuter, Roth, etc.)
- **1099-R Pension/Retirement** — gross distributions with pre-tax deductions (SBP, insurance), federal withholding
- **Non-taxable income** — non-taxable benefit, SSA disability, gifts — tracked for household totals and W-4 calculations

### Tax Calculation
- Federal income tax with bracket-by-bracket breakdown
- FICA: Social Security (capped at wage base), Medicare, Additional Medicare
- Child tax credits
- Standard or itemized deductions (with age 65+ additional amounts)
- Effective and marginal tax rates
- **Database reconciliation** — compare calculated liability vs. actual withholding → refund or amount owed

### W-4 Optimization
- Optimize W-4 settings to target a specific refund amount (default $0 = break even)
- Outputs step-by-step W-4 form recommendations (Steps 2, 3, 4a-c)
- Per-paycheck withholding calculator (IRS Publication 15-T percentage method)
- Annual withholding estimator

### Tax Projections
- Project future year tax liability from expected income
- Year-over-year comparison (income change, tax change, rate changes)
- Database-driven projections using historical pension/VA averages

### Data Management
- Employer CRUD with cascade to paychecks
- Full CRUD for all income types with year filtering
- YTD summary aggregation across all income sources
- Custom tax bracket and FICA data upload per year

## Tech Stack

- Python 3.14, FastAPI, SQLAlchemy (async), aiosqlite/SQLite
- Pydantic v2 for validation and schemas
- uv for dependency management
- Ruff for linting/formatting, ty for type checking

## Commands

- `uv run pytest` — run full test suite (80% coverage minimum enforced)
- `uv run pytest tests/unit` — unit tests only
- `uv run pytest tests/integration` — integration tests only
- `uv run pytest -m "not slow"` — skip slow tests
- `uv run ruff check src/ tests/` — lint
- `uv run ruff format src/ tests/` — format
- `uv run ruff check --fix src/ tests/` — auto-fix lint issues

## Project Structure

```
src/taxtracker/
├── api/          # FastAPI route handlers (income, taxes, w4, projections)
├── cli/          # App factory and uvicorn entry point
├── core/         # Config (Pydantic Settings) and custom exceptions
├── data/         # JSON tax bracket and FICA data files (IRS-sourced)
├── models/       # SQLAlchemy ORM models (database.py), Pydantic schemas (schemas.py), tax domain models (tax_data.py)
├── services/     # Business logic — tax calculation, W-4 optimization, income CRUD, CSV import, projections
tests/
├── unit/         # Service-level tests with IRS-verified data
├── integration/  # Full API endpoint tests via TestClient
├── fixtures/     # IRS test data (irs_test_data.py)
├── data/         # Test scenario JSON files
```

## Architecture

Layered: API routes → Services (business logic) → Models/DB. Dependency injection via FastAPI `Depends()` for DB sessions and tax data loading. All DB operations are async.

Key domain concept: three income types with different tax treatments:
- **W-2 (Paycheck)** — subject to income tax + FICA, has pre/post-tax deductions
- **1099-R (Retirement)** — subject to income tax only (no FICA)
- **Non-taxable** — non-taxable benefit, SSA, gifts — tracked but not taxed

Tax brackets use pre-computed cumulative tax for O(1) bracket lookups.

## Tax Calculation Flow

The calculation order matters — deductions are critical:

1. **Gross Income** (W-2 wages + pension distributions)
2. **Minus pre-tax deductions** (401k, insurance, HSA, etc.) → gives W-2 taxable wages
3. **AGI** = W-2 taxable wages + pension taxable amount - retirement pre-tax deductions
4. **Minus standard deduction or itemized deduction** (either/or, not both) → gives **taxable income**
5. **Apply tax brackets** to taxable income → federal tax
6. **Minus child tax credits** → federal tax liability
7. **Plus FICA** (on W-2 wages only, not pension) → total tax liability

Standard deductions are defined per filing status in the JSON data files and include age 65+ additional amounts. Itemized deductions are accepted as a single total (no category breakdown yet). The `use_standard_deduction` flag on TaxCalculationRequest controls which path is used.

## IRS Data Validation (Active Problem)

Tax bracket and FICA data is currently added **manually** from IRS publications. Current sources noted in the JSON files:
- 2025: IRS Revenue Procedure 2024-40 + One Big Beautiful Bill Act
- 2026: IRS Publication RP-25-32 (manually parsed)

**Current state:** No automated validation. Data accuracy is not independently verified. We need to:
- Establish a reliable process for sourcing and validating IRS data each year
- Document exactly where each number comes from (publication, table, line)
- Build automated checks to validate data against known IRS examples
- Cross-reference test expected values against IRS publications

When working with tax data, always cite the specific IRS source document and cross-check values.

## Critical Rules

- **Always run tests and lint after code changes.** Run `uv run pytest` and `uv run ruff check src/ tests/` to verify.
- **Every logic component must have comprehensive tests.** This is tax/finance software — calculations must be verified against IRS data.
- **Tests must verify correct behavior, not be adjusted to match incorrect code.** Do not create trivial tests or modify IRS-validated assertions to make failing tests pass. Fix the implementation. If unsure, ask for guidance.
- **Be careful with tax calculations** (`services/tax_calculator.py`, `services/w4_calculator.py`, `services/w4_withholding.py`). These contain IRS-verified math. Changes require matching test updates with known-correct values.
- **Be careful with data files** (`data/tax_brackets_*.json`, `data/fica_limits_*.json`). These are sourced from IRS publications. Do not modify without IRS source verification.
- **Suggest commits** after completing tasks but don't auto-commit. Use conventional commit format: `type: message` (e.g., `feat:`, `fix:`, `chore:`, `test:`, `refactor:`).
- **State taxes are out of scope.** Do not add state tax logic.

## Claude Code Plugins — Astral Tools

This project uses Astral's Claude Code plugin for best-practice guidance on ruff, uv, and ty. Invoke the relevant skill when working with these tools:

- `/astral:ruff` — guidance on linting and formatting
- `/astral:uv` — guidance on dependency management, project setup, scripts
- `/astral:ty` — guidance on type checking

### Setup (one-time per developer)

```shell
# Add the Astral marketplace
/plugin marketplace add astral-sh/claude-code-plugins

# Install the Astral plugin
/plugin install astral@astral-sh
```

Or use `/plugin` interactively → Discover tab → search "astral".

### Project-level config

The plugin can be enabled for all contributors via `.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "astral@astral-sh": true
  }
}
```

## Conventions

- Line length: 100 characters
- Type hints on all functions (enforced by Ruff ANN rules)
- Snake_case for all Python identifiers and JSON fields
- Async-first for all DB operations
- Custom exceptions in `core/exceptions.py` — use the hierarchy (TaxTrackerError base)
- Pydantic schemas for all API request/response validation
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
- Flexible date/decimal parsing via custom Annotated types in schemas

## Known Limitations / Out of Scope

The following IRS features are **not supported** and should not be added without explicit discussion:
- AMT (Alternative Minimum Tax)
- NIIT (Net Investment Income Tax, 3.8%)
- Self-employment tax / 1099-NEC income
- Qualified dividends / capital gains preferential rates
- Stock options (ISOs/NSOs), RSUs
- Rental income / Schedule C
- Education credits (AOTC, Lifetime Learning)
- EITC (Earned Income Tax Credit)
- Quarterly estimated tax payments
- Mid-year W-4 change optimization (full-year assumption only)
- 1099-R distribution code handling (all distributions treated as taxable minus pre-tax deductions)
