"""Validate a terminology proposal against its source without interpreting science.

This module only checks recorded data; it does not generate, approve, or apply
changes. Shared workspace path checks are not a concurrent filesystem sandbox.
"""

import json
from pathlib import Path
from typing import Any

from .contracts import create_artifact, validate_workspace_path


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_terminology_run(workspace_root: Path, input_path: str, changes_path: str) -> list[str]:
    """Return non-sensitive errors on a terminology proposal and source.

    Checks of this format cannot identify scientific or mathematical meaning,
    confirm execution provenance, or substitute for human approval.
    """
    errors: list[str] = []
    try:
        source = validate_workspace_path(workspace_root, input_path, must_exist=True)
        changes_file = validate_workspace_path(workspace_root, changes_path, must_exist=True)
        if source == changes_file:
            return ['changes path must be different from input path']
        artifact = create_artifact(workspace_root, input_path)
        lines = source.read_text(encoding='utf-8').splitlines()
    except (OSError, ValueError, UnicodeError):
        return ['input or changes path is invalid or input is unreadable']
    try:
        data = json.loads(changes_file.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return ['changes are unreadable or invalid JSON']
    if not isinstance(data, dict):
        return ['changes document must be an object']
    if data.get('schema_version') != '0.1':
        errors.append('schema_version must be 0.1')
    for field in ('task_id', 'review_scope'):
        if not _nonempty_text(data.get(field)):
            errors.append(f'{field} must be a non-empty string')
    if data.get('execution_mode') not in ('native_subagent', 'inline'):
        errors.append('execution_mode must be native_subagent or inline')
    manuscript = data.get('manuscript')
    if not isinstance(manuscript, dict):
        errors.append('manuscript must be an object')
    else:
        if manuscript.get('path') != input_path:
            errors.append('manuscript.path must match the input path')
        if manuscript.get('sha256') != artifact.sha256:
            errors.append('manuscript.sha256 must match the input content')
    changes = data.get('changes')
    if not isinstance(changes, list):
        errors.append('changes must be an array')
        return errors
    seen_ids: set[str] = set()
    for index, change in enumerate(changes):
        label = f'changes[{index}]'
        if not isinstance(change, dict):
            errors.append(f'{label} must be an object')
            continue
        for field in ('issue_id', 'original_term', 'reason'):
            if not _nonempty_text(change.get(field)):
                errors.append(f'{label}.{field} must be a non-empty string')
        issue_id = change.get('issue_id')
        if _nonempty_text(issue_id):
            if issue_id in seen_ids:
                errors.append(f'{label}.issue_id must be unique')
            seen_ids.add(issue_id)
        if 'suggested_term' not in change or (change['suggested_term'] is not None and not _nonempty_text(change['suggested_term'])):
            errors.append(f'{label}.suggested_term must be null or a non-empty string')
        for field, options in (('semantic_risk', ('low', 'medium', 'high')),
                               ('status', ('proposed', 'approved', 'rejected'))):
            if change.get(field) not in options:
                errors.append(f'{label}.{field} has an invalid value')
        if type(change.get('approval_required')) is not bool:
            errors.append(f'{label}.approval_required must be a boolean')
        if change.get('semantic_risk') == 'high' and change.get('approval_required') is not True:
            errors.append(f'{label} requires author approval for high semantic risk')
        location = change.get('location')
        if not isinstance(location, dict):
            errors.append(f'{label}.location must be an object')
            continue
        for field in ('section', 'quote'):
            if not _nonempty_text(location.get(field)):
                errors.append(f'{label}.location.{field} must be a non-empty string')
        start, end = location.get('start_line'), location.get('end_line')
        valid_range = type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)
        quote = location.get('quote')
        if not valid_range:
            errors.append(f'{label}.location line range must be within the source')
        elif _nonempty_text(quote) and quote not in '\n'.join(lines[start - 1:end]):
            errors.append(f'{label}.location.quote must appear exactly in the line range')
        term = change.get('original_term')
        if _nonempty_text(term) and _nonempty_text(quote) and term not in quote:
            errors.append(f'{label}.original_term must appear exactly in the quote')
    return errors


