# Changelog

## 0.3.0 — 2026-10-25

- Add a composite GitHub Action that installs the checker from the selected action revision, compares local snapshots and writes a Markdown job summary.
- Preserve CLI exit thresholds, expose comparison status/report outputs, and avoid presenting stale reports after invalid input.
- Add Windows/Linux action smoke checks and regressions for linked outputs, path boundaries, literal path values and runner diagnostics.

## 0.2.1 — 2026-10-25

- Reject report outputs that alias either input snapshot through a hard link, as well as the same path or a symbolic link, preserving the input files and returning exit code 2.
- Add regression coverage for linked outputs, new report directories, and invalid output paths.

## 0.2.0 — 2026-10-23

- Add a self-contained HTML report with severity filters, search, expandable values, and print styling.
- Accept empty and repeated enum entries with set semantics.
- Add a review fallback for changed input schemas containing references.
- Reject decimal inputs that would silently lose precision; compare supported int/float values consistently.
- Add a short usage walkthrough and regression coverage for the new behavior.

## 0.1.0 — 2026-10-23

Initial alpha implementation:

- Offline comparison of complete MCP tool-list snapshots.
- Input requirements, types, enums, metadata, and annotation change checks.
- Text, JSON, and Markdown reports with configurable CI thresholds.
- Synthetic examples, English and Chinese documentation, and regression tests.

No live server transport, runtime security enforcement, or full JSON Schema compatibility proof.
