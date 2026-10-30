"""Read-only checks for methodology-review artifacts, not scientific judgment.

The three outputs must already exist, be distinct from one another and all
authorized inputs, and lie inside the workspace. This module never writes files.
The assumptions YAML is deliberately restricted to JSON syntax (a YAML 1.2
subset), avoiding an optional YAML dependency and unsafe object constructors.
Only Markdown/text evidence with line locators ``L1-L2`` is supported. Finding
structure is evaluated against the actual team schema using its present keyword
subset; unknown schema keywords fail closed. File identity and SHA-256 do not
prove relevance or scientific accuracy. Workspace checks are not an OS sandbox
and do not prevent concurrent filesystem replacement.
"""

import json
import re
from pathlib import Path
from typing import Any

from .contracts import ArtifactReference, validate_workspace_path

_SCHEMA = Path(__file__).resolve().parents[2] / 'teams/strict_review/review-finding.schema.json'
_KEYWORDS = {'$schema', '$defs', '$ref', 'title', 'description', 'type', 'additionalProperties',
             'required', 'properties', 'const', 'enum', 'minLength', 'pattern', 'items',
             'minItems', 'allOf', 'if', 'then'}
_ASSUMPTION_FIELDS = {'assumption_id', 'assumption_description', 'explicit_or_implicit',
                      'source_location', 'why_required', 'evidence_support', 'failure_condition',
                      'impact_if_violated', 'suggested_validation', 'verification_status',
                      'reporting_status'}
_STATUSES = {'verified', 'potential', 'insufficient_information', 'not_checked'}


def _check_schema_keywords(schema: dict) -> None:
    """Reject unsupported keywords even inside an unvisited schema branch."""
    if not isinstance(schema, dict) or set(schema) - _KEYWORDS:
        raise ValueError('unsupported finding schema keyword')
    for key in ('$defs', 'properties'):
        for nested in schema.get(key, {}).values():
            _check_schema_keywords(nested)
    for key in ('items', 'if', 'then'):
        if key in schema:
            _check_schema_keywords(schema[key])
    for nested in schema.get('allOf', ()):
        _check_schema_keywords(nested)


def _schema_valid(value: Any, schema: dict, root: dict) -> bool:
    """Evaluate exactly the known keywords used by the current finding schema."""
    if not isinstance(schema, dict) or set(schema) - _KEYWORDS:
        raise ValueError('unsupported finding schema keyword')
    if '$ref' in schema:
        ref = schema['$ref']
        if not isinstance(ref, str) or not ref.startswith('#/$defs/'):
            raise ValueError('unsupported finding schema reference')
        return _schema_valid(value, root['$defs'][ref.split('/')[-1]], root)
    kind = schema.get('type')
    types = {'object': dict, 'array': list, 'string': str}
    if kind is not None and (kind not in types or not isinstance(value, types[kind])):
        return False
    if 'const' in schema and value != schema['const']:
        return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if isinstance(value, str) and (len(value) < schema.get('minLength', 0) or
                                   ('pattern' in schema and not re.search(schema['pattern'], value))):
        return False
    if isinstance(value, list) and (len(value) < schema.get('minItems', 0) or
                                    ('items' in schema and not all(_schema_valid(x, schema['items'], root) for x in value))):
        return False
    if isinstance(value, dict):
        if not set(schema.get('required', ())) <= value.keys():
            return False
        properties = schema.get('properties', {})
        if schema.get('additionalProperties') is False and set(value) - set(properties):
            return False
        if any(not _schema_valid(v, properties[k], root) for k, v in value.items() if k in properties):
            return False
    if any(not _schema_valid(value, part, root) for part in schema.get('allOf', ())):
        return False
    if 'if' in schema and _schema_valid(value, schema['if'], root) and 'then' in schema:
        return _schema_valid(value, schema['then'], root)
    return True


def _line_range(location: Any, count: int, allowed: tuple | None = None) -> bool:
    if not isinstance(location, str):
        return False
    match = re.fullmatch(r'L([1-9][0-9]*)-L([1-9][0-9]*)', location)
    if not match:
        return False
    start, end = map(int, match.groups())
    return start <= end <= count and (allowed is None or any(a <= start <= end <= b for a, b in allowed))


