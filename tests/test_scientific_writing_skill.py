#!/usr/bin/env python3
"""Synthetic integration checks of staged scientific-writing CLI tools."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('SW_TEST_WORKSPACE', str(Path(__file__).resolve().parents[1]))).resolve()
SKILL = ROOT / '.agents/skills/scientific-writing'
SCRIPTS = SKILL / 'scripts'

class SkillIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='sw-tests-', dir=ROOT)
        cls.base = Path(cls.temp.name)
        cls.outside = tempfile.TemporaryDirectory(prefix='sw-outside-', dir='/private/tmp')
        cls.external = Path(cls.outside.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        cls.outside.cleanup()

    def invoke(self, script, *args):
        p = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], cwd=ROOT,
                           text=True, capture_output=True, timeout=15)
        self.assertEqual(p.stderr, '', msg=p.stderr)
        try:
            report = json.loads(p.stdout)
        except json.JSONDecodeError:
            self.fail(f'{script} output was not JSON: {p.stdout!r}')
        return p.returncode, report

    def codes(self, report):
        return {i['code'] for i in report['issues']}

    def fixture(self):
        return {'schema_version':'1.0','sources':[{
            'authors':['Example Author'], 'confidentiality':'unknown', 'evidence_id':'E001',
            'identifiers':{'doi':'','isbn':'','pmcid':'','pmid':'','url':''},
            'locator':'page 1', 'source_type':'other', 'title':'Synthetic source',
            'verification':{'source_opened':False,'status':'unverified','verified_by':'','verified_on':''},
            'year':2020}]}

    def validate(self, data, *extra):
        path = self.base / 'source.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return self.invoke('validate_manifest.py', path, '--kind', 'source', *extra)

    def test_01_unknown_and_template_default(self):
        template = json.loads((SKILL/'assets/source_manifest_template.json').read_text())
        self.assertEqual(template['sources'][0]['confidentiality'], 'unknown')
        status, report = self.validate(self.fixture())
        self.assertEqual(status, 0, report)
        self.assertNotIn('INVALID_CONFIDENTIALITY_CLASS', self.codes(report))

    def test_02_public_needs_explicit_verification(self):
        fixture = self.fixture()
        fixture['sources'][0]['confidentiality'] = 'public'
        status, report = self.validate(fixture)
        self.assertEqual(status, 1)
        self.assertIn('PUBLIC_ACCESS_UNVERIFIED', self.codes(report))
        for invalid in ({'verified':False,'verified_by':'Reviewer','verified_on':'2026-10-29','basis':'Publisher website'},
                        {'verified':True,'verified_by':'','verified_on':'2026-10-29','basis':'Publisher website'},
                        {'verified':True,'verified_by':'Reviewer','verified_on':'not-a-date','basis':'Publisher website'},
                        {'verified':True,'verified_by':'Reviewer','verified_on':'2026-10-29','basis':''}):
            fixture['sources'][0]['public_access_verification'] = invalid
            status, report = self.validate(fixture)
            self.assertEqual(status, 1)
            self.assertIn('PUBLIC_ACCESS_UNVERIFIED', self.codes(report))
        fixture['sources'][0]['public_access_verification'] = {'verified':True, 'verified_by':'Reviewer', 'verified_on':'2026-10-29', 'basis':'Publisher website'}
        status, report = self.validate(fixture)
        self.assertEqual(status, 0, report)

    def test_03_scientific_and_public_verification_are_independent(self):
        fixture = self.fixture()
        fixture['sources'][0]['verification'] = {'source_opened':True,'status':'verified','verified_by':'Reviewer','verified_on':'2026-10-29'}
        status, report = self.validate(fixture, '--require-verified')
        self.assertEqual(status, 0, report)
        fixture['sources'][0]['confidentiality'] = 'public'
        status, report = self.validate(fixture, '--require-verified')
        self.assertEqual(status, 1)
        self.assertIn('PUBLIC_ACCESS_UNVERIFIED', self.codes(report))
        self.assertNotIn('SOURCE_NOT_VERIFIED', self.codes(report))
        fixture['sources'][0]['public_access_verification'] = {'verified':True,'verified_by':'Reviewer','verified_on':'2026-10-29','basis':'Publisher website'}
        fixture['sources'][0]['verification'] = {'source_opened':False,'status':'unverified','verified_by':'','verified_on':''}
        status, report = self.validate(fixture, '--require-verified')
        self.assertEqual(status, 1)
        self.assertIn('SOURCE_NOT_VERIFIED', self.codes(report))
        self.assertNotIn('PUBLIC_ACCESS_UNVERIFIED', self.codes(report))

    def test_04_scaffold_and_lint(self):
        out = self.base/'generated'
        status, report = self.invoke('scaffold_manuscript.py', '--output-dir', out, '--document-id', 'synthetic01', '--study-design', 'observational')
        self.assertEqual(status, 0, report)
        self.assertEqual(json.loads((out/'source_manifest.json').read_text())['sources'][0]['confidentiality'], 'unknown')
        self.assertTrue((out/'manuscript.md').is_file())
        status, report = self.invoke('lint_manuscript.py', out/'manuscript.md', '--manifest', out/'manuscript_manifest.json')
        self.assertEqual(status, 1, report)
        self.assertIn('UNRESOLVED_PLACEHOLDER', self.codes(report))
        self.assertIn('CONFIDENTIALITY_REVIEW_INCOMPLETE', self.codes(report))
        manuscript = self.base/'synthetic.md'
        manuscript.write_text('This treatment proves the result.\n[[TODO:check]]\n', encoding='utf-8')
        status, report = self.invoke('lint_manuscript.py', manuscript)
        self.assertEqual(status, 1, report)
        self.assertTrue({'UNRESOLVED_PLACEHOLDER','POTENTIAL_OVERSTATEMENT','CONFIDENTIALITY_GATE_NOT_CHECKED'} <= self.codes(report), report)
        self.assertNotIn('This treatment', json.dumps(report))
        self.assertEqual(report['summary']['raw_text_echoed'], False)

    def test_05_external_input_and_traversal_rejected(self):
        outside_file = self.external/'secret.md'
        outside_file.write_text('synthetic text', encoding='utf-8')
        for path in (outside_file, ROOT/'..'/self.external.name/'secret.md'):
            status, report = self.invoke('lint_manuscript.py', path)
            self.assertEqual(status, 1, report)
            self.assertIn('INVALID_INPUT', self.codes(report))

    def test_06_symlink_input_and_directory_rejected(self):
        outside_file = self.external/'linked.md'
        outside_file.write_text('synthetic text', encoding='utf-8')
        file_link = self.base/'linked.md'
        file_link.symlink_to(outside_file)
        directory_link = self.base/'external-dir'
        directory_link.symlink_to(self.external, target_is_directory=True)
        for path in (file_link, directory_link/'linked.md'):
            status, report = self.invoke('lint_manuscript.py', path)
            self.assertEqual(status, 1, report)
            self.assertIn('INVALID_INPUT', self.codes(report))

    def test_07_external_and_symlink_output_rejected(self):
        output_link = self.base/'output-link'
        output_link.symlink_to(self.external, target_is_directory=True)
        for path in (self.external/'new-output', output_link/'new-output'):
            status, report = self.invoke('scaffold_manuscript.py', '--output-dir', path, '--document-id', 'synthetic02', '--study-design', 'observational')
            self.assertEqual(status, 1, report)
            self.assertIn('INVALID_INPUT', self.codes(report))
            self.assertFalse((self.external/'new-output').exists())

if __name__ == '__main__':
    unittest.main(verbosity=2)
