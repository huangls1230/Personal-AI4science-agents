"""Bounded text-PDF inspection; extracted content is untrusted research data.

Text extraction is not visual inspection, OCR, or a security sandbox. Printed page
numbers, figure contents, formulas, and metadata must be verified independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import re

from .contracts import validate_workspace_path

PARSER_VERSION = 'pdf-inspection-2'
_METADATA_MAX_CHARS = 1000


class PDFInspectionError(ValueError):
    """PDF cannot be safely inspected within the requested limits."""


@dataclass(frozen=True)
class PDFLimits:
    max_file_bytes: int = 30_000_000
    max_pages: int = 200
    max_text_chars: int = 3_000_000
    max_cache_bytes: int = 16_000_000

    def __post_init__(self):
        if any(type(n) is not int or n <= 0 for n in
               (self.max_file_bytes, self.max_pages, self.max_text_chars, self.max_cache_bytes)):
            raise ValueError('PDF limits must be positive integers')


# Only common heading names are detected. These are suggestions, not verified structure.
_HEADING = re.compile(
    r'^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?'
    r'(abstract|introduction|background|related work|materials and methods|methods|'
    r'methodology|experimental setup|experiments|results|discussion|limitations|'
    r'conclusions?|references|appendix)\s*$', re.IGNORECASE)
_LABEL = re.compile(r'\b(?:fig(?:ure)?\.?|table|equation|eq\.)\s*\d+[a-z]?\b', re.IGNORECASE)


def _load_pypdf():
    try:
        import pypdf
        return pypdf
    except ImportError as exc:
        raise PDFInspectionError('PDF parsing requires the optional pypdf dependency') from exc


def _cached(cache_path: Path, digest: str, parser: str, limits: PDFLimits):
    try:
        if cache_path.stat().st_size > limits.max_cache_bytes:
            return None
        data = json.loads(cache_path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or data.get('document_hash') != digest
                or data.get('parser_version') != parser
                or not isinstance(data.get('pages'), list)
                or type(data.get('page_count')) is not int
                or data['page_count'] != len(data['pages'])
                or not 1 <= data['page_count'] <= limits.max_pages):
            return None
        if any(not isinstance(p, dict) or type(p.get('pdf_page')) is not int
               or p['pdf_page'] != i or not isinstance(p.get('text'), str)
               or p.get('text_status') not in ('extracted', 'empty_or_unextractable', 'extraction_failed')
               for i, p in enumerate(data['pages'], 1)):
            return None
        if sum(len(p['text']) for p in data['pages']) > limits.max_text_chars:
            return None
        # Local caches may be damaged or modified. Validate all structures used by
        # callers, including offsets; this does not prove cached text matches PDF.
        sections, labels, warnings = (data.get('sections'), data.get('label_mentions'),
                                      data.get('warnings'))
        if not isinstance(sections, list) or not isinstance(labels, list) or not isinstance(warnings, list):
            return None
        if any(not isinstance(w, str) for w in warnings):
            return None
        metadata = data.get('metadata_candidates')
        if not isinstance(metadata, dict) or set(metadata) != {'title', 'author'}:
            return None
        for candidate in metadata.values():
            if candidate is not None and (not isinstance(candidate, dict)
                    or set(candidate) != {'value', 'status', 'truncated'}
                    or not isinstance(candidate['value'], str)
                    or not candidate['value'].strip()
                    or len(candidate['value']) > _METADATA_MAX_CHARS
                    or candidate['status'] != 'source_reported_unverified'
                    or type(candidate['truncated']) is not bool):
                return None
        previous = (0, -1)
        for item in sections:
            if not isinstance(item, dict) or not isinstance(item.get('heading'), str):
                return None
            page, offset = item.get('pdf_page'), item.get('text_offset')
            if (type(page) is not int or not 1 <= page <= data['page_count']
                    or type(offset) is not int or not 0 <= offset < len(data['pages'][page - 1]['text'])
                    or item.get('status') != 'heuristic_unverified'
                    or (page, offset) < previous
                    or not _HEADING.fullmatch(item['heading'].strip())
                    or data['pages'][page - 1]['text'][offset:].splitlines()[0].strip() != item['heading']):
                return None
            previous = (page, offset)
        for item in labels:
            if not isinstance(item, dict) or not isinstance(item.get('label'), str):
                return None
            page, offset = item.get('pdf_page'), item.get('text_offset')
            if (type(page) is not int or not 1 <= page <= data['page_count']
                    or type(offset) is not int or not 0 <= offset < len(data['pages'][page - 1]['text'])
                    or item.get('status') != 'text_mention_unverified'
                    or not _LABEL.fullmatch(item['label'])
                    or not data['pages'][page - 1]['text'].startswith(item['label'], offset)):
                return None
        return data
    except (OSError, ValueError, TypeError, UnicodeError):
        return None


def inspect_pdf(workspace_root: Path, path: str, *, cache_dir: str | None = None,
                limits: PDFLimits | None = None) -> dict:
    """Inspect one authorized workspace PDF with numbered pages and optional cache.

    Cache is an optimization, not an evidence source: independently verify important
    claims against the source PDF. `cache_dir` is an opt-in workspace-relative path.
    """
    limits = limits or PDFLimits()
    pypdf = _load_pypdf()
    try:
        source = validate_workspace_path(workspace_root, path, must_exist=True)
        with source.open('rb') as stream:
            data = stream.read(limits.max_file_bytes + 1)
    except (OSError, ValueError) as exc:
        raise PDFInspectionError(f'PDF is missing, unreadable or outside workspace: {exc}') from exc
    if len(data) > limits.max_file_bytes:
        raise PDFInspectionError('PDF exceeds max_file_bytes')
    if b'%PDF-' not in data[:1024]:
        raise PDFInspectionError('input is not a PDF (missing PDF header)')
    digest = sha256(data).hexdigest()
    parser = f'{PARSER_VERSION}/pypdf-{pypdf.__version__}'
    cache_path = None
    if cache_dir is not None:
        try:
            # Validate before and after mkdir to reject traversal and symlink escape.
            folder = validate_workspace_path(workspace_root, cache_dir)
            folder.mkdir(parents=True, exist_ok=True)
            folder = validate_workspace_path(workspace_root, cache_dir)
            if not folder.is_dir():
                raise ValueError('cache path is not a directory')
            name = sha256((digest + '\0' + parser).encode()).hexdigest() + '.json'
            cache_path = validate_workspace_path(workspace_root, f'{cache_dir}/{name}')
            cached = _cached(cache_path, digest, parser, limits)
            if cached is not None:
                cached['source_document'] = path
                cached['cache_hit'] = True
                return cached
        except (OSError, ValueError) as exc:
            raise PDFInspectionError(f'invalid or inaccessible PDF cache: {exc}') from exc
    import io
    try:
        reader = pypdf.PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise PDFInspectionError('encrypted PDF is not supported')
        page_count = len(reader.pages)
        if page_count == 0 or page_count > limits.max_pages:
            raise PDFInspectionError('PDF page count is zero or exceeds max_pages')
        pages, sections, labels, warnings = [], [], [], []
        metadata_candidates = {'title': None, 'author': None}
        try:
            # Embedded PDF metadata is a source claim, not verified paper identity.
            metadata = reader.metadata
            for key, attr in (('title', 'title'), ('author', 'author')):
                value = getattr(metadata, attr, None) if metadata is not None else None
                if isinstance(value, str) and value.strip():
                    value = value.strip()
                    metadata_candidates[key] = {
                        'value': value[:_METADATA_MAX_CHARS],
                        'status': 'source_reported_unverified',
                        'truncated': len(value) > _METADATA_MAX_CHARS,
                    }
        except Exception:
            warnings.append('PDF embedded metadata could not be read; identity remains unverified.')
        total_chars = 0
        for index, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ''
                status = 'extracted' if text.strip() else 'empty_or_unextractable'
            except Exception:
                text, status = '', 'extraction_failed'
            total_chars += len(text)
            if total_chars > limits.max_text_chars:
                raise PDFInspectionError('extracted text exceeds max_text_chars')
            if status != 'extracted':
                warnings.append(f'PDF page {index}: {status}; scanned or image content may be unreadable')
            pages.append({'pdf_page': index, 'text': text, 'text_status': status})
            offset = 0
            for line in text.splitlines(keepends=True):
                if _HEADING.fullmatch(line.strip()):
                    sections.append({'heading': line.strip(), 'pdf_page': index,
                                     'text_offset': offset, 'status': 'heuristic_unverified'})
                offset += len(line)
            for match in _LABEL.finditer(text):
                labels.append({'label': match.group(), 'pdf_page': index,
                               'text_offset': match.start(), 'status': 'text_mention_unverified'})
    except PDFInspectionError:
        raise
    except Exception as exc:
        raise PDFInspectionError(f'invalid or unsupported PDF: {type(exc).__name__}') from exc
    warnings.append('Heading and figure/table/equation mentions are heuristic and unverified; inspect source pages.')
    warnings.append('PDF page numbers are one-based physical pages, not verified printed page numbers.')
    result = {'source_document': path, 'document_hash': digest, 'parser_version': parser,
              'page_count': page_count, 'pages': pages, 'sections': sections,
              'label_mentions': labels, 'metadata_candidates': metadata_candidates,
              'warnings': warnings, 'cache_hit': False}
    if cache_path is not None:
        payload = json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(payload) <= limits.max_cache_bytes:
            try:
                # Do not overwrite arbitrary existing content or follow cache-file symlinks.
                with cache_path.open('xb') as stream:
                    stream.write(payload)
            except FileExistsError:
                pass  # Invalid/stale cache is ignored, never trusted or overwritten.
            except OSError as exc:
                warnings.append(f'cache write failed: {type(exc).__name__}')
    return result


def extract_chunks(inspection: dict, *, page_numbers: tuple[int, ...] | None = None,
                   chunk_chars: int = 6000) -> list[dict]:
    """Select pages and split text with exact physical page and text offset provenance."""
    if type(chunk_chars) is not int or chunk_chars <= 0:
        raise ValueError('chunk_chars must be a positive integer')
    pages = inspection['pages']
    selected = set(page_numbers) if page_numbers is not None else None
    if selected is not None and (not selected or any(type(n) is not int or n < 1 or n > len(pages) for n in selected)):
        raise ValueError('invalid PDF page selection')
    chunks = []
    for page in pages:
        if selected is not None and page['pdf_page'] not in selected:
            continue
        for offset in range(0, len(page['text']), chunk_chars):
            chunks.append({'pdf_page': page['pdf_page'], 'text_offset': offset,
                           'text': page['text'][offset:offset + chunk_chars]})
    return chunks


def extract_section_chunks(inspection: dict, heading: str, *, occurrence: int = 1,
                           chunk_chars: int = 6000) -> list[dict]:
    """Select a detected section until the next detected heading.

    The section boundary is heuristic and must be checked against the PDF.
    Chunks retain physical page numbers and offsets within extracted page text.
    """
    if not isinstance(heading, str) or not heading.strip():
        raise ValueError('heading must be a non-empty string')
    if type(occurrence) is not int or occurrence < 1 or type(chunk_chars) is not int or chunk_chars <= 0:
        raise ValueError('occurrence and chunk_chars must be positive integers')
    sections = inspection['sections']
    matches = [i for i, item in enumerate(sections)
               if item['heading'].casefold() == heading.strip().casefold()]
    if occurrence > len(matches):
        raise ValueError('requested detected heading occurrence does not exist')
    position = matches[occurrence - 1]
    start = sections[position]
    end = sections[position + 1] if position + 1 < len(sections) else None
    chunks = []
    for page in inspection['pages']:
        number = page['pdf_page']
        if number < start['pdf_page'] or (end is not None and number > end['pdf_page']):
            continue
        left = start['text_offset'] if number == start['pdf_page'] else 0
        right = end['text_offset'] if end is not None and number == end['pdf_page'] else len(page['text'])
        for offset in range(left, right, chunk_chars):
            chunks.append({'pdf_page': number, 'text_offset': offset,
                           'text': page['text'][offset:min(offset + chunk_chars, right)],
                           'section_boundary_status': 'heuristic_unverified'})
    return chunks
