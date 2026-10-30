import json
import tempfile
import unittest
from pathlib import Path

from ai4science.contracts import create_artifact
from ai4science.doublecheck_review_validation import validate_doublecheck_review_run


class DoublecheckValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.names = ['paper.md', 'independent.md', 'argument.md', 'independent.json',
                      'adjudication.json', 'missed.md', 'report.md', 'phases.json']
        (self.root / 'paper.md').write_text('# Experiment\nThe result is 7.\n', encoding='utf-8')
        for name in ('independent.md', 'argument.md', 'missed.md', 'report.md'):
            (self.root / name).write_text('# Report\nScoped review.\n', encoding='utf-8')
        self.evidence = {'schema_version':'1.0', 'artifact':self.ref('paper.md'),
                         'description':'Reported result', 'locator':'L2-L2'}
        self.original = self.finding('M1', 'review_method')
        self.write('source.json', [self.original])
        self.write('independent.json', [self.finding('D1', 'review_doublecheck')])
        self.row = {'source_finding_id':'M1', 'original_reviewer':'review_method',
                    'original_severity':'major', 'original_claim':'A reported concern',
                    'original_evidence':[self.evidence], 'independent_assessment':'Supported as reported',
                    'adjudication_status':'supported', 'final_severity':'major',
                    'supporting_evidence':[self.evidence], 'contradicting_evidence':[],
                    'reasoning':'Evidence corresponds to the concern.', 'recommended_action':'Clarify.',
                    'verification_limitations':'No external verification.'}
        self.write('adjudication.json', {'schema_version':'1.0', 'adjudications':[self.row]})
        self.manifest = {'schema_version':'1.0', 'execution_mode':'inline_skill',
                         'independence_status':'context_limited_not_enforced',
                         'limitations':'The event log does not enforce isolation.',
                         'manuscript':self.ref('paper.md'),
                         'pass1_artifacts':[self.ref(x) for x in ('independent.md','argument.md','independent.json')],
                         'events':['pass1_frozen','pass2_sources_opened'],
                         'source_reports':[{'reviewer_role':'review_method','findings':self.ref('source.json'),
                                            'manuscript':self.ref('paper.md')}]}
        self.write('phases.json', self.manifest)

    def ref(self, name):
        return create_artifact(self.root, name).to_dict()

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def finding(self, ident, role):
        return {'schema_version':'1.0', 'finding_id':ident, 'reviewer_role':role, 'issue_type':'claim',
                'severity':'major', 'confidence':'medium', 'verification_status':'potential',
                'source_location':'L2-L2', 'claim_or_observation':'A reported concern',
                'evidence_location':[self.evidence], 'reasoning':'A gap is possible.',
                'impact':'Interpretation may change.', 'recommended_action':'Clarify.',
                'additional_material_required':[], 'verification_method':'textual comparison',
                'verification_limitations':'Materials limited.'}

    def validate(self, evidence=(), source=('source.json',), names=None):
        return validate_doublecheck_review_run(self.root, *(names or self.names),
                                               source_finding_paths=source, evidence_paths=evidence)

    def test_valid(self):
        self.assertEqual(self.validate(), [])

    def test_manifest_does_not_certify_independence(self):
        self.assertEqual(self.manifest['independence_status'], 'context_limited_not_enforced')
        self.assertEqual(self.validate(), [])

    def test_reverse_phase_order_rejected(self):
        self.manifest['events'].reverse()
        self.write('phases.json', self.manifest)
        self.assertIn('phase events', self.validate()[0])

    def test_tampered_frozen_pass1_rejected(self):
        (self.root / 'independent.md').write_text('# Later edit\n')
        self.assertIn('frozen hashes mismatch', self.validate()[0])

    def test_mismatched_manuscript_blocks_before_reading_invalid_adjudication(self):
        (self.root / 'other.md').write_text('# Different version\n')
        self.manifest['source_reports'][0]['manuscript'] = self.ref('other.md')
        self.write('phases.json', self.manifest)
        (self.root / 'adjudication.json').write_text('invalid json')
        self.assertIn('version conflict', self.validate(evidence=('other.md',))[0])

    def test_unknown_source_path_needs_explicit_authorization(self):
        self.assertIn('not explicitly authorized', self.validate(source=())[0])

    def test_malformed_source_finding_rejected(self):
        self.original.pop('reasoning')
        self.write('source.json', [self.original])
        self.manifest['source_reports'][0]['findings'] = self.ref('source.json')
        self.write('phases.json', self.manifest)
        self.assertTrue(any('fails Review Finding Schema' in x for x in self.validate()))

    def test_duplicate_source_id_and_duplicate_adjudication_rejected(self):
        self.write('source.json', [self.original, self.original])
        self.manifest['source_reports'][0]['findings'] = self.ref('source.json')
        self.write('phases.json', self.manifest)
        self.write('adjudication.json', {'schema_version':'1.0','adjudications':[self.row,self.row]})
        errors = self.validate()
        self.assertTrue(any('duplicate finding_id' in x for x in errors))
        self.assertTrue(any('duplicate source finding reference' in x for x in errors))

    def test_severity_change_and_unsupported_require_actual_evidence(self):
        self.row['original_severity'] = 'minor'
        self.row['adjudication_status'] = 'unsupported'
        self.row['supporting_evidence'] = []
        self.write('adjudication.json', {'schema_version':'1.0','adjudications':[self.row]})
        errors = self.validate()
        self.assertTrue(any('does not preserve original' in x for x in errors))
        self.assertTrue(any('requires traceable evidence' in x for x in errors))

    def test_potential_evidence_and_scope_checked(self):
        self.row['supporting_evidence'][0]['locator'] = 'L200-L200'
        self.write('adjudication.json', {'schema_version':'1.0','adjudications':[self.row]})
        self.assertTrue(any('locator' in x for x in self.validate()))

    def test_missing_major_adjudication_detected(self):
        self.write('adjudication.json', {'schema_version':'1.0','adjudications':[]})
        self.assertTrue(any('has not been adjudicated' in x for x in self.validate()))

    def test_traversal_and_symlink_rejected(self):
        names = list(self.names)
        names[0] = '../outside.md'
        self.assertTrue(self.validate(names=names))
        (self.root / 'escape.md').symlink_to('/etc/hosts')
        names[0] = 'escape.md'
        self.assertTrue(self.validate(names=names))

    def test_output_may_not_alias_source(self):
        names = list(self.names)
        names[1] = 'paper.md'
        self.assertTrue(self.validate(names=names))

    def test_invalid_status_and_missing_limitation(self):
        self.row['adjudication_status'] = 'confirmed_everything'
        self.row['verification_limitations'] = ''
        self.write('adjudication.json', {'schema_version':'1.0','adjudications':[self.row]})
        self.assertTrue(self.validate())


if __name__ == '__main__':
    unittest.main()
