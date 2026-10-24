# Use the GitHub Action

Compare two complete MCP tool snapshots during a pull request and read the Markdown report in the workflow's job summary. The action does not start an MCP server or call a model. It does not post PR comments, edit baselines or commit files.

## Minimal workflow

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
      - uses: L1Huash1/mcp-changecheck@v0.3.0
        id: contract
        with:
          before: snapshots/baseline.json
          after: snapshots/candidate.json
```

Supply your own snapshots. Paths above are examples, not files provided by this repository. For a reproducible demonstration, this repository's own CI runs the action on its bundled unchanged and changed snapshots on Windows and Linux.

Use a specific release tag or a reviewed full commit SHA when adopting the action. This remains an early release; finding levels are conservative signals rather than a complete compatibility proof.

## Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `before` | required | Baseline snapshot path |
| `after` | required | Candidate snapshot path |
| `fail-on` | `review` | `review`, `breaking`, `any` or `never`, with the same meaning as the CLI |
| `report-path` | `mcp-changecheck-report.md` | Markdown output path within the workspace |
| `summary` | `true` | Append the generated report to the job summary; set `false` to keep only the local file |

Snapshot paths may be absolute or relative to `GITHUB_WORKSPACE`. Report paths must resolve within the workspace, including when symbolic links are involved. The CLI refuses report paths that alias either input, including hard links. An unrelated existing report may be replaced.

Input values are passed through environment variables and a Python argument array, not interpolated into shell commands. Spaces, Unicode and shell metacharacters in paths are treated as file-name characters. This does not make arbitrary untrusted code checkout safe; use normal GitHub workflow trust boundaries.

## Outputs and failures

| Output | Meaning |
| --- | --- |
| `exit-code` | `0` below the threshold, `1` for findings reaching the threshold, `2` for input/configuration/file errors |
| `report-path` | Absolute path of the generated report; empty when no valid report was generated |

Findings cause the action step to fail by default, while the report and summary are still generated. Use `fail-on: never` to inspect findings without failing the threshold. Invalid input still fails with exit code 2 and does not publish a stale report as the result of the current check.

The outputs are available after the comparison step runs. Installation or runner setup failures happen before that step and may leave outputs unset. Any artifact-upload or notification step belongs to the consuming workflow and should account for failure, for example with `if: always()` and a nonempty report path. The action does not upload artifacts automatically.

Generated reports may include tool names, schemas, descriptions and before/after values from the snapshots. Keep reports within the audience permitted to see those snapshots. Disable the summary if you only want the local report.

## Runner behavior

The composite action selects Python 3.13 using `actions/setup-python`, installs the checker from the **same action revision**, then compares files. Initial Python/package installation may access GitHub and PyPI; comparison itself makes no network requests. No API key or write permission is required. Windows and Ubuntu hosted runners are tested; other runner types are not claimed supported.

This selects Python and installs a package in the job environment. Use a separate job if another part of your workflow needs a different Python setup.

Design references: GitHub's [composite action guide](https://docs.github.com/en/actions/tutorials/create-actions/create-a-composite-action), [environment files and summaries](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands), and [script injection guidance](https://docs.github.com/en/actions/reference/security/secure-use).

中文：在自己的 GitHub 自动检查里添加这个 Action，指定升级前后的两个快照文件，就能在运行页面看到变更报告。默认遇到需要复核或破坏兼容的变化会失败；`fail-on: never` 可以只报告。它不会运行 MCP 服务、调用模型、修改基线或发布评论。
