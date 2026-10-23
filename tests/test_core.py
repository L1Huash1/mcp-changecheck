"""Regression tests for meaningful MCP tool-contract changes."""

from copy import deepcopy
import unittest

from mcp_changecheck.core import SnapshotError, compare_snapshots, normalize_snapshot


def tool(name="search", *, properties=None, required=None, **fields):
    schema = {"type": "object", "properties": properties or {}}
    if required is not None:
        schema["required"] = required
    return {"name": name, "inputSchema": schema, **fields}


def report_for(before, after):
    return compare_snapshots({"tools": before}, {"tools": after})


class NormalizationTests(unittest.TestCase):
    def test_accepts_supported_list_tools_and_jsonrpc_result_shapes(self):
        expected = tool()
        for value in ([expected], {"tools": [expected]}, {"result": {"tools": [expected]}}):
            with self.subTest(value=value):
                self.assertEqual(normalize_snapshot(value), {"search": expected})

    def test_accepts_empty_complete_snapshot(self):
        for value in ([], {"tools": []}, {"result": {"tools": []}}):
            with self.subTest(value=value):
                self.assertEqual(normalize_snapshot(value), {})

    def test_incomplete_pagination_is_rejected(self):
        for value in (
            {"tools": [tool()], "nextCursor": "page-2"},
            {"result": {"tools": [tool()], "nextCursor": "page-2"}},
        ):
            with self.subTest(value=value), self.assertRaises(SnapshotError):
                normalize_snapshot(value)

    def test_input_required_results_are_not_complete_snapshots(self):
        for value in (
            {"tools": [tool()], "resultType": "input_required"},
            {"result": {"tools": [tool()], "resultType": "input_required"}},
        ):
            with self.subTest(value=value), self.assertRaises(SnapshotError):
                normalize_snapshot(value)

    def test_explicit_complete_result_types_are_accepted(self):
        expected = tool()
        for value in (
            {"tools": [expected], "resultType": "complete"},
            {"result": {"tools": [expected], "resultType": "complete"}},
        ):
            with self.subTest(value=value):
                self.assertEqual(normalize_snapshot(value), {"search": expected})

    def test_duplicate_names_are_rejected(self):
        with self.assertRaises(SnapshotError):
            normalize_snapshot([tool(), tool()])

    def test_missing_or_nonstring_names_are_rejected(self):
        for name in (None, "", 12, False, ["search"]):
            item = tool()
            if name is None:
                del item["name"]
            else:
                item["name"] = name
            with self.subTest(name=name), self.assertRaises(SnapshotError):
                normalize_snapshot([item])

    def test_invalid_containers_are_rejected(self):
        for value in (None, "tools", 1, True, {}, {"tools": {}}, {"tools": [None]}, {"result": []}):
            with self.subTest(value=value), self.assertRaises(SnapshotError):
                normalize_snapshot(value)

    def test_input_schema_must_be_an_object_schema(self):
        for schema in (None, [], True, "object", {"type": "array"}, {"type": "string"}):
            item = tool()
            item["inputSchema"] = schema
            with self.subTest(schema=schema), self.assertRaises(SnapshotError):
                normalize_snapshot([item])

    def test_missing_input_schema_is_rejected(self):
        with self.assertRaises(SnapshotError):
            normalize_snapshot([{"name": "search"}])

    def test_output_schema_accepts_nonobject_json_schema_roots(self):
        for schema in (
            {"type": "array", "items": {"type": "string"}},
            {"type": "string"},
            {"oneOf": [{"type": "string"}, {"type": "array"}]},
            True,
            False,
        ):
            item = tool(outputSchema=schema)
            with self.subTest(schema=schema):
                self.assertEqual(normalize_snapshot([item]), {"search": item})

    def test_output_schema_rejects_values_that_are_not_schemas(self):
        for schema in (None, [], 1, 1.5, "string"):
            with self.subTest(schema=schema), self.assertRaises(SnapshotError):
                normalize_snapshot([tool(outputSchema=schema)])

    def test_malformed_nested_schemas_are_rejected(self):
        bad_schemas = (
            {"type": "object", "properties": []},
            {"type": "object", "properties": {"q": 123}},
            {"type": "object", "properties": {"q": {"type": "strng"}}},
            {"type": "object", "required": "q"},
            {"type": "object", "required": [1]},
            {"type": "object", "properties": {"q": {"enum": "a,b"}}},
            {"type": "object", "additionalProperties": "yes"},
        )
        for schema in bad_schemas:
            with self.subTest(schema=schema), self.assertRaises(SnapshotError):
                normalize_snapshot([{"name": "search", "inputSchema": schema}])

    def test_annotation_flags_must_be_json_booleans(self):
        for key in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
            for bad_value in (1, 0, "false", None):
                with self.subTest(key=key, value=bad_value), self.assertRaises(SnapshotError):
                    normalize_snapshot([tool(annotations={key: bad_value})])


