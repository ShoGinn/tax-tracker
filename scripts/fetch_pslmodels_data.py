"""Fetch and normalize tax data from PSLmodels Tax-Calculator.

Downloads policy_current_law.json from PSLmodels GitHub and extracts federal tax
parameters for cross-validation against our IRS-sourced data files, or generates
draft data files for new tax years.

PSLmodels is a CROSS-REFERENCE, not the source of truth. All generated data must
be verified against IRS publications before use.

Usage:
    # Generate snapshot for cross-validation tests
    uv run python scripts/fetch_pslmodels_data.py snapshot

    # Generate draft data files for a new tax year
    uv run python scripts/fetch_pslmodels_data.py draft --year 2027

    # Dry-run draft (print to stdout, don't write files)
    uv run python scripts/fetch_pslmodels_data.py draft --year 2027 --dry-run

    # Force overwrite existing draft files
    uv run python scripts/fetch_pslmodels_data.py draft --year 2027 --force
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import click

PSLMODELS_URL = "https://raw.githubusercontent.com/PSLmodels/Tax-Calculator/master/taxcalc/policy_current_law.json"

# Project paths (relative to this script's location)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "src" / "taxtracker" / "data"
TESTS_DATA_DIR = PROJECT_ROOT / "tests" / "data"

# PSLmodels MARS -> our filing status mapping
MARS_MAP: dict[str, str] = {
    "single": "single",
    "mjoint": "married_filing_jointly",
    "mseparate": "married_filing_separately",
    "headhh": "head_of_household",
}

# PSLmodels parameters we extract
BRACKET_PARAMS = ["II_brk1", "II_brk2", "II_brk3", "II_brk4", "II_brk5", "II_brk6"]
RATE_PARAMS = ["II_rt1", "II_rt2", "II_rt3", "II_rt4", "II_rt5", "II_rt6", "II_rt7"]
TAX_RATES = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]


def fetch_pslmodels_data() -> dict[str, Any]:
    """Download and parse policy_current_law.json from PSLmodels GitHub.

    Returns:
        Parsed JSON data dictionary.

    Raises:
        click.ClickException: If download or parse fails.
    """
    click.echo(f"Fetching PSLmodels data from:\n  {PSLMODELS_URL}")
    try:
        req = urllib.request.Request(PSLMODELS_URL, headers={"User-Agent": "tax-tracker"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise click.ClickException(f"Failed to download PSLmodels data: {e}") from e

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Failed to parse PSLmodels JSON: {e}") from e

    click.echo(f"  Downloaded {len(raw):,} bytes, {len(data)} parameters")
    return data


def _resolve_value_for_year(entries: list[dict[str, Any]], year: int, mars: str | None = None) -> float | None:
    """Resolve a PSLmodels parameter value for a specific year, handling forward-carry.

    PSLmodels uses year-forward-carry semantics: a value set in year Y applies to all
    subsequent years until overridden. For example, FICA_ss_trt_employee is only set for
    2013 but applies to all years after.

    Args:
        entries: List of value entries from a PSLmodels parameter.
        year: Target tax year.
        mars: MARS filing status filter (None for non-MARS parameters).

    Returns:
        The resolved value, or None if no applicable entry found.
    """
    best_year = -1
    best_value = None

    for entry in entries:
        entry_year = entry["year"]
        if entry_year > year:
            continue

        if mars is not None and entry.get("MARS") != mars:
            continue

        if entry_year > best_year:
            best_year = entry_year
            best_value = entry["value"]

    return best_value


def extract_bracket_thresholds(data: dict[str, Any], year: int) -> dict[str, list[dict[str, float | None]]]:
    """Extract tax bracket thresholds for all filing statuses.

    Returns:
        Dict mapping filing status to list of {threshold, rate} dicts.
    """
    brackets: dict[str, list[dict[str, float | None]]] = {}

    for mars_psl, status in MARS_MAP.items():
        status_brackets: list[dict[str, float | None]] = []
        for i, param in enumerate(BRACKET_PARAMS):
            if param not in data:
                click.echo(f"  WARNING: {param} not found in PSLmodels data", err=True)
                continue
            threshold = _resolve_value_for_year(data[param]["value"], year, mars_psl)
            if threshold is not None:
                status_brackets.append({"threshold": threshold, "rate": TAX_RATES[i]})

        # Add the final bracket (no threshold, highest rate)
        status_brackets.append({"threshold": None, "rate": TAX_RATES[6]})
        brackets[status] = status_brackets

    return brackets


def extract_rates(data: dict[str, Any], year: int) -> list[float]:
    """Extract the 7 income tax rates for a given year.

    Returns:
        List of 7 tax rates.
    """
    rates: list[float] = []
    for param in RATE_PARAMS:
        if param not in data:
            click.echo(f"  WARNING: {param} not found in PSLmodels data", err=True)
            continue
        rate = _resolve_value_for_year(data[param]["value"], year)
        if rate is not None:
            rates.append(rate)
    return rates


def extract_standard_deductions(data: dict[str, Any], year: int) -> dict[str, int]:
    """Extract standard deduction amounts by filing status.

    Returns:
        Dict mapping filing status to deduction amount.
    """
    deductions: dict[str, int] = {}
    if "STD" not in data:
        click.echo("  WARNING: STD not found in PSLmodels data", err=True)
        return deductions

    for mars_psl, status in MARS_MAP.items():
        val = _resolve_value_for_year(data["STD"]["value"], year, mars_psl)
        if val is not None:
            deductions[status] = int(val)

    return deductions


def extract_aged_deductions(data: dict[str, Any], year: int) -> dict[str, int]:
    """Extract additional standard deduction for age 65+.

    Our format uses "single" and "married" keys. PSLmodels uses full MARS.
    Single and headhh get "single" amount; mjoint and mseparate get "married" amount.

    Returns:
        Dict with "single" and "married" keys.
    """
    result: dict[str, int] = {}
    if "STD_Aged" not in data:
        click.echo("  WARNING: STD_Aged not found in PSLmodels data", err=True)
        return result

    single_val = _resolve_value_for_year(data["STD_Aged"]["value"], year, "single")
    married_val = _resolve_value_for_year(data["STD_Aged"]["value"], year, "mjoint")

    if single_val is not None:
        result["single"] = int(single_val)
    if married_val is not None:
        result["married"] = int(married_val)

    return result


def extract_fica(data: dict[str, Any], year: int) -> dict[str, Any]:
    """Extract FICA parameters (SS wage base, rates, Medicare, Additional Medicare).

    Returns:
        Dict with social_security, medicare, and additional_medicare sections.
    """
    result: dict[str, Any] = {}

    # Social Security
    ss_wage_base = _resolve_value_for_year(data.get("SS_Earnings_c", {}).get("value", []), year)
    ss_rate = _resolve_value_for_year(data.get("FICA_ss_trt_employee", {}).get("value", []), year)

    if ss_wage_base is not None and ss_rate is not None:
        max_employee_tax = round(ss_wage_base * ss_rate, 2)
        result["social_security"] = {
            "employee_rate": ss_rate,
            "employer_rate": ss_rate,
            "total_rate": round(ss_rate * 2, 4),
            "wage_base_limit": int(ss_wage_base),
            "max_employee_tax": max_employee_tax,
            "max_employer_tax": max_employee_tax,
            "max_combined_tax": round(max_employee_tax * 2, 2),
        }

    # Medicare
    mc_rate = _resolve_value_for_year(data.get("FICA_mc_trt_employee", {}).get("value", []), year)
    if mc_rate is not None:
        result["medicare"] = {
            "employee_rate": mc_rate,
            "employer_rate": mc_rate,
            "total_rate": round(mc_rate * 2, 4),
            "wage_base_limit": None,
            "note": "No wage base limit - applies to all wages",
        }

    # Additional Medicare
    amedt_rate = _resolve_value_for_year(data.get("AMEDT_rt", {}).get("value", []), year)
    amedt_thresholds: dict[str, int] = {}
    if "AMEDT_ec" in data:
        for mars_psl, status in MARS_MAP.items():
            val = _resolve_value_for_year(data["AMEDT_ec"]["value"], year, mars_psl)
            if val is not None:
                amedt_thresholds[status] = int(val)

    if amedt_rate is not None:
        result["additional_medicare"] = {
            "rate": amedt_rate,
            "employer_match": False,
            "thresholds": amedt_thresholds,
            "note": "Applies to wages above threshold, no employer match",
        }

    # Combined rates
    if ss_rate is not None and mc_rate is not None and amedt_rate is not None:
        result["combined_rates"] = {
            "below_ss_wage_base": round(ss_rate + mc_rate, 4),
            "above_ss_wage_base": mc_rate,
            "above_additional_medicare_threshold": round(mc_rate + amedt_rate, 4),
        }

    return result


def extract_ctc(data: dict[str, Any], year: int) -> dict[str, Any]:
    """Extract Child Tax Credit parameters.

    Returns:
        Dict with amount_per_child, refundable_portion, and phase_out_threshold.
    """
    result: dict[str, Any] = {}

    ctc_amount = _resolve_value_for_year(data.get("CTC_c", {}).get("value", []), year)
    actc_amount = _resolve_value_for_year(data.get("ACTC_c", {}).get("value", []), year)

    if ctc_amount is not None:
        result["amount_per_child"] = int(ctc_amount)
    if actc_amount is not None:
        result["refundable_portion"] = int(actc_amount)

    # Phase-out thresholds
    if "CTC_ps" in data:
        phase_outs: dict[str, int] = {}
        for mars_psl, status in MARS_MAP.items():
            val = _resolve_value_for_year(data["CTC_ps"]["value"], year, mars_psl)
            if val is not None:
                phase_outs[status] = int(val)
        if phase_outs:
            result["phase_out_threshold"] = phase_outs

    return result


def extract_year_data(data: dict[str, Any], year: int) -> dict[str, Any]:
    """Extract all relevant tax data for a single year.

    Returns:
        Normalized data dict for the given year.
    """
    rates = extract_rates(data, year)

    return {
        "year": year,
        "tax_brackets": extract_bracket_thresholds(data, year),
        "tax_rates": rates,
        "standard_deductions": extract_standard_deductions(data, year),
        "aged_deductions": extract_aged_deductions(data, year),
        "fica": extract_fica(data, year),
        "child_tax_credit": extract_ctc(data, year),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_currency(value: float) -> str:
    """Format a number as currency for display."""
    return f"${value:,.0f}"


def _print_brackets_checklist(year_data: dict[str, Any]) -> None:
    """Print bracket and rate verification checklist items."""
    brackets = year_data["tax_brackets"]
    rates = year_data["tax_rates"]

    if "married_filing_jointly" in brackets:
        click.echo("  Tax Brackets (MFJ):")
        for b in brackets["married_filing_jointly"]:
            if b["threshold"] is not None:
                pct = f"{b['rate'] * 100:.0f}%"
                click.echo(f"  [ ] {pct} threshold: {_format_currency(b['threshold'])} — check IRS Rev. Proc.")

    click.echo("\n  Tax Rates:")
    for i, rate in enumerate(rates, 1):
        click.echo(f"  [ ] Rate {i}: {rate * 100:.1f}%")


def _print_deductions_checklist(year_data: dict[str, Any]) -> None:
    """Print deduction and CTC verification checklist items."""
    std = year_data["standard_deductions"]
    aged = year_data["aged_deductions"]
    ctc = year_data["child_tax_credit"]

    click.echo("\n  Standard Deductions:")
    for status, amount in std.items():
        label = status.replace("_", " ").title()
        click.echo(f"  [ ] {label}: {_format_currency(amount)}")

    if aged:
        click.echo("\n  Age 65+ Additional Deduction:")
        for key, amount in aged.items():
            click.echo(f"  [ ] {key.title()}: {_format_currency(amount)}")

    click.echo("\n  Child Tax Credit:")
    if "amount_per_child" in ctc:
        click.echo(f"  [ ] Per child: {_format_currency(ctc['amount_per_child'])}")
    if "refundable_portion" in ctc:
        click.echo(f"  [ ] Refundable: {_format_currency(ctc['refundable_portion'])}")
    if "phase_out_threshold" in ctc:
        for status, threshold in ctc["phase_out_threshold"].items():
            label = status.replace("_", " ").title()
            click.echo(f"  [ ] Phase-out {label}: {_format_currency(threshold)}")


def _print_fica_checklist(year_data: dict[str, Any]) -> None:
    """Print FICA verification checklist items."""
    fica = year_data["fica"]

    if "social_security" in fica:
        ss = fica["social_security"]
        click.echo("\n  FICA - Social Security:")
        click.echo(f"  [ ] Wage base: {_format_currency(ss['wage_base_limit'])} — check SSA.gov")
        click.echo(f"  [ ] Employee rate: {ss['employee_rate']}")
        click.echo(f"  [ ] Max employee tax: {_format_currency(ss['max_employee_tax'])}")

    if "additional_medicare" in fica:
        am = fica["additional_medicare"]
        click.echo("\n  FICA - Additional Medicare:")
        click.echo(f"  [ ] Rate: {am['rate']}")
        for status, threshold in am["thresholds"].items():
            label = status.replace("_", " ").title()
            click.echo(f"  [ ] Threshold {label}: {_format_currency(threshold)}")


def _print_verification_checklist(year: int, year_data: dict[str, Any]) -> None:
    """Print a checklist of values to verify against IRS publications."""
    click.echo(f"\nDRAFT files generated for {year}. VERIFY BEFORE USE:\n")
    _print_brackets_checklist(year_data)
    _print_deductions_checklist(year_data)
    _print_fica_checklist(year_data)
    click.echo("\nAfter verification:")
    click.echo('  1. Update "source" and "citations" fields with actual IRS sources')
    click.echo('  2. Set "verified_date" to today')
    click.echo("  3. Add validation test class to test_irs_data_validation.py")
    click.echo("  4. Run: uv run pytest tests/unit/test_irs_data_validation.py -v")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Fetch PSLmodels Tax-Calculator data for cross-validation or draft generation."""


