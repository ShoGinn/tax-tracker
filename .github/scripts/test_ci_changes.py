"""Regression tests for selective CI, runnable with the standard library alone."""

# This suite runs before installing dependencies, using standard-library unittest.
# ruff: noqa: PT009

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ci_changes import FILTERS, changed_paths, detect_jobs, main, select_jobs


class TestCIChanges(unittest.TestCase):
    def test_ci_editor_and_docs_changes_skip_product_jobs(self) -> None:
        for path in [
            ".github/workflows/ci.yml",
            ".github/scripts/ci_changes.py",
            ".zed/settings.json",
            "docs/setup.md",
        ]:
            with self.subTest(path=path):
                self.assertFalse(any(select_jobs([path]).values()))

    def test_frontend_changes_cover_browser_and_container(self) -> None:
        for path in ["frontend/src/app.tsx", "frontend/e2e/workflow.spec.ts", "frontend/pnpm-lock.yaml", ".nvmrc"]:
            with self.subTest(path=path):
                jobs = select_jobs([path])
                self.assertTrue(jobs["frontend"])
                self.assertTrue(jobs["e2e"])
                self.assertTrue(jobs["container"])
                self.assertFalse(jobs["test"])
                self.assertFalse(jobs["security"])

    def test_backend_runtime_changes_cover_browser(self) -> None:
        jobs = select_jobs(["src/taxtracker/api/taxes.py"])
        self.assertTrue(jobs["test"])
        self.assertTrue(jobs["typecheck"])
        self.assertTrue(jobs["e2e"])
        self.assertTrue(jobs["container"])
        self.assertFalse(jobs["frontend"])
        self.assertFalse(jobs["psl"])

    def test_python_dependencies_cover_security_and_runtime(self) -> None:
        jobs = select_jobs(["uv.lock"])
        self.assertTrue(jobs["security"])
        self.assertTrue(jobs["test"])
        self.assertTrue(jobs["typecheck"])
        self.assertTrue(jobs["e2e"])
        self.assertTrue(jobs["psl"])
        self.assertFalse(jobs["frontend"])

    def test_backend_tests_skip_browser(self) -> None:
        jobs = select_jobs(["tests/unit/test_tax_calculator.py"])
        self.assertTrue(jobs["test"])
        self.assertFalse(jobs["e2e"])
        self.assertFalse(jobs["typecheck"])

    def test_tax_data_and_loader_trigger_psl(self) -> None:
        for path in [
            "src/taxtracker/data/2026.json",
            "src/taxtracker/services/data_loader.py",
            "scripts/fetch_pslmodels_data.py",
            "tests/data/pslmodels_snapshot.json",
        ]:
            with self.subTest(path=path):
                self.assertTrue(select_jobs([path])["psl"])

    def test_container_inputs_skip_browser(self) -> None:
        for path in ["Dockerfile", ".dockerignore", "README.md"]:
            with self.subTest(path=path):
                jobs = select_jobs([path])
                self.assertTrue(jobs["container"])
                self.assertFalse(jobs["e2e"])

    def test_unknown_paths_run_everything(self) -> None:
        self.assertTrue(all(select_jobs(["new-runtime-config.json"]).values()))

    def test_mixed_changes_combine_jobs(self) -> None:
        jobs = select_jobs([".github/workflows/ci.yml", "frontend/src/app.tsx", "tests/unit/test_tax_calculator.py"])
        self.assertTrue(jobs["frontend"])
        self.assertTrue(jobs["test"])
        self.assertTrue(jobs["e2e"])

    def test_empty_diff_skips_product_jobs(self) -> None:
        self.assertFalse(any(select_jobs([]).values()))

    def test_manual_and_initial_push_run_full_suite(self) -> None:
        self.assertTrue(all(detect_jobs("workflow_dispatch", {}).values()))
        self.assertTrue(all(detect_jobs("push", {"before": "0" * 40}).values()))

    def test_pr_and_push_use_correct_comparisons(self) -> None:
        with patch("ci_changes.changed_paths", return_value=["docs/setup.md"]) as diff:
            detect_jobs("pull_request", {"pull_request": {"base": {"sha": "abc"}}})
            diff.assert_called_once_with("abc", pull_request=True)
            diff.reset_mock()
            detect_jobs("push", {"before": "def"})
            diff.assert_called_once_with("def", pull_request=False)

    def test_missing_history_runs_full_suite(self) -> None:
        with patch("ci_changes.changed_paths", side_effect=subprocess.CalledProcessError(1, "git")):
            self.assertEqual(detect_jobs("push", {"before": "abc"}), dict.fromkeys(FILTERS, True))

    def test_output_protocol_appends_all_boolean_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / "event.json"
            output = Path(directory) / "output"
            event.write_text("{}")
            output.write_text("existing=value\n")
            environment = {
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_EVENT_PATH": str(event),
                "GITHUB_OUTPUT": str(output),
            }
            with patch.dict(os.environ, environment), patch("ci_changes.sys.stdout"):
                main()
            self.assertEqual(output.read_text(), "existing=value\n" + "".join(f"{job}=true\n" for job in FILTERS))

    def test_git_diff_includes_deleted_and_renamed_paths(self) -> None:
        with patch("ci_changes.subprocess.check_output", return_value=b"src/old.py\0docs/new name.md\0") as diff:
            self.assertEqual(changed_paths("abc", pull_request=True), ["src/old.py", "docs/new name.md"])
            self.assertIn("--no-renames", diff.call_args.args[0])
            self.assertIn("abc...HEAD", diff.call_args.args[0])
            changed_paths("abc", pull_request=False)
            self.assertIn("abc..HEAD", diff.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
