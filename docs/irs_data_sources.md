# IRS Data Sources Reference

Canonical citation document mapping every value in the tax data files to its IRS source.

## How Data Was Generated

All tax data was **manually extracted** from IRS publications and cross-referenced against independent sources. There is no IRS API for tax parameters — the source of truth is published Revenue Procedures, IRS.gov pages, and SSA announcements.

## Primary Sources (IRS / SSA)

| Source | URL | Used For |
|--------|-----|----------|
| IRS.gov Brackets Page | https://www.irs.gov/filing/federal-income-tax-rates-and-brackets | Consolidated bracket thresholds |
| IRS Rev. Proc. 2024-40 | https://www.irs.gov/pub/irs-drop/rp-24-40.pdf | 2025 original brackets (pre-OBBB) |
| IRS Rev. Proc. 2025-32 | https://www.irs.gov/pub/irs-drop/rp-25-32.pdf | 2026 brackets |
| IRS OBBB Provisions | https://www.irs.gov/newsroom/one-big-beautiful-bill-provisions | 2025 OBBB changes overview |
| IRS OBBB Deductions | https://www.irs.gov/newsroom/one-big-beautiful-bill-act-tax-deductions-for-working-americans-and-seniors | 2025 standard deductions |
| IRS OBBB Families | https://www.irs.gov/newsroom/one-big-beautiful-bill-provisions-families | 2025 child tax credit ($2,200) |
| SSA Wage Base | https://www.ssa.gov/oact/cola/cbbdet.html | SS contribution base per year |
| IRS Topic 751 | https://www.irs.gov/taxtopics/tc751 | FICA rates |
| IRS Additional Medicare | https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax | Additional 0.9% Medicare |

## Cross-Reference Sources (Independent Verification)

| Source | URL | Notes |
|--------|-----|-------|
| PSLmodels Tax-Calculator | https://github.com/PSLmodels/Tax-Calculator | `policy_current_law.json` — independent federal tax parameter database (2013-2026) |
| Tax Foundation | https://taxfoundation.org/data/all/federal/2026-tax-brackets/ | Reputable secondary source |
| IRS Tax Withholding Estimator | https://apps.irs.gov/app/tax-withholding-estimator | Live tool for spot-checks |
| IRS TWE Source Code | https://github.com/IRS-Public/tax-withholding-estimator | Scala source for withholding logic |

## Tax Year 2025

### Tax Brackets (`tax_brackets_2025.json`)

Source: IRS Rev. Proc. 2024-40 + OBBB Act (PL 119-21)
IRS.gov: https://www.irs.gov/filing/federal-income-tax-rates-and-brackets

| Filing Status | Rate | Threshold | IRS Source | PSLmodels Match |
|--------------|------|-----------|------------|-----------------|
| Single | 10% | $11,925 | IRS.gov brackets | Yes |
| Single | 12% | $48,475 | IRS.gov brackets | Yes |
| Single | 22% | $103,350 | IRS.gov brackets | Yes |
| Single | 24% | $197,300 | IRS.gov brackets | Yes |
| Single | 32% | $250,525 | IRS.gov brackets | Yes |
| Single | 35% | $626,350 | IRS.gov brackets | Yes |
| Single | 37% | (no limit) | IRS.gov brackets | Yes |
| MFJ | 10% | $23,850 | IRS.gov brackets | Yes |
| MFJ | 12% | $96,950 | IRS.gov brackets | Yes |
| MFJ | 22% | $206,700 | IRS.gov brackets | Yes |
| MFJ | 24% | $394,600 | IRS.gov brackets | Yes |
| MFJ | 32% | $501,050 | IRS.gov brackets | Yes |
| MFJ | 35% | $751,600 | IRS.gov brackets | Yes |
| MFJ | 37% | (no limit) | IRS.gov brackets | Yes |
| MFS | 10% | $11,925 | = Single | Yes |
| MFS | 12% | $48,475 | = Single | Yes |
| MFS | 22% | $103,350 | = Single | Yes |
| MFS | 24% | $197,300 | = Single | Yes |
| MFS | 32% | $250,525 | = Single | Yes |
| MFS | 35% | $375,800 | = MFJ / 2 | Yes |
| MFS | 37% | (no limit) | IRS.gov brackets | Yes |
| HoH | 10% | $17,000 | IRS.gov brackets | Yes |
| HoH | 12% | $64,850 | IRS.gov brackets | Yes |
| HoH | 22% | $103,350 | IRS.gov brackets | Yes |
| HoH | 24% | $197,300 | IRS.gov brackets | Yes |
| HoH | 32% | $250,500 | IRS.gov brackets | Yes |
| HoH | 35% | $626,350 | IRS.gov brackets | Yes |
| HoH | 37% | (no limit) | IRS.gov brackets | Yes |

### Standard Deductions

Source: OBBB Act Sec. 101
https://www.irs.gov/newsroom/one-big-beautiful-bill-act-tax-deductions-for-working-americans-and-seniors

