"""Conservative, offline comparisons of MCP tools/list snapshots.

This module validates the shapes it inspects; it is not a JSON Schema validator.
Changes to keywords whose compatibility cannot be established need review.
"""

from __future__ import annotations

from decimal import Decimal
import math
from typing import Any


class SnapshotError(ValueError):
    """A snapshot is malformed or does not contain a complete tools listing."""


_MISSING = object()
_TYPES = {"null", "boolean", "object", "array", "number", "integer", "string"}
_DEFAULTS = {"readOnlyHint": False, "destructiveHint": True,
             "idempotentHint": False, "openWorldHint": True}
_MAP_SCHEMAS = {"properties", "patternProperties", "$defs", "definitions",
                "dependentSchemas"}
_SINGLE_SCHEMAS = {"additionalProperties", "unevaluatedProperties", "items",
                   "additionalItems", "unevaluatedItems", "contains", "not",
                   "if", "then", "else", "propertyNames", "contentSchema"}
_LIST_SCHEMAS = {"allOf", "anyOf", "oneOf", "prefixItems"}


def _pointer(path: str, key: str) -> str:
    return path + "/" + key.replace("~", "~0").replace("/", "~1")


def _json(value: Any, path: str = "") -> None:
    if value is None or type(value) in (bool, str, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json(item, _pointer(path, str(index)))
        return
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for key, item in value.items():
            _json(item, _pointer(path, key))
        return
    raise SnapshotError(f"{path or '/'}: expected a finite JSON value")


def _freeze(value: Any) -> Any:
    """JSON equality: booleans differ from numbers; object order is irrelevant."""
    if value is _MISSING:
        return ("missing",)
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("boolean", value)
    if isinstance(value, (int, float)):
        return ("number", Decimal(str(value)))
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, list):
        return ("array", tuple(_freeze(v) for v in value))
    return ("object", tuple((k, _freeze(v)) for k, v in sorted(value.items())))


def _schema_key(schema: Any) -> Any:
    if type(schema) is bool:
        return _freeze(schema)
    result = {}
    for key, value in schema.items():
        if key in {"required", "enum"} or (key == "type" and isinstance(value, list)):
            result[key] = ("set", frozenset(_freeze(v) for v in value))
        elif key in _MAP_SCHEMAS:
            result[key] = tuple((k, _schema_key(v)) for k, v in sorted(value.items()))
        elif key in _SINGLE_SCHEMAS:
            result[key] = _schema_key(value)
        elif key in _LIST_SCHEMAS:
            result[key] = tuple(_schema_key(v) for v in value)
        else:
            result[key] = _freeze(value)
    return tuple(sorted(result.items()))


def _has_reference(schema: Any) -> bool:
    """Look only in schema locations, never in enum/default/example data."""
    if type(schema) is bool:
        return False
    if "$ref" in schema or "$dynamicRef" in schema:
        return True
    for key in _MAP_SCHEMAS & schema.keys():
        if any(_has_reference(child) for child in schema[key].values()):
            return True
    for key in _SINGLE_SCHEMAS & schema.keys():
        if _has_reference(schema[key]):
            return True
    for key in _LIST_SCHEMAS & schema.keys():
        if any(_has_reference(child) for child in schema[key]):
            return True
    return False


def _validate_schema(schema: Any, path: str) -> None:
    if type(schema) is bool:
        return
    if not isinstance(schema, dict):
        raise SnapshotError(f"{path}: expected an object or boolean schema")
    if "type" in schema:
        types = schema["type"]
        values = types if isinstance(types, list) else [types]
        if (not values or any(not isinstance(v, str) or v not in _TYPES for v in values)
                or len(set(values)) != len(values)):
            raise SnapshotError(f"{path}/type: expected a valid type or unique nonempty type list")
    if "required" in schema:
        required = schema["required"]
        if (not isinstance(required, list) or any(not isinstance(v, str) for v in required)
                or len(set(required)) != len(required)):
            raise SnapshotError(f"{path}/required: expected a list of unique strings")
    if "enum" in schema:
        values = schema["enum"]
        if not isinstance(values, list):
            raise SnapshotError(f"{path}/enum: expected a list of JSON values")
    for key in _MAP_SCHEMAS & schema.keys():
        value = schema[key]
        if not isinstance(value, dict):
            raise SnapshotError(f"{path}/{key}: expected an object of schemas")
        for name, child in value.items():
            _validate_schema(child, _pointer(_pointer(path, key), name))
    for key in _SINGLE_SCHEMAS & schema.keys():
        _validate_schema(schema[key], _pointer(path, key))
    for key in _LIST_SCHEMAS & schema.keys():
        value = schema[key]
        if not isinstance(value, list):
            raise SnapshotError(f"{path}/{key}: expected a list of schemas")
        for index, child in enumerate(value):
            _validate_schema(child, _pointer(_pointer(path, key), str(index)))


