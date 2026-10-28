"""Executor boundaries. No subprocess, network, or background orchestration."""
from __future__ import annotations
from pathlib import Path
from typing import Protocol

from .budget import BudgetExceeded, BudgetGuard, BudgetPolicy, UsageRecorder
from .contracts import (EvidenceReference, ExecutionRequest, ExecutionResult,
                        ExecutorCapabilities, UsageMetrics, create_artifact,
                        validate_workspace_path)


class ExecutorAdapter(Protocol):
    capabilities: ExecutorCapabilities
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


def _result(request: ExecutionRequest, status: str, *, summary: str = "",
            errors: tuple[str, ...] = (), metrics: UsageMetrics | None = None,
            evidence: tuple[EvidenceReference, ...] = ()) -> ExecutionResult:
    return ExecutionResult(task_id=request.task.task_id, executor=request.executor, status=status,
                           summary=summary, errors=errors, evidence=evidence,
                           usage_metrics=metrics or UsageMetrics(),
                           approval_status="pending" if status == "approval_required" else "not_required")


class _LocalAdapter:
    def __init__(self, workspace_root: Path, *, guard: BudgetGuard | None = None,
                 recorder: UsageRecorder | None = None):
        self.root = Path(workspace_root)
        self.guard = guard or BudgetGuard(BudgetPolicy())
        self.recorder = recorder

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.executor != self.capabilities.executor:
            return _result(request, "blocked", errors=("executor does not match adapter",))
        if request.task.status not in ("pending", "running"):
            return _result(request, "blocked", errors=("task is not executable in its current state",))
        if request.task.sensitivity not in self.capabilities.allowed_sensitivities:
            return _result(request, "blocked", errors=("sensitivity not permitted",))
        if not set(request.task.required_capabilities).issubset(self.capabilities.capabilities):
            return _result(request, "blocked", errors=("required capability unavailable",))
        if request.model is not None:
            return _result(request, "blocked", errors=("adapter does not invoke models",))
        try:
            with self.guard.reserve(request.task.task_id, request.attempt, token_upper_bound=0, cost_upper_bound=0, model_calls_upper_bound=0):
                request.validate(self.root)
                result = self._run(request)
        except BudgetExceeded as exc:
            result = _result(request, exc.disposition, errors=(str(exc),))
        except (ValueError, OSError) as exc:
            result = _result(request, "failed", errors=(str(exc),))
        if self.recorder is not None:
            try:
                self.recorder.record(result.task_id, result.executor, result.status, result.usage_metrics)
            except (ValueError, OSError) as exc:
                return _result(request, "failed", errors=("usage recording failed: " + str(exc),))
        return result

    def _run(self, request: ExecutionRequest) -> ExecutionResult:
        raise NotImplementedError


class ScriptAdapter(_LocalAdapter):
    """Only hashes one existing verified workspace file. No user-provided commands.

    This operation is read-only and safe to retry, assuming immutable input bytes.
    """
    capabilities = ExecutorCapabilities("script", ("sha256",), True, True,
                                        ("public", "internal", "sensitive"))

    def _run(self, request: ExecutionRequest) -> ExecutionResult:
        task = request.task
        if task.task_type != "sha256" or len(task.input_artifacts) != 1 or task.output_artifacts:
            raise ValueError("sha256 requires exactly one input and no output files")
        ref = task.input_artifacts[0]
        actual = create_artifact(self.root, ref.path)
        if actual.sha256 != ref.sha256:
            raise ValueError("input changed while executing")
        path = validate_workspace_path(self.root, ref.path, must_exist=True)
        return _result(request, "completed", summary="sha256: " + actual.sha256,
                       evidence=(EvidenceReference(actual, "SHA-256 of input file"),),
                       metrics=UsageMetrics(model_calls=0, input_bytes=path.stat().st_size))


class MockExecutor(_LocalAdapter):
    capabilities = ExecutorCapabilities("mock", ("mock",), True, True,
                                        ("public", "internal", "sensitive"))

    def _run(self, request: ExecutionRequest) -> ExecutionResult:
        if request.task.task_type != "mock" or request.task.output_artifacts:
            raise ValueError("mock only accepts mock tasks without output files")
        return _result(request, "completed", summary="Offline mock result; no research was performed.",
                       metrics=UsageMetrics(model_calls=0))


class CodexNativeAdapter:
    """Placeholder. The enclosing Codex session delegates; Python cannot invoke it."""
    capabilities = ExecutorCapabilities("codex_native", (), False, False)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _result(request, "blocked", errors=("Codex native delegation is not wired to Python",))


class ExternalHarnessAdapter:
    """Placeholder; availability requires a real, permission-checked integration."""
    capabilities = ExecutorCapabilities("external_harness", (), False, False)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return _result(request, "blocked", errors=("external harness is not implemented",))
