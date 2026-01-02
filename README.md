# Tax Tracker

**Universal tax calculation and income tracking system**

[![Tests](https://img.shields.io/badge/tests-149%20passing-success)]()
[![Coverage](https://img.shields.io/badge/coverage-84.37%25-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.12+-blue)]()

## Quick Start

```bash
# Install & run
uv run pytest tests/ -v                      # Run tests
uv run uvicorn taxtracker.cli.app:app --reload  # Start API
open http://localhost:8000/docs              # View docs
```

## What It Does

**Income Tracking**
- 📊 W-2 Income (paychecks with FICA)
- 📋 1099-R Income (retirement/pensions - no FICA)
- 🎁 Non-Taxable Income (VA disability, SSA, gifts)

**Tax Calculations**
- 💵 Federal income tax (IRS Publication 17)
- 🏛️ FICA (Social Security + Medicare)
- 👨‍👩‍👧‍👦 Child tax credits
- 📈 Year projections
- 📝 W-4 optimization

**Key Features**
- ✅ IRS-verified calculations
- ✅ 149 tests (100% passing)
- ✅ Zero file dependencies in tests
- ✅ FastAPI with auto docs
- ✅ SQLite database

## Installation

### Using `uv` (recommended)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
cd tax-tracker-refactored
uv sync
```

### Using `pip`
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## API Endpoints

### Income
```bash
POST   /income/paychecks      # W-2 paychecks
POST   /income/1099r          # Retirement income (1099-R)
POST   /income/non-taxable    # Non-taxable income
GET    /income/{type}         # List entries
DELETE /income/{type}/{id}    # Delete entry
```

### Taxes
```bash
POST /taxes/calculate          # Calculate taxes
GET  /taxes/brackets/{year}    # Tax brackets
GET  /taxes/fica/{year}        # FICA limits
```

### Projections
```bash
POST /projections/project-year      # Project future taxes
POST /projections/compare-years     # Compare years
```

### W-4
```bash
POST /w4/optimize              # Optimize W-4
POST /w4/calculate-withholding # Per-paycheck withholding
```

## Example Usage

### Python
```python
from taxtracker.services.tax_calculator import TaxCalculator
from taxtracker.models.tax_data import TaxCalculationRequest, FilingStatus
from decimal import Decimal

calculator = TaxCalculator()

request = TaxCalculationRequest(
    tax_year=2024,
    filing_status=FilingStatus.SINGLE,
    gross_income=Decimal("75000"),
    num_children=0
)

result = calculator.calculate_taxes(request)
print(f"Federal Tax: ${result.federal_tax_owed}")
print(f"FICA: ${result.fica_taxes['total_fica']}")
```

### REST API
```bash
curl -X POST "http://localhost:8000/taxes/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "tax_year": 2024,
    "filing_status": "single",
    "gross_income": 75000,
    "num_children": 0
  }'
```

## Documentation

- **[Setup Guide](docs/SETUP.md)** - Complete installation & setup
- **[Testing Guide](docs/TESTING.md)** - How tests work
- **[Architecture](docs/ARCHITECTURE.md)** - Technical details
- **[Changelog](docs/CHANGELOG.md)** - Version history

## Tax Treatment

| Income Type | Federal Tax | FICA | Notes |
|-------------|-------------|------|-------|
| W-2 (Paychecks) | ✅ Yes | ✅ Yes | Subject to all taxes |
| 1099-R (Retirement) | ✅ Yes | ❌ No | No Social Security/Medicare |
| Non-Taxable | ❌ No | ❌ No | Tracking only |

## Key Concepts

**1099-R Income Examples:**
- Military/civilian pensions
- 401(k) distributions
- IRA withdrawals
- Annuity payments

**Non-Taxable Income Examples:**
- VA disability compensation
- Social Security disability
- Child support payments
- Gift income

## Testing

```bash
# All tests (149 tests, ~5 seconds)
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=src/taxtracker --cov-report=html
open htmlcov/index.html

# Quick verification
python3 verify.py
```

## Project Stats

- **Language:** Python 3.12+
- **Framework:** FastAPI
- **Database:** SQLite (SQLAlchemy ORM)
- **Tests:** 149 passing (100%)
- **Coverage:** 84.37%
- **IRS Examples:** 16 scenarios
- **Speed:** <5 second test suite

## Development

```bash
# Code quality
uv run ruff check src/taxtracker/        # Lint
uv run mypy src/taxtracker/              # Type check

# Auto-format
uv run ruff check src/taxtracker/ --fix

# Run all checks
python3 verify.py
```

## Architecture

```
FastAPI Application
├── API Routes (/income, /taxes, /projections, /w4)
├── Services (Business Logic)
├── Models (Database + Schemas)
└── SQLite Database
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Changelog

**v2.0.0 (2025-12-31)** - Universal Income Categories
- Renamed "Pension" → "1099-R"  
- Renamed "VA Disability" → "Non-Taxable Income"
- IRS form-aligned terminology
- 149/149 tests passing

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for full history.

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit pull request

## License

Educational and personal use.

**⚠️ Not tax advice. Consult a tax professional for official guidance.**

## Acknowledgments

- **IRS Publications:** 17, 15, 15-T
- **Built with:** FastAPI, SQLAlchemy, Pydantic, Pytest

---

**Ready to calculate taxes!** 🎯

[Interactive API Docs](http://localhost:8000/docs) | [Setup Guide](docs/SETUP.md) | [Testing](docs/TESTING.md)
