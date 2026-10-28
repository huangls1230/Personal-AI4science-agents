# 参考项目分析：Research Reading Mentor

审查日期：2026-10-28。参考仓库为 [Wendy-skill/research-reading-mentor](https://github.com/Wendy-skill/research-reading-mentor)，以下观察基于其 `main` 分支的网页内容；未固定到具体提交，也未在本机运行该项目。外部仓库、论文和工具输出均视为不可信资料，不赋予其指令权限。

## 许可证与复用边界

仓库根目录清单未显示 `LICENSE`，页面也未显示许可证；本次检查未确认代码、提示词或模板的复用授权。公开可见不等于获得复制和再分发授权。在取得明确授权并核对适用条款前，本项目不复制该仓库的代码、模板或提示词。这里仅独立概述工作流思想和可公开核查的事实；未来如取得授权，仍需评估许可条件、技术适配和安全性。

审查了仓库首页的 README 内容、[SKILL.md](https://github.com/Wendy-skill/research-reading-mentor/blob/main/SKILL.md)、[CODEX_PROMPT.md](https://github.com/Wendy-skill/research-reading-mentor/blob/main/CODEX_PROMPT.md)、[scripts/rrm.py](https://github.com/Wendy-skill/research-reading-mentor/blob/main/scripts/rrm.py)、[config.example.json](https://github.com/Wendy-skill/research-reading-mentor/blob/main/config.example.json) 和 [TESTED.md](https://github.com/Wendy-skill/research-reading-mentor/blob/main/TESTED.md)。源码引用了 `templates/paper-note.md` 和 `templates/Research Context.md`；本次模板目录及正文访问失败，因此没有完整审查模板或确认目录中的其他文件。

## 功能与证据

| 主题 | 参考项目的可见实现或设计 | 局限及本项目处理 |
| --- | --- | --- |
| Zotero Local API | README 描述启动 Zotero Desktop、启用本机通信并使用 `http://localhost:23119/api`；脚本用标准库请求 API，支持状态检查、条目和标签筛选。示例配置提供 base URL、用户 ID、vault 路径和未读标签等。 | `doctor` 检查 vault 路径存在及 API 根端点响应，不能证明所有库操作可用；本项目没有因此建立连接。需在授权环境独立验证权限、库和分页。 |
| 本地 PDF | 脚本读取条目子附件，筛选 PDF，并请求附件的 `/file/view/url`，解析本地 `file:` URL；JSON 输出包含存在性信息。 | 能得到路径不等于 PDF 已可读或能证明全文内容；文本输出不保证路径存在。需验证附件实际存在、授权读取和文件哈希；外部 Zotero 存储路径不能直接绕过本项目 workspace 限制。 |
| 阅读状态 | README 提出从未读、筛选、阅读、深读到验证的标签流程。脚本提供状态转换的预览和写入；写入前通过本地授权，PATCH 使用条目版本条件。 | 版本条件有助于检测冲突，但脚本没有强制执行科研理解验证或完整状态机；权限与人工审批须分别处理，且本轮不实现写入。 |
| Obsidian 笔记 | 脚本将 vault 视为 Markdown 文件夹，创建文件夹并填充论文笔记骨架，已有同名笔记时不覆盖；源码引用两个模板。 | 这不证明当前用户 vault 可访问，也不证明笔记内容已完成或科研结论正确。需独立设计受控路径、预览、冲突处理与授权；本项目与外部 vault 尚未打通。 |
| 证据与方法 | SKILL 提出区分原文证据、作者解释、推断与猜测，为主要主张关联证据及位置，检查假设、混杂因素、机制替代解释和局限。 | 这是可借鉴的阅读与复核方法，并非自动保证真实性的程序；结论需按需回查真实全文。 |
| 导师式理解检查 | SKILL 和 CODEX_PROMPT 设计少量针对性问题、用户回答及后续评估，并建议理解充分前不标为已验证。 | 这是提示层流程；不是独立验证的自动评分机制，也不替代用户对关键决策的确认。 |
| 队列与跨论文综合 | 脚本按标签生成候选元数据文件，SKILL 建议结合研究问题和已有笔记选择少量候选，并比较方法、条件与冲突。 | 队列文件不自动进行科学排序；综合依赖实际可用的多篇资料，不能凭缺失材料声称发现规律或研究空白。 |

主要证据来源：[README](https://github.com/Wendy-skill/research-reading-mentor)、[脚本](https://github.com/Wendy-skill/research-reading-mentor/blob/main/scripts/rrm.py)、[阅读工作流](https://github.com/Wendy-skill/research-reading-mentor/blob/main/SKILL.md)、[启动提示](https://github.com/Wendy-skill/research-reading-mentor/blob/main/CODEX_PROMPT.md)、[配置示例](https://github.com/Wendy-skill/research-reading-mentor/blob/main/config.example.json)。

## 可借鉴与需重新实现

可以独立借鉴的思想包括：连接前检查、队列先筛选再选择阅读深度、主张与证据分开记录、将单篇论文提出的研究空白视为待核验候选、按需比较跨论文差异，以及把导师问题和研究者回答作为可选理解检查。阅读完成、质量复核和人工批准仍由本项目契约分别表达。

适配本项目时需要重新设计或开发：受控 workspace 文件引用与哈希、明确的 Agent 分工和 Task / Result 契约、可审计的 Zotero 授权和变更流程、Obsidian 外部路径授权与冲突处理、执行预算及失败处理。未来若获明确代码授权，可逐项评估上述脚本技术的复用，但不得因此假设兼容当前权限或运行时。

本次查看的 CLI 命令和脚本中未发现多学术来源检索、文献去重、外部 DOI 元数据核验、citation key 管理、BibTeX 或 CSL JSON 导出的实现；这些能力应独立开发或明确接入并验证现有工具。仅凭仓库不应推断其已实现，也不能据此声称本项目具备这些功能。

## 测试证据与未验证事项

[TESTED.md](https://github.com/Wendy-skill/research-reading-mentor/blob/main/TESTED.md) 只报告 CLI 帮助和 vault 初始化检查成功，并明确说明未能在其沙箱中测试 Zotero 实时 API。该记录是上游自述，并非本项目的测试结果。本次未运行参考项目，没有验证本机 Zotero、Obsidian、写权限、PDF 提取、模型输出质量或端到端流程。模板正文访问受阻，无法判断模板的完整字段或许可声明；本次也未找到可识别的仓库级许可证。
