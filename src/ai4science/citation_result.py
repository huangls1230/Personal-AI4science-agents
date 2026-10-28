"""Citation result envelope; execution, verification and authorization stay separate."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import ArtifactReference, ExecutionResult, UsageMetrics, validate_workspace_path
from .citation_metadata import validate_citation_record

_FIELDS = {'schema_version', 'task_id', 'operation', 'execution_status', 'affected_records',
           'proposed_changes', 'applied_changes', 'exported_artifacts', 'verification_results',
           'warnings', 'errors', 'usage_metrics', 'execution'}
def validate_citation_result(result: dict[str, Any], workspace_root: Path, *,
                             verify_files: bool = True) -> None:
    """Validate the envelope and project contracts; does not prove claims or authorization.

    V0.1 supports only dry-run mutation proposals; actual applied changes are
    therefore rejected even if a caller asserts that a write succeeded.
    """
    if not isinstance(result, dict) or set(result) != _FIELDS:
        raise ValueError('CitationResult requires exactly the documented fields')
    if result['schema_version'] != '1.0':
        raise ValueError('unsupported CitationResult schema_version')
    for name in ('task_id', 'operation'):
        if not isinstance(result[name], str) or not result[name].strip():
            raise ValueError(f'{name} must be a nonempty string')
    if result['execution_status'] not in ('completed', 'failed', 'blocked', 'approval_required'):
        raise ValueError('invalid execution_status')
    for name in ('affected_records', 'proposed_changes', 'applied_changes', 'verification_results'):
        if not isinstance(result[name], list) or any(not isinstance(v, dict) for v in result[name]):
            raise ValueError(f'{name} must be a list of objects')
    if result['applied_changes']:
        raise ValueError('applied changes are unsupported: Zotero and Vault writes are not implemented')
    for name in ('warnings', 'errors'):
        if not isinstance(result[name], list) or any(not isinstance(v, str) or not v.strip() for v in result[name]):
            raise ValueError(f'{name} must be a list of nonempty strings')
    if not isinstance(result['exported_artifacts'], list):
        raise ValueError('exported_artifacts must be a list')
    exports = [ArtifactReference.from_dict(value) for value in result['exported_artifacts']]
    usage = UsageMetrics.from_dict(result['usage_metrics'])
    execution = ExecutionResult.from_dict(result['execution'])
    if (execution.task_id != result['task_id'] or execution.status != result['execution_status']
            or execution.usage_metrics != usage or list(execution.errors) != result['errors']):
        raise ValueError('embedded execution task, status, usage and errors must match CitationResult')
    if any(ref not in execution.output_artifacts for ref in exports):
        raise ValueError('exported artifacts must be referenced by embedded execution')
    for record in result['affected_records']:
        validate_citation_record(record, workspace_root)
        if verify_files and record['reading_card_path'] is not None:
            validate_workspace_path(workspace_root, record['reading_card_path'], must_exist=True)
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('CitationResult must contain finite JSON values') from exc
    if verify_files:
        execution.validate(workspace_root)
