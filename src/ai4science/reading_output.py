"""Reading output serialization; no scientific claims or external writes are generated.

All content is supplied by the caller. Source documents and outputs are confined
by the existing workspace path and hash validation, not an OS sandbox.
"""
from __future__ import annotations

import copy
from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Any

from .contracts import (ArtifactReference, EvidenceReference, ExecutionResult,
                        UsageMetrics, create_artifact, validate_workspace_path)

VERSION = '1.0'
_FIELDS = {'schema_version', 'task_id', 'paper_id', 'zotero_item_key',
           'source_document', 'document_hash', 'reading_mode', 'evidence_scope',
           'analysis_status', 'reading_card_path', 'evidence_references',
           'limitations', 'unresolved_questions', 'suggested_next_actions',
           'suggested_zotero_status', 'usage_metrics', 'execution', 'citation_handoff', 'claim_evidence'}
_SECTIONS = (
    ('Paper Overview', '论文概览'), ('Research Background', '研究背景'),
    ('Research Question', '研究问题'), ('Claimed Research Gap', '作者所述研究空白'),
    ('Core Contributions', '核心贡献'), ('Methodology', '研究方法'),
    ('Algorithms / Architecture', '算法与架构'), ('Experimental Setup', '实验设置'),
    ('Results', '结果'), ('Claim–Evidence Table', '论点与证据'),
    ('Critical Analysis', '批判性分析'), ('Limitations', '局限'),
    ('Connection to My Research', '与本人研究的联系'),
    ('Candidate Research Opportunities', '候选研究机会'), ('Open Questions', '开放问题'),
    ('Personal Notes', '个人笔记'), ('Mentor Questions', '导师问题'),
    ('Next Reading Action', '下一步阅读行动'),
)
_METADATA = ('title', 'authors', 'year', 'doi', 'zotero_item_key', 'citekey',
             'source_pdf', 'source_hash', 'reading_date', 'reading_status',
             'evidence_scope', 'related_research_project', 'tags')


def _string(value: Any, field: str, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a non-empty string' + (' or null' if optional else ''))


def _string_list(value: Any, name: str) -> None:
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f'{name} must be a list of non-empty strings')


def validate_reading_result(result: dict[str, Any], workspace_root: Path, *, verify_files: bool = True) -> None:
    """Validate the reading envelope and embedded core contracts and references.

    File/hash consistency is checkable; this function does not re-extract PDF pages
    or recheck excerpts, and cannot establish the truth or entailment of analysis.
    """
    if not isinstance(result, dict) or set(result) != _FIELDS:
        raise ValueError('ReadingResult requires exactly the documented fields')
    if result['schema_version'] != VERSION:
        raise ValueError('unsupported ReadingResult schema_version')
    for field in ('task_id', 'paper_id'):
        _string(result[field], field)
    for field in ('zotero_item_key', 'document_hash', 'reading_card_path', 'suggested_zotero_status'):
        _string(result[field], field, optional=True)
    if result['reading_mode'] not in ('deep', 'abstract', 'inspection'):
        raise ValueError('invalid reading_mode')
    if result['evidence_scope'] not in ('full_text', 'partial_text', 'abstract', 'metadata'):
        raise ValueError('invalid evidence_scope')
    if result['evidence_scope'] in ('abstract', 'metadata') and result['reading_mode'] == 'deep':
        raise ValueError('deep mode requires accessible full or partial text')
    if result['analysis_status'] not in ('draft', 'partial', 'completed', 'blocked'):
        raise ValueError('invalid analysis_status')
    for field in ('limitations', 'unresolved_questions', 'suggested_next_actions'):
        _string_list(result[field], field)
    source = result['source_document']
    if source is not None:
        source = ArtifactReference.from_dict(source)
        if result['document_hash'] != source.sha256:
            raise ValueError('document_hash must match source_document sha256')
        if verify_files and not source.verify(workspace_root):
            raise ValueError('source_document hash mismatch')
    elif result['document_hash'] is not None:
        raise ValueError('document_hash requires source_document')
    if result['reading_card_path'] is not None:
        validate_workspace_path(workspace_root, result['reading_card_path'], must_exist=verify_files)
    if not isinstance(result['evidence_references'], list):
        raise ValueError('evidence_references must be a list')
    references = [EvidenceReference.from_dict(x) for x in result['evidence_references']]
    for ref in references:
        if verify_files and not ref.artifact.verify(workspace_root):
            raise ValueError('evidence artifact hash mismatch')
    validate_claim_evidence(result['claim_evidence'])
    if result['analysis_status'] == 'completed':
        if source is None or not any(ref.artifact == source for ref in references):
            raise ValueError('completed analysis requires the source and a source evidence reference')
        supported = [claim for claim in result['claim_evidence']
                     if claim['kind'] in ('evidence', 'author_interpretation') and claim['excerpt']]
        if not supported:
            raise ValueError('completed analysis requires at least one source claim with an excerpt')
        if result['evidence_scope'] in ('full_text', 'partial_text') and not any(
                claim['location_status'] == 'verified' for claim in supported):
            raise ValueError('completed PDF analysis requires a matched physical page excerpt')
    usage = UsageMetrics.from_dict(result['usage_metrics'])
    execution = ExecutionResult.from_dict(result['execution'])
    if execution.task_id != result['task_id'] or execution.usage_metrics != usage:
        raise ValueError('embedded execution task_id and usage must match ReadingResult')
    if result['analysis_status'] == 'completed' and execution.status != 'completed':
        raise ValueError('completed analysis requires completed execution')
    if verify_files:
        execution.validate(workspace_root)
    suggestion = result['suggested_zotero_status']
    if suggestion == 'research-verified':
        raise ValueError('research-verified is unsupported: user comprehension has not been validated by this runtime')
    if suggestion not in (None, 'research-reading', 'research-deepread', 'research-reread'):
        raise ValueError('invalid suggested_zotero_status')
    if suggestion == 'research-deepread' and (result['analysis_status'] != 'completed'
            or result['reading_mode'] != 'deep' or result['evidence_scope'] not in ('full_text', 'partial_text')):
        raise ValueError('research-deepread requires completed deep analysis of accessible PDF text')
    handoff = result['citation_handoff']
    if handoff is not None:
        if not isinstance(handoff, dict) or set(handoff) != {'schema_version', 'action', 'zotero_item_key', 'suggested_status', 'understanding_verified', 'requires_approval', 'reason'}:
            raise ValueError('invalid Citation handoff fields')
        if handoff['schema_version'] != VERSION or handoff['action'] != 'propose_reading_status':
            raise ValueError('invalid Citation handoff type or version')
        _string(handoff['zotero_item_key'], 'handoff zotero_item_key')
        _string(handoff['reason'], 'handoff reason')
        if type(handoff['understanding_verified']) is not bool or handoff['requires_approval'] is not True:
            raise ValueError('Citation handoff requires explicit approval and boolean verification')
        if handoff['zotero_item_key'] != result['zotero_item_key'] or handoff['suggested_status'] != suggestion or suggestion is None:
            raise ValueError('handoff must match the reading result')


