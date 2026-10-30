# 术语审阅报告

- 任务 ID / 执行者 / 实际模式：integration-full-terminology / paper_terminology / native_subagent。
- 原稿：`paper-language-v0.1-fixture/manuscript.md`，SHA-256 `fa05039c73ebacae4d9f1d76d901521e00d78603ddf703ce91974bf2d45a4501`；全文，包括表格、公式和代码。结构建议未应用，故采用原稿。
- 旧表：`paper-language-v0.1-fixture/terminology_glossary.yaml`，SHA-256 `b9984d7799e7ceb01ab603447cc27ab1085fb40d19a8a17333c568b20baad2a0`。原条目完整保留，其 approved 仅为合成模拟，并非真人批准。
- 结构报告：`paper-editing-integration-fixture/full-run/structure/structure_report.md`，SHA-256 `aeae3590b105d85d236a0e620c26dfcae6b8caf349f77a2933a38db708564648`；仅作未批准参考。
- 主题：多智能体协作中的时间序列预测；研究领域、文章类型及目标期刊的更具体信息未知。第3行声明全部观察、数值、模型名与引用标识均为虚构；不作为真实研究发现。未联网或独立核验科学主张。
- 分析及提案已完成；质量待父级独立验证。所有新增术语和修改建议为 proposed，未获作者审批，均未应用。

## 核心术语清单

既有模拟批准条目为 multi-agent system / MAS、Horizon Mapper、mean absolute error / MAE、x_t。增量候选为 time series、forecast horizon / forecast_horizon、controller、monitor、预测符号和函数表达式。完整逐次原文、行号、上下文及计数见 `terminology_glossary.yaml`。大小写敏感，以每个选定字面串出现次数计数，包括子串与重叠变体分别计数；候选代码标识未断言与正文术语等价。旧表条目完整保留，含原有核验及模拟批准状态。算法和数据集名称未给出；存在合成代码与结果表，无图。第32行表格重述 MAE 数值和单位，第28行的 units 未进一步定义；不推断单位。

## 术语、缩写及符号问题

- T01，第11行 `multi-agent system`：摘要第7行定义 MAS，正文未再次引入该缩写。摘要与正文是否各自定义取决于未知期刊规则；请作者确认，不直接替换。优先级低，语义风险低，待审批。
- T02，第17行 `forecast horizon`：四时间步与第19行单步下标及第23行代码变量的关系未说明；可能一致亦可能不同，请作者解释。优先级高，语义风险高，待审批；禁止自动修改公式或数值。
- T03，第19行 `\hat{y}_{t+1}`：预测符号、函数 f 与正文复数 observations 和 x_t 的关系未充分定义。请作者确认，保留原式及定义。优先级高，语义风险高，待审批。
- T04，第13行 `input`：检查对象及检查者未明确；不假定 input、observations、x_t 等价或改变组件职责。请作者确认。优先级中，语义风险高，待审批。

MAE 在方法第17行定义，结果及表格中使用；MAS 在摘要第7行定义。是否需在正文独立定义 MAS 取决于目标期刊，当前未知。这里未对公式、变量、代码、单位、引文或数字作改动，也未将相近术语强行合并。

## 待作者决定和边界

请确认四步预测与单步表达式的关系，函数和变量所指，input 与 observation 的关系及检查组件，并确定目标期刊的缩写规则。涉及符号定义、公式、代码或科学含义的任何修改须专项作者审批。第28行差异及关联的依据由结构审阅提出，术语阶段不新增依据。所有定义均未独立核验；研究结论、引用及数值不在此次验证范围。

## 语言阶段交接

旧表 approved 仅为合成模拟约束；新增术语均为未批准建议，不能作为作者批准的标准。详见 `language_handoff.md`。
