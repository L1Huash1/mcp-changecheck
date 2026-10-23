# Rules and limitations

`breaking`, `review`, and `info` describe static **change signals**. They are not a proof that an accepted-input set has changed, because other unchanged constraints may mask a changed keyword. For example, an unchanged enum may already exclude a type that is removed later.

The default CLI threshold fails on both `breaking` and `review`. Selecting `--fail-on breaking` deliberately allows findings that this version cannot classify.

## Input schemas

Only corresponding `properties` recurse into the rules below. An input schema's root must be an object with `type: "object"`. Nested boolean schemas are accepted but changes to them need review.

| Change | Signal |
| --- | --- |
| Tool removed | breaking |
| Tool added | info |
| Input `required` name added | breaking |
| Input `required` name removed | info |
| Input type set narrowed | breaking |
| Input type set widened | info |
| Type set both adds and removes types | breaking |
| Enum restriction introduced | breaking |
| Previously enumerated value removed | breaking |
| Enum values only added, or restriction removed | info |
| Property removed with new `additionalProperties: false` | breaking |
| Other property removal | review |
| Optional constrained property added where extra names or patterns were allowed | review |
| Other property addition | info; requiredness reported separately |
| Other changed schema keywords, including schema descriptions/titles | review |

`number` includes `integer`. JSON booleans and numbers are distinct enum values, while `1` and `1.0` represent the same numeric value. Ordering in `required`, `type`, and `enum` is ignored. Object key order and tool list order are ignored.

References, combinators, patterns, numeric/string limits, `items`, `$defs`, and additional-property schemas are not interpreted for compatibility. Changes are reported atomically as review findings. Unchanged references are not resolved, and unchanged complex constraints do not alter the simple rules above. Unknown changed keywords are review findings.

This checker follows modern object/boolean subschema shapes. It does not implement older dialect-specific shapes such as draft-07 tuple `items` arrays. It validates the structural fields it inspects, not every rule of a JSON Schema dialect.

## Output schemas

Adding, removing, or substantively changing an output schema needs review. Object, array, primitive, combination, and boolean output schemas are supported structurally; output schemas are not restricted to `type: "object"`. Input and output compatibility have different directions; this version does not apply input narrowing rules to outputs. Semantically unordered lists are normalized before comparison.

## Metadata and annotations

Tool descriptions, titles, unknown metadata, and effective annotation changes need review because they may change an agent's choices. This is a text/structure comparison, not prompt-injection detection.

The four hints use MCP defaults when omitted:

| Hint | Default |
| --- | --- |
| `readOnlyHint` | false |
| `destructiveHint` | true |
| `idempotentHint` | false |
| `openWorldHint` | true |

An explicit default and an omitted hint compare equally. Every effective hint change is reported, even when another hint could make it irrelevant (for example, destructive/idempotent hints on a read-only tool). This is intentionally conservative. An annotation is an unverified server declaration, not an access-control guarantee.

## Snapshot completeness and reports

The inputs must represent the same intended server scope. A complete empty list is valid and compared as-is. Any non-null `nextCursor` at the outer or result envelope is rejected, including an empty string cursor. If `resultType` is present it must be `complete`; intermediate responses are rejected. Pagination is never fetched automatically.

The JSON report has `schema_version: 1`, `summary`, and `changes`. Paths are JSON Pointers relative to the affected tool; an empty path identifies the whole tool. Changes are sorted by tool, path, code, and severity. Missing old/new values are omitted; JSON null is preserved as a value. Findings may include snapshot values, so treat generated reports with the same care as the input files.

Text output escapes control characters. Markdown output escapes tool-provided markup. The CLI rejects duplicate JSON keys and nonfinite JSON numbers. The Python API validates finite JSON values but cannot recover duplicate keys already discarded by a caller's JSON parser.

No finding means only that these static rules found no change. Server code, external state, authorization, prompts, actual outputs, and runtime side effects are outside this comparison.
