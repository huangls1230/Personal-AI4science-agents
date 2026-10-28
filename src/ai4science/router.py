"""Deterministic recommendation only; Codex remains the scheduler."""
from __future__ import annotations
from dataclasses import dataclass

from .budget import BudgetPolicy
from .contracts import ExecutorCapabilities, ResearchTask
from .models import ModelDescriptor


@dataclass(frozen=True)
class RoutingCandidate:
    executor: ExecutorCapabilities
    kind: str  # script, codex_native, external, mock
    model_id: str | None = None
    cost_score: float = 0.5     # lower is better, normalized to [0, 1]
    speed_score: float = 0.5    # higher is better
    quality_score: float = 0.5  # higher is better
    token_upper_bound: int | None = None
    cost_upper_bound: float | None = None
    model_calls_upper_bound: int | None = None

    def __post_init__(self):
        if self.kind not in ("script", "codex_native", "external_harness", "mock"):
            raise ValueError("invalid executor kind")
        for value in (self.cost_score, self.speed_score, self.quality_score):
            if not 0 <= value <= 1:
                raise ValueError("scores must be between zero and one")


@dataclass(frozen=True)
class RoutingDecision:
    status: str
    executor: str | None = None
    model_id: str | None = None
    reason: str = ""
    candidates: tuple[str, ...] = ()


def route(task: ResearchTask, candidates: list[RoutingCandidate], models: list[ModelDescriptor],
          budget: BudgetPolicy, *, attempt: int = 1,
          preferences: dict[str, float] | None = None) -> RoutingDecision:
    """Filter hard constraints first and then rank. No execution or state mutation."""
    preferences = preferences or {"cost": 1.0, "speed": 1.0, "quality": 1.0}
    if set(preferences) != {"cost", "speed", "quality"} or any(
        not isinstance(v, (float, int)) or isinstance(v, bool) or not 0 <= v < float('inf')
        for v in preferences.values()
    ):
        raise ValueError("invalid routing preferences")
    if type(attempt) is not int or attempt < 1 or attempt - 1 > budget.max_retries:
        return RoutingDecision(budget.on_exceed, reason="retry budget exceeded")
    by_id = {m.model_id: m for m in models}
    accepted = []
    for candidate in candidates:
        caps = candidate.executor
        if not caps.available or not caps.implemented:
            continue
        if candidate.kind in ("script", "mock") and task.task_type != {"script": "sha256", "mock": "mock"}[candidate.kind]:
            continue
        if task.executor and task.executor != caps.executor:
            continue
        if not set(task.required_capabilities).issubset(caps.capabilities):
            continue
        if task.sensitivity not in caps.allowed_sensitivities:
            continue
        if candidate.model_id:
            model = by_id.get(candidate.model_id)
            if (model is None or not model.available or not model.implemented
                    or task.sensitivity not in model.allowed_sensitivities
                    or candidate.model_id not in caps.compatible_models):
                continue
        elif candidate.kind in ("codex_native", "external_harness"):
            # A model-dependent candidate must name a compatible, available model.
            continue
        if budget.max_tokens is not None and (type(candidate.token_upper_bound) is not int
                                               or not 0 <= candidate.token_upper_bound <= budget.max_tokens):
            continue
        call_bound = candidate.model_calls_upper_bound
        if call_bound is None and candidate.kind in ("script", "mock"):
            call_bound = 0
        if budget.max_model_calls is not None and (type(call_bound) is not int
                                                    or not 0 <= call_bound <= budget.max_model_calls):
            continue
        if budget.max_cost is not None and (not isinstance(candidate.cost_upper_bound, (float, int))
                                             or isinstance(candidate.cost_upper_bound, bool)
                                             or not 0 <= candidate.cost_upper_bound <= budget.max_cost):
            continue
        priority = 0
        if task.complexity == "deterministic" and candidate.kind == "script":
            priority = 1
        if task.complexity == "complex" and candidate.kind == "codex_native":
            priority = 1
        score = (preferences["speed"] * candidate.speed_score + preferences["quality"] * candidate.quality_score
                 - preferences["cost"] * candidate.cost_score)
        accepted.append((priority, score, caps.executor, candidate.model_id))
    if not accepted:
        return RoutingDecision("blocked", reason="no eligible executor satisfies hard constraints")
    accepted.sort(key=lambda item: (-item[0], -item[1], item[2], item[3] or ""))
    chosen = accepted[0]
    return RoutingDecision("recommended", chosen[2], chosen[3], "eligible executor recommended",
                           tuple(item[2] for item in accepted))


