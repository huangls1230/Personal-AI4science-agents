# Research Methodology Reviewer V0.1

> 本文中的合成审查与角色测试为 Step 2 原始记录。两个参考 Skill 的后续安装、实际加载证据及托管 peer-review 门控限制见 [Step 2.5 集成验证](review-skills-integration-v0.1.md)。

`review_method` 进行方法和实验设计审查，由 Codex 主控；角色负责学术判断，[methodology-review Skill](../.agents/skills/methodology-review/SKILL.md) 定义流程，[只读校验器](../src/ai4science/method_review_validation.py)检查可确定的结构和引用。该阶段不实现 Statistics、Consistency 或 Doublecheck 业务，也不连接新的模型 API。

## 使用与输入

提供 `project_id`、workspace 内 Markdown 的 `manuscript_path`、`review_scope`、`research_domain`、可授权的 `evidence_paths`、独立 `output_directory` 和 `review_policy`。先核实文件权限与哈希；涉及他人保密送审稿件，核查适用的权利人、期刊 AI 与保密政策。未知、未提供或未授权的资料不应当作已审查。生成成果不能覆盖原稿或其他输入。当前校验器仅处理 UTF-8 文本和行号；PDF 等须先通过已有授权解析能力转换并保留原始页码映射，此阶段没有实现 PDF 页面定位。

审稿者按需读取相关章节，重建研究问题、目标、假设、方法、实验和主张；提取明确和有依据推断的假设；根据研究内容选择基线、泄漏、预测误差、通信成本、扩展性和有效性等检查项。报告应包含合理设计及局限；不把未报告当作未执行。建议额外实验时说明目标主张、证据缺口、排除的替代解释与可行的低成本选项。Statistics、Consistency 和 Doublecheck 的工作不由本角色冒充。

## 输出协议

- `method_review.md`：审查范围、设计图、设计优点、问题及严重性、假设、对照、有效性、可复现性和局限。明确 `inline_skill` 或有真实事件的 `native_subagent`。
- `method_findings.json`：由 [Review Finding Schema](../teams/strict_review/review-finding.schema.json) 对象构成的 JSON 数组。稿件的 `source_location` 和每条证据的 `locator` 均为 `L<起>-L<止>`；证据包含 workspace 相对路径、SHA-256、说明和位置。`verified` 仅表示确实检查了具体观察，不表示研究结论为真。
- `assumptions_register.yaml`：JSON 语法的 YAML 1.2 子集，顶层唯一键为 `assumptions` 数组；每项含假设描述、显式或隐含、原文行号、为何需要、支持依据、失效条件、影响、验证建议、`verification_status` 和 `reporting_status`。模型推断必须与作者原文分开。
- 主控可将任务和结果分别映射到现有 `ResearchTask` 和 `ExecutionResult`；生成完成、机械检查、科研质量和人工批准是不同状态。项目产物仅返回必要摘要、路径与哈希。

对已生成的三个文件使用只读检查：

```python
from pathlib import Path
from ai4science.method_review_validation import validate_method_review_run

errors = validate_method_review_run(
    Path('workspace'), 'projects/example/manuscript.md',
    'projects/example/review/method_findings.json',
    'projects/example/review/assumptions_register.yaml',
    'projects/example/review/method_review.md',
    evidence_paths=(), allowed_line_ranges=None,
)
```

以上路径只是示意。调用方必须明确授权额外证据；验证器检查文件存在和非别名、授权范围、行号、哈希、原 Schema 当前关键字、重复 ID 和假设字段，但不判断引文是否支持结论，不证明质量或授权，不提供防并发路径替换的 OS 沙箱。它是只读 API，不生成输出；写入时仍需使用实际权限，确保独占输出且不覆盖原稿。

## 本次合成验证

主控先依据合成稿独立审查，固定三个输出哈希后才读取 [预期核对清单](../teams/strict_review/fixtures/method-review-v01/expected-checks.md)；独立通用子代理仅使用 Skill 与两份稿件进行只读盲查，不冒充 `review_method`。两者均定位到稿件明确描述的 t 时输入 t+5 真实值、单一弱对照、20 个体支持不足的扩展性主张、遗漏维护成本和未报告的预测误差；均区分聚合规则未描述与已证实缺陷，并识别共享时钟和配对任务作为合理控制。合成结果数值没有被当成真实实验。

边界稿有当前或历史输入、匹配的无预测对照、范围有限的主张和误差扰动；主控审查没有将它们误报为主稿中的同类缺陷，只记录未提供配置和日志。此单个边界样本不代表实际误报率。

三个主报告输出及对应假设登记使用 `validate_method_review_run` 通过校验，边界案例也通过；[校验器测试](../tests/test_method_review_validation.py)九项通过，覆盖未授权证据、路径逃逸/别名、行号范围、哈希和格式。示例的 `ResearchTask` 和 `ExecutionResult` 已分别校验；质量和人工批准未自动通过。校验器按原 Schema 已用关键字实现受限子集，不是完整 JSON Schema 实现。

本会话实际调用 `collaboration.spawn_agent` 时指定 `agent_type=review_method`，工具返回 `unknown agent_type 'review_method'`，因此实际角色未发现、未调用；主审查记录为 `inline_skill`。独立盲查使用的是通用角色而非原生审稿角色。新 Skill 在本会话可直接读取；不能由此推断当前会话启动时的 Skill 清单已更新或新会话已自动加载。
