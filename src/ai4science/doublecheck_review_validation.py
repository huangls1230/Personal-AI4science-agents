"""Read-only Doublecheck artifact checks, not an isolation or scientific verifier.

All supplied paths are workspace-relative. Source findings and supporting evidence
must be explicitly authorized by the caller. The manifest's order, fingerprints
and isolation label are declarations only: they cannot establish access control,
actual order, blind review, independent reasoning, or scientific correctness.
These path checks do not prevent filesystem race conditions.
"""
import json
import re
from pathlib import Path

from .contracts import ArtifactReference, validate_workspace_path
from .method_review_validation import _SCHEMA, _check_schema_keywords, _line_range, _schema_valid

_ROLES = {'review_method', 'review_statistics', 'review_consistency'}
_SEVERITIES = {'critical', 'major', 'minor', 'suggestion'}
_ADJUDICATION = {'supported', 'partially_supported', 'unsupported', 'requires_more_evidence', 'out_of_scope'}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_doublecheck_review_run(workspace_root, manuscript_path, independent_review_path,
                                    argument_map_path, independent_findings_path,
                                    adjudication_path, missed_issues_path, final_report_path,
                                    phase_manifest_path, *, source_finding_paths=(),
                                    evidence_paths=()):
    """Validate saved outputs, returning diagnostic strings without writing anything.

    A version mismatch aborts before reading source findings or the adjudication.
    All evidence is confined to explicitly provided files; line locators are
    ``Lx-Ly`` for UTF-8 text and ``image`` for explicitly authorized images.
    A zero-error result checks record structure and hashes, not review quality or
    a secure enforcement of its declared timeline or context isolation.
    """
    try:
        inputs = [manuscript_path, *evidence_paths, *source_finding_paths]
        outputs = [independent_review_path, argument_map_path, independent_findings_path,
                   adjudication_path, missed_issues_path, final_report_path, phase_manifest_path]
        if len(set(inputs)) != len(inputs) or len(set(outputs)) != len(outputs):
            return ['duplicate input or output paths']
        paths = {p: validate_workspace_path(workspace_root, p, must_exist=True) for p in inputs + outputs}
        for i, out in enumerate(outputs):
            if any(paths[out] == paths[x] or paths[out].samefile(paths[x]) for x in inputs + outputs[:i]):
                return ['output paths must be independent of all inputs and other outputs']
        # Manifest is read before source findings or adjudication; even a correct
        # manifest is not proof that callers have not read them elsewhere.
        manifest = json.loads(paths[phase_manifest_path].read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('schema_version') != '1.0':
            return ['invalid phase manifest']
        if manifest.get('execution_mode') not in {'inline_skill', 'native_subagent'}:
            return ['invalid execution_mode']
        if manifest.get('independence_status') not in {'context_limited_not_enforced', 'non_blind', 'unknown', 'enforced_isolation_claimed'} or not _text(manifest.get('limitations')):
            return ['invalid independence status or missing limitations']
        if manifest.get('events') != ['pass1_frozen', 'pass2_sources_opened']:
            return ['phase events must record pass1_frozen before pass2_sources_opened']
        manuscript = ArtifactReference.from_dict(manifest.get('manuscript'))
        if manuscript.path != manuscript_path or not manuscript.verify(workspace_root):
            return ['frozen manuscript path or hash mismatch']
        frozen = manifest.get('pass1_artifacts')
        if not isinstance(frozen, list) or len(frozen) != 3:
            return ['pass1_artifacts must identify the three independent outputs']
        refs = [ArtifactReference.from_dict(item) for item in frozen]
        if {x.path for x in refs} != {independent_review_path, argument_map_path, independent_findings_path} or not all(x.verify(workspace_root) for x in refs):
            return ['pass1 output identities or frozen hashes mismatch']
        sources = manifest.get('source_reports')
        if not isinstance(sources, list):
            return ['source_reports must be an array']
        seen_roles, seen_paths = set(), set()
        for item in sources:
            if not isinstance(item, dict) or set(item) != {'reviewer_role', 'findings', 'manuscript'}:
                return ['invalid source report declaration']
            role = item['reviewer_role']
            finding_ref, manuscript_ref = ArtifactReference.from_dict(item['findings']), ArtifactReference.from_dict(item['manuscript'])
            if role not in _ROLES or role in seen_roles or finding_ref.path in seen_paths:
                return ['duplicate or invalid source reviewer or report']
            seen_roles.add(role)
            seen_paths.add(finding_ref.path)
            if finding_ref.path not in source_finding_paths or manuscript_ref.path not in {manuscript_path, *evidence_paths}:
                return ['source report or manuscript version is not explicitly authorized']
            if not finding_ref.verify(workspace_root) or not manuscript_ref.verify(workspace_root):
                return ['source report or manuscript hash mismatch']
            if manuscript_ref.sha256 != manuscript.sha256:
                return ['version conflict: source report references a different manuscript; adjudication blocked']
        if seen_paths != set(source_finding_paths):
            return ['every explicitly supplied source findings file must be declared']
        schema = json.loads(_SCHEMA.read_text(encoding='utf-8'))
        _check_schema_keywords(schema)
        lines = paths[manuscript_path].read_text(encoding='utf-8').splitlines()
        independent = json.loads(paths[independent_findings_path].read_text(encoding='utf-8'))
        records = json.loads(paths[adjudication_path].read_text(encoding='utf-8'))
        report_texts = [paths[p].read_text(encoding='utf-8') for p in (independent_review_path, argument_map_path, missed_issues_path, final_report_path)]
        sources_by_role = {item['reviewer_role']: json.loads(paths[item['findings']['path']].read_text(encoding='utf-8')) for item in sources}
    except (OSError, ValueError, TypeError, UnicodeError, KeyError, RecursionError):
        return ['invalid, unreadable or unauthorized path, schema, manifest, or JSON']

    errors = []
    for label, text in zip(('independent_review', 'argument_map', 'missed_issues', 'doublecheck_report'), report_texts):
        if not _text(text) or not re.search(r'^#{1,6}\s+\S', text, re.M):
            errors.append(f'{label} must be a nonempty Markdown document with a heading')
    allowed_evidence = {manuscript_path, *evidence_paths}

    def evidence_check(evidence, label):
        if not isinstance(evidence, list):
            errors.append(f'{label} must be an evidence array')
            return
        for item in evidence:
            try:
                if not isinstance(item, dict) or set(item) != {'schema_version', 'artifact', 'description', 'locator'} or item['schema_version'] != '1.0' or not _text(item['description']):
                    raise ValueError('bad evidence')
                ref = ArtifactReference.from_dict(item['artifact'])
                if ref.path not in allowed_evidence:
                    errors.append(f'{label} evidence is not explicitly authorized')
                    continue
                if not ref.verify(workspace_root):
                    errors.append(f'{label} evidence hash mismatch')
                path = paths[ref.path]
                if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
                    if item['locator'] != 'image':
                        errors.append(f'{label} image evidence locator must be image')
                else:
                    n = len(path.read_text(encoding='utf-8').splitlines())
                    if not _line_range(item['locator'], n):
                        errors.append(f'{label} invalid text evidence locator')
            except (ValueError, OSError, UnicodeError, TypeError, KeyError):
                errors.append(f'{label} invalid evidence')

    def check_findings(items, role, label):
        found = {}
        if not isinstance(items, list):
            errors.append(f'{label} must be an array')
            return found
        for i, item in enumerate(items):
            tag = f'{label}[{i}]'
            try:
                if not _schema_valid(item, schema, schema):
                    errors.append(f'{tag} fails Review Finding Schema')
                    continue
                if item['reviewer_role'] != role:
                    errors.append(f'{tag} wrong reviewer_role')
                ident = item['finding_id']
                if ident in found:
                    errors.append(f'{tag} duplicate finding_id for reviewer')
                found[ident] = item
                if not _line_range(item['source_location'], len(lines)):
                    errors.append(f'{tag} source_location not in manuscript')
                evidence_check(item['evidence_location'], tag)
            except (ValueError, KeyError, TypeError, RecursionError):
                errors.append(f'{tag} invalid finding or unsupported schema')
        return found

    check_findings(independent, 'review_doublecheck', 'independent_findings')
    original = {(role, ident): item for role, items in sources_by_role.items()
                for ident, item in check_findings(items, role, f'{role}_findings').items()}
    if not isinstance(records, dict) or records.get('schema_version') != '1.0' or not isinstance(records.get('adjudications'), list):
        errors.append('invalid adjudication envelope')
        return errors
    observed = set()
    required = {'source_finding_id', 'original_reviewer', 'original_severity', 'original_claim', 'original_evidence',
                'independent_assessment', 'adjudication_status', 'final_severity', 'supporting_evidence',
                'contradicting_evidence', 'reasoning', 'recommended_action', 'verification_limitations'}
    for i, row in enumerate(records['adjudications']):
        label = f'adjudications[{i}]'
        if not isinstance(row, dict) or not required <= row.keys():
            errors.append(f'{label} missing required fields')
            continue
        if any(not _text(row[k]) for k in ('source_finding_id', 'original_reviewer', 'original_severity', 'original_claim', 'independent_assessment', 'adjudication_status', 'final_severity', 'reasoning', 'recommended_action', 'verification_limitations')):
            errors.append(f'{label} has empty required fields')
            continue
        key = (row['original_reviewer'], row['source_finding_id'])
        if key in observed:
            errors.append(f'{label} duplicate source finding reference')
        observed.add(key)
        original_finding = original.get(key)
        if original_finding is None:
            errors.append(f'{label} does not reference a valid source finding')
        elif (row['original_severity'] != original_finding['severity'] or row['original_claim'] != original_finding['claim_or_observation'] or row['original_evidence'] != original_finding['evidence_location']):
            errors.append(f'{label} does not preserve original claim, severity and evidence')
        if row['adjudication_status'] not in _ADJUDICATION or row['final_severity'] not in _SEVERITIES:
            errors.append(f'{label} invalid status or final severity')
        for field in ('supporting_evidence', 'contradicting_evidence'):
            evidence_check(row[field], f'{label}.{field}')
        if row['adjudication_status'] in {'supported', 'partially_supported', 'unsupported'} and not (row['supporting_evidence'] or row['contradicting_evidence']):
            errors.append(f'{label} adjudication requires traceable evidence')
    for key, item in original.items():
        if item['severity'] in {'major', 'critical'} and key not in observed:
            errors.append(f'major/critical finding {key[0]}:{key[1]} has not been adjudicated')
    return errors