def candidates_from_config(config: dict, capabilities: dict[str, ExecutorCapabilities]) -> list[RoutingCandidate]:
    """Apply scores from config to capability records obtained from trusted adapters.

    Configuration cannot change runtime availability, implementation or permissions.
    Disabled or unknown adapters are not instantiated or returned.
    """
    if not isinstance(config, dict) or not isinstance(config.get("candidates"), list):
        raise ValueError("routing config must contain a candidates list")
    result = []
    for entry in config["candidates"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("executor"), str):
            raise ValueError("invalid routing candidate")
        if entry.get("enabled", True) is False:
            continue
        cap = capabilities.get(entry["executor"])
        if cap is None:
            continue
        allowed = {"kind", "model_id", "cost_score", "speed_score", "quality_score", "token_upper_bound", "cost_upper_bound", "model_calls_upper_bound"}
        extra = set(entry) - allowed - {"executor", "enabled"}
        if extra:
            raise ValueError("unknown routing candidate fields")
        result.append(RoutingCandidate(executor=cap, **{k: v for k, v in entry.items() if k in allowed}))
    return result


def project_candidates(routing_config: dict, executors_config: dict, models_config: dict,
                       runtime_executors: dict, runtime_models: dict, *, include_test_only: bool = False):
    """Intersect configuration with trusted runtime registries; config cannot enable code.

    runtime_executors maps IDs to (kind, ExecutorCapabilities), runtime_models maps
    IDs to ModelDescriptor. Test-only entries are excluded by default.
    """
    from dataclasses import replace
    for config in (routing_config, executors_config, models_config):
        if not isinstance(config, dict) or config.get('schema_version') != '0.1.0':
            raise ValueError('unsupported project config version')
    def entries(config, key):
        values = config.get(key)
        if not isinstance(values, list):
            raise ValueError('invalid project config entries')
        result = {}
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in result:
                raise ValueError('invalid or duplicate project config ID')
            if type(item.get('enabled')) is not bool or type(item.get('test_only', False)) is not bool:
                raise ValueError('enabled and test_only must be boolean')
            result[item['id']] = item
        return result
    executor_entries = entries(executors_config, 'executors')
    model_entries = entries(models_config, 'models')
    models = []
    for key, item in model_entries.items():
        descriptor = runtime_models.get(key)
        if (not item['enabled'] or (item.get('test_only', False) and not include_test_only)
                or descriptor is None or descriptor.model_id != key or item.get('provider') != descriptor.provider):
            continue
        model_caps = item.get('capabilities', [])
        if not isinstance(model_caps, list) or any(not isinstance(x, str) for x in model_caps):
            raise ValueError('invalid model capabilities')
        models.append(replace(descriptor, capabilities=tuple(x for x in descriptor.capabilities if x in model_caps)))
    caps = {}
    for key, item in executor_entries.items():
        runtime = runtime_executors.get(key)
        if not item['enabled'] or (item.get('test_only', False) and not include_test_only) or runtime is None:
            continue
        kind, descriptor = runtime
        if item.get('kind') != kind or descriptor.executor != key:
            continue
        allowed_caps, allowed_models = item.get('capabilities'), item.get('models')
        if not isinstance(allowed_caps, list) or not isinstance(allowed_models, list) or any(
                not isinstance(x, str) for x in allowed_caps + allowed_models):
            raise ValueError('invalid executor configuration')
        caps[key] = replace(descriptor,
                            capabilities=tuple(x for x in descriptor.capabilities if x in allowed_caps),
                            compatible_models=tuple(x for x in descriptor.compatible_models if x in allowed_models))
    routing_entries = []
    for item in routing_config.get('candidates', []):
        if not isinstance(item, dict):
            raise ValueError('invalid routing candidate')
        runtime = runtime_executors.get(item.get('executor'))
        if runtime is not None and item.get('kind') == runtime[0]:
            routing_entries.append(item)
    return candidates_from_config({'candidates': routing_entries}, caps), models
