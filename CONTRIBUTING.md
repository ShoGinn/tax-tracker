# Contributing to Tax Tracker

Thanks for helping improve Tax Tracker. Contributions are welcome for bug fixes, documentation, accessibility, tests, and source-backed tax calculations.

## Before You Start

- Search existing issues and pull requests before opening a duplicate.
- Use synthetic examples only. Never post real tax records, Social Security numbers, addresses, credentials, or other personally identifiable information.
- Open an issue before starting a broad feature or calculation-model change so scope and validation sources can be discussed.
- Report security vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Development Setup

Requirements are Python 3.14, Node.js 26, pnpm 11, uv, and just.

```bash
git clone https://github.com/ShoGinn/tax-tracker.git
cd tax-tracker
just install
just frontend-install
```

Run the API and frontend in separate terminals:

```bash
just run
just frontend-dev
```

## Making Changes

1. Create a focused branch from `main`.
2. Add or update tests for behavior changes.
3. Cite authoritative IRS or SSA sources when changing tax constants or tax logic.
4. Keep examples and fixtures synthetic unless they reproduce published agency examples.
5. Run the relevant focused tests while iterating, then run `just check` before opening a pull request.

Useful commands:

```bash
just test-unit
just test-integration
just test-services
just frontend-test
just frontend-test-e2e
just check
```

## Pull Requests

Keep pull requests small enough to review and explain:

- What changed and why
- How the change was tested
- Which authoritative sources support tax-data or calculation changes
- Any user-facing, privacy, compatibility, or deployment impact

The repository uses conventional commit prefixes such as `feat:`, `fix:`, `docs:`, and `chore:` for release automation.
