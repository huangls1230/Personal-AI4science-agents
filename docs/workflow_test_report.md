# AI Paper Editing Team 工作流测试报告

日期：2026-10-29。测试材料是 [合成稿](../workspace/paper-language-v0.1-fixture/manuscript.md)，其中数值、引用及结果均是虚构内容。[术语表](../workspace/paper-language-v0.1-fixture/terminology_glossary.yaml)的批准是模拟的，不存在真实作者批准。没有发送真实科研稿件到外部服务。

主控在本次会话实际依次调用 `collaboration.spawn_agent`：`agent_type=paper_structure`（`/root/integration_structure`）、`agent_type=paper_terminology`（`/root/integration_terminology`）、`agent_type=paper_language`（`/root/integration_language`）。三者返回的原生角色调用事件可核查；各自仅获得授权材料和独占输出目录。结构提案和术语提案均未被应用，术语和语言阶段引用同一原稿哈希。历史各阶段的独立单角色原生调用与结果分别见 [Structure](paper-structure-v0.1.md)、[Terminology](paper-terminology-v0.1.md)、[Language](paper-language-v0.1.md)。

| 测试 | 结果与证据 |
| --- | --- |
| 1 Structure-only | 路由单元测试仅选择 structure；上一阶段已实际单独调用该角色。本轮完整流程再次真实调用。 |
| 2 Terminology-only | 路由单元测试仅选择 terminology；上一阶段已有实际单角色调用。本轮完整流程再次真实调用。 |
| 3 Language-only | 路由单元测试仅选择 language；上一阶段已有实际单角色调用。本轮完整流程再次真实调用。 |
| 4 完整三阶段 | 本轮三个真实原生调用串行完成；[结构](../workspace/paper-editing-integration-fixture/full-run/structure/structure_report.md)、[术语](../workspace/paper-editing-integration-fixture/full-run/terminology/terminology_report.md)、[语言](../workspace/paper-editing-integration-fixture/full-run/language/language_report.md)产物经主控核验。 |
| 5 已批准术语一致性 | 合成术语表中的模拟批准条目被增量保留，语言校验的字面匹配通过；这不是实际作者批准。 |
| 6 引用、公式、数值 | 现有语言校验器对样例中可识别的保护项通过；不证明任意格式或科研事实正确。 |
| 7 原稿保护 | 原稿前后 SHA-256 均为 `fa05039c73ebacae4d9f1d76d901521e00d78603ddf703ce91974bf2d45a4501`；候选稿单独存放。 |
| 8 未批准结构 | 术语与语言阶段的请求均指向原稿；结构报告只作为未批准参考。 |
| 9 单阶段失败 | 模拟失败后依赖阶段不能开始；显式重试受次数限制。没有对真实角色注入故障。 |
| 10 源文件冲突 | 单元测试修改临时源文件后，阶段完成被拒绝，状态标记失败。该检查不防并发竞态。 |
| 11 修改记录 | [修改日志](../workspace/paper-editing-integration-fixture/full-run/change_log.md)、[逐项 JSON](../workspace/paper-editing-integration-fixture/full-run/language/language_changes.json)和[版本清单](../workspace/paper-editing-integration-fixture/full-run/version_manifest.json)已生成；端到端测试核对各产物哈希。 |
| 12 原生与内联区分 | 本轮真实调用为 native；单元测试验证 `inline_skill` 与 `native_subagent` 分别记录。本轮未实际执行内联业务流程，字段值单独不能证明调用事件。 |
| 13 重复执行 | 状态辅助模块对相同输入和配置复用已记录运行，并校验产物未被改写；此测试是本地状态测试，实际角色调用由 Codex 主控完成。 |
| 14 缺少术语表 | 语言及完整任务准备时拒绝缺失术语表，给出错误；不猜测作者批准。 |

专项 `test_paper_editing*.py` 共 14 项通过。全项目测试运行 167 项，11 项因缺少可选 PDF 依赖而跳过。最终候选稿仍包含四条未获真人批准的语言建议，因此批准检查明确为 **PENDING**，最终状态 `awaiting_author_approval`；详见 [最终一致性报告](../workspace/paper-editing-integration-fixture/full-run/final_validation_report.md)。
