# Strict Review Workflow V0.1

Codex 主控依用户需求选择最少阶段；[工作流 Skill](../.agents/skills/strict-review-workflow/SKILL.md) 定义完整、方法、统计、一致性、独立复核和针对性复审六条路径。其余四个已有业务 Skill 与角色配置继续负责具体专业审查；本模块不调用模型、创建 Review Lead、修改稿件或提交期刊意见。

## 现有能力与边界

已有四组角色配置、业务 Skills、Review Finding Schema、任务契约和只读阶段校验器；语义审查仍需要实际 Codex 上下文，校验器只检查支持的 Schema 子集与引用。旧 Method、Statistics、Consistency 和 Doublecheck 示例对应不同稿件，不能将它们拼成同一审稿。`ExecutionResult` 不含 partial，因此会话清单使用 `partial`，各角色的结果仍按原有契约记录。聚合扩展保存在独立封套，不往 `additionalProperties: false` 的原 Finding 内添加字段。

[本地工作流模块](../src/ai4science/strict_review_workflow.py) 提供 `route`、`prepare_session`、`build_evidence_inventory`、`verify_session`、`record_stage`、`aggregate_findings`、`reuse_session` 和 `prepare_rereview`。仅在调用方先确认实际处理授权后创建独占会话与一次快照；在计算及汇总前校对原稿、快照、数据、配置和成果哈希。清单的权限判断、角色执行模式、材料状态和阶段成功是调用者的声明，并非权限、模型调用或科学判断的证明。多进程修改、符号链接竞态和操作系统访问控制不由 Python 路径检查保证。

单阶段模式仅路由指定阶段；完整模式采用 Method、Statistics、Consistency、Doublecheck、最终验证。先用新上下文对原始材料完成 Doublecheck Pass 1 并固定输出，之后才加载专家 findings；未实际强制隔离则 `blind_review=false`。失效阶段标记 `partial` 并保留其他输出。校验稿件版本及证据后，人工显式指定重复组，工具保留全部原 Finding、来源角色和 ID；严重性、状态分歧保持 unresolved。统计复算必须由受控工具实际执行；没有数据是报告级审查，没有看图片就不能声称视觉检查。旧版本 findings 在针对性复审中保持 `not_checked`，不能自动关闭。

已知限制：当前不提供自动语义去重、自动执行四个角色或对声明执行事件的硬证明；`record_stage` 不自动调用各角色专用校验器，主控必须先验证。没有实现正式的结构化统一审稿报告 Schema；原 Finding 使用现有 Schema，聚合封套在代码中检查；材料分类与审稿场景均须由人工判断。显式缓存复用要求权限、范围、配置文件、输入输出路径和哈希相同；如果配置文件只是包含 Skill 哈希的清单，调用方还必须重新核验其所指向的实际 Skill 文件，否则不能视作有效复用。

## 合成端到端验证

[完整会话](../workspace/projects/strict-review-synthetic/reviews/full-v01/)从一份授权合成稿及数据生成快照。三名新鲜上下文的通用代理分别执行对应 Skill，独立目录输出通过各角色既有 validator；Doublecheck Pass 1 先于读取这些结果冻结，再核验全部 11 条专家发现。共享文件系统并未强制隔离，诚实记录为非盲。四次自定义角色选择均真实返回 `unknown agent_type`；这些通用代理和 Skill 执行不冒称原生角色。新 Codex 调试上下文发现了工作流 Skill，但这并不证明原生角色发现。

[最终报告](../workspace/projects/strict-review-synthetic/reviews/full-v01/final_validation/strict_review_report.md)、[聚合结果](../workspace/projects/strict-review-synthetic/reviews/full-v01/final_validation/aggregated_findings.json)、[执行清单](../workspace/projects/strict-review-synthetic/reviews/full-v01/execution_manifest.json)、[20 项测试结果](../workspace/projects/strict-review-synthetic/reviews/full-v01/e2e_test_results.json)及各阶段保存在该目录。17 条原始发现人工分为 9 组；原 findings 和来源全部保留。对四条合成观测实际计算 RMSE 约 1.5811，单项计算不是实验复现；没有供应图像，未进行视觉审查。

20 项检查由 `PYTHONPATH=src python3 tests/validate_strict_review_saved_run.py` 复核已保存运行；不是自动重演模型审稿。单阶段路由、partial 失败和版本复审通过确定性测试；缺失数据使用先前已校验的 report-only 样例。由于真实本轮方法和统计审查已发现工作量差异，本轮没有声称 Doublecheck 发现了专家遗漏；测试 8 和 9 使用此前独立冻结的受控反例，三份审稿记录为人工合成，分别验证新问题识别和错误 Major finding 撤销，不冒称本轮真实专家生成了该误报。测试 10 只确认 `blind_review=false`，不证明访问隔离；测试 20 验证现有可用 Schema 和契约，不声称新封套有完整 JSON Schema。

正式保密送审须核查权利人及期刊、机构对实际模型处理环境的授权。若调用已安装 `peer-review` 工作流，必须通过其 unchanged intake gate；现有门控对 hosted processing 阻止，即使其他授权存在也不能伪称本地、改名或切 Skill 绕过。本次是用户明确要求的合成工程测试，不是期刊审稿。`scientific-critical-thinking` 1.5、`scientific-writing` 2.3 按适用范围复用，不调用外部图示或额外模型 API。

## 简短使用

在项目中指定或提供可确定的 `project_id` 和授权稿件，例如“对项目 X 的这份稿件做严格审稿”，或“只复核项目 X 稿件的统计方法”。收到作者修订稿后可说“针对新版本复查已确认的 Finding ID”；主控须重新核对新版本及证据，旧 finding 不自动关闭。人工保留最终决定，输出不等于期刊审稿意见或录用决策。
