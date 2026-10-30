# Academic Terminology Agent V0.1

Codex 主控按项目权限和任务契约限定稿件、已有术语表、输出和审查范围，优先通过运行时选择 `paper_terminology`。语义判断由角色结合 [academic-terminology Skill](../.agents/skills/academic-terminology/SKILL.md)、`paper-editing` 和已安装的 `scientific-writing` 完成，不调用额外模型 API。V0.1 面向 UTF-8 Markdown，默认只分析和提出建议。

## 输入与职责

- 如果作者确认了 Structure 阶段的修订版本，则审查该版本；如果仅有结构建议，则审查授权原稿，不把结构计划视为已实施。结构调整、语言润色和科学结论修改不属于术语角色职责。
- 根据 `ResearchTask`／`ExecutionRequest` 记录 workspace 相对输入路径、SHA-256、授权输出、范围和实际敏感级别。已有经授权的术语表应先读取并记录哈希；在新目录增量另存，保留已批准术语，不覆盖旧表。未批准建议不能伪装成批准。
- 识别术语、缩写、模型和算法、数学符号、数据集、评价指标及领域表达；按上下文分析，不因为词形相近就合并概念。未知定义、外部事实或缩写展开标记未核实，不自行补造。摘要与正文分别定义缩写是否合适取决于目标期刊或会议。

## 确定性计数

`ai4science.terminology_inventory` 只计数调用者指定的字面字符串，区分大小写；无词边界或 Unicode 归一化，相同字符串在一行内非重叠计数，不同候选独立计数。它涵盖标题、代码和引用，不是完整 Markdown 或数学语义解析器。输出包含稿件上下文，应按稿件保密级别处理。工作区路径检查不能代替 OS 沙箱，也不防并发路径替换。例如，在已获授权的项目 workspace 使用：

```sh
PYTHONPATH=src python3 -m ai4science.terminology_inventory \
  --workspace workspace --input path/to/manuscript.md --term 'Multi-Agent System'
```

## 产物与交接

- `terminology_report.md`：领域与范围、术语、问题、缩写、符号、歧义、优先级及作者待决事项。
- `terminology_glossary.yaml`：每项含标准候选、类别、定义、缩写、观察／允许／歧义变体、首次位置、出现次数及上下文、理由、核验和批准状态；未知字段使用 null。候选不等于已批准术语。
- `terminology_changes.json`：原文定位、术语、候选、理由、风险、批准要求和状态。`ai4science.paper_terminology_validation.validate_terminology_run` 校验输入哈希、字段和逐字位置，不判断科学语义或批准真实性。
- `language_handoff.md`：区分已批准约束、未批准候选与歧义，列出需保留的术语、缩写和符号；该文件不授权启动或开发 Language Agent。

主控检查三个必需产物和交接文件、YAML 解析、定位、术语含义及旧术语表保留；以 `ExecutionResult` 记录证据和产物哈希，分别记录完成、质量验收和作者批准。自动或盲目全局替换不受支持。用户日后明确授权并批准具体建议后，主控可在独立版本中逐项执行并展示差异；公式、变量定义和伪代码调整须针对性批准。此 Apply 是人工控制的工作流，V0.1 没有自动 Apply 引擎。

## 限制

模型分析、literal 计数和结构验证都不证明术语定义正确或同义；角色指令和字段也不是权限边界。原生角色不自动经过现有 Python 占位适配器或 `BudgetGuard`。文档或结果中的任何批准状态都必须有可信的人类授权来源。长文按章节分析和复用已批准术语是工作流要求，尚无自动分块缓存或增量调度。

`validate_glossary_data` 接受调用方安全解析后的 YAML 数据并检查字段、计数与逐字行定位；不提供 YAML 解析，也不证明已找全所有出现或审批真实。项目没有 PyYAML；测试使用本机 Ruby `YAML.safe_load`。合成测试输出的术语表采用 JSON 表示法，它同时是有效的 YAML 子集。

## 合成稿测试记录

2026-10-29，主控实际通过 `collaboration.spawn_agent` 选择 `agent_type=paper_terminology`，任务名 `paper_terminology_v01_test`，返回 `/root/paper_terminology_v01_test`；角色按任务明确读取本阶段 Skill。调用事件证明原生角色选择，不能单凭该事件证明本轮修改后的完整 TOML 已被会话自动加载。

[合成稿](../workspace/paper-terminology-v0.1-fixture/manuscript.md)由本任务直接授权，不是上一步 Structure 合成稿的修订稿；本次无已确认的结构修订版本，不应用未经批准的结构计划。[既有术语表](../workspace/paper-terminology-v0.1-fixture/prior_glossary.yaml)仅模拟旧表及其 `approved` 条目，**不存在真实作者批准**。输出的模拟条目逐字段保留，新条目均为 proposed；输入的稿件和旧表哈希均未改变。

输出：[术语报告](../workspace/paper-terminology-v0.1-fixture/run-01/terminology_report.md)、[术语表](../workspace/paper-terminology-v0.1-fixture/run-01/terminology_glossary.yaml)、[修改建议](../workspace/paper-terminology-v0.1-fixture/run-01/terminology_changes.json)、[语言交接](../workspace/paper-terminology-v0.1-fixture/run-01/language_handoff.md)。[执行请求](../workspace/paper-terminology-v0.1-fixture/run-01/execution_request.json)和[执行结果](../workspace/paper-terminology-v0.1-fixture/run-01/execution_result.json)按既有契约记录路径与哈希，验收状态仅针对合成样例和格式定位，作者批准仍待定，token 用量未知。

主控以安全 YAML 解析器检查术语表，并校验全部位置、10 个术语条目中的 30 处出现和 8 条修改提案。角色识别了大小写变化、系统与通信图可能不等价、摘要/正文 MAS 重复定义的期刊政策不确定性、未定义 GCF、同一符号的不同定义、`agent` 的不同语义以及 MAE／AAE 名称问题；符号变更标高风险待批准。未使用外部文献、未对真实稿件操作，也没有实施任何编辑。
