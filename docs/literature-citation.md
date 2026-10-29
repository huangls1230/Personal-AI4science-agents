# Literature Citation：只读工具与边界

Codex 是主控；`literature_citation` 是角色，`zotero-citation` 是按需加载的 Skill，`citation_cli` 和相关 Python 模块是确定性工具，不是新的 Agent 循环。角色配置不绑定模型；现有 Router、预算策略与模型适配器不因本模块而改变。项目级角色文件通过了 TOML 静态解析，但本次实际委派尝试中可用的 spawn 接口不能选择该自定义类型，角色发现和真正的角色调用均未验证。

## 配置与调用

在项目根目录运行，Python 3.11+，无需额外安装依赖；若系统的 `python3` 版本不足，请使用已安装的 Python 3.11+ 解释器。先启动 Zotero Desktop 并启用 Local API；工具只连接本机 `127.0.0.1:23119`，不接受调用方指定服务器、URL 或代理。实际环境必须允许访问本机端口。各命令输出 CitationResult JSON；路径均相对于现有项目 `workspace/`，输出文件必须是新文件且父目录已存在。

```sh
PYTHONPATH=src python3 -m ai4science.citation_cli --task-id citation-doctor doctor
PYTHONPATH=src python3 -m ai4science.citation_cli --task-id citation-list list --limit 10 --start 0
PYTHONPATH=src python3 -m ai4science.citation_cli --task-id citation-get get --item-key X9XPICKZ --attachments
PYTHONPATH=src python3 -m ai4science.citation_cli --task-id citation-verify verify --item-key X9XPICKZ --allow-network
PYTHONPATH=src python3 -m ai4science.citation_cli --task-id citation-export export --item-key X9XPICKZ --format bibtex --output runs/example/reference.bib
PYTHONPATH=src python3 -m ai4science.citation_cli --task-id citation-state status-plan --item-key X9XPICKZ --target research-reading
PYTHONPATH=src python3 -m ai4science.citation_cli --task-id citation-bbt bbt --item-key X9XPICKZ
```

以上 Item Key 仅是本机实际测试样例，其他馆藏未必存在；先在 workspace 创建单独输出目录。主控可在支持选择项目自定义 agent 的运行时委派 `literature_citation`，提供最小任务、范围与输出路径；如当前运行时不支持指定类型，主控仍可直接调用 CLI，不得声称子代理已运行。`--library` 和 `--kind` 选择本机 Local API 的用户或群组库；`users/0` 不是 Better BibTeX 的内部数值 library ID。群组的 BBT 查询须显式提供其内部 ID。

`list`、`search` 有边界与分页；默认搜索标题、作者和年份，`everything` 必须显式选择。Python 客户端另提供 collection、tag 和附件元数据查询；不下载附件。`plan-import` 对 Search JSON 中指定条目进行有界标题检索并输出导入建议，未找到匹配不证明唯一，也不会导入。`compare` 比较两条 CitationRecord。`link` 校验 ReadingResult、阅读卡片文件与哈希并生成 workspace 映射，不更改阅读分析或已有笔记。

## 核验、重复和导出

`verify` 默认不访问外部网络；`--allow-network` 才把 DOI 发给 Crossref。工具复用 Search 的 Crossref 能力，逐字段记录匹配、冲突或未知，明确区分 verified、partially_verified、unverified、conflict。Crossref 有结果不代表 DOI 解析器已被独立验证，也不证明科学结论正确；缺失字段保持未知。相同完整实例／馆藏／Item Key 或规范 DOI 可识别精确匹配；预印本与正式发表版本保守标为 related_version，标题、作者、年份联合匹配仅作为 probable_duplicate；其他情况报告 distinct 或 uncertain。不会自动删除、合并或修改条目。

`export` 接受多个 `--item-key`，调用 Zotero 原生 BibTeX、BibLaTeX、CSL JSON 或 CSL bibliography 输出；支持 `apa`、`ieee`、`chicago` 和 `gbt7714`。真实环境中这些格式均有返回；指定不存在的样式时，该 Zotero 返回 HTTP 400。不同安装的样式可用性可能不同，不能把本次测试推广到所有机器。BibTeX、BibLaTeX 和 CSL JSON 检查条目数量，但不验证每条导出与请求的具体 Item Key 对应；格式化 HTML 的数量和身份也未逐项检查，跨请求实例检查不是原子事务。导出内容由 Zotero 提供，HTML 是不可信内容，使用前需在下游安全处理；不应当把语法和 CSL 合规性推断为已独立验证。输出文件的 SHA-256 证明内容一致性，不能证明来源或格式正确。原生 BibTeX 导出键不是已验证的 Better BibTeX 稳定键。

BBT 只使用其官方 JSON-RPC 的只读能力；未安装或不可用返回 blocked，citation key 保持 null，不重新生成。特定 key 反查及 BBT 可用实例的端到端功能尚未验证。

## 阅读状态、关联和权限

状态工具识别 `research-unread`、`research-screened`、`research-reading`、`research-deepread`、`research-reread` 和 `research-verified`，生成版本、旧标签与目标变化的 dry-run，保留其他用户标签。`research-verified` 需要明确确认用户理解；一个 CLI 标志只记录调用方声明，并非独立证明。`apply_status_transition` 和所有 Zotero 写入始终 blocked，即使已有批准；目前没有申请 API key、执行授权、调用写入端点或记录真实变更。版本冲突路径仅做模拟测试，真实并发写入未测试。[Zotero 10 Local API](https://www.zotero.org/support/dev/web_api/v3/local_api) 支持授权写入并不等于用户允许任何特定操作，未来需要分别实现并审查两层授权、服务端身份、版本前置条件、凭据保护和审计。

Citation 的关联记录使用馆藏类型、library ID、Item Key、可取得的 server ID、DOI、Markdown 阅读笔记和文件哈希；缺失服务器身份时不声称完整的全局身份。ReadingResult 本身不能证明笔记来自哪个库，关联始终标记为需要人工复核。关联限于项目内部，不连接 Obsidian，也不解析或修改外部笔记；用户可自行将 Markdown 导入 Obsidian。Reading CLI 的 Zotero 读取桥接尚未接入。

外部数据、论文、HTML 和 Agent 结果视为不可信数据。受控路径和服务端限制不能替代操作系统隔离；调用前主控应检查权限及敏感数据外传。CLI 的 token 与成本保持 unknown，现有项目 BudgetGuard 不自动约束此 CLI 或 Codex 内部消耗。

## 实测记录

2026-10-28，本机 Zotero 10.0.6 Local API v3 可访问 `users/0`；本沙箱内 localhost 被拒，实测经允许的外部进程进行。读取 Item Key `X9XPICKZ`，对应 Dan Sun 等，2024，*Investigating students' programming behaviors, interaction qualities and perceptions through prompt-based learning in ChatGPT*，DOI `10.1057/s41599-024-03991-6`。Crossref 对照结果为部分核验，卷、期、页等字段未知；导出七种格式成功返回。BBT 端点返回 404，真实写入未执行。示例结果与导出位于 `workspace/runs/citation-real-test/`，真实原生委派测试日志也保存在该目录。测试中的条目和本机 ID 仅代表当时环境。

参考 [Zotero API formats](https://www.zotero.org/support/dev/web_api/v3/basics)、[Better BibTeX JSON-RPC](https://retorque.re/zotero-better-bibtex/exporting/json-rpc/index.html)。参考项目 `research-reading-mentor` 的工作流思想；未确认其代码许可证，未复制其代码。
