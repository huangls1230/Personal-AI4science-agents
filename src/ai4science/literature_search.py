"""Evidence-preserving search result processing; this module does not query services.

Source records, snippets, and URLs are untrusted data. Ranking is a transparent
lexical triage heuristic, not a judgment of scientific quality.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .contracts import create_artifact, validate_workspace_path

VERSION = '1.0'
PUBLICATION_TYPES = {'journal_article', 'conference_paper', 'preprint', 'book', 'other', 'unknown'}


def normalize_doi(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = unquote(value.strip()).lower()
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value)
    return value if re.fullmatch(r'10\.\d{4,9}/\S+', value) else None


def _title_key(title: Any) -> str:
    if not isinstance(title, str):
        return ''
    return ' '.join(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', title).casefold()))


def _clean_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _terms(terms: list[str]) -> list[str]:
    if not isinstance(terms, (list, tuple)) or any(not isinstance(t, str) for t in terms):
        raise ValueError('query_terms must be a list of strings')
    # Ignore punctuation and common boolean operators; no claim of semantic equivalence.
    return sorted({x for t in terms for x in _title_key(t).split() if x not in {'and', 'or', 'not'} and len(x) > 1})


def _verification(doi: str | None, title: str, verification: dict | None) -> dict:
    if doi is None:
        return {'status': 'no_doi', 'source': None, 'retrieved_at': None,
                'detail': 'No valid DOI supplied; independent DOI check was not possible.'}
    if not isinstance(verification, dict) or verification.get('status') != 'ok':
        error = verification.get('error') if isinstance(verification, dict) else None
        detail = 'Crossref DOI lookup unavailable, failed, or not requested; metadata is source-reported.'
        if isinstance(error, str) and error.strip():
            detail += ' Error: ' + error.strip()[:300]
        return {'status': 'unverified', 'source': 'crossref' if verification else None,
                'retrieved_at': verification.get('retrieved_at') if isinstance(verification, dict) else None,
                'detail': detail}
    item = verification.get('item')
    if not isinstance(item, dict) or normalize_doi(item.get('doi')) != doi or not _title_key(item.get('title')):
        return {'status': 'conflict', 'source': 'crossref', 'retrieved_at': verification.get('retrieved_at'),
                'detail': 'Crossref response lacks a matching DOI or title; investigate manually.'}
    match = _title_key(title) == _title_key(item['title'])
    return {'status': 'doi_title_match' if match else 'conflict', 'source': 'crossref',
            'retrieved_at': verification.get('retrieved_at'),
            'detail': 'Crossref DOI and normalized title match; authors, year, venue and content not independently verified.' if match
                      else 'Crossref title differs; investigate manually.'}


def _rank(result: dict, terms: list[str]) -> tuple[int, str, str]:
    text = _title_key(result['title'] + ' ' + (result.get('abstract') or ''))
    words = set(text.split())
    matched = sorted(set(terms) & words)
    score = len(matched) / len(terms) if terms else 0.0
    level = 'high' if score >= .6 else 'medium' if score >= .3 else 'low'
    reason = (f"Lexical title/abstract match: {len(matched)}/{len(terms)} query terms"
              f" ({', '.join(matched) if matched else 'none'}). "
              'This is triage, not a scientific quality score; method, evidence quality, novelty and recency require review.')
    return (len(matched), level, reason)


def build_results(source_responses: list[dict], query_terms: list[str],
                  verifications: dict[str, dict] | None = None, *, max_results: int = 20) -> dict:
    """Normalize, deduplicate conservatively, verify, rank, and cap output.

    `verifications` maps a DOI to the result of a *separate* Crossref DOI lookup.
    A DOI/title match does not verify all metadata or the scientific claims.
    Failed source responses remain visible, even when other sources succeeded.
    """
    if not isinstance(source_responses, list) or not source_responses:
        raise ValueError('at least one source response is required')
    if type(max_results) is not int or not 1 <= max_results <= 100:
        raise ValueError('max_results must be between 1 and 100')
    terms = _terms(query_terms)
    checks = {normalize_doi(k): v for k, v in (verifications or {}).items() if normalize_doi(k)}
    groups: list[dict] = []
    doi_groups: dict[str, dict] = {}
    sources = []
    malformed = 0
    for response in source_responses:
        if not isinstance(response, dict) or response.get('status') not in ('ok', 'error'):
            raise ValueError('each source response must have status ok or error')
        sources.append({k: response.get(k) for k in ('source', 'query', 'retrieved_at', 'status', 'error', 'page', 'limit', 'has_more', 'cached')})
        if response['status'] != 'ok':
            continue
        items = response.get('items', [])
        if not isinstance(items, list):
            raise ValueError('items must be a list')
        for item in items:
            if not isinstance(item, dict) or not _clean_text(item.get('title')):
                malformed += 1
                continue
            title = item['title'].strip()
            doi = normalize_doi(item.get('doi'))
            year = item.get('year') if type(item.get('year')) is int and 1000 <= item['year'] <= 9999 else None
            abstract = _clean_text(item.get('abstract'))
            fulltext_url = _clean_text(item.get('fulltext_url'))
            source = _clean_text(item.get('source')) or _clean_text(response.get('source')) or 'unknown'
            pub_type = item.get('publication_type') if item.get('publication_type') in PUBLICATION_TYPES else 'unknown'
            authors = [a.strip() for a in item.get('authors', []) if isinstance(a, str) and a.strip()] if isinstance(item.get('authors'), list) else []
            record = {'source': source, 'title': title, 'authors': authors, 'year': year,
                      'venue': _clean_text(item.get('venue')), 'doi': doi,
                      'source_url': _clean_text(item.get('source_url')), 'abstract': abstract,
                      'fulltext_url': fulltext_url, 'publication_type': pub_type,
                      'retrieved_at': response.get('retrieved_at')}
            # Only a shared normalized DOI establishes a merge. No-DOI records
            # remain separate; a title/year match alone is not reliable identity.
            group = doi_groups.get(doi) if doi else None
            if group is None:
                group = {'title': title, 'authors': authors, 'year': year,
                         'venue': record['venue'], 'doi': doi, 'source_url': record['source_url'],
                         'abstract': abstract, 'fulltext_url': fulltext_url,
                         'publication_type': pub_type, 'retrieved_at': response.get('retrieved_at'),
                         'source_records': [], 'metadata_conflicts': []}
                groups.append(group)
                if doi:
                    doi_groups[doi] = group
            group['source_records'].append(record)
            for field in ('title', 'authors', 'year', 'venue', 'publication_type'):
                a, b = group[field], record[field]
                if a and b and a != 'unknown' and b != 'unknown' and (field != 'title' or _title_key(a) != _title_key(b)) and a != b:
                    conflict = f'{field}: {a} | {b}'
                    if conflict not in group['metadata_conflicts']:
                        group['metadata_conflicts'].append(conflict)
            # Fill only missing fields; keep the original asserted source record.
            for field in ('authors', 'year', 'venue', 'source_url', 'abstract', 'fulltext_url', 'publication_type'):
                if not group[field] or group[field] == 'unknown':
                    group[field] = record[field]
    for group in groups:
        group['abstract_availability'] = 'available' if group['abstract'] else 'missing'
        group['fulltext_availability'] = 'link_reported' if group['fulltext_url'] else 'unknown'
        group['fulltext_downloaded'] = False
        verification = _verification(group['doi'], group['title'], checks.get(group['doi']))
        if verification['status'] == 'doi_title_match' and any(x.startswith('title:') for x in group['metadata_conflicts']):
            verification['status'] = 'conflict'
            verification['detail'] = 'Sources disagree on title despite DOI match; investigate manually.'
        group['verification_status'] = verification['status']
        group['verification'] = verification
        group['schema_version'] = VERSION
        group['_rank'], group['relevance_level'], group['relevance_reason'] = _rank(group, terms)
    groups.sort(key=lambda g: (-g['_rank'], _title_key(g['title']), g['doi'] or ''))
    total = len(groups)
    groups = groups[:max_results]
    for group in groups:
        del group['_rank']
    ok = sum(s['status'] == 'ok' for s in sources)
    status = 'blocked' if not ok else 'partial' if ok < len(sources) else 'completed'
    return {'schema_version': VERSION, 'status': status, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'query_terms': list(query_terms), 'sources': sources, 'malformed_records_skipped': malformed,
            'unique_count_before_limit': total, 'returned_count': len(groups), 'max_results': max_results,
            'results': groups}


def _md(value: Any) -> str:
    # Prevent untrusted newlines or Markdown syntax from injecting report structure.
    return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', str('' if value is None else value).replace('\n', ' ').replace('\r', ' '))


def render_report(payload: dict) -> str:
    lines = ['# Literature search report', '', f"Status: {_md(payload['status'])}",
             f"Generated at: {_md(payload['generated_at'])}",
             f"Unique before limit: {payload['unique_count_before_limit']}; returned: {payload['returned_count']}",
             '', '## Sources and queries', '']
    for s in payload['sources']:
        lines.append(f"- {_md(s['source'])}: {_md(s['status'])}; query: {_md(s['query'])}; retrieved: {_md(s['retrieved_at'])}; page: {_md(s['page'])}; has more: {_md(s['has_more'])}; error: {_md(s['error']) or 'none'}")
    lines += ['', '## Candidates', '', 'Levels are lexical triage, not scientific quality assessments. Full text links are source-reported and access has not been tested.', '']
    for i, r in enumerate(payload['results'], 1):
        lines.extend([f"### {i}. {_md(r['title'])}", '',
                      f"- Authors: {_md(', '.join(r['authors']) or 'unknown')}; year: {_md(r['year']) or 'unknown'}; venue: {_md(r['venue']) or 'unknown'}",
                      f"- DOI: {_md(r['doi']) or 'unknown'}; source URL: {_md(r['source_url']) or 'unknown'}",
                      f"- Publication type: {_md(r['publication_type'])}; abstract: {_md(r['abstract_availability'])}; full text: {_md(r['fulltext_availability'])}; downloaded: false",
                      f"- Verification: {_md(r['verification_status'])}; {_md(r['verification']['detail'])}",
                      f"- Relevance: {_md(r['relevance_level'])}; {_md(r['relevance_reason'])}",
                      f"- Metadata conflicts: {_md('; '.join(r['metadata_conflicts']) or 'none observed')}", ''])
    return '\n'.join(lines) + '\n'


def write_outputs(workspace_root: Path, output_dir: str, payload: dict) -> tuple[dict, dict]:
    """Create two new workspace outputs, refusing to replace existing files.

    Workspace root must be supplied from trusted project configuration. Path checks
    do not provide an OS sandbox against concurrent filesystem modification.
    """
    if not isinstance(payload, dict) or payload.get('schema_version') != VERSION:
        raise ValueError('invalid results payload')
    directory = validate_workspace_path(workspace_root, output_dir)
    if not directory.exists() or not directory.is_dir():
        raise ValueError('output directory must already exist inside workspace')
    paths = [f'{output_dir}/search_results.json', f'{output_dir}/search_report.md']
    # Refuse both if either output exists; create exclusively to avoid accidental replacement.
    for path in paths:
        if validate_workspace_path(workspace_root, path).exists():
            raise FileExistsError(path)
    data = [json.dumps(payload, ensure_ascii=False, indent=2) + '\n', render_report(payload)]
    created = []
    try:
        for path, content in zip(paths, data):
            target = validate_workspace_path(workspace_root, path)
            with target.open('x', encoding='utf-8') as stream:
                stream.write(content)
            created.append(target)
    except Exception:
        for target in created:
            target.unlink(missing_ok=True)
        raise
    return tuple(create_artifact(workspace_root, path).to_dict() for path in paths)
