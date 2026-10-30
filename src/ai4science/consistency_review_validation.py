"""Read-only consistency-review indexing and structural provenance checks.

The index reports literal Markdown references, never scientific facts. A valid
manifest records an inspection assertion, not independent proof a person/model
actually viewed a figure. The checks are not an OS sandbox against concurrent
filesystem changes and never establish scientific correctness or execution.
"""
import json
import re
from pathlib import Path

from .contracts import ArtifactReference, create_artifact, validate_workspace_path
from .method_review_validation import _SCHEMA, _check_schema_keywords, _schema_valid, _line_range


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def index_markdown(workspace_root, manuscript_path):
    """Index literal headings, image links and numbered references outside code.

    Only the explicitly supplied Markdown is read. Matches are candidates, not
    complete parsing or proof of existence. Image paths are never dereferenced.
    """
    path = validate_workspace_path(workspace_root, manuscript_path, must_exist=True)
    lines = path.read_text(encoding='utf-8').splitlines()
    headings, images, references = [], [], []
    fence = None
    for number, line in enumerate(lines, 1):
        m = re.match(r'^\s*(`{3,}|~{3,})', line)
        if m:
            token = m.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            continue
        if fence:
            continue
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
        if heading:
            headings.append({'level': len(heading[1]), 'title': heading[2], 'line': number})
        for image in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', line):
            images.append({'alt': image[1], 'target': image[2], 'line': number})
        for ref in re.finditer(r'\b(Fig(?:ure)?\.?|Table|Eq(?:uation)?\.?)\s*\(?([0-9]+)\)?', line, re.I):
            references.append({'text': ref[0], 'kind': ref[1], 'number': ref[2], 'line': number})
    return {'headings': headings, 'images': images, 'references': references,
            'limitations': 'Literal patterns only; not a complete Markdown, equation or visual parser.'}


