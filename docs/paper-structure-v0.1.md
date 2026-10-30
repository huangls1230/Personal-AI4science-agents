# Paper Structure Agent V0.1

Codex 主控接收授权范围，优先通过当前运行时的 `paper_structure` 自定义角色执行 Markdown 稿件的结构审查。角色读取 [paper-structure Skill](../.agents/skills/paper-structure/SKILL.md)，结合现有 `paper-editing` 和 `scientific-writing` 指导进行语义判断；本项目的 Python 校验器只做确定性验收，不执行论文分析，不连接其他模型 API。

## 调用与输入

1. 主控指定 workspace 内授权的 UTF-8 Markdown 稿件、审阅范围、论文类型和目标期刊（未知时标未知）。按照项目契约建立 `ResearchTask`、`ExecutionRequest`，使用 `create_artifact` 记录 workspace 相对路径及 SHA-256；明确敏感级别，不把未知材料默认为公开。
2. 预留独占输出目录和三个不与原稿重合的文件，验证其路径。通过可用的 Codex Native 调用接口选择 `agent_type=paper_structure`，请求其读取 Skill、模板与指定稿件。新建配置是否在某个会话中加载，以实际会话证据为准；角色不可用时可由主控按同一 Skill 内联执行，真实标注 `inline`。
3. Agent 检查适合论文类型的宏观结构、六阶段论证链及每个范围内正文段落的六个维度，并生成三份建议产物。对缺失证据只向作者提出问题；不推断整个领域的研究空白，不改写原稿。

## 输出与验收

`structure_report.md` 汇总宏观问题、逐段评估和逐条建议；`argument_map.md` 记录问题、空白、目标、方法、证据、结论的文本位置及关联；`restructuring_plan.json` 以机器可读字段给出每条建议的位置、逐字原文锚点、问题、动作、建议、理由、优先级和科学含义风险。三个模板位于 [templates/paper-editing](../templates/paper-editing/)。段落动作是 `keep`、`move`、`merge`、`split` 或 `add_argument`；最后一项是要求作者补充或核实论证，不是授权编造证据。

主控可调用 `ai4science.paper_structure_validation.validate_structure_run(workspace_root, input_path, plan_path)`；三个路径参数中的后两者必须相对 workspace。它检查 JSON、输入哈希、必填字段、行动/优先级、逐字锚点及风险对应批准标记。还须人工检查三个输出的完整性、逐段覆盖、论证判断和跨文件一致性，并核对输入哈希未改变。调用结果、证据与产物哈希记录到现有 `ExecutionResult`；`completed`、质量检查和作者批准互相独立，未知用量保持 unknown。大量重排或可能改变科学含义的建议须先交作者确认。

## 限制

语义判断由 Codex 原生角色完成，结构建议并非证据核验或事实证明。V0.1 不自动重排 Markdown，不支持 DOCX 或 LaTeX 自动重排，也没有将原生调用接入项目的占位适配器或 `BudgetGuard`。workspace 路径检查不能替代操作系统沙箱和真实工具权限，也不能防御并发路径替换。

## 合成稿测试记录

2026-10-29，主控通过当前会话的 `collaboration.spawn_agent` 实际调用 `agent_type=paper_structure`，任务名为 `paper_structure_v01_test`，返回 `/root/paper_structure_v01_test`；要求其显式读取结构 Skill 和授权合成稿件，执行方式记录为 `native_subagent`。该调用事件证明角色选择，不能单凭本次结果证明本轮修改后的完整 TOML 指令已由运行时自动加载。

输入是 [合成稿](../workspace/paper-structure-v0.1-fixture/manuscript.md)，由任务契约记录的 SHA-256 为 `d492389a525752fc3b5aa0dc3e42dac3f92d69be71c87c2a02d6d8c458480845`；复核后的原稿哈希相同。[执行请求](../workspace/paper-structure-v0.1-fixture/run-01/execution_request.json)和[执行结果](../workspace/paper-structure-v0.1-fixture/run-01/execution_result.json)使用现有契约；结果的 `quality_status=passed` 仅指主控对合成测试的格式、定位、覆盖与预期问题检查通过，`approval_status=pending`，不能解读为科研事实或建议已被作者认可。

输出：[结构报告](../workspace/paper-structure-v0.1-fixture/run-01/structure_report.md)、[论证图](../workspace/paper-structure-v0.1-fixture/run-01/argument_map.md)、[重组建议](../workspace/paper-structure-v0.1-fixture/run-01/restructuring_plan.json)。主控检查了 12 个段落、六阶段论证链以及全部 12 条建议的逐字原文定位；报告指出引言动机和比较依据不足、相关工作脱节、方法未具体化、第 25 和 27 行重复、目标与第 31 行评估不符、结论超出稿内支持，并保留第 35 行的测量局限。未使用外部文献或真实实验材料。
