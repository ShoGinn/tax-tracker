# Tax Tracker

Personal federal tax calculation and W-4 optimization system built with FastAPI.

Tax Tracker helps model W-2 paychecks, 1099-R pension income, and non-taxable income to calculate federal tax liability, reconcile withholding, and optimize W-4 settings.

## Table Of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [Development Commands](#development-commands)
- [API Capabilities](#api-capabilities)
- [Project Structure](#project-structure)
- [Tax Calculation Flow](#tax-calculation-flow)
- [Data Sources And Validation](#data-sources-and-validation)
- [Development Guidelines](#development-guidelines)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

## Overview

This project focuses on federal tax workflows only. It provides:

- Detailed paycheck-based modeling for real-world withholding reconciliation
- Direct calculation endpoints for quick what-if tax scenarios
- W-4 optimization to target a desired refund or balance due
- Year-over-year projections and annual tax data extensibility

The codebase is under active development and prioritizes correctness, maintainability, and verified tax logic over internal backward compatibility.

## Key Features

### Income Tracking

- Detailed paycheck entry with full deduction and withholding breakdown
- Summary tax calculation mode via request payloads
- CSV bulk import with flexible column mapping and date/currency normalization

### Supported Income Types

- W-2 paychecks with pre-tax and post-tax deductions
- 1099-R pension and retirement distributions
- Non-taxable income (for household totals and planning context)

### Tax And Withholding

- Federal bracket calculation with per-bracket breakdown
- FICA (Social Security, Medicare, Additional Medicare)
- Child tax credits
- Standard versus itemized deduction handling
- Withholding reconciliation (refund or amount owed)

### W-4 Optimization And Projections

- W-4 recommendation generation (steps 2, 3, 4a-4c)
- Mid-year W-4 optimization from database YTD paychecks with remaining-period projections
- Per-paycheck withholding estimator (IRS Publication 15-T method)
- Annual projections and year-over-year comparison

## Technology Stack

- Python 3.14
- FastAPI
- SQLAlchemy async ORM with SQLite and aiosqlite
- Pydantic v2
- React 19 + TypeScript + Vite (frontend in `frontend/`)
- uv for package and environment workflows
- just for local task automation
- Ruff for linting and formatting
- ty for static type checks
- pnpm for frontend package management
- Biome for frontend linting and formatting

## Quick Start

### Prerequisites

- Python 3.14
- uv
- just

### Setup

```bash
just install
```

### Run The API

```bash
just run
```

### Run The Frontend

```bash
just frontend-install
just frontend-dev
```

The frontend accepts `VITE_API_BASE_URL` for explicit API targets.
If not set, it uses same-origin requests and Vite dev proxy routes to `http://127.0.0.1:8000`.

## Development Commands

Preferred workflow uses just recipes:

```bash
just check          # fast quality gate: format-check, lint, typecheck, test-fast
just ci             # full local CI gate
just test           # full test suite (80% coverage minimum)
just test-unit
just test-integration
just test-fast
just lint
just lint-fix
just format
just format-check
just typecheck
just frontend-install
just frontend-dev
just frontend-build
just frontend-typecheck
just frontend-lint
just frontend-lint-fix
just frontend-format
just frontend-check
just security
just psl-snapshot years="2025 2026"
just psl-draft year=YYYY
just test-psl
```

Direct uv commands are also supported:

```bash
uv run pytest
uv run ruff check src/ tests/ scripts/
uv run ty check
```

### Automated PSL Snapshot Monitoring

This repository includes an automated monitor workflow at [`.github/workflows/pslmodels-snapshot-monitor.yml`](.github/workflows/pslmodels-snapshot-monitor.yml):

- Runs weekly and also supports manual execution via `workflow_dispatch`
- Regenerates `tests/data/pslmodels_snapshot.json` from PSLmodels
- Runs `tests/unit/test_pslmodels_cross_check.py`
- Opens or updates a pull request automatically only when tax values drift
- Ignores date-only `generated_date` churn to avoid noisy metadata-only PRs

The existing CI PSL check still runs on push and pull request, but now distinguishes tax-value drift from date-only metadata updates.

## API Capabilities

The service includes endpoints for:

- Income CRUD for employers, paychecks, retirement income, and non-taxable income
- Tax calculations from direct payload input
- Database-backed reconciliation of withholding versus liability
- W-4 optimization and withholding estimates
- Mid-year W-4 optimization from DB-backed YTD actuals via `POST /w4/optimize-midyear-from-db` with optional `as_of_date` cutoff
- Tax projections based on expected or historical income patterns

For implementation details and route handlers, see source packages under src/taxtracker/api.

## Project Structure

```text
src/taxtracker/
├── api/          # FastAPI route handlers
├── cli/          # app factory and entrypoint
├── core/         # config and exceptions
├── data/         # IRS-sourced tax and FICA JSON files
├── models/       # ORM and Pydantic models
├── services/     # tax, W-4, import, and projection logic
tests/
├── unit/
├── integration/
├── fixtures/
└── data/
```

## Tax Calculation Flow

The core flow is:

1. Gross income from taxable sources
2. Subtract eligible pre-tax deductions
3. Compute AGI
4. Apply standard or itemized deduction
5. Compute federal income tax by bracket
6. Apply child tax credits
7. Add FICA components where applicable

## Data Sources And Validation

Tax constants are manually curated from IRS publications and cross-checked with independent references.

Primary references:

- IRS federal tax bracket publications for each year
- SSA wage base publication for Social Security limits
- PSLmodels Tax-Calculator and other cross-reference sources

Validation strategy:

- Unit tests assert IRS data values and calculation correctness
- Year-specific tests verify behavior for current supported years
- W-4 tests verify recommendation and withholding math

Additional documentation:

- docs/irs_data_sources.md
- docs/annual_tax_data_update.md

## Development Guidelines

- Federal taxes only (state tax logic is out of scope)
- Treat tax math changes as high-risk and verify with tests
- Prefer clean refactors over compatibility shims during active development
- Keep tax data updates tied to explicit source citations

## Known Limitations

Out of scope unless explicitly planned:

- AMT
- NIIT
- Self-employment tax flows
- Preferential capital gains and qualified dividend rates
- Education credits and EITC
- Estimated quarterly payments

## Roadmap

Planned next major enhancement:

- Mid-year W-4 optimization refinements (manual YTD mode, variable schedule modeling, richer scenario comparison)

Planning document:

- docs/mid_year_w4_change_optimization_plan.md
