"""Read-only, conservative checks on a proposed language-editing draft.

These checks are incomplete heuristics, not proof of meaning preservation,
author approval, provenance, or a replacement for the workspace sandbox.
"""

from collections import Counter
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from .contracts import create_artifact, validate_workspace_path


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(value: str) -> str:
    return sha256(value.encode('utf-8')).hexdigest()


def render_language_diff(workspace_root: Path, input_path: str, edited_path: str) -> str:
    """Return a unified diff for authorized workspace files without writing them.

    The diff contains manuscript text and must be handled as confidential as the source.
    Like the shared path contract, this is not a concurrent filesystem sandbox.
    """
    source = validate_workspace_path(workspace_root, input_path, must_exist=True)
    edited = validate_workspace_path(workspace_root, edited_path, must_exist=True)
    if source.samefile(edited):
        raise ValueError('input and edited paths must refer to distinct files')
    with source.open('r', encoding='utf-8', newline='') as stream:
        original_lines = stream.readlines()
    with edited.open('r', encoding='utf-8', newline='') as stream:
        edited_lines = stream.readlines()
    return ''.join(unified_diff(original_lines, edited_lines, fromfile=input_path, tofile=edited_path))


def find_anchor_candidates(workspace_root: Path, input_path: str, original_text: str,
                           original_sha256: str) -> list[tuple[int, int]]:
    """Find exact anchor positions after line shifts without applying an edit.

    The caller must independently authorize and hash the new source version;
    zero or multiple matches remain unresolved and require human review.
    """
    if not _text(original_text) or original_sha256 != _digest(original_text):
        raise ValueError('anchor text and hash must match')
    source = validate_workspace_path(workspace_root, input_path, must_exist=True)
    with source.open('r', encoding='utf-8', newline='') as stream:
        content = stream.read()
    positions = []
    offset = 0
    while True:
        found = content.find(original_text, offset)
        if found < 0:
            return positions
        start_line = content.count('\n', 0, found) + 1
        end_line = start_line + original_text.rstrip('\r\n').count('\n')
        positions.append((start_line, end_line))
        offset = found + 1


def _protected(text: str) -> dict[str, object]:
    """Extract conservative Markdown/prose markers; this is not a Markdown parser."""
    lines = text.splitlines()
    headings = []
    tables = []
    fences = []
    fence: list[str] | None = None
    fence_char = ''
    fence_len = 0
    for line in lines:
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence is not None:
            fence.append(line)
            if marker and marker.group(1)[0] == fence_char and len(marker.group(1)) >= fence_len and not line[marker.end():].strip():
                fences.append('\n'.join(fence))
                fence = None
            continue
        if marker:
            fence = [line]
            fence_char, fence_len = marker.group(1)[0], len(marker.group(1))
        elif re.match(r'^ {0,3}#{1,6}(?:\s|$)', line):
            headings.append(line)
        elif '|' in line and (line.lstrip().startswith('|') or line.rstrip().endswith('|')):
            tables.append(line)
    if fence is not None:
        fences.append('\n'.join(fence))
    for i, line in enumerate(lines):
        if i and re.match(r'^ {0,3}(?:=+|-+)\s*$', line) and lines[i - 1].strip():
            headings.append(lines[i - 1] + '\n' + line)
    patterns = {
        'formulas': r'(?s)(?<!\\)\$\$.*?(?<!\\)\$\$|(?<![\\$])\$(?!\$)[^\n$]+?(?<!\\)\$|\\\[.*?\\\]|\\\(.*?\\\)',
        'citations': r'\[[^\]\n]*@[\w:./-]+[^\]\n]*\]|\[\d+(?:\s*[,–-]\s*\d+)*\]|\[[^\]\n]+\]\[[^\]\n]*\]|\\cite\w*\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}',
        'numbers': r'(?<![\w.])[-+]?\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?%?(?![\w.])',
        'number_units': r'(?<![\w.])[-+]?\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?\s*(?:%|°[CF]|milliseconds?|ms|seconds?|sec|s|minutes?|hours?|days?|weeks?|months?|years?|time[ -]steps?|units?|Hz|kHz|MHz|GHz|mm|cm|km|m|kg|mg|g|GB|MB|KB)(?![A-Za-z])',
        'qualifiers': r'\b(?:may|might|could|suggest|suggests|suggested|indicate|indicates|indicated|not|no|never|without|unless|possibly|perhaps)\b',
    }
    result: dict[str, object] = {'headings': headings, 'tables': tables, 'fenced blocks': fences}
    for label, pattern in patterns.items():
        result[label] = Counter(re.findall(pattern, text, flags=re.IGNORECASE if label == 'qualifiers' else 0))
    return result


