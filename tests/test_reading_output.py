import json
import tempfile
import unittest
from pathlib import Path

from ai4science.contracts import ArtifactReference, EvidenceReference, ExecutionResult, UsageMetrics, create_artifact
from ai4science.reading_output import (propose_vault_export, render_reading_card,
                                      save_reading_outputs, validate_reading_result)


class ReadingOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'source.pdf').write_bytes(b'%PDF-1.4\nexample')
        self.source = create_artifact(self.root, 'source.pdf')
        usage = UsageMetrics()
        self.result = {
            'schema_version': '1.0', 'task_id': 'read-1', 'paper_id': self.source.sha256,
            'zotero_item_key': None, 'source_document': self.source.to_dict(),
            'document_hash': self.source.sha256, 'reading_mode': 'deep',
            'evidence_scope': 'partial_text', 'analysis_status': 'draft',
            'reading_card_path': 'notes/reading_card.md', 'evidence_references': [],
            'limitations': ['Figures not inspected'], 'unresolved_questions': [],
            'suggested_next_actions': [], 'suggested_zotero_status': None,
            'usage_metrics': usage.to_dict(),
            'execution': ExecutionResult(task_id='read-1', executor='codex_native',
                                         status='completed', usage_metrics=usage).to_dict(),
            'citation_handoff': None, 'claim_evidence': [],
        }
        self.card = render_reading_card({'title': 'Original Title', 'authors': ['A'],
                                         'source_hash': self.source.sha256},
                                        {'Personal Notes': 'My own notes'})

    def tearDown(self):
        self.tmp.cleanup()

    def claim(self):
        return {'claim': 'Authors report a result', 'kind': 'author_interpretation',
                'excerpt': 'This is a verifiable source quote.', 'pdf_page': 2,
                'printed_page': None, 'section': 'Results', 'figure': None,
                'table': None, 'equation': None, 'location_status': 'verified',
                'evidence_strength': None, 'assumptions': None,
                'alternative_explanation': None, 'assessment': None}

    def test_write_contract_card_and_preserve_duplicate(self):
        card_ref, result_ref = save_reading_outputs(self.root, 'notes', self.result, self.card)
        self.assertTrue(ArtifactReference.from_dict(card_ref).verify(self.root))
        self.assertTrue(ArtifactReference.from_dict(result_ref).verify(self.root))
        value = json.loads((self.root / result_ref['path']).read_text())
        validate_reading_result(value, self.root)
        with (self.root / card_ref['path']).open('a') as stream:
            stream.write('\nA user annotation\n')
        with self.assertRaises(FileExistsError):
            save_reading_outputs(self.root, 'notes', self.result, self.card)
        self.assertIn('A user annotation', (self.root / card_ref['path']).read_text())

    def test_verified_quote_requires_real_page_text(self):
        self.result['claim_evidence'] = [self.claim()]
        with self.assertRaisesRegex(ValueError, 'not found'):
            save_reading_outputs(self.root, 'notes', self.result, self.card,
                                 pages=[{'pdf_page': 2, 'text': 'Different text.'}])
        self.assertFalse((self.root / 'notes/reading_card.md').exists())
        save_reading_outputs(self.root, 'notes', self.result, self.card,
                             pages=[{'pdf_page': 2, 'text': 'Context: This is a verifiable\nsource quote.'}])

    def test_abstract_cannot_claim_deep(self):
        self.result['evidence_scope'] = 'abstract'
        with self.assertRaisesRegex(ValueError, 'deep mode'):
            validate_reading_result(self.result, self.root, verify_files=False)

    def test_citation_handoff_is_only_a_proposal(self):
        self.result['zotero_item_key'] = 'ABCD1234'
        self.result['suggested_zotero_status'] = 'research-deepread'
        self.result['citation_handoff'] = {
            'schema_version': '1.0', 'action': 'propose_reading_status',
            'zotero_item_key': 'ABCD1234', 'suggested_status': 'research-deepread',
            'understanding_verified': False, 'requires_approval': True, 'reason': 'Card ready for review'}
        with self.assertRaisesRegex(ValueError, 'completed deep analysis'):
            validate_reading_result(self.result, self.root, verify_files=False)
        self.result['analysis_status'] = 'completed'
        self.result['claim_evidence'] = [self.claim()]
        self.result['evidence_references'] = [EvidenceReference(
            artifact=self.source, description='PDF page 2', locator='PDF page 2').to_dict()]
        validate_reading_result(self.result, self.root, verify_files=False)
        self.result['suggested_zotero_status'] = 'research-verified'
        self.result['citation_handoff']['suggested_status'] = 'research-verified'
        self.result['citation_handoff']['understanding_verified'] = True
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            validate_reading_result(self.result, self.root, verify_files=False)

    def test_completed_requires_source_and_substantive_evidence(self):
        self.result['analysis_status'] = 'completed'
        with self.assertRaisesRegex(ValueError, 'source evidence'):
            validate_reading_result(self.result, self.root, verify_files=False)
        self.result['evidence_references'] = [EvidenceReference(
            artifact=self.source, description='Page 2', locator='PDF page 2').to_dict()]
        with self.assertRaisesRegex(ValueError, 'source claim'):
            validate_reading_result(self.result, self.root, verify_files=False)
        self.result['claim_evidence'] = [self.claim()]
        self.result['claim_evidence'][0]['location_status'] = 'unverified'
        with self.assertRaisesRegex(ValueError, 'matched physical page'):
            validate_reading_result(self.result, self.root, verify_files=False)
        self.result['claim_evidence'][0]['location_status'] = 'verified'
        save_reading_outputs(self.root, 'notes', self.result, self.card,
                             pages=[{'pdf_page': 2, 'text': 'This is a verifiable source quote.'}])

    def test_abstract_deepread_rejected_even_when_completed(self):
        self.result['reading_mode'] = 'abstract'
        self.result['evidence_scope'] = 'abstract'
        self.result['analysis_status'] = 'completed'
        self.result['evidence_references'] = [EvidenceReference(
            artifact=self.source, description='Abstract').to_dict()]
        self.result['claim_evidence'] = [self.claim()]
        self.result['claim_evidence'][0]['location_status'] = 'unverified'
        self.result['suggested_zotero_status'] = 'research-deepread'
        with self.assertRaisesRegex(ValueError, 'completed deep analysis'):
            validate_reading_result(self.result, self.root, verify_files=False)

    def test_deepread_requires_card_sections_and_matched_excerpt(self):
        self.result['analysis_status'] = 'completed'
        self.result['zotero_item_key'] = 'ABCD1234'
        self.result['suggested_zotero_status'] = 'research-deepread'
        self.result['citation_handoff'] = {
            'schema_version': '1.0', 'action': 'propose_reading_status',
            'zotero_item_key': 'ABCD1234', 'suggested_status': 'research-deepread',
            'understanding_verified': False, 'requires_approval': True, 'reason': 'Awaiting approval'}
        self.result['evidence_references'] = [EvidenceReference(
            artifact=self.source, description='Page 2', locator='PDF page 2').to_dict()]
        self.result['claim_evidence'] = [self.claim()]
        pages = [{'pdf_page': 2, 'text': 'This is a verifiable source quote.'}]
        # A default card has mandatory placeholder sections and must not qualify.
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            save_reading_outputs(self.root, 'notes', self.result, self.card, pages=pages)
        sections = {'Paper Overview': '本文讨论一个可重复检验的研究方法。',
                    'Research Question': '作者提出研究问题并明确目标。',
                    'Methodology': '论文说明测试条件和具体方法。',
                    'Claim–Evidence Table': '作者结论对应第二页的原文摘录。',
                    'Limitations': '本分析无法验证未检查的图像。'}
        card = render_reading_card({'title': 'A Title'}, sections)
        with self.assertRaisesRegex(ValueError, 'not found'):
            save_reading_outputs(self.root, 'notes', self.result, card,
                                 pages=[{'pdf_page': 2, 'text': 'Not the quote.'}])
        self.assertFalse((self.root / 'notes/reading_card.md').exists())
        save_reading_outputs(self.root, 'notes', self.result, card, pages=pages)
        self.assertTrue((self.root / 'notes/reading_result.json').is_file())

    def test_vault_blocked_preserves_local_card(self):
        card_ref, _ = save_reading_outputs(self.root, 'notes', self.result, self.card)
        proposal = propose_vault_export(ArtifactReference.from_dict(card_ref), self.root)
        self.assertEqual('blocked', proposal['status'])
        self.assertIn('not authorized', proposal['reason'])
        self.assertTrue((self.root / 'notes/reading_card.md').is_file())
        self.assertIn('not implemented', propose_vault_export(ArtifactReference.from_dict(card_ref), self.root, authorized=True)['reason'])

    def test_unreadable_formula_and_figure_are_marked_unverified(self):
        claim = self.claim()
        claim.update(claim='图片和公式未读取', excerpt=None, pdf_page=None,
                     figure='unverified', equation='unverified', location_status='unverified')
        self.result['claim_evidence'] = [claim]
        card = render_reading_card({}, {'Algorithms / Architecture': '图示和公式未能读取，未验证。'})
        save_reading_outputs(self.root, 'notes', self.result, card)
        saved = json.loads((self.root / 'notes/reading_result.json').read_text())
        self.assertEqual(saved['claim_evidence'][0]['location_status'], 'unverified')
        self.assertIn('未能读取，未验证', (self.root / 'notes/reading_card.md').read_text())

    def test_escape_and_hash_mismatch_rejected(self):
        self.result['reading_card_path'] = '../notes/reading_card.md'
        with self.assertRaises(ValueError):
            save_reading_outputs(self.root, '../notes', self.result, self.card)
        self.result['reading_card_path'] = 'notes/reading_card.md'
        self.result['document_hash'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'document_hash'):
            validate_reading_result(self.result, self.root, verify_files=False)


if __name__ == '__main__':
    unittest.main()
