"""Safe, local-only reading-status proposals and paper identity links.

This module does not modify Zotero or external notes. Workspace path checks follow the
project contract and are not an OS sandbox against concurrent symlink changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .contracts import ArtifactReference, create_artifact, validate_workspace_path
from .reading_output import validate_reading_result

READING_STATUSES = frozenset({
    'research-unread', 'research-screened', 'research-reading',
    'research-deepread', 'research-reread', 'research-verified',
})


def _identity(library_id: str | int, item_key: str) -> tuple[str, str]:
    if isinstance(library_id, bool) or not isinstance(library_id, (str, int)) or not str(library_id).strip():
        raise ValueError('library_id is required')
    if not isinstance(item_key, str) or not item_key.strip():
        raise ValueError('item_key is required')
    return str(library_id), item_key


def _identity_scope(library_kind: str | None, server_id: str | None) -> None:
    if library_kind not in (None, 'users', 'groups'):
        raise ValueError('library kind must be users, groups, or null')
    if server_id is not None and (not isinstance(server_id, str) or not server_id.strip()):
        raise ValueError('server ID must be nonempty or null')


def _tag_value(tag: Any) -> str:
    if isinstance(tag, str) and tag:
        return tag
    if isinstance(tag, dict) and isinstance(tag.get('tag'), str) and tag['tag']:
        return tag['tag']
    raise ValueError('each tag must be a nonempty string or Zotero tag object')


def get_reading_status(tags: list) -> str | None:
    """Return the unique workflow tag; ambiguous multiple statuses are a conflict."""
    if not isinstance(tags, list):
        raise ValueError('tags must be a list')
    values = [_tag_value(t) for t in tags]
    statuses = [value for value in values if value in READING_STATUSES]
    if len(statuses) > 1:
        raise ValueError('multiple workflow status tags; resolve conflict manually')
    return statuses[0] if statuses else None


def validate_status_transition(tags: list, target_status: str, *,
                               user_understanding_confirmed: bool = False) -> str | None:
    current = get_reading_status(tags)
    if target_status not in READING_STATUSES:
        raise ValueError('unknown research reading status')
    if target_status == 'research-verified' and user_understanding_confirmed is not True:
        raise ValueError('research-verified requires explicit user understanding confirmation')
    return current


def propose_status_transition(library_id: str | int, item_key: str, version: int,
                              tags: list, target_status: str, *,
                              library_kind: str | None = None, server_id: str | None = None,
                              user_understanding_confirmed: bool = False) -> dict:
    """Preview the exact tag edit, with no network or storage mutation.

    Confirmation here only records caller input; this runtime cannot authenticate
    or evaluate a user's answer and never performs the proposed write.
    """
    library, key = _identity(library_id, item_key)
    _identity_scope(library_kind, server_id)
    if type(version) is not int or version < 0:
        raise ValueError('a nonnegative object version is required')
    current = validate_status_transition(tags, target_status,
                                         user_understanding_confirmed=user_understanding_confirmed)
    before = [dict(t) if isinstance(t, dict) else t for t in tags]
    after = [dict(t) if isinstance(t, dict) else t for t in tags if _tag_value(t) not in READING_STATUSES]
    if current == target_status:
        after = before.copy()
    else:
        after.append({'tag': target_status})
    return {'schema_version': '1.0', 'operation': 'reading_status', 'dry_run': True,
            'zotero_library_id': library, 'zotero_item_key': key, 'expected_version': version,
            'zotero_library_kind': library_kind, 'zotero_server_id': server_id,
            'identity_scope_complete': bool(library_kind and server_id),
            'previous_status': current, 'target_status': target_status,
            'before_tags': before, 'after_tags': after, 'requires_user_approval': True,
            'user_understanding_confirmed_by_caller': user_understanding_confirmed,
            'created_at': datetime.now(timezone.utc).isoformat(), 'applied': False}


def apply_status_transition(proposal: dict, *, user_approved: bool = False,
                            current_version: int | None = None) -> dict:
    """Fail closed, including on stale object versions; write support is unimplemented."""
    if not user_approved:
        return {'status': 'blocked', 'applied': False, 'reason': 'explicit user approval is required'}
    if not isinstance(proposal, dict) or type(proposal.get('expected_version')) is not int:
        return {'status': 'blocked', 'applied': False, 'reason': 'invalid proposal'}
    if type(current_version) is not int or current_version != proposal['expected_version']:
        return {'status': 'blocked', 'applied': False, 'reason': 'object version missing or changed; reread and review'}
    return {'status': 'blocked', 'applied': False, 'reason': 'Zotero status writes are not implemented'}


def _card_frontmatter(card: str) -> dict[str, Any]:
    """Read managed JSON-valued YAML fields; ignore unrelated template entries.

    Reading emits managed values as JSON scalars (valid YAML). Other template
    entries may use normal YAML, including nested lists, and are not interpreted.
    """
    lines = card.splitlines()
    if not lines or lines[0] != '---':
        raise ValueError('missing reading-card frontmatter')
    values: dict[str, Any] = {}
    managed = {'zotero_item_key', 'citekey', 'doi', 'source_pdf'}
    seen: set[str] = set()
    for line in lines[1:]:
        if line == '---':
            return values
        name, sep, value = line.partition(':')
        if not sep or not name or name[0].isspace() or name.startswith('#'):
            continue
        if name in seen:
            raise ValueError('duplicate frontmatter field')
        seen.add(name)
        if name not in managed:
            continue
        try:
            values[name] = json.loads(value.strip())
        except (ValueError, TypeError) as exc:
            raise ValueError('frontmatter is not in the supported JSON-valued YAML subset') from exc
    raise ValueError('unterminated reading-card frontmatter')


def link_reading_card(workspace_root: Path, reading_result: dict, *,
                      library_id: str | int, item_key: str,
                      library_kind: str | None = None, server_id: str | None = None,
                      citation_key: str | None = None, doi: str | None = None,
                      metadata_verification_status: str = 'unverified') -> dict:
    """Build a workspace-based identity mapping, never modifying the reading card.

    Zotero library ID must be supplied separately: ReadingResult only has item key.
    Artifact hash mismatch (including later edits) fails rather than linking stale data.
    """
    library, key = _identity(library_id, item_key)
    _identity_scope(library_kind, server_id)
    validate_reading_result(reading_result, workspace_root, verify_files=True)
    if reading_result['zotero_item_key'] != key:
        raise ValueError('reading result item key does not match requested Zotero item')
    path = reading_result['reading_card_path']
    if not path:
        raise ValueError('reading result has no reading card')
    for name, value in (('citation_key', citation_key), ('doi', doi)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f'{name} must be a nonempty string or null')
    refs = [ArtifactReference.from_dict(r) for r in reading_result['execution']['output_artifacts']
            if r.get('path') == path]
    if len(refs) != 1 or not refs[0].verify(workspace_root):
        raise ValueError('reading card must have a matching verified output artifact')
    card_path = validate_workspace_path(workspace_root, path, must_exist=True)
    if card_path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('reading card exceeds 4 MiB limit')
    meta = _card_frontmatter(card_path.read_text(encoding='utf-8'))
    if meta.get('zotero_item_key') not in (None, key):
        raise ValueError('reading-card frontmatter item key conflicts')
    if meta.get('citekey') is not None and citation_key is not None and meta['citekey'] != citation_key:
        raise ValueError('reading-card citation key conflicts')
    if meta.get('doi') is not None and doi is not None:
        if not isinstance(meta['doi'], str) or meta['doi'].casefold() != doi.casefold():
            raise ValueError('reading-card DOI conflicts; review normalization and metadata')
    if metadata_verification_status not in ('verified', 'partially_verified', 'unverified', 'conflict'):
        raise ValueError('invalid metadata verification status')
    source = reading_result['source_document']
    return {'schema_version': '1.0', 'zotero_library_id': library, 'zotero_item_key': key,
            'zotero_library_kind': library_kind, 'zotero_server_id': server_id,
            'identity_scope_complete': bool(library_kind and server_id),
            'link_status': 'requires_review', 'source_identity_verified': False,
            'link_review_reason': ('ReadingResult provides an item key but does not identify its Zotero library or server; '
                                   'the proposed association requires user review.'),
            'citation_key': citation_key, 'doi': doi,
            'reading_card': refs[0].to_dict(), 'source_pdf_path': source['path'] if source and reading_result['reading_mode'] != 'abstract' else None,
            'metadata_verification_status': metadata_verification_status,
            'frontmatter_fields': {k: meta.get(k) for k in ('zotero_item_key', 'citekey', 'doi', 'source_pdf')},
            'note_modified': False}


def save_link_record(workspace_root: Path, path: str, mapping: dict) -> dict:
    """Create a new workspace record exclusively; never overwrite user content."""
    target = validate_workspace_path(workspace_root, path)
    if not target.parent.is_dir():
        raise ValueError('parent directory must already exist')
    payload = json.dumps(mapping, ensure_ascii=False, indent=2) + '\n'
    with target.open('x', encoding='utf-8') as stream:
        stream.write(payload)
    return create_artifact(workspace_root, path).to_dict()
