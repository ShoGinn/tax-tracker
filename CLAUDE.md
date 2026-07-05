# Tax Tracker

Personal federal tax calculation and W-4 optimization system. FastAPI backend with SQLAlchemy/SQLite. Tracks W-2 paychecks, 1099-R pension income, and non-taxable income (VA disability, etc.) to calculate federal tax liability, reconcile withholding, and optimize W-4 settings.

## Development Status

This project is actively developed and currently versioned as v1.0.0.

- **Internal compatibility is not required.** APIs, models, schemas, and data formats may be restructured when the design improves.
- **Prefer clean design over compatibility shims.** If a better approach exists, refactor instead of adding adapters or legacy wrappers.
- **Breaking changes are acceptable during active development.** Prioritize correctness and maintainability.
- Remove dead code, legacy validators, and format converters when found rather than maintaining them.

## Project Direction

- **Frontend UI** — React 19 + TypeScript + Vite SPA in `frontend/`, served by FastAPI from `frontend/dist` when built
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
- **Non-taxable income** — VA disability, SSA disability, gifts — tracked for household totals and W-4 calculations

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
- just for task recipes and local CI-style workflows
- Ruff for linting/formatting, ty for type checking
- React 19 + TypeScript + Vite (SPA in `frontend/`), pnpm, Oxc (`oxlint`/`oxfmt`), Vitest + React Testing Library

## Commands

Preferred workflow uses just recipes:

- `just install` — install project and dev dependencies
- `just run` — run API with project defaults
- `just test` — run full test suite (80% coverage minimum enforced)
- `just test-unit` — unit tests only
- `just test-integration` — integration tests only
- `just test-fast` — skip slow tests
- `just lint` — run Ruff checks
- `just lint-fix` — auto-fix Ruff issues
- `just format` — format with Ruff
- `just format-check` — formatting check only
- `just typecheck` — run ty static checks
- `just security` — run dependency vulnerability scan
- `just psl-snapshot years="2025 2026"` — refresh PSLmodels cross-validation snapshot
- `just psl-draft year=YYYY` — generate draft tax data files from PSLmodels
- `just test-psl` — run PSLmodels cross-validation tests
- `just check` — local fast quality gate (format-check, lint, typecheck, test-fast, frontend-check)
- `just ci` — local full CI gate (lint, typecheck, full tests, frontend-check)

Frontend-specific recipes (run from repo root via just):

- `just frontend-install` — install pnpm dependencies
- `just frontend-dev` — start Vite dev server (proxies API to `http://127.0.0.1:8000`)
- `just frontend-build` — production build to `frontend/dist`
- `just frontend-test` — run frontend unit/component tests (Vitest)
- `just frontend-check` — lint + typecheck + test + build (Oxc + tsc + Vitest + vite)
- `just frontend-lint` / `just frontend-lint-fix` / `just frontend-format` — Oxc wrappers

CI/CD expectations:

- `.github/workflows/ci.yml` includes a dedicated `frontend-check` job (pnpm install, lint, typecheck, test, build)
- The `release` job depends on `frontend-check` in addition to backend gates
- `.github/dependabot.yml` includes npm updates for `/frontend` plus uv and GitHub Actions updates

Direct uv equivalents remain valid when needed:

- `uv run pytest`
- `uv run ruff check src/ tests/ scripts/`
- `uv run ty check`

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
justfile           # Canonical developer task recipes
pyproject.toml     # Tooling config: pytest, ruff, ty, package metadata
```

## Architecture

Layered: API routes -> Services (business logic) -> Models/DB. Dependency injection via FastAPI `Depends()` for DB sessions and tax data loading. All DB operations are async.

`src/taxtracker/cli/app.py` wires the FastAPI app, middleware, exception handlers, and route inclusion.

Key domain concept: three income types with different tax treatments:
- **W-2 (Paycheck)** — subject to income tax + FICA, has pre/post-tax deductions
- **1099-R (Retirement)** — subject to income tax only (no FICA)
- **Non-taxable** — VA disability, SSA, gifts — tracked but not taxed

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

## Data Provenance and Validation

Tax bracket and FICA data is **manually extracted** from IRS publications and cross-referenced against independent sources. Each data file includes a `citations` object with per-section IRS source URLs and a `verified_date`.

**Primary sources:**
- 2025: IRS Rev. Proc. 2024-40 + OBBB Act (PL 119-21) — https://www.irs.gov/filing/federal-income-tax-rates-and-brackets
- 2026: IRS Rev. Proc. 2025-32 — https://www.irs.gov/pub/irs-drop/rp-25-32.pdf
- FICA: SSA contribution base — https://www.ssa.gov/oact/cola/cbbdet.html

**Cross-references:** PSLmodels Tax-Calculator `policy_current_law.json`, Tax Foundation, IRS Tax Withholding Estimator

**Automated validation:**
- `tests/unit/test_irs_data_validation.py` — asserts every value in data files matches IRS-published constants (run: `uv run pytest tests/unit/test_irs_data_validation.py -v`)
- `tests/unit/test_irs_calculation_verification.py` — end-to-end calculation tests with hand-computed audit trails
- `tests/unit/test_irs_examples_comprehensive.py` — broader IRS scenario coverage
- `tests/unit/test_tax_calculator_irs_data.py` and `tests/unit/test_tax_calculator_2026.py` — tax calculator behavior and year-specific verification
- `tests/unit/test_real_world_2026_data.py` — real-world 2026 validation cases
- `tests/unit/test_w4_calculator.py` and `tests/unit/test_w4_withholding.py` — W-4 recommendation and withholding math coverage

**Full documentation:** `docs/irs_data_sources.md` (per-value citations), `docs/annual_tax_data_update.md` (how to add new tax years)

When working with tax data, always cite the specific IRS source document and cross-check values.

## Critical Rules

- **Always run quality checks after code changes.** At minimum run `just check` before finishing any change.
- **For frontend changes, also run `just frontend-check`.** If the change touches tax math, W-4 logic, projections, or other high-risk calculations, prefer `just ci` before handing it off.
- **Every logic component must have comprehensive tests.** This is tax/finance software — calculations must be verified against IRS data.
- **Frontend changes require frontend tests when behavior changes.** Add/adjust Vitest + React Testing Library tests and run `just frontend-check`.
- **Tests must verify correct behavior, not be adjusted to match incorrect code.** Do not create trivial tests or modify IRS-validated assertions to make failing tests pass. Fix the implementation. If unsure, ask for guidance.
- **Keep README.md current.** Any change that affects behavior, setup, commands, supported features, or limitations must be reflected in `README.md` within the same change.
- **Update documentation whenever appropriate.** When code changes impact usage, APIs, architecture, workflows, tax-data updates, or contributor processes, update the relevant docs in `docs/` (and `README.md` when applicable) as part of the same task.
- **Be careful with tax calculations** (`src/taxtracker/services/tax_calculator.py`, `src/taxtracker/services/w4_calculator.py`, `src/taxtracker/services/w4_withholding.py`). These contain IRS-verified math. Changes require matching test updates with known-correct values.
- **Be careful with data files** (`src/taxtracker/data/tax_brackets_*.json`, `src/taxtracker/data/fica_limits_*.json`). These are sourced from IRS publications. Do not modify without IRS source verification.
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

Current repository includes `.claude/settings.local.json` for local tool permissions.

- Keep local permission allow/deny lists there.
- If team-wide plugin enablement is needed, add a project-level Claude settings file explicitly in a separate change.

## Conventions

- Line length: 120 characters
- Type hints on all functions (enforced by Ruff ANN rules with test-specific exceptions)
- Snake_case for all Python identifiers and JSON fields
- Async-first for all DB operations
- Custom exceptions in `core/exceptions.py` — use the hierarchy (TaxTrackerError base)
- Pydantic schemas for all API request/response validation
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
- Flexible date/decimal parsing via custom Annotated types in schemas
- Ruff configured in `pyproject.toml` with broad rule selection plus explicit ignore/per-file-ignore policy
- ty configured in `pyproject.toml`; use `just typecheck` (or `uv run ty check`) during verification

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
- Mid-year W-4 change optimization (planned; see `docs/mid_year_w4_change_optimization_plan.md`; until implemented, full-year assumption only)
- 1099-R distribution code handling (all distributions treated as taxable minus pre-tax deductions)