@cli.command()
@click.option(
    "--years",
    type=int,
    multiple=True,
    help="Tax years to extract. Defaults to years with both local tax and FICA data files.",
)
def snapshot(years: tuple[int, ...]) -> None:
    """Generate snapshot JSON for cross-validation tests."""
    if not years:
        bracket_years = {path.stem.removeprefix("tax_brackets_") for path in DATA_DIR.glob("tax_brackets_*.json")}
        fica_years = {path.stem.removeprefix("fica_limits_") for path in DATA_DIR.glob("fica_limits_*.json")}
        years = tuple(sorted(int(year) for year in bracket_years & fica_years))
    if not years:
        raise click.ClickException("No supported tax years were found in the local data directory")

    data = fetch_pslmodels_data()

    snapshot_data: dict[str, Any] = {
        "source": "PSLmodels Tax-Calculator policy_current_law.json",
        "url": PSLMODELS_URL,
        "generated_date": date.today().isoformat(),
        "notes": (
            "Cross-reference data — NOT the source of truth. "
            "See docs/irs_data_sources.md for authoritative IRS sources."
        ),
        "years": {},
    }

    for year in years:
        click.echo(f"\nExtracting year {year}...")
        year_data = extract_year_data(data, year)
        snapshot_data["years"][str(year)] = year_data

        # Quick sanity summary
        brackets = year_data["tax_brackets"]
        rates = year_data["tax_rates"]
        std = year_data["standard_deductions"]
        fica = year_data["fica"]
        ctc = year_data["child_tax_credit"]
        click.echo(f"  Brackets: {len(brackets)} statuses, 7 rates each")
        click.echo(f"  Rates: {rates}")
        click.echo(f"  Standard deductions: {std}")
        if "social_security" in fica:
            click.echo(f"  SS wage base: {fica['social_security']['wage_base_limit']:,}")
        click.echo(f"  CTC: {ctc.get('amount_per_child', 'N/A')}")

    TESTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TESTS_DATA_DIR / "pslmodels_snapshot.json"
    with out_path.open("w") as f:
        json.dump(snapshot_data, f, indent="\t")
        f.write("\n")

    click.echo(f"\nSnapshot written to {out_path.relative_to(PROJECT_ROOT)}")
    click.echo(f"  Years: {', '.join(str(y) for y in years)}")
    click.echo("  Use with: uv run pytest tests/unit/test_pslmodels_cross_check.py -v")


