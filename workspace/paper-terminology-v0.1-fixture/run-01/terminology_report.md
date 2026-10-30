# 术语审查报告

- 任务 ID：paper-terminology-v0.1-synthetic-01；执行器：paper_terminology；实际模式：native_subagent。
- 输入版本与范围：`paper-terminology-v0.1-fixture/manuscript.md`，SHA-256 `c339f56ab7f085348c3bc2c057083129d858a1b68b8a5a7ff753f2f48b36dc1c`；合成稿件全文；只分析和提出建议。
- 既有术语表：`paper-terminology-v0.1-fixture/prior_glossary.yaml`，SHA-256 `d887a5bb46d15984f87436e87ba039cda9a044da353d50b20e5e6c74de2a94b2`。原条目完整增量保留；其 approved 仅模拟批准，未发生真实作者批准。
- 领域及主题：仅依据稿件可识别为多智能体协调中的时间序列预测；投稿期刊、政策与实际研究证据未知。稿件明确为虚构测试，未报告实验或测量。
- 提案已生成；科学真实性和作者批准均未验证，不代表质量已获确认。全文未编辑。

## 核心清单

上下文、逐次字面位置和精确计数见 `terminology_glossary.yaml`。涵盖系统／通信图、模型 Horizon Mapper、GCF、预测时域、通信惩罚权重、符号 `\lambda`、具有不同意义的 agent、MAE 和 AAE。计数区分大小写、包含子串、不同变体或条目重叠时分别计数；相同行的重复项分别列出，不将计数视为同义证明。所有新项均为 proposed、unverified；定义仅转述稿件，未知的保留 null。未提供数据集、实际算法名称或伪代码；没有实际表格、图、测量。单位仅可评估第 19 行时间步和第 21 行无量纲。

## 问题、缩写与符号

| ID | 原文定位及上下文 | 提议／作者问题 | 优先级；语义风险；批准 |
| --- | --- | --- | --- |
| T01 | Introduction 第 11 行 `Multi-Agent System`；Abstract 第 7 行为 `multi-agent system` | 专名地位确认后，可统一大小写；摘要和正文各自定义 MAS 是否合适取决于未知的期刊规则。 | 中；低；需确认 |
| T02 | Introduction 第 13 行 `Multi-Agent system` | 与第 7、11 行大小写不同；确认专名地位后考虑统一。 | 中；低；需确认 |
| T03 | Introduction 第 11 行 `Agent Network` 与 `agent network` 同句并存 | 是否统一大小写取决于专名地位。 | 低；低；需确认 |
| T04 | Introduction 第 13 行 `MAS and the Agent Network`；第 11 行图、第 7 和 11 行系统的描述不同 | 两者被称作可互换；请作者确认是否确实等同，不能自动替换，可能改变科学含义。 | 高；高；需作者批准 |
| T05 | Introduction 第 15 行 `GCF` | 无扩展及定义；请作者提供，不能猜测。 | 高；中；需确认 |
| T06 | Method 第 19、21 行 `\lambda` | 同一符号分别用于以时间步计的预测时域及无量纲通信惩罚权重；请作者区分并核对公式和引用，任何变量变更均可能改变科学含义。 | 高；高；需作者明确批准 |
| T07 | Method 第 23 行 `agent` | 自主决策实体和软件组件是文中区分的含义；具体用法不作全局等同，改变可能影响科学含义。 | 中；高；需作者批准 |
| T08 | Planned Evaluation 第 27 行 `mean absolute error (MAE)`、`Average Absolute Error (AAE)` | 文稿称为相同预期量，但没有实际表格；请作者确认未来使用的名称及缩写，统一可能影响科学含义。 | 中；中；需确认 |

## 未决事项与交接

请作者决定系统与图的关系、GCF 含义、两种 `\lambda` 的记号及其引用、agent 的语境、MAE/AAE 的拟用名称。符号或定义变更必须经过作者专门审查。结构与一般语言修改不在本任务范围。模拟批准的 Horizon Mapper 约束、新提案及未决项分别载于 `language_handoff.md`；模拟状态不构成真实批准。
