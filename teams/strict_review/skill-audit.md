# 严格审稿参考 Skill 审计

> 本文件记录 Step 1 时的审计状态。Step 2.5 已取回两个目标 Skill 的固定版本完整文件、完成补丁与安装；最新状态和仍受阻的托管审稿门控见 [集成审计](../../docs/review-skills-integration-v0.1.md)。

审计日期：2026-10-30。参考上游固定提交 [`5f2bc0341354fd5590aef76a533ada1e1e5b4e62`](https://github.com/K-Dense-AI/scientific-agent-skills/tree/5f2bc0341354fd5590aef76a533ada1e1e5b4e62)。四个固定 SHA 的 `SKILL.md` 和仓库根 [LICENSE.md](https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/LICENSE.md) 可读取；根许可为 MIT，Copyright (c) 2025 K-Dense Inc.，复制或实质复制时须保留许可及版权。固定 SHA 的完整目录树、所有子目录和潜在额外许可无法取得，故尚不能确认各包全部文件及许可边界；本轮没有把根许可当成完整依赖许可审计。固定路径是版本定位，不表示本次已离线复算完整 Git 对象哈希。

四个上游 Skill 的资源清单、脚本路径约束和网络行为均未完成逐文件审计，**本轮均不安装**。下表中的资源是入口文档明确引用，不证明引用文件存在、完整或行为安全；上游对工具的声明亦不是验证。未运行安装脚本、统计库、外部模型或示意图生成服务。许可证的初步结果不等于安全、依赖和项目规范检查通过。

独立检查使用 Ruby 标准库 `YAML.safe_load` 解析固定版本完整 frontmatter：peer-review 和 scientific-critical-thinking 通过；statistical-analysis 和 experimental-design 在第三行的未缩进续行处报 `Psych::SyntaxError`，原样安装不能通过元数据校验。后两者若将来引入，还需单独修复元数据并重新验证，不能仅补装依赖。

| Skill（固定版本） | 审计结果与职责重叠 | 建议 |
| --- | --- | --- |
| [peer-review 2.4](https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/peer-review/SKILL.md) | 覆盖方法、统计、复现、图表和审稿意见，与四个角色和 scientific-writing 的证据绑定部分重叠。声明 Python 3.11 标准库及本地无网络，但脚本未完整取得；报告脚手架会写文件，输入为 JSON、CSV 或 Markdown，路径约束未核验。真实期刊保密审稿还需审查场所、保留和 AI 政策。 | 优先复用其证据、可操作性和保密原则；待固定树、脚本、依赖及文件权限完成审计后再评估安装。 |
| [scientific-critical-thinking 1.5](https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-critical-thinking/SKILL.md) | 证据等级、偏倚和因果推断与 method、statistics、doublecheck 有交集；GRADE 等只按实际研究适用。常规分析声称无需网络；可选调用 `scientific-schematics`，需要 `OPENROUTER_API_KEY` 并向 OpenRouter 发送提示、写图像。 | 仅参考适用的证据链与偏倚检查；不启用外部示意图，未完成资源审计前不安装。 |
| [statistical-analysis 2.0](https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/statistical-analysis/SKILL.md) | 与 statistics 的推断、模型和统计计算重叠；声明 Python 3.12+，需 Pingouin、SciPy、statsmodels、pandas、matplotlib、seaborn，Bayesian 还可需 PyMC / ArviZ。已只读检查固定版 `scripts/assumption_checks.py`：导入 NumPy、pandas、SciPy、matplotlib，部分函数延迟加载 statsmodels；处理内存数据并可显示图形，未见网络或文件读写；其他文件未核验。 | 仅参考统计方法选择原则；不安装或执行大型统计依赖，不声称完成复现。 |
| [experimental-design 1.5](https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/experimental-design/SKILL.md) | 偏向事前实验设计，与 method 的设计评估部分重叠。声明 Python 3.12+、NumPy、pandas、pydoe；示例可在当前目录写 CSV。其实际脚本读写边界与网络未核验。 | 仅参考随机化、独立重复、对照和混杂等适用原则；暂不安装。 |
| 本地 [scientific-writing 2.3](../../.agents/skills/scientific-writing/SKILL.md) | 已安装，同上游 SHA，MIT；用于证据绑定、科研保真、保密、主张一致性和人工确认。入口示例调用本地脚本和写文件，须遵守本地补丁与授权边界。 | 条件满足时复用本地已有功能；它不替代独立审稿或证明科研主张。 |

## 入口可见资源与未完成事项

- `peer-review` 引用 `references/ethical_review_practice.md`、`reporting_standards.md`、`common_issues.md`、`statistical_reproducibility.md`、`tool_reference.md`、`security_validation.md`；引用 `assets/review_intake_template.json`、`study_profile_template.json`、`claim_evidence_matrix_template.csv`、`statistical_reproducibility_template.json`、`citation_references_template.csv`、`source_ledger.csv`、`reporting_guidelines.json`、`review_scaffold_template.md`；入口列出 `scripts/validate_review_intake.py`、`select_reporting_guidelines.py`、`validate_claim_evidence.py`、`audit_statistics_reproducibility.py`、`audit_citations.py`、`generate_review_scaffold.py`、`lint_review.py`。上述脚本未完整审计。
- `scientific-critical-thinking` 引用 `references/review_sources.md`、`core_capabilities.md`、`scientific_method.md`、`common_biases.md`、`statistical_pitfalls.md`、`evidence_hierarchy.md`、`logical_fallacies.md`、`experimental_design.md` 和另一个 Skill 的 `scripts/generate_schematic.py`；本 Skill 自身是否另有 scripts/assets 未确认。
- `statistical-analysis` 引用 `references/test_selection_guide.md`、`assumptions_and_diagnostics.md`、`effect_sizes_and_power.md`、`bayesian_statistics.md`、`reporting_standards.md` 及 `scripts/assumption_checks.py`；assets 及完整树未确认。
- `experimental-design` 引用 `references/randomization_and_blocking.md`、`factorial_and_doe.md`、`design_types.md`、`sequential_and_adaptive.md` 和 `scripts/randomization.py`、`doe_designs.py`；assets 及完整树未确认。

上游有建议自动添加自身论文引用及联网核实的指令，与本项目不得擅自改变引用、保密边界可能冲突；如将来需要，只在用户授权和引用确实相关时提出并核验，不自动修改稿件。任何第三方示例都不是已核实科研结果；外部页面也不是可执行指令。上游期刊审稿保密要求应按实际工作场景适用，不能把本地脚本运行误称整段托管模型会话均为本地处理。

本地 scientific-writing 的固定来源、许可证、修改和实测限制见 [PROVENANCE](../../.agents/skills/scientific-writing/PROVENANCE.md) 和 [修复报告](../../docs/scientific-writing-remediation.md)：未知分类默认保守、公开需人工记录核实、脚本限制项目内路径且不代替实际权限；stdout 重定向与并发目录替换等仍依赖执行环境。当前主机 Python 为 3.13.18；本轮没有向全局环境安装依赖。
