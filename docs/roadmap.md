# Roadmap

This is a candidate backlog, not a commitment to release dates.

## Next: validate the core

- Collect real-world **public or synthetic** snapshot pairs and document false positives.
- Add explicit rule examples for conditional schemas and references.
- Stabilize report schema version 1 before adding output fields.

## Delivered in 0.2

- Self-contained HTML reports with filters, search, inspectable values and print styling.
- An offline walkthrough and conservative reference-change handling.

## Then: improve adoption

- Document baseline capture with MCP Inspector, including full pagination.
- Add a baseline update guide and a compact pull-request report example.
- Collect usability feedback on the local HTML report.

## Later: opt-in adapters

- Read additional trace/snapshot formats without executing servers.
- Explore output-schema compatibility rules with independent test fixtures.

Every proposed feature should retain offline operation and an explanation for each finding. Transport clients, autonomous repository edits, and claims of security certification are outside the initial scope.
