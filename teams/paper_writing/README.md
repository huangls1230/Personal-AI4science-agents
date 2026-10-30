# AI Paper Editing Team

Codex 主控接收作者任务、分配独占输出、协调意见并交作者决策；团队不是独立管理 Agent。角色配置位于 `.codex/agents/`，不指定模型，实际权限和可用性由父会话决定。

| 角色 | 职责 | 边界 |
| --- | --- | --- |
| `paper_structure` | 宏观结构、章节和段落顺序、论证链，提供定位明确的调整建议 | 不做术语统一或逐句润色；不自行补充论据 |
| `paper_terminology` | 术语、缩写、变量名称和专业表述的一致性，提供术语表及有定位的建议 | 不重排结构或润色句子；变量和公式相关变更标记待作者确认 |
| `paper_language` | 语法、学术语气、简洁性与可读性，提供局部语言建议 | 不改变结构、术语决策或科学主张；有语义风险时停止自动改写并标记 |

共享指导为 [paper-editing](../../.agents/skills/paper-editing/SKILL.md)，主控路由使用 [paper-editing-workflow](../../.agents/skills/paper-editing-workflow/SKILL.md)，结构审查使用 [paper-structure](../../.agents/skills/paper-structure/SKILL.md)，术语审查使用 [academic-terminology](../../.agents/skills/academic-terminology/SKILL.md)，语言审查使用 [academic-language](../../.agents/skills/academic-language/SKILL.md)；调度、证据和输出约定见 [工作流](../../workflows/paper-editing.md)。三个 V0.1 角色可通过 Codex 原生角色生成独立建议或候选稿，另有确定性格式和定位检查；语义判断与科研核验仍由主控和作者负责。该组没有自动变更合并或自动科研验收功能。用户确认前，建议和草稿不覆盖原稿。角色文件不提供独立沙箱，也不保证已被当前会话发现或调用。
