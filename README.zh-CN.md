# mcp-changecheck

**在 MCP 工具升级前，找出可能影响 Agent 的接口变化。**

[English](README.md) · [规则与限制](docs/rules.md) · [开发计划](docs/roadmap.md)

MCP 服务更新后，工具可能被删除、参数可能新增必填项、输入类型可能收窄。`mcp-changecheck` 读取更新前后的两份工具快照，生成可读报告，帮助开发者在 CI 中发现这些变化。

**Python 3.10+，运行时零第三方依赖。** 完全离线，不调用大模型、不执行 MCP 服务、不需要 API Key。

## 快速体验

```sh
git clone https://github.com/L1Huash1/mcp-changecheck.git
cd mcp-changecheck
python -m pip install .
mcp-changecheck examples/before.json examples/after.json
```

示例数据是人工构造的：删除 `archive_note` 工具，为 `search_notes` 新增必填参数，并改变只读提示。默认会返回退出码 **1**，表示发现了需要处理的变化，这是预期结果。

```sh
# 生成 Markdown 报告
mcp-changecheck examples/before.json examples/after.json --format markdown --output report.md

# 只查看 JSON，不因发现变化而返回失败
mcp-changecheck examples/before.json examples/after.json --format json --fail-on never

# 相同快照应通过
mcp-changecheck examples/before.json examples/before.json
```

| 等级 | 含义 | 默认行为 |
| --- | --- | --- |
| breaking | 删除工具、新增必填输入、类型或枚举收窄等规则命中 | 返回失败 |
| review | 描述、提示、输出 schema 或复杂 schema 变化，需要人工核对 | 返回失败 |
| info | 新增工具、放宽必填要求等 | 通过 |

`--fail-on breaking` 只因 breaking 失败；`review` 同时包括 breaking，且为默认值；`any` 包括所有变化；`never` 只报告。输入无效时始终返回 **2**。正常且未达到阈值返回 **0**。

## 如何准备快照

可以使用自己的 MCP 客户端或 [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) 保存 `tools/list` 结果。支持以下结构，也支持直接使用工具数组：

```json
{"tools":[{"name":"lookup","inputSchema":{"type":"object"}}]}
```

```json
{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"lookup","inputSchema":{"type":"object"}}]}}
```

分页结果必须先完整收集并合并。存在非 null 的 `nextCursor` 会被拒绝，以免把尚未加载的工具误判为删除。不要直接删除分页标记来绕过检查。

工具顺序、属性顺序以及 `required`、`type`、`enum` 数组顺序不影响结果。报告包含稳定排序的变化、等级、JSON Pointer 路径和说明，可用于代码审查。

## 能力边界

- 这是基于规则的静态变化检查，不是完整的 JSON Schema 向后兼容证明。复杂组合、引用等改动进入 review。
- 输出 schema 与输入 schema 的兼容方向不同，首版对输出 schema 的实质变化统一要求人工核对。
- description 可能影响 Agent 选择工具，因此变化进入 review；这不代表检测到了提示注入。
- annotations 是服务端声明的提示。检查其变化不等于验证真实权限或安全性。
- 没有发现变化，只表示这些规则没有命中；不能推断服务端运行行为没有变化。
- 快照可能包含业务信息。程序不会联网，分享报告前仍需自行检查其中的输入内容。

完整 CLI、Python API、CI 示例和同类工具说明请看 [英文 README](README.md)。底层规则和已知限制见 [rules.md](docs/rules.md)。

## 开发

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

项目使用 MIT 许可证，开发过程有 AI 编程辅助。首版以可运行示例和回归测试为依据，不宣称生产级完备性。
