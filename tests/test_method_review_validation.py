import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from ai4science.contracts import create_artifact
from ai4science.method_review_validation import validate_method_review_run


class MethodReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'paper.md').write_text('# Paper\nFuture values are used.\n# Method\nDetails are unclear.\n')
        (self.root / 'other.md').write_text('# Supplement\nIndependent text.\n')
        self.ref = create_artifact(self.root, 'paper.md').to_dict()
        self.finding = {
            'schema_version': '1.0', 'finding_id': 'M1', 'reviewer_role': 'review_method',
            'issue_type': 'temporal leakage', 'severity': 'major', 'confidence': 'high',
            'verification_status': 'verified', 'source_location': 'L2-L2',
            'claim_or_observation': 'An observation',
            'evidence_location': [{'schema_version': '1.0', 'artifact': self.ref,
                                   'description': 'Relevant source passage', 'locator': 'L2-L2'}],
            'reasoning': 'Reason', 'impact': 'Impact', 'recommended_action': 'Verify the protocol',
            'additional_material_required': [], 'verification_method': 'Read the passage',
            'verification_limitations': 'No data or code inspected',
        }
        self.assumption = {'assumption_id': 'A1', 'assumption_description': 'Hypothetical assumption',
                           'explicit_or_implicit': 'implicit', 'source_location': 'L2-L2',
                           'why_required': 'Explain dependency', 'evidence_support': 'Relevant passage',
                           'failure_condition': 'May fail under other conditions',
                           'impact_if_violated': 'Requires investigation',
                           'suggested_validation': 'Inspect protocol',
                           'verification_status': 'potential', 'reporting_status': 'unclear'}
        (self.root / 'report.md').write_text('# Method review\nNo replication claimed.\n')
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, findings=None, assumptions=None):
        (self.root / 'findings.json').write_text(json.dumps([self.finding] if findings is None else findings))
        (self.root / 'assumptions.yaml').write_text(json.dumps({'assumptions': [self.assumption] if assumptions is None else assumptions}))

    def validate(self, **kwargs):
        return validate_method_review_run(self.root, kwargs.pop('manuscript', 'paper.md'),
                                          kwargs.pop('findings', 'findings.json'),
                                          kwargs.pop('assumptions', 'assumptions.yaml'),
                                          kwargs.pop('report', 'report.md'), **kwargs)

    def test_valid_read_only_and_scope(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual([], self.validate(allowed_line_ranges=((1, 2),)))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_empty_findings_and_assumptions_are_valid(self):
        self.write([], [])
        self.assertEqual([], self.validate())

    def test_finding_schema_and_verification_requirement(self):
        for field, value in [('verification_status', 'replicated'), ('severity', 'fatal'),
                             ('reviewer_role', 'review_statistics'), ('reasoning', ' '),
                             ('evidence_location', [])]:
            with self.subTest(field=field):
                finding = copy.deepcopy(self.finding)
                finding[field] = value
                self.write([finding])
                self.assertTrue(self.validate())
        finding = copy.deepcopy(self.finding)
        finding['verification_status'] = 'insufficient_information'
        finding['evidence_location'] = []
        self.write([finding])
        self.assertEqual([], self.validate())

    def test_stale_hash_wrong_locator_and_review_scope(self):
        for field, value in [('locator', 'L50-L50'), ('locator', 'L2-L1'),
                             ('locator', 'Experiments'), ('locator', 'L4-L4')]:
            with self.subTest(value=value):
                finding = copy.deepcopy(self.finding)
                finding['evidence_location'][0][field] = value
                self.write([finding])
                self.assertTrue(self.validate(allowed_line_ranges=((1, 2),)))
        (self.root / 'paper.md').write_text('# Paper\nchanged\n# Method\nDetails are unclear.\n')
        self.write()
        self.assertTrue(any('sha256' in e for e in self.validate()))

    def test_authorized_extra_evidence_and_rejection(self):
        finding = copy.deepcopy(self.finding)
        finding['evidence_location'][0]['artifact'] = create_artifact(self.root, 'other.md').to_dict()
        finding['evidence_location'][0]['locator'] = 'L2-L2'
        self.write([finding])
        self.assertTrue(any('not authorized' in e for e in self.validate()))
        self.assertEqual([], self.validate(evidence_paths=('other.md',)))

    def test_scope_cannot_be_bypassed_by_authorized_source_alias(self):
        (self.root / 'alias.md').symlink_to(self.root / 'paper.md')
        finding = copy.deepcopy(self.finding)
        finding['evidence_location'][0]['artifact'] = create_artifact(self.root, 'alias.md').to_dict()
        finding['evidence_location'][0]['locator'] = 'L4-L4'
        self.write([finding])
        self.assertTrue(self.validate(evidence_paths=('alias.md',), allowed_line_ranges=((1, 2),)))

    def test_path_traversal_symlink_escape_and_output_alias(self):
        self.assertTrue(self.validate(manuscript='../outside.md'))
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'secret.md'
            target.write_text('secret')
            (self.root / 'escape').symlink_to(target)
            self.assertTrue(self.validate(manuscript='escape'))
            self.assertTrue(self.validate(report='escape'))
        self.assertTrue(self.validate(report='paper.md'))
        (self.root / 'alias').symlink_to(self.root / 'paper.md')
        self.assertTrue(self.validate(report='alias'))
        os.link(self.root / 'paper.md', self.root / 'hardlink')
        self.assertTrue(self.validate(report='hardlink'))
        self.assertTrue(self.validate(report='findings.json'))
        self.assertTrue(self.validate(report='other.md', evidence_paths=('other.md',)))

    def test_source_status_and_duplicates(self):
        finding = copy.deepcopy(self.finding)
        finding['source_location'] = 'L4-L4'
        self.write([finding])
        self.assertTrue(self.validate(allowed_line_ranges=((1, 2),)))
        self.write([self.finding, self.finding])
        self.assertTrue(any('unique' in e for e in self.validate()))
        self.write(assumptions=[self.assumption, self.assumption])
        self.assertTrue(any('unique' in e for e in self.validate()))
        for field, value in [('verification_status', 'unclear'), ('reporting_status', 'verified'),
                             ('explicit_or_implicit', 'guess'), ('source_location', 'L30-L31')]:
            with self.subTest(field=field):
                bad = dict(self.assumption, **{field: value})
                self.write(assumptions=[bad])
                self.assertTrue(self.validate())
        self.write(assumptions=[dict(self.assumption, reporting_status='not_reported')])
        self.assertEqual([], self.validate())

    def test_report_and_invalid_inputs(self):
        (self.root / 'report.md').write_text('  ')
        self.assertTrue(self.validate())
        (self.root / 'report.md').write_text('# Report\n')
        (self.root / 'assumptions.yaml').write_text('assumptions: []')
        self.assertTrue(self.validate())  # Only JSON syntax is supported.
        self.write()
        self.assertTrue(self.validate(allowed_line_ranges=((1, 99),)))
        self.assertTrue(self.validate(findings='missing.json'))


if __name__ == '__main__':
    unittest.main()
