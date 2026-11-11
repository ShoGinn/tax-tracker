# Tax Tracker

[![CI](https://github.com/ShoGinn/tax-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/ShoGinn/tax-tracker/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/ShoGinn/tax-tracker)](https://github.com/ShoGinn/tax-tracker/releases/latest)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Railway deployment](https://img.shields.io/badge/Railway-live-0B0D0E?logo=railway&logoColor=white)](https://shoginn-tax-tracker.up.railway.app)

A local-first federal tax calculator and W-4 optimizer for modeling income, reconciling withholding, and planning the rest of the tax year.

Tax Tracker combines a React interface with a stateless FastAPI calculation service. Personal records and settings stay in the browser; the API receives calculation inputs only for the duration of each request and does not persist them.

> [!IMPORTANT]
> Tax Tracker is planning software, not tax, legal, or financial advice. Verify results against current IRS guidance and consult a qualified professional for decisions with material consequences. Do not enter real financial data into a deployment you do not trust.

## What It Does

- Models W-2 paychecks, 1099-R pension income, and non-taxable household income
- Calculates federal income tax with a per-bracket breakdown
- Calculates Social Security, Medicare, and Additional Medicare tax
- Reconciles projected tax against withholding to estimate a refund or balance due
- Suggests W-4 Steps 2, 3, and 4(a-c) for a target year-end result
- Optimizes mid-year W-4 changes using year-to-date records and remaining pay periods
- Compares annual projections across supported tax years
- Imports paycheck CSV files and exports portable JSON backups

Current tax and FICA data files cover tax years **2025 and 2026**.
All records and monetary values under `examples/` are fictional and exist only to demonstrate import formats.

## Privacy Model

| Data | Where it lives |
| --- | --- |
| Paychecks, pensions, settings, and saved scenarios | IndexedDB in the current browser profile |
| CSV imports and JSON backups | Processed locally in the browser |
| Calculation requests | Sent transiently to the FastAPI service and not stored server-side |
| Accounts and server database | Not used |

Browser storage is specific to an origin and browser profile. Clearing site data removes the working copy, so export backups periodically from **Settings**.

## Supported Calculations

### Income and deductions

- W-2 wages with pre-tax and post-tax deductions
- 1099-R pension and retirement distributions
- Non-taxable income for household planning context
- Standard or itemized deductions
- Child tax credit inputs

### Withholding and planning

- Federal withholding reconciliation
- IRS Publication 15-T per-paycheck withholding estimates
- W-4 recommendation generation
- Mid-year remaining-period suggestions by income cadence
- Annual and year-over-year projections

### Known limitations

The project currently focuses on common federal wage and pension workflows. It does not yet model:

- State or local taxes
- Alternative minimum tax (AMT)
- Net investment income tax (NIIT)
- Self-employment tax
- Preferential capital-gains or qualified-dividend rates
- Education credits, earned income tax credit, or estimated quarterly payments

## Quick Start

### Prerequisites

- Python 3.14
- Node.js 26
- pnpm 11
- [uv](https://docs.astral.sh/uv/)
- [just](https://just.systems/)

### Install

```bash
git clone https://github.com/ShoGinn/tax-tracker.git
cd tax-tracker
just install
just frontend-install
```

### Run for development

Start the API:

```bash
just run
```

In a second terminal, start the frontend:

```bash
just frontend-dev
```

Open `http://localhost:5173`. The Vite development server proxies API routes to `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to target a different API origin.

### Run the production container

```bash
docker build -t tax-tracker .
docker run --rm -p 8000:8000 -e PORT=8000 tax-tracker
```

Open `http://localhost:8000`. The multi-stage image builds the React frontend and serves it from FastAPI.

## Development

The main quality gates are:

```bash
just check             # Fast local backend and frontend checks
just ci                # Full local CI suite
just test              # Python tests with 80% overall coverage minimum
just test-services     # Calculation-service coverage gate
just frontend-check    # Frontend lint, types, tests, and build
just frontend-test-e2e # Browser workflow tests
just security          # Dependency vulnerability scan
```

Run `just --list` for all available recipes. Direct `uv`, `pytest`, and `pnpm` commands are also supported.

### Zed editor

Open the repository root in [Zed](https://zed.dev/) after installing the locked dependencies:

```bash
uv sync --locked --dev
pnpm --dir frontend install --frozen-lockfile
zed .
```

Use `toolchain: select` in the command palette to select this checkout's `.venv` Python interpreter.
Zed uses the Ruff and ty binaries installed in that environment, matching `just lint` and
`just typecheck`. Python saves apply Ruff fixes, organize imports, and format using the rules
in `pyproject.toml`. The pre-commit hook has its own Ruff version pin in
`.pre-commit-config.yaml`; keep it aligned with the project dependency when updating Ruff.

The shared `.zed/settings.json` enables ty and Ruff for Python and uses the frontend's installed
Oxfmt for JavaScript, TypeScript, JSX/TSX, CSS, and JSON formatting on save. Zed's built-in
TypeScript support supplies frontend navigation and completions; use the frontend lint and
typecheck tasks for the repository's Oxc and TypeScript checks.

Run `task: spawn` from the command palette to start the API and frontend in separate terminals,
run tests (including the current Python file), or invoke the existing `just` quality checks.
The task definitions live in `.zed/tasks.json`. See Zed's [Python setup](https://zed.dev/docs/languages/python)
and [task documentation](https://zed.dev/docs/tasks) for toolchain and task details.

### CI job selection

CI starts on every pull request to `main` and every push to `main`. Pre-commit checks and
regression tests for the change filters always run. The remaining jobs use the complete Git
diff (the PR merge base or the previous push tip), including deletions and renames:

| Changed inputs | Selected checks |
| --- | --- |
| Frontend files or Node version | Frontend gate, browser E2E, production container |
| Backend runtime source | Backend tests, typecheck, browser E2E, production container |
| Backend tests or scripts | Backend tests; PSL cross-check for its specific inputs |
| Python dependencies or Python version | Backend tests, typecheck, browser E2E, PSL cross-check |
| Python dependency manifest or lockfile | Dependency security scan in addition to applicable checks above |
| Tax data, data models, loader, or PSL snapshot tooling/fixtures | PSL cross-check in addition to applicable checks above |
| Dockerfile, Docker ignore rules, or root README | Production container |
| CI configuration, editor settings, or other documentation | Always-on checks only |

The container also runs for `pyproject.toml` changes because it installs the backend package.
Frontend paths intentionally include its tests and tool configuration. Unknown paths or unavailable
comparison history run the full suite. Use **Run workflow** on CI for a manual full run.
The weekly PSL snapshot monitor continues checking upstream drift independently.

`CI required checks` accepts deliberately skipped jobs and fails if any selected job fails or is
cancelled. Releases on `main` depend on this gate, so selective skips do not block release evaluation.
The existing job names remain available for branch protection; `CI required checks` can be used as
a single required status. Repository branch-protection settings are managed separately.

Selection rules and their regression tests live in `.github/scripts/ci_changes.py` and
`.github/scripts/test_ci_changes.py`. When adding runtime inputs, update the rules and tests together.

### Technology

- FastAPI, Pydantic v2, and Python 3.14
- React 19, React Router 8, TypeScript 7, and Vite 8
- IndexedDB through Dexie 4
- uv, Ruff, ty, pytest, pnpm, Oxc, Vitest, and Playwright
- Docker and Railway deployment configuration

### Project layout

```text
src/taxtracker/
├── api/          # FastAPI route handlers
├── cli/          # Application factory and entry point
├── core/         # Configuration and exceptions
├── data/         # IRS-sourced tax and FICA data
├── models/       # Pydantic request and response models
└── services/     # Tax, W-4, withholding, and projection logic
frontend/
├── src/pages/    # Product screens
├── src/lib/      # API client, storage, and utilities
└── e2e/          # Playwright workflows
tests/
├── unit/
├── integration/
├── fixtures/
└── data/
```

## Tax Calculation Flow

The core federal calculation:

1. Totals taxable income
2. Subtracts eligible pre-tax deductions
3. Computes adjusted gross income
4. Applies the standard or itemized deduction
5. Calculates federal income tax by bracket
6. Applies supported credits
7. Adds applicable FICA components
8. Reconciles the result against withholding

## Data Sources and Validation

Tax constants are curated from IRS and SSA publications and cross-checked against independent tax models. Changes to tax math are treated as high-risk and require source-backed tests.

- [IRS data sources](docs/irs_data_sources.md)
- [Annual tax data update process](docs/annual_tax_data_update.md)
- [Mid-year W-4 optimization plan](docs/mid_year_w4_change_optimization_plan.md)

Validation includes year-specific unit tests, integration tests, IRS example cases, service-layer coverage thresholds, and automated comparisons with PSLmodels Tax-Calculator data.

Repository workflows pin GitHub-hosted runners to Ubuntu 24.04 for a stable CI environment.
Release and hook-update workflows use the repository variable `RELEASE_APP_CLIENT_ID`
and secret `RELEASE_APP_PRIVATE_KEY` for the existing release App. Date-only PSL
snapshot changes are logged normally; changes to tax values still emit a warning.

## API

FastAPI exposes interactive OpenAPI documentation at `/docs` while the service is running. Major capabilities include:

- Direct federal tax calculations and bracket/FICA data lookup
- Reconciliation of transient browser snapshots
- W-4 optimization and Publication 15-T withholding estimates
- Mid-year period suggestions and W-4 optimization
- Annual and year-over-year projections

The API is stateless with respect to personal tax records.

## Deployment

The included [`Dockerfile`](Dockerfile) builds the frontend and backend into one image. [`railway.json`](railway.json) configures Railway to use the Dockerfile and validate deployments through `/health`.

No database or application secrets are required for the default deployment. Railway supplies `PORT`; the container listens on `0.0.0.0:$PORT`.

## Automation

GitHub Actions provides:

- Backend and frontend CI, coverage, type checking, and dependency scanning
- Production-container smoke testing
- Playwright end-to-end testing
- Weekly PSLmodels tax-data drift monitoring
- Weekly pre-commit hook update pull requests
- Semantic releases from `main`

## Contributing

Bug reports, feature proposals, documentation fixes, and source-backed tax updates are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md) before participating, and never attach real tax records, credentials, or personally identifiable information to an issue.

## Security

Please report vulnerabilities privately according to [SECURITY.md](SECURITY.md). Do not use a public issue for security reports or include real financial data in reproduction steps.

## License

Tax Tracker is available under the [MIT License](LICENSE).

### Understanding tax balances

The overview estimates a full-year **federal income tax** refund or amount due:
projected federal withholding minus projected federal income tax after credits.
For the current year, remaining income, pre-tax deductions, and federal withholding
continue at their recorded per-payment averages, separately for wages and pensions.
Bonuses are included in the wage average; this is an assumption, not a prediction of
future bonuses. Recorded withholding is shown separately from projected withholding.
Future-dated records already entered consume remaining payment periods instead of
being projected a second time. Completed years use recorded totals without extrapolation. The overview prefers the
current tax year when tax data for it is available.

Tax-position reconciliation uses only records for the selected year, without
annualizing them. It shows gross wages and pensions, pre-tax deductions, income before
the standard/itemized deduction, and the resulting federal taxable income. Bracket
rows show how portions of taxable income are taxed; their taxes sum to federal tax
**before** credits. Effective federal rates use income after recorded pre-tax
deductions and before the standard/itemized deduction as the denominator.

FICA is displayed separately and does not change the primary federal refund estimate.
Combined income and payroll taxes remain available for cashflow planning. The current
FICA model estimates tax on aggregate gross W-2 wages with one Social Security wage
cap; it does not model separate spouses' wage caps or benefit-specific FICA exemptions.
It is an estimate, not a payroll reconciliation or a complete Form 1040 calculation
(including excess Social Security credits or Additional Medicare reconciliation).

API dashboard amounts are decimal strings. `projected.estimated_withholding` and
`projected.estimated_refund_or_owed` are federal-only; `total_tax_liability` includes
FICA, while `federal_tax_liability` does not. Reconciliation's `refund_or_owed`,
`result_status`, and `overpayment_percentage` use federal income tax and federal
withholding only; combined liability and total withholding remain informational.
Missing dashboard values display an unavailable state rather than a zero balance.

Reference rules: [IRS Publication 505, 2026](https://www.irs.gov/publications/p505),
[IRS Revenue Procedure 2025-32](https://www.irs.gov/pub/irs-drop/rp-25-32.pdf),
[SSA contribution and benefit bases](https://www.ssa.gov/oact/cola/cbb.html), and
[IRS Topic 751](https://www.irs.gov/taxtopics/tc751).

W-2 entry and CSV imports treat `gross_wages` as wages **excluding** the separate
`bonus` field. Federal taxable wages equal `gross_wages + bonus − pre-tax deductions`;
federal withholding and Roth contributions do not reduce them. The paycheck table
shows gross including bonuses consistently for rows and totals, the included bonus,
and pre-tax deductions. If a pay stub's gross already includes a bonus, either remove
the bonus from the entered gross or leave the separate bonus field at zero.

A paycheck with a separate bonus is flagged for review when both recorded Social
Security and Medicare withholding match gross wages alone rather than wages plus
bonus (within rounding tolerance). This is a hint to check gross wages, bonus, and withholding against the original
pay stub, not proof of a bonus input error: withholding may be entered incorrectly,
and payroll adjustments can also change tax bases. No
stored values are automatically corrected.
