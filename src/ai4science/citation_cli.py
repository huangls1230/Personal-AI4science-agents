"""Read-only citation tools. Codex decides and approves; this is not an agent loop."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .citation_links import link_reading_card, propose_status_transition, save_link_record
from .citation_metadata import citation_record_from_search, citation_record_from_zotero, detect_duplicate, validate_metadata
from .citation_result import validate_citation_result
from .contracts import ArtifactReference, ExecutionResult, UsageMetrics, create_artifact, validate_workspace_path
from .zotero_local import BetterBibTeXAdapter, ZoteroError, ZoteroLocalClient

_STYLES = {'apa': 'apa', 'ieee': 'ieee', 'chicago': 'chicago-note-bibliography',
           'gbt7714': 'china-national-standard-gb-t-7714-2015-numeric'}


def _root(path):
    root = Path(path).resolve(strict=True)
    workspace = (Path(__file__).resolve().parents[2] / 'workspace').resolve(strict=True)
    root.relative_to(workspace)
    if not root.is_dir():
        raise ValueError('workspace must be an existing project workspace directory')
    return root


def _read_json(root, path):
    file = validate_workspace_path(root, path, must_exist=True)
    if file.stat().st_size > 5_000_000:
        raise ValueError('JSON input exceeds 5 MB')
    with file.open(encoding='utf-8') as f:
        return json.load(f)


def _bounded_read(client, library, kind, operation):
    """Check local instance identity around a multi-request operation.

    Missing server IDs remain unknown; they never assert matching identity.
    A known change aborts. Local API checks do not provide atomic snapshots.
    """
    before = client.doctor(library, kind)
    if before.get('library_accessible') is not True:
        raise ZoteroError('unavailable', 'Cannot verify local library access before reading')
    value = operation()
    after = client.doctor(library, kind)
    if after.get('library_accessible') is not True:
        raise ZoteroError('unavailable', 'Cannot verify local library access after reading')
    first, last = before.get('server_id'), after.get('server_id')
    if first and last and first != last:
        raise ZoteroError('identity_changed', 'Local Zotero server identity changed during read')
    return value, first if first and last and first == last else None


def _identity_warnings(server_id):
    return [] if server_id else ['Zotero server identity could not be verified across the operation.']


def _item_record(client, library, kind, key, *, attachments=False):
    def read():
        item = client.get_item(library, key, library_kind=kind)
        data = item.get('data') if isinstance(item, dict) else None
        if not isinstance(data, dict) or data.get('itemType') in ('attachment', 'note', 'annotation'):
            raise ZoteroError('invalid_response', 'Item is not a bibliographic Zotero record')
        if item.get('key') != key or data.get('key') != key:
            raise ZoteroError('invalid_response', 'Returned item key does not match requested key')
        children = client.get_attachments(library, key, library_kind=kind) if attachments else None
        return item, children
    (item, children), server_id = _bounded_read(client, library, kind, read)
    record = citation_record_from_zotero(item, library, attachments=children, library_kind=kind,
                                         server_id=server_id)
    return item, record


def _result(root, task, operation, status='completed', *, records=None, proposals=None,
            exports=None, verification=None, warnings=None, errors=None, artifacts=None):
    usage = UsageMetrics()
    errors = errors or []
    output = [ArtifactReference.from_dict(a) for a in (artifacts or [])]
    execution = ExecutionResult(task_id=task, executor='citation_cli', status=status,
                                errors=tuple(errors), output_artifacts=tuple(output), usage_metrics=usage)
    result = {'schema_version': '1.0', 'task_id': task, 'operation': operation, 'execution_status': status,
              'affected_records': records or [], 'proposed_changes': proposals or [], 'applied_changes': [],
              'exported_artifacts': exports or [], 'verification_results': verification or [],
              'warnings': warnings or [], 'errors': errors, 'usage_metrics': usage.to_dict(),
              'execution': execution.to_dict()}
    validate_citation_result(result, root)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only local Zotero citation tools; never writes a library.')
    parser.add_argument('--workspace', default='workspace')
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--library', type=int, default=0, help='Local API numeric user or group ID')
    parser.add_argument('--kind', choices=('users', 'groups'), default='users')
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('doctor')
    listing = sub.add_parser('list')
    listing.add_argument('--limit', type=int, default=10)
    listing.add_argument('--start', type=int, default=0)
    search = sub.add_parser('search')
    search.add_argument('--query', required=True)
    search.add_argument('--limit', type=int, default=10)
    search.add_argument('--start', type=int, default=0)
    search.add_argument('--qmode', choices=('titleCreatorYear', 'everything'), default='titleCreatorYear')
    get = sub.add_parser('get')
    get.add_argument('--item-key', required=True)
    get.add_argument('--attachments', action='store_true')
    verify = sub.add_parser('verify')
    verify.add_argument('--item-key', required=True)
    verify.add_argument('--allow-network', action='store_true', help='Allow DOI disclosure to Crossref')
    export = sub.add_parser('export')
    export.add_argument('--item-key', action='append', required=True)
    export.add_argument('--format', choices=('bibtex', 'biblatex', 'csljson', 'apa', 'ieee', 'chicago', 'gbt7714'), required=True)
    export.add_argument('--output', required=True, help='New workspace-relative file')
    status = sub.add_parser('status-plan')
    status.add_argument('--item-key', required=True)
    status.add_argument('--target', required=True)
    status.add_argument('--user-understanding-confirmed', action='store_true')
    bbt = sub.add_parser('bbt')
    bbt.add_argument('--item-key', action='append', default=[])
    bbt.add_argument('--bbt-library-id', type=int, help='BBT internal library ID, not local API user/group ID')
    compare = sub.add_parser('compare')
    compare.add_argument('--left', required=True)
    compare.add_argument('--right', required=True)
    plan = sub.add_parser('plan-import')
    plan.add_argument('--search-result', required=True)
    plan.add_argument('--index', type=int, default=0)
    plan.add_argument('--limit', type=int, default=20)
    link = sub.add_parser('link')
    link.add_argument('--item-key', required=True)
    link.add_argument('--reading-result', required=True)
    link.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    root = None
    try:
        root = _root(args.workspace)
        if not args.task_id.strip():
            raise ValueError('task-id must be nonempty')
        client = ZoteroLocalClient()
        if args.operation == 'doctor':
            info = client.doctor(args.library, args.kind)
            ok = info['api_enabled'] is True and info['library_accessible'] is True
            result = _result(root, args.task_id, 'doctor', 'completed' if ok else 'blocked',
                             verification=[info], errors=[] if ok else ['Zotero Local API or library unavailable'])
        elif args.operation in ('list', 'search'):
            def fetch_page():
                if args.operation == 'list':
                    return client.list_items(args.library, library_kind=args.kind, limit=args.limit, start=args.start)
                return client.search_items(args.library, args.query, library_kind=args.kind,
                                           limit=args.limit, start=args.start, qmode=args.qmode)
            items, server_id = _bounded_read(client, args.library, args.kind, fetch_page)
            if not isinstance(items, list):
                raise ZoteroError('invalid_response', 'Expected a list of Zotero items')
            records = [citation_record_from_zotero(item, args.library, library_kind=args.kind, server_id=server_id)
                       for item in items if isinstance(item, dict) and isinstance(item.get('data'), dict)
                       and item['data'].get('itemType') not in ('attachment', 'note', 'annotation')]
            result = _result(root, args.task_id, args.operation, records=records,
                             warnings=[f'Bounded page start={args.start}, limit={args.limit}; child records omitted.'] + _identity_warnings(server_id))
        elif args.operation == 'get':
            _, record = _item_record(client, args.library, args.kind, args.item_key, attachments=args.attachments)
            result = _result(root, args.task_id, 'get', records=[record], warnings=_identity_warnings(record['zotero_server_id']))
        elif args.operation == 'verify':
            _, record = _item_record(client, args.library, args.kind, args.item_key)
            check = validate_metadata(record, perform_lookup=args.allow_network)
            record['metadata_verification_status'] = check['status']
            result = _result(root, args.task_id, 'verify', records=[record], verification=[check], warnings=check['warnings'] + _identity_warnings(record['zotero_server_id']))
        elif args.operation == 'export':
            target = validate_workspace_path(root, args.output)
            if target.exists():
                raise FileExistsError('output already exists')
            if not target.parent.is_dir():
                raise ValueError('output parent directory does not exist')
            style = _STYLES.get(args.format)
            fmt = 'bib' if style else args.format
            data, server_id = _bounded_read(client, args.library, args.kind,
                                    lambda: client.export(args.library, args.item_key, fmt, library_kind=args.kind, style=style))
            with target.open('xb') as stream:
                stream.write(data)
            ref = create_artifact(root, args.output).to_dict()
            result = _result(root, args.task_id, 'export', exports=[ref], artifacts=[ref],
                             warnings=['Zotero native export; exported BibTeX keys are not asserted to be Better BibTeX keys.',
                                       'Exported item identities are not independently verified; formatted bibliography completeness is not checked.'] + _identity_warnings(server_id))
        elif args.operation == 'status-plan':
            item, record = _item_record(client, args.library, args.kind, args.item_key)
            version = item.get('version') if isinstance(item, dict) else None
            tags = item['data'].get('tags', [])
            proposal = propose_status_transition(args.library, args.item_key, version, tags, args.target,
                           library_kind=args.kind, server_id=record['zotero_server_id'],
                           user_understanding_confirmed=args.user_understanding_confirmed)
            result = _result(root, args.task_id, 'status-plan', records=[record], proposals=[proposal],
                             warnings=['Dry-run only; no Zotero write was performed.'] + _identity_warnings(record['zotero_server_id']))
        elif args.operation == 'bbt':
            adapter = BetterBibTeXAdapter()
            ready = adapter.ready()
            if args.kind == 'groups' and args.item_key and args.bbt_library_id is None:
                raise ValueError('group lookup requires an explicit BBT internal library ID')
            keys = adapter.citation_keys(args.bbt_library_id, args.item_key) if args.item_key else {}
            result = _result(root, args.task_id, 'bbt', verification=[{'ready': ready, 'citation_keys': keys}])
        elif args.operation == 'compare':
            left, right = _read_json(root, args.left), _read_json(root, args.right)
            result = _result(root, args.task_id, 'compare', verification=[detect_duplicate(left, right)])
        elif args.operation == 'plan-import':
            data = _read_json(root, args.search_result)
            items = data.get('results') if isinstance(data, dict) else None
            if not isinstance(items, list) or args.index < 0 or args.index >= len(items):
                raise ValueError('invalid search result or index')
            candidate = citation_record_from_search(items[args.index])
            if not candidate['title']:
                raise ValueError('search record has no title for local candidate search')
            rows, server_id = _bounded_read(client, args.library, args.kind,
                lambda: client.search_items(args.library, candidate['title'], library_kind=args.kind, limit=args.limit))
            if not isinstance(rows, list):
                raise ZoteroError('invalid_response', 'Expected a list of Zotero items')
            matches = []
            for item in rows:
                if isinstance(item, dict) and isinstance(item.get('data'), dict) and item['data'].get('itemType') not in ('attachment', 'note', 'annotation'):
                    local = citation_record_from_zotero(item, args.library, library_kind=args.kind, server_id=server_id)
                    matches.append({'item_key': local['zotero_item_key'], **detect_duplicate(candidate, local)})
            proposal = {'action': 'propose_import', 'candidate': candidate, 'duplicate_candidates': matches,
                        'requires_user_approval': True, 'applied': False}
            result = _result(root, args.task_id, 'plan-import', records=[candidate], proposals=[proposal],
                             warnings=['Bounded title search only; missing candidates do not prove uniqueness. Import is not implemented.'] + _identity_warnings(server_id))
        elif args.operation == 'link':
            _, record = _item_record(client, args.library, args.kind, args.item_key)
            reading = _read_json(root, args.reading_result)
            mapping = link_reading_card(root, reading, library_id=args.library, item_key=args.item_key,
                                        doi=record['doi'], library_kind=args.kind, server_id=record['zotero_server_id'],
                                        metadata_verification_status=record['metadata_verification_status'])
            ref = save_link_record(root, args.output, mapping)
            result = _result(root, args.task_id, 'link', records=[record], artifacts=[ref],
                             proposals=[mapping], warnings=['Workspace mapping requires review; source library identity is not independently verified. No external vault was modified.'] + _identity_warnings(record['zotero_server_id']))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['execution_status'] == 'completed' else 2
    except (ZoteroError, ValueError, OSError, json.JSONDecodeError) as exc:
        message = f'{getattr(exc, "code", type(exc).__name__)}: {exc}'
        if root is None:
            print(json.dumps({'status': 'blocked', 'errors': [message]}, ensure_ascii=False), file=sys.stderr)
        else:
            result = _result(root, args.task_id or 'invalid', args.operation, 'blocked', errors=[message])
            print(json.dumps(result, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