def validate_consistency_review_run(workspace_root, manuscript_path, findings_path, claims_path,
                                    inventory_path, crossrefs_path, visual_path, report_path, *,
                                    evidence_paths=()):
    """Validate existing outputs without writing or running any supplied code.

    The manuscript and the explicitly listed evidence paths are the only sources
    authorized for this call. Missing evidence may be listed but must be declared
    in evidence_paths. Structured validity does not attest observation or truth.
    Source locations use manuscript Lx-Ly; evidence for text also uses lines,
    while authorized images use the exact locator 'image'.
    """
    errors = []
    try:
        inputs = [manuscript_path, *evidence_paths]
        if len(inputs) != len(set(inputs)):
            return ['duplicate input paths']
        resolved_inputs = [validate_workspace_path(workspace_root, p, must_exist=(i == 0))
                           for i, p in enumerate(inputs)]
        outputs = [findings_path, claims_path, inventory_path, crossrefs_path, visual_path, report_path]
        resolved_outputs = [validate_workspace_path(workspace_root, p, must_exist=True) for p in outputs]
        for i, out in enumerate(resolved_outputs):
            if any(out == p or (p.exists() and out.samefile(p)) for p in resolved_inputs + resolved_outputs[:i]):
                return ['output paths must be independent of all inputs and other outputs']
        allowed = dict(zip(inputs, resolved_inputs))
        source_lines = resolved_inputs[0].read_text(encoding='utf-8').splitlines()
        findings, claims, inventory, crossrefs, visual = [json.loads(p.read_text(encoding='utf-8')) for p in resolved_outputs[:5]]
        report = resolved_outputs[-1].read_text(encoding='utf-8')
        schema = json.loads(_SCHEMA.read_text(encoding='utf-8'))
        _check_schema_keywords(schema)
    except (OSError, ValueError, UnicodeError, TypeError, RecursionError):
        return ['invalid, unreadable or unauthorized path, schema, or JSON']
    if not _text(report) or not re.search(r'^#{1,6}\s+\S', report, re.M):
        errors.append('report must contain a Markdown heading and text')

    def envelope(value, key):
        if not isinstance(value, dict) or value.get('schema_version') != '1.0' or not isinstance(value.get(key), list):
            errors.append(f'{key} invalid envelope')
            return []
        return value[key]

    items = envelope(inventory, 'artifacts')
    inventory_by_id = {}
    for i, item in enumerate(items):
        label = f'artifacts[{i}]'
        keys = ('artifact_id', 'source_path', 'artifact_type', 'document_section', 'page_or_location', 'extraction_method', 'verification_status')
        if not isinstance(item, dict) or 'source_hash' not in item or any(not _text(item.get(k)) for k in keys):
            errors.append(f'{label} missing fields')
            continue
        ident, name = item['artifact_id'], item['source_path']
        if ident in inventory_by_id:
            errors.append(f'{label} duplicate artifact_id')
        inventory_by_id[ident] = item
        if name not in allowed:
            errors.append(f'{label} source not authorized')
            continue
        path = allowed[name]
        state = item['verification_status']
        if state not in ('available', 'missing'):
            errors.append(f'{label} invalid verification_status')
        elif state == 'missing':
            if path.exists() or item.get('source_hash') is not None:
                errors.append(f'{label} missing source must be absent and hash null')
        else:
            try:
                ref = ArtifactReference(path=name, sha256=item.get('source_hash'))
                if not ref.verify(workspace_root):
                    errors.append(f'{label} source hash mismatch')
            except (OSError, ValueError, TypeError):
                errors.append(f'{label} source invalid or unreadable')

    visual_by_id = {}
    for i, item in enumerate(envelope(visual, 'figures')):
        label = f'figures[{i}]'
        if not isinstance(item, dict) or not _text(item.get('artifact_id')):
            errors.append(f'{label} invalid figure')
            continue
        ident = item['artifact_id']
        if ident in visual_by_id:
            errors.append(f'{label} duplicate artifact_id')
        visual_by_id[ident] = item
        source = inventory_by_id.get(ident)
        if not source or source.get('artifact_type') != 'image':
            errors.append(f'{label} must reference an inventoried image')
            continue
        state = item.get('visual_review_status')
        if state not in ('checked', 'not_performed') or not _text(item.get('limitations')):
            errors.append(f'{label} invalid visual status or limitations')
        if state == 'checked':
            if source.get('verification_status') != 'available' or any(not _text(item.get(k)) for k in ('inspection_method', 'inspection_event', 'checked_content')):
                errors.append(f'{label} checked requires available image and explicit inspection record')
        elif state == 'not_performed' and (item.get('inspection_event') or item.get('checked_content')):
            errors.append(f'{label} unperformed review cannot claim inspection')

    claim_ids = set()
    states = {'verified_internal_consistency', 'contradicted', 'potential_issue', 'insufficient_information', 'not_checked'}
    for i, item in enumerate(envelope(claims, 'claims')):
        label = f'claims[{i}]'
        keys = ('claim_id', 'claim_text', 'source_location', 'evidence_scope', 'reported_magnitude', 'uncertainty_information', 'alignment_status', 'limitation', 'recommended_action')
        if not isinstance(item, dict) or any(not _text(item.get(k)) for k in keys):
            errors.append(f'{label} missing fields')
            continue
        if item['claim_id'] in claim_ids:
            errors.append(f'{label} duplicate claim_id')
        claim_ids.add(item['claim_id'])
        if not _line_range(item['source_location'], len(source_lines)):
            errors.append(f'{label} invalid manuscript source location')
        ids, locs = item.get('evidence_ids'), item.get('evidence_locations')
        if not isinstance(ids, list) or not isinstance(locs, list) or len(ids) != len(locs) or any(not _text(x) for x in ids + locs):
            errors.append(f'{label} invalid evidence links')
            continue
        if item['alignment_status'] not in states:
            errors.append(f'{label} invalid alignment_status')
        if item['alignment_status'] in ('verified_internal_consistency', 'contradicted', 'potential_issue') and not ids:
            errors.append(f'{label} evidence required for this status')
        for ident, loc in zip(ids, locs):
            source = inventory_by_id.get(ident)
            if not source or source.get('verification_status') != 'available':
                errors.append(f'{label} evidence not available in inventory')
                continue
            path = allowed.get(source['source_path'])
            if source['artifact_type'] == 'image':
                if loc != 'image' or visual_by_id.get(ident, {}).get('visual_review_status') != 'checked':
                    errors.append(f'{label} image evidence has not been visually checked')
            else:
                try:
                    if not _line_range(loc, len(path.read_text(encoding='utf-8').splitlines())):
                        errors.append(f'{label} invalid evidence location')
                except (OSError, UnicodeError, AttributeError):
                    errors.append(f'{label} evidence location unreadable')

    ref_ids = set()
    for i, item in enumerate(envelope(crossrefs, 'references')):
        label = f'references[{i}]'
        keys = ('reference_id', 'reference_type', 'source_location', 'target', 'status')
        if not isinstance(item, dict) or any(not _text(item.get(k)) for k in keys):
            errors.append(f'{label} missing fields')
            continue
        if item['reference_id'] in ref_ids:
            errors.append(f'{label} duplicate reference_id')
        ref_ids.add(item['reference_id'])
        if not _line_range(item['source_location'], len(source_lines)):
            errors.append(f'{label} invalid manuscript source location')
        if item['reference_type'] not in ('figure', 'table', 'equation', 'citation') or item['status'] not in ('resolved', 'missing', 'ambiguous', 'not_checked'):
            errors.append(f'{label} invalid type or status')

    if not isinstance(findings, list):
        errors.append('findings must be an array')
        findings = []
    ids = set()
    for i, item in enumerate(findings):
        label = f'findings[{i}]'
        try:
            if not _schema_valid(item, schema, schema):
                errors.append(f'{label} fails Review Finding Schema')
                continue
            if item['reviewer_role'] != 'review_consistency':
                errors.append(f'{label} incorrect reviewer role')
            if item['finding_id'] in ids:
                errors.append(f'{label} duplicate finding_id')
            ids.add(item['finding_id'])
            if not _line_range(item['source_location'], len(source_lines)):
                errors.append(f'{label} invalid manuscript source location')
            for ev in item['evidence_location']:
                ref = ArtifactReference.from_dict(ev['artifact'])
                if ref.path not in allowed or not ref.verify(workspace_root):
                    errors.append(f'{label} unauthorized or hash mismatch')
                    continue
                sources = [x for x in inventory_by_id.values() if x.get('source_path') == ref.path and x.get('verification_status') == 'available']
                if not sources:
                    errors.append(f'{label} evidence missing from inventory')
                elif sources[0]['artifact_type'] == 'image':
                    if ev['locator'] != 'image' or visual_by_id.get(sources[0]['artifact_id'], {}).get('visual_review_status') != 'checked':
                        errors.append(f'{label} image evidence not visually checked')
                elif not _line_range(ev['locator'], len(allowed[ref.path].read_text(encoding='utf-8').splitlines())):
                    errors.append(f'{label} invalid evidence locator')
        except (ValueError, OSError, UnicodeError, TypeError, KeyError, RecursionError):
            errors.append(f'{label} invalid or unreadable finding evidence')
    return errors


