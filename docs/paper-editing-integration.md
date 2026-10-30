# AI Paper Editing Team 集成 V0.1

Codex 是唯一主控。[paper-editing-workflow Skill](../.agents/skills/paper-editing-workflow/SKILL.md) 路由已存在的 `paper_structure`、`paper_terminology` 和 `paper_language`，不建立新的模型运行时或外部 Harness。当前实际团队目录是 `teams/paper_writing/`，不是 `teams/paper_editing/`。

## 启动

用户可在本项目中请求使用 `$paper-editing-workflow`，提供 `project_id`、workspace 内 Markdown 稿件、目标语言、编辑范围和输出目录；完整或语言任务还需要有授权、适用于该版本且已由负责作者确认的术语表。编辑模式默认 conservative。主控按目标选择 `structure`、`terminology`、`language` 或 `full`；完整任务顺序为 Structure → Terminology → Language → Final Validation。角色不可用时允许由 Codex 内联执行相应 Skill，记录 `inline_skill`，不得冒充原生角色。

结构和术语审查默认产生提案，不改稿。未实际批准和应用的结构方案不传递为修订稿；后续使用原稿。术语表的 `approved` 字段本身不是批准证据；缺少可信批准或术语表时停止依赖它的语言阶段并报告，而不是自动承认提案。语言候选稿是未获批准的独立版本。

## 状态和版本

`ai4science.paper_editing_workflow` 提供确定性路由、按输入和任务配置派生的运行目录、版本清单、串行阶段状态、源／输出哈希核对、失败中止、显式有限重试与重复请求复用。主控仍负责调用角色、核验其结果与审批；该模块不调度模型、不验证真实工具调用事件、也不批准修改。重复运行只在同一输出目录、相同输入和配置下复用，并核验先前产物；调用方在 Skill、角色或环境变化时必须改变项目任务配置后重新评估，缓存不证明语义或模型等价。

运行目录中的阶段各自拥有独立子目录；重试必须使用新的 `attempt-N` 子目录，不覆盖前一尝试。`max_retries` 限 0–3，显式失败后才能重排失败阶段。处理前和交接时比对输入和已记录产物哈希；冲突终止，不合并。版本记录包含 artifact_id、来源 ID 和哈希、输出哈希、阶段、执行器、批准状态和时间。该文件级检查不防并发路径替换或恶意并发写入，权限和隔离依靠实际 Codex 沙箱；只允许单一主控写清单。

`approved_changes_only` 接收主控从可信作者决定得到的批准 ID，绝不相信模型在产物中自行填写的批准状态。用户未批准语言修改前，只生成 `awaiting_author_approval` 预览；即使格式检查成功，批准关卡仍未通过。没有自动论文提交、原稿覆盖、自动语义证明或通用 Apply 引擎。

## 最终检查

主控复用三个角色的结构化校验器；对语言候选稿使用 `validate_language_run` 检查可追溯重建及常见 Markdown、引用、数字、单位、公式、限定词和批准术语。模型输出与用户源均是不可信输入。确定性检查不能保证科研主张、条件、关联与因果、推断强度或所有格式都没变化；这些由主控逐项语义审阅，并将未决项交作者。审批、源版本、质量和执行状态分开记录。角色使用量不可获得时为 unknown；项目当前没有对原生会话强制 token 或费用上限的机制。

## 当前执行路径

本阶段示例是 Codex 主控以三个真实角色调用依次生成产物并手工执行交接和校验；独立状态辅助模块的路由、冲突、失败和去重以单元测试验证。它没有将原生 `spawn_agent` 接入 Python，也没有实现全自动任务队列、跨进程锁或持久审批服务；不要把辅助函数视为生产调度器。
