"""Check structural-review artifacts against their source, without judging science.

Paths are workspace-relative and use the project's existing artifact contract. This
validator is read-only and does not generate or approve recommendations.
"""

import json
from pathlib import Path
from typing import Any

from .contracts import create_artifact, validate_workspace_path


_ACTIONS = {'keep', 'move', 'merge', 'split', 'add_argument'}
_PRIORITIES = {'high', 'medium', 'low'}


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_structure_run(workspace_root: Path, input_path: str, plan_path: str) -> list[str]:
    """Return non-sensitive validation errors for a plan and its Markdown source.

    A passing result verifies shape, source identity and exact evidence anchoring;
    it does not establish completeness or scientific validity. Like the shared
    workspace contract, this is not a sandbox against concurrent path changes.
    """
    errors: list[str] = []
    try:
        source = validate_workspace_path(workspace_root, input_path, must_exist=True)
        plan_file = validate_workspace_path(workspace_root, plan_path, must_exist=True)
        if source == plan_file:
            return ['plan path must be different from input path']
        artifact = create_artifact(workspace_root, input_path)
        lines = source.read_text(encoding='utf-8').splitlines()
    except (OSError, ValueError, UnicodeError):
        return ['input or plan path is invalid or input is unreadable']
    try:
        plan = json.loads(plan_file.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return ['plan is unreadable or invalid JSON']
    if not isinstance(plan, dict):
        return ['plan must be an object']
    if plan.get('schema_version') != '0.1':
        errors.append('schema_version must be 0.1')
    for field in ('task_id', 'review_scope'):
        if not _nonempty_text(plan.get(field)):
            errors.append(f'{field} must be a non-empty string')
    if plan.get('execution_mode') not in ('native_subagent', 'inline'):
        errors.append('execution_mode must be native_subagent or inline')
    manuscript = plan.get('manuscript')
    if not isinstance(manuscript, dict):
        errors.append('manuscript must be an object')
    else:
        if manuscript.get('path') != input_path:
            errors.append('manuscript.path must match the input path')
        if manuscript.get('sha256') != artifact.sha256:
            errors.append('manuscript.sha256 must match the input content')
    findings = plan.get('findings')
    if not isinstance(findings, list):
        errors.append('findings must be an array')
        return errors
    seen_ids: set[str] = set()
    for index, finding in enumerate(findings):
        label = f'findings[{index}]'
        if not isinstance(finding, dict):
            errors.append(f'{label} must be an object')
            continue
        for field in ('id', 'issue_type', 'recommendation', 'rationale'):
            if not _nonempty_text(finding.get(field)):
                errors.append(f'{label}.{field} must be a non-empty string')
        finding_id = finding.get('id')
        if _nonempty_text(finding_id):
            if finding_id in seen_ids:
                errors.append(f'{label}.id must be unique')
            seen_ids.add(finding_id)
        for field, options in (('priority', _PRIORITIES), ('action', _ACTIONS)):
            value = finding.get(field)
            if not isinstance(value, str) or value not in options:
                errors.append(f'{label}.{field} has an invalid value')
        for field in ('may_change_scientific_meaning', 'author_approval_required'):
            if type(finding.get(field)) is not bool:
                errors.append(f'{label}.{field} must be a boolean')
        if finding.get('may_change_scientific_meaning') is True and finding.get('author_approval_required') is not True:
            errors.append(f'{label} requires author approval for scientific meaning risk')
        location = finding.get('location')
        if not isinstance(location, dict):
            errors.append(f'{label}.location must be an object')
            continue
        for field in ('section', 'quote'):
            if not _nonempty_text(location.get(field)):
                errors.append(f'{label}.location.{field} must be a non-empty string')
        start, end = location.get('start_line'), location.get('end_line')
        valid_range = type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)
        if not valid_range:
            errors.append(f'{label}.location line range must be within the source')
        elif _nonempty_text(location.get('quote')) and location['quote'] not in '\n'.join(lines[start - 1:end]):
            errors.append(f'{label}.location.quote must appear exactly in the line range')
    return errors