def validate_claim_evidence(claims: Any, pages: list[dict] | None = None) -> None:
    """Validate claim fields and, when pages are supplied, exact quoted page location.

    A quote match establishes only that text occurs in supplied extracted text for
    a physical PDF page. Printed page, section, figure, table and equation labels
    are not checked; they require human verification. A match does not establish
    the claim's truth, interpretation, or that a figure was inspected.
    """
    fields = {'claim', 'kind', 'excerpt', 'pdf_page', 'printed_page', 'section',
              'figure', 'table', 'equation', 'location_status', 'evidence_strength',
              'assumptions', 'alternative_explanation', 'assessment'}
    if not isinstance(claims, list):
        raise ValueError('claim_evidence must be a list')
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != fields:
            raise ValueError('invalid claim evidence fields')
        _string(claim['claim'], 'claim')
        if claim['kind'] not in ('evidence', 'author_interpretation', 'agent_inference', 'speculation'):
            raise ValueError('invalid claim kind')
        if claim['location_status'] not in ('verified', 'unverified'):
            raise ValueError('invalid location status')
        for key in ('excerpt', 'printed_page', 'section', 'figure', 'table', 'equation',
                    'evidence_strength', 'assumptions', 'alternative_explanation', 'assessment'):
            _string(claim[key], key, optional=True)
        page = claim['pdf_page']
        if page is not None and (type(page) is not int or page < 1):
            raise ValueError('pdf_page must be a positive integer or null')
        if claim['location_status'] == 'verified':
            if page is None or not claim['excerpt']:
                raise ValueError('verified location requires PDF page and direct text excerpt')
            if pages is not None:
                matches = [p for p in pages if isinstance(p, dict) and p.get('pdf_page') == page]
                normalize = lambda text: ' '.join(text.split())
                if len(matches) != 1 or not isinstance(matches[0].get('text'), str) or normalize(claim['excerpt']) not in normalize(matches[0]['text']):
                    raise ValueError('verified excerpt not found on specified PDF page')


def reading_output_dir(paper_id: str) -> str:
    """Stable location for a caller-supplied identifier; identical IDs share a card.

    This is exact identifier matching, not bibliographic identity resolution.
    Citation owns cross-identifier duplicate detection.
    """
    _string(paper_id, 'paper_id')
    return 'notes/papers/' + sha256(paper_id.strip().encode('utf-8')).hexdigest()


