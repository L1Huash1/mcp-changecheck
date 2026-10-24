# mcp-changecheck

**Catch MCP tool contract changes before they surprise your agent.**

[中文说明](README.zh-CN.md) · [Rules and limitations](docs/rules.md) · [Contributing](CONTRIBUTING.md)

[![Tests](https://github.com/L1Huash1/mcp-changecheck/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/L1Huash1/mcp-changecheck/actions/workflows/ci.yml)

`mcp-changecheck` compares two complete MCP `tools/list` snapshots locally. It reports removed tools, newly required arguments, narrowed input types or enums, and changes that deserve review, including tool descriptions and annotation hints.

No model calls. No server execution. No API key. **Zero runtime dependencies; Python 3.10+.**

This is an early, rule-based static checker. It does not prove JSON Schema compatibility or inspect server behavior.

## Try it in a minute

```sh
git clone https://github.com/L1Huash1/mcp-changecheck.git
cd mcp-changecheck
python -m pip install .
mcp-changecheck examples/before.json examples/after.json
```

The synthetic example removes `archive_note`, makes `workspace` required, and changes a read-only annotation. The command intentionally exits **1** because findings exceed the default threshold.

```text
[BREAKING] archive_note ... Tool removed ...
[BREAKING] search_notes ... Required ... workspace ...
[REVIEW] search_notes ... readOnlyHint ...
```

The excerpt above illustrates the findings; exact wording is in [the generated example report](examples/report.md).

```sh
# Machine-readable report
mcp-changecheck examples/before.json examples/after.json --format json --fail-on never

# Review report for a pull request
mcp-changecheck examples/before.json examples/after.json --format markdown --output report.md

# Interactive offline report: open report.html in your browser
mcp-changecheck examples/before.json examples/after.json --format html --output report.html

# Unchanged snapshots pass
mcp-changecheck examples/before.json examples/before.json
```

`--fail-on never` still returns 2 for invalid input. Writing a report does not suppress the threshold exit code.

`--output` rejects a path that refers to either input snapshot, including hard links and symbolic links, with exit code 2 to preserve the input files.

## What is checked?

| Level | Examples | Default result |
| --- | --- | --- |
| `breaking` | Tool removed; required input added; input type or enum narrowed | Fail |
| `review` | Description/hint/output schema changed; unsupported schema changes | Fail |
| `info` | Tool added; input requirement relaxed | Pass |

The levels are conservative change signals, not a formal compatibility verdict. Some combinations of constraints can mask the effect of another change. See [exact rules](docs/rules.md).

Annotations are server-provided **hints**. Comparing them does not verify permissions, detect malicious tools, or establish that a server is safe.

## Snapshot format

Accepts any of these complete JSON documents:

```json
{"tools":[{"name":"lookup","inputSchema":{"type":"object"}}]}
```

```json
{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"lookup","inputSchema":{"type":"object"}}]}}
```

The bare `tools` array is also accepted. Obtain snapshots with your own MCP client or [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector); this utility does not connect to servers. If listing is paginated, collect **all** pages into one `tools` array and remove pagination cursors only after collection. A non-null `nextCursor` is rejected to prevent false removal reports.

Tool order, property order, and `required`/`type`/`enum` array order do not matter. Duplicate tool names, duplicate JSON keys, invalid JSON values, and malformed recognized schema fields are rejected. This is structural validation, not a full JSON Schema validator.

## CI

Use the bundled GitHub Action to compare snapshots and read the report in the job summary:

```yaml
- uses: actions/checkout@v7.0.1
- uses: L1Huash1/mcp-changecheck@v0.3.0
  with:
    before: snapshots/baseline.json
    after: snapshots/candidate.json
```

The snapshot paths are supplied by your project. See [the complete workflow, inputs and outputs](docs/github-action.md). No write permission or API key is required.

You can also install and invoke the CLI directly:

```yaml
name: MCP contract check
on: [push, pull_request]
permissions:
  contents: read
jobs:
  contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7.0.1
      - uses: actions/setup-python@v7.1.0
        with:
          python-version: '3.12'
      - run: python -m pip install .
      - run: mcp-changecheck snapshots/baseline.json snapshots/candidate.json
```

Supply your own baseline and candidate snapshots at the paths in the example. The repository's own [CI workflow](.github/workflows/ci.yml) runs regression tests and the bundled examples on Linux and Windows.

| Option | Meaning |
| --- | --- |
| `--format text\|json\|markdown\|html` | Report format, default `text` |
| `--output PATH` | Save report instead of printing it |
| `--fail-on breaking` | Fail only on `breaking` findings |
| `--fail-on review` | Fail on `breaking` or `review`, the default |
| `--fail-on any` | Fail on any finding, including `info` |
| `--fail-on never` | Report findings without failing the threshold |

Exit codes: **0** below threshold; **1** findings exceed threshold; **2** invalid input, arguments, or file errors.

## Python API

```python
import json
from mcp_changecheck import compare_snapshots

with open("examples/before.json", encoding="utf-8") as f:
    before = json.load(f)
with open("examples/after.json", encoding="utf-8") as f:
    after = json.load(f)
report = compare_snapshots(before, after)
print(report["summary"])
```

Reports have `schema_version: 1`, a count per severity, and a stable `changes` array. Each change includes its severity, code, tool name, JSON Pointer path, and explanation. Present old/new values are included as `before`/`after`; an absent value is omitted rather than represented as JSON null.

## Scope and related work

This project focuses on small, offline tool snapshots and explainable CI output. [mcp-server-diff](https://github.com/SamMorrowDrums/mcp-server-diff) is related work with broader MCP interface diffing. [MCP Inspector](https://github.com/modelcontextprotocol/inspector) provides interactive inspection and protocol testing. Use those when their scope fits your needs.

Companion project: [agent-tracecheck](https://github.com/L1Huash1/agent-tracecheck) diagnoses repeated tool calls, missing results, and observed budgets from a recorded run. Use this project before tool upgrades and the companion after a run.

HTML reports are self-contained files with severity filters, text search, and expandable old/new values. They also work as readable reports with JavaScript disabled; no data is uploaded. See the [walkthrough](docs/walkthrough.md).

No native framework adapters, live MCP transport, runtime enforcement, model evaluation, or full schema inclusion proof are implemented. See the [roadmap](docs/roadmap.md).

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Design references: [MCP tool specification, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), [JSON Schema type reference](https://json-schema.org/understanding-json-schema/reference/type). Snapshot envelopes with or without `resultType: "complete"` are accepted; intermediate results are rejected. Non-object output schemas are supported. The linked protocol version is a reference, not a claim of complete protocol conformance.

MIT licensed. Created with AI coding assistance; features and examples should be evaluated against the documented tests and limitations.