@cli.command()
@click.option("--year", type=int, required=True, help="Tax year to generate (e.g., 2027).")
@click.option("--dry-run", is_flag=True, help="Print draft files to stdout without writing.")
@click.option("--force", is_flag=True, help="Overwrite existing files.")
def draft(year: int, dry_run: bool, force: bool) -> None:
    """Generate draft tax data files for a new year."""
    data = fetch_pslmodels_data()
    click.echo(f"\nExtracting year {year}...")
    year_data = extract_year_data(data, year)

    today = date.today().isoformat()

    # --- Tax brackets file ---
    brackets_file = _build_tax_brackets_draft(year, year_data, today)
    brackets_path = DATA_DIR / f"tax_brackets_{year}.json"

    # --- FICA limits file ---
    fica_file = _build_fica_limits_draft(year, year_data, today)
    fica_path = DATA_DIR / f"fica_limits_{year}.json"

    if dry_run:
        click.echo(f"\n=== DRAFT tax_brackets_{year}.json ===\n")
        click.echo(json.dumps(brackets_file, indent="\t"))
        click.echo(f"\n=== DRAFT fica_limits_{year}.json ===\n")
        click.echo(json.dumps(fica_file, indent="\t"))
    else:
        # Check for existing files
        for path, label in [(brackets_path, "tax brackets"), (fica_path, "FICA limits")]:
            if path.exists() and not force:
                raise click.ClickException(
                    f"{label} file already exists: {path.relative_to(PROJECT_ROOT)}\n  Use --force to overwrite."
                )

        with brackets_path.open("w") as f:
            json.dump(brackets_file, f, indent="\t")
            f.write("\n")
        click.echo(f"  Wrote {brackets_path.relative_to(PROJECT_ROOT)}")

        with fica_path.open("w") as f:
            json.dump(fica_file, f, indent="\t")
            f.write("\n")
        click.echo(f"  Wrote {fica_path.relative_to(PROJECT_ROOT)}")

    # Print verification checklist
    _print_verification_checklist(year, year_data)


