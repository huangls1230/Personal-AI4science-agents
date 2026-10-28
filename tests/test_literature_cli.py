import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai4science.literature_cli import main

PROJECT = Path(__file__).resolve().parents[1]


class LiteratureCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=PROJECT / 'workspace')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'output').mkdir()
        self.args = ['--task-id', 'test', '--query', 'multi agent', '--term', 'multi',
                     '--source', 'crossref', '--workspace', str(self.root),
                     '--output-dir', 'output', '--allow-network', '--sensitivity', 'public']

    def test_end_to_end_mocked_source_and_unverified_doi(self):
        record = {'title': 'Multi agent systems', 'authors': ['A'], 'year': 2024, 'venue': None,
                  'doi': '10.1234/example', 'source_url': 'https://example.org', 'abstract': None,
                  'fulltext_url': None, 'publication_type': 'preprint', 'source': 'crossref'}
        response = {'source': 'crossref', 'query': 'multi agent', 'retrieved_at': '2026-01-01T00:00:00Z',
                    'status': 'ok', 'items': [record], 'page': 1, 'limit': 10, 'has_more': False, 'cached': False, 'error': None}
        stdout = io.StringIO()
        with patch('ai4science.literature_cli.search_source', return_value=response), \
             patch('ai4science.literature_cli.verify_crossref_doi', side_effect=ValueError('invalid')), \
             contextlib.redirect_stdout(stdout):
            self.assertEqual(main(self.args), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['output_artifacts']), 2)
        payload = json.loads((self.root / 'output/search_results.json').read_text())
        self.assertEqual(payload['results'][0]['verification_status'], 'unverified')
        self.assertEqual(payload['results'][0]['abstract_availability'], 'missing')
        self.assertFalse(payload['results'][0]['fulltext_downloaded'])
        with contextlib.redirect_stderr(io.StringIO()), patch('ai4science.literature_cli.search_source') as source:
            self.assertEqual(main(self.args), 2)
            source.assert_not_called()

    def test_sensitive_and_external_root_are_blocked_before_network(self):
        args = self.args[:-1] + ['sensitive']
        with contextlib.redirect_stderr(io.StringIO()), patch('ai4science.literature_cli.search_source') as source:
            self.assertEqual(main(args), 2)
            source.assert_not_called()
        args = list(self.args)
        args[args.index('--workspace') + 1] = str(PROJECT)
        with contextlib.redirect_stderr(io.StringIO()), patch('ai4science.literature_cli.search_source') as source:
            self.assertEqual(main(args), 2)
            source.assert_not_called()

    def test_source_failure_is_reported_and_not_success(self):
        response = {'source': 'crossref', 'query': 'multi agent', 'retrieved_at': '2026-01-01T00:00:00Z',
                    'status': 'error', 'items': [], 'page': 1, 'limit': 10, 'has_more': False,
                    'cached': False, 'error': 'HTTP 429'}
        stdout = io.StringIO()
        with patch('ai4science.literature_cli.search_source', return_value=response), contextlib.redirect_stdout(stdout):
            self.assertEqual(main(self.args), 2)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('HTTP 429', result['errors'][0])
        self.assertEqual(json.loads((self.root / 'output/search_results.json').read_text())['status'], 'blocked')

    def test_source_specific_queries_and_partial_results(self):
        def fake_search(source, query, **kwargs):
            return {'source': source, 'query': query, 'retrieved_at': '2026-01-01T00:00:00Z',
                    'status': 'ok' if source == 'crossref' else 'error', 'items': [], 'page': 1,
                    'limit': 10, 'has_more': False, 'cached': False,
                    'error': None if source == 'crossref' else 'HTTP 503'}
        stdout = io.StringIO()
        with patch('ai4science.literature_cli.search_source', side_effect=fake_search) as search, contextlib.redirect_stdout(stdout):
            self.assertEqual(main(self.args + ['--source', 'arxiv', '--source-query', 'arxiv=all:agent AND all:topology']), 2)
        self.assertEqual(search.call_count, 2)
        self.assertEqual(search.call_args_list[1].args[:2], ('arxiv', 'all:agent AND all:topology'))
        result = json.loads(stdout.getvalue())
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('HTTP 503', result['errors'][0])
        payload = json.loads((self.root / 'output/search_results.json').read_text())
        self.assertEqual(payload['status'], 'partial')
