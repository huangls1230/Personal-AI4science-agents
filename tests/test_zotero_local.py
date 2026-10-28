import json
import unittest
from urllib.parse import parse_qs, urlsplit

from ai4science.zotero_local import BetterBibTeXAdapter, ZoteroError, ZoteroLocalClient


class FakeTransport:
    def __init__(self):
        self.calls = []
    def __call__(self, path, method='GET', payload=None, timeout=5):
        self.calls.append((path, method, payload, timeout))
        if path == '/api/':
            return 200, {'Zotero-API-Version': '3', 'Zotero-Server-ID': 'instance'}, b'{}'
        if path == '/better-bibtex/json-rpc':
            req = json.loads(payload)
            response = {'api.ready': {'betterbibtex': '7', 'zotero': '10'},
                        'item.citationkey': {'1:ABCDEFGH': 'anExistingKey'},
                        'item.export': '@article{anExistingKey, title={Title}}'}[req['method']]
            return 200, {}, json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': response}).encode()
        if 'itemKey=' in path and 'format=' not in path:
            keys = parse_qs(urlsplit(path).query)['itemKey'][0].split(',')
            return 200, {}, json.dumps([{'key': key} for key in keys]).encode()
        if '/children?' in path:
            return 200, {}, json.dumps([{'data': {'itemType': 'attachment'}}, {'data': {'itemType': 'note'}}]).encode()
        if 'format=bibtex' in path:
            return 200, {}, b'@article{one, title={Test}}'
        if 'format=csljson' in path:
            return 200, {}, b'[{"title":"Test"}]'
        if 'format=bib' in path:
            return 200, {}, b'<div>Formatted bibliography</div>'
        return 200, {}, b'[]'


class ZoteroClientTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.client = ZoteroLocalClient(transport=self.transport)

    def test_doctor_and_pagination(self):
        state = self.client.doctor()
        self.assertTrue(state['api_enabled'])
        self.assertTrue(state['library_accessible'])
        self.assertEqual(state['api_version'], '3')
        self.assertEqual(state['write_authorization'], 'not_checked')
        self.assertEqual(parse_qs(urlsplit(self.transport.calls[-1][0]).query), {'limit': ['1'], 'start': ['0']})
        self.client.list_items(0, limit=8, start=16)
        self.assertIn('limit=8&start=16', self.transport.calls[-1][0])
        self.client.search_items(0, 'quantum & biology', limit=5)
        self.assertEqual(parse_qs(urlsplit(self.transport.calls[-1][0]).query)['q'], ['quantum & biology'])
        self.assertEqual(parse_qs(urlsplit(self.transport.calls[-1][0]).query)['qmode'], ['titleCreatorYear'])
        self.client.search_items(0, '10.1000/example', qmode='everything')
        self.assertEqual(parse_qs(urlsplit(self.transport.calls[-1][0]).query)['qmode'], ['everything'])
        with self.assertRaises(ValueError):
            self.client.search_items(0, 'test', qmode='unsupported')
        self.client.list_collections(0, limit=4)
        self.client.get_tags(0, limit=3)
        self.assertEqual(len(self.client.get_attachments(0, 'ABCDEFGH')), 1)

    def test_invalid_inputs_rejected_before_transport(self):
        for args in [(0, '../etc/passwd'), (-1, 'ABCDEFGH'), (0, 'bad')]:
            with self.assertRaises(ValueError):
                self.client.get_item(*args)
        for kw in ({'limit': 0}, {'limit': 101}, {'start': -1}):
            with self.assertRaises(ValueError):
                self.client.list_items(**kw)
        with self.assertRaises(ValueError):
            self.client.export(0, ['ABCDEFGH'], 'bib', style='http://evil/')
        with self.assertRaises(ValueError):
            self.client.export(0, ['ABCDEFGH', 'ABCDEFGH'], 'bibtex')
        self.assertEqual(self.transport.calls, [])

    def test_exports_use_server_formats(self):
        self.assertTrue(self.client.export(0, ['ABCDEFGH'], 'bibtex').startswith(b'@article'))
        self.assertEqual(json.loads(self.client.export(0, ['ABCDEFGH'], 'csljson'))[0]['title'], 'Test')
        self.assertIn(b'Formatted bibliography', self.client.export(0, ['ABCDEFGH'], 'bib', style='apa'))
        self.assertEqual(parse_qs(urlsplit(self.transport.calls[-1][0]).query)['style'], ['apa'])

    def test_export_rejects_missing_item_in_preflight(self):
        def missing(path, **kwargs):
            return 200, {}, b'[]'
        with self.assertRaises(ZoteroError) as ctx:
            ZoteroLocalClient(transport=missing).export(0, ['ABCDEFGH'], 'bibtex')
        self.assertEqual(ctx.exception.code, 'incomplete_export')

    def test_bibtex_and_biblatex_require_complete_entry_count(self):
        def incomplete(path, **kwargs):
            if 'format=' not in path:
                return 200, {}, b'[{"key":"ABCDEFGH"},{"key":"BCDEFGHJ"}]'
            return 200, {}, b'@article{one, title={{Nested} paper}}'
        client = ZoteroLocalClient(transport=incomplete)
        for fmt in ('bibtex', 'biblatex'):
            with self.subTest(fmt=fmt), self.assertRaises(ZoteroError) as ctx:
                client.export(0, ['ABCDEFGH', 'BCDEFGHJ'], fmt)
            self.assertEqual(ctx.exception.code, 'incomplete_export')

    def test_bibtex_nested_fields_and_unterminated_entries(self):
        def entries(path, **kwargs):
            if 'format=' not in path:
                return 200, {}, b'[{"key":"ABCDEFGH"},{"key":"BCDEFGHJ"}]'
            return 200, {}, b'@article{one, title={{Nested} paper}}\n@book{two, title={A \\{literal\\} quote}}'
        client = ZoteroLocalClient(transport=entries)
        self.assertIn(b'@book', client.export(0, ['ABCDEFGH', 'BCDEFGHJ'], 'bibtex'))
        def broken(path, **kwargs):
            if 'format=' not in path:
                return 200, {}, b'[{"key":"ABCDEFGH"}]'
            return 200, {}, b'@article{one, title={Unclosed}'
        with self.assertRaises(ZoteroError) as ctx:
            ZoteroLocalClient(transport=broken).export(0, ['ABCDEFGH'], 'bibtex')
        self.assertEqual(ctx.exception.code, 'invalid_response')

    def test_not_found_and_disabled_are_distinct(self):
        def missing(*args, **kwargs):
            raise ZoteroError('not_found', 'not found', 404)
        with self.assertRaises(ZoteroError) as ctx:
            ZoteroLocalClient(transport=missing).get_item(0, 'ABCDEFGH')
        self.assertEqual(ctx.exception.code, 'not_found')
        def disabled(*args, **kwargs):
            raise ZoteroError('forbidden', 'forbidden', 403)
        state = ZoteroLocalClient(transport=disabled).doctor()
        self.assertFalse(state['api_enabled'])
        self.assertEqual(state['library_accessible'], 'unknown')

    def test_writes_are_never_attempted(self):
        with self.assertRaises(ZoteroError) as ctx:
            self.client.write()
        self.assertEqual(ctx.exception.code, 'blocked')
        self.assertEqual(self.transport.calls, [])

    def test_bbt_allowlisted_rpc_and_unavailable(self):
        bbt = BetterBibTeXAdapter(transport=self.transport)
        self.assertEqual(bbt.ready()['zotero'], '10')
        self.assertEqual(bbt.citation_keys(1, ['ABCDEFGH'])['1:ABCDEFGH'], 'anExistingKey')
        bbt.citation_keys(None, ['ABCDEFGH'])
        self.assertEqual(json.loads(self.transport.calls[-1][2])['params'], [['ABCDEFGH']])
        bbt.export(['anExistingKey'], 'Better BibTeX')
        self.assertEqual(len(json.loads(self.transport.calls[-1][2])['params']), 2)
        with self.assertRaises(ValueError):
            bbt.citation_keys(0, ['ABCDEFGH'])
        with self.assertRaises(ValueError):
            bbt.export(['anExistingKey'], 'Better BibTeX', 0)
        self.assertIn('anExistingKey', bbt.export(['anExistingKey'], 'Better BibTeX', 1))
        with self.assertRaises(ValueError):
            bbt._rpc('item.regenerate_key', [])
        with self.assertRaises(ValueError):
            bbt.export(['key'], 'anything', 1)
        def absent(*args, **kwargs):
            raise ZoteroError('not_found', 'not found', 404)
        with self.assertRaises(ZoteroError):
            BetterBibTeXAdapter(transport=absent).ready()

    def test_bbt_rpc_error_is_sanitized(self):
        def error(*args, **kwargs):
            return 200, {}, b'{"jsonrpc":"2.0","id":1,"error":{"message":"private"}}'
        with self.assertRaises(ZoteroError) as ctx:
            BetterBibTeXAdapter(transport=error).ready()
        self.assertEqual(ctx.exception.code, 'bbt_error')
        self.assertNotIn('private', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
