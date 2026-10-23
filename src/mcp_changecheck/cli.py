"""Command-line interface. Reading snapshots never contacts an MCP server."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import sys

from . import __version__
from .core import SnapshotError, compare_snapshots


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise SnapshotError(f"Non-standard JSON value: {value}")


def load_snapshot(path: Path):
    """Load strict UTF-8 JSON; accept Windows' optional UTF-8 BOM."""
    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=_object,
        parse_constant=_invalid_constant,
    )


def _single_line(value):
    return re.sub(r"[\x00-\x1f\x7f]", lambda m: repr(m.group())[1:-1], str(value))


def _markdown(value):
    escaped = html.escape(_single_line(value), quote=False)
    return re.sub(r"([\\`*_|\[\]{}()#!])", r"\\\1", escaped)


def render_report(report: dict, output_format: str = "text") -> str:
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    summary = report["summary"]
    counts = ", ".join(f"{summary[key]} {key}" for key in ("breaking", "review", "info"))
    if output_format == "markdown":
        lines = ["# MCP tool change report", "", counts, ""]
        if report["changes"]:
            lines += ["| Level | Tool | Path | Change |", "| --- | --- | --- | --- |"]
            for change in report["changes"]:
                lines.append("| " + " | ".join(_markdown(change[key]) for key in (
                    "severity", "tool", "path", "message"
                )) + " |")
        else:
            lines.append("No changes detected by these static rules.")
        lines += ["", "Static rules only; review findings are not compatibility or security guarantees."]
        return "\n".join(lines) + "\n"
    lines = [f"MCP tool change report: {counts}"]
    for change in report["changes"]:
        lines.append(_single_line(
            f"[{change['severity'].upper()}] {change['tool']} {change['path']}: {change['message']}"
        ))
    if not report["changes"]:
        lines.append("No changes detected by these static rules.")
    return "\n".join(lines) + "\n"


def _fails(report, threshold):
    levels = {
        "breaking": ("breaking",),
        "review": ("breaking", "review"),
        "any": ("breaking", "review", "info"),
        "never": (),
    }
    return any(report["summary"][level] for level in levels[threshold])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare complete MCP tools/list snapshots offline. No server calls or API keys."
    )
    parser.add_argument("before", type=Path, help="baseline JSON snapshot")
    parser.add_argument("after", type=Path, help="candidate JSON snapshot")
    parser.add_argument("--version", action="version", version=f"mcp-changecheck {__version__}")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--output", type=Path, help="write report to this file instead of stdout")
    parser.add_argument(
        "--fail-on", choices=("breaking", "review", "any", "never"), default="review",
        help="exit 1 on this threshold (review includes breaking; default: review)",
    )
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.resolve() in (args.before.resolve(), args.after.resolve()):
            raise SnapshotError("Report output must not overwrite either input snapshot")
        report = compare_snapshots(load_snapshot(args.before), load_snapshot(args.after))
        rendered = render_report(report, args.format)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 1 if _fails(report, args.fail_on) else 0
    except (SnapshotError, OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"mcp-changecheck: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