def validate_method_review_run(workspace_root: Path, manuscript_path: str, findings_path: str,
                               assumptions_path: str, report_path: str, *,
                               evidence_paths: tuple[str, ...] = (),
                               allowed_line_ranges: tuple[tuple[int, int], ...] | None = None) -> list[str]:
    """Return errors for existing artifacts; never generate, change or approve them.

    ``evidence_paths`` authorizes additional workspace files; a workspace path on
    its own is not authorization. Locators and finding source locations are line
    ranges, anchored to the manuscript unless an evidence artifact states another
    authorized path. The optional review scope applies to manuscript ranges.
    A clean result cannot establish that a source supports a claim, a finding is
    complete or an experiment was performed.
    """
    errors: list[str] = []
    try:
        paths = [manuscript_path, *evidence_paths, findings_path, assumptions_path, report_path]
        resolved = [validate_workspace_path(workspace_root, p, must_exist=True) for p in paths]
        # Resolve catches aliases and samefile additionally catches hard links.
        for i, out in enumerate(resolved[1 + len(evidence_paths):]):
            for other in resolved[:1 + len(evidence_paths) + i]:
                if out == other or out.samefile(other):
                    return ['output paths must be independent of all inputs and other outputs']
        source_lines = resolved[0].read_text(encoding='utf-8').splitlines()
        if allowed_line_ranges is not None and any(
            not isinstance(r, (tuple, list)) or len(r) != 2 or
            type(r[0]) is not int or type(r[1]) is not int or
            not 1 <= r[0] <= r[1] <= len(source_lines) for r in allowed_line_ranges
        ):
            return ['allowed_line_ranges must be valid manuscript ranges']
        allowed = {p: resolved[i] for i, p in enumerate(paths[:1 + len(evidence_paths)])}
        schema = json.loads(_SCHEMA.read_text(encoding='utf-8'))
        _check_schema_keywords(schema)
        findings = json.loads(resolved[-3].read_text(encoding='utf-8'))
        assumptions = json.loads(resolved[-2].read_text(encoding='utf-8'))
        report = resolved[-1].read_text(encoding='utf-8')
    except (OSError, ValueError, UnicodeError, RecursionError, TypeError):
        return ['invalid, unreadable or unauthorized path, schema, JSON or JSON-compatible YAML']
    if not report.strip() or not re.search(r'^#{1,6}\s+\S', report, re.MULTILINE):
        errors.append('report must contain a Markdown heading and text')
    if not isinstance(findings, list):
        errors.append('findings must be an array')
        findings = []
    ids: set[str] = set()
    for index, finding in enumerate(findings):
        label = f'findings[{index}]'
        try:
            if not _schema_valid(finding, schema, schema):
                errors.append(f'{label} fails Review Finding Schema')
                continue
        except (ValueError, KeyError, TypeError, RecursionError):
            return ['unsupported or invalid Review Finding Schema']
        if finding['reviewer_role'] != 'review_method':
            errors.append(f'{label} must use review_method role')
        ident = finding['finding_id']
        if ident in ids:
            errors.append(f'{label} finding_id must be unique')
        ids.add(ident)
        if not _line_range(finding['source_location'], len(source_lines), allowed_line_ranges):
            errors.append(f'{label} source_location is outside reviewed manuscript scope')
        for evidence in finding['evidence_location']:
            try:
                ref = ArtifactReference.from_dict(evidence['artifact'])
                if ref.path not in allowed:
                    errors.append(f'{label} evidence artifact is not authorized')
                    continue
                if not ref.verify(workspace_root):
                    errors.append(f'{label} evidence sha256 does not match')
                lines = allowed[ref.path].read_text(encoding='utf-8').splitlines()
                same_as_source = allowed[ref.path] == resolved[0] or allowed[ref.path].samefile(resolved[0])
                scope = allowed_line_ranges if same_as_source else None
                if not _line_range(evidence['locator'], len(lines), scope):
                    errors.append(f'{label} evidence locator is outside authorized source scope')
            except (ValueError, OSError, UnicodeError, TypeError):
                errors.append(f'{label} evidence is invalid or unreadable')
    if not isinstance(assumptions, dict) or set(assumptions) != {'assumptions'} or not isinstance(assumptions['assumptions'], list):
        errors.append('assumptions must be an object with an assumptions array')
        return errors
    ids = set()
    for index, item in enumerate(assumptions['assumptions']):
        label = f'assumptions[{index}]'
        if not isinstance(item, dict) or set(item) != _ASSUMPTION_FIELDS:
            errors.append(f'{label} must contain all required assumption fields')
            continue
        if any(not isinstance(value, str) or not value.strip() for value in item.values()):
            errors.append(f'{label} fields must be nonempty strings')
            continue
        if item['assumption_id'] in ids:
            errors.append(f'{label} assumption_id must be unique')
        ids.add(item['assumption_id'])
        if item['explicit_or_implicit'] not in ('explicit', 'implicit'):
            errors.append(f'{label} explicit_or_implicit is invalid')
        if item['verification_status'] not in _STATUSES:
            errors.append(f'{label} verification_status is invalid')
        if item['reporting_status'] not in ('reported', 'not_reported', 'unclear'):
            errors.append(f'{label} reporting_status is invalid')
        if not _line_range(item['source_location'], len(source_lines), allowed_line_ranges):
            errors.append(f'{label} source_location is outside reviewed manuscript scope')
    return errors
