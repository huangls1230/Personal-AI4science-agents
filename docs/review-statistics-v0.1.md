# Statistical Review & Reproducibility V0.1

Codex 主控按任务选择 `review_statistics` 和 [statistical-review Skill](../.agents/skills/statistical-review/SKILL.md)。该角色审查统计报告、指标定义、结果与证据；[确定性计算模块](../src/ai4science/statistics_recalculation.py)负责限定的 CSV 计算，[只读校验模块](../src/ai4science/statistics_review_validation.py)校验产物结构、定位和哈希。没有模型推断执行器、外部服务、未知脚本执行或 pickle 加载能力。

## 输入和安全

提供 `project_id`、workspace 相对稿件路径和审查范围、**明确授权的**实验数据与代码路径、作者的指标定义、报告值、输出目录及 review policy。只读源文件，在独立目录写新结果；提供代码路径不等于授权或安全审查通过，也不触发代码执行。第三方保密送审稿需实际权限及适用 AI 政策。托管模型会话不是本地脚本；使用 peer-review 的请求继续遵守该 Skill 的 intake 门控，BLOCKED 时停止该请求，不得借其他 Skill 改名绕过。独立授权的统计测试不冒称 peer-review。

数据文件须明确列入 `authorized_data_paths`、位于 workspace，拒绝遍历、符号链接、硬链接、非普通文件、非 CSV、无效列、缺失和非有限数值。目录并发替换仍受 OS 沙箱保护，不能由路径检查代替；单文件上限 20 MiB / 200,000 行，V0.1 未实现大文件分块。输入哈希只证明被计算字节与记录一致，不证明数据真实性或实验独立性。

区分 **A** 报告审查（无复算）、**B** 数据指标复算、统计再分析，以及 **C** 具备代码和环境时可能进行的实验复现；材料等级本身不意味着权限或成功。实际运行了指标代码也不表示复现研究实验。

## 计算接口

- `recalculate_forecast`：显式指定目标/预测列、单位、`mean_over_rows`、所需指标、授权路径和容差；支持 MAE、MSE、RMSE、MAPE、sMAPE。MAPE 为 `100*mean(abs(error)/abs(actual))`，实际值为零时拒绝；sMAPE 为 `200*mean(abs(error)/(abs(actual)+abs(prediction)))`，两者同时为零时拒绝。不同论文及库的零值、尺度和聚合约定可能不同，须先核对作者定义；例如 scikit-learn 文档使用 epsilon 的 MAPE 策略，不能默认认为数值等同。[scikit-learn 指标文档](https://scikit-learn.org/stable/modules/model_evaluation.html)。
- `recalculate_reduction`：仅当作者定义与 `100*(mean(baseline)-mean(proposed))/mean(baseline)` 相同时使用；显式选择 `ratio_of_means`、单位、配对列与容差。基准均值须大于零；此计算不等于逐行降幅的平均。通信、延迟等研究特定指标不自动假定通用公式。
- `summarize_paired`：显式给配对 ID、方向和单位，输出描述性差值及改善/恶化/持平数；不做统计推断。
- `paired_sign_flip`：仅对 2–16 个独立配对实验单位提供精确双侧符号翻转枚举。调用者须分别显式声明独立单位和零假设下符号可交换性；代码不能证明这些假设，不能把重叠窗口或共享环境的多个 Agent 当独立对。统计量及极端值定义记录在结果中；[SciPy 配对置换说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html)描述配对内交换的零假设。没有实现通用 t 检验、置信区间、效应量、复杂依赖结构或任意研究代码执行。

这些函数仅返回数据，不写文件、不联网；调用方记录实际命令、代码版本和输入/输出。相同文件哈希、参数、实现哈希且现有结果经主控核验时，可由主控复用；没有自动缓存或自动证明历史执行的机制。

## 输出与契约

`statistics_review.md`、`statistics_findings.json`、`recalculation_report.json` 和 `reproduction_manifest.json` 分别保存审稿、符合原 Review Finding Schema 的问题、逐项计算和实际执行/限制。`claim_evaluations.json` 单独记录 `verified`、`contradicted`、`partially_supported`、`insufficient_information`、`not_checked`；这些状态不改写 finding 的四个核验状态。实际数据不足时 `report_only` 结果无伪造的数值记录。清单记录实际命令、Python 版本、输入和脚本哈希、随机种子及未执行事项；执行完成、科研质量与人工批准分开。

对现有文件调用 `validate_statistics_review_run`，显式传入已授权 evidence 路径和可信计算脚本绝对路径；它复用原 Schema 的有限关键字验证，检查 scope、路径、哈希、公式数值比较一致性、输出别名、状态及限制。它不运行计算、不证明记录的历史执行、不证明证据是否支持主张，亦不会自动接受完整实验复现。

## 合成验证与诚实的修订记录

三份合成稿与 CSV 在 [fixtures](../teams/strict_review/fixtures/statistics-review-v01/)；最终版本在 [workspace/runs/statistics-review-v01-final](../workspace/runs/statistics-review-v01-final/)。Codex 主控先加载 statistical-review，以 `inline_skill` 审查及执行 Python 算法，另有通用子代理只看稿件做盲审，不读取 CSV 或期望清单。首轮报告、15 项输出哈希固定后才打开预期清单：首轮正确标出数值不符、配对与窗口依赖问题，但仅将“全部条件改善”标为证据不足。核对后新增可审计的 `summarize_paired`；在单独后续运行中复算发现四对中两对改善、两对恶化，因而对所给配对观测的全改善主张标为 contradicted。原始盲审输出未覆盖；后续记录不冒称盲审发现了它。

预测数据得到 MAE 1.5、RMSE 约 1.5811388300841898；报告值 1.20 超过 0.005 容差。通信计算用基准均值作为分母，得到 20%；在等行数情形与论文的总和比等价。另用独立 `decimal.Decimal` 脚本复核 MAE、RMSE、百分比和配对方向。边界论文的已报告指标在其精度内一致，不因重叠窗口自动误报；只摘要场景 Level A 停止复算，结果数组为空并注明原因。配对数据为手工合成，没有独立随机机制或可交换性证据，本次**未计算推断 p 值**。没有原始真实科研数据或研究代码，也未复现论文实验。

三种最终产物经只读校验器和 `ResearchTask` / `ExecutionResult` 验证；质量与人类批准保持未自动通过。具体可复查 [测试记录](../workspace/runs/statistics-review-v01-final/validation.md)、[审稿示例](../workspace/runs/statistics-review-v01-final/outputs/statistics_review.md)、[复算结果](../workspace/runs/statistics-review-v01-final/outputs/recalculation_report.json)、[执行清单](../workspace/runs/statistics-review-v01-final/outputs/reproduction_manifest.json)。

本会话直接选择 `agent_type=review_statistics` 返回 `unknown agent_type 'review_statistics'`，因此没有原生自定义角色调用；主控执行方式记录为 `inline_skill`。已安装 `scientific-critical-thinking` 和 `scientific-writing` 可按需复用，`statistical-analysis` 未通过项目先前审计且未安装，不得声称使用；上游 peer-review 的托管执行门控保持原样。
