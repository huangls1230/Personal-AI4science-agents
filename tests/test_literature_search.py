import json
import tempfile
import unittest
from pathlib import Path

from ai4science.literature_search import build_results, normalize_doi, write_outputs


def record(title='Multi agent network topology', doi='10.1234/XYZ', **extra):
    data = {'title': title, 'authors': ['A Researcher'], 'year': 2024,
            'venue': 'Journal', 'doi': doi, 'source_url': 'https://example.org/paper',
            'abstract': None, 'fulltext_url': None, 'publication_type': 'journal_article',
            'source': 'test'}
    data.update(extra)
    return data


def response(items, **extra):
    data = {'source': 'test', 'query': 'multi agent network',
            'retrieved_at': '2026-10-28T00:00:00Z', 'items': items, 'status': 'ok',
            'error': None, 'page': 1, 'limit': 10, 'has_more': False, 'cached': False}
    data.update(extra)
    return data


class SearchResultTests(unittest.TestCase):
    def test_duplicate_doi_and_absent_abstract(self):
        one = record(doi='https://doi.org/10.1234/XYZ')
        two = record(doi='10.1234/xyz', source='another')
        result = build_results([response([one, two])], ['agent', 'network'])
        self.assertEqual(result['returned_count'], 1)
        item = result['results'][0]
        self.assertEqual(item['doi'], '10.1234/xyz')
        self.assertEqual(len(item['source_records']), 2)
        self.assertEqual(item['abstract_availability'], 'missing')
        self.assertEqual(item['verification_status'], 'unverified')
        self.assertEqual(item['fulltext_availability'], 'unknown')
        self.assertFalse(item['fulltext_downloaded'])

    def test_independent_doi_verification_and_conflict(self):
        check = {'status': 'ok', 'item': record(), 'retrieved_at': '2026-10-28T01:00:00Z'}
        result = build_results([response([record()])], ['network'], {'10.1234/xyz': check})['results'][0]
        self.assertEqual(result['verification_status'], 'doi_title_match')
        self.assertIn('authors, year, venue', result['verification']['detail'])
        check['item']['title'] = 'A different paper'
        result = build_results([response([record()])], ['network'], {'10.1234/xyz': check})['results'][0]
        self.assertEqual(result['verification_status'], 'conflict')
        check['status'] = 'error'
        result = build_results([response([record()])], ['network'], {'10.1234/xyz': check})['results'][0]
        self.assertEqual(result['verification_status'], 'unverified')

    def test_relevance_sort_and_fulltext_link_is_not_proof_of_access(self):
        results = build_results([response([
            record(title='Graph overview', doi='10.1234/first', fulltext_url='https://example.org/a.pdf'),
            record(title='Multi agent network topology', doi='10.1234/second', abstract='topology study')])],
            ['multi agent network topology'])['results']
        self.assertEqual(results[0]['doi'], '10.1234/second')
        self.assertEqual(results[0]['relevance_level'], 'high')
        self.assertIn('not a scientific quality score', results[0]['relevance_reason'])
        self.assertEqual(results[1]['fulltext_availability'], 'link_reported')
        self.assertFalse(results[1]['fulltext_downloaded'])

    def test_errors_and_limits(self):
        failure = response([], source='unavailable', status='error', error='timeout')
        blocked = build_results([failure], ['network'])
        self.assertEqual(blocked['status'], 'blocked')
        partial = build_results([failure, response([record()])], ['network'])
        self.assertEqual(partial['status'], 'partial')
        self.assertEqual(partial['sources'][0]['error'], 'timeout')
        with self.assertRaises(ValueError):
            build_results([response([])], ['network'], max_results=101)

    def test_do_not_merge_distinct_dois_with_same_title(self):
        results = build_results([response([record(doi='10.1234/first'), record(doi='10.1234/second')])], ['network'])
        self.assertEqual(results['returned_count'], 2)
        self.assertIsNone(normalize_doi('not a doi'))

    def test_no_doi_title_matches_remain_separate(self):
        results = build_results([response([record(doi=None), record(doi=None)])], ['network'])
        self.assertEqual(results['returned_count'], 2)
        self.assertEqual(results['results'][0]['verification_status'], 'no_doi')

    def test_conflicting_source_title_flags_verification(self):
        items = [record(), record(title='Unrelated title')]
        check = {'status': 'ok', 'item': record(), 'retrieved_at': 'now'}
        result = build_results([response(items)], ['network'], {'10.1234/xyz': check})['results'][0]
        self.assertEqual(result['verification_status'], 'conflict')
        self.assertTrue(result['metadata_conflicts'])

    def test_conflicting_authors_are_not_silently_discarded(self):
        result = build_results([response([record(), record(authors=['B Researcher'])])], ['network'])['results'][0]
        self.assertTrue(any(x.startswith('authors:') for x in result['metadata_conflicts']))
        self.assertEqual(result['source_records'][1]['authors'], ['B Researcher'])

    def test_safe_output_no_overwrite_and_artifact_hash(self):
        result = build_results([response([record()])], ['network'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'run').mkdir()
            refs = write_outputs(root, 'run', result)
            self.assertEqual(len(refs), 2)
            self.assertEqual(json.loads((root / 'run/search_results.json').read_text())['returned_count'], 1)
            self.assertIn('scientific quality', (root / 'run/search_report.md').read_text())
            with self.assertRaises(FileExistsError):
                write_outputs(root, 'run', result)
            with self.assertRaises(ValueError):
                write_outputs(root, '../outside', result)

    def test_schema_matches_produced_record(self):
        schema_path = Path(__file__).resolve().parents[1] / 'schemas/SearchResult.schema.json'
        schema = json.loads(schema_path.read_text())
        item = build_results([response([record()])], ['network'])['results'][0]
        self.assertEqual(set(item), set(schema['required']))
        self.assertEqual(item['schema_version'], schema['properties']['schema_version']['const'])


if __name__ == '__main__':
    unittest.main()