def compare_numeric_claims(left, right, *, tolerance):
    """Compare explicit values under identical, nonempty definitions and conditions.

    Each mapping requires numeric value, nonempty metric/unit and a nonempty
    conditions mapping of nonempty scalar strings. No assumptions are made about
    units, denominators, rounding rules, definitions or statistical independence.
    Caller supplies an absolute tolerance in the stated unit. This is arithmetic,
    not scientific or statistical validation.
    """
    import math
    from decimal import Decimal
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('tolerance must be a finite nonnegative number')
    for item in (left, right):
        if not isinstance(item, dict) or type(item.get('value')) not in (int, float) or not math.isfinite(item['value']):
            raise ValueError('values must be finite numbers')
    def known(value):
        return _text(value) and value.strip().lower() not in (
            'unknown', 'unclear', 'not reported', 'not_reported', 'n/a')
    def complete(item):
        conditions = item.get('conditions')
        return (known(item.get('metric')) and known(item.get('unit')) and
                isinstance(conditions, dict) and bool(conditions) and
                all(known(k) and known(v) for k, v in conditions.items()))
    if not complete(left) or not complete(right) or any(left[k] != right[k] for k in ('metric', 'unit', 'conditions')):
        return {'status': 'insufficient_information', 'difference': None, 'tolerance': tolerance}
    difference = Decimal(str(left['value'])) - Decimal(str(right['value']))
    return {'status': 'within_tolerance' if abs(difference) <= Decimal(str(tolerance)) else 'contradicted',
            'difference': float(difference), 'tolerance': tolerance}


