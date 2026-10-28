# Codex 原生集成边界

本机初始检查：Codex CLI `0.163.0-alpha.10.2`，`codex features list` 显示 `multi_agent` 为 stable 且启用；Python 为 3.13.18。CLI 启动时提示无法创建 PATH aliases，但只读版本、帮助和功能列表命令均成功。此检查不证明特定模型、外部服务或项目级配置在所有环境可用。

当前 OpenAI 官方文档说明，Codex 可以使用项目级 `.codex/agents/*.toml` 定义自定义子代理；`.agents/skills/<skill>/SKILL.md` 是项目级技能目录；受信任项目可以在 `.codex/config.toml` 配置 MCP 服务。配置参考中的 `agents.max_concurrent_threads_per_session` 控制会话中子代理并发线程数，`agents.max_threads` 是旧别名。具体选项必须按实际安装版本验证，不应直接把当前在线文档视为旧版本的实测结果。

- [Codex Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)

Codex 原生委派是当前运行时提供的工具能力，不是 Python 可以默认导入的公共 API。V0.1 的原生执行器仅作为集成边界；真正的委派由 Codex 发起，调用后需将结构化结果和证据交回主控验证。没有在本项目注册实际的原生角色或 MCP 服务，也没有修改用户全局配置。后续连接前须验证当前 CLI 版本、角色发现、运行权限、输入裁剪、输出契约与用量可观测性。
