# Scientific consistency review V0.1

Codex 主控按任务选择 `.codex/agents/review_consistency.toml` 和 [consistency-review](../.agents/skills/consistency-review/SKILL.md)。以授权 Markdown 及所需证据为输入，以独立 Workspace 输出报告；不修改原稿、原图、数据或其他审稿角色的成果。此版本的论文语义、公式和图形判断由实际阅读材料的 Codex 执行，Python 不替代科学判断。只使用必要的引用和参考材料，不创建新的调度器或外部模型连接。

## 执行与证据

1. 确认材料授权、保密规则和处理环境。外部保密送审稿件必须先核查相关权利方 AI 政策；本地文件不代表托管模型本地运行。`peer-review` 如被用于正式工作流，必须实际通过其 intake 门控；阻止时停止该工作流，不得改名绕过。
2. 索引章节与引用，记录来源路径、SHA-256、位置及可用状态。围绕每个 claim 比较实际原文、表格、公式和经查看的图像，记录条件、单位、精度与范围；缺失或未查看单列，不能从图注推断图像。
3. 输出 `consistency_review.md`、符合统一审稿 Schema 的 `consistency_findings.json`、`claim_evidence_matrix.json`、`cross_reference_audit.json`、`visual_review_manifest.json` 和 `evidence_inventory.json`。Finding 的 verified 只表示该有限观察被核验；矩阵另区分内部一致、矛盾、潜在问题、资料不足、未核查。
4. [consistency_review_validation.py](../src/ai4science/consistency_review_validation.py) 提供有限 Markdown 索引、同单位同条件数值比较、证据路径与哈希、位置、输出结构和 Finding Schema 检查；视觉清单只能检查字段和文件，无法证明图片确被查看。路径检查不是 OS 沙箱，不抵抗并发替换。
5. Statistics 交接须提供其审查稿件、全套报告、获授权输入及可信计算脚本；复用原有校验并核对两份稿件 SHA-256。`completed_record` 仅表明报告记录了完成，并非独立证明执行、数据真实性或结论。未执行、版本不匹配或材料不足不得宣称独立核实。逐项比较指标、单位、条件、聚合和证据 ID；不重算整个统计工作流。

## 合成测试

[输入材料](../teams/strict_review/fixtures/consistency-review-v01/)包含两张真实图、其数据、盲审稿、边界对照稿和独立预期清单。主控实际读取图像并产生 [报告](../workspace/runs/consistency-review-v01/outputs/consistency_review.md)、[矩阵](../workspace/runs/consistency-review-v01/outputs/claim_evidence_matrix.json)、[视觉记录](../workspace/runs/consistency-review-v01/outputs/visual_review_manifest.json)。报告及其控制产物的 SHA-256 在读取期望清单前固定。另一个通用子代理对稿件及图像进行了独立盲审；它不是 `review_consistency` 原生调用。

本会话 `spawn_agent(agent_type="review_consistency")` 返回 `unknown agent_type 'review_consistency'`；因此测试执行方式为 `inline_skill`，不宣称角色已被发现或调用。新启动的 Codex `debug prompt-input` 可发现 Skill 元数据，当前会话通过读取文件实际加载 Skill；这不等同于原生角色加载。已读取 scientific-writing 2.3 和 scientific-critical-thinking 1.5 以约束证据与推理；peer-review 2.4 已安装但本合成工程测试未调用其受限正式审稿工作流。上游版本与本地补丁参见团队审计记录。

视觉检查、语义判断和报告需要人工复核。当前解析器仅做有限 Markdown 字面索引，不保证完整支持复杂 Markdown、跨文件 LaTeX、DOCX、PDF、图片像素精确值、自动提取图表或所有文献编号；不存在自动端到端审稿或科学真实性证明。
