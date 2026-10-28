"""In-process admission control; it does not cap a remote provider's bill."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from threading import Lock

from .contracts import UsageMetrics, validate_workspace_path


@dataclass(frozen=True)
class BudgetPolicy:
    max_executions: int = 1
    max_retries: int = 0
    max_concurrent: int = 1
    max_tokens: int | None = None
    max_model_calls: int | None = None
    max_cost: float | None = None
    on_exceed: str = "blocked"  # or approval_required

    def __post_init__(self):
        for name in ("max_executions", "max_concurrent"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.max_retries) is not int or self.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        if self.max_tokens is not None and (type(self.max_tokens) is not int or self.max_tokens < 0):
            raise ValueError("max_tokens must be non-negative")
        if self.max_model_calls is not None and (type(self.max_model_calls) is not int or self.max_model_calls < 0):
            raise ValueError("max_model_calls must be non-negative")
        if self.max_cost is not None and (not isinstance(self.max_cost, (float, int)) or isinstance(self.max_cost, bool) or not 0 <= self.max_cost < float('inf')):
            raise ValueError("max_cost must be finite and non-negative")
        if self.on_exceed not in ("blocked", "approval_required"):
            raise ValueError("invalid on_exceed")


class BudgetExceeded(RuntimeError):
    def __init__(self, reason: str, disposition: str):
        super().__init__(reason)
        self.disposition = disposition


class BudgetGuard:
    """Shared across calls in one process. Reservations conservatively accumulate.

    Token/cost estimates are admission bounds, not enforcement of remote spending.
    A runtime/provider must independently enforce a declared bound for it to be hard.
    State is not shared across processes or persisted across restarts.
    """
    def __init__(self, policy: BudgetPolicy):
        self.policy = policy
        self._lock = Lock()
        self._active = 0
        self._executions: dict[str, int] = {}
        self._tokens: dict[str, int] = {}
        self._model_calls: dict[str, int] = {}
        self._cost: dict[str, float] = {}

    @contextmanager
    def reserve(self, task_id: str, attempt: int, *, token_upper_bound: int | None = None,
                cost_upper_bound: float | None = None, model_calls_upper_bound: int | None = None):
        p = self.policy
        def reject(message):
            raise BudgetExceeded(message, p.on_exceed)
        with self._lock:
            if type(attempt) is not int or attempt < 1:
                reject("attempt must be positive")
            if attempt - 1 > p.max_retries:
                reject("retry limit exceeded")
            if attempt != self._executions.get(task_id, 0) + 1:
                reject("attempt must be the next unused attempt")
            if self._executions.get(task_id, 0) >= p.max_executions:
                reject("execution limit exceeded")
            if self._active >= p.max_concurrent:
                reject("concurrency limit exceeded")
            if p.max_tokens is not None:
                if type(token_upper_bound) is not int or token_upper_bound < 0:
                    reject("known token bound required")
                if self._tokens.get(task_id, 0) + token_upper_bound > p.max_tokens:
                    reject("token admission budget exceeded")
            if p.max_model_calls is not None:
                if type(model_calls_upper_bound) is not int or model_calls_upper_bound < 0:
                    reject("known model call bound required")
                if self._model_calls.get(task_id, 0) + model_calls_upper_bound > p.max_model_calls:
                    reject("model call admission budget exceeded")
            if p.max_cost is not None:
                if not isinstance(cost_upper_bound, (float, int)) or isinstance(cost_upper_bound, bool) or not 0 <= cost_upper_bound < float('inf'):
                    reject("known cost bound required")
                if self._cost.get(task_id, 0) + cost_upper_bound > p.max_cost:
                    reject("cost admission budget exceeded")
            self._executions[task_id] = self._executions.get(task_id, 0) + 1
            self._tokens[task_id] = self._tokens.get(task_id, 0) + (token_upper_bound or 0)
            self._model_calls[task_id] = self._model_calls.get(task_id, 0) + (model_calls_upper_bound or 0)
            self._cost[task_id] = self._cost.get(task_id, 0) + (cost_upper_bound or 0)
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1


class UsageRecorder:
    """Append JSONL records to a controlled workspace-relative file."""
    def __init__(self, workspace_root: Path, path: str = "usage/usage.jsonl"):
        self.workspace_root = Path(workspace_root)
        self.path = path
        self._lock = Lock()
        validate_workspace_path(self.workspace_root, path)

    def record(self, task_id: str, executor: str, status: str, metrics: UsageMetrics):
        entry = {"task_id": task_id, "executor": executor, "status": status,
                 "usage_metrics": asdict(metrics)}
        with self._lock:
            path = validate_workspace_path(self.workspace_root, self.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path = validate_workspace_path(self.workspace_root, self.path)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + "\n")


def policy_from_config(config: dict) -> BudgetPolicy:
    """Load the policy from a parsed project config; unknown fields are rejected."""
    if not isinstance(config, dict):
        raise ValueError("budget config must be an object")
    try:
        config = dict(config)
        if config.pop("schema_version", "0.1.0") != "0.1.0":
            raise ValueError("unsupported budget config version")
        return BudgetPolicy(**config)
    except TypeError as exc:
        raise ValueError("invalid budget configuration") from exc
