# Codex 原生集成边界

本机初始检查：Codex CLI `0.163.0-alpha.10.2`，`codex features list` 显示 `multi_agent` 为 stable 且启用；Python 为 3.13.18。CLI 启动时提示无法创建 PATH aliases，但只读版本、帮助和功能列表命令均成功。此检查不证明特定模型、外部服务或项目级配置在所有环境可用。

当前 OpenAI 官方文档说明，Codex 可以使用项目级 `.codex/agents/*.toml` 定义自定义子代理；`.agents/skills/<skill>/SKILL.md` 是项目级技能目录；受信任项目可以在 `.codex/config.toml` 配置 MCP 服务。配置参考中的 `agents.max_concurrent_threads_per_session` 控制会话中子代理并发线程数，`agents.max_threads` 是旧别名。具体选项必须按实际安装版本验证，不应直接把当前在线文档视为旧版本的实测结果。

- [Codex Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)

Codex 原生委派是当前运行时提供的工具能力，不是 Python 可以默认导入的公共 API。V0.1 的原生执行器仅作为集成边界；真正的委派由 Codex 发起，调用后需将结构化结果和证据交回主控验证。项目已在 `.codex/agents/` 定义三个 Literature 角色，未配置 MCP 服务，也没有修改用户全局配置。角色发现和实际调用需单独验证；原生调用不自动经过项目 Python 适配器和 BudgetGuard。后续连接前须验证运行权限、输入裁剪、输出契约与用量可观测性。

## 本次发现与调用验证

2026-10-28，CLI `0.163.0-alpha.10.2` 的 `multi_agent` 功能列表显示启用；三个角色文件已用 Python `tomllib` 解析并检查必填字段与唯一名称。这些静态检查不能证明 Codex 已发现或调用角色。

尝试在本项目目录执行 `codex exec --ephemeral --sandbox read-only --json`，请求分别委派三个角色；当前受限环境在初始化进程内 app-server 时返回 `Operation not permitted (os error 1)`，未产生角色发现或调用事件。还需在有适当执行权限的 Codex 会话中重新启动或刷新项目后分别调用三种角色，并检查实际委派事件与结果；仅凭模型自述不算验证。该检查不需要修改全局配置。

2026-10-28 后续验证：在允许启动 CLI 的环境里，两次 `codex exec --ephemeral --sandbox read-only --json` 已能运行（一次使用默认配置，一次只在该次进程中启用 `multi_agent_v2`）。两次均未产生 `literature_search` 的 spawn 事件；会话报告当前 spawn 接口无法选择自定义 Agent 类型。WebSocket TLS 握手失败后 CLI 回退 HTTPS 并完成请求，因此这次阻塞不应简单归因于 app-server 启动失败。实际角色发现及委派仍未通过验证；普通子代理和模型自述不能代替委派事件。测试事件位于 `workspace/runs/live-multi-agent-topology/codex-discovery*.jsonl`。未修改全局配置。