class ComparisonTests(unittest.TestCase):
    def assert_severity(self, report, severity):
        self.assertGreater(report["summary"][severity], 0, report)
        self.assertTrue(any(c["severity"] == severity for c in report["changes"]), report)

    def test_report_has_consistent_schema_and_counts(self):
        report = report_for([tool("old")], [tool("new")])
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(set(report["summary"]), {"breaking", "review", "info"})
        for severity, count in report["summary"].items():
            self.assertEqual(count, sum(c["severity"] == severity for c in report["changes"]))
        for change in report["changes"]:
            self.assertTrue({"severity", "code", "tool", "path", "message"} <= change.keys())
            self.assertIsInstance(change["path"], str)
            self.assertIsInstance(change["message"], str)

    def test_identical_contract_has_no_changes(self):
        item = tool(properties={"q": {"type": "string"}}, required=["q"])
        report = report_for([item], [deepcopy(item)])
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["summary"], {"breaking": 0, "review": 0, "info": 0})

    def test_removed_tool_is_breaking_and_added_tool_is_information(self):
        report = report_for([tool("old")], [tool("new")])
        self.assert_severity(report, "breaking")
        self.assert_severity(report, "info")
        self.assertTrue(any(c["tool"] == "old" and c["severity"] == "breaking" for c in report["changes"]))
        self.assertTrue(any(c["tool"] == "new" and c["severity"] == "info" for c in report["changes"]))

    def test_new_required_property_is_breaking(self):
        before = tool(properties={"q": {"type": "string"}})
        after = tool(properties={"q": {"type": "string"}}, required=["q"])
        self.assert_severity(report_for([before], [after]), "breaking")

    def test_new_required_property_that_was_not_declared_is_breaking(self):
        before = tool()
        after = tool(properties={"q": {"type": "string"}}, required=["q"])
        self.assert_severity(report_for([before], [after]), "breaking")

    def test_input_type_narrowing_is_breaking(self):
        for old_type, new_type in ((["string", "null"], "string"), ("number", "integer")):
            before = tool(properties={"q": {"type": old_type}})
            after = tool(properties={"q": {"type": new_type}})
            with self.subTest(old=old_type, new=new_type):
                self.assert_severity(report_for([before], [after]), "breaking")

    def test_input_type_widening_is_information(self):
        for old_type, new_type in (("string", ["string", "null"]), ("integer", "number")):
            before = tool(properties={"q": {"type": old_type}})
            after = tool(properties={"q": {"type": new_type}})
            with self.subTest(old=old_type, new=new_type):
                report = report_for([before], [after])
                self.assertEqual(report["summary"]["breaking"], 0, report)
                self.assert_severity(report, "info")

    def test_replacing_any_previously_accepted_type_is_breaking(self):
        for old_type, new_type in (("string", "integer"),
                                   (["string", "null"], ["number", "null"])):
            before = tool(properties={"q": {"type": old_type}})
            after = tool(properties={"q": {"type": new_type}})
            with self.subTest(old=old_type, new=new_type):
                self.assert_severity(report_for([before], [after]), "breaking")

    def test_removing_enum_value_is_breaking(self):
        before = tool(properties={"q": {"enum": ["a", "b"]}})
        after = tool(properties={"q": {"enum": ["a"]}})
        self.assert_severity(report_for([before], [after]), "breaking")

    def test_json_enum_values_distinguish_boolean_from_number(self):
        for boolean, number in ((True, 1), (False, 0)):
            before = tool(properties={"q": {"enum": [boolean, number]}})
            after = tool(properties={"q": {"enum": [number]}})
            with self.subTest(boolean=boolean):
                self.assert_severity(report_for([before], [after]), "breaking")

    def test_nested_json_enum_values_also_keep_boolean_and_number_distinct(self):
        before = tool(properties={"q": {"enum": [{"enabled": True}, {"enabled": 1}]}})
        after = tool(properties={"q": {"enum": [{"enabled": 1}]}})
        self.assert_severity(report_for([before], [after]), "breaking")

    def test_property_removed_from_closed_object_is_breaking(self):
        before = tool(properties={"q": {"type": "string"}})
        after = tool()
        before["inputSchema"]["additionalProperties"] = False
        after["inputSchema"]["additionalProperties"] = False
        self.assert_severity(report_for([before], [after]), "breaking")

    def test_property_removed_from_open_object_needs_review(self):
        report = report_for([tool(properties={"q": {"type": "string"}})], [tool()])
        self.assert_severity(report, "review")

    def test_optional_property_added_to_previously_open_object_is_not_assumed_safe(self):
        report = report_for([tool()], [tool(properties={"q": {"type": "string"}})])
        self.assertGreater(report["summary"]["breaking"] + report["summary"]["review"], 0, report)

    def test_optional_property_can_narrow_existing_pattern_properties(self):
        before = tool()
        before["inputSchema"].update({"patternProperties": {"^q$": {}}, "additionalProperties": False})
        after = deepcopy(before)
        after["inputSchema"]["properties"]["q"] = {"type": "string"}
        self.assert_severity(report_for([before], [after]), "review")

    def test_complex_schema_change_needs_review(self):
        before = tool(properties={"q": {"type": "string", "pattern": "^[a-z]+$"}})
        after = tool(properties={"q": {"type": "string", "pattern": "^[a-z0-9]+$"}})
        self.assert_severity(report_for([before], [after]), "review")

    def test_output_schema_changes_need_review(self):
        before = tool(outputSchema={"type": "object", "properties": {"count": {"type": "integer"}}})
        after = tool(outputSchema={"type": "object", "properties": {"count": {"type": "string"}}})
        self.assert_severity(report_for([before], [after]), "review")

    def test_unchanged_nonobject_output_schema_has_no_changes(self):
        for schema in (
            {"type": "array", "items": {"type": "string"}},
            {"type": "string"},
            {"anyOf": [{"type": "null"}, {"type": "string"}]},
            True,
            False,
        ):
            item = tool(outputSchema=schema)
            with self.subTest(schema=schema):
                report = report_for([item], [deepcopy(item)])
                self.assertEqual(report["changes"], [], report)
                self.assertEqual(report["summary"], {"breaking": 0, "review": 0, "info": 0})

    def test_changed_nonobject_output_schema_needs_review(self):
        for old_schema, new_schema in (
            ({"type": "array"}, {"type": "string"}),
            ({"anyOf": [{"type": "null"}, {"type": "string"}]}, {"type": "string"}),
            (True, False),
        ):
            with self.subTest(old=old_schema, new=new_schema):
                report = report_for([tool(outputSchema=old_schema)], [tool(outputSchema=new_schema)])
                self.assert_severity(report, "review")
                self.assertEqual(report["summary"]["breaking"], 0, report)

    def test_description_change_needs_review(self):
        self.assert_severity(report_for([tool(description="Search notes")], [tool(description="Delete notes")]), "review")

    def test_explicit_hint_defaults_equal_omitted_hints(self):
        after = tool(annotations={"readOnlyHint": False, "destructiveHint": True,
                                  "idempotentHint": False, "openWorldHint": True})
        report = report_for([tool()], [after])
        self.assertEqual(report["changes"], [], report)

    def test_semantic_hint_changes_need_review(self):
        defaults = {"readOnlyHint": False, "destructiveHint": True,
                    "idempotentHint": False, "openWorldHint": True}
        for key, default in defaults.items():
            with self.subTest(key=key):
                report = report_for([tool()], [tool(annotations={key: not default})])
                self.assert_severity(report, "review")

    def test_order_of_tools_properties_required_types_and_enum_is_irrelevant(self):
        before = tool(properties={"q": {"type": ["null", "string"], "enum": [None, "a", "b"]},
                                  "limit": {"type": "integer"}}, required=["q", "limit"])
        after = tool(properties={"limit": {"type": "integer"},
                                 "q": {"enum": ["b", "a", None], "type": ["string", "null"]}},
                     required=["limit", "q"])
        report = report_for([before, tool("other")], [tool("other"), after])
        self.assertEqual(report["changes"], [], report)

    def test_comparison_does_not_mutate_inputs(self):
        before = {"tools": [tool(properties={"q": {"type": ["string", "null"]}})]}
        after = {"tools": [tool(properties={"q": {"type": "string"}})]}
        original_before, original_after = deepcopy(before), deepcopy(after)
        compare_snapshots(before, after)
        self.assertEqual(before, original_before)
        self.assertEqual(after, original_after)


if __name__ == "__main__":
    unittest.main()
