"""End-to-end CLI tests using real files and the active Python runtime."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


def snapshot(*names, description=None):
    tools = [{"name": name, "inputSchema": {"type": "object", "properties": {}}} for name in names]
    if description is not None:
        tools[0]["description"] = description
    return {"tools": tools}


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.before = self.directory / "before.json"
        self.after = self.directory / "after.json"
        self.write_snapshots(snapshot("search"), snapshot("search"))

    def write_snapshots(self, before, after):
        self.before.write_text(json.dumps(before), encoding="utf-8")
        self.after.write_text(json.dumps(after), encoding="utf-8")

    def run_cli(self, *args):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run([sys.executable, "-m", "mcp_changecheck", *map(str, args)],
                              cwd=self.directory, env=env, capture_output=True,
                              text=True, encoding="utf-8", timeout=20)

    def compare(self, *options):
        return self.run_cli(self.before, self.after, *options)

    def assert_user_error(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertTrue(result.stderr.strip(), result)
        self.assertNotIn("Traceback", result.stderr)

    def test_version_runs_without_snapshot_paths(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"\d+\.\d+")

    def test_identical_snapshots_pass_and_json_has_report_schema(self):
        result = self.compare("--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["summary"], {"breaking": 0, "review": 0, "info": 0})
        self.assertEqual(result.stderr, "")

    def test_default_threshold_fails_on_breaking_change(self):
        self.write_snapshots(snapshot("search"), snapshot())
        result = self.compare()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_default_threshold_fails_on_review_change(self):
        self.write_snapshots(snapshot("search", description="Search notes"),
                             snapshot("search", description="Delete notes"))
        result = self.compare()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_default_threshold_allows_informational_change(self):
        self.write_snapshots(snapshot("search"), snapshot("search", "new_tool"))
        result = self.compare()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_breaking_threshold_allows_review(self):
        self.write_snapshots(snapshot("search", description="Old"), snapshot("search", description="New"))
        result = self.compare("--fail-on", "breaking")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_review_threshold_includes_breaking_changes(self):
        self.write_snapshots(snapshot("search"), snapshot())
        result = self.compare("--fail-on", "review")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_breaking_threshold_fails_when_input_type_is_replaced(self):
        for old_type, new_type in (("string", "integer"),
                                   (["string", "null"], ["number", "null"])):
            before, after = snapshot("search"), snapshot("search")
            before["tools"][0]["inputSchema"]["properties"]["q"] = {"type": old_type}
            after["tools"][0]["inputSchema"]["properties"]["q"] = {"type": new_type}
            self.write_snapshots(before, after)
            with self.subTest(old=old_type, new=new_type):
                result = self.compare("--fail-on", "breaking", "--format", "json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertGreater(json.loads(result.stdout)["summary"]["breaking"], 0)

    def test_default_threshold_fails_on_pattern_property_restriction(self):
        before, after = snapshot("search"), snapshot("search")
        for data in (before, after):
            data["tools"][0]["inputSchema"].update(
                {"patternProperties": {"^q$": {}}, "additionalProperties": False})
        after["tools"][0]["inputSchema"]["properties"]["q"] = {"type": "string"}
        self.write_snapshots(before, after)
        result = self.compare("--format", "json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertGreater(json.loads(result.stdout)["summary"]["review"], 0)

    def test_any_threshold_fails_on_informational_change(self):
        self.write_snapshots(snapshot(), snapshot("new_tool"))
        result = self.compare("--fail-on", "any")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_never_threshold_allows_breaking_changes(self):
        self.write_snapshots(snapshot("search"), snapshot())
        result = self.compare("--fail-on", "never")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_never_threshold_does_not_hide_invalid_input(self):
        self.after.write_text("{", encoding="utf-8")
        self.assert_user_error(self.compare("--fail-on", "never"))

    def test_text_and_markdown_report_identify_changed_tool(self):
        self.write_snapshots(snapshot("removed"), snapshot())
        for format_name in ("text", "markdown"):
            with self.subTest(format_name=format_name):
                result = self.compare("--format", format_name)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("removed", result.stdout)
                self.assertIn("breaking", result.stdout.lower())

    def test_markdown_escapes_markup_and_renders_control_characters_inert(self):
        name = "<script>|*danger*\nFORGED\t\x1b"
        self.write_snapshots(snapshot(name), snapshot())
        result = self.compare("--format", "markdown")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("<script>", result.stdout)
        self.assertIn("&lt;script&gt;", result.stdout)
        self.assertIn(r"\|", result.stdout)
        self.assertIn(r"\*danger\*", result.stdout)
        self.assertNotIn("\nFORGED", result.stdout)
        self.assertNotIn("\t", result.stdout)
        self.assertNotIn("\x1b", result.stdout)

    def test_output_path_receives_report_without_stdout(self):
        target = self.directory / "report.json"
        result = self.compare("--format", "json", "--output", target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["changes"], [])

    def test_report_is_written_even_when_threshold_fails(self):
        target = self.directory / "report.json"
        self.write_snapshots(snapshot("search"), snapshot())
        result = self.compare("--format", "json", "--output", target)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        report = json.loads(target.read_text(encoding="utf-8"))
        self.assertGreater(report["summary"]["breaking"], 0)

    def test_output_cannot_overwrite_either_input_snapshot(self):
        before_bytes, after_bytes = self.before.read_bytes(), self.after.read_bytes()
        for target in (self.before, self.after):
            with self.subTest(target=target):
                self.assert_user_error(self.compare("--format", "json", "--output", target))
                self.assertEqual(self.before.read_bytes(), before_bytes)
                self.assertEqual(self.after.read_bytes(), after_bytes)

    def test_utf8_bom_snapshots_are_supported(self):
        self.before.write_text(json.dumps(snapshot("search")), encoding="utf-8-sig")
        self.after.write_text(json.dumps(snapshot("search")), encoding="utf-8-sig")
        result = self.compare("--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["changes"], [])

    def test_unicode_names_and_paths_work(self):
        self.before = self.directory / "变更前.json"
        self.after = self.directory / "变更后.json"
        self.write_snapshots(snapshot("搜索"), snapshot())
        result = self.compare("--format", "json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["changes"][0]["tool"], "搜索")

    def test_duplicate_json_keys_are_rejected_even_inside_schema(self):
        self.after.write_text('{"tools":[{"name":"search","inputSchema":{"type":"object",'
                              '"properties":{"q":{"type":"string","type":"integer"}}}}]}',
                              encoding="utf-8")
        self.assert_user_error(self.compare())

    def test_nonfinite_json_numbers_are_rejected(self):
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(literal=literal):
                self.after.write_text('{"tools":[{"name":"search","inputSchema":'
                                      '{"type":"object","default":' + literal + '}}]}', encoding="utf-8")
                self.assert_user_error(self.compare())

    def test_invalid_json_has_diagnostic_without_traceback(self):
        self.after.write_text("{broken", encoding="utf-8")
        self.assert_user_error(self.compare())

    def test_invalid_utf8_has_diagnostic_without_traceback(self):
        self.after.write_bytes(b"\xff\xfe\xff")
        self.assert_user_error(self.compare())

    def test_invalid_snapshot_has_diagnostic_without_traceback(self):
        self.after.write_text('{"tools":[{"name":"search"}]}', encoding="utf-8")
        self.assert_user_error(self.compare())

    def test_missing_input_file_has_diagnostic_without_traceback(self):
        self.after.unlink()
        self.assert_user_error(self.compare())

    def test_unwritable_output_has_diagnostic_without_traceback(self):
        self.assert_user_error(self.compare("--output", self.directory))

    def test_unknown_option_value_is_usage_error(self):
        self.assert_user_error(self.compare("--fail-on", "sometimes"))

    def test_html_report_is_written_and_threshold_is_preserved(self):
        self.write_snapshots(snapshot("removed"), snapshot())
        target = self.directory / "report.html"
        result = self.compare("--format", "html", "--output", target)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        content = target.read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", content.lower())
        self.assertIn("removed", content)
        self.assertIn("Content-Security-Policy", content)

    def test_decimal_values_that_would_be_silently_rounded_are_rejected(self):
        for literal in ("0.100000000000000000001", "9007199254740993.0", "1e999", "1e-99999999999999999999"):
            with self.subTest(literal=literal):
                self.after.write_text('{"tools":[{"name":"search","inputSchema":'
                                      '{"type":"object","properties":{"q":{"enum":['
                                      + literal + ']}}}}]}', encoding="utf-8")
                self.assert_user_error(self.compare())

    def test_exact_large_numeric_equivalents_do_not_report_changes(self):
        before, after = snapshot("search"), snapshot("search")
        before['tools'][0]['inputSchema']['properties']['q'] = {'enum': [10 ** 100]}
        after['tools'][0]['inputSchema']['properties']['q'] = {'enum': [1e100]}
        self.write_snapshots(before, after)
        result = self.compare("--format", "json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['changes'], [])

    def test_normal_decimal_values_remain_supported(self):
        data = snapshot("search")
        data['tools'][0]['inputSchema']['properties']['q'] = {'enum': [0.1, 2.5, 1e100]}
        self.write_snapshots(data, data)
        result = self.compare("--format", "json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
