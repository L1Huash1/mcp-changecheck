"""Safety and usability checks for the self-contained HTML artifact."""

from html.parser import HTMLParser
import json
import re
import unittest

from mcp_changecheck.html_report import render_html


def report(*changes):
    return {"schema_version": 1, "summary": {
        level: sum(c["severity"] == level for c in changes)
        for level in ("breaking", "review", "info")
    }, "changes": list(changes)}


def change(**fields):
    return {"severity": "breaking", "code": "enum_changed", "tool": "search",
            "path": "/inputSchema/properties/query/enum", "message": "An input value was removed.",
            "before": [True, 1, None], "after": [1], **fields}


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.scripts = []
        self.code_values = []
        self.content = []
        self._script = False
        self._code = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "script":
            self._script = True
            self.scripts.append("")
        if tag == "code":
            self._code = True
            self.code_values.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._script = False
        if tag == "code":
            self._code = False

    def handle_data(self, data):
        self.content.append(data)
        if self._script:
            self.scripts[-1] += data
        if self._code:
            self.code_values[-1] += data


class HtmlReportTests(unittest.TestCase):
    def test_complete_self_contained_document_with_no_external_resources(self):
        output = render_html(report(change()))
        doc = Document(output)
        self.assertTrue(output.startswith("<!doctype html>"))
        self.assertIn('<html lang="en">', output)
        self.assertIn('name="viewport"', output)
        self.assertEqual(len(doc.scripts), 1)
        for tag, attrs in doc.tags:
            self.assertNotIn(tag, {"iframe", "link", "img", "object"})
            self.assertNotIn("src", attrs)
        self.assertNotRegex(output, r"https?://|@import|url\(")
        self.assertIn("<noscript>", output)
        self.assertIn("@media print", output)

    def test_script_and_markup_payloads_are_text_in_every_displayed_field(self):
        payload = '</script><script>alert("xss")</script><img src=x onerror=alert(1)>&\'"'
        output = render_html(report(change(tool=payload, code=payload, path=payload,
                                           message=payload, before={payload: payload}, after=payload)))
        doc = Document(output)
        self.assertEqual(len(doc.scripts), 1)
        self.assertNotIn("alert", doc.scripts[0])
        self.assertNotIn("innerHTML", doc.scripts[0])
        self.assertFalse(any(tag == "img" for tag, _ in doc.tags))
        self.assertFalse(any(key.startswith("on") for _, attrs in doc.tags for key in attrs))
        self.assertIn("&lt;/script&gt;", output)
        self.assertIn(payload, "".join(doc.content))
        self.assertEqual(json.loads(doc.code_values[0]), {payload: payload})
        self.assertEqual(json.loads(doc.code_values[1]), payload)

    def test_control_characters_are_visible_escapes_not_raw_dom_controls(self):
        payload = "left\x00\x1b\x7f\x85\u202e\U000e0001right"
        output = render_html(report(change(tool=payload, message=payload, before=payload)))
        for char in ("\x00", "\x1b", "\x7f", "\x85", "\u202e", "\U000e0001"):
            self.assertNotIn(char, output)
        for escape in ("\\u0000", "\\u001b", "\\u007f", "\\u0085", "\\u202e", "\\udb40\\udc01"):
            self.assertIn(escape, output)
        self.assertEqual(json.loads(Document(output).code_values[0]), payload)

    def test_empty_report_is_readable_without_javascript(self):
        output = render_html(report())
        self.assertIn("No contract changes detected", output)
        self.assertIn("No changes found", output)
        self.assertIn("0 changes across 0 tools", output)
        self.assertEqual(len(re.findall(r'class="change-card ', output)), 0)
        self.assertIn('id="toolbar" hidden', output)
        for level in ("breaking", "review", "info"):
            self.assertIn(f'data-count="{level}">0</span>', output)

    def test_counts_and_original_json_values_are_preserved(self):
        value = {"enabled": True, "count": 1, "zero": 0, "empty": "", "nothing": None,
                 "nested": [False, 1.5, {"中文": "保留"}]}
        output = render_html(report(change(before=value, after=None),
                                    change(severity="review", tool="write"),
                                    change(severity="info", tool="write")))
        doc = Document(output)
        self.assertEqual(json.loads(doc.code_values[0]), value)
        self.assertIsNone(json.loads(doc.code_values[1]))
        self.assertIn("3 changes across 2 tools", output)
        for level in ("breaking", "review", "info"):
            self.assertIn(f'data-count="{level}">1</span>', output)

    def test_missing_and_null_values_are_distinct(self):
        item = change(after=None)
        del item["before"]
        output = render_html(report(item))
        self.assertIn("Not present in this snapshot", output)
        self.assertEqual(Document(output).code_values, ["null"])

    def test_non_numeric_counts_cannot_inject_markup(self):
        data = report(change())
        data["summary"] = {"breaking": '<img src=x onerror="evil()">', "review": True, "info": -2}
        output = render_html(data)
        self.assertIn('data-count="breaking">1</span>', output)
        self.assertIn('data-count="review">0</span>', output)
        self.assertIn('data-count="info">0</span>', output)
        self.assertFalse(any(tag == "img" for tag, _ in Document(output).tags))

    def test_metadata_is_plain_text_and_unknown_severity_cannot_inject_attributes(self):
        output = render_html(report(change(severity='bad" onclick="evil()',
                                           message="**bold** [click](javascript:evil()) <b>plain</b>")))
        doc = Document(output)
        self.assertFalse(any(tag in {"b", "a"} for tag, _ in doc.tags))
        self.assertIn("**bold** [click](javascript:evil()) &lt;b&gt;plain&lt;/b&gt;", output)
        cards = [attrs for tag, attrs in doc.tags if tag == "article"]
        self.assertEqual(cards[0]["data-severity"], "review")
        self.assertNotIn("onclick", cards[0])

    def test_filters_search_and_folded_values_use_static_enhancement(self):
        output = render_html(report(change()))
        self.assertIn('aria-label="Filter by severity"', output)
        self.assertIn('type="search"', output)
        self.assertIn('aria-live="polite"', output)
        self.assertIn("<details", output)
        self.assertNotIn('<details open', output)
        self.assertIn("card.hidden = !matches", output)
        self.assertIn("count.textContent", output)


if __name__ == "__main__":
    unittest.main()
