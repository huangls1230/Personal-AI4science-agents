# 学术语言审校报告

- 任务 ID、实际执行方式和执行器：`integration-full-language`；`native_subagent`；`paper_language`。
- 项目与原稿：`integration-synthetic-v01`；合成测试稿 `paper-language-v0.1-fixture/manuscript.md`；SHA-256 `fa05039c73ebacae4d9f1d76d901521e00d78603ddf703ce91974bf2d45a4501`。文档类型、学科与阶段仅可从稿件识别为多智能体预测合成测试稿，目标期刊未知。
- 编辑模式与范围：`conservative`；语言变体 `preserve`；仅第 7、11、13、17、28、36 行的文字。保留现有拼写风格；现有 `analyze` 倾向美式，但样本不足以断言统一变体。
- 授权术语表：`paper-editing-integration-fixture/full-run/terminology/terminology_glossary.yaml`；SHA-256 `e4e90df841c312e0ede2c1adf79f27c2f248af41b450bfcbb0582b1df2f9dcb0`。其中 `approved` 是测试模拟，未经真实作者批准；仅作为本次模拟保护约束，`proposed` 条目未被批准。术语交接文件 SHA-256 `87508ae05090742f7d9f4a455952e889f8a22c9d5bb9e0744c91c3b4a83aef2b`。
- 候选稿：`paper-editing-integration-fixture/full-run/language/manuscript_edited.md`；仅供审阅，所有修改均未获作者批准；审校不构成科学验证或质量认证。结构和术语提案均未应用。

## 建议与待定项目

### L01（原稿第 7 行；已写入候选稿）

- 原文：A multi-agent system (MAS) use time series forecasts to coordinate agents.
- 建议（未经作者批准）：A multi-agent system (MAS) uses time series forecasts to coordinate agents.
- 类型与理由：主谓一致；单数主语与动词一致。
- 科学含义风险：low；状态：proposed；需作者批准：是。

### L02（原稿第 11 行；已写入候选稿）

- 原文：In order to be able to make decisions at a later time, agents use forecasts that are produced before that time, and these forecasts are produced in advance of the decisions that will be made later.
- 建议（未经作者批准）：To make decisions at a later time, agents use forecasts produced before that time.
- 类型与理由：冗余和简洁性；删去重复的预测先于决策的表述，保留时间关系和目的。
- 科学含义风险：low；状态：proposed；需作者批准：是。

### L03（原稿第 13 行；延期，未写入候选稿）

- 原文：It checks whether the input is available.
- 建议（未经作者批准）：It checks whether the input is available.
- 类型与理由：指代不明；It 可能指 controller 或 monitor；input 的具体含义也未明，需作者确认，不能推断。
- 科学含义风险：high；状态：deferred；需作者批准：是。

### L04（原稿第 17 行；已写入候选稿）

- 原文：The Horizon Mapper produce a forecast from the available observations.
- 建议（未经作者批准）：The Horizon Mapper produces a forecast from the available observations.
- 类型与理由：主谓一致；单数模型名称与动词一致，不改模型名称。
- 科学含义风险：low；状态：proposed；需作者批准：是。

### L05（原稿第 28 行；延期，未写入候选稿）

- 原文：These fictional values indicate a difference in this example, but they do not establish a causal effect.
- 建议（未经作者批准）：These fictional values indicate a difference in this example, but they do not establish a causal effect.
- 类型与理由：表述含糊；差异涉及哪些对象及其依据不明确；不推断或强化因果解释。
- 科学含义风险：high；状态：deferred；需作者批准：是。

### L06（原稿第 36 行；已写入候选稿）

- 原文：The synthetic result is limited to the described example. The synthetic result is limited to the described example.
- 建议（未经作者批准）：The synthetic result is limited to the described example.
- 类型与理由：重复；删除完全重复的一句，保留原有限定。
- 科学含义风险：low；状态：proposed；需作者批准：是。

## 待作者确认与交接

- L03：由哪个组件检查 input 的可用性，input 指什么？不猜测指代或将 input 等同于 observations。
- L05：difference 比较的对象及其依据是什么？不补入解释；该行的因果限制、可能性限定语和引用保持原样。
- 术语交接中指出的四时间步与单步公式之间的关系、`f` 的含义和正文变量与代码标识的关系仍待作者核实，均超出本语言修改范围。未独立决定术语或改动公式。
- L02 简化重复的时间描述，L06 删除重复句；虽判断为低语义风险，仍需作者核对原意并批准，不能由自动检查证明语义不变。

## 保留情况与局限

仅修改许可的第 7、11、17、36 行；第 13、28 行待定而未改，其余各行逐字保留。标题、Markdown 表格、代码块、公式、引用、数字、单位、模型名称、缩写和模拟保护的术语均保留。候选稿按 JSON 记录重建；这些局部与确定性检查不能证明科学含义未变，也不能替代作者审核或证据核验。未联网；用量 unknown。
