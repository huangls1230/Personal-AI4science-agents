"""Versioned, strictly validated contracts for Codex-controlled execution."""
from dataclasses import asdict, dataclass, field, fields
from hashlib import sha256
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
import math
import re

VERSION = '1.0'
T = TypeVar('T', bound='Contract')


def _text(value: Any, name: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _sequence(value: Any, name: str, item_type: type) -> None:
    if not isinstance(value, (list, tuple)) or any(not isinstance(x, item_type) for x in value):
        raise ValueError(f'{name} must be a sequence of {item_type.__name__}')
    if item_type is str and any(not x.strip() for x in value):
        raise ValueError(f'{name} cannot contain empty strings')


def _enum(value: Any, name: str, options: Tuple[str, ...]) -> None:
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {options}')


def _nonnegative(value: Any, name: str, *, integral: bool = True) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int if integral else (int, float)) or value < 0:
        raise ValueError(f'{name} must be a nonnegative number or unknown')
    if not integral and not math.isfinite(value):
        raise ValueError(f'{name} must be finite')


def validate_workspace_path(workspace_root: Path, path: str, *, must_exist: bool = False) -> Path:
    """Resolve a relative reference and reject traversal, absolute paths and symlink escapes.

    Call immediately before IO; this is not an OS sandbox against concurrent symlink changes.
    """
    _text(path, 'path')
    if '\\' in path or '\x00' in path or PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute() or PureWindowsPath(path).drive:
        raise ValueError('path must be a portable workspace-relative path')
    parts = PurePosixPath(path).parts
    if not parts or any(part in ('', '.', '..') for part in path.split('/')):
        raise ValueError('path traversal is not allowed')
    root = Path(workspace_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('workspace root must be a directory')
    try:
        resolved = (root / path).resolve(strict=must_exist)
        resolved.relative_to(root)
    except (ValueError, OSError, RuntimeError) as exc:
        raise ValueError('path escapes workspace or cannot be resolved') from exc
    if resolved == root:
        raise ValueError('path must refer to an item inside workspace')
    if must_exist and not resolved.is_file():
        raise ValueError('artifact must be a regular file')
    return resolved


def create_artifact(workspace_root: Path, path: str) -> 'ArtifactReference':
    resolved = validate_workspace_path(workspace_root, path, must_exist=True)
    digest = sha256()
    with resolved.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return ArtifactReference(path=path, sha256=digest.hexdigest())


class Contract:
    schema_version: str

    def _version(self) -> None:
        if self.schema_version != VERSION:
            raise ValueError(f'unsupported schema version: {self.schema_version!r}')

    def to_dict(self) -> Dict[str, Any]:
        def json_value(value: Any) -> Any:
            if isinstance(value, (tuple, list)):
                return [json_value(item) for item in value]
            if isinstance(value, dict):
                return {key: json_value(item) for key, item in value.items()}
            return value
        return json_value(asdict(self))

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        if not isinstance(data, dict):
            raise ValueError(f'{cls.__name__} must be an object')
        valid = {f.name for f in fields(cls)}
        if set(data) - valid:
            raise ValueError(f'unknown fields in {cls.__name__}: {sorted(set(data)-valid)}')
        if data.get('schema_version') != VERSION:
            raise ValueError('schema_version is required and must be supported')
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f'invalid {cls.__name__}: {exc}') from exc