| Filing Status | Amount | Source |
|--------------|--------|--------|
| Single | $15,750 | OBBB Act Sec. 101 |
| MFJ | $31,500 | OBBB Act Sec. 101 |
| MFS | $15,750 | OBBB Act Sec. 101 |
| HoH | $23,625 | OBBB Act Sec. 101 |
| Age 65+ (single/HoH) | +$2,000 | Rev. Proc. 2024-40, Sec. 3.15 |
| Age 65+ (married) | +$1,600 | Rev. Proc. 2024-40, Sec. 3.15 |

### Child Tax Credit

Source: OBBB Act Sec. 1001
https://www.irs.gov/newsroom/one-big-beautiful-bill-provisions-families

| Parameter | Value | Source |
|-----------|-------|--------|
| Amount per child | $2,200 | OBBB Act Sec. 1001 |
| Refundable portion | $1,700 | OBBB Act Sec. 1001 |
| Phase-out MFJ | $400,000 | IRC Sec. 24 |
| Phase-out Single/HoH | $200,000 | IRC Sec. 24 |

### FICA (`fica_limits_2025.json`)

| Parameter | Value | Source |
|-----------|-------|--------|
| SS employee rate | 6.2% | IRS Topic 751 |
| SS wage base | $176,100 | SSA.gov |
| SS max employee tax | $10,918.20 | $176,100 x 0.062 |
| Medicare rate | 1.45% | IRS Topic 751 |
| Additional Medicare rate | 0.9% | IRC Sec. 3101(b)(2) |
| Add'l Medicare Single threshold | $200,000 | IRC Sec. 3101(b)(2) |
| Add'l Medicare MFJ threshold | $250,000 | IRC Sec. 3101(b)(2) |
| Add'l Medicare MFS threshold | $125,000 | IRC Sec. 3101(b)(2) |

## Tax Year 2026

### Tax Brackets (`tax_brackets_2026.json`)

Source: IRS Rev. Proc. 2025-32
https://www.irs.gov/pub/irs-drop/rp-25-32.pdf

| Filing Status | Rate | Threshold | Source |
|--------------|------|-----------|--------|
| Single | 10% | $12,400 | RP-25-32 |
| Single | 12% | $50,400 | RP-25-32 |
| Single | 22% | $105,700 | RP-25-32 |
| Single | 24% | $201,775 | RP-25-32 |
| Single | 32% | $256,225 | RP-25-32 |
| Single | 35% | $640,600 | RP-25-32 |
| MFJ | 10% | $24,800 | RP-25-32 |
| MFJ | 12% | $100,800 | RP-25-32 |
| MFJ | 22% | $211,400 | RP-25-32 |
| MFJ | 24% | $403,550 | RP-25-32 |
| MFJ | 32% | $512,450 | RP-25-32 |
| MFJ | 35% | $768,700 | RP-25-32 |
| HoH | 10% | $17,700 | RP-25-32 |
| HoH | 12% | $67,450 | RP-25-32 |
| HoH | 22% | $105,700 | RP-25-32 |
| HoH | 24% | $201,750 | RP-25-32 |
| HoH | 32% | $256,200 | RP-25-32 |
| HoH | 35% | $640,600 | RP-25-32 |

### Standard Deductions (2026)

| Filing Status | Amount |
|--------------|--------|
| Single | $16,100 |
| MFJ | $32,200 |
| MFS | $16,100 |
| HoH | $24,150 |
| Age 65+ (single/HoH) | +$2,050 |
| Age 65+ (married) | +$1,650 |

### FICA (`fica_limits_2026.json`)

| Parameter | Value | Source |
|-----------|-------|--------|
| SS wage base | $184,500 | SSA.gov |
| SS max employee tax | $11,439.00 | $184,500 x 0.062 |
| Medicare rate | 1.45% | Unchanged |
| Additional Medicare thresholds | Unchanged | Not indexed for inflation |

## Verification Methodology

1. **Primary**: Every value traced to an IRS publication or SSA announcement
2. **Cross-reference**: Key values checked against PSLmodels Tax-Calculator `policy_current_law.json`
3. **Secondary**: Tax Foundation and Fidelity for independent bracket verification
4. **Automated**: `tests/unit/test_irs_data_validation.py` asserts every value in data files
5. **Calculation**: `tests/unit/test_irs_calculation_verification.py` verifies end-to-end computations

## Note on PSLmodels Tax-Calculator

The PSLmodels [Tax-Calculator](https://github.com/PSLmodels/Tax-Calculator) is a valuable cross-reference but **not a primary source**. It independently processes the same IRS publications, so agreement provides additional confidence. However, it could itself have errors. IRS publications are always the source of truth.

Key PSLmodels parameters for cross-reference:
- `II_brk*` — income tax bracket thresholds
- `STD` — standard deductions
- `SS_Earnings_c` — SS wage base
- `FICA_ss_trt` — SS tax rate
- `CTC_c` — child tax credit amount
