"""Run the installed checker using argument arrays and GitHub environment files."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


def _output(stream, name: str, value: str) -> None:
    delimiter = "mcp_" + uuid4().hex
    while delimiter in value.splitlines():
        delimiter = "mcp_" + uuid4().hex
    stream.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def _diagnostic(message: str) -> None:
    # Keep diagnostic text from becoming runner commands or forged log lines.
    escaped = json.dumps(message, ensure_ascii=True).replace("::", r"\u003a\u003a")
    print("mcp-changecheck action: " + escaped, file=sys.stderr)


def main() -> int:
    status = 2
    report_output = ""
    try:
        workspace_value = os.environ.get("GITHUB_WORKSPACE")
        if not workspace_value:
            raise ValueError("GITHUB_WORKSPACE is required")
        workspace = Path(workspace_value).resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError("GITHUB_WORKSPACE must be a directory")
        before_value = os.environ.get("MCP_BEFORE", "")
        after_value = os.environ.get("MCP_AFTER", "")
        if not before_value or not after_value:
            raise ValueError("Both before and after snapshot paths are required")
        threshold = os.environ.get("MCP_FAIL_ON", "review")
        if threshold not in {"review", "breaking", "any", "never"}:
            raise ValueError("fail-on must be review, breaking, any, or never")
        summary = os.environ.get("MCP_SUMMARY", "true").lower()
        if summary not in {"true", "false"}:
            raise ValueError("summary must be true or false")
        before = (workspace / before_value).resolve()
        after = (workspace / after_value).resolve()
        report = (workspace / os.environ.get("MCP_REPORT_PATH", "mcp-changecheck-report.md")).resolve()
        if not report.is_relative_to(workspace):
            raise ValueError("report-path must stay inside GITHUB_WORKSPACE")
        # Inputs are values, never shell source. Absolute paths also prevent a
        # file named with a leading '-' from being interpreted as a CLI option.
        result = subprocess.run([
            sys.executable, "-m", "mcp_changecheck", str(before), str(after),
            "--format", "markdown", "--output", str(report), "--fail-on", threshold,
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=workspace,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        status = result.returncode if result.returncode in {0, 1, 2} else 2
        if result.stderr:
            _diagnostic(result.stderr)
        if status in {0, 1}:
            if not report.is_file():
                raise ValueError("Checker did not generate a report")
            if summary == "true":
                summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
                if not summary_path:
                    raise ValueError("GITHUB_STEP_SUMMARY is required when summary is true")
                with Path(summary_path).open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(report.read_text(encoding="utf-8") + "\n")
            report_output = str(report)
    except (OSError, ValueError, RuntimeError) as error:
        _diagnostic(str(error))
        status = 2
        report_output = ""
    try:
        output_path = os.environ.get("GITHUB_OUTPUT")
        if not output_path:
            raise ValueError("GITHUB_OUTPUT is required")
        with Path(output_path).open("a", encoding="utf-8", newline="\n") as stream:
            _output(stream, "exit-code", str(status))
            _output(stream, "report-path", report_output)
    except (OSError, ValueError) as error:
        _diagnostic(str(error))
        return 2
    print(f"mcp-changecheck finished with exit code {status}.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
