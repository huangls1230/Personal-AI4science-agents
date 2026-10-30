"""Local strict-review state and provenance helpers; never invokes a model.

The caller is responsible for authorization and scientific review. Hashes and
structural validation do not establish validity of research conclusions or
prove blind-review isolation. Workspace path checks are not an OS sandbox and
cannot prevent concurrent symlink replacement. Use a single writer per session.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re

from .contracts import ArtifactReference, create_artifact, validate_workspace_path
from .method_review_validation import _SCHEMA, _check_schema_keywords, _schema_valid, _line_range

ROUTES = {
    'full': ('method', 'statistics', 'consistency', 'doublecheck', 'final_validation'),
    'method': ('method',), 'statistics': ('statistics',), 'consistency': ('consistency',),
    'doublecheck': ('doublecheck',), 'targeted_rereview': ('targeted_rereview', 'final_validation'),
}
ROLES = {'method': 'review_method', 'statistics': 'review_statistics',
         'consistency': 'review_consistency', 'doublecheck': 'review_doublecheck'}
MODES = {'native_subagent', 'inline_skill', 'deterministic'}
ADJUDICATION = {'supported', 'partially_supported', 'unsupported', 'requires_more_evidence', 'unresolved'}


def route(mode):
    if mode not in ROUTES:
        raise ValueError('unknown review mode')
    return ROUTES[mode]


def build_evidence_inventory(workspace_root, items):
    """Record explicit availability without reading restricted or absent content.

    Items have artifact_id, artifact_type, status, and optional path. Available or
    partial items with paths are hashed; unavailable, restricted and not_checked
    items are never opened. Availability is supplied by the caller and does not
    prove any image was visually inspected or data interpreted.
    """
    statuses = {'available', 'partial', 'unavailable', 'restricted', 'not_checked'}
    if not isinstance(items, (list, tuple)):
        raise ValueError('inventory items must be a list')
    out, ids = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('invalid inventory item')
        ident, kind, status = item.get('artifact_id'), item.get('artifact_type'), item.get('status')
        if (not isinstance(ident, str) or not ident.strip() or ident in ids or
                not isinstance(kind, str) or not kind.strip() or status not in statuses):
            raise ValueError('invalid inventory item or duplicate id')
        ids.add(ident)
        path = item.get('path')
        if path is not None and (not isinstance(path, str) or not path.strip()):
            raise ValueError('invalid path')
        entry = {'artifact_id': ident, 'artifact_type': kind, 'status': status,
                 'path': path, 'sha256': None, 'access_method': 'not_read'}
        if status == 'available' and not path:
            raise ValueError('available artifact needs a path')
        if status in {'available', 'partial'} and path:
            entry['sha256'] = create_artifact(workspace_root, path).sha256
            entry['access_method'] = 'local_file'
        out.append(entry)
    return {'schema_version': '1.0', 'artifacts': out}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value):
        raise ValueError('project and session identifiers must be safe path components')
    return value


def _write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def _save(path, value):
    # Single writer; temp file is exclusive and os.replace is atomic on one filesystem.
    temp = path.with_name(path.name + '.next')
    _write_new(temp, value)
    temp.replace(path)


def _read(root, path):
    ref = validate_workspace_path(root, path, must_exist=True)
    with ref.open(encoding='utf-8') as stream:
        return json.load(stream)


def prepare_session(workspace_root, *, project_id, review_session_id, manuscript_path,
                    mode, review_scope, permission_status, evidence_paths=(),
                    review_policy='authorized', output_directory=None, configuration_paths=()):
    """Create a single immutable-input snapshot and exclusive session directory.

    permission_status is a caller-supplied decision, not evidence of permission.
    No other source is opened if permission is absent. Reuse requires explicit
    reuse_session() and verification of input/output hashes and configuration.
    """
    if permission_status != 'authorized':
        raise PermissionError('AI processing authorization must be established before reading')
    project_id, review_session_id = _name(project_id), _name(review_session_id)
    stages = route(mode)
    if not isinstance(review_scope, str) or not review_scope.strip() or not isinstance(review_policy, str) or not review_policy.strip():
        raise ValueError('review scope and policy required')
    if (not isinstance(evidence_paths, (tuple, list)) or not isinstance(configuration_paths, (tuple, list))
            or len(set(evidence_paths)) != len(evidence_paths)
            or len(set(configuration_paths)) != len(configuration_paths)
            or manuscript_path in evidence_paths or manuscript_path in configuration_paths
            or set(evidence_paths) & set(configuration_paths)):
        raise ValueError('unique evidence and configuration paths required')
    root = Path(workspace_root).resolve(strict=True)
    source = create_artifact(root, manuscript_path)
    evidence = [create_artifact(root, p).to_dict() for p in evidence_paths]
    configuration = [create_artifact(root, p).to_dict() for p in configuration_paths]
    session_rel = output_directory or f'projects/{project_id}/reviews/{review_session_id}'
    session = validate_workspace_path(root, session_rel)
    if session.exists() or session.is_symlink():
        raise FileExistsError('session directory already exists; never overwrite')
    session.parent.mkdir(parents=True, exist_ok=True)
    # Revalidate containment after creating intermediate directories.
    session = validate_workspace_path(root, session_rel)
    session.mkdir(mode=0o700)
    snapshot = session / 'manuscript_snapshot.md'
    original = validate_workspace_path(root, manuscript_path, must_exist=True)
    # Exclusive create prevents accidental overwrite of an existing target.
    with original.open('rb') as src, snapshot.open('xb') as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)
    snapshot_rel = snapshot.relative_to(root).as_posix()
    snap_ref = create_artifact(root, snapshot_rel)
    if snap_ref.sha256 != source.sha256 or create_artifact(root, manuscript_path).sha256 != source.sha256:
        raise ValueError('manuscript changed during snapshot; session unusable')
    for stage in stages:
        (session / stage).mkdir(mode=0o700)
    config = {'project_id': project_id, 'review_session_id': review_session_id,
              'manuscript': source.to_dict(), 'snapshot': snap_ref.to_dict(),
              'mode': mode, 'review_scope': review_scope, 'review_policy': review_policy,
              'permission_status': permission_status, 'evidence': evidence, 'configuration': configuration}
    state = {'schema_version': '1.0', 'review_start_time': _now(), 'config': config,
             'status': 'pending', 'stages': {s: {'status': 'pending', 'artifacts': []} for s in stages},
             'usage': 'unknown', 'blind_review': False,
             'limitation': 'Hash and manifest validation do not establish scientific correctness or isolation.'}
    inventory = [{'artifact_id': 'manuscript', **source.to_dict(), 'status': 'available', 'access_method': 'local_file'}]
    inventory.extend({'artifact_id': f'evidence-{i}', **item, 'status': 'available', 'access_method': 'local_file'}
                     for i, item in enumerate(evidence, 1))
    _write_new(session / 'input_manifest.json', {'schema_version': '1.0', **config, 'inventory': inventory})
    _write_new(session / 'execution_manifest.json', state)
    return session


def verify_session(workspace_root, session_rel):
    """Check all bound hashes and output containment; return stored state or raise."""
    root = Path(workspace_root).resolve(strict=True)
    manifest_path = f'{session_rel}/execution_manifest.json'
    state = _read(root, manifest_path)
    if not isinstance(state, dict) or state.get('schema_version') != '1.0':
        raise ValueError('invalid session manifest')
    cfg = state['config']
    if cfg['permission_status'] != 'authorized' or tuple(state['stages']) != route(cfg['mode']):
        raise ValueError('invalid authorization or stage configuration')
    input_record = _read(root, f'{session_rel}/input_manifest.json')
    if any(input_record.get(k) != v for k, v in cfg.items()):
        raise ValueError('input manifest mismatch')
    for item in (cfg['manuscript'], cfg['snapshot'], *cfg['evidence'], *cfg['configuration']):
        if not ArtifactReference.from_dict(item).verify(root):
            raise ValueError('input or snapshot version conflict')
    for stage, entry in state['stages'].items():
        if entry.get('status') not in {'pending', 'completed', 'failed'}:
            raise ValueError('invalid stage status')
        for artifact in entry.get('artifacts', []):
            ref = ArtifactReference.from_dict(artifact)
            actual = validate_workspace_path(root, ref.path, must_exist=True)
            stage_dir = validate_workspace_path(root, f'{session_rel}/{stage}')
            if not actual.is_relative_to(stage_dir) or not ref.verify(root):
                raise ValueError('stage artifact path or hash mismatch')
    return state


def reuse_session(workspace_root, session_rel, *, project_id, manuscript_path, mode,
                  review_scope, permission_status, review_policy='authorized', evidence_paths=(),
                  configuration_paths=()):
    """Reuse only an exact, still-authorized, fully completed session.

    Configuration paths are hashed as files, not as transitive references. If a
    configuration file lists Skill paths/hashes, the caller must revalidate the
    real Skill files and regenerate it before claiming a safe cache hit. Current
    approval and all required specialist validators are the caller's duties.
    """
    if permission_status != 'authorized':
        raise PermissionError('current authorization is required')
    state = verify_session(workspace_root, session_rel)
    cfg = state['config']
    requested = (project_id, manuscript_path, mode, review_scope, permission_status, review_policy, list(evidence_paths), list(configuration_paths))
    saved = (cfg['project_id'], cfg['manuscript']['path'], cfg['mode'], cfg['review_scope'],
             cfg['permission_status'], cfg['review_policy'], [x['path'] for x in cfg['evidence']],
             [x['path'] for x in cfg['configuration']])
    if not configuration_paths or requested != saved or state['status'] != 'completed':
        raise ValueError('session not completed or reuse parameters differ')
    return state


def record_stage(workspace_root, session_rel, stage, *, status, execution_mode,
                 output_paths=(), errors=(), manuscript_hash=None, blind_review=False):
    """Record one finished stage. Validation and invocation evidence are caller duties."""
    root = Path(workspace_root).resolve(strict=True)
    state = verify_session(root, session_rel)
    cfg = state['config']
    if stage not in state['stages'] or state['stages'][stage]['status'] != 'pending':
        raise ValueError('stage not routed or already recorded')
    if status not in {'completed', 'failed'} or execution_mode not in MODES:
        raise ValueError('invalid stage status or executor')
    if manuscript_hash != cfg['snapshot']['sha256']:
        raise ValueError('stage manuscript version conflict')
    if blind_review:
        raise ValueError('this local helper cannot establish enforced blind isolation')
    if not isinstance(errors, (tuple, list)) or any(not isinstance(x, str) or not x.strip() for x in errors):
        raise ValueError('errors must be a list of nonempty strings')
    if status == 'completed' and (errors or not output_paths):
        raise ValueError('completed stage needs outputs and no validation errors')
    if status == 'failed' and not errors:
        raise ValueError('failed stage requires a reason')
    if stage == 'doublecheck' and cfg['mode'] == 'full' and any(state['stages'][s]['status'] == 'pending' for s in ('method', 'statistics', 'consistency')):
        raise ValueError('specialist stages must first be recorded')
    if stage == 'final_validation' and any(v['status'] == 'pending' for k, v in state['stages'].items() if k != stage):
        raise ValueError('final validation requires prior recorded stages')
    refs = []
    stage_dir = validate_workspace_path(root, f'{session_rel}/{stage}')
    for path in output_paths:
        actual = validate_workspace_path(root, path, must_exist=True)
        if not actual.is_relative_to(stage_dir):
            raise ValueError('output must be in its stage directory')
        for item in (cfg['manuscript'], cfg['snapshot'], *cfg['evidence'], *cfg['configuration']):
            if actual.samefile(validate_workspace_path(root, item['path'], must_exist=True)):
                raise ValueError('output aliases an input')
        refs.append(create_artifact(root, path).to_dict())
    if len({item['path'] for item in refs}) != len(refs):
        raise ValueError('duplicate output paths')
    state['stages'][stage] = {'status': status, 'execution_mode': execution_mode,
                             'manuscript_hash': manuscript_hash, 'artifacts': refs,
                             'errors': list(errors), 'recorded_at': _now()}
    statuses = [x['status'] for x in state['stages'].values()]
    state['status'] = 'partial' if 'failed' in statuses else ('completed' if all(x == 'completed' for x in statuses) else 'pending')
    manifest = validate_workspace_path(root, f'{session_rel}/execution_manifest.json', must_exist=True)
    _save(manifest, state)
    return state


def aggregate_findings(workspace_root, manuscript_path, records, *, evidence_paths=(), duplicate_groups=()):
    """Validate findings and bind them to the manuscript; merge only explicit groups.

    Each record has finding, manuscript_hash, adjudication_status and unresolved_questions.
    Caller supplies explicit groups as lists of fully qualified role:finding_id keys.
    The result is a separate envelope, leaving the underlying finding schema intact.
    """
    root = Path(workspace_root).resolve(strict=True)
    manuscript = create_artifact(root, manuscript_path)
    source_path = validate_workspace_path(root, manuscript_path, must_exist=True)
    lines = source_path.read_text(encoding='utf-8').splitlines()
    allowed = {manuscript_path, *evidence_paths}
    schema = json.loads(_SCHEMA.read_text(encoding='utf-8'))
    _check_schema_keywords(schema)
    indexed = {}
    for record in records:
        finding = record.get('finding')
        if record.get('manuscript_hash') != manuscript.sha256:
            raise ValueError('finding manuscript version conflict')
        if not _schema_valid(finding, schema, schema):
            raise ValueError('finding schema invalid')
        if not _line_range(finding['source_location'], len(lines)):
            raise ValueError('finding source location invalid')
        if (record.get('adjudication_status') not in ADJUDICATION
                or not isinstance(record.get('unresolved_questions'), list)
                or any(not isinstance(q, str) or not q.strip() for q in record['unresolved_questions'])):
            raise ValueError('invalid adjudication or unresolved questions')
        for ev in finding['evidence_location']:
            ref = ArtifactReference.from_dict(ev['artifact'])
            if ref.path not in allowed or not ref.verify(root):
                raise ValueError('evidence missing, changed or unauthorized')
            path = validate_workspace_path(root, ref.path, must_exist=True)
            if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
                if ev['locator'] != 'image':
                    raise ValueError('invalid image locator')
            elif not _line_range(ev['locator'], len(path.read_text(encoding='utf-8').splitlines())):
                raise ValueError('invalid evidence locator')
        key = f"{finding['reviewer_role']}:{finding['finding_id']}"
        if key in indexed:
            raise ValueError('duplicate source finding key')
        indexed[key] = record
    used = set()
    groups = []
    for group in duplicate_groups:
        if not isinstance(group, (tuple, list)) or len(group) < 2 or len(set(group)) != len(group) or any(k not in indexed or k in used for k in group):
            raise ValueError('invalid or overlapping explicit duplicate group')
        used.update(group)
        groups.append(list(group))
    groups.extend([[key] for key in indexed if key not in used])
    rows = []
    for index, group in enumerate(groups, 1):
        members = [indexed[k] for k in group]
        statuses = {x['adjudication_status'] for x in members}
        rows.append({'finding_id': f'AGG-{index:03d}', 'manuscript_hash': manuscript.sha256,
                     'originating_agent': [x['finding']['reviewer_role'] for x in members],
                     'source_finding_ids': group, 'source_findings': [x['finding'] for x in members],
                     'issue_type': [x['finding']['issue_type'] for x in members],
                     'severity': members[0]['finding']['severity'] if len({x['finding']['severity'] for x in members}) == 1 else 'unresolved',
                     'verification_status': members[0]['finding']['verification_status'] if len({x['finding']['verification_status'] for x in members}) == 1 else 'unresolved',
                     'source_location': [x['finding']['source_location'] for x in members],
                     'evidence_location': [ev for x in members for ev in x['finding']['evidence_location']],
                     'reasoning': [x['finding']['reasoning'] for x in members],
                     'impact': [x['finding']['impact'] for x in members],
                     'recommended_action': [x['finding']['recommended_action'] for x in members],
                     'adjudication_status': statuses.pop() if len(statuses) == 1 else 'unresolved',
                     'unresolved_questions': [q for x in members for q in x['unresolved_questions']]})
    return {'schema_version': '1.0', 'manuscript_hash': manuscript.sha256, 'findings': rows,
            'limitation': 'Explicit grouping is a reviewer assertion, not semantic verification.'}


def prepare_rereview(old_hash, new_hash, finding_ids):
    """Old findings remain historical and need an explicit new-version assessment."""
    if not all(isinstance(h, str) and re.fullmatch(r'[0-9a-f]{64}', h) for h in (old_hash, new_hash)):
        raise ValueError('valid hashes required')
    if old_hash == new_hash:
        raise ValueError('targeted re-review requires a changed manuscript version')
    if not isinstance(finding_ids, (tuple, list)) or not finding_ids or len(set(finding_ids)) != len(finding_ids) or any(not isinstance(i, str) or not i.strip() for i in finding_ids):
        raise ValueError('unique finding IDs required')
    return {'schema_version': '1.0', 'old_manuscript_hash': old_hash, 'new_manuscript_hash': new_hash,
            'findings': [{'source_finding_id': x, 'status': 'not_checked', 'resolution': 'unknown'} for x in finding_ids]}
