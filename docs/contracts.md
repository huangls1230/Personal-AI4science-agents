# 任务契约与验证

`src/ai4science/contracts.py` 定义版本 `1.0` 的 `ResearchTask`、`ExecutionRequest`、`ExecutionResult`、`ArtifactReference`、`EvidenceReference`、`UsageMetrics` 和 `ExecutorCapabilities`；`schemas/` 提供 JSON Schema。`from_dict` 检查版本和字段，并执行数据类约束；涉及实际文件与哈希的检查需要显式调用 `validate(workspace_root)`。仅解析结构不能证明文件或证据真实。

文件引用使用 workspace 内的相对路径和 SHA-256，`create_artifact` 基于文件内容计算哈希；文件校验拒绝绝对路径、路径穿越、盘符和解析后逃逸 workspace 的符号链接。该检查不抵御并发替换符号链接等竞态，不能代替 OS 权限、沙箱或可信执行器。哈希证明内容一致，不证明科学结论正确或来源可信。

执行状态包括 pending、running、completed、failed、blocked、approval_required；`validate_transition` 验证合法转换但不保存状态。结果的质量状态和人工批准状态分别记录，`completed` 本身不表示通过科研验收或获得批准。

重试使用 attempt 和 idempotency key 识别同一任务，重试需要 key；该标识并不会自动去重或撤销部分副作用。真实执行器必须提供安全重试、可靠去重或明确禁止重试。token 用量可为 unknown、estimated 或 exact，unknown 不应伪装为精确数字；成本未知时保留空值。