def render_reading_card(metadata: dict[str, Any], sections: dict[str, str]) -> str:
    """Render supplied analysis; no unsupplied data or scientific interpretation is invented."""
    if not isinstance(metadata, dict) or not isinstance(sections, dict):
        raise ValueError('metadata and sections must be dictionaries')
    if set(metadata) - set(_METADATA) or set(sections) - {k for k, _ in _SECTIONS}:
        raise ValueError('unknown metadata or section')
    if any(not isinstance(v, str) for v in sections.values()):
        raise ValueError('section values must be strings')
    # JSON scalars and arrays are valid YAML 1.2. Reject structured/multiline keys.
    lines = ['---']
    for key in _METADATA:
        value = metadata.get(key)
        if value is not None and not (isinstance(value, (str, int)) and not isinstance(value, bool) or
                                      isinstance(value, list) and all(isinstance(x, str) for x in value)):
            raise ValueError(f'unsupported metadata value for {key}')
        lines.append(f'{key}: {json.dumps(value, ensure_ascii=False)}')
    lines.append('---\n')
    for key, title in _SECTIONS:
        value = sections.get(key, '').strip()
        lines.append(f'## {title}\n\n{value if value else "待分析或不适用；尚未验证。"}\n')
    return '\n'.join(lines)


def _validate_deepread_card(card: str) -> None:
    """Reject missing and obvious placeholder sections, not assess scientific quality."""
    required = ('论文概览', '研究问题', '研究方法', '论点与证据', '局限')
    headings = list(re.finditer(r'^##[ \t]+(.+?)[ \t]*$', card, re.MULTILINE))
    sections: dict[str, list[str]] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(card)
        sections.setdefault(match.group(1).strip(), []).append(card[match.end():end].strip())
    placeholders = {'待分析或不适用；尚未验证。', '待分析', '待验证', '不适用', '暂无',
                    '未提供', '待补充', '未分析', 'unknown', 'n/a', 'none', 'todo', 'tbd'}
    for section in required:
        if len(sections.get(section, [])) != 1:
            raise ValueError(f'research-deepread card requires exactly one {section} section')
        text = sections[section][0]
        normalized = ' '.join(text.casefold().split()).strip(' #*-：:。.;；')
        if normalized in {x.casefold().strip(' #*-：:。.;；') for x in placeholders}:
            raise ValueError(f'research-deepread card section {section} is a placeholder')
        if len(re.findall(r'[\w\u3400-\u9fff]', text, re.UNICODE)) < 8:
            raise ValueError(f'research-deepread card section {section} is empty or too short')


def save_reading_outputs(workspace_root: Path, output_dir: str, result: dict[str, Any], card: str, *, pages: list[dict] | None = None) -> tuple[dict, dict]:
    """Create reading_card.md and reading_result.json exactly once, without overwrite.

    A repeated execution raises FileExistsError and preserves every existing byte.
    The standard execution result can reference the card; the result file's own hash
    is returned separately to avoid a self-referential hash.
    """
    if not isinstance(card, str) or not card.strip():
        raise ValueError('card must be non-empty')
    card_path = output_dir.rstrip('/') + '/reading_card.md'
    result_path = output_dir.rstrip('/') + '/reading_result.json'
    if result.get('reading_card_path') != card_path:
        raise ValueError('reading_card_path must identify the requested output card')
    result = copy.deepcopy(result)
    validate_reading_result(result, workspace_root, verify_files=False)
    if result['suggested_zotero_status'] == 'research-deepread':
        _validate_deepread_card(card)
    if any(c['location_status'] == 'verified' for c in result['claim_evidence']):
        if pages is None or result['source_document'] is None:
            raise ValueError('verified claim location requires source and extracted PDF pages')
        validate_claim_evidence(result['claim_evidence'], pages)
    for rel in (card_path, result_path):
        if validate_workspace_path(workspace_root, rel).exists():
            raise FileExistsError(f'output already exists: {rel}; no content was overwritten')
    directory = validate_workspace_path(workspace_root, output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        target = validate_workspace_path(workspace_root, card_path)
        with target.open('x', encoding='utf-8') as stream:
            created.append(target)
            stream.write(card)
        card_ref = create_artifact(workspace_root, card_path).to_dict()
        outputs = result['execution'].setdefault('output_artifacts', [])
        outputs[:] = [item for item in outputs if item.get('path') != card_path] + [card_ref]
        validate_reading_result(result, workspace_root, verify_files=True)
        target = validate_workspace_path(workspace_root, result_path)
        with target.open('x', encoding='utf-8') as stream:
            created.append(target)
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except Exception:
        for target in reversed(created):
            target.unlink(missing_ok=True)
        raise
    return create_artifact(workspace_root, card_path).to_dict(), create_artifact(workspace_root, result_path).to_dict()


def propose_vault_export(card: ArtifactReference, workspace_root: Path, *, authorized: bool = False) -> dict:
    """Report the state of an external vault export without modifying any vault."""
    if not card.verify(workspace_root):
        raise ValueError('local card hash mismatch')
    return {'status': 'blocked', 'local_artifact': card.to_dict(),
            'reason': ('External vault write is not authorized.' if not authorized else
                       'Vault writer is not implemented; permissions and conflicts were not checked.')}
