# Personal AI4Science Agents — V0.1

Codex 是唯一科研主控；本项目提供离线任务契约、规则推荐、受控上下文和本地执行原语，不自动调度科研任务。V0.1 不连接任何真实模型 API、外部 Harness 或科研 MCP，也未实现从 Python 调用 Codex 原生委派。

## 快速验证

需要 Python 3.11+，无需安装第三方依赖。在项目目录运行：

```sh
mkdir -p .test-tmp
TMPDIR="$PWD/.test-tmp" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

测试的临时文件位于项目内；macOS 工具链可能留下缓存，可在检查后删除 `.test-tmp`。Windows 用户可以采用相应的环境变量设置方式。JSON Schema 为跨语言结构定义；Python 的 `from_dict` 与 `validate` 分别验证结构语义及实际文件路径与哈希，不需安装 JSON Schema 校验器。

## 离线示例

在项目目录运行下方代码，读取现有的 workspace 说明文件，创建受控引用、推荐执行器并执行一次只读 SHA-256 校验。此操作不调用模型，不产生科研结论：

```sh
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path
from ai4science.adapters import ScriptAdapter
from ai4science.budget import BudgetGuard, policy_from_config
from ai4science.contracts import ResearchTask, ExecutionRequest, create_artifact
from ai4science.router import project_candidates, route

load = lambda name: json.loads(Path('config', name + '.yaml').read_text())
routing, executors, models, budget = (load(n) for n in ('routing', 'executors', 'models', 'budgets'))
policy = policy_from_config(budget)
root = Path('workspace')
ref = create_artifact(root, 'README.md')
task = ResearchTask('example-1', '校验资料', 'sha256', ('sha256',),
                    complexity='deterministic', input_artifacts=(ref,))
candidates, available_models = project_candidates(
    routing, executors, models, {'script': ('script', ScriptAdapter.capabilities)}, {})
decision = route(task, candidates, available_models, policy, preferences=routing['preferences'])
print('route:', decision.status, decision.executor)
if decision.executor == 'script':
    result = ScriptAdapter(root, guard=BudgetGuard(policy)).execute(ExecutionRequest(task, 'script'))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
PY
```

`workspace_root` 是调用者选择的信任边界，必须指向项目内授权工作区。路径检查不能代替系统沙箱，尤其不能抵御并发符号链接替换。真实敏感数据的存放与网络权限须由环境提供控制。守卫仅在同一进程内为使用同一 `BudgetGuard` 的调用生效；配置文件不会自动注入到执行器。详见 [运行时边界](docs/runtime.md) 和 [契约](docs/contracts.md)。

- [架构](docs/architecture.md)
- [科研可信性规范](docs/research-integrity.md)
- [Codex 集成边界](docs/codex-integration.md)
- [配置说明](config/README.md)
