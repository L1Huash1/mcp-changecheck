"""End-to-end action runner regressions against the real checker."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


def snapshot(required=False):
    schema = {"type": "object", "properties": {"query": {"type": "string"}}}
    if required:
        schema["required"] = ["query"]
    return {"tools": [{"name": "lookup", "inputSchema": schema}]}


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.workspace = self.directory / "workspace with spaces"
        self.workspace.mkdir()
        self.before = self.workspace / "before.json"
        self.after = self.workspace / "after.json"
        for path in (self.before, self.after):
            path.write_text(json.dumps(snapshot()), encoding="utf-8")
        self.outputs = self.directory / "outputs"
        self.summary = self.directory / "summary.md"

    def run_action(self, **overrides):
        env = os.environ.copy()
        env.update({"PYTHONPATH": str(PROJECT / "src"), "PYTHONIOENCODING": "utf-8",
                    "GITHUB_WORKSPACE": str(self.workspace), "GITHUB_OUTPUT": str(self.outputs),
                    "GITHUB_STEP_SUMMARY": str(self.summary), "MCP_BEFORE": "before.json",
                    "MCP_AFTER": "after.json", "MCP_FAIL_ON": "review",
                    "MCP_REPORT_PATH": "reports/result.md", "MCP_SUMMARY": "true"})
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run([sys.executable, str(PROJECT / "action" / "run.py")],
                              env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)

    def read_outputs(self):
        values = {}
        lines = iter(self.outputs.read_text(encoding="utf-8").splitlines())
        for line in lines:
            key, delimiter = line.split("<<", 1)
            parts = []
            for value in lines:
                if value == delimiter:
                    break
                parts.append(value)
            values[key] = "\n".join(parts)
        return values

    def test_passing_snapshot_generates_report_outputs_and_summary(self):
        self.summary.write_text("Existing summary\n", encoding="utf-8")
        result = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        outputs = self.read_outputs()
        self.assertEqual(outputs["exit-code"], "0")
        report = Path(outputs["report-path"])
        self.assertTrue(report.is_file())
        self.assertIn(report.read_text(encoding="utf-8"), self.summary.read_text(encoding="utf-8"))
        self.assertTrue(self.summary.read_text(encoding="utf-8").startswith("Existing summary\n"))

    def test_breaking_change_fails_but_keeps_a_readable_report(self):
        self.after.write_text(json.dumps(snapshot(required=True)), encoding="utf-8")
        result = self.run_action()
        self.assertEqual(result.returncode, 1, result.stderr)
        outputs = self.read_outputs()
        self.assertEqual(outputs["exit-code"], "1")
        self.assertIn("breaking", Path(outputs["report-path"]).read_text(encoding="utf-8").lower())
        self.assertTrue(self.summary.exists())

    def test_repository_examples_keep_escaped_tool_names_in_the_markdown_report(self):
        result = self.run_action(MCP_BEFORE=str(PROJECT / "examples" / "before.json"),
                                 MCP_AFTER=str(PROJECT / "examples" / "after.json"))
        self.assertEqual(result.returncode, 1, result.stderr)
        report = Path(self.read_outputs()["report-path"]).read_text(encoding="utf-8")
        self.assertIn(r"archive\_note", report)
        self.assertIn("breaking", report.lower())

    def test_never_threshold_keeps_findings_without_failing(self):
        self.after.write_text(json.dumps(snapshot(required=True)), encoding="utf-8")
        result = self.run_action(MCP_FAIL_ON="never")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_outputs()["exit-code"], "0")
        self.assertIn("breaking", self.summary.read_text(encoding="utf-8").lower())

    def test_invalid_input_does_not_publish_an_existing_stale_report(self):
        self.after.write_text("{broken", encoding="utf-8")
        report = self.workspace / "report.md"
        report.write_text("stale report", encoding="utf-8")
        result = self.run_action(MCP_REPORT_PATH="report.md")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.read_outputs(), {"exit-code": "2", "report-path": ""})
        self.assertFalse(self.summary.exists())
        self.assertEqual(report.read_text(encoding="utf-8"), "stale report")

    def test_summary_can_be_disabled_without_a_summary_environment_file(self):
        result = self.run_action(MCP_SUMMARY="false", GITHUB_STEP_SUMMARY=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(self.read_outputs()["report-path"]).exists())
        self.assertFalse(self.summary.exists())

    def test_report_cannot_escape_the_workspace(self):
        result = self.run_action(MCP_REPORT_PATH="../outside.md")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.directory / "outside.md").exists())
        self.assertEqual(self.read_outputs()["report-path"], "")

    def test_output_alias_cannot_overwrite_snapshot(self):
        original = self.before.read_bytes()
        alias = self.workspace / "report.md"
        try:
            os.link(self.before, alias)
        except OSError as error:
            self.skipTest(f"Hard links unavailable: {error}")
        result = self.run_action(MCP_REPORT_PATH="report.md")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.before.read_bytes(), original)
        self.assertEqual(self.read_outputs()["report-path"], "")

    def test_shell_metacharacters_and_unicode_are_literal_paths(self):
        name = "快照 $(echo injected); notes.json"
        source = self.workspace / name
        source.write_bytes(self.before.read_bytes())
        result = self.run_action(MCP_BEFORE=name, MCP_AFTER=name,
                                 MCP_REPORT_PATH="结果 $(echo injected); report.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(self.read_outputs()["report-path"]).is_file())
        self.assertEqual(source.read_bytes(), self.before.read_bytes())

    def test_leading_dash_snapshot_path_is_not_a_cli_option(self):
        source = self.workspace / "--version"
        source.write_bytes(self.before.read_bytes())
        result = self.run_action(MCP_BEFORE=source.name, MCP_AFTER=source.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.summary.exists())

    def test_bad_configuration_and_missing_inputs_return_two(self):
        for overrides in ({"MCP_BEFORE": ""}, {"MCP_AFTER": "missing.json"},
                          {"MCP_FAIL_ON": "invalid"}, {"MCP_SUMMARY": "maybe"},
                          {"GITHUB_WORKSPACE": None}):
            with self.subTest(overrides=overrides):
                result = self.run_action(**overrides)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_runner_output_file_is_a_clear_error(self):
        result = self.run_action(GITHUB_OUTPUT=None)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("GITHUB_OUTPUT", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_untrusted_diagnostic_cannot_emit_runner_commands(self):
        result = self.run_action(MCP_AFTER="missing\n::warning::forged.json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("::warning::", result.stderr)
        self.assertNotIn("\nforged", result.stderr)
        self.assertEqual(self.read_outputs()["report-path"], "")
