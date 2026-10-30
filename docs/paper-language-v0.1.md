# Academic Language Agent V0.1

Codex 主控以授权稿件和术语表创建现有 `ResearchTask`／`ExecutionRequest`，优先通过 `paper_language` 原生角色执行。角色使用 [academic-language Skill](../.agents/skills/academic-language/SKILL.md)、`paper-editing` 与已安装的 `scientific-writing`；不接入其他模型 API。实际团队目录为 `teams/paper_writing/`，不存在 `teams/paper_editing/`。

## 输入、模式与边界

输入记录 `manuscript_path`、`project_id`、`editing_mode`、`language_variant`、`editing_scope`、`terminology_glossary_path`、`output_directory`，路径相对 workspace；稿件和术语表必须各自授权并记录 SHA-256。默认模式是 `conservative`，默认 `language_variant=preserve`，也可明确要求 `en-GB` 或 `en-US`。实际拼写选择仍由角色和作者判断，没有自动语言检测器。

- `proofreading`：必要的语法、拼写和标点修正，尽量保留句子结构。
- `conservative`：在纠错基础上有限度提升清晰度、简洁性和语气。
- `academic_polishing`：在不改变论据或限定关系的前提下适度改写冗长句子。

采用已确认的结构修订版本；若 Structure 仅产出未经批准的计划，继续使用授权原稿。读取 Terminology 的实际 `terms` schema，仅将有可信作者批准的条目及允许变体作为约束；`proposed` 与 `rejected` 不是批准。`approval_status` 字段本身不证明授权，术语表版本适用性由主控确认。找不到已授权且可确认的术语表时，不得虚构批准或应用依赖术语判断的编辑。

语言角色不重排章节、大规模改组段落、改变研究主张或调用其他角色；新结构／术语问题只报告主控。所有候选稿均为独立、未批准版本；可能影响科学含义的修改标高风险、暂不写入候选稿。模糊代词不猜测指代。作者最终确认前，原稿不覆盖。

## 输出、差异和验收

每个任务产生 `language_report.md`、`language_changes.json`、`manuscript_edited.md`；示例中主控还另存了 `language_diff.patch`。变更记录包括 ID、原文及改写、行范围、原文 UTF-8 SHA-256、类型、理由、语义风险、审批要求、状态和是否进入候选稿。源文件哈希和精确文本锚点绑定版本；发生行号移动后 `find_anchor_candidates` 可在另一个经授权版本查找完全匹配，零个或多个匹配均需人工解决，不自动应用或证明新版本等同。

`validate_language_run` 检查输入／术语表哈希、路径、定位、非重叠、候选稿可由已记录修改精确重建、高风险不进入候选稿，并可接收主控提供的 `allowed_line_ranges` 约束已应用的修改。要检查术语，主控须从对应授权文件安全解析 glossary 并传入 `glossary_data`；检查器不验证传入字典是否确由该文件解析，也不验证批准真实性。`render_language_diff` 生成只读统一差异，差异含原文，应同稿件一样保护。

检查器使用保守的字面匹配保护常见 Markdown 标题、围栏代码、管道表、公式、引用、数字、部分单位、限定词及原文中出现的批准术语；它不是完整 Markdown／LaTeX 解析器，可能漏报或误报，不能证明科研含义、因果关系、证据强度、保密性或真实作者批准。主控仍须逐项审阅修改、表格和保护范围；用户批准是独立步骤。已有 contracts 的路径检查不抵御并发路径替换，也不替代 OS 沙箱。长文可按授权章节调用并提供必要术语上下文；自动分块、缓存、统一调度和自动 Apply 尚未实现。原生调用没有自动接入 Python 占位适配器或 `BudgetGuard`。

## 合成稿运行记录

2026-10-29，主控分别调用 `collaboration.spawn_agent` 并选择 `agent_type=paper_language`，任务为 `language_proofreading`、`language_conservative` 和 `language_academic_polishing`；每次独立输出，均标记 `native_subagent`。调用事件证明角色选择，不证明本轮改写的完整 TOML 已被当前会话自动加载；任务明确要求角色读取新 Skill。

[合成稿](../workspace/paper-language-v0.1-fixture/manuscript.md)中所有数字、引用和结果均为虚构测试内容；[术语表](../workspace/paper-language-v0.1-fixture/terminology_glossary.yaml)的 approved 项仅模拟作者批准，**没有真实作者批准**。没有已确认的结构修订稿，本次使用用户授权的独立合成原稿。输入稿与术语表的前后哈希一致。

| 模式 | 报告 | 修改记录 | 未批准候选稿 | 主控生成差异 | 候选修改／延期问题 |
| --- | --- | --- | --- | --- | --- |
| proofreading | [报告](../workspace/paper-language-v0.1-fixture/run-proofreading/language_report.md) | [JSON](../workspace/paper-language-v0.1-fixture/run-proofreading/language_changes.json) | [稿件](../workspace/paper-language-v0.1-fixture/run-proofreading/manuscript_edited.md) | [差异](../workspace/paper-language-v0.1-fixture/run-proofreading/language_diff.patch) | 2／1 |
| conservative | [报告](../workspace/paper-language-v0.1-fixture/run-conservative/language_report.md) | [JSON](../workspace/paper-language-v0.1-fixture/run-conservative/language_changes.json) | [稿件](../workspace/paper-language-v0.1-fixture/run-conservative/manuscript_edited.md) | [差异](../workspace/paper-language-v0.1-fixture/run-conservative/language_diff.patch) | 4／2 |
| academic_polishing | [报告](../workspace/paper-language-v0.1-fixture/run-academic_polishing/language_report.md) | [JSON](../workspace/paper-language-v0.1-fixture/run-academic_polishing/language_changes.json) | [稿件](../workspace/paper-language-v0.1-fixture/run-academic_polishing/manuscript_edited.md) | [差异](../workspace/paper-language-v0.1-fixture/run-academic_polishing/language_diff.patch) | 4／2 |

各目录的 `execution_request.json`／`execution_result.json` 记录标准契约及输入和产物哈希；`language_input.json` 记录受授权行范围与模式。差异由主控独立生成，不是角色请求的三个产物之一。结果的 `quality_status=passed` 仅表示此合成样例的格式、定位、保护项及主控检查通过；`approval_status=pending`，用量 unknown。具体语义仍须作者确认。
