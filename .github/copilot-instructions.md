# Copilot repository instructions

Follow the complete workflow in the root `AGENTS.md`. Treat current code, tests, `pyproject.toml`, `justfile`, `frontend/package.json`, and `.github/workflows/ci.yml` as authoritative.

Tax Tracker is a local-first federal tax calculator and W-4 optimizer. Its React 19/TypeScript/Vite SPA stores personal records only in browser IndexedDB through Dexie. Its Python 3.14 FastAPI/Pydantic service performs transient calculations and does not persist personal data. Do not add server persistence, accounts, real financial data, or state-tax behavior unless explicitly requested. API routes have no `/api` prefix, and FastAPI serves `frontend/dist` with SPA fallback behavior in production.

Use `uv` with the committed `uv.lock`, Node.js 26, and pnpm 11 with `frontend/pnpm-lock.yaml`. Bootstrap from the repository root with:

```bash
uv sync --locked --dev
pnpm --dir frontend install --frozen-lockfile
```

Use focused tests while iterating. Before completing a code change, run the relevant checks and normally `just check`; use `just ci` for broader or high-risk changes. Backend pytest configuration enforces 80% overall coverage, while `just test-services` enforces 90% coverage across calculation services. Frontend behavior changes require Vitest/React Testing Library tests and `just frontend-check`. Run `uv run pre-commit run --all-files` for repository configuration, workflow, or documentation changes.

Treat tax calculations, W-4 logic, projections, and files under `src/taxtracker/data/` as high risk. Tax logic or constants must cite an authoritative IRS or SSA source and include independently verifiable tests. Never weaken known-correct tax assertions to accommodate an implementation. Keep all examples and fixtures synthetic and free of personally identifiable information.

CI additionally runs a Docker production smoke test, Playwright browser tests, dependency scanning, and a network-backed PSLmodels cross-check. Run those checks when the change affects them and the required Docker, browser, or network capability is available; do not claim they ran when they did not. Do not update dependencies, lockfiles, generated snapshots, or generated frontend output unless the task calls for it.

Keep changes focused, update user or contributor documentation when behavior or workflows change, preserve unrelated work, and do not commit or push unless explicitly requested.
