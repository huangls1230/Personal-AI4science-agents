# 本地执行和预算

`ScriptAdapter` 当前仅支持 `sha256`：读取一个已登记且哈希匹配的 workspace 文件，返回哈希和证据，不运行任意命令。`MockExecutor` 返回明确标记为 mock 的离线结果，不产生科研发现。`CodexNativeAdapter` 和 `ExternalHarnessAdapter` 是不可用占位，直接调用会返回 blocked；它们不连接原生委派或任何外部 Harness。模型接口与 `MockModel` 仅用于离线验证。

`ContextSelector` 只读取 manifest 中显式选取的文件，检查相对路径、哈希与总字节上限；字节不是 token。`UsageRecorder` 可在 workspace 写入 JSONL，保留实际输入、输出字节和报告的 token、成本字段。未提供的用量保留 unknown。

`BudgetGuard` 以进程内锁控制执行次数、重试次数和并发；根据调用方提供的 token、费用上界执行准入检查，缺少必要上界时拒绝。已接入的本地执行器不调用模型，因此提供零模型 token 和费用上界。预留值累计且不自动退款；状态不跨进程或重启共享。调用者必须共享同一个 guard 才能共享其限制。token 与费用准入估算不能约束远端实际账单，也不能约束 Codex 账户内的所有消耗；接入真实模型时还需验证执行器或供应商可实施的硬上限及故障处理。项目不具备统一跨进程预算或成本监控。
