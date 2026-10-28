"""Page-selective inspection and evidence-checked publication of Codex analysis.

The caller supplies the scientific analysis; this tool does not run a model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .contracts import EvidenceReference, ExecutionResult, UsageMetrics, create_artifact, validate_workspace_path
from .pdf_inspection import PDFInspectionError, extract_chunks, inspect_pdf
from .reading_output import reading_output_dir, render_reading_card, save_reading_outputs


def _root(value):
    root = Path(value).resolve(strict=True)
    project_workspace = (Path(__file__).resolve().parents[2] / 'workspace').resolve(strict=True)
    root.relative_to(project_workspace)
    if not root.is_dir():
        raise ValueError('workspace must be a directory')
    return root


def _json_file(root, relative):
    file = validate_workspace_path(root, relative, must_exist=True)
    if file.stat().st_size > 5_000_000:
        raise ValueError('JSON input exceeds 5 MB')
    with file.open(encoding='utf-8') as stream:
        return json.load(stream)


def _record(root, path, index):
    raw = _json_file(root, path)
    records = raw.get('results') if isinstance(raw, dict) else None
    if not isinstance(records, list) or not 0 <= index < len(records) or not isinstance(records[index], dict):
        raise ValueError('SearchResult file or index is invalid')
    row = records[index]
    if row.get('schema_version') != '1.0' or row.get('abstract_availability') != 'available' or not isinstance(row.get('title'), str) or not row['title'].strip():
        raise ValueError('SearchResult version, title or abstract status is invalid')
    if not isinstance(row.get('abstract'), str) or not row['abstract'].strip():
        raise ValueError('SearchResult has no available abstract; no full text can be inferred')
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect a paper and save supplied evidence-linked reading analysis.')
    parser.add_argument('--workspace', default='workspace')
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='Inspect one PDF, optionally returning selected pages')
    inspect.add_argument('--pdf', required=True, help='Workspace-relative PDF path')
    inspect.add_argument('--page', type=int, action='append', default=[])
    inspect.add_argument('--max-chars', type=int, default=20000, help='Maximum selected page characters, at most 50000')
    inspect.add_argument('--cache-dir', default='cache/pdf')
    abstract = sub.add_parser('abstract', help='Inspect one SearchResult abstract')
    abstract.add_argument('--record', required=True)
    abstract.add_argument('--index', type=int, default=0)
    zotero = sub.add_parser('zotero', help='Report the unavailable Zotero bridge')
    zotero.add_argument('--item-key', required=True)
    final = sub.add_parser('finalize', help='Save a supplied analysis; no LLM call is made')
    group = final.add_mutually_exclusive_group(required=True)
    group.add_argument('--pdf')
    group.add_argument('--record')
    final.add_argument('--index', type=int, default=0)
    final.add_argument('--analysis', required=True, help='Workspace-relative JSON written by the analyzing agent')
    final.add_argument('--output-dir', help='Workspace-relative directory; default uses stable paper ID')
    final.add_argument('--task-id', required=True)
    args = parser.parse_args(argv)
    try:
        root = _root(args.workspace)
        if args.command == 'zotero':
            print(json.dumps({'status': 'blocked', 'error': 'Project Zotero adapter is not connected', 'item_key': args.item_key}))
            return 2
        if args.command == 'abstract':
            row = _record(root, args.record, args.index)
            print(json.dumps({'status': 'completed', 'evidence_scope': 'abstract', 'record': row}, ensure_ascii=False))
            return 0
        if args.command == 'inspect':
            data = inspect_pdf(root, args.pdf, cache_dir=args.cache_dir)
            if not 1 <= args.max_chars <= 50000:
                raise ValueError('max-chars must be between 1 and 50000')
            summary = {k: data[k] for k in ('source_document', 'document_hash', 'parser_version', 'page_count', 'metadata_candidates', 'warnings', 'cache_hit')}
            summary['sections'] = data['sections'][:100]
            summary['label_mentions'] = data['label_mentions'][:100]
            summary['section_count'] = len(data['sections'])
            summary['label_mention_count'] = len(data['label_mentions'])
            summary['status'] = 'completed'
            summary['page_status'] = [{'pdf_page': p['pdf_page'], 'text_status': p['text_status']} for p in data['pages']]
            if args.page:
                if len(args.page) > 10:
                    raise ValueError('at most 10 explicitly selected pages')
                chunks = extract_chunks(data, page_numbers=tuple(args.page), chunk_chars=6000)
                remaining = args.max_chars
                selected = []
                for chunk in chunks:
                    if remaining <= 0:
                        break
                    item = dict(chunk)
                    item['text'] = item['text'][:remaining]
                    remaining -= len(item['text'])
                    selected.append(item)
                summary['chunks'] = selected
                summary['text_truncated'] = sum(len(x['text']) for x in chunks) > args.max_chars
            print(json.dumps(summary, ensure_ascii=False))
            return 0
        analysis = _json_file(root, args.analysis)
        if not isinstance(analysis, dict):
            raise ValueError('analysis must be an object')
        source_path = args.pdf or args.record
        source = create_artifact(root, source_path)
        pages = None
        if args.pdf:
            # Re-extract from source on finalize: cache and analysis JSON are not evidence authorities.
            inspection = inspect_pdf(root, args.pdf)
            if inspection['document_hash'] != source.sha256:
                raise ValueError('source PDF changed during inspection')
            pages = inspection['pages']
            # A page containing some text may still include unreadable images or tables.
            scope = 'partial_text'
            mode = 'deep'
        else:
            row = _record(root, args.record, args.index)
            scope, mode = 'abstract', 'abstract'
            norm = lambda value: ' '.join(value.split())
            for claim in analysis.get('claim_evidence', []):
                if (isinstance(claim, dict) and claim.get('kind') in ('evidence', 'author_interpretation')
                        and isinstance(claim.get('excerpt'), str) and claim['excerpt'].strip()
                        and norm(claim['excerpt']) not in norm(row['abstract'])):
                    raise ValueError('claim excerpt not present in the available abstract')
        default_paper_id = source.sha256 if args.pdf else (f"doi:{row['doi'].strip().lower()}" if isinstance(row.get('doi'), str) and row['doi'].strip() else f'search:{source.sha256}:{args.index}')
        paper_id = analysis.get('paper_id') or default_paper_id
        output_dir = args.output_dir or reading_output_dir(paper_id)
        meta = dict(analysis.get('metadata', {}))
        if not args.pdf:
            for field in ('title', 'authors', 'year', 'doi'):
                meta[field] = row.get(field)
        # Frontmatter is a local reading stage, never an assertion of Zotero state or comprehension.
        meta.update(source_pdf=source_path if args.pdf else None, source_hash=source.sha256,
                    evidence_scope=scope, reading_status='research-reading')
        card = render_reading_card(meta, analysis.get('sections', {}))
        usage = UsageMetrics()
        references = [EvidenceReference(source, 'Authorized source document', 'PDF physical pages' if args.pdf else f'SearchResult index {args.index}').to_dict()]
        zotero_key = meta.get('zotero_item_key')
        suggestion = analysis.get('suggested_zotero_status')
        handoff = None
        if zotero_key and suggestion:
            handoff = {'schema_version': '1.0', 'action': 'propose_reading_status', 'zotero_item_key': zotero_key,
                       'suggested_status': suggestion, 'understanding_verified': False, 'requires_approval': True,
                       'reason': 'Proposed by reading agent; review and authorization required.'}
        if suggestion == 'research-verified':
            raise ValueError('CLI cannot verify user understanding; verified requires an actual reviewed answer')
        result = {'schema_version': '1.0', 'task_id': args.task_id, 'paper_id': paper_id,
                  'zotero_item_key': zotero_key, 'source_document': source.to_dict(), 'document_hash': source.sha256,
                  'reading_mode': mode, 'evidence_scope': scope, 'analysis_status': analysis.get('analysis_status', 'draft'),
                  'reading_card_path': output_dir.rstrip('/') + '/reading_card.md', 'evidence_references': references,
                  'limitations': analysis.get('limitations', []), 'unresolved_questions': analysis.get('unresolved_questions', []),
                  'suggested_next_actions': analysis.get('suggested_next_actions', []), 'suggested_zotero_status': suggestion,
                  'usage_metrics': usage.to_dict(), 'execution': ExecutionResult(task_id=args.task_id, executor='reading_cli',
                        status='completed', usage_metrics=usage).to_dict(), 'citation_handoff': handoff,
                  'claim_evidence': analysis.get('claim_evidence', [])}
        card_ref, result_ref = save_reading_outputs(root, output_dir, result, card, pages=pages)
        print(json.dumps({'status': 'completed', 'analysis_status': result['analysis_status'],
                          'evidence_scope': scope, 'output_artifacts': [card_ref, result_ref]}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, PDFInspectionError, json.JSONDecodeError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
