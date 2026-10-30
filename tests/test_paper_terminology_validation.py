import copy
import json
import tempfile
import unittest
from pathlib import Path

from ai4science.contracts import create_artifact
from ai4science.paper_terminology_validation import validate_glossary_data, validate_terminology_run


class TerminologyValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input_path = 'manuscript.md'
        self.changes_path = 'changes.json'
        (self.root / self.input_path).write_text('# Introduction\nThe forecast error is unknown.\n', encoding='utf-8')
        self.data = {
            'schema_version': '0.1', 'task_id': 'term-test', 'execution_mode': 'native_subagent',
            'review_scope': 'entire manuscript',
            'manuscript': {'path': self.input_path, 'sha256': create_artifact(self.root, self.input_path).sha256},
            'changes': [{
                'issue_id': 'T01',
                'location': {'section': 'Introduction', 'start_line': 2, 'end_line': 2,
                             'quote': 'The forecast error is unknown.'},
                'original_term': 'forecast error', 'suggested_term': None,
                'reason': 'Ask the author to clarify the term.', 'semantic_risk': 'high',
                'approval_required': True, 'status': 'proposed',
            }],
        }

    def validate(self, data=None, input_path=None, changes_path=None):
        (self.root / self.changes_path).write_text(json.dumps(self.data if data is None else data), encoding='utf-8')
        return validate_terminology_run(self.root, input_path or self.input_path, changes_path or self.changes_path)

    def test_valid_null_suggestion_and_inline(self):
        self.assertEqual([], self.validate())
        data = copy.deepcopy(self.data)
        data['execution_mode'] = 'inline'
        data['changes'][0].update(suggested_term='prediction error', semantic_risk='low', approval_required=False)
        self.assertEqual([], self.validate(data))
        data['changes'] = []
        self.assertEqual([], self.validate(data))

    def test_required_values_and_enums(self):
        for field, value in (('issue_id', ''), ('original_term', None), ('reason', '  '),
                             ('suggested_term', ''), ('semantic_risk', 'unknown'),
                             ('approval_required', 1), ('status', 'done')):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data['changes'][0][field] = value
                self.assertTrue(any(field in error for error in self.validate(data)))
        data = copy.deepcopy(self.data)
        del data['changes'][0]['suggested_term']
        self.assertTrue(any('suggested_term' in error for error in self.validate(data)))
        data['changes'].append(copy.deepcopy(data['changes'][0]))
        self.assertTrue(any('unique' in error for error in self.validate(data)))
        for field in ('task_id', 'execution_mode', 'review_scope'):
            data = copy.deepcopy(self.data)
            del data[field]
            self.assertTrue(any(field in error for error in self.validate(data)))

    def test_high_risk_requires_approval(self):
        data = copy.deepcopy(self.data)
        data['changes'][0]['approval_required'] = False
        self.assertTrue(any('approval' in error for error in self.validate(data)))

    def test_hash_identity_and_unchanged_input(self):
        data = copy.deepcopy(self.data)
        data['manuscript']['sha256'] = '0' * 64
        self.assertTrue(any('sha256' in error for error in self.validate(data)))
        data = copy.deepcopy(self.data)
        data['manuscript']['path'] = 'other.md'
        self.assertTrue(any('manuscript.path' in error for error in self.validate(data)))
        (self.root / self.input_path).write_text('changed\n', encoding='utf-8')
        self.assertTrue(any('sha256' in error for error in self.validate()))

    def test_source_anchors_and_errors_do_not_leak_text(self):
        for update in ({'quote': 'private fabricated text'}, {'start_line': 0}, {'end_line': 3},
                       {'start_line': True}, {'start_line': 2, 'end_line': 1}):
            with self.subTest(update=update):
                data = copy.deepcopy(self.data)
                data['changes'][0]['location'].update(update)
                errors = self.validate(data)
                self.assertTrue(errors)
                self.assertNotIn('private fabricated text', str(errors))
        data = copy.deepcopy(self.data)
        data['changes'][0]['original_term'] = 'secret fabricated term'
        errors = self.validate(data)
        self.assertTrue(any('original_term' in error for error in errors))
        self.assertNotIn('secret fabricated term', str(errors))

    def test_workspace_escape_invalid_json_and_same_file(self):
        self.assertTrue(self.validate(input_path='../secret.md'))
        self.assertTrue(self.validate(changes_path='../secret.json'))
        with tempfile.TemporaryDirectory() as elsewhere:
            (Path(elsewhere) / 'secret.md').write_text('secret', encoding='utf-8')
            (self.root / 'escape').symlink_to(elsewhere, target_is_directory=True)
            self.assertTrue(self.validate(input_path='escape/secret.md'))
        self.assertTrue(self.validate(data=[]))
        self.assertTrue(validate_terminology_run(self.root, self.input_path, self.input_path))
        (self.root / self.changes_path).write_text('{ invalid', encoding='utf-8')
        self.assertTrue(validate_terminology_run(self.root, self.input_path, self.changes_path))


class GlossaryValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = 'manuscript.md'
        (self.root / self.source).write_text('# Intro\nThe forecast error matters.\nThe forecast error changes.\n', encoding='utf-8')
        self.glossary = {
            'schema_version': '0.1',
            'manuscript': {'path': self.source, 'sha256': create_artifact(self.root, self.source).sha256},
            'terms': [{
                'canonical_term': 'forecast error', 'category': 'concept',
                'definition': None, 'abbreviation': None,
                'observed_variants': ['forecast error'], 'allowed_variants': [], 'ambiguous_variants': [],
                'first_occurrence': {'line': 2, 'section': 'Intro'}, 'occurrences': 2,
                'occurrence_locations': [
                    {'line': 2, 'section': 'Intro', 'term': 'forecast error', 'context': 'The forecast error matters.'},
                    {'line': 3, 'section': 'Intro', 'term': 'forecast error', 'context': 'The forecast error changes.'},
                ],
                'rationale': 'Check consistent use.', 'verification_status': 'unverified',
                'approval_status': 'proposed',
            }],
        }

    def validate(self, data=None, input_path=None):
        return validate_glossary_data(self.root, input_path or self.source, self.glossary if data is None else data)

    def test_valid_and_permitted_statuses(self):
        self.assertEqual([], self.validate())
        data = copy.deepcopy(self.glossary)
        data['terms'][0].update(definition='an error', abbreviation='FE', verification_status='unknown', approval_status='rejected')
        self.assertEqual([], self.validate(data))
        data['terms'][0].update(verification_status='verified', approval_status='approved')
        self.assertEqual([], self.validate(data))

    def test_schema_and_content_identity(self):
        for field, value in (('schema_version', '1.0'), ('manuscript', None), ('terms', {})):
            data = copy.deepcopy(self.glossary)
            data[field] = value
            self.assertTrue(any(field in error for error in self.validate(data)))
        data = copy.deepcopy(self.glossary)
        data['manuscript']['sha256'] = '0' * 64
        data['manuscript']['path'] = 'other.md'
        self.assertGreaterEqual(len(self.validate(data)), 2)
        self.assertTrue(self.validate(input_path='../outside.md'))

    def test_required_term_fields_and_statuses(self):
        for field, value in (('canonical_term', ''), ('category', ''), ('rationale', None),
                             ('definition', ''), ('abbreviation', 5), ('observed_variants', ['']),
                             ('allowed_variants', 'error'), ('ambiguous_variants', [None]),
                             ('verification_status', 'assumed'), ('approval_status', 'pending')):
            with self.subTest(field=field):
                data = copy.deepcopy(self.glossary)
                data['terms'][0][field] = value
                self.assertTrue(any(field in error for error in self.validate(data)))
        data = copy.deepcopy(self.glossary)
        del data['terms'][0]['definition']
        self.assertTrue(any('definition' in error for error in self.validate(data)))

    def test_counts_first_occurrence_and_ranges(self):
        for field, value in (('occurrences', True), ('occurrences', -1), ('occurrences', 1),
                             ('first_occurrence', {'line': 3, 'section': 'Intro'}),
                             ('first_occurrence', {'line': 2, 'section': 'Wrong'}),
                             ('occurrence_locations', [])):
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.glossary)
                data['terms'][0][field] = value
                self.assertTrue(self.validate(data))
        data = copy.deepcopy(self.glossary)
        data['terms'][0]['occurrence_locations'][0]['line'] = True
        self.assertTrue(any('line' in error for error in self.validate(data)))

    def test_exact_source_anchors_and_private_errors(self):
        for field, value in (('section', ''), ('term', 'secret absent term'), ('context', 'secret absent context')):
            with self.subTest(field=field):
                data = copy.deepcopy(self.glossary)
                data['terms'][0]['occurrence_locations'][0][field] = value
                errors = self.validate(data)
                self.assertTrue(errors)
                if value:
                    self.assertNotIn(value, str(errors))
        data = copy.deepcopy(self.glossary)
        location = data['terms'][0]['occurrence_locations'][0]
        location['term'] = 'forecast'
        location['context'] = 'error matters'
        self.assertTrue(any('in context' in error for error in self.validate(data)))


if __name__ == '__main__':
    unittest.main()
