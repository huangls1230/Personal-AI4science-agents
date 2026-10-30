# AI Strict Review Team（初始化）

本组独立检查研究方法、统计与可复现性、文稿内部一致性和科研论证；仅提供有证据、可追溯的审稿意见。Codex 是唯一主控，选择必要角色、分配授权材料和独占报告路径并核验结果；不创建 Review Lead 或独立调度器。团队默认只读稿件，可生成独立报告，不直接修改或覆盖原稿。

| 角色 | 主要职责 | 边界 |
| --- | --- | --- |
| `review_method` | 问题与方法匹配、假设、实验设计、基线、对照、消融及偏差 | 不做语言润色或实际统计重算。 |
| `review_statistics` | 指标、统计假设、重复实验、不确定性、关键计算和可复现性 | 没有经授权的原始数据、代码和设置时仅审查报告，不能声称复现。 |
| `review_consistency` | 摘要、正文、表格、图形、公式、单位和主张与证据的对应 | 没有实际图像时标明未视觉核查；不做排版或润色。 |
| `review_doublecheck` | 先独立重建问题到结论的科研证据链，再核验其他角色的重大意见和冲突 | 对原稿及证据形成独立判断；不等同以组织结构为主的 `paper_structure`，不只复述别人的意见。 |

审查必须区分已核实的问题、潜在风险、报告不足、资料缺失和未检查；“未报告”不等于“未执行”。每项意见依据位置、证据、推理及影响具体说明，并附适用的可执行建议与不确定性。严重程度由研究背景和实际影响判断，不按措辞自动判定。AI 报告不是正式期刊专家意见或录用判断。

具体执行边界见 [workflow.md](workflow.md)、[审稿问题 Schema](review-finding.schema.json)、[报告模板](templates/review-report-template.md)、[Skill 审计](skill-audit.md)和[验证记录](validation.md)。项目已有 [scientific-writing](../../.agents/skills/scientific-writing/SKILL.md) 可按其授权边界复用证据绑定与一致性检查；其文件约束、依赖和局限以本地安装版本为准。四个新配置不证明当前会话已发现它们，且角色指令不构成操作系统级只读沙箱。

`review_method` 的方法审查 V0.1 见[方法审查说明](../../docs/review-method-v0.1.md)；`review_statistics` 的统计复算和可复现性 V0.1 见[统计审查说明](../../docs/review-statistics-v0.1.md)；`review_consistency` 的证据约束审查见[一致性审查说明](../../docs/review-consistency-v0.1.md)。`review_doublecheck` 的独立推理及裁定 V0.1 见[双重审查说明](../../docs/review-doublecheck-v0.1.md)；完整团队集成尚未实现。

统一审稿入口、执行状态及合成验证见 [Strict Review Workflow V0.1](../../docs/strict-review-workflow-v0.1.md)。