def normalize_snapshot(data: Any) -> dict[str, dict[str, Any]]:
    """Validate a tools array, tools envelope, or JSON-RPC result envelope."""
    _json(data)
    if isinstance(data, list):
        tools = data
    elif isinstance(data, dict):
        result = data.get("result")
        for envelope in (data, result):
            if isinstance(envelope, dict) and envelope.get("nextCursor") is not None:
                raise SnapshotError("nextCursor indicates an incomplete snapshot; collect every page first")
            if isinstance(envelope, dict) and "resultType" in envelope and envelope["resultType"] != "complete":
                raise SnapshotError("resultType must be 'complete'; unfinished results are not complete snapshots")
        if "tools" in data:
            tools = data["tools"]
        elif isinstance(result, dict) and "tools" in result:
            tools = result["tools"]
        else:
            raise SnapshotError("expected a tools array, {tools: [...]}, or {result: {tools: [...]}}")
    else:
        raise SnapshotError("expected a tools array or tools envelope")
    if not isinstance(tools, list):
        raise SnapshotError("tools: expected an array")
    normalized = {}
    for index, tool in enumerate(tools):
        path = f"/tools/{index}"
        if not isinstance(tool, dict):
            raise SnapshotError(f"{path}: expected a tool object")
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            raise SnapshotError(f"{path}/name: expected a nonempty string")
        if name in normalized:
            raise SnapshotError(f"{path}/name: duplicate tool name {name!r}")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise SnapshotError(f"{path}/inputSchema: expected an object schema with type 'object'")
        _validate_schema(schema, path + "/inputSchema")
        if "outputSchema" in tool:
            output = tool["outputSchema"]
            _validate_schema(output, path + "/outputSchema")
        if "annotations" in tool:
            annotations = tool["annotations"]
            if not isinstance(annotations, dict):
                raise SnapshotError(f"{path}/annotations: expected an object")
            for key in _DEFAULTS.keys() & annotations.keys():
                if type(annotations[key]) is not bool:
                    raise SnapshotError(f"{path}/annotations/{key}: expected a boolean")
        normalized[name] = tool
    return normalized


def _type_set(value: Any) -> set[str]:
    types = _TYPES if value is _MISSING else ({value} if isinstance(value, str) else set(value))
    return set(types) | ({"integer"} if "number" in types else set())


