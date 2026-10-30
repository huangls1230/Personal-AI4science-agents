"""Adversarial checks for deterministic language-edit artifact validation."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from ai4science.paper_language_validation import find_anchor_candidates, render_language_diff, validate_language_run


def digest(text):
    return sha256(text.encode('utf-8')).hexdigest()


class LanguageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = ('# Study\n\nThe model are useful and may suggest a trend [@Smith2020].\n\n'
                       'The Horizon Mapper achieved 3 ms and $x=2$.\n\n'
                       '| Item | Value |\n| --- | --- |\n| count | 3 |\n\n'
                       '```python\nx = 2\n```\n')
        self.glossary = {'terms': [{'canonical_term': 'Horizon Mapper', 'abbreviation': None,
                                    'allowed_variants': [], 'approval_status': 'approved'},
                                   {'canonical_term': 'model', 'abbreviation': None,
                                    'allowed_variants': [], 'approval_status': 'proposed'}]}
        self.glossary_text = 'terms: test\n'
        (self.root / 'source.md').write_text(self.source)
        (self.root / 'glossary.yaml').write_text(self.glossary_text)
        old = 'The model are useful'
        self.change = {'change_id': 'C1', 'source_location': {'start_line': 3, 'end_line': 3, 'original_sha256': digest(old)},
                       'original_text': old, 'revised_text': 'The model is useful',
                       'issue_type': 'grammar', 'reason': 'Agreement', 'semantic_risk': 'low',
                       'approval_required': False, 'status': 'proposed', 'applied_to_draft': True}
        self.data = {'schema_version': '0.1', 'task_id': 'T1', 'execution_mode': 'inline',
                     'project_id': 'P1', 'editing_mode': 'conservative', 'language_variant': 'preserve',
                     'editing_scope': 'entire manuscript', 'manuscript': {'path': 'source.md', 'sha256': digest(self.source)},
                     'terminology_glossary': {'path': 'glossary.yaml', 'sha256': digest(self.glossary_text)},
                     'changes': [self.change]}
        self.edited = self.source.replace(old, self.change['revised_text'])

    def check(self, *, scope=None):
        (self.root / 'changes.json').write_text(json.dumps(self.data))
        (self.root / 'edited.md').write_text(self.edited)
        return validate_language_run(self.root, 'source.md', 'changes.json', 'edited.md', self.glossary, scope)

    def test_good_and_scope(self):
        self.assertEqual([], self.check(scope=[(3, 3)]))
        self.assertTrue(any('scope' in x for x in self.check(scope=[(5, 5)])))
        self.assertTrue(any('allowed_line_ranges' in x for x in self.check(scope=[(0, 30)])))

    def test_bad_anchor_hash_and_id(self):
        self.change['source_location']['original_sha256'] = digest('incorrect')
        self.assertTrue(any('original_sha256' in x for x in self.check()))
        self.change['source_location']['start_line'] = 5
        self.change['source_location']['end_line'] = 5
        self.assertTrue(any('match uniquely' in x for x in self.check()))
        self.data['manuscript']['sha256'] = '0' * 64
        self.assertTrue(any('manuscript path and sha256' in x for x in self.check()))

    def test_unrecorded_edits_and_overlapping_changes(self):
        self.edited += 'Unrecorded sentence.\n'
        self.assertTrue(any('exactly match' in x for x in self.check()))
        self.data['changes'].append(dict(self.change, change_id='C2'))
        self.assertTrue(any('overlap' in x for x in self.check()))

    def test_high_risk_and_deferred_cannot_be_applied(self):
        self.change['semantic_risk'] = 'high'
        self.assertTrue(any('high-risk' in x for x in self.check()))
        self.change.update(approval_required=True, applied_to_draft=False, status='deferred')
        self.edited = self.source
        self.assertEqual([], self.check())
        self.change['applied_to_draft'] = True
        self.assertTrue(any('deferred' in x for x in self.check()))

    def test_protected_markers(self):
        cases = [('$x=2$', '$x=3$', 'formulas'), ('3 ms', '4 ms', 'numbers'), ('3 ms', '3 s', 'number_units'),
                 ('[@Smith2020]', '[@Other]', 'citations'), ('Horizon Mapper', 'Forecast Model', 'approved glossary'),
                 ('may suggest', 'prove', 'qualifiers'), ('# Study', '# Work', 'headings'),
                 ('x = 2\n```', 'x = 3\n```', 'fenced blocks'), ('| count | 3 |', '| count | 4 |', 'tables')]
        for index, (old, new, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                pos = self.source.index(old)
                start = self.source[:pos].count('\n') + 1
                end = start + old.count('\n')
                change = {'change_id': f'X{index}', 'source_location': {'start_line': start, 'end_line': end, 'original_sha256': digest(old)},
                          'original_text': old, 'revised_text': new, 'issue_type': 'test', 'reason': 'test',
                          'semantic_risk': 'low', 'approval_required': False, 'status': 'proposed', 'applied_to_draft': True}
                self.data['changes'] = [change]
                self.edited = self.source.replace(old, new, 1)
                self.assertTrue(any(expected in x for x in self.check()), self.check())

    def test_paths_and_hardlink(self):
        self.assertTrue(validate_language_run(self.root, '../outside.md', 'changes.json', 'edited.md'))
        (self.root / 'changes.json').write_text(json.dumps(self.data))
        (self.root / 'edited.md').hardlink_to(self.root / 'source.md')
        self.assertTrue(any('distinct' in x for x in validate_language_run(self.root, 'source.md', 'changes.json', 'edited.md')))
        outside = self.root.parent / f'{self.root.name}-outside'
        outside.write_text('outside')
        self.addCleanup(outside.unlink)
        (self.root / 'escape').symlink_to(outside)
        self.assertTrue(validate_language_run(self.root, 'escape', 'changes.json', 'edited.md'))

    def test_glossary_mismatch(self):
        self.data['terminology_glossary']['sha256'] = '0' * 64
        self.assertTrue(any('terminology_glossary.sha256' in x for x in self.check()))

    def test_diff_is_read_only_and_refuses_same_or_external_file(self):
        (self.root / 'edited.md').write_text(self.edited)
        diff = render_language_diff(self.root, 'source.md', 'edited.md')
        self.assertIn('-The model are useful', diff)
        self.assertIn('+The model is useful', diff)
        self.assertEqual(self.source, (self.root / 'source.md').read_text())
        with self.assertRaises(ValueError):
            render_language_diff(self.root, 'source.md', 'source.md')
        with self.assertRaises(ValueError):
            render_language_diff(self.root, '../outside.md', 'edited.md')

    def test_anchor_relocation_reports_unique_and_ambiguous_matches(self):
        anchor = 'The model are useful'
        revised = '# New context\n\n' + self.source
        (self.root / 'new.md').write_text(revised)
        self.assertEqual([(5, 5)], find_anchor_candidates(self.root, 'new.md', anchor, digest(anchor)))
        (self.root / 'new.md').write_text(revised + anchor + '\n')
        self.assertEqual(2, len(find_anchor_candidates(self.root, 'new.md', anchor, digest(anchor))))
        self.assertEqual([], find_anchor_candidates(self.root, 'new.md', 'not present', digest('not present')))
        with self.assertRaises(ValueError):
            find_anchor_candidates(self.root, 'new.md', anchor, digest('wrong'))


if __name__ == '__main__':
    unittest.main()
