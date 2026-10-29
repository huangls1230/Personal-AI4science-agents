"""Acceptance coverage for the workspace-only Markdown reading workflow.

PDF cases use the project's optional pypdf plus reportlab fixture generator.
Frontmatter is parsed by the system Ruby/Psych parser when available.
"""
import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai4science.reading_cli import main

PROJECT = Path(__file__).resolve().parents[1]
try:
    import pypdf  # noqa: F401
    from reportlab.pdfgen import canvas
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


@unittest.skipUnless(PDF_AVAILABLE, 'optional pypdf and reportlab are required for PDF acceptance')
@unittest.skipUnless(shutil.which('ruby'), 'Ruby Psych is required to parse YAML frontmatter')
class MarkdownNotesAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=PROJECT / 'workspace')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = ['--workspace', str(self.root)]
        pdf = canvas.Canvas(str(self.root / 'paper.pdf'))
        pdf.setTitle('Synthetic test paper')
        pdf.drawString(72, 750, 'Methods')
        pdf.drawString(72, 725, 'The protocol evaluated three baselines.')
        pdf.save()
        analysis = {
            'paper_id': 'fixture-doi-10.1234/test',
            'metadata': {'title': 'A title: with quotes "safe"', 'authors': ['A Researcher', 'B Author'],
                         'doi': '10.1234/test', 'year': 2024, 'zotero_item_key': 'ABCD1234',
                         'citekey': 'Researcher2024'},
            'sections': {'Paper Overview': '本文研究测试方法。', 'Research Question': '方法是否有效？',
                         'Methodology': '比较三个基线。', 'Mentor Questions': '为何选择这些基线？'},
            'claim_evidence': [{'claim': '作者比较三个基线', 'kind': 'evidence',
                                'excerpt': 'The protocol evaluated three baselines.', 'pdf_page': 1,
                                'printed_page': None, 'section': 'Methods', 'figure': None, 'table': None,
                                'equation': None, 'location_status': 'verified', 'evidence_strength': None,
                                'assumptions': None, 'alternative_explanation': None, 'assessment': None}],
            'limitations': ['此测试不验证科研结论。'],
        }
        (self.root / 'analysis.json').write_text(json.dumps(analysis, ensure_ascii=False), encoding='utf-8')
        self.template = self.root / 'custom-template.md'
        original_template = (PROJECT / 'templates/literature/reading-note.md').read_text(encoding='utf-8')
        self.template.write_text(original_template + '\n## TEST TEMPLATE MARKER\n', encoding='utf-8')
        self.template_arg = str(self.template.relative_to(PROJECT))

    def call(self, args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            status = main(self.base + args)
        return status, output.getvalue(), error.getvalue()

    def finalize(self, *extra):
        return self.call(['finalize', '--pdf', 'paper.pdf', '--analysis', 'analysis.json',
                          '--task-id', 'test-reading', '--template', self.template_arg, *extra])

    def frontmatter(self, text):
        self.assertTrue(text.lstrip().startswith('---\n'))
        yaml_text = text.lstrip().split('---\n', 2)[1]
        ruby = 'require "yaml"; require "json"; puts JSON.generate(YAML.safe_load(STDIN.read))'
        result = subprocess.run(['ruby', '-e', ruby], input=yaml_text, text=True,
                                capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_pdf_template_output_frontmatter_and_no_network(self):
        with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')) as connect, \
                patch('subprocess.Popen', side_effect=AssertionError('external process forbidden')) as spawn:
            status, out, err = self.call(['inspect', '--pdf', 'paper.pdf'])
            self.assertEqual(status, 0, err)
            inspection = json.loads(out)
            self.assertEqual(inspection['page_count'], 1)
            self.assertNotIn('chunks', inspection)  # no complete PDF content in main-agent summary
            status, out, err = self.finalize('--output-dir', 'authorized-output')
            self.assertEqual(status, 0, err)
            connect.assert_not_called()
            spawn.assert_not_called()
        result = json.loads(out)
        self.assertEqual(result['status'], 'completed')
        card = next(x for x in result['output_artifacts'] if x['path'].endswith('.md'))
        path = self.root / card['path']
        self.assertEqual(path.parent, self.root / 'authorized-output')
        contents = path.read_text(encoding='utf-8')
        parsed = self.frontmatter(contents)
        self.assertEqual(parsed['title'], 'A title: with quotes "safe"')
        self.assertEqual(parsed['authors'], ['A Researcher', 'B Author'])
        self.assertEqual(parsed['doi'], '10.1234/test')
        self.assertEqual(parsed['zotero_item_key'], 'ABCD1234')
        self.assertEqual(parsed['citekey'], 'Researcher2024')
        self.assertIn('TEST TEMPLATE MARKER', contents)
        self.assertIn('The protocol evaluated three baselines.', contents)
        self.assertEqual(card['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertIn('方法', contents)

    def test_default_project_path_and_repeated_execution_preserves_user_changes(self):
        status, out, err = self.finalize('--project-id', 'project-demo')
        self.assertEqual(status, 0, err)
        first = next(x for x in json.loads(out)['output_artifacts'] if x['path'].endswith('.md'))
        path = self.root / first['path']
        self.assertEqual(path.parent, self.root / 'projects/project-demo/reading-notes')
        self.assertNotIn('/', path.name)
        path.write_text(path.read_text(encoding='utf-8') + '\n个人批注不可覆盖\n', encoding='utf-8')
        user_content = path.read_bytes()
        status, out, err = self.finalize('--project-id', 'project-demo')
        self.assertEqual(status, 0, err)
        second = next(x for x in json.loads(out)['output_artifacts'] if x['path'].endswith('.md'))
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(path.read_bytes(), user_content)
        self.assertTrue((self.root / second['path']).is_file())

    def test_default_template_and_default_project_without_citation_key(self):
        analysis_path = self.root / 'analysis.json'
        analysis = json.loads(analysis_path.read_text(encoding='utf-8'))
        analysis['metadata'].pop('citekey')
        analysis_path.write_text(json.dumps(analysis, ensure_ascii=False), encoding='utf-8')
        status, out, err = self.call(['finalize', '--pdf', 'paper.pdf', '--analysis', 'analysis.json',
                                      '--task-id', 'test-default'])
        self.assertEqual(status, 0, err)
        card = next(x for x in json.loads(out)['output_artifacts'] if x['path'].endswith('.md'))
        path = self.root / card['path']
        self.assertEqual(path.parent, self.root / 'projects/default/reading-notes')
        text = path.read_text(encoding='utf-8')
        self.assertIn('## 4. 核心方法与技术', text)
        self.assertIn(self.frontmatter(text).get('citekey'), ('', None))

    def test_title_placeholder_and_multiline_table_keep_markdown_structure(self):
        analysis_path = self.root / 'analysis.json'
        analysis = json.loads(analysis_path.read_text(encoding='utf-8'))
        analysis['metadata']['title'] = 'A study\nwith normalized title'
        table = '| Claim | Evidence |\n| --- | --- |\n| Three baselines | PDF page 1 |'
        analysis['sections']['Claim–Evidence Table'] = table
        analysis_path.write_text(json.dumps(analysis, ensure_ascii=False), encoding='utf-8')
        status, out, err = self.finalize('--output-dir', 'notes')
        self.assertEqual(status, 0, err)
        path = self.root / next(a['path'] for a in json.loads(out)['output_artifacts']
                                if a['path'].endswith('.md'))
        text = path.read_text(encoding='utf-8')
        self.assertIn('\n# A study with normalized title\n', text)
        self.assertIn('**论点与证据：**\n\n' + table, text)
        self.assertEqual(self.frontmatter(text)['title'], 'A study\nwith normalized title')

        self.template.write_text(self.template.read_text(encoding='utf-8').replace(
            '# 论文标题', '# 个人定制阅读笔记'), encoding='utf-8')
        status, out, err = self.finalize('--output-dir', 'notes')
        self.assertEqual(status, 0, err)
        path = self.root / next(a['path'] for a in json.loads(out)['output_artifacts']
                                if a['path'].endswith('.md'))
        text = path.read_text(encoding='utf-8')
        self.assertIn('\n# 个人定制阅读笔记\n', text)
        self.assertNotIn('\n# A study with normalized title\n', text)
        self.assertIn('**论点与证据：**\n\n' + table, text)

    def test_template_and_output_escape_are_rejected(self):
        status, _, _ = self.finalize('--output-dir', '../outside')
        self.assertEqual(status, 2)
        status, _, _ = self.call(['finalize', '--pdf', 'paper.pdf', '--analysis', 'analysis.json',
                                  '--task-id', 'test', '--template', '../not-allowed.md'])
        self.assertEqual(status, 2)


if __name__ == '__main__':
    unittest.main()
