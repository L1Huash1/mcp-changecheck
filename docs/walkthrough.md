# Walkthrough / 操作指南

The bundled snapshots are synthetic. You can run this walkthrough without a model, API key, or MCP server.

## 1. Generate a report

```sh
python -m pip install .
mcp-changecheck examples/before.json examples/after.json --format html --output report.html
```

The example intentionally returns exit code 1 because two breaking findings and one review finding are present. The HTML file is still written. Open it with any modern browser. For a demonstration that always returns 0 on valid inputs, append `--fail-on never`.

示例会故意返回退出码 1，但仍然生成 `report.html`。用浏览器打开即可；如果只想演示而不触发失败，可加 `--fail-on never`。

## 2. Read the findings

- **Breaking / 可能破坏旧调用**: `archive_note` disappeared; `workspace` became required for `search_notes`.
- **Review / 需要人工检查**: the `readOnlyHint` declaration changed. This may affect how an agent presents or selects the tool; it does not verify real permissions.
- **Info / 信息提示**: the new `workspace` property appears in the schema. Its requiredness is a separate finding, so findings count changes rather than unique tools.

Use the severity buttons to focus on one level. Search matches tool names, paths, explanations and recorded values. Expand **Inspect values** to compare the old and new JSON. Filtering does not alter the underlying report or the CLI result.

点击等级按钮筛选，搜索框可检索工具名、路径、说明及快照值。展开 **Inspect values** 查看前后数据。过滤只是改变显示，不会修改报告或命令行退出码。

## 3. Replace the examples with your snapshots

Save a complete `tools/list` response before and after a deliberate server update. Use the same server scope, identity and authorization context. If the response is paginated, collect all pages first and combine their `tools` arrays. The checker rejects remaining non-null `nextCursor` markers.

快照应该来自同一服务和相同授权范围。先完整收集分页，再比较；不要为绕过检查而直接删除分页标记。

## 4. Choose a baseline policy

Store the accepted baseline alongside the agent code or in your own private fixtures. Generate a candidate snapshot in your trusted test environment. Run the comparison in CI, inspect breaking and review findings, update the agent if necessary, and update the baseline in the same reviewed change. Avoid automatically accepting every new baseline.

The repository's [CI example](../README.md#ci) compares files already present in the checkout. This project does not start servers or obtain snapshots on your behalf.

## 5. Share carefully

HTML embeds the same recorded values as the JSON report. It does not upload them, but the file itself can contain private business details from your tools. Use synthetic data for public bug reports and examples.

HTML 文件会包含快照中的原始值。程序不会上传它们，但你分享文件时会一起分享这些内容；公开反馈请使用人工构造的数据。
