# 初始化验证记录

日期：2026-10-30。只使用 [合成稿](fixtures/manuscript.md)，没有审查真实论文、运行统计复现、调用额外第三方模型服务或写入原稿；下述临时 Codex 会话使用了 Codex 自身模型运行时。

## 配置与 Schema

- 四个 `.codex/agents/review_*.toml` 可用 Python `tomllib` 解析；各有且仅有非空 `name`、`description`、`developer_instructions`，名字与文件名一致，均未指定模型。已按职责核对只读和证据边界、图像与复现限制，以及 doublecheck 的先独立后交叉复核要求；这不能证明真实科研判断质量。
- `python3 teams/strict_review/tests/test_schema.py -v`：5 项通过，包含四种核验状态、无证据反例、错误字段、哈希和报告模板。此测试是针对本 Schema 所用关键字的离线检查器，并非完整的 JSON Schema 2020-12 官方验证器。结构合法不代表证据或科研判断为真。
- 按模板字段填写了 [合成报告示例](fixtures/review-report.example.md)；示例明确列出未执行复现、图像核查和独立复核，不冒充真实 Agent 结果。
- 在临时 workspace 中将合成稿复制到示例所指的相对路径，以现有 `EvidenceReference.from_dict` 和 `ArtifactReference.verify` 校验示例中的证据及哈希，均通过；仓库示例的相对路径是演示路径，不表示真实 workspace 已存在该文件。
- `PYTHONPATH=src python3 -m unittest tests.test_paper_editing_workflow tests.test_literature_search tests.test_contracts`：25 项通过；没有修改两组核心业务。检查范围仅涵盖这些测试，不代表完整系统均通过验证。
- 四个上游 Skill 的审核覆盖范围和阻塞见 [skill-audit.md](skill-audit.md)。本轮没有安装它们；已安装 scientific-writing 的本地来源及补丁另见其 PROVENANCE。

## 运行时发现与调用

当前主会话的 `collaboration.spawn_agent` 支持 `agent_type`，并列出已存在的 Literature 和 Paper Editing 自定义角色；其可见类型清单中没有本轮新建的四个角色。文件可解析不等于已被本会话发现，也不能通过任务名称或提示词冒充角色。主会话未使用新角色执行测试。

本地 `codex debug prompt-input` 可以生成新提示内容，但该内容未暴露 `agent_type` 工具定义，不能用于证明或否定新角色发现。另启动了一次本地 `codex exec --ephemeral --sandbox read-only --json` 的有界新会话，请其仅在确有 `review_method` 类型时以该角色只读概括本组 README。测试在 85 秒后超时；[部分事件日志](../../workspace/runs/strict-review-initialization/codex-role-probe.jsonl)包含传输降级错误、助手声称及 `wait` 开始事件，但**没有可核查的 `review_method` 创建或完成事件**，因此不计为成功调用，发现和配置实际加载均未证明。需在后续会话观察真实类型清单和指定角色委派事件，再验证实际加载；不因缺少此证据阻止后续功能设计。

[OpenAI 官方 Subagents 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)说明 `.codex/agents/` 可存放项目级自定义角色，`name` 是角色身份，角色继承父会话权限；具体会话是否发现、刷新或调用必须以实际工具为准。配置指令不能形成独立的只读沙箱。