def validate_glossary_data(workspace_root: Path, input_path: str, data: dict) -> list[str]:
    """Validate parsed glossary data and literal source anchors; never parse YAML.

    Counts are consistency checks on the supplied locations, not proof that all
    manuscript occurrences have been found. Approval and verification statuses
    are claims in the artifact and do not constitute proof of human action.
    """
    try:
        source = validate_workspace_path(workspace_root, input_path, must_exist=True)
        artifact = create_artifact(workspace_root, input_path)
        lines = source.read_text(encoding='utf-8').splitlines()
    except (OSError, ValueError, UnicodeError):
        return ['input path is invalid or input is unreadable']
    if not isinstance(data, dict):
        return ['glossary must be an object']
    errors: list[str] = []
    if data.get('schema_version') != '0.1':
        errors.append('schema_version must be 0.1')
    manuscript = data.get('manuscript')
    if not isinstance(manuscript, dict):
        errors.append('manuscript must be an object')
    else:
        if manuscript.get('path') != input_path:
            errors.append('manuscript.path must match the input path')
        if manuscript.get('sha256') != artifact.sha256:
            errors.append('manuscript.sha256 must match the input content')
    terms = data.get('terms')
    if not isinstance(terms, list):
        errors.append('terms must be an array')
        return errors
    for i, entry in enumerate(terms):
        label = f'terms[{i}]'
        if not isinstance(entry, dict):
            errors.append(f'{label} must be an object')
            continue
        for field in ('canonical_term', 'category', 'rationale'):
            if not _nonempty_text(entry.get(field)):
                errors.append(f'{label}.{field} must be a non-empty string')
        for field in ('definition', 'abbreviation'):
            if field not in entry or (entry[field] is not None and not _nonempty_text(entry[field])):
                errors.append(f'{label}.{field} must be null or a non-empty string')
        for field in ('observed_variants', 'allowed_variants', 'ambiguous_variants'):
            value = entry.get(field)
            if not isinstance(value, list) or any(not _nonempty_text(item) for item in value):
                errors.append(f'{label}.{field} must be an array of non-empty strings')
        for field, options in (('verification_status', ('unverified', 'verified', 'unknown')),
                               ('approval_status', ('proposed', 'approved', 'rejected'))):
            if entry.get(field) not in options:
                errors.append(f'{label}.{field} has an invalid value')
        first = entry.get('first_occurrence')
        first_valid = isinstance(first, dict)
        if not first_valid:
            errors.append(f'{label}.first_occurrence must be an object')
        else:
            first_line = first.get('line')
            if type(first_line) is not int or not 1 <= first_line <= len(lines):
                errors.append(f'{label}.first_occurrence.line must be within the source')
                first_valid = False
            if not _nonempty_text(first.get('section')):
                errors.append(f'{label}.first_occurrence.section must be a non-empty string')
                first_valid = False
        locations = entry.get('occurrence_locations')
        count = entry.get('occurrences')
        if type(count) is not int or count < 0:
            errors.append(f'{label}.occurrences must be a nonnegative integer')
        if not isinstance(locations, list):
            errors.append(f'{label}.occurrence_locations must be an array')
            continue
        if type(count) is int and count >= 0 and count != len(locations):
            errors.append(f'{label}.occurrences must equal the number of locations')
        if not locations:
            errors.append(f'{label}.occurrence_locations must include the first occurrence')
        valid_locations = []
        for j, location in enumerate(locations):
            loc_label = f'{label}.occurrence_locations[{j}]'
            if not isinstance(location, dict):
                errors.append(f'{loc_label} must be an object')
                continue
            line_number = location.get('line')
            valid_line = type(line_number) is int and 1 <= line_number <= len(lines)
            if not valid_line:
                errors.append(f'{loc_label}.line must be within the source')
            for field in ('section', 'term', 'context'):
                if not _nonempty_text(location.get(field)):
                    errors.append(f'{loc_label}.{field} must be a non-empty string')
            term, context = location.get('term'), location.get('context')
            if valid_line:
                valid_locations.append(location)
                for field, value in (('term', term), ('context', context)):
                    if _nonempty_text(value) and value not in lines[line_number - 1]:
                        errors.append(f'{loc_label}.{field} must appear exactly on the source line')
            if _nonempty_text(term) and _nonempty_text(context) and term not in context:
                errors.append(f'{loc_label}.term must appear exactly in context')
        if first_valid and valid_locations:
            earliest = min(location['line'] for location in valid_locations)
            if first['line'] != earliest or not any(
                location['line'] == earliest and location.get('section') == first['section']
                for location in valid_locations
            ):
                errors.append(f'{label}.first_occurrence must match an earliest location')
    return errors