def compare_snapshots(before: Any, after: Any) -> dict[str, Any]:
    """Compare input acceptance conservatively; output and behavioral changes need review."""
    old_tools, new_tools = normalize_snapshot(before), normalize_snapshot(after)
    changes = []

    def add(severity: str, code: str, tool: str, path: str, message: str,
            old: Any = _MISSING, new: Any = _MISSING) -> None:
        change = dict(severity=severity, code=code, tool=tool, path=path, message=message)
        if old is not _MISSING:
            change["before"] = old
        if new is not _MISSING:
            change["after"] = new
        changes.append(change)

    def schema_diff(old: Any, new: Any, name: str, path: str) -> None:
        if _schema_key(old) == _schema_key(new):
            return
        if type(old) is bool or type(new) is bool:
            add("review", "schema_changed", name, path,
                "Boolean schema change requires compatibility review.", old, new)
            return
        old_required, new_required = set(old.get("required", [])), set(new.get("required", []))
        for value in sorted(new_required - old_required):
            add("breaking", "required_added", name, path + "/required",
                f"Input property {value!r} is now required.", new=value)
        for value in sorted(old_required - new_required):
            add("info", "required_removed", name, path + "/required",
                f"Input property {value!r} is no longer required.", old=value)
        old_props, new_props = old.get("properties", {}), new.get("properties", {})
        for key in sorted(old_props.keys() | new_props.keys()):
            prop_path = _pointer(path + "/properties", key)
            if key not in old_props:
                previously_allowed = old.get("additionalProperties", True) is not False or bool(old.get("patternProperties"))
                constrained = (key not in new_required and previously_allowed
                               and new_props[key] is not True and new_props[key] != {})
                severity = "review" if constrained else "info"
                message = ("New optional property may constrain values previously accepted by additional or pattern properties."
                           if constrained else "Input property added; requiredness is reported separately.")
                add(severity, "property_added", name, prop_path, message, new=new_props[key])
            elif key not in new_props:
                forbidden = new.get("additionalProperties", True) is False
                add("breaking" if forbidden else "review", "property_removed", name, prop_path,
                    "Input property removed and additional properties are forbidden." if forbidden else
                    "Input property removed; acceptance now depends on additional-property rules.", old=old_props[key])
            else:
                schema_diff(old_props[key], new_props[key], name, prop_path)
        old_type, new_type = old.get("type", _MISSING), new.get("type", _MISSING)
        old_set, new_set = _type_set(old_type), _type_set(new_type)
        if old_set != new_set:
            severity, code = ("breaking", "type_narrowed") if new_set < old_set else (
                ("info", "type_widened") if old_set < new_set else ("breaking", "type_changed"))
            add(severity, code, name, path + "/type",
                "Accepted input types changed (integer is a subset of number).", old_type, new_type)
        old_enum, new_enum = old.get("enum", _MISSING), new.get("enum", _MISSING)
        if old_enum is _MISSING and new_enum is not _MISSING:
            add("breaking", "enum_added", name, path + "/enum", "Input is now restricted to enumerated values.", new=new_enum)
        elif new_enum is _MISSING and old_enum is not _MISSING:
            add("info", "enum_removed", name, path + "/enum", "Input enumeration restriction removed.", old=old_enum)
        elif old_enum is not _MISSING and new_enum is not _MISSING:
            old_values, new_values = {_freeze(v) for v in old_enum}, {_freeze(v) for v in new_enum}
            if old_values != new_values:
                removed = bool(old_values - new_values)
                code = "enum_narrowed" if new_values < old_values else (
                    "enum_widened" if old_values < new_values else "enum_changed")
                add("breaking" if removed else "info", code, name, path + "/enum",
                    "Previously enumerated input values removed." if removed else "Additional enumerated input values accepted.",
                    old_enum, new_enum)
        for key in sorted((old.keys() | new.keys()) - {"required", "properties", "type", "enum"}):
            left, right = old.get(key, _MISSING), new.get(key, _MISSING)
            if left is not _MISSING and right is not _MISSING:
                if key in _MAP_SCHEMAS:
                    equal = _schema_key({key: left}) == _schema_key({key: right})
                elif key in _SINGLE_SCHEMAS | _LIST_SCHEMAS:
                    equal = _schema_key({key: left}) == _schema_key({key: right})
                else:
                    equal = _freeze(left) == _freeze(right)
            else:
                equal = left is right
            if not equal:
                add("review", "schema_keyword_changed", name, _pointer(path, key),
                    "Schema keyword changed; constraints or agent behavior may change.", left, right)

    for name in sorted(old_tools.keys() | new_tools.keys()):
        if name not in old_tools:
            add("info", "tool_added", name, "", "Tool added.", new=new_tools[name])
            continue
        if name not in new_tools:
            add("breaking", "tool_removed", name, "", "Tool removed.", old=old_tools[name])
            continue
        old, new = old_tools[name], new_tools[name]
        input_changes_start = len(changes)
        schema_diff(old["inputSchema"], new["inputSchema"], name, "/inputSchema")
        if (len(changes) > input_changes_start
                and (_has_reference(old["inputSchema"]) or _has_reference(new["inputSchema"]))):
            add("review", "referenced_input_changed", name, "/inputSchema",
                "Input schema changed and contains references; compatibility requires review without resolving references.")
        left, right = old.get("outputSchema", _MISSING), new.get("outputSchema", _MISSING)
        if ((left is _MISSING or right is _MISSING) and left is not right
                or left is not _MISSING and right is not _MISSING and _schema_key(left) != _schema_key(right)):
            add("review", "output_schema_changed", name, "/outputSchema",
                "Output contract changed; compatibility direction differs from input acceptance.", left, right)
        old_ann, new_ann = old.get("annotations", {}), new.get("annotations", {})
        for key in sorted(old_ann.keys() | new_ann.keys() | _DEFAULTS.keys()):
            left, right = old_ann.get(key, _DEFAULTS.get(key, _MISSING)), new_ann.get(key, _DEFAULTS.get(key, _MISSING))
            if _freeze(left) != _freeze(right):
                add("review", "annotation_changed", name, _pointer("/annotations", key),
                    "Effective annotation changed; tool behavior expectations may change.", left, right)
        for key in sorted((old.keys() | new.keys()) - {"name", "inputSchema", "outputSchema", "annotations"}):
            left, right = old.get(key, _MISSING), new.get(key, _MISSING)
            if _freeze(left) != _freeze(right):
                add("review", "tool_metadata_changed", name, _pointer("", key),
                    "Tool metadata changed; agent behavior may change.", left, right)
    changes.sort(key=lambda c: (c["tool"], c["path"], c["code"], c["severity"]))
    summary = {severity: sum(c["severity"] == severity for c in changes)
               for severity in ("breaking", "review", "info")}
    return {"schema_version": 1, "summary": summary, "changes": changes}
