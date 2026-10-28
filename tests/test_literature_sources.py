import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from ai4science.literature_sources import search_source, verify_crossref_doi


class SourcesTests(unittest.TestCase):
    def test_crossref_search_paging_and_missing_abstract(self):
        data = {"message": {"total-results": 5, "items": [{"title": ["A topology paper"], "DOI": "10.1234/foo", "URL": "https://doi.org/10.1234/foo", "type": "journal-article", "published": {"date-parts": [[2024]]}}]}}
        with patch("ai4science.literature_sources._fetch", return_value=json.dumps(data).encode()) as fetch:
            result = search_source("crossref", "network topology", limit=1, page=2)
        self.assertIn("offset=1", fetch.call_args.args[0])
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["has_more"])
        self.assertIsNone(result["items"][0]["abstract"])
        self.assertEqual(result["items"][0]["year"], 2024)
        self.assertEqual(result["items"][0]["publication_type"], "journal_article")

    def test_invalid_server_shape_returns_error(self):
        with patch("ai4science.literature_sources._fetch", return_value=b'{"message":{"items":[null]}}'):
            result = search_source("crossref", "topic")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["items"], [])

    def test_metadata_lookup_and_cache(self):
        payload = {"message": {"title": ["Verified title"], "DOI": "10.1234/test", "URL": "https://doi.org/10.1234/test"}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "workspace") as directory, patch("ai4science.literature_sources._fetch", return_value=json.dumps(payload).encode()) as fetch:
            first = verify_crossref_doi("https://doi.org/10.1234/test", cache_dir=Path(directory))
            second = verify_crossref_doi("10.1234/test", cache_dir=Path(directory))
            self.assertEqual(first["item"]["title"], "Verified title")
            self.assertTrue(second["cached"])
            self.assertEqual(fetch.call_count, 1)
        with self.assertRaises(ValueError):
            verify_crossref_doi("10.1234/test?evil=1")

    def test_failure_differs_from_empty(self):
        with patch("ai4science.literature_sources._fetch", side_effect=URLError("offline")):
            failed = search_source("crossref", "topology")
        with patch("ai4science.literature_sources._fetch", return_value=b'{"message":{"items":[],"total-results":0}}'):
            empty = search_source("crossref", "topology")
        self.assertEqual(failed["status"], "error")
        self.assertEqual(empty["status"], "ok")
        self.assertEqual(empty["items"], [])

    def test_search_cache_and_no_key_leak(self):
        payload = {"results": [{"id": "https://openalex.org/W1", "display_name": "Test", "abstract_inverted_index": {"networks": [1], "Agent": [0]}, "type": "preprint"}], "meta": {"count": 1}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "workspace") as directory, patch("ai4science.literature_sources._fetch", return_value=json.dumps(payload).encode()) as fetch:
            first = search_source("openalex", "agent", api_key="secret-key", cache_dir=Path(directory))
            second = search_source("openalex", "agent", api_key="secret-key", cache_dir=Path(directory))
            self.assertEqual(first["items"][0]["abstract"], "Agent networks")
            self.assertTrue(second["cached"])
            self.assertEqual(fetch.call_count, 1)
            self.assertNotIn("secret-key", next(Path(directory).iterdir()).read_text())

    def test_missing_key_and_http_error_redacted(self):
        result = search_source("openalex", "topic")
        self.assertEqual(result["status"], "error")
        secret_url = "https://api.openalex.org/works?api_key=secret"
        with patch("ai4science.literature_sources._fetch", side_effect=HTTPError(secret_url, 403, "forbidden", {}, None)):
            result = search_source("openalex", "topic", api_key="secret")
        self.assertEqual(result["error"], "HTTP 403")
        self.assertNotIn("secret", json.dumps(result))

    def test_arxiv_and_semantic_scholar_pages(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A preprint</title><id>https://arxiv.org/abs/1234.5678</id><published>2025-01-01T00:00:00Z</published><summary>Text</summary><author><name>A Author</name></author><link title="pdf" href="https://arxiv.org/pdf/1234.5678"/></entry></feed>'''
        with patch("ai4science.literature_sources._fetch", return_value=xml) as fetch:
            result = search_source("arxiv", "all:network", page=2, limit=1)
            self.assertIn("start=1", fetch.call_args.args[0])
            self.assertEqual(result["items"][0]["publication_type"], "preprint")
        semantic = {"data": [{"title": "Networks", "authors": [{"name": "A"}], "externalIds": {"DOI": "10.1234/x"}, "publicationTypes": ["Conference"]}], "next": 2}
        with patch("ai4science.literature_sources._fetch", return_value=json.dumps(semantic).encode()) as fetch:
            result = search_source("semantic_scholar", "network", page=2, limit=1)
            self.assertIn("offset=1", fetch.call_args.args[0])
            self.assertEqual(result["items"][0]["publication_type"], "conference_paper")

    def test_arxiv_total_prevents_false_next_page(self):
        xml = b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:os="http://a9.com/-/spec/opensearch/1.1/"><os:totalResults>1</os:totalResults><entry><title>X</title></entry></feed>'
        with patch("ai4science.literature_sources._fetch", return_value=xml), patch("ai4science.literature_sources._wait_arxiv"):
            result = search_source("arxiv", "all:network", limit=1)
        self.assertFalse(result["has_more"])

    def test_arxiv_rate_limit_and_cache_hit(self):
        import ai4science.literature_sources as sources
        xml = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "workspace") as directory, \
             patch.object(sources, "_ARXIV_LAST", None), \
             patch.object(sources.time, "monotonic", side_effect=[100.0, 100.0, 101.0, 103.0]), \
             patch.object(sources.time, "sleep") as sleep, \
             patch.object(sources, "_fetch", return_value=xml) as fetch:
            sources.search_source("arxiv", "all:one", cache_dir=Path(directory))
            sources.search_source("arxiv", "all:one", cache_dir=Path(directory))
            sources.search_source("arxiv", "all:two", cache_dir=Path(directory))
        sleep.assert_called_once_with(2.0)
        self.assertEqual(fetch.call_count, 2)

    def test_arxiv_non_atom_success_response_is_an_error(self):
        html = b'<html><body>Service temporarily unavailable</body></html>'
        with patch("ai4science.literature_sources._fetch", return_value=html), patch("ai4science.literature_sources._wait_arxiv"):
            result = search_source("arxiv", "all:network")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["items"], [])

    def test_arxiv_error_feed_is_not_a_paper(self):
        data = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#bad_query</id><title>Error</title><summary>Invalid search</summary></entry></feed>'
        with patch("ai4science.literature_sources._fetch", return_value=data):
            result = search_source("arxiv", "invalid")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["items"], [])

    def test_cache_outside_workspace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                search_source("crossref", "topic", cache_dir=Path(directory))

    def test_invalid_parameters_and_untrusted_urls(self):
        for kwargs in ({"limit": 51}, {"page": 0}, {"timeout": 31}, {"timeout": float("nan")}):
            with self.assertRaises(ValueError):
                search_source("crossref", "topic", **kwargs)
        payload = {"message": {"items": [{"title": ["X"], "URL": "javascript:alert(1)"}]}}
        with patch("ai4science.literature_sources._fetch", return_value=json.dumps(payload).encode()):
            self.assertIsNone(search_source("crossref", "topic")["items"][0]["source_url"])


if __name__ == "__main__":
    unittest.main()
