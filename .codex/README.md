# 项目 Codex 配置

`agents/` 定义 Literature 和 Paper Editing 的项目级 Custom Subagents。未指定模型时继承会话的模型配置；角色继承父会话工具和权限。项目没有配置 MCP 服务，Python 原生适配器仍未接通。实际发现与调用需按当前 Codex 版本验证；详见 `docs/codex-integration.md`。
