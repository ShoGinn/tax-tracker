set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# Show all available recipes.
default:
    @just --list

# Install project and dev dependencies, then install pre-commit hooks.
install:
    uv sync --dev
    uv run pre-commit install --hook-type pre-commit --hook-type pre-push

# Install pre-commit hooks only (run after cloning if hooks are missing).
hooks:
    uv run pre-commit install --hook-type pre-commit --hook-type pre-push

# Upgrade lockfile to latest compatible versions.
update-lock:
    uv lock --upgrade

# Run API with project defaults from settings.
run:
    uv run taxtracker

# Frontend workflows (pnpm + Oxc).
frontend-install:
    cd frontend && pnpm install

frontend-dev:
    cd frontend && pnpm dev

frontend-build:
    cd frontend && pnpm build

frontend-test:
    cd frontend && pnpm test

frontend-typecheck:
    cd frontend && pnpm typecheck

frontend-lint:
    cd frontend && pnpm lint

frontend-lint-fix:
    cd frontend && pnpm lint:fix

frontend-format:
    cd frontend && pnpm format:fix

frontend-check:
    cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build

# Run API with explicit host/port overrides.
run-host host="127.0.0.1" port="8000":
    uv run uvicorn taxtracker.cli.app:app --reload --host {{host}} --port {{port}}

# Run full test suite (coverage threshold enforced by pytest config).
test:
    uv run pytest

test-unit:
    uv run pytest tests/unit

test-integration:
    uv run pytest tests/integration

test-fast:
    uv run pytest -m "not slow"

test-file file:
    uv run pytest {{file}}

test-name file pattern:
    uv run pytest {{file}} -k {{pattern}}

# Linting and formatting.
lint:
    uv run ruff check src/ tests/ scripts/

lint-fix:
    uv run ruff check --fix src/ tests/ scripts/

format:
    uv run ruff format src/ tests/ scripts/

format-check:
    uv run ruff format --check src/ tests/ scripts/

# Static type checking.
typecheck:
    uv run ty check

# Dependency vulnerability scan.
security:
    uvx uv-secure

# Refresh local PSLmodels validation data.
psl-snapshot years="2025 2026":
    uv run python scripts/fetch_pslmodels_data.py snapshot --years {{years}}

# Generate draft tax data for a target year.
psl-draft year:
    uv run python scripts/fetch_pslmodels_data.py draft --year {{year}}

# Focused PSLmodels cross-validation test.
test-psl:
    uv run pytest tests/unit/test_pslmodels_cross_check.py -v

# CI-style local gates.
check: format-check lint typecheck test-fast frontend-check

ci: lint typecheck test frontend-check

# Remove common local caches and coverage outputs.
clean:
    rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

# Full App Run that includes frontend build with api static hosting
app: frontend-build run
