# 统一入口验证记录

日期：2026-10-29。此记录区分配置检查、模拟路由和实际原生角色调用；没有检索新文献、读取或上传科研全文、写入 Zotero 或编辑论文。

## 六条指令：独立只读场景演练

验证者读取项目入口和两个 Skill，以合成项目 `demo` 为假设：用户已按顺序选定 P1–P3，P1 的授权材料、当前 Markdown 稿件和针对该版本已由作者批准的术语表均可用。验证者没有实际读取这些合成文件，也没有执行委派或外部写入。若真实项目、输入、确认依据或文件哈希不存在或冲突，必须先澄清或阻止依赖阶段。

| 指令 | 工作流与最小角色 | 输入、产物和边界 |
| --- | --- | --- |
| 帮我精选3篇多智能体协同相关论文。 | research-literature-workflow；literature_search | 确定主题及允许来源，按需复用检索清单，保存来源、候选与筛选理由；不自动深读，选择待用户确认。 |
| 深度阅读刚才选定的第一篇文章。 | research-literature-workflow；literature_reading | 从本项目可信确认顺序解析 P1，核验材料授权和哈希；保存有证据定位的 Markdown 笔记，不连接 Obsidian。 |
| 把已确认的论文整理到Zotero。 | research-literature-workflow；literature_citation | 使用确认清单并核验目标馆藏和元数据；保存核验与导入提案。请求本身可授权写入，但项目客户端仅只读；实际外部写入能力须另行验证。 |
| 检查论文Introduction的结构逻辑。 | paper-editing-workflow；paper_structure | 使用指定稿件及 Introduction，保存源定位、报告和方案；改稿及高风险改变按规则先确认。 |
| 检查当前论文中的术语一致性。 | paper-editing-workflow；paper_terminology | 核验当前稿和适用的已批准术语表，保存定位明确的问题与提案；不自动批准新术语。 |
| 对当前论文进行完整学术编辑。 | paper-editing-workflow；structure → terminology → language → 主控最终检查 | 使用授权稿和可信批准术语表，按序保存各阶段产物、哈希和风险；不应用未批准结构方案、不覆盖原稿，候选稿待作者批准。 |

演练验证的是 Codex 在给定上下文下的路由判断，不是六次真实任务执行，也不是自然语言分类器的覆盖率证明。

## 可核查的实际检查

- 六个项目角色 TOML 均被 Python `tomllib` 解析。2026-10-29 当前会话调用 `collaboration.spawn_agent`，参数包含 `agent_type=literature_search`、`task_name=unified_entry_role_probe`；返回 `/root/unified_entry_role_probe`。该角色实际只读了 `teams/literature/README.md` 并返回职责摘要。工具事件证明可选择该角色，不能单凭其回答证明具体配置的每项指令均已加载；本轮没有借此声称其他角色均被调用。
- `ruby tests/validate_scientific_writing_metadata.rb` 分别检查两个 Skill 的 YAML、名称、字段及占位符，均通过；这是等效静态检查，不是 Skill Creator 的 Python validator。
- `codex debug prompt-input test` 在允许的本地进程中成功生成新提示上下文，其中同时出现两个 Skill；此操作不调用模型。当前会话初始目录列出了 paper-editing-workflow，但没有新建的 research-literature-workflow；新文件可在本会话按路径读取，不能声称当前会话初始目录已动态刷新或证明真实语义触发。
- `PYTHONPATH=src python3 -m unittest tests.test_paper_editing_workflow`：11 项通过。额外用临时 workspace 验证 ContextSelector 对明确列入清单的上下文可读取、拒绝未列入的另一项目文件、拒绝发生变化的哈希。
- 已为现有 `tsf-mas-literature` 项目创建非覆盖式上下文索引，记录已有检索材料及其哈希；报告中精选论文仍待用户确认，索引未把候选排序认作用户决定。索引仅为主控维护的文件约定，不自动验证批准或维护项目状态。
