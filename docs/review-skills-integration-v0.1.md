# Method 审稿 Skill 集成与审计

日期：2026-10-30。两个目标目录均从上游固定提交 `5f2bc0341354fd5590aef76a533ada1e1e5b4e62` 取回；逐文件 `git hash-object` 对照该提交的 tree，共 33 个 blob 一致。只获取目标 Skill 目录，没有安装整个仓库。根 LICENSE 为 MIT，Copyright (c) 2025 K-Dense Inc.；安装目录分别保留原始 LICENSE 和 PROVENANCE。本轮未引入第三方模型、OpenRouter、scientific-schematics 或 Python 包。

## 审计和本地补丁

- **peer-review 2.4**：24 个上游文件，包括入口、6 references、9 assets、8 个标准库 Python 文件。原版无默认 public 分类，intake 默认 `unpublished_confidential` 且未授权，但敏感数据 false 是未核实占位。逐文件静态审查未发现网络、子进程或凭据读取。实际实验发现原 `_common.py` 接受项目外路径、`..` 和父级链接；`--force` 与 `os.replace` 能覆盖文件。安装版限定用户文件为项目 workspace，两个必要内置 assets 使用精确只读例外；以目录 fd、`O_NOFOLLOW` 和排他创建限制遍历、符号链接、硬链接输入及覆盖，禁用 `--force`。自动联网或插入上游引用的指令改为须经授权才可建议。保留原有授权和保密规则及 intake 校验逻辑，未放宽任何门控。详见 [PROVENANCE](../.agents/skills/peer-review/PROVENANCE.md)。
- **scientific-critical-thinking 1.5**：9 个上游文件，入口及 8 references，没有脚本、assets 或 Python 依赖。安装版明确禁用可选 scientific-schematics/OpenRouter、读密钥、自动联网和添加引用，保留科学判断及保密要求；参考资料中的链接和教学案例不自动执行，也不自动适用于计算机科学。详见 [PROVENANCE](../.agents/skills/scientific-critical-thinking/PROVENANCE.md)。
- **scientific-writing 2.3**：继续使用已安装的本地修订版；不覆盖或重新安装。其许可、固定版本及限制见原有 [PROVENANCE](../.agents/skills/scientific-writing/PROVENANCE.md)。

安全脚本是辅助措施，不是 OS 沙箱或访问授权。输出写失败可能留下部分新文件；shell 重定向和并发搬移已打开目录仍依赖执行环境。绝对路径的 `/var` 与 `/private/var` 别名可能被保守拒绝。外部文件须先经授权移入 workspace；上游来源目录与政策声明不自动证明当前场景获授权或适用。

## Method 集成和门控

[methodology-review](../.agents/skills/methodology-review/SKILL.md) 指引按需读取 critical-thinking 的假设、偏倚及替代解释资源；当用户任务使用 peer-review 时先执行其真实 intake，只有门控允许时才能按 peer-review 工作流继续。保密第三方来稿还需核实授权及期刊、机构适用政策。不得把托管模型处理描述成本地、伪造人类责任或把同一被阻止的任务改名来绕过门控。`review_method.toml` 指向这些受限指引，不改变角色职责或启动新 Harness。

## 验证 A–E

1. **安装 A：** 两个目标包已安装，分别有 26 和 11 个文件（含 LICENSE 和 PROVENANCE），逐文件 SHA-256 与经审计暂存版本一致。三个 Skill 的元数据通过 Ruby YAML / 项目等效验证；原版 Python quick_validate 因 PyYAML 缺失未执行。
2. **发现 B：** 本地 `codex debug prompt-input` 生成的新提示上下文列出两个新 Skill 和 methodology-review；这只是发现元数据，不证明当前启动时清单或角色执行时自动加载。
3. **读取 C：** 主控本轮通过文件工具实际读取了安装后的两个 `SKILL.md`，并读取了 critical-thinking 的 `references/common_biases.md`。文件内容和命令事件可在会话中核查，文件哈希记录于 [加载清单](../workspace/runs/review-skill-integration-v01/load-evidence.json)。peer-review 只用于读取规则和执行 intake；不能将此说成完整审稿。
4. **规范落实 D：** 使用合成材料的真实托管执行声明运行安装版 intake，结果是 [BLOCKED](../workspace/runs/review-skill-integration-v01/intake-report-v2.json)。第二版 intake 不将材料标为 public，保留政策仍为未确认；第一版及其结果也保留以便核对。不虚报 `local_only`，也不借另一 Skill 绕过本次 peer-review 工作流。独立通用代理读取 critical-thinking 后，只检查此前 Step 2 的主案例和边界案例 *finding 文件*，没有读取稿件或 peer 指引：它指出先前意见区分了观察、风险和材料不足，边界意见未机械套用主稿问题，但不能核验原文证据，也不能证明新的 Method 端到端回归完成。原 [Step 2 报告](../workspace/runs/method-review-v01/validation.md) 是安装前的执行记录，不能冒称本轮产生。
5. **原生调用 E：** 本轮直接指定 `agent_type=review_method`，工具返回 `unknown agent_type 'review_method'`；没有创建该角色。上述独立通用代理不是原生 review_method。

上游 validator 不支持任何 `external_service_use=true` 的审稿，即使外部处理另有授权也仍 BLOCKED；它还要求真实的人类责任、冲突、政策与处置声明。当前 synthetic 用户授权不自动证明这些字段，不能为通过测试填写虚构值。因此两个 Skill 安装和部分验证完成，**联合 peer-review + Method 端到端测试尚未完成**。除非后续有真实可用且授权合规的本地处理路径，否则保持阻止；不能由本地 CLI 的成功推断托管会话可处理真实送审稿。

## 测试

- `python3 -m unittest discover -s tests -p 'test_peer_review_skill.py' -v`：8 项通过；从安装包复制到临时仿项目，检查授权 workspace、越界与遍历、父/叶符号链接、硬链接、覆盖/force、两个允许 assets、默认 intake 和如实 hosted intake 的拒绝。
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_method_review_validation.py' -v`：9 项通过。
- peer-review 8 个脚本通过 Python AST 解析，JSON assets 与 review_method TOML 解析成功。相关实际读写、参考资料和静态网络检查见两个 PROVENANCE 与本报告；没有对真实稿件运行完整新审稿。
