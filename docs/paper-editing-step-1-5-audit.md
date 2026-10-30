# Paper Editing Team Step 1.5：运行时与 scientific-writing 审计

审计日期：2026-10-29。本报告记录本次观察，不将静态检查推断为运行时发现或科研质量保证。

## 角色运行时

- 当前客户端为 Codex desktop，父会话工作目录为 `/Users/hls/Desktop/dev/Free/AI4Science`；目标项目是其子目录 `Personal-AI4science-agents`，可从当前工作区读写，但不是父会话当前工作目录。命令使用显式项目工作目录不等于更改父会话启动目录。官方文档说明项目技能按当前目录到仓库根的路径发现；不能据此断言本会话自动发现子目录技能。
- 本机 CLI 报告 `codex-cli 0.163.0-alpha.10.2`；其功能列表的 multi-agent 状态是 CLI 的观察，不证明本桌面会话发现项目角色。
- 三个角色 TOML 可由 Python 3.13 `tomllib` 解析，`name` 与文件名一致，`name`、`description`、`developer_instructions` 非空，未指定模型。文件 SHA-256：
  - `paper_structure.toml`: `6e7f6813c3270e0607f81cdbd52f149a9ef58e8e555d0627e87361a178dfe441`
  - `paper_terminology.toml`: `179be2228f409d96cb87aad0163fc5b2b90a556582690389d9046b0223a1aeb1`
  - `paper_language.toml`: `4705e58b6dddb3918da575794dd58b3d1d2a5050b7b758daf2393a3bb13545fd`
- 当前会话没有可供核对的项目自定义角色发现列表；发现状态 **未验证**。可见的 `collaboration.spawn_agent` 参数为 `task_name`、`message`、`fork_turns`、`model`、`reasoning_effort`，没有选择项目角色类型或返回已加载角色配置的字段。指定角色选择在该接口 **不可用**，实际加载 **未验证**。
- 按用户条件，未执行 `paper_structure` 调用测试，未产生对应角色的调用事件。用于本次源码审计的普通子代理不是自定义 Paper Editing 角色。此限制不证明其他客户端不可用，也不阻止后续开发。
- 参考：[Codex 子代理](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[Skill 发现路径](https://learn.chatgpt.com/docs/build-skills)、[项目目录](https://learn.chatgpt.com/docs/projects)。

## 固定版本和审计范围

通过公开 Git 远端 `refs/heads/main` 的只读查询并在临时稀疏检出中核对 HEAD，固定为 [`5f2bc0341354fd5590aef76a533ada1e1e5b4e62`](https://github.com/K-Dense-AI/scientific-agent-skills/tree/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing)，Skill 自述版本 2.3。检出无工作区修改。审读同一提交的 SKILL.md、12 个 references、9 个 assets、9 个 Python 脚本和仓库根 LICENSE；未执行第三方脚本，也未逐项验证上游提及的外部政策或学术事实的时效性。

同一提交的 [LICENSE.md](https://github.com/K-Dense-AI/scientific-agent-skills/blob/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/LICENSE.md) 为 MIT，允许复制和修改，但复制或实质部分须保留原版权和许可全文。许可证不是本次停止安装的原因。

## 依赖、外传与文件行为

- 指导声明可选 CLI 需要 Python 3.11+。9 个脚本静态检查仅见标准库和 Skill 内部模块，未见网络、子进程或动态代码执行；这不保证未来版本相同，也不能证明 Codex 会话或所用模型服务在本地执行。
- 8 个任务脚本中，`scaffold_manuscript.py` 创建新目录并用独占创建方式写入七个文件；目录已存在则拒绝。失败可能残留部分目录。其他任务脚本读取本地输入并把报告输出到 stdout；报告可含标识符或其他元数据，shell 重定向不受其控制。`_common.py` 是共享辅助模块。调用脚本前仍需检查授权和输出路径。
- [`_common.py`](https://github.com/K-Dense-AI/scientific-agent-skills/blob/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing/scripts/_common.py#L37-L58) 只检查输入最终路径是否为符号链接，未将祖先路径限定在项目 workspace，且检查与读取之间存在竞态。它不是项目文件边界或独立安全沙箱。
- [`source_manifest_template.json`](https://github.com/K-Dense-AI/scientific-agent-skills/blob/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing/assets/source_manifest_template.json) 示例 `confidentiality` 默认为 `public`，而样本仍是未验证的占位来源。若被误当成真实材料分类，会造成未公开材料分类错误的风险；示例值不能构成外传授权。未发现此模板自行传输数据。
- SKILL.md 要求对受限材料外传进行授权与政策核查，并在其论文引用条件满足时建议联网核验公开文献信息。提示词不能强制网络隔离，也不能代替用户对稿件处理和引用变更的授权。其他一般模型或工具的网络行为不在脚本静态审计范围内。

## 功能判断

| 功能 | 审计观察和可复用边界 |
| --- | --- |
| Scientific Fidelity | 保留不确定性、区分相关与因果、保持方法结果一致；与项目保护科学主张的规则一致。 |
| Evidence Binding | 引导来源、主张、精确定位和人工核验；完整工作流要求证据 ID 与逐行标记，不应自动强加于现有原稿。 |
| Academic Writing | 证据大纲、章节目的、研究设计和 venue 适配的结构；IMRAD 并非普适模板。 |
| Consistency Checking | 本地一致性检查基于人工准备的 registry，不证明数字或科学事实真实。 |
| Manuscript Revision | 把编辑、科学和统计问题区分，定位受影响的主张和证据；受用户授权范围及默认不覆盖约束。 |
| Author Approval | 科学歧义、声明、投稿等由负责的作者决定；不能由代理代填批准。 |

与本项目轻量结构建议的范围存在张力：上游每条事实均要求人工验证证据绑定和逐行标记；不应把完整工作流当成 Structure 的默认前置条件。其要求在特定条件下添加论文引用及获取最新引用元数据，也须服从用户指令和实际授权，不能自动改写原稿。

## 安装和格式验证结论

按本任务“存在安全风险时停止安装”的条件，因上面的默认公开分类及路径约束缺口，未将 Skill 复制到 `.agents/skills/scientific-writing/`；目标目录不存在，未覆盖已有 Skill。以上是潜在风险，不是已发生泄漏。将来要安装，须先设计可信来源的保密分类、workspace 路径约束与受控输出，再重新审计用户允许的适配。

上游 SKILL.md 的 YAML 前置字段通过 Ruby YAML 解析，`name` 与 `description` 存在；9 个脚本通过 Python AST 解析，6 个 JSON assets 通过解析。引用的 Skill 资源路径均存在。当前 Skill Creator 快速校验工具因本环境缺少 PyYAML **未运行成功**；静态检查该工具发现其允许字段列表不包含上游的 `compatibility` 字段，因此不能声称该 Skill 已通过该工具。实际 Codex 发现、已安装文件路径及运行时外传限制均未验证：本会话技能清单没有该 Skill，且本次没有安装。静态路径存在和无网络 import 不构成运行时安全保证。