def inspect_statistics_handoff(workspace_root, manuscript_path, statistics_manuscript_path,
                               findings_path, claims_path, recalculation_path, manifest_path,
                               report_path, *, evidence_paths=(), trusted_calculation_scripts=()):
    """Check a complete, explicitly supplied Statistics handoff without rerunning it.

    Reuses the Statistics artifact validator, requires its manifest to identify the
    actual reviewed manuscript hash, and requires the current manuscript to match.
    `completed_record` only says a structurally valid record declares completion;
    it does not prove execution, data provenance, applicability or any scientific
    conclusion. Records marked not_executed never become completed records.
    """
    from .statistics_review_validation import validate_statistics_review_run
    try:
        validate_workspace_path(workspace_root, manuscript_path, must_exist=True)
        result = validate_statistics_review_run(
            workspace_root, statistics_manuscript_path, findings_path, claims_path,
            recalculation_path, manifest_path, report_path, evidence_paths=evidence_paths,
            trusted_calculation_scripts=trusted_calculation_scripts)
        if result:
            return {'status': 'blocked', 'errors': result, 'records': [],
                    'limitation': 'Structural checks do not establish scientific correctness or execution.'}
        current = create_artifact(workspace_root, manuscript_path)
        previous = create_artifact(workspace_root, statistics_manuscript_path)
        manifest = json.loads(validate_workspace_path(workspace_root, manifest_path, must_exist=True).read_text(encoding='utf-8'))
        recalc = json.loads(validate_workspace_path(workspace_root, recalculation_path, must_exist=True).read_text(encoding='utf-8'))
        if current.sha256 != previous.sha256:
            return {'status': 'blocked', 'errors': ['statistics manuscript differs from current manuscript'], 'records': [],
                    'limitation': 'Different version; no calculation can be transferred automatically.'}
        if not any(item.get('path') == statistics_manuscript_path and item.get('sha256') == previous.sha256
                   for item in manifest['input_artifacts'] if isinstance(item, dict)):
            return {'status': 'blocked', 'errors': ['statistics manifest does not identify the reviewed manuscript hash'], 'records': [],
                    'limitation': 'A manuscript association must be explicitly recorded.'}
        records = [{'record_index': i,
                    'status': 'completed_record' if item.get('status') != 'not_executed' and item.get('execution', {}).get('status') == 'completed' else 'not_executed',
                    'source_data': item.get('source_data')}
                   for i, item in enumerate(recalc['records'])]
        return {'status': 'available' if any(x['status'] == 'completed_record' for x in records) else 'no_completed_recalculation',
                'errors': [], 'records': records,
                'limitation': 'Hashes and structure do not prove execution, scientific correctness, data provenance or claim applicability.'}
    except (OSError, ValueError, UnicodeError, TypeError, KeyError, RecursionError):
        return {'status': 'blocked', 'errors': ['invalid or unreadable handoff'], 'records': [],
                'limitation': 'Could not establish the handoff association.'}
