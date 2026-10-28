"""Explicit, bounded context selection with source integrity checks."""
from dataclasses import dataclass
from pathlib import Path

from .contracts import ArtifactReference, validate_workspace_path


@dataclass(frozen=True)
class ContextManifest:
    artifacts: tuple[ArtifactReference, ...]
    max_bytes: int = 100_000
    schema_version: str = "1.0"

    def __post_init__(self):
        if self.schema_version != "1.0" or type(self.max_bytes) is not int or self.max_bytes < 0:
            raise ValueError("invalid context manifest")


class ContextSelector:
    def __init__(self, workspace_root: Path):
        self.root = Path(workspace_root)

    def load(self, manifest: ContextManifest, selected_paths: tuple[str, ...]) -> dict[str, bytes]:
        """Load only explicitly selected references; reject stale hashes and oversize input."""
        refs = {ref.path: ref for ref in manifest.artifacts}
        if len(refs) != len(manifest.artifacts) or len(set(selected_paths)) != len(selected_paths):
            raise ValueError("duplicate context path")
        result: dict[str, bytes] = {}
        total = 0
        for name in selected_paths:
            if name not in refs:
                raise ValueError("path absent from context manifest")
            path = validate_workspace_path(self.root, name, must_exist=True)
            if not path.is_file():
                raise ValueError("context is missing")
            size = path.stat().st_size
            if size > manifest.max_bytes - total:
                raise ValueError("context byte budget exceeded")
            with path.open("rb") as stream:
                data = stream.read(manifest.max_bytes - total + 1)
            total += len(data)
            if total > manifest.max_bytes:
                raise ValueError("context byte budget exceeded")
            # Verify the bytes actually returned, even if the file changed after the initial check.
            import hashlib
            if hashlib.sha256(data).hexdigest() != refs[name].sha256:
                raise ValueError("context changed during read")
            result[name] = data
        return result
