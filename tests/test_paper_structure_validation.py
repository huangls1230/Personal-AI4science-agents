import copy
import json
import tempfile
import unittest
from pathlib import Path

from ai4science.contracts import create_artifact
from ai4science.paper_structure_validation import validate_structure_run


class StructureValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = 'manuscript.md'
        self.plan_path = 'restructuring_plan.json'
        (self.root / self.source).write_text(
            '# Introduction\nA coordination problem remains.\n\n# Method\nWe use a forecast.\n', encoding='utf-8')
        self.plan = {
            'schema_version': '0.1', 'task_id': 'structure-test',
            'review_scope': 'Complete manuscript', 'execution_mode': 'native_subagent',
            'manuscript': {'path': self.source, 'sha256': create_artifact(self.root, self.source).sha256},
            'findings': [{
                'id': 'S1', 'location': {'section': 'Introduction', 'start_line': 2,
                                         'end_line': 2, 'quote': 'coordination problem'},
                'issue_type': 'missing motivation', 'recommendation': 'Explain the problem.',
                'rationale': 'The significance is not stated.', 'priority': 'high',
                'action': 'add_argument', 'may_change_scientific_meaning': True,
                'author_approval_required': True,
            }],
        }

    def validate(self, plan=None, input_path=None, plan_path=None):
        (self.root / self.plan_path).write_text(json.dumps(self.plan if plan is None else plan), encoding='utf-8')
        return validate_structure_run(self.root, input_path or self.source, plan_path or self.plan_path)

    def test_valid_plan_and_empty_findings(self):
        self.assertEqual([], self.validate())
        plan = copy.deepcopy(self.plan)
        plan['findings'] = []
        self.assertEqual([], self.validate(plan))

    def test_quote_and_line_ranges(self):
        for change in ({'quote': 'not in source'}, {'start_line': 0}, {'end_line': 20},
                       {'start_line': True}, {'start_line': 4, 'end_line': 2}):
            with self.subTest(change=change):
                plan = copy.deepcopy(self.plan)
                plan['findings'][0]['location'].update(change)
                self.assertTrue(self.validate(plan))
        # Error messages must not expose source text or supplied quote.
        plan = copy.deepcopy(self.plan)
        plan['findings'][0]['location']['quote'] = 'private invented quote'
        self.assertNotIn('private invented quote', str(self.validate(plan)))

    def test_hash_and_path_identity(self):
        plan = copy.deepcopy(self.plan)
        plan['manuscript']['sha256'] = '0' * 64
        self.assertTrue(any('sha256' in e for e in self.validate(plan)))
        plan = copy.deepcopy(self.plan)
        plan['manuscript']['path'] = 'other.md'
        self.assertTrue(any('manuscript.path' in e for e in self.validate(plan)))
        (self.root / self.source).write_text('changed\n', encoding='utf-8')
        self.assertTrue(any('sha256' in e for e in self.validate()))

    def test_risk_needs_author_approval_and_boolean_values(self):
        plan = copy.deepcopy(self.plan)
        plan['findings'][0]['author_approval_required'] = False
        self.assertTrue(any('requires author approval' in e for e in self.validate(plan)))
        plan['findings'][0]['may_change_scientific_meaning'] = 1
        self.assertTrue(any('boolean' in e for e in self.validate(plan)))

    def test_run_metadata_requires_scope_identifier_and_known_execution_mode(self):
        plan = copy.deepcopy(self.plan)
        plan['execution_mode'] = 'inline'
        self.assertEqual([], self.validate(plan))
        for field, value in (('task_id', ''), ('review_scope', '  '),
                             ('execution_mode', 'native'), ('execution_mode', None),
                             ('execution_mode', ['inline'])):
            with self.subTest(field=field, value=value):
                plan = copy.deepcopy(self.plan)
                plan[field] = value
                self.assertTrue(any(field in error for error in self.validate(plan)))
        for field in ('task_id', 'review_scope', 'execution_mode'):
            with self.subTest(missing=field):
                plan = copy.deepcopy(self.plan)
                del plan[field]
                self.assertTrue(any(field in error for error in self.validate(plan)))

    def test_missing_fields_invalid_values_and_duplicate_ids(self):
        plan = copy.deepcopy(self.plan)
        del plan['findings'][0]['rationale']
        plan['findings'][0]['priority'] = 'urgent'
        plan['findings'][0]['action'] = 'delete'
        plan['findings'].append(copy.deepcopy(plan['findings'][0]))
        errors = self.validate(plan)
        for text in ('rationale', 'priority', 'action', 'unique'):
            self.assertTrue(any(text in error for error in errors), errors)

    def test_workspace_traversal_and_symlink_escape(self):
        self.assertTrue(self.validate(input_path='../secret.md'))
        self.assertTrue(self.validate(plan_path='../secret.json'))
        with tempfile.TemporaryDirectory() as elsewhere:
            (Path(elsewhere) / 'secret.md').write_text('secret', encoding='utf-8')
            (self.root / 'escape').symlink_to(elsewhere, target_is_directory=True)
            self.assertTrue(self.validate(input_path='escape/secret.md'))

    def test_invalid_json_and_top_level(self):
        self.assertTrue(self.validate(plan=[]))
        (self.root / self.plan_path).write_text('{ invalid', encoding='utf-8')
        self.assertTrue(validate_structure_run(self.root, self.source, self.plan_path))
        self.assertTrue(validate_structure_run(self.root, self.source, self.source))


if __name__ == '__main__':
    unittest.main()