@dataclass(frozen=True)
class ArtifactReference(Contract):
    path: str
    sha256: str
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        self._version()
        _text(self.path, 'path')
        if '\\' in self.path or '\x00' in self.path or PurePosixPath(self.path).is_absolute() or PureWindowsPath(self.path).drive or any(part in ('', '.', '..') for part in self.path.split('/')):
            raise ValueError('artifact path must be workspace-relative without traversal')
        if not isinstance(self.sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', self.sha256):
            raise ValueError('sha256 must be 64 lowercase hexadecimal characters')

    def verify(self, workspace_root: Path) -> bool:
        return create_artifact(workspace_root, self.path).sha256 == self.sha256


@dataclass(frozen=True)
class EvidenceReference(Contract):
    artifact: ArtifactReference
    description: str
    locator: Optional[str] = None
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        self._version()
        if not isinstance(self.artifact, ArtifactReference):
            raise ValueError('artifact must be an ArtifactReference')
        _text(self.description, 'description')
        _text(self.locator, 'locator', optional=True)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'EvidenceReference':
        data = dict(data)
        if 'artifact' in data:
            data['artifact'] = ArtifactReference.from_dict(data['artifact'])
        return super()._from_dict(data)


@dataclass(frozen=True)
class UsageMetrics(Contract):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    token_measurement: str = 'unknown'
    cost: Optional[float] = None
    currency: Optional[str] = None
    model_calls: Optional[int] = None
    input_bytes: Optional[int] = None
    output_bytes: Optional[int] = None
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        self._version()
        for name in ('input_tokens', 'output_tokens', 'model_calls', 'input_bytes', 'output_bytes'):
            _nonnegative(getattr(self, name), name)
        _nonnegative(self.cost, 'cost', integral=False)
        _text(self.currency, 'currency', optional=True)
        _enum(self.token_measurement, 'token_measurement', ('unknown', 'estimated', 'exact'))
        if self.token_measurement == 'unknown' and (self.input_tokens is not None or self.output_tokens is not None):
            raise ValueError('unknown token measurement cannot claim token counts')
        if self.token_measurement != 'unknown' and self.input_tokens is None and self.output_tokens is None:
            raise ValueError('token measurement requires at least one count')
        if self.cost is not None and self.currency is None:
            raise ValueError('known cost requires currency')


@dataclass(frozen=True)
class ExecutorCapabilities(Contract):
    executor: str
    capabilities: Tuple[str, ...] = ()
    available: bool = False
    implemented: bool = False
    allowed_sensitivities: Tuple[str, ...] = ('public',)
    compatible_models: Tuple[str, ...] = ()
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        self._version()
        _text(self.executor, 'executor')
        for name in ('capabilities', 'allowed_sensitivities', 'compatible_models'):
            _sequence(getattr(self, name), name, str)
        if type(self.available) is not bool or type(self.implemented) is not bool:
            raise ValueError('availability and implementation flags must be booleans')
        if self.available and not self.implemented:
            raise ValueError('unimplemented executor cannot be available')
        if any(x not in ('public', 'internal', 'sensitive') for x in self.allowed_sensitivities):
            raise ValueError('invalid sensitivity')


TRANSITIONS = {
    'pending': ('running', 'blocked', 'approval_required'),
    'running': ('completed', 'failed', 'blocked', 'approval_required'),
    'failed': ('pending',),
    'blocked': ('pending',),
    'approval_required': ('pending',),
    'completed': (),
}


def validate_transition(previous: str, following: str) -> None:
    if previous not in TRANSITIONS or following not in TRANSITIONS[previous]:
        raise ValueError(f'invalid task transition {previous!r} -> {following!r}')


@dataclass(frozen=True)
class ResearchTask(Contract):
    task_id: str
    objective: str
    task_type: str
    required_capabilities: Tuple[str, ...] = ()
    complexity: str = 'simple'
    sensitivity: str = 'public'
    executor: Optional[str] = None
    input_artifacts: Tuple[ArtifactReference, ...] = ()
    output_artifacts: Tuple[str, ...] = ()
    status: str = 'pending'
    idempotency_key: Optional[str] = None
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        self._version()
        for name in ('task_id', 'objective', 'task_type'):
            _text(getattr(self, name), name)
        _text(self.executor, 'executor', optional=True)
        _text(self.idempotency_key, 'idempotency_key', optional=True)
        _sequence(self.required_capabilities, 'required_capabilities', str)
        _sequence(self.input_artifacts, 'input_artifacts', ArtifactReference)
        _sequence(self.output_artifacts, 'output_artifacts', str)
        _enum(self.complexity, 'complexity', ('deterministic', 'simple', 'complex'))
        _enum(self.sensitivity, 'sensitivity', ('public', 'internal', 'sensitive'))
        _enum(self.status, 'status', tuple(TRANSITIONS))

    def validate(self, workspace_root: Path, *, verify_inputs: bool = True) -> None:
        for artifact in self.input_artifacts:
            validate_workspace_path(workspace_root, artifact.path, must_exist=verify_inputs)
            if verify_inputs and not artifact.verify(workspace_root):
                raise ValueError(f'artifact hash mismatch: {artifact.path}')
        for path in self.output_artifacts:
            validate_workspace_path(workspace_root, path)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'ResearchTask':
        data = dict(data)
        if 'input_artifacts' in data:
            _sequence(data['input_artifacts'], 'input_artifacts', dict)
            data['input_artifacts'] = tuple(ArtifactReference.from_dict(x) for x in data['input_artifacts'])
        return super()._from_dict(data)


@dataclass(frozen=True)
class ExecutionRequest(Contract):
    task: ResearchTask
    executor: str
    model: Optional[str] = None
    attempt: int = 1
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        self._version()
        if not isinstance(self.task, ResearchTask):
            raise ValueError('task must be a ResearchTask')
        _text(self.executor, 'executor')
        _text(self.model, 'model', optional=True)
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError('attempt must be a positive integer')
        if self.attempt > 1 and not self.task.idempotency_key:
            raise ValueError('retries require an idempotency key and external deduplication')
        if self.task.executor is not None and self.task.executor != self.executor:
            raise ValueError('request executor conflicts with task executor')

    def validate(self, workspace_root: Path, *, verify_inputs: bool = True) -> None:
        self.task.validate(workspace_root, verify_inputs=verify_inputs)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'ExecutionRequest':
        data = dict(data)
        if 'task' in data:
            data['task'] = ResearchTask.from_dict(data['task'])
        return super()._from_dict(data)


@dataclass(frozen=True)
class ExecutionResult(Contract):
    task_id: str
    executor: str
    status: str
    summary: str = ''
    output_artifacts: Tuple[ArtifactReference, ...] = ()
    evidence: Tuple[EvidenceReference, ...] = ()
    errors: Tuple[str, ...] = ()
    usage_metrics: UsageMetrics = field(default_factory=UsageMetrics)
    quality_status: str = 'not_reviewed'
    approval_status: str = 'not_required'
    schema_version: str = VERSION

    def __post_init__(self) -> None:
        self._version()
        _text(self.task_id, 'task_id')
        _text(self.executor, 'executor')
        if not isinstance(self.summary, str):
            raise ValueError('summary must be a string')
        _enum(self.status, 'status', ('completed', 'failed', 'blocked', 'approval_required'))
        _enum(self.quality_status, 'quality_status', ('not_reviewed', 'passed', 'failed'))
        _enum(self.approval_status, 'approval_status', ('not_required', 'pending', 'approved', 'rejected'))
        _sequence(self.output_artifacts, 'output_artifacts', ArtifactReference)
        _sequence(self.evidence, 'evidence', EvidenceReference)
        _sequence(self.errors, 'errors', str)
        if not isinstance(self.usage_metrics, UsageMetrics):
            raise ValueError('usage_metrics must be UsageMetrics')
        if self.status == 'completed' and self.errors:
            raise ValueError('completed execution cannot contain errors')
        if self.status != 'completed' and self.quality_status == 'passed':
            raise ValueError('only completed execution may pass quality validation')

    def validate(self, workspace_root: Path, *, verify_outputs: bool = True) -> None:
        for artifact in list(self.output_artifacts) + [e.artifact for e in self.evidence]:
            validate_workspace_path(workspace_root, artifact.path, must_exist=verify_outputs)
            if verify_outputs and not artifact.verify(workspace_root):
                raise ValueError(f'artifact hash mismatch: {artifact.path}')

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'ExecutionResult':
        data = dict(data)
        for key, item_type in (('output_artifacts', ArtifactReference), ('evidence', EvidenceReference)):
            if key in data:
                _sequence(data[key], key, dict)
                data[key] = tuple(item_type.from_dict(x) for x in data[key])
        if 'usage_metrics' in data:
            data['usage_metrics'] = UsageMetrics.from_dict(data['usage_metrics'])
        return super()._from_dict(data)
