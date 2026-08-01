# Repository Agent Guide

Use this file as the primary guide for automated work in this repository. Trust it before doing broad searches. If an instruction conflicts with executable configuration or current code, follow the configuration or code and update this guide when appropriate.

## Product and boundaries

Tax Tracker is a local-first federal tax calculator and W-4 optimizer. The React SPA stores paychecks, pensions, settings, and scenarios in browser IndexedDB through Dexie. The FastAPI service is stateless: it accepts calculation inputs for a request and does not persist personal records. Do not introduce accounts, server-side personal-data storage, or a database without an explicit product decision.

The supported scope is common federal wage and pension workflows. State and local taxes are out of scope. Treat this as tax-planning software, not tax advice. Never put real financial records, personally identifiable information, credentials, or secrets in code, fixtures, logs, issues, or documentation; use synthetic examples only.

## Toolchain and bootstrap

- Python 3.14 (`.python-version`), managed with `uv`; FastAPI and Pydantic v2.
- Node.js 26 (`.nvmrc`) and pnpm 11; React 19, TypeScript, and Vite.
- Backend quality tools: Ruff, `ty`, pytest, and pre-commit.
- Frontend quality tools: Oxc (`oxlint`/`oxfmt`), TypeScript, Vitest, React Testing Library, and Playwright.
- `justfile` is the canonical command catalog. Run `just --list` for recipes. Direct `uv` and `pnpm` equivalents are valid when `just` is unavailable.

From the repository root, install locked dependencies without changing lockfiles:

```bash
uv sync --locked --dev
pnpm --dir frontend install --frozen-lockfile
```

Do not upgrade dependencies or regenerate `uv.lock` or `frontend/pnpm-lock.yaml` unless the task requires it.

## Architecture and navigation

- `src/taxtracker/cli/app.py` creates the FastAPI application, registers routers, exposes `/health`, and serves the built SPA from `frontend/dist` when present.
- `src/taxtracker/api/` contains stateless route handlers. API routes do **not** use an `/api` prefix.
- `src/taxtracker/models/` contains Pydantic request, response, and browser-record models.
- `src/taxtracker/services/` contains tax, projection, reconciliation, W-4, withholding, and data-loading logic.
- `src/taxtracker/data/` contains IRS/SSA-sourced tax-bracket and FICA JSON for supported years.
- `frontend/src/pages/` contains screens; `frontend/src/lib/api/` contains the API client and wire types; `frontend/src/lib/storage/` owns browser persistence.
- `frontend/src/app/router.tsx` defines browser routes. Vite proxies backend route prefixes to `127.0.0.1:8000` during development.
- `tests/unit/` covers calculations, data, and SPA routing; `tests/integration/` covers API behavior; frontend tests live beside the TypeScript modules; `frontend/e2e/` contains Playwright workflows.
- `pyproject.toml`, `frontend/package.json`, frontend tool configs, `.pre-commit-config.yaml`, and `.github/workflows/ci.yml` are the sources of truth for tooling and validation.

## Run and validate

Run the API and frontend in separate terminals:

```bash
just run
just frontend-dev
```

The frontend is available at `http://localhost:5173` and proxies the API at `http://127.0.0.1:8000`. For the production-style combined app, run `just app` and open `http://127.0.0.1:8000`.

Use focused checks while iterating:

```bash
just test-file tests/unit/test_tax_calculator.py
just test-name tests/unit/test_tax_calculator.py pattern
just test-unit
just test-integration
just frontend-test
```

Before finishing, run checks proportional to the change, then the applicable aggregate gate:

```bash
just check          # format-check, lint, typecheck, fast backend tests, frontend checks
just ci             # lint, typecheck, full backend tests, frontend checks
just test-services  # separate 90% calculation-service coverage gate
```

The normal pytest configuration enforces at least 80% overall backend coverage. CI also runs pre-commit, the 90% service gate, a production-container smoke test, Playwright E2E, dependency scanning, and a PSLmodels cross-check. Run `uv run pre-commit run --all-files` when changing configuration, workflows, or documentation. Run `just frontend-test-e2e` for browser workflow changes after installing Chromium with `pnpm --dir frontend exec playwright install chromium`. Network-dependent security and PSL snapshot commands need not run for unrelated work.

## Correctness rules

- Tax math and tax-data changes are high risk. Cite the exact authoritative IRS or SSA source, cross-check values, and add tests with independently known-correct outcomes. See `docs/irs_data_sources.md` and `docs/annual_tax_data_update.md`.
- Preserve calculation ordering: taxable income and deductions feed federal tax; supported credits reduce federal tax; FICA applies to eligible W-2 wages, not pension income.
- Never weaken or rewrite IRS-validated assertions merely to make tests pass. Fix the implementation or establish that the expected value is wrong from an authoritative source.
- Behavior changes require tests. Frontend behavior changes require Vitest/React Testing Library coverage; API changes require integration coverage; calculation changes require focused unit and validation cases.
- Keep API and frontend wire types synchronized. Preserve browser-only persistence and SPA fallback behavior.
- Update `README.md` or relevant `docs/` files when behavior, supported features, setup, APIs, architecture, tax data, or contributor workflow changes.
- Keep changes focused and preserve unrelated user work. Do not commit or push unless explicitly asked. When asked to commit, use conventional prefixes such as `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, or `chore:`.
