"""Select CI jobs from the complete Git diff, without third-party actions or APIs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

PYTHON_INPUTS = ("pyproject.toml", "uv.lock", ".python-version")
FILTERS = {
    "frontend": ("frontend/**", ".nvmrc"),
    "container": ("Dockerfile", ".dockerignore", "README.md", "pyproject.toml", "src/**", "frontend/**", ".nvmrc"),
    "e2e": ("src/**", "frontend/**", ".nvmrc", *PYTHON_INPUTS),
    "test": ("src/**", "tests/**", "scripts/**", *PYTHON_INPUTS),
    "typecheck": ("src/**", *PYTHON_INPUTS),
    "security": ("pyproject.toml", "uv.lock"),
    "psl": (
        "src/taxtracker/data/**",
        "src/taxtracker/core/**",
        "src/taxtracker/__init__.py",
        "src/taxtracker/services/__init__.py",
        "src/taxtracker/models/**",
        "src/taxtracker/services/data_loader.py",
        "scripts/fetch_pslmodels_data.py",
        "tests/unit/test_pslmodels_cross_check.py",
        "tests/data/**",
        "tests/conftest.py",
        "tests/**/conftest.py",
        *PYTHON_INPUTS,
    ),
}
# These paths still receive the always-on pre-commit checks and filter tests.
CHECKS_ONLY = (
    ".github/**",
    ".zed/**",
    ".vscode/**",
    "docs/**",
    "*.md",
    "LICENSE*",
    ".gitignore",
    ".pre-commit-config.yaml",
    "justfile",
    ".editorconfig",
)


def select_jobs(paths: list[str]) -> dict[str, bool]:
    """Combine relevant jobs; unknown inputs conservatively enable the full suite."""
    selected = dict.fromkeys(FILTERS, False)
    for path in paths:
        matched = False
        for job, patterns in FILTERS.items():
            if any(fnmatchcase(path, pattern) for pattern in patterns):
                selected[job] = True
                matched = True
        if not matched and not any(fnmatchcase(path, pattern) for pattern in CHECKS_ONLY):
            return dict.fromkeys(FILTERS, True)
    return selected


def changed_paths(base: str, *, pull_request: bool) -> list[str]:
    """Include deletions and both sides of renames, with no API file-count limit."""
    comparison = f"{base}...HEAD" if pull_request else f"{base}..HEAD"
    output = subprocess.check_output(  # noqa: S603 - arguments come from GitHub's commit SHAs
        ["git", "diff", "--no-renames", "--name-only", "-z", comparison, "--"],  # noqa: S607
    )
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def detect_jobs(event_name: str, event: dict[str, Any]) -> dict[str, bool]:
    """Compare PRs to their merge base, pushes to their previous tip; fail open."""
    if event_name == "pull_request":
        base = event["pull_request"]["base"]["sha"]
    elif event_name == "push":
        base = event["before"]
    else:
        return dict.fromkeys(FILTERS, True)
    if not base or base == "0" * 40:
        return dict.fromkeys(FILTERS, True)
    try:
        paths = changed_paths(base, pull_request=event_name == "pull_request")
    except subprocess.CalledProcessError:
        sys.stderr.write("Unable to compare commits; running the full CI suite.\n")
        return dict.fromkeys(FILTERS, True)
    return select_jobs(paths)


def main() -> None:
    """Write booleans consumed by the workflow's job conditions."""
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    selected = detect_jobs(os.environ["GITHUB_EVENT_NAME"], event)
    output = "".join(f"{job}={str(enabled).lower()}\n" for job, enabled in selected.items())
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as destination:
        destination.write(output)
    sys.stdout.write(output)


if __name__ == "__main__":
    main()
