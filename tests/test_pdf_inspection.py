import json
import tempfile
import unittest
from pathlib import Path

from ai4science.pdf_inspection import PDFInspectionError, PDFLimits, extract_chunks, extract_section_chunks, inspect_pdf

try:
    import pypdf  # noqa: F401
    from reportlab.pdfgen import canvas
    HAS_PDF_TOOLS = True
except ImportError:
    HAS_PDF_TOOLS = False


@unittest.skipUnless(HAS_PDF_TOOLS, 'optional pypdf and reportlab required for PDF fixtures')
class PDFInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        pdf = canvas.Canvas(str(self.root / 'paper.pdf'))
        pdf.setTitle('A Study of Methods')
        pdf.setAuthor('A. Researcher')
        pdf.drawString(72, 750, 'Introduction')
        pdf.drawString(72, 725, 'The protocol achieved 90 percent accuracy. Table 1.')
        pdf.showPage()
        pdf.drawString(72, 750, 'Methods')
        pdf.drawString(72, 725, 'We evaluated three baselines.')
        pdf.showPage()
        pdf.save()

    def tearDown(self):
        self.tmp.cleanup()

    def test_physical_pages_heuristic_sections_and_chunks(self):
        result = inspect_pdf(self.root, 'paper.pdf')
        self.assertEqual(result['page_count'], 2)
        self.assertEqual(result['metadata_candidates']['title'], {
            'value': 'A Study of Methods', 'status': 'source_reported_unverified', 'truncated': False})
        self.assertEqual(result['metadata_candidates']['author']['value'], 'A. Researcher')
        self.assertIn('90 percent accuracy', result['pages'][0]['text'])
        self.assertEqual(result['sections'][0]['pdf_page'], 1)
        self.assertEqual(result['sections'][0]['status'], 'heuristic_unverified')
        self.assertEqual(result['label_mentions'][0]['label'], 'Table 1')
        selected = extract_chunks(result, page_numbers=(2,), chunk_chars=20)
        self.assertTrue(selected)
        self.assertTrue(all(chunk['pdf_page'] == 2 for chunk in selected))
        self.assertEqual(''.join(x['text'] for x in selected), result['pages'][1]['text'])
        self.assertEqual(selected[1]['text_offset'], 20)
        section = extract_section_chunks(result, 'Introduction', chunk_chars=20)
        self.assertTrue(section)
        self.assertTrue(all(x['pdf_page'] == 1 for x in section))
        self.assertIn('accuracy', ''.join(x['text'] for x in section))
        with self.assertRaises(ValueError):
            extract_section_chunks(result, 'not a heading')

    def test_cache_reused_and_invalidated_by_file_hash(self):
        first = inspect_pdf(self.root, 'paper.pdf', cache_dir='cache')
        second = inspect_pdf(self.root, 'paper.pdf', cache_dir='cache')
        self.assertFalse(first['cache_hit'])
        self.assertTrue(second['cache_hit'])
        # A valid PDF may have trailing bytes and must still get a distinct key.
        with (self.root / 'paper.pdf').open('ab') as stream:
            stream.write(b'\n% revision')
        third = inspect_pdf(self.root, 'paper.pdf', cache_dir='cache')
        self.assertFalse(third['cache_hit'])
        self.assertNotEqual(first['document_hash'], third['document_hash'])

    def test_corrupt_cache_is_ignored_and_pdf_reparsed(self):
        first = inspect_pdf(self.root, 'paper.pdf', cache_dir='cache')
        cache_path = next((self.root / 'cache').glob('*.json'))
        original = json.loads(cache_path.read_text())
        for field, bad_value in (('sections', [{'pdf_page': 999}]),
                                 ('label_mentions', [{'label': 'Table 1', 'pdf_page': 999}]),
                                 ('warnings', [123]),
                                 ('metadata_candidates', {'title': 'invalid'})):
            broken = dict(original)
            broken[field] = bad_value
            cache_path.write_text(json.dumps(broken))
            fresh = inspect_pdf(self.root, 'paper.pdf', cache_dir='cache')
            self.assertFalse(fresh['cache_hit'], field)
            self.assertEqual(fresh['document_hash'], first['document_hash'])
            self.assertIn('90 percent accuracy', fresh['pages'][0]['text'])

    def test_limits_and_untrusted_paths(self):
        with self.assertRaises(PDFInspectionError):
            inspect_pdf(self.root, 'missing.pdf')
        with self.assertRaises(PDFInspectionError):
            inspect_pdf(self.root, '../paper.pdf')
        with self.assertRaises(PDFInspectionError):
            inspect_pdf(self.root, 'paper.pdf', cache_dir='../outside')
        with self.assertRaisesRegex(PDFInspectionError, 'max_pages'):
            inspect_pdf(self.root, 'paper.pdf', limits=PDFLimits(max_pages=1))
        with self.assertRaisesRegex(PDFInspectionError, 'max_text_chars'):
            inspect_pdf(self.root, 'paper.pdf', limits=PDFLimits(max_text_chars=10))
        (self.root / 'bad.pdf').write_text('not a PDF')
        with self.assertRaisesRegex(PDFInspectionError, 'not a PDF'):
            inspect_pdf(self.root, 'bad.pdf')

    def test_metadata_is_bounded_and_not_inferred_from_filename(self):
        pdf = canvas.Canvas(str(self.root / 'invented-title.pdf'))
        pdf.setTitle('X' * 1200)
        pdf.setAuthor('')
        pdf.drawString(72, 750, 'Some text')
        pdf.showPage()
        pdf.save()
        result = inspect_pdf(self.root, 'invented-title.pdf')
        self.assertEqual(len(result['metadata_candidates']['title']['value']), 1000)
        self.assertTrue(result['metadata_candidates']['title']['truncated'])
        self.assertIsNone(result['metadata_candidates']['author'])
        self.assertNotIn('invented-title', result['metadata_candidates']['title']['value'])

    def test_blank_page_is_not_reported_as_read(self):
        pdf = canvas.Canvas(str(self.root / 'blank.pdf'))
        pdf.showPage()
        pdf.save()
        result = inspect_pdf(self.root, 'blank.pdf')
        self.assertEqual(result['pages'][0]['text_status'], 'empty_or_unextractable')
        self.assertTrue(any('unreadable' in x for x in result['warnings']))


if __name__ == '__main__':
    unittest.main()
