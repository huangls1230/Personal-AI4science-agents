# Scientific Writing Skill：修复、安装和验证

日期：2026-10-29。上游版本固定为 `5f2bc0341354fd5590aef76a533ada1e1e5b4e62`，上游 Skill 版本 2.3；来源、MIT 许可和本地修改见 [安装包记录](../.agents/skills/scientific-writing/PROVENANCE.md) 与 [许可证](../.agents/skills/scientific-writing/LICENSE.md)。仅安装了该 Skill，目标目录独占创建，没有覆盖同名目录。

## 修复和边界

- 来源模板默认分类为 `unknown`，验证器接受该状态；标为 `public` 时必须提供独立的人工核实人、日期与依据。科学内容已核实不等同公开状态已核实。原有 `public` 记录缺少该记录时需要迁移核实。该记录是声明而不是证明或传输授权。
- CLI 从其安装位置确定项目根，拒绝项目外路径、`..`、符号链接和多硬链接输入；通过目录文件描述符、`O_NOFOLLOW` 和新建文件排他操作限制文件读写。脚手架目录创建也使用相同边界。没有通过命令行参数或环境变量扩大授权范围的入口。经用户明确授权的外部文件，应通过符合 Codex 实际权限和审批的方式复制到 workspace 后处理。
- 以上机制不代替 Codex 工具权限和操作系统沙箱；stdout 重定向、目录被并发搬移，以及文件复制本身的授权，仍依赖执行环境和人工控制。不支持必要目录描述符原语的系统会拒绝执行。未知和受限资料的外传仍需适当授权和政策核查。
- 将 CLI 示例改为从项目根运行，并将上游自动添加自身论文的要求改为在授权范围内向作者提出建议和核实；没有添加任何论文引用。

## 验证

Python 3.13.18；系统 Python 和捆绑 Python 均无 PyYAML，未修改全局 Python 环境。使用 Ruby 自带 YAML 解析器及等效于本机 Skill Creator 校验器的前置元数据、名称、描述和未完成占位符检查；它不是原版 `quick_validate.py` 的成功运行，也不证明 Skill 安全。复现：

```sh
ruby tests/validate_scientific_writing_metadata.rb .agents/skills/scientific-writing
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_scientific_writing_skill.py
```

对实际安装副本：七项合成材料测试通过，覆盖 `unknown`、公开状态记录、科学和公开核实相互独立、脚手架及文稿 lint、项目外输入、遍历、符号链接和未授权输出。报告指南选择命令在临时副本成功返回 `prisma-2020`。29 个引用的 Skill 资源路径存在；9 个 Python 文件通过 AST 解析，6 个 JSON 资产通过解析；安装的 33 个文件与经过审计的临时版本逐文件一致。未使用真实科研稿件或调用外部模型 API。

本机 `codex debug prompt-input` 在项目根生成的新提示上下文中列出 `scientific-writing`，并将路径别名映射到本项目 `.agents/skills`。这是本机新上下文**发现元数据**的证据；不是独立交互式新会话已加载或执行 `SKILL.md` 正文的证据。当前聊天的启动技能清单也不会因安装而自动刷新。
