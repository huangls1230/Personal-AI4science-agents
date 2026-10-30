"""Deterministic state and artifact helpers; Codex remains the sole orchestrator.

This module never dispatches agents or grants approval. The workspace contract is
not a race-proof filesystem sandbox; use the actual Codex sandbox and permissions.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from .contracts import create_artifact, validate_workspace_path

ROUTES = {
    'structure': ('structure',), 'terminology': ('terminology',),
    'language': ('language',), 'full': ('structure', 'terminology', 'language', 'final_validation'),
}
EXECUTORS = {'structure': 'paper_structure', 'terminology': 'paper_terminology',
             'language': 'paper_language', 'final_validation': 'codex_main'}


def route(task_type: str) -> tuple[str, ...]:
    if task_type not in ROUTES:
        raise ValueError('unknown editing task type')
    return ROUTES[task_type]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def prepare_run(workspace_root: Path, output_directory: str, *, project_id: str,
                manuscript_path: str, task_type: str, editing_scope: str,
                glossary_path: str | None = None, editing_mode: str = 'conservative',
                language_variant: str = 'preserve', max_retries: int = 0) -> tuple[Path, bool]:
    """Create an exclusive deterministic run or reuse an unchanged verified run.

    Returns (run directory, reused). Never invokes a model or approves edits.
    Language/full requires an authorized glossary input; approval is a separate
    trusted human check by the caller, never inferred from a file field.
    """
    stages = route(task_type)
    if not all(isinstance(x, str) and x.strip() for x in (project_id, editing_scope)):
        raise ValueError('project_id and scope are required')
    if editing_mode not in ('proofreading', 'conservative', 'academic_polishing') or language_variant not in ('preserve', 'en-GB', 'en-US'):
        raise ValueError('unsupported editing mode or language variant')
    if type(max_retries) is not int or not 0 <= max_retries <= 3:
        raise ValueError('max_retries must be an integer between 0 and 3')
    source = create_artifact(workspace_root, manuscript_path)
    if not manuscript_path.lower().endswith('.md'):
        raise ValueError('only Markdown inputs are supported')
    if 'language' in stages and not glossary_path:
        raise ValueError('language stage requires an authorized glossary')
    glossary = create_artifact(workspace_root, glossary_path) if glossary_path else None
    base = validate_workspace_path(workspace_root, output_directory, must_exist=False)
    if not base.is_dir():
        raise ValueError('output directory must already exist')
    config = {'project_id': project_id, 'manuscript': source.to_dict(), 'task_type': task_type,
              'editing_scope': editing_scope, 'glossary': glossary.to_dict() if glossary else None,
              'editing_mode': editing_mode, 'language_variant': language_variant, 'max_retries': max_retries}
    key = sha256(json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    run = base / key
    try:
        run.mkdir(mode=0o700)
    except FileExistsError:
        if run.is_symlink() or not run.is_dir():
            raise ValueError('run path is not a safe directory')
        state = _load(run)
        if state.get('key') != key or state.get('config') != config:
            raise ValueError('run identity mismatch')
        verify_run(workspace_root, run, state)
        return run, True
    state = {'schema_version': '0.1', 'key': key, 'config': config, 'status': 'pending',
             'stages': [{'stage': stage, 'status': 'pending', 'attempts': 0} for stage in stages],
             'artifacts': [{'artifact_id':'original', 'source_artifact_id':None,
                            'source_hash':source.sha256,'output_hash':source.sha256,'path':source.path,
                            'stage':'preparation','agent_or_executor':'codex_main',
                            'approval_status':'not_required','created_at':_now()}],
             'author_approval':'pending','usage':'unknown'}
    with (run / 'manifest.json').open('x', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2); f.write('\n')
    return run, False


def _load(run: Path) -> dict:
    with (run / 'manifest.json').open(encoding='utf-8') as f:
        value = json.load(f)
    if not isinstance(value, dict) or value.get('schema_version') != '0.1':
        raise ValueError('invalid workflow manifest')
    return value


def _check_run(workspace_root: Path, run: Path) -> None:
    root = Path(workspace_root).resolve(strict=True)
    if run.is_symlink() or not run.is_dir() or (run / 'manifest.json').is_symlink():
        raise ValueError('invalid run directory')
    try:
        relative = run.resolve(strict=True).relative_to(root).as_posix()
        validate_workspace_path(root, relative)
    except (OSError, ValueError, RuntimeError) as exc:
        raise ValueError('run directory escapes workspace') from exc


def _save(run: Path, state: dict) -> None:
    # Single writer by contract; an incomplete tmp file never replaces the manifest.
    temp = run / 'manifest.next.json'
    with temp.open('x', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2); f.write('\n')
    temp.replace(run / 'manifest.json')


def verify_run(workspace_root: Path, run: Path, state: dict | None = None) -> None:
    _check_run(workspace_root, run)
    state = state or _load(run)
    inputs = [state['config']['manuscript'], state['config']['glossary']]
    for item in inputs:
        if item and create_artifact(workspace_root, item['path']).sha256 != item['sha256']:
            raise ValueError('input version conflict')
    for item in state['artifacts']:
        if create_artifact(workspace_root, item['path']).sha256 != item['output_hash']:
            raise ValueError('artifact version conflict')


def _guard_versions(workspace_root: Path, run: Path, state: dict, stage: str) -> None:
    try:
        verify_run(workspace_root, run, state)
    except (OSError, ValueError) as exc:
        item = next((x for x in state['stages'] if x['stage'] == stage), None)
        if item and item['status'] in ('pending', 'running'):
            item.update(status='failed', error='input or artifact version conflict', completed_at=_now())
            state['status'] = 'failed'
            _save(run, state)
        raise ValueError('input or artifact version conflict') from exc


def begin_stage(workspace_root: Path, run: Path, stage: str) -> None:
    _check_run(workspace_root, run); state = _load(run); _guard_versions(workspace_root, run, state, stage)
    stages = state['stages']; matches = [i for i, x in enumerate(stages) if x['stage'] == stage]
    if len(matches) != 1:
        raise ValueError('stage is not routed for this task')
    i = matches[0]; item = stages[i]
    if state['status'] in ('failed', 'blocked', 'awaiting_author_approval') or item['status'] != 'pending' or any(x['status'] != 'completed' for x in stages[:i]):
        raise ValueError('stage is blocked by state or dependencies')
    if item['attempts'] >= state['config']['max_retries'] + 1:
        raise ValueError('retry limit reached')
    item.update(status='running', attempts=item['attempts'] + 1, started_at=_now())
    state['status'] = 'running'; _save(run, state)


def complete_stage(workspace_root: Path, run: Path, stage: str, output_paths: list[str],
                   *, execution_mode: str) -> None:
    _check_run(workspace_root, run); state = _load(run); _guard_versions(workspace_root, run, state, stage)
    stages = state['stages']; item = next((x for x in stages if x['stage'] == stage), None)
    if not item or item['status'] != 'running' or not output_paths or len(output_paths) != len(set(output_paths)):
        raise ValueError('stage is not running or outputs are missing/duplicated')
    if execution_mode not in ('native_subagent', 'inline_skill', 'deterministic'):
        raise ValueError('invalid execution mode')
    run_root = run.resolve(strict=True); original = state['config']['manuscript']; records = []
    for index, path in enumerate(output_paths):
        artifact = create_artifact(workspace_root, path)
        actual = validate_workspace_path(workspace_root, path, must_exist=True)
        stage_root = run_root / stage
        if item['attempts'] > 1:
            stage_root = stage_root / f"attempt-{item['attempts']}"
        try: actual.relative_to(stage_root)
        except ValueError as exc: raise ValueError('stage output escapes its exclusive stage directory') from exc
        if actual.samefile(validate_workspace_path(workspace_root, original['path'], must_exist=True)):
            raise ValueError('stage output cannot be original')
        records.append({'artifact_id':f'{stage}:{index+1}', 'source_artifact_id':'original',
                        'source_hash':original['sha256'], 'output_hash':artifact.sha256, 'path':path,
                        'stage':stage, 'agent_or_executor':EXECUTORS[stage],
                        'approval_status':'pending', 'created_at':_now()})
    item.update(status='completed', execution_mode=execution_mode, completed_at=_now())
    state['artifacts'].extend(records)
    state['status'] = 'awaiting_author_approval' if all(x['status'] == 'completed' for x in stages) else 'pending'
    _save(run, state)


def fail_stage(workspace_root: Path, run: Path, stage: str, reason: str) -> None:
    _check_run(workspace_root, run); state = _load(run); verify_run(workspace_root, run, state)
    item = next((x for x in state['stages'] if x['stage'] == stage), None)
    if not item or item['status'] != 'running' or not isinstance(reason, str) or not reason.strip():
        raise ValueError('stage is not running or reason is missing')
    item.update(status='failed', error=reason, completed_at=_now());state['status']='failed';_save(run,state)


def retry_stage(workspace_root: Path, run: Path, stage: str) -> None:
    """Explicitly requeue only the failed stage within the configured bound.

    Callers must use a fresh attempt output directory; existing files are not removed.
    """
    _check_run(workspace_root, run); state = _load(run); verify_run(workspace_root, run, state)
    item = next((x for x in state['stages'] if x['stage'] == stage), None)
    if not item or item['status'] != 'failed' or state['status'] != 'failed':
        raise ValueError('only a failed stage can be retried')
    if item['attempts'] >= state['config']['max_retries'] + 1:
        raise ValueError('retry limit reached')
    item['status'] = 'pending'; state['status'] = 'pending'; _save(run, state)


def approved_changes_only(changes: list[dict], trusted_approved_ids: set[str]) -> bool:
    """Do not trust artifact-reported status as proof of human approval."""
    if not isinstance(changes, list) or not isinstance(trusted_approved_ids, set):
        raise ValueError('changes and trusted approval identifiers are required')
    for change in changes:
        if not isinstance(change, dict) or type(change.get('applied_to_draft')) is not bool:
            raise ValueError('invalid change')
        if change['applied_to_draft'] and (not isinstance(change.get('change_id'), str) or change['change_id'] not in trusted_approved_ids):
            return False
    return True
