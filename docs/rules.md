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

References, combinators, patterns, numeric/string limits, `items`, `$defs`, and additional-property schemas are not interpreted for compatibility. Changes are reported atomically as review findings. When input changes are detected and the old or new schema contains `$ref` or `$dynamicRef` at a recognized schema location, an additional review finding is emitted. A reference can reverse the effect of a local change through contexts such as `not`. References are never fetched or resolved. Unknown changed keywords are review findings.

`enum` must be an array; empty and duplicate entries are accepted and compared with set semantics. These are valid structural inputs even though nonempty unique entries are preferable for interoperable schemas.

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

Text output escapes control characters. Markdown and HTML output escape tool-provided markup. HTML is a self-contained file with a fixed filter/search script; snapshot content is never executed. The CLI rejects duplicate JSON keys, nonfinite numbers, and decimal tokens that cannot round-trip through its supported numeric representation. For example, `0.1` is supported; `0.100000000000000000001` is explicitly rejected rather than silently rounded. Arbitrary-precision numeric parsing is outside this version's scope. The Python API validates finite JSON values but cannot recover duplicate keys or precision already discarded by a caller's JSON parser.

No finding means only that these static rules found no change. Server code, external state, authorization, prompts, actual outputs, and runtime side effects are outside this comparison.
