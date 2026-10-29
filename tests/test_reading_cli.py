import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ai4science.reading_cli import main

PROJECT = Path(__file__).resolve().parents[1]


class ReadingCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=PROJECT / 'workspace')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = ['--workspace', str(self.root)]
        self.analysis = {'paper_id': 'paper', 'metadata': {}, 'sections': {'Paper Overview': '摘要级分析。'},
                         'limitations': ['仅摘要可用。'], 'claim_evidence': []}
        (self.root / 'analysis.json').write_text(json.dumps(self.analysis), encoding='utf-8')
        self.row = {'schema_version': '1.0', 'title': 'A Study', 'authors': ['A'], 'year': 2024,
                    'doi': None, 'abstract': 'The work reports a result.', 'abstract_availability': 'available'}
        (self.root / 'search.json').write_text(json.dumps({'results': [self.row]}), encoding='utf-8')

    def test_missing_pdf_and_zotero_are_blocked(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(self.base + ['inspect', '--pdf', 'missing.pdf']), 2)
        self.assertFalse((self.root / 'reading_card.md').exists())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(self.base + ['zotero', '--item-key', 'ITEM']), 2)
        self.assertIn('not connected', out.getvalue())

    def test_abstract_only_and_duplicate_preserves_card(self):
        args = self.base + ['finalize', '--record', 'search.json', '--analysis', 'analysis.json',
                            '--output-dir', 'reading', '--task-id', 'test']
        with contextlib.redirect_stdout(io.StringIO()) as first_output:
            self.assertEqual(main(args), 0)
        first = json.loads(first_output.getvalue())['output_artifacts']
        result_ref = next(ref for ref in first if ref['path'].endswith('.json'))
        result = json.loads((self.root / result_ref['path']).read_text())
        self.assertEqual((result['reading_mode'], result['evidence_scope']), ('abstract', 'abstract'))
        card = self.root / next(ref['path'] for ref in first if ref['path'].endswith('.md'))
        with card.open('a') as f: f.write('\nuser comment')
        with contextlib.redirect_stdout(io.StringIO()) as second_output:
            self.assertEqual(main(args), 0)
        second = json.loads(second_output.getvalue())['output_artifacts']
        self.assertNotEqual(str(card), str(self.root / next(ref['path'] for ref in second if ref['path'].endswith('.md'))))
        self.assertIn('user comment', card.read_text())

    def test_misreported_abstract_and_fabricated_excerpt_are_blocked(self):
        self.row['abstract_availability'] = 'missing'
        (self.root / 'search.json').write_text(json.dumps({'results': [self.row]}))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(self.base + ['abstract', '--record', 'search.json']), 2)
        self.row['abstract_availability'] = 'available'
        (self.root / 'search.json').write_text(json.dumps({'results': [self.row]}))
        self.analysis['claim_evidence'] = [{'kind': 'evidence', 'excerpt': 'Not in the abstract'}]
        (self.root / 'analysis.json').write_text(json.dumps(self.analysis))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(self.base + ['finalize', '--record', 'search.json', '--analysis', 'analysis.json',
                                               '--output-dir', 'other', '--task-id', 'test']), 2)
        self.assertFalse((self.root / 'other/reading_card.md').exists())

    def test_abstract_identity_is_per_record_and_state_is_conservative(self):
        self.analysis.pop('paper_id')
        self.analysis['metadata'] = {'reading_status': 'research-verified'}
        (self.root / 'analysis.json').write_text(json.dumps(self.analysis))
        second = dict(self.row, title='A Different Study')
        (self.root / 'search.json').write_text(json.dumps({'results': [self.row, second]}))
        refs = []
        for index in (0, 1):
            out = io.StringIO()
            args = self.base + ['finalize', '--record', 'search.json', '--index', str(index),
                                '--analysis', 'analysis.json', '--task-id', f'test-{index}']
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(args), 0)
            refs.append(json.loads(out.getvalue())['output_artifacts'][0]['path'])
        self.assertNotEqual(refs[0], refs[1])
        self.assertIn('reading_status: "research-reading"', (self.root / refs[0]).read_text())
