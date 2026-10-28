"""Model contracts and an offline mock; no provider connections are made."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol
import math

from .contracts import UsageMetrics


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    provider: str
    context_length: int | None
    capabilities: tuple[str, ...] = ()
    available: bool = False
    implemented: bool = False
    allowed_sensitivities: tuple[str, ...] = ("public",)
    schema_version: str = "1.0"

    def __post_init__(self):
        if not self.model_id or not self.provider or self.schema_version != "1.0":
            raise ValueError("invalid model descriptor")
        if self.context_length is not None and (type(self.context_length) is not int or self.context_length < 1):
            raise ValueError("invalid context length")


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None
    schema_version: str = "1.0"


@dataclass(frozen=True)
class ModelResult:
    model_id: str
    provider: str
    status: str
    text: str = ""
    error: str | None = None
    usage_metrics: UsageMetrics = field(default_factory=UsageMetrics)
    schema_version: str = "1.0"


class ModelAdapter(Protocol):
    descriptor: ModelDescriptor
    def invoke(self, request: ModelRequest) -> ModelResult: ...


class MockModel:
    """No real inference, networking, tokenization, or provider costs."""
    def __init__(self, descriptor: ModelDescriptor | None = None):
        self.descriptor = descriptor or ModelDescriptor(
            "mock-model", "local-mock", None, ("text",), True, True)

    def invoke(self, request: ModelRequest) -> ModelResult:
        d = self.descriptor
        if not d.available or not d.implemented:
            return ModelResult(d.model_id, d.provider, "unavailable", error="model unavailable")
        if (request.schema_version != "1.0" or not isinstance(request.prompt, str)
                or not isinstance(request.parameters, dict)):

            return ModelResult(d.model_id, d.provider, "failed", error="invalid model request")
        if request.timeout_seconds is not None and (not isinstance(request.timeout_seconds, (int, float))
                or isinstance(request.timeout_seconds, bool) or not math.isfinite(request.timeout_seconds)):
            return ModelResult(d.model_id, d.provider, "failed", error="invalid timeout")
        if request.timeout_seconds is not None and request.timeout_seconds <= 0:
            return ModelResult(d.model_id, d.provider, "timeout", error="deadline already elapsed")
        return ModelResult(d.model_id, d.provider, "completed", text="MOCK: " + request.prompt,
                           usage_metrics=UsageMetrics(input_bytes=len(request.prompt.encode("utf-8")),
                                                      output_bytes=len(("MOCK: " + request.prompt).encode("utf-8"))))
