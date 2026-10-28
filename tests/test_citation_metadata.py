import unittest
from unittest.mock import patch

from ai4science.citation_metadata import (citation_record_from_search, citation_record_from_zotero,
                                         detect_duplicate, validate_metadata, validate_citation_record)


def paper(**updates):
    data = {'doi': '10.1234/XYZ', 'title': 'A Paper', 'authors': ['A Person'],
            'publication_year': 2024, 'venue': 'Journal', 'publication_type': 'journal_article'}
    data.update(updates)
    return data


class CitationMetadataTests(unittest.TestCase):
    def test_zotero_normalization_preserves_unknown_and_no_file_reads(self):
        item = {'key': 'ABCDEFGH', 'data': {'key': 'ABCDEFGH', 'title': 'A Paper',
                'DOI': 'https://doi.org/10.1234/XyZ', 'date': '2024-01-01',
                'creators': [{'creatorType': 'author', 'firstName': 'A', 'lastName': 'Person'}],
                'tags': [{'tag': 'mine'}, {'tag': 'research-reading'}], 'collections': ['AAA']}}
        record = citation_record_from_zotero(item, 1, attachments=[{'key': 'ATTACH01', 'data': {'key': 'ATTACH01', 'path': '/private/data.pdf'}}])
        self.assertEqual(record['doi'], '10.1234/xyz')
        self.assertEqual(record['authors'], ['A Person'])
        self.assertEqual(record['reading_status'], 'research-reading')
        self.assertEqual(record['attachment_references'][0]['item_key'], 'ATTACH01')
        self.assertNotIn('path', record['attachment_references'][0])
        self.assertIsNone(record['citation_key'])
        self.assertIsNone(record['venue'])

    def test_search_record_does_not_claim_membership_or_verification(self):
        record = citation_record_from_search({'title': 'Example', 'year': 2020, 'verification_status': 'doi_title_match'})
        self.assertIsNone(record['zotero_item_key'])
        self.assertEqual(record['metadata_verification_status'], 'unverified')
        self.assertEqual(record['authors'], [])

    def test_duplicate_doi_and_versions(self):
        a, b = paper(), paper(doi='https://doi.org/10.1234/xyz')
        self.assertEqual(detect_duplicate(a, b)['classification'], 'exact_match')
        preprint = paper(doi='10.48550/arXiv.1234.56789', publication_type='preprint')
        self.assertEqual(detect_duplicate(a, preprint)['classification'], 'related_version')
        self.assertEqual(detect_duplicate(paper(doi=None), paper(doi=None))['classification'], 'probable_duplicate')
        self.assertEqual(detect_duplicate(paper(doi=None, authors=[]), paper(doi=None, authors=[]))['classification'], 'uncertain')

    def test_library_identity_requires_kind_and_known_matching_server(self):
        left = paper(doi=None, title=None, authors=[], zotero_library_id=123,
                     zotero_library_kind='users', zotero_item_key='ABCDEFGH', zotero_server_id='s1')
        right = dict(left)
        self.assertEqual(detect_duplicate(left, right)['classification'], 'exact_match')
        right['zotero_library_kind'] = 'groups'
        self.assertEqual(detect_duplicate(left, right)['classification'], 'uncertain')
        right['zotero_library_kind'] = 'users'
        right['zotero_server_id'] = 's2'
        self.assertEqual(detect_duplicate(left, right)['classification'], 'uncertain')
        right['zotero_server_id'] = None
        left['zotero_server_id'] = None
        self.assertEqual(detect_duplicate(left, right)['classification'], 'uncertain')
        left['doi'] = right['doi'] = '10.1234/X'
        self.assertEqual(detect_duplicate(left, right)['classification'], 'exact_match')
        self.assertIn('DOI', detect_duplicate(left, right)['reason'])

    def test_explicit_library_kind_and_server(self):
        record = citation_record_from_zotero({'key': 'ABCDEFGH'}, 123,
                                              library_kind='groups', server_id='local-1')
        self.assertEqual(record['zotero_library_kind'], 'groups')
        self.assertEqual(record['zotero_server_id'], 'local-1')
        with self.assertRaises(ValueError):
            citation_record_from_zotero({'key': 'ABCDEFGH'}, 123, library_kind='other')

    def test_doi_title_only_is_partial_not_fully_verified(self):
        response = {'status': 'ok', 'source': 'crossref', 'retrieved_at': 'now',
                    'item': {'doi': '10.1234/xyz', 'title': 'A Paper'}}
        result = validate_metadata(paper(), lookup=response)
        self.assertEqual(result['status'], 'partially_verified')
        self.assertEqual(result['fields']['authors'], 'unknown')
        self.assertEqual(result['fields']['volume'], 'unknown')
        self.assertIn('not an independent DOI resolver', result['warnings'][0])
        response['item']['title'] = 'Other'
        self.assertEqual(validate_metadata(paper(), lookup=response)['status'], 'conflict')

    def test_record_runtime_validation(self):
        import tempfile
        from pathlib import Path
        record = citation_record_from_search({'title': 'Example'})
        validate_citation_record(record)
        for field, value in [('publication_year', True), ('zotero_library_kind', 'other'),
                             ('authors', [42]), ('metadata_verification_status', 'verified-ish'),
                             ('reading_card_path', '../outside'), ('reading_card_path', '/tmp/outside'),
                             ('reading_card_path', 'C:/private/file')]:
            bad = dict(record, **{field: value})
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_citation_record(bad)
        with self.assertRaises(ValueError):
            validate_citation_record(dict(record, unexpected='x'))
        bad = dict(record)
        del bad['title']
        with self.assertRaises(ValueError):
            validate_citation_record(bad)
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / 'escape').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                validate_citation_record(dict(record, reading_card_path='escape/note.md'), root)
            validate_citation_record(dict(record, reading_card_path='safe/new-note.md'), root)

    def test_missing_doi_never_networks(self):
        with patch('ai4science.citation_metadata.verify_crossref_doi') as mock:
            result = validate_metadata(paper(doi=None), perform_lookup=True)
            self.assertEqual(result['status'], 'unverified')
            mock.assert_not_called()

    def test_lookup_failure_is_unverified(self):
        self.assertEqual(validate_metadata(paper(), lookup={'status': 'error'})['status'], 'unverified')


if __name__ == '__main__':
    unittest.main()
