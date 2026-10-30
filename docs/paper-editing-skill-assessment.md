# 论文编辑 Skill 初步评估

核查日期：2026-10-29。来源为 [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) 的网页 `main`；网页缓存可能不一致，未能取得可核实的当前 Git commit，以下版本为各 SKILL.md 所声明的版本，不能视作固定快照。Git clone 在本环境因 DNS 失败；仓库 API 也未能访问。

| Skill／声明版本 | 功能与适用角色 | 依赖、外部服务和许可 | 复用、冲突与建议 |
| --- | --- | --- | --- |
| [scientific-writing](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-writing/SKILL.md) 2.3 | 学术写作与结构；主要给 structure 参考，language 可参考写作表达 | 声明 MIT；可选本地脚本需 Python 3.11+；SKILL 声明离线、无需 API key；完整脚本及依赖未审计 | 与现有 academic-research-suite 的写作指导有范围重叠，尚未发现已证实的指令冲突。本轮仅参考其职责方向；优先作为将来统一写作 Skill 的候选，但暂不复制、安装或运行，待逐文件与许可审计。项目新建的 `paper-editing` 是独立编写的最小约束，不是该 Skill 的安装。 |
| [scientific-critical-thinking](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-critical-thinking/SKILL.md) 1.5 | 批判性论证检查；structure 可借鉴识别论证缺口 | 声明 MIT，核心无需网络；可选 scientific-schematics 涉及 OpenRouter API；全部依赖与传输路径未审计 | 与 academic-research-suite 的 review 和 critical review 角色有功能重叠，尚未确认具体指令冲突。此次只借鉴问题定位，不安装，避免扩大为同行评审或触发外部服务。 |
| [markdown-mermaid-writing](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/markdown-mermaid-writing/SKILL.md) 1.3 | Markdown 与 Mermaid 写作；结构图可供 structure 按需参考 | 声明 Apache-2.0；渲染涉及 Node 22.13+、Mermaid CLI 12 与 Chromium，安装可能联网；该声明与仓库根 MIT 的适用关系未核实 | 可与项目 Markdown 输出及可视化工具功能重叠，未发现已证实的指令冲突。当前不需要绘图，且许可适用范围和依赖未核实，暂不安装。 |
| [venue-templates](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/venue-templates/SKILL.md) 1.6 | 会议／期刊格式模板；可供 structure 与 language 在明确投稿要求时参考 | 声明 MIT；脚本需 Python 3.11+，可选 LaTeX、Poppler；核查 venue 现行规则可能需要联网；脚本审计未完成 | 与现有 academic-research-suite 的格式指导可能重叠。已发现脚本输出可能覆盖已有文件，与默认保护原稿的规则有操作冲突；目标 venue 和规则时效需独立核实。本轮不安装或运行。 |

## 证据与未完成范围

- 四个 SKILL.md 均访问了元数据和部分主体；网页响应截断，不能声称逐篇完整阅读。
- 访问了四个 references 目录列表，抽查了 writing 的 `imrad_structure.md`、`writing_principles.md`，critical-thinking 的 `core_capabilities.md`，markdown-mermaid 的 `markdown_style_guide.md`，venue 的 `ml_conference_style.md`；可见内容仅为页面开头，不能声称完整读过。其余 reference 未逐一阅读。
- 查看了 scientific-writing 的九个脚本的前约 45–90 行，未完成源码审计。venue 的 `customize_template.py` 和 `query_template.py` 可见全部源码，`validate_format.py` 读取了前 291／323 行；不同时刻的网页缓存未必是同一快照，不构成完整安全审计。[customize_template.py](https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/main/skills/venue-templates/scripts/customize_template.py) 使用写入模式打开输出路径，[validate_format.py](https://raw.githubusercontent.com/K-Dense-AI/scientific-agent-skills/main/skills/venue-templates/scripts/validate_format.py) 的报告写入也可能覆盖现有文件，不能未经防覆盖适配直接采用。`query_template.py` 中存在日期化的 venue 资料，使用时仍需验证时效。另两个 Skill 的目录网页未显示 scripts，但缓存列表不能证明某个固定版本没有 scripts。未运行第三方脚本。
- 四个 Skill 顶层目录页面未显示单独 LICENSE；已阅读仓库根 [LICENSE.md](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/LICENSE.md)，内容为 MIT、版权 © 2025 K-Dense。各 Skill 自身许可声明及其与根许可的关系需要以固定快照再次核实；尤其是 markdown-mermaid 的 Apache-2.0 声明不应自动等同于根 MIT。
- 由于缺少固定 commit、完整文件阅读和脚本审计，上表的依赖、外部传输与冲突结论均是初步的，不是安全认证。要直接复用，先取得固定提交、逐项审阅完整文件及许可证、核实依赖与传输，再按适用许可保留声明；禁止未经确认运行来源不明的安装脚本。
