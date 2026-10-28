# Literature Reading：阅读工具与边界

Codex 负责科研任务调度与最终验收。`literature_reading` 是项目角色，`paper-deep-reading` 是按需加载的工作流，`pdf_inspection.py`、`reading_cli.py`、`reading_output.py` 是确定性工具。工具不调用 LLM、不编造分析，不等同于已经验证的原生子代理调用。

## 输入与依赖

Python 3.11+；PDF 输入需要可选依赖 `pypdf>=6,<7`，见 `pyproject.toml` 的 `pdf` extra。缺依赖时报告错误。Codex bundled Python 在本次开发环境中已有 pypdf；其他机器须自行准备依赖，无需假定相同绝对路径。

- PDF：将用户授权读取的 PDF 放入项目 `workspace/`，使用相对于该目录的路径。外部路径不能直接绕过 workspace 限制；仅在有授权时复制，保留来源和许可信息。检查路径、大小、PDF 头、解析器、页数及加密状态；真实页面按 1 开始计数。
- Search：`abstract` / `finalize --record` 接收搜索结果 JSON 和记录索引。仅有摘要时分析范围固定为 abstract；来源记录和摘要不等于全文。若已授权获得 PDF，使用 `--pdf` 分开读取，不自动下载来源链接。
- Zotero：Reading 的 `zotero --item-key ...` 桥接尚未接入，因此明确返回 blocked；Citation 已有独立的只读适配器，详见 [Citation 使用说明](literature-citation.md)。Reading 不会假称附件已解析。
- Obsidian：项目没有配置或实现 vault 读写，本轮不对外部 vault 作任何操作；本地卡片是可人工导入的 Markdown。`propose_vault_export` 明确返回 blocked 并保留本地产物，未实际测试外部权限。不要假设用户的机器不存在其他 vault。

## Inspection → Analysis → Finalize

在项目目录使用准备好 `pypdf` 的 Python：

```sh
PYTHONPATH=src python3 -m ai4science.reading_cli --workspace workspace \
  inspect --pdf inputs/paper.pdf

PYTHONPATH=src python3 -m ai4science.reading_cli --workspace workspace \
  inspect --pdf inputs/paper.pdf --page 2 --page 3 --max-chars 12000

PYTHONPATH=src python3 -m ai4science.reading_cli --workspace workspace \
  finalize --pdf inputs/paper.pdf --analysis runs/example/analysis.json \
  --task-id read-example
```

Inspection 摘要返回 SHA-256、页数、未验证的 PDF 内嵌标题／作者候选、页文本状态、启发式章节与文本图表标记；每次只返回最多 100 个章节和标签，以及最多 10 个用户指定页、50,000 字符。每页文字以 physical PDF page 和提取文本偏移定位。`extract_section_chunks` 按猜测的标题边界分段；标题和边界须回查，复杂布局不保证准确。

`analysis.json` 由实际阅读论文的 Codex 或人工准备，不由脚本编造。它包含 `paper_id`、`metadata`、`sections`、`claim_evidence`、`limitations`、`unresolved_questions`、`suggested_next_actions` 和可选状态建议；可参考真实示例的 `analysis.json`。`sections` 使用 `reading_output.py` 定义的英文章节键。四类 claim 标签为 `evidence`、`author_interpretation`、`agent_inference`、`speculation`。Verified 的物理页定位必须有逐字摘录，finalize 从 PDF 重新提取后对照；它只确认摘录在提取的该页出现，章节、印刷页、图表、公式、语义与科学正确性须独立检查。独立调用 `validate_reading_result` 只检查结构和文件哈希，不重新提取 PDF 或比对摘录；需要显式重提取并调用 `validate_claim_evidence`。摘要模式的论据摘录须来自实际摘要。自动提取无文字页会标记不完整，但部分可提取文字不证明图像或表格可读。工具保守将 PDF 模式的范围记为 `partial_text`；它不代表已阅读完整正文。

默认以 `paper_id` 的稳定哈希确定 workspace 笔记目录，也可以明确指定 `--output-dir`。两个输出文件以独占创建，重复执行返回错误并保留原有笔记及个人批注；不会自动修改现有 Agent 区域或外部 vault。卡片模板见 `.agents/skills/paper-deep-reading/templates/reading-card.md`。Result 包含既有 `ExecutionResult`、原文哈希、证据引用、范围、局限、问题和可选 Citation 交接；此处 `execution.status=completed` 仅表示文件生成完成，`analysis_status` 是独立判断，质量和人工批准均未自动通过。生成工具不会确定正文论述是否被引用支持，主控必须检查。

解析结果缓存位于 workspace，键包含 PDF hash、解析器及 pypdf 版本；缓存可能包含论文文本，应受适当访问控制。缓存数据可被同权限用户篡改，结构检查不证明其等同于源 PDF。数据量及逐页字符有上限，但解析器与路径检查不是处理恶意 PDF 的 OS 沙箱；对不可信 PDF 使用适当隔离。无 OCR、图像语义识别、公式自动推导或独立 DOI 核验。`UsageMetrics` 默认为 unknown；该工具和原生会话不会自动受项目 `BudgetGuard` 约束。

## 状态与后续协作

可以生成 `research-deepread` 提议，但仅当阅读范围、分析状态、证据摘录和卡片必要章节满足最低格式约束；格式检查不证明科研质量，它不会写 Zotero。当前工具不支持证明用户理解，不接受 `research-verified` 提案。可选导师问题与回答评估由实际阅读者处理；Citation Agent 仅接收结构化、需审批的建议。单篇的局限最多是观察或候选 gap，跨论文验证需由主控决定是否委派 Search。

## 本次端到端验证

读取公开论文 [Attention Is All You Need, arXiv:1706.03762v7](https://arxiv.org/abs/1706.03762)，PDF 为 15 页。Codex 主控实际阅读选定页面，检查渲染的 Figure 1、Figure 2 和 Table 2，并调用本工具生成 `workspace/runs/reading-attention-v7/reading_card.md` 与 `reading_result.json`。结果如实标为 `partial`、`partial_text`；四个物理页摘录通过源 PDF 当次提取匹配。该示例没有验证全部附录、独立复现实验或完成自动原生子代理调用。

同日原生 CLI 单独尝试了对 `literature_reading` 的只读委派：启动期间 WebSocket TLS 失败并回退 HTTPS，最后会话报告 spawn 接口不支持选择该自定义类型，未产生该角色的 spawn 事件。见 `workspace/runs/reading-attention-v7/codex-native-test.jsonl`。因此真实项目自定义角色调用未验证；主控的阅读示例不能替代此验收项。
