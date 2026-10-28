"""A bounded local tool for Codex's literature-search role; no LLM orchestration."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .contracts import ArtifactReference, ExecutionResult, UsageMetrics, validate_workspace_path
from .literature_search import build_results, normalize_doi, write_outputs
from .literature_sources import search_source, verify_crossref_doi


def main(argv=None):
    parser = argparse.ArgumentParser(description='Search public scholarly metadata. Network queries leave this machine.')
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--query', action='append', required=True, help='Source query text; repeat for alternative keywords')
    parser.add_argument('--term', action='append', default=[], help='Relevance keyword; repeat as needed')
    parser.add_argument('--source-query', action='append', default=[], metavar='SOURCE=QUERY', help='Override the common query for one source using its native syntax')
    parser.add_argument('--source', action='append', choices=('crossref', 'openalex', 'semantic_scholar', 'arxiv'), required=True)
    parser.add_argument('--workspace', default='workspace', help='Trusted project workspace directory')
    parser.add_argument('--output-dir', required=True, help='Existing workspace-relative directory for new output files')
    parser.add_argument('--cache-dir', default='cache/literature', help='Workspace-relative cache directory')
    parser.add_argument('--page', type=int, default=1)
    parser.add_argument('--limit', type=int, default=10, help='Per query and source, maximum 50')
    parser.add_argument('--max-results', type=int, default=20, help='Maximum output candidates, at most 100')
    parser.add_argument('--verify-limit', type=int, default=5, help='Maximum separate Crossref DOI lookups, at most 20')
    parser.add_argument('--timeout', type=float, default=10.0, help='Maximum seconds per HTTP request, at most 30')
    parser.add_argument('--sensitivity', choices=('public', 'internal', 'sensitive'), required=True)
    parser.add_argument('--allow-network', action='store_true', help='Confirm sending queries to the named public services')
    args = parser.parse_args(argv)
    try:
        if not args.allow_network or args.sensitivity != 'public':
            raise ValueError('public sensitivity and --allow-network are required for external queries')
        if (not args.task_id.strip() or len(args.query) > 5 or len(set(args.source)) != len(args.source)
                or any(not q.strip() or len(q) > 2000 for q in args.query)):
            raise ValueError('task ID and valid queries required; at most five queries; duplicate sources are not allowed')
        if not 1 <= args.limit <= 50 or not 1 <= args.page <= 100 or not 1 <= args.max_results <= 100 or not 0 <= args.verify_limit <= 20 or not 0 < args.timeout <= 30:
            raise ValueError('limit, page, max-results, verify-limit or timeout outside supported range')
        overrides = {}
        for value in args.source_query:
            source, separator, query = value.partition('=')
            if not separator or source not in args.source or source in overrides or not query.strip() or len(query) > 2000:
                raise ValueError('invalid or duplicate source-specific query')
            overrides[source] = query
        root = Path(args.workspace).resolve(strict=True)
        # Contract roots must not be caller-selected external locations.
        project = Path(__file__).resolve().parents[2]
        root.relative_to(project / 'workspace')
        directory = validate_workspace_path(root, args.output_dir, must_exist=False)
        if not directory.is_dir():
            raise ValueError('output directory must already exist in the workspace')
        for name in ('search_results.json', 'search_report.md'):
            if validate_workspace_path(root, f'{args.output_dir}/{name}').exists():
                raise FileExistsError('output file already exists')
        cache = validate_workspace_path(root, args.cache_dir)
        keys = {'openalex': os.environ.get('OPENALEX_API_KEY'), 'semantic_scholar': os.environ.get('SEMANTIC_SCHOLAR_API_KEY')}
        responses = [search_source(source, query, limit=args.limit, page=args.page, cache_dir=cache,
                                   timeout=args.timeout, api_key=keys.get(source))
                     for source in args.source for query in ([overrides[source]] if source in overrides else args.query)]
        terms = args.term or args.query
        initial = build_results(responses, terms, max_results=args.max_results)
        checks = {}
        for row in initial['results']:
            doi = normalize_doi(row.get('doi'))
            if doi and len(checks) < args.verify_limit:
                try:
                    checks[doi] = verify_crossref_doi(doi, cache_dir=cache, timeout=args.timeout)
                except ValueError:
                    checks[doi] = {'status': 'error', 'error': 'DOI is invalid for lookup', 'retrieved_at': None}
        payload = build_results(responses, terms, checks, max_results=args.max_results)
        refs = write_outputs(root, args.output_dir, payload)
        search_status = payload['status']
        errors = tuple(f"{x['source']}: {x['error']}" for x in payload['sources'] if x['status'] != 'ok')
        status = 'completed' if search_status == 'completed' else 'blocked'
        result = ExecutionResult(task_id=args.task_id, executor='literature_search_cli', status=status,
                                 summary=f"search_status={search_status}; returned={payload['returned_count']}; DOI checks={len(checks)}",
                                 output_artifacts=tuple(ArtifactReference.from_dict(r) for r in refs),
                                 errors=errors, usage_metrics=UsageMetrics(model_calls=0))
        print(json.dumps(result.to_dict(), ensure_ascii=False))
        return 0 if search_status == 'completed' else 2
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