def validate_language_run(workspace_root: Path, input_path: str, changes_path: str, edited_path: str,
                          glossary_data: dict | None = None,
                          allowed_line_ranges: list[tuple[int, int]] | None = None) -> list[str]:
    """Validate artifacts, evidence anchors, reconstruction and protected markers.

    All paths are workspace-relative. Error messages avoid manuscript contents.
    Literal counts and regular expressions cannot prove scientific equivalence.
    When supplied, allowed_line_ranges is a caller-provided scope, independent of
    the changes document. Shared workspace checks do not guard against races.
    """
    try:
        source = validate_workspace_path(workspace_root, input_path, must_exist=True)
        changes_file = validate_workspace_path(workspace_root, changes_path, must_exist=True)
        edited_file = validate_workspace_path(workspace_root, edited_path, must_exist=True)
        if len({source, changes_file, edited_file}) != 3 or source.samefile(edited_file) or source.samefile(changes_file) or changes_file.samefile(edited_file):
            return ['input, changes and edited paths must refer to distinct files']
        artifact = create_artifact(workspace_root, input_path)
        # newline='' keeps exact bytes represented in decoded text, including CRLF.
        with source.open('r', encoding='utf-8', newline='') as stream:
            original = stream.read()
        with edited_file.open('r', encoding='utf-8', newline='') as stream:
            edited = stream.read()
        with changes_file.open('r', encoding='utf-8') as stream:
            data = json.load(stream)
    except (OSError, ValueError, UnicodeError, RecursionError):
        return ['workspace paths or artifact contents are invalid or unreadable']
    if not isinstance(data, dict):
        return ['changes document must be an object']
    errors: list[str] = []
    if data.get('schema_version') != '0.1':
        errors.append('schema_version must be 0.1')
    for field in ('task_id', 'project_id', 'editing_scope'):
        if not _text(data.get(field)):
            errors.append(f'{field} must be a non-empty string')
    for field, choices in (
        ('execution_mode', ('native_subagent', 'inline')),
        ('editing_mode', ('proofreading', 'conservative', 'academic_polishing')),
        ('language_variant', ('preserve', 'en-GB', 'en-US')),
    ):
        if data.get(field) not in choices:
            errors.append(f'{field} has an invalid value')
    manuscript = data.get('manuscript')
    if not isinstance(manuscript, dict) or manuscript.get('path') != input_path or manuscript.get('sha256') != artifact.sha256:
        errors.append('manuscript path and sha256 must match the input')
    glossary = data.get('terminology_glossary')
    if not isinstance(glossary, dict) or not _text(glossary.get('path')):
        errors.append('terminology_glossary must identify a workspace file')
    else:
        try:
            glossary_file = validate_workspace_path(workspace_root, glossary['path'], must_exist=True)
            if any(glossary_file.samefile(p) for p in (source, changes_file, edited_file)):
                errors.append('terminology_glossary must be a distinct file')
            if create_artifact(workspace_root, glossary['path']).sha256 != glossary.get('sha256'):
                errors.append('terminology_glossary.sha256 must match the file')
        except (OSError, ValueError):
            errors.append('terminology_glossary path is invalid or unreadable')
    changes = data.get('changes')
    if not isinstance(changes, list):
        errors.append('changes must be an array')
        return errors
    lines = original.splitlines(keepends=True)
    if allowed_line_ranges is not None and (not isinstance(allowed_line_ranges, list) or any(
        not isinstance(pair, (tuple, list)) or len(pair) != 2 or
        type(pair[0]) is not int or type(pair[1]) is not int or
        not 1 <= pair[0] <= pair[1] <= len(lines) for pair in allowed_line_ranges
    )):
        errors.append('allowed_line_ranges must contain valid source line ranges')
        allowed_line_ranges = []
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    seen_ids: set[str] = set()
    spans: list[tuple[int, int, str, bool]] = []
    for i, change in enumerate(changes):
        label = f'changes[{i}]'
        if not isinstance(change, dict):
            errors.append(f'{label} must be an object')
            continue
        for field in ('change_id', 'original_text', 'revised_text', 'issue_type', 'reason'):
            if not _text(change.get(field)):
                errors.append(f'{label}.{field} must be a non-empty string')
        cid = change.get('change_id')
        if _text(cid):
            if cid in seen_ids:
                errors.append(f'{label}.change_id must be unique')
            seen_ids.add(cid)
        for field, choices in (('semantic_risk', ('low', 'medium', 'high')), ('status', ('proposed', 'deferred'))):
            if change.get(field) not in choices:
                errors.append(f'{label}.{field} has an invalid value')
        for field in ('approval_required', 'applied_to_draft'):
            if type(change.get(field)) is not bool:
                errors.append(f'{label}.{field} must be a boolean')
        if change.get('semantic_risk') == 'high' and (change.get('approval_required') is not True or change.get('applied_to_draft') is not False):
            errors.append(f'{label} high-risk changes require approval and cannot be applied')
        if change.get('status') == 'deferred' and change.get('applied_to_draft') is True:
            errors.append(f'{label} deferred changes cannot be applied')
        location = change.get('source_location')
        if not isinstance(location, dict):
            errors.append(f'{label}.source_location must be an object')
            continue
        start, end = location.get('start_line'), location.get('end_line')
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            errors.append(f'{label}.source_location line range is invalid')
            continue
        if change.get('applied_to_draft') is True and allowed_line_ranges is not None and not any(
            lo <= start <= end <= hi for lo, hi in allowed_line_ranges
        ):
            errors.append(f'{label} applied change is outside the authorized scope')
        old, new = change.get('original_text'), change.get('revised_text')
        if not _text(old) or not _text(new):
            continue
        if location.get('original_sha256') != _digest(old):
            errors.append(f'{label}.source_location original_sha256 mismatch')
        region = original[offsets[start - 1]:offsets[end]]
        first = region.find(old)
        if first < 0 or region.find(old, first + 1) >= 0:
            errors.append(f'{label}.original_text must match uniquely in its line range')
            continue
        absolute = offsets[start - 1] + first
        spans.append((absolute, absolute + len(old), new, change.get('applied_to_draft') is True))
    spans.sort(key=lambda span: (span[0], span[1]))
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        errors.append('change source ranges must not overlap')
    applied = [span for span in spans if span[3]]
    rebuilt = original
    for start, end, replacement, _ in reversed(applied):
        rebuilt = rebuilt[:start] + replacement + rebuilt[end:]
    if rebuilt != edited:
        errors.append('edited manuscript must exactly match applied recorded changes')
    old_protected, new_protected = _protected(original), _protected(edited)
    for label in old_protected:
        if old_protected[label] != new_protected[label]:
            errors.append(f'protected {label} changed')
    if glossary_data is not None:
        if not isinstance(glossary_data, dict) or not isinstance(glossary_data.get('terms'), list):
            errors.append('glossary_data.terms must be an array')
        else:
            for entry in glossary_data['terms']:
                if not isinstance(entry, dict) or entry.get('approval_status') != 'approved':
                    continue
                variants = entry.get('allowed_variants', [])
                if not isinstance(variants, list):
                    errors.append('approved glossary allowed_variants must be an array')
                    continue
                terms = [entry.get('canonical_term'), entry.get('abbreviation'), *variants]
                if any(t is not None and not _text(t) for t in terms):
                    errors.append('approved glossary terms must be non-empty strings')
                    continue
                for term in set(t for t in terms if t is not None):
                    if edited.count(term) < original.count(term):
                        errors.append('an approved glossary literal occurs fewer times in the edited draft')
                        break
    return errors
