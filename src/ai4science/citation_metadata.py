"""Conservative, read-only citation metadata checks and duplicate suggestions.

Crossref lookup reuses the bounded Search client. Nothing here changes Zotero.
A Crossref hit is a registry assertion, not proof of independent DOI resolution.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .literature_search import normalize_doi
from .literature_sources import verify_crossref_doi

FIELDS = ('doi', 'title', 'authors', 'publication_year', 'venue', 'volume', 'issue',
          'pages_or_article_number', 'source_url', 'publication_type')
_SOURCE_KEYS = {'publication_year': 'year', 'pages_or_article_number': 'pages_or_article_number'}


def _doi(value: Any) -> str | None:
    normalized = normalize_doi(value)
    return normalized if normalized and re.fullmatch(r'10\.\d{4,9}/[^\s?#]{1,300}', normalized) else None


def _key(value: Any) -> str:
    if not isinstance(value, str):
        return ''
    return ' '.join(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', value).casefold()))


def _comparable(field: str, value: Any) -> Any:
    if field == 'doi':
        return _doi(value)
    if field == 'authors':
        return tuple(_key(v) for v in value if _key(v)) if isinstance(value, list) else ()
    if field == 'publication_year':
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    return _key(value)


def validate_metadata(record: dict, *, lookup: dict | None = None,
                      cache_dir: Path | None = None, timeout: float = 10.0,
                      perform_lookup: bool = False) -> dict:
    """Compare supplied fields with a DOI lookup, never fill or modify a record.

    ``lookup`` has the existing verify_crossref_doi result shape. Network access
    is opt-in through perform_lookup. Full verified requires all ten fields to
    be present and equal; Crossref's current mapper lacks several, so the
    practical outcome normally is partially_verified.
    """
    if not isinstance(record, dict):
        raise ValueError('record must be an object')
    original_doi = record.get('doi')
    doi = _doi(original_doi)
    result = {'status': 'unverified', 'source': None, 'retrieved_at': None,
              'fields': {field: 'unknown' for field in FIELDS}, 'warnings': []}
    if not doi:
        result['warnings'].append('No valid DOI; no DOI lookup performed.')
        return result
    if perform_lookup and lookup is not None:
        raise ValueError('provide lookup or request network lookup, not both')
    if perform_lookup:
        try:
            lookup = verify_crossref_doi(doi, cache_dir=cache_dir, timeout=timeout)
        except ValueError as exc:
            result['warnings'].append('DOI lookup rejected: ' + str(exc))
            return result
    if not isinstance(lookup, dict) or lookup.get('status') != 'ok' or not isinstance(lookup.get('item'), dict):
        result['warnings'].append('Crossref lookup not requested or unavailable; metadata remains unverified.')
        if isinstance(lookup, dict):
            result['source'] = lookup.get('source')
            result['retrieved_at'] = lookup.get('retrieved_at')
        return result
    result['source'] = lookup.get('source') or 'crossref'
    result['retrieved_at'] = lookup.get('retrieved_at')
    source = lookup['item']
    for field in FIELDS:
        left = _comparable(field, record.get(field))
        right = _comparable(field, source.get(_SOURCE_KEYS.get(field, field)))
        if left and right:
            result['fields'][field] = 'match' if left == right else 'conflict'
    if 'conflict' in result['fields'].values():
        result['status'] = 'conflict'
        result['warnings'].append('Conflicting values require review; no values were overwritten.')
    elif all(value == 'match' for value in result['fields'].values()):
        result['status'] = 'verified'
    elif result['fields']['doi'] == 'match' and result['fields']['title'] == 'match':
        result['status'] = 'partially_verified'
    else:
        result['warnings'].append('DOI and title must both match before marking fields partially verified.')
    result['warnings'].append('Crossref lookup is not an independent DOI resolver check.')
    return result


def _is_preprint(record: dict) -> bool:
    doi = _doi(record.get('doi')) or ''
    return record.get('publication_type') in ('preprint', 'preprintArticle') or doi.startswith('10.48550/arxiv.')


def detect_duplicate(left: dict, right: dict) -> dict:
    """Classify a pair; results are suggestions and never merge or delete data."""
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError('records must be objects')
    def answer(classification: str, reason: str) -> dict:
        return {'classification': classification, 'reason': reason}
    lib1, lib2 = left.get('zotero_library_id'), right.get('zotero_library_id')
    key1, key2 = left.get('zotero_item_key'), right.get('zotero_item_key')
    kind1, kind2 = left.get('zotero_library_kind'), right.get('zotero_library_kind')
    server1, server2 = left.get('zotero_server_id'), right.get('zotero_server_id')
    same_server = bool(server1 and server2 and server1 == server2)
    if (kind1 in ('users', 'groups') and kind1 == kind2 and same_server
            and lib1 is not None and lib2 is not None and str(lib1) == str(lib2)
            and key1 and key1 == key2):
        return answer('exact_match', 'Same Zotero server, library kind, library ID and item key.')
    d1, d2 = _doi(left.get('doi')), _doi(right.get('doi'))
    t1, t2 = _key(left.get('title')), _key(right.get('title'))
    same_title = bool(t1 and t1 == t2)
    authors1 = _comparable('authors', left.get('authors'))
    authors2 = _comparable('authors', right.get('authors'))
    year1, year2 = left.get('publication_year'), right.get('publication_year')
    if _is_preprint(left) != _is_preprint(right) and (same_title or (d1 and d1 == d2)):
        return answer('related_version', 'Preprint and publication may be versions; manual review required.')
    if d1 and d1 == d2:
        return answer('exact_match', 'Normalized DOIs match; review conflicting metadata before any action.')
    if d1 and d2 and d1 != d2:
        return answer('distinct', 'Different DOI identifiers; records are not automatically merged.')
    if same_title and authors1 and authors1 == authors2 and year1 and year1 == year2:
        return answer('probable_duplicate', 'Title, author sequence and year match; manual review required.')
    if t1 and t2 and SequenceMatcher(None, t1, t2).ratio() >= 0.9:
        return answer('uncertain', 'Similar titles alone do not establish identity.')
    return answer('uncertain', 'Insufficient evidence to establish identity or distinction.')


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _year(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and 1000 <= value <= 9999:
        return value
    if isinstance(value, str):
        match = re.search(r'(?<!\d)([12]\d{3})(?!\d)', value)
        return int(match.group(1)) if match else None
    return None


def _empty_record() -> dict:
    return {'schema_version': '1.0', 'zotero_library_id': None, 'zotero_item_key': None, 'zotero_library_kind': None, 'zotero_server_id': None,
            'citation_key': None, 'doi': None, 'title': None, 'authors': [],
            'publication_year': None, 'venue': None, 'volume': None, 'issue': None,
            'pages_or_article_number': None, 'publication_type': None, 'source_url': None,
            'collections': [], 'tags': [], 'reading_status': None,
            'metadata_verification_status': 'unverified', 'reading_card_path': None,
            'attachment_references': []}


def citation_record_from_zotero(item: dict, library_id: str | int, *, attachments: list | None = None,
                                library_kind: str | None = None, server_id: str | None = None) -> dict:
    """Map a Zotero API item without opening attached files or inventing a key."""
    if not isinstance(item, dict) or not isinstance(library_id, (str, int)) or isinstance(library_id, bool) or not str(library_id).strip():
        raise ValueError('item and explicit library ID required')
    if library_kind not in (None, 'users', 'groups'):
        raise ValueError('library kind must be users, groups, or None')
    if server_id is not None and not _text(server_id):
        raise ValueError('server ID must be nonempty when supplied')
    data = item.get('data', item)
    if not isinstance(data, dict):
        raise ValueError('invalid Zotero item data')
    key = _text(data.get('key')) or _text(item.get('key'))
    if not key:
        raise ValueError('Zotero item key required')
    result = _empty_record()
    authors = []
    for author in data.get('creators') if isinstance(data.get('creators'), list) else []:
        if not isinstance(author, dict) or author.get('creatorType') not in (None, 'author'):
            continue
        name = _text(author.get('name')) or _text(' '.join(x for x in (_text(author.get('firstName')), _text(author.get('lastName'))) if x))
        if name:
            authors.append(name)
    tags = [tag['tag'] for tag in (data.get('tags') if isinstance(data.get('tags'), list) else []) if isinstance(tag, dict) and _text(tag.get('tag'))]
    states = [tag for tag in tags if tag in {'research-unread', 'research-screened', 'research-reading',
                                              'research-deepread', 'research-reread', 'research-verified'}]
    types = {'journalArticle': 'journal_article', 'conferencePaper': 'conference_paper',
             'preprint': 'preprint', 'book': 'book'}
    result.update(zotero_library_id=library_id, zotero_item_key=key,
                  zotero_library_kind=library_kind, zotero_server_id=_text(server_id),
                  doi=_doi(data.get('DOI')), title=_text(data.get('title')), authors=authors,
                  publication_year=_year(data.get('date')),
                  venue=_text(data.get('publicationTitle')) or _text(data.get('proceedingsTitle')),
                  volume=_text(data.get('volume')), issue=_text(data.get('issue')),
                  pages_or_article_number=_text(data.get('pages')) or _text(data.get('articleNumber')),
                  publication_type=types.get(data.get('itemType'), _text(data.get('itemType'))),
                  source_url=_text(data.get('url')), collections=[x for x in (data.get('collections') if isinstance(data.get('collections'), list) else []) if _text(x)],
                  tags=tags, reading_status=states[0] if len(states) == 1 else None)
    if attachments is not None:
        if not isinstance(attachments, list):
            raise ValueError('attachments must be a list')
        for item in attachments:
            if not isinstance(item, dict):
                continue
            child = item.get('data', item)
            if not isinstance(child, dict):
                continue
            result['attachment_references'].append({'item_key': _text(child.get('key')) or _text(item.get('key')),
                'title': _text(child.get('title')), 'content_type': _text(child.get('contentType'))})
    return result


def citation_record_from_search(item: dict) -> dict:
    """Map a SearchResult without asserting Zotero membership or verification."""
    if not isinstance(item, dict):
        raise ValueError('search item must be an object')
    result = _empty_record()
    authors = item.get('authors')
    result.update(title=_text(item.get('title')), authors=[x for x in authors if _text(x)] if isinstance(authors, list) else [],
                  publication_year=_year(item.get('year')), venue=_text(item.get('venue')),
                  doi=_doi(item.get('doi')), source_url=_text(item.get('source_url')),
                  publication_type=_text(item.get('publication_type')))
    return result


def validate_citation_record(record: dict, workspace_root: Path | None = None) -> None:
    """Check the CitationRecord contract without requiring referenced files to exist.

    If a workspace root is provided, resolve existing symlinks and check the
    boundary as well. Callers must repeat that check immediately before I/O.
    """
    from pathlib import PurePosixPath, PureWindowsPath
    from .contracts import validate_workspace_path

    if not isinstance(record, dict) or set(record) != set(_empty_record()):
        raise ValueError('CitationRecord has missing or unknown fields')
    if record['schema_version'] != '1.0':
        raise ValueError('unsupported CitationRecord schema version')
    library_id = record['zotero_library_id']
    if library_id is not None and (isinstance(library_id, bool) or not isinstance(library_id, (str, int))):
        raise ValueError('invalid Zotero library ID')
    nullable_strings = ('zotero_item_key', 'citation_key', 'doi', 'title', 'venue', 'volume', 'issue',
                        'pages_or_article_number', 'publication_type', 'source_url', 'reading_card_path',
                        'zotero_server_id')
    for field in nullable_strings:
        if record[field] is not None and not isinstance(record[field], str):
            raise ValueError(f'{field} must be a string or null')
    if record['zotero_server_id'] is not None and not record['zotero_server_id']:
        raise ValueError('empty Zotero server ID')
    if record['zotero_library_kind'] not in (None, 'users', 'groups'):
        raise ValueError('invalid Zotero library kind')
    year = record['publication_year']
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999):
        raise ValueError('invalid publication year')
    for field in ('authors', 'collections', 'tags'):
        if not isinstance(record[field], list) or any(not isinstance(x, str) for x in record[field]):
            raise ValueError(f'{field} must be an array of strings')
    if record['reading_status'] not in (None, 'research-unread', 'research-screened', 'research-reading',
                                         'research-deepread', 'research-reread', 'research-verified'):
        raise ValueError('invalid reading status')
    if record['metadata_verification_status'] not in ('verified', 'partially_verified', 'unverified', 'conflict'):
        raise ValueError('invalid metadata verification status')
    refs = record['attachment_references']
    if not isinstance(refs, list):
        raise ValueError('attachment_references must be an array')
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'item_key', 'title', 'content_type'}:
            raise ValueError('invalid attachment reference')
        if any(value is not None and not isinstance(value, str) for value in ref.values()):
            raise ValueError('attachment reference fields must be strings or null')
    path = record['reading_card_path']
    if path is not None:
        if (not path.strip() or '\\' in path or '\x00' in path or PurePosixPath(path).is_absolute()
                or PureWindowsPath(path).is_absolute() or PureWindowsPath(path).drive
                or any(part in ('', '.', '..') for part in path.split('/'))):
            raise ValueError('reading_card_path must be a portable workspace-relative path')
        if workspace_root is not None:
            validate_workspace_path(workspace_root, path, must_exist=False)
