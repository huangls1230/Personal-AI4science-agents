# Paper Editing Team Step 1.5：当前运行时验证与 Skill 审计

日期：2026-10-29。此记录对应本次 Codex desktop 会话；先前同目录的 Step 1.5 审计记录描述的是不同会话，不应作为本次运行时事实。

## 自定义角色

- 当前工作目录和 `git rev-parse --show-toplevel` 均为 `/Users/hls/Desktop/dev/Free/AI4Science/Personal-AI4science-agents`。本机 CLI 显示 `codex-cli 0.163.0-alpha.10.2`；这不证明 desktop 内部组件版本相同。
- Python `tomllib` 成功解析下列文件，名称与文件名一致，`name`、`description` 和 `developer_instructions` 均非空。语法及字段检查不证明完整配置已被执行器加载。

| 角色 | 文件 SHA-256 | 当前会话发现 |
| --- | --- | --- |
| paper_structure | `6e7f6813c3270e0607f81cdbd52f149a9ef58e8e555d0627e87361a178dfe441` | 是 |
| paper_terminology | `179be2228f409d96cb87aad0163fc5b2b90a556582690389d9046b0223a1aeb1` | 是 |
| paper_language | `4705e58b6dddb3918da575794dd58b3d1d2a5050b7b758daf2393a3bb13545fd` | 是 |

当前 `collaboration.spawn_agent` 工具声明的 `agent_type` 枚举包含三个角色及其说明，支持选择自定义角色。测试调用事件使用 `agent_type: paper_structure`、`task_name: structure_readonly_test`、`fork_turns: none`，要求只读论文编辑组 README；工具返回任务 `/root/structure_readonly_test`。第一次调用因并发槽位已满而失败；释放槽位后，该次角色选择成功创建并完成。子代理返回结构、术语、语言三项职责及不覆盖原稿的边界；主控对照 [团队 README](../teams/paper_writing/README.md) 核实一致。本次没有要求其他两个角色执行测试。

工具事件证明选择并运行了该角色，但接口没有暴露已解析的完整 `developer_instructions`、配置来源或哈希，不能证明每一条磁盘指令都被加载。角色列举和成功调用也不构成权限隔离或科研质量保证。官方参考：[子代理](https://learn.chatgpt.com/docs/agent-configuration/subagents)。

## 上游版本和许可

审计 [scientific-writing](https://github.com/K-Dense-AI/scientific-agent-skills/tree/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing)，固定提交 `5f2bc0341354fd5590aef76a533ada1e1e5b4e62`，Skill 自述版本 2.3。核对已有临时 Git 检出：HEAD 等于该 SHA，工作区无修改；固定提交页面和文件也可通过 GitHub 查看。审计范围包括 SKILL.md、12 个 references、9 个 assets 和 9 个 Python 文件；未运行第三方脚本，也未逐项核验参考材料中的学术政策和事实。

同一提交的 [根 LICENSE.md](https://github.com/K-Dense-AI/scientific-agent-skills/blob/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/LICENSE.md) 是 MIT，Copyright 2025 K-Dense Inc.，允许复制和修改，分发副本或实质部分时须保留版权和许可全文。许可本身不阻止安装。

## 安全、依赖和格式

- [SKILL.md](https://github.com/K-Dense-AI/scientific-agent-skills/blob/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing/SKILL.md) 要求未经授权不向外部服务发送受限材料，并要求科学决策由人负责；这是工作流指令，不是网络隔离或权限控制。其末尾另要求在特定条件下增加上游论文引用并联网核验元数据；这不是 MIT 许可条件，不能越过项目的引用核验和用户授权要求。
- 可选 CLI 声明需 Python 3.11+；静态检查九个脚本的 imports，仅见标准库及同目录模块，未发现网络、子进程或动态执行调用。该检查不代表实际运行时、其他工具或模型服务具有网络隔离。未执行脚本。
- `scaffold_manuscript.py` 在指定的新目录生成七个文件，使用排他创建避免覆盖；失败可能留下部分目录。其余工具读取本地输入并将报告写到 stdout，报告和重定向仍可能泄露元数据。
- [来源模板](https://github.com/K-Dense-AI/scientific-agent-skills/blob/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing/assets/source_manifest_template.json) 将 `confidentiality` 默认设为 `public`，而来源仍是未验证占位符；误用可能把未公开材料分类为公开。[文件检查辅助函数](https://github.com/K-Dense-AI/scientific-agent-skills/blob/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing/scripts/_common.py) 不把输入约束在项目 workspace，仅检查最终路径是否为符号链接，检查和读取之间还有竞态。它不是安全沙箱。这些是潜在风险，并非已发生外传。
- SKILL.md YAML 前置元数据可解析，含 name 与 description；文中 29 个 `assets/`、`references/` 和 `scripts/` 文件路径均存在，九个脚本通过 Python AST 解析，六个 JSON 资产通过解析。Skill Creator 的 `quick_validate.py` 因缺少 PyYAML 无法运行；其当前允许键列表也不含上游的 `compatibility`，所以不能声称通过该校验器，更不能将 YAML 可解析等同 Codex 运行时接受。

按本任务“存在安全风险则停止安装”的条件，**未安装**，目标 `.agents/skills/scientific-writing/` 不存在，未覆盖任何 Skill。当前会话 Skill 列表没有它，安装后的发现、资源路径及运行时外传控制均无法验证。日后重新审计时应明确可信保密分类、文件路径约束与受控输出，再评估适配；不应将提示词当作强制控制。

## 可复用功能与边界

| 功能 | 适用判断 |
| --- | --- |
| Scientific Fidelity | 可借鉴保留不确定性、避免将相关改成因果、保持方法与结果一致。 |
| Evidence Binding | 可借鉴主张到来源和具体位置的追溯，人工核验；完整的逐行标记和注册表不应强加于轻量结构审阅。 |
| Academic Writing | 可借鉴章节目的、证据大纲和读者导向；IMRAD 仅在研究类型和期刊适合时使用。 |
| Consistency Checking | 可借鉴跨章节与方法结果的一致性问题清单；本地注册表检查不能证明科学事实正确。 |
| Manuscript Revision | 可借鉴将编辑、科学和统计问题分开并定位受影响内容；原稿和作者意图受现有工作流约束。 |
| Author Approval | 科学歧义、可能改变含义的结构调整以及最终稿交由负责的作者决定，不由代理代替批准。 |

下一阶段 Structure Agent 可在现有授权材料中提出章节、段落和论证链建议，标明位置、理由、可能涉及的证据缺口及需作者裁决的含义风险；不自行补充论据、不重写术语或语言，不要求先安装此 Skill。
