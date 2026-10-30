# Independent scientific doublecheck V0.1

Codex 是唯一主控。`review_doublecheck` 的职责与三阶段边界由 [scientific-doublecheck](../.agents/skills/scientific-doublecheck/SKILL.md) 和 [.codex/agents/review_doublecheck.toml](../.codex/agents/review_doublecheck.toml) 定义。先仅依据授权稿件及必要原始材料重建问题、研究空白、假设、目标、方法、实验、观察、解释和结论；固定 `independent_review.md`、`scientific_argument_map.md` 与 `independent_findings.json` 后，才逐条核查其他审稿记录，最后识别遗漏和分歧。与已审查的问题不同的新问题须给出原文、影响、不同点、验证建议和限制。不得推测未报告内容必未执行。

输入为 workspace 相对的稿件、审查范围、明确授权的原始证据及审稿记录；引用以路径、SHA-256 和精确位置绑定。输出包括独立审查、论证图、符合原 Review Finding Schema 的独立 findings、`review_adjudication.json`、`missed_issues.md`、`doublecheck_report.md` 和 `phase_manifest.json`。裁定保留原主张、证据、角色和等级，支持 supported、partially_supported、unsupported、requires_more_evidence、out_of_scope；原审稿结论不因多位审稿者认同而自动成立。执行完成、质量和人工批准独立记录，不覆盖原稿或原审稿文件。

[只读校验器](../src/ai4science/doublecheck_review_validation.py) 接受显式白名单，校验文件哈希、定位、证据、Finding Schema 的项目支持子集、三份 Pass 1 输出、来源 finding ID、重大问题覆盖及裁定字段。它先核对各记录声明的稿件版本，版本不一致时在读取裁定内容前阻断；逐条裁定需要实际审读原文。校验器的相同哈希和阶段顺序为文件或声明一致性检查，不能证明审稿报告真实产生于所声明的稿件、过程实际顺序、隔离或科学结论；路径校验也不提供 OS 沙箱或防止并发替换。重复问题的语义关联与等级调整由审稿者完成，不是自动语义去重器。

外部保密送审稿件须核查权利人、期刊和机构对实际 AI 处理环境的授权；本地文件不意味着托管模型本地处理。使用 peer-review 工作流必须通过其 unchanged intake gate；BLOCKED 时停止该工作流，不得改名绕过。本轮合成工程测试未调用该受限正式审稿工作流；scientific-critical-thinking 1.5 和 scientific-writing 2.3 被用于约束证据、推理与保密。无第三方模型 API、自动论文外传或完整实验运行。

## 测试与独立性

[合成案例](../teams/strict_review/fixtures/doublecheck-review-v01/)包含稿件、CSV、三组**人工构造的测试审稿记录**、实际使用现有统计模块计算的 RMSE 记录、另一版本稿件和独立预期。它们不冒称真实的三个 Subagent 运行。执行记录在 [workspace/runs/doublecheck-review-v01](../workspace/runs/doublecheck-review-v01/)。Pass 1 调用不继承父会话历史的通用子代理，只提供稿件、数据、Skill 和 Schema；但文件系统访问没有被技术强制限制，因此诚实标为 `non_blind`，不能声明严格盲审。主控先核验并固定 Pass 1，才打开测试审稿意见和测试预期。原始 findings 的路径含 `workspace/` 前缀，部分 source_location 为多范围，不符项目工作区相对路径及单一范围格式；原始冻结结果保留，第二组副本仅规范化路径和主位置，未改变内容，再冻结并用于裁定。

主审发现总消息下降时有效任务数量也下降，这是另外三组测试意见没有涵盖的替代解释；20% 总消息下降本身在指定的两次合成运行内算术正确。复核指出预测输入使用了决策后才知道的值、RMSE 报告 1.20 而本地对四条 CSV 做定向复算得到约 1.5811、不同条件的 80 和 120 消息不构成直接矛盾；训练/测试划分未报告且实际是否执行未知。人工构造的 M-01 和 C-02 指同一问题但等级不同，裁定将 C-02 的 minor 调至 major 并保留原等级与依据。另一个稿件 SHA 不一致的测试在裁定前阻断。合成数据、报告、计算和输入哈希不等于真实科研实验复现。

14 个 Doublecheck 校验单元测试、现有方法/统计/一致性回归与 Finding Schema 测试均通过；固定产物之后的 11 项案例断言通过。复查已存在运行可执行 `PYTHONPATH=src python3 teams/strict_review/fixtures/doublecheck-review-v01/verify_saved_run.py`，它检查该次保存的结果，并不重演模型推理或证明盲审。实际工作流测试只覆盖一个合成案例，不能由此估计泛化表现或实际误报率。

本会话实际指定 `agent_type=review_doublecheck` 返回 `unknown agent_type 'review_doublecheck'`，未原生调用；总体执行为 `inline_skill`，其中 Pass 1 的上下文隔离尝试使用通用子代理，不伪称原生角色。新 Codex 调试上下文可以发现 Skill 元数据；主控实际读取其文件。Skill Creator Python quick validator 缺 PyYAML，未运行成功；TOML 和 YAML frontmatter 单独解析通过。没有安装依赖。原有 Method、Statistics、Consistency 的业务代码未改变。
