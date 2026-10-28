import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai4science.citation_cli import main
from ai4science.zotero_local import ZoteroError

PROJECT = Path(__file__).resolve().parents[1]


class FakeZotero:
    def doctor(self, library_id=0, library_kind='users'):
        return {'connection': 'local', 'desktop_running': 'reachable', 'api_enabled': True,
                'api_version': '3', 'server_id': 'test-server', 'library_accessible': True,
                'write_authorization': 'not_checked', 'errors': []}

    def get_item(self, library, key, *, library_kind='users'):
        if key == 'ZZZZZZZZ':
            raise ZoteroError('not_found', 'Local Zotero returned HTTP 404', 404)
        return {'key': key, 'version': 7, 'data': {'key': key, 'itemType': 'journalArticle',
                'title': 'Verified Science', 'date': '2024', 'DOI': '10.1234/example',
                'creators': [{'creatorType': 'author', 'lastName': 'Smith'}],
                'tags': [{'tag': 'personal'}, {'tag': 'research-unread'}], 'collections': []}}

    def get_attachments(self, *args, **kwargs):
        return []

    def list_items(self, library, **kwargs):
        return [self.get_item(library, 'ABCD2345')]

    def search_items(self, library, query, **kwargs):
        return [self.get_item(library, 'ABCD2345')]

    def export(self, library, keys, format, **kwargs):
        if format == 'csljson': return b'[{"id":"ABCD2345"}]'
        if format == 'bib': return b'<div class="csl-bib-body">example</div>'
        return b'@article{a, title={Verified Science}}'


class CitationCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=PROJECT / 'workspace')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = ['--workspace', str(self.root), '--task-id', 'test', '--library', '0']

    def call(self, args):
        out = io.StringIO()
        with patch('ai4science.citation_cli.ZoteroLocalClient', return_value=FakeZotero()), contextlib.redirect_stdout(out):
            code = main(self.base + args)
        return code, json.loads(out.getvalue())

    def test_get_and_nonexistent(self):
        code, result = self.call(['get', '--item-key', 'ABCD2345', '--attachments'])
        self.assertEqual(code, 0)
        self.assertEqual(result['affected_records'][0]['zotero_item_key'], 'ABCD2345')
        self.assertIsNone(result['affected_records'][0]['citation_key'])
        code, result = self.call(['get', '--item-key', 'ZZZZZZZZ'])
        self.assertEqual(code, 2)
        self.assertEqual(result['execution_status'], 'blocked')
        self.assertIn('404', result['errors'][0])

    def test_export_and_no_overwrite(self):
        args = ['export', '--item-key', 'ABCD2345', '--format', 'bibtex', '--output', 'ref.bib']
        code, result = self.call(args)
        self.assertEqual(code, 0)
        self.assertEqual(result['exported_artifacts'][0]['path'], 'ref.bib')
        before = (self.root / 'ref.bib').read_bytes()
        code, result = self.call(args)
        self.assertEqual(code, 2)
        self.assertEqual((self.root / 'ref.bib').read_bytes(), before)

    def test_dry_run_preserves_other_tags_and_never_writes(self):
        code, result = self.call(['status-plan', '--item-key', 'ABCD2345', '--target', 'research-reading'])
        self.assertEqual(code, 0)
        plan = result['proposed_changes'][0]
        self.assertFalse(plan['applied'])
        self.assertEqual(plan['expected_version'], 7)
        self.assertTrue(plan['identity_scope_complete'])
        self.assertIn({'tag': 'personal'}, plan['after_tags'])
        self.assertEqual(result['applied_changes'], [])

    def test_plan_import_only_suggests_and_is_bounded(self):
        search_result = {'results': [{'title': 'Verified Science', 'doi': '10.1234/EXAMPLE', 'authors': ['Smith'],
                                      'year': 2024, 'publication_type': 'journal_article'}]}
        (self.root / 'search.json').write_text(json.dumps(search_result))
        code, result = self.call(['plan-import', '--search-result', 'search.json'])
        self.assertEqual(code, 0)
        self.assertFalse(result['proposed_changes'][0]['applied'])
        self.assertEqual(result['proposed_changes'][0]['duplicate_candidates'][0]['classification'], 'exact_match')
        self.assertEqual(result['applied_changes'], [])

    def test_changed_local_server_blocks_entire_read(self):
        fake = FakeZotero()
        base = fake.doctor
        calls = 0
        def switched(library_id=0, library_kind='users'):
            nonlocal calls
            calls += 1
            info = base(library_id, library_kind)
            info['server_id'] = 'server-before' if calls == 1 else 'server-after'
            return info
        fake.doctor = switched
        output = io.StringIO()
        with patch('ai4science.citation_cli.ZoteroLocalClient', return_value=fake), contextlib.redirect_stdout(output):
            code = main(self.base + ['get', '--item-key', 'ABCD2345'])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(result['execution_status'], 'blocked')
        self.assertEqual(result['affected_records'], [])
        self.assertIn('identity_changed', result['errors'][0])

    def test_missing_server_id_remains_unknown_with_warning(self):
        fake = FakeZotero()
        base = fake.doctor
        def no_id(library_id=0, library_kind='users'):
            info = base(library_id, library_kind)
            info['server_id'] = None
            return info
        fake.doctor = no_id
        output = io.StringIO()
        with patch('ai4science.citation_cli.ZoteroLocalClient', return_value=fake), contextlib.redirect_stdout(output):
            code = main(self.base + ['get', '--item-key', 'ABCD2345'])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertIsNone(result['affected_records'][0]['zotero_server_id'])
        self.assertTrue(any('identity could not be verified' in w for w in result['warnings']))

    def test_wrong_item_key_rejected_before_status_plan(self):
        fake = FakeZotero()
        def wrong_item(library, key, *, library_kind='users'):
            return {'key': 'EFGH2345', 'version': 1, 'data': {'key': 'EFGH2345', 'itemType': 'journalArticle', 'tags': []}}
        fake.get_item = wrong_item
        output = io.StringIO()
        with patch('ai4science.citation_cli.ZoteroLocalClient', return_value=fake), contextlib.redirect_stdout(output):
            code = main(self.base + ['status-plan', '--item-key', 'ABCD2345', '--target', 'research-reading'])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(result['proposed_changes'], [])
        self.assertIn('invalid_response', result['errors'][0])

    def test_model_usage_unknown_and_network_not_automatic(self):
        with patch('ai4science.citation_cli.validate_metadata') as validate:
            validate.return_value = {'status': 'unverified', 'warnings': [], 'fields': {}}
            code, result = self.call(['verify', '--item-key', 'ABCD2345'])
        self.assertEqual(code, 0)
        self.assertFalse(validate.call_args.kwargs['perform_lookup'])
        self.assertIsNone(result['usage_metrics']['input_tokens'])
        self.assertEqual(result['usage_metrics']['token_measurement'], 'unknown')
