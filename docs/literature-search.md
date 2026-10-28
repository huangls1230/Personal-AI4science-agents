# Literature Search：实际执行边界

`literature_search` 是由 Codex 调用的原生角色；`literature_cli.py` 是可独立运行的 Python 工具，不启动 LLM 或第二个主控。角色根据用户问题设计检索词、同义词、布尔策略及来源，并对工具返回的候选进行科研解释；Python 完成 API 请求、分页、去重、有限 DOI 核查、可解释的词项初筛和受控文件输出。用户授权外发检索词后运行，严禁传送敏感或内部内容。

## 使用

从项目根目录，先为每次运行创建 workspace 内独占的输出目录；输出文件已存在时工具拒绝覆盖。以下是公开测试主题示例：

```sh
mkdir -p workspace/runs/search-example
PYTHONPATH=src python3 -m ai4science.literature_cli \
  --task-id search-example --query 'multi-agent systems network topology' \
  --term multi-agent --term topology --source crossref \
  --workspace workspace --output-dir runs/search-example \
  --limit 5 --page 1 --max-results 5 --verify-limit 3 \
  --sensitivity public --allow-network
```

`--query` 可重复以搜索同义表达；`--source` 可重复，`--source-query source=...` 可为某个来源提供其自身语法的查询（覆盖该来源的公共 query 列表）。Boolean 策略须按来源翻译：Crossref `query.bibliographic` 不提供通用布尔运算符，不要把 `AND`/`OR` 当成严格过滤；arXiv 可使用其支持的 `all:...` 等表达式。Semantic Scholar 的 relevance search 使用普通文本，不支持特殊查询语法，带连字符的词可能无匹配，应按其文档改为空格。`--page` 为单次请求的页码，`has_more` 为来源结果中的继续提示；不自动遍历所有页面。每源每查询最多 50 条，一次最多 5 个公共 query、4 个来源、100 条输出与 20 次 DOI 核验。每个 socket 操作超时不超过 30 秒，不能视作完整执行的绝对截止。

支持 Crossref、arXiv、Semantic Scholar 和 OpenAlex 公开 API；实际连接、配额和服务策略必须在运行时验证。OpenAlex 需要 `OPENALEX_API_KEY`；Semantic Scholar 可选使用 `SEMANTIC_SCHOLAR_API_KEY`。密钥不写入结果或缓存。arXiv 网络请求在同一进程内间隔至少 3 秒，不协调其他进程。无有效密钥、限流、网络异常或解析错误会作为来源错误记录，而非伪装为空检索结果。

24 小时缓存位于 workspace 的 `cache/literature`（可通过 `--cache-dir` 指定其他 workspace 相对目录）；缓存保存元数据与可能受版权保护的摘要，可能透露检索主题，须按数据政策管理。缓存命中保留原检索时间。摘要并非全文，程序不下载全文；来源报告的 PDF 链接仅标为 `link_reported`，未验证其可访问性或使用许可。

## 结果与验证

输出 `search_results.json` 和 `search_report.md`，stdout 只返回符合现有 `ExecutionResult` 形状的简短状态及 SHA-256 文件引用。结果记录真实查询、来源、页码、时间、来源错误、缓存状态、候选和原始来源断言。仅相同规范化 DOI 自动合并；没有 DOI 的条目留待人工核对，冲突字段保留。单条 Crossref DOI 查验的 `doi_title_match` 只表示 DOI 和归一化标题匹配，不保证作者、年份、期刊或科学内容正确；请求未做或失败为 `unverified`。

相关性级别是标题／摘要词项重合的透明初筛，不按引用量排列，也不是客观质量分数。方法关联、证据质量、创新性及新近性需要主控或 Search 角色依据材料人工／模型复核，全文不可用时须说明证据不足。不同数据库对出版类型的元数据不一致时，保留冲突和不确定性。检索空结果与来源失败分开；部分失败时进程返回非零，结果文件保留 `partial` 状态及错误。

该路径不自动接入项目 Router、`BudgetGuard` 或 Codex 账户预算。请求数量和每次 socket 超时是工具范围内的限制，不是总费用、Token、跨进程并发或总墙钟时间的硬上限。底层 Python 来源函数供可信调用者使用；调用者负责敏感度、网络授权和预算。路径检查不能替代操作系统沙箱。

来源文档：[Crossref REST API](https://support.crossref.org/hc/en-us/articles/214320426-REST-API)、[Crossref 查询限制](https://community.crossref.org/t/advanced-set-boolean-operators/4596)、[Semantic Scholar API](https://api.semanticscholar.org/api-docs/graphs)、[arXiv API 手册](https://info.arxiv.org/help/api/user-manual.html)、[OpenAlex 文档](https://docs.openalex.org/)。