def _build_tax_brackets_draft(year: int, year_data: dict[str, Any], today: str) -> dict[str, Any]:
    """Build draft tax_brackets_YYYY.json content."""
    brackets = year_data["tax_brackets"]
    std = year_data["standard_deductions"]
    aged = year_data["aged_deductions"]
    ctc = year_data["child_tax_credit"]

    # Convert brackets to project format (threshold as int or null)
    formatted_brackets: dict[str, list[dict[str, Any]]] = {}
    for status, bracket_list in brackets.items():
        formatted: list[dict[str, Any]] = []
        for b in bracket_list:
            threshold = int(b["threshold"]) if b["threshold"] is not None else None
            formatted.append({"threshold": threshold, "rate": b["rate"]})
        formatted_brackets[status] = formatted

    return {
        "tax_year": year,
        "last_updated": today,
        "source": "DRAFT — PSLmodels Tax-Calculator (VERIFY AGAINST IRS PUBLICATIONS)",
        "notes": "Auto-generated from PSLmodels. Must verify against IRS Rev. Proc. before use.",
        "citations": {
            "tax_brackets": "https://www.irs.gov/filing/federal-income-tax-rates-and-brackets",
            "standard_deductions": "TODO: Add IRS source URL",
            "child_tax_credit": "TODO: Add IRS source URL",
            "revenue_procedure": "TODO: Add IRS Rev. Proc. URL",
        },
        "verified_date": None,
        "tax_brackets": formatted_brackets,
        "standard_deductions": {
            "amounts": std,
            "additional_age_65_plus": aged,
        },
        "child_tax_credit": {
            "amount_per_child": ctc.get("amount_per_child"),
            "refundable_portion": ctc.get("refundable_portion"),
            "phase_out_threshold": ctc.get("phase_out_threshold", {}),
        },
    }


def _build_fica_limits_draft(year: int, year_data: dict[str, Any], today: str) -> dict[str, Any]:
    """Build draft fica_limits_YYYY.json content."""
    fica = year_data["fica"]

    return {
        "tax_year": year,
        "last_updated": today,
        "source": "DRAFT — PSLmodels Tax-Calculator (VERIFY AGAINST IRS PUBLICATIONS)",
        "citations": {
            "social_security_wage_base": "https://www.ssa.gov/oact/cola/cbbdet.html",
            "fica_rates": "https://www.irs.gov/taxtopics/tc751",
            "additional_medicare": (
                "https://www.irs.gov/businesses/small-businesses-self-employed"
                "/questions-and-answers-for-the-additional-medicare-tax"
            ),
        },
        "verified_date": None,
        **{k: v for k, v in fica.items() if k != "combined_rates"},
        "combined_rates": fica.get("combined_rates", {}),
    }


if __name__ == "__main__":
    cli()
