import json
import tempfile
import unittest
from pathlib import Path

from ai4science.contracts import create_artifact
from ai4science.statistics_recalculation import recalculate_forecast, summarize_paired
from ai4science.statistics_review_validation import validate_statistics_review_run
import ai4science.statistics_recalculation as calculation


class StatisticsReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'paper.md').write_text('# Paper\nClaim.\n', encoding='utf-8')
        (self.root / 'data.csv').write_text('actual,predicted\n2,1\n3,4\n', encoding='utf-8')
        self.evidence = {'schema_version':'1.0', 'artifact':create_artifact(self.root, 'paper.md').to_dict(), 'description':'claim', 'locator':'L2-L2'}
        self.claims = [{'claim_id':'c1','source_location':'L2-L2','claim':'Claim.', 'status':'partially_supported','evidence_location':[self.evidence]}]
        self.record = recalculate_forecast(self.root, 'data.csv', actual_column='actual', prediction_column='predicted', metrics=['MAE'], unit='units', aggregation='mean_over_rows', authorized_data_paths=('data.csv',), reported_values={'MAE':1.0}, tolerance=0.01)
        self.recalc = {'schema_version':'1.0','mode':'metric_recalculation','records':[self.record]}
        self.manifest = {'schema_version':'1.0','execution_mode':'inline_skill','review_level':'B','executed_commands':['python test command'], 'input_artifacts':[create_artifact(self.root, 'data.csv').to_dict()], 'software_versions':{'python':'test'}, 'reproduction_status':'not_performed','limitations':['No experiment rerun']}
        self.findings = []
        self.save()

    def save(self):
        for name, value in [('claims.json',self.claims), ('findings.json',self.findings), ('recalc.json',self.recalc), ('manifest.json',self.manifest)]:
            (self.root / name).write_text(json.dumps(value), encoding='utf-8')
        (self.root / 'report.md').write_text('# Report\nReviewed.\n', encoding='utf-8')

    def validate(self, **kwargs):
        opts = {'evidence_paths':('data.csv',), 'trusted_calculation_scripts':(Path(calculation.__file__).resolve(),)}
        opts.update(kwargs)
        return validate_statistics_review_run(self.root, 'paper.md', 'findings.json', 'claims.json', 'recalc.json', 'manifest.json', 'report.md', **opts)

    def test_valid_provenance(self):
        self.assertEqual(self.validate(), [])

    def test_data_requires_authorization_and_hash(self):
        self.assertTrue(self.validate(evidence_paths=()))
        (self.root / 'data.csv').write_text('changed', encoding='utf-8')
        self.assertTrue(any('hash' in error for error in self.validate()))

    def test_script_must_be_explicitly_trusted(self):
        self.assertTrue(any('script' in e for e in self.validate(trusted_calculation_scripts=())))

    def test_claim_evidence_and_location(self):
        self.claims[0]['evidence_location'][0]['locator'] = 'L999-L999'
        self.save()
        self.assertTrue(any('locator' in e for e in self.validate()))

    def test_report_only_and_no_data(self):
        self.recalc = {'schema_version':'1.0','mode':'report_only','records':[],'reason':'No measurements supplied'}
        self.manifest['review_level'] = 'A'
        self.manifest['input_artifacts'] = []
        self.save()
        self.assertEqual(self.validate(), [])
        self.recalc.pop('reason')
        self.save()
        self.assertTrue(self.validate())

    def test_not_executed_cannot_contain_values(self):
        self.recalc['records'] = [{'status':'not_executed','reason':'No data','recalculated_value':42}]
        self.save()
        self.assertTrue(any('not_executed' in e for e in self.validate()))

    def test_complete_reproduction_never_auto_accepted(self):
        self.manifest['reproduction_status'] = 'reproduced'
        self.save()
        self.assertTrue(any('reproduction' in e for e in self.validate()))

    def test_result_comparison_consistency(self):
        self.record['calculations'][0]['difference'] = 9
        self.save()
        self.assertTrue(any('comparison' in e for e in self.validate()))

    def paired_record(self):
        (self.root / 'pairs.csv').write_text('id,baseline,proposed\na,10,9\nb,10,12\n', encoding='utf-8')
        self.record = summarize_paired(self.root, 'pairs.csv', pair_id_column='id',
            baseline_column='baseline', proposed_column='proposed', lower_is_better=True,
            unit='messages', authorized_data_paths=('pairs.csv',))
        self.recalc['records'] = [self.record]
        self.manifest['input_artifacts'] = [create_artifact(self.root, 'pairs.csv').to_dict()]
        self.save()

    def test_descriptive_paired_summary(self):
        self.paired_record()
        self.assertEqual(self.validate(evidence_paths=('pairs.csv',)), [])

    def test_paired_summary_rejects_invalid_values(self):
        import copy
        self.paired_record()
        valid = copy.deepcopy(self.record)
        changes = [
            ('n_pairs', 3), ('improved_count', -1), ('worsened_count', True),
            ('unit', 'seconds'), ('lower_is_better', False),
            ('mean_proposed_minus_baseline', 99), ('min_proposed_minus_baseline', float('nan')),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                self.record = copy.deepcopy(valid)
                self.record['calculation'][field] = value
                self.recalc['records'] = [self.record]
                self.save()
                self.assertTrue(self.validate(evidence_paths=('pairs.csv',)))

    def test_paired_summary_cannot_claim_inference(self):
        self.paired_record()
        self.record['calculation']['p_two_sided'] = 0.01
        self.save()
        self.assertTrue(self.validate(evidence_paths=('pairs.csv',)))
        del self.record['calculation']['p_two_sided']
        self.record['execution']['operation'] = 'paired_sign_flip'
        self.save()
        self.assertTrue(self.validate(evidence_paths=('pairs.csv',)))

    def test_output_alias_rejected(self):
        self.assertTrue(validate_statistics_review_run(self.root, 'paper.md', 'paper.md', 'claims.json', 'recalc.json', 'manifest.json', 'report.md', evidence_paths=('data.csv',)))

    def test_traversal_and_symlink_escape(self):
        self.assertTrue(validate_statistics_review_run(self.root, '../bad', 'findings.json', 'claims.json', 'recalc.json', 'manifest.json', 'report.md'))
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / 'secret').write_text('secret')
            (self.root / 'link').symlink_to(Path(outside) / 'secret')
            self.assertTrue(validate_statistics_review_run(self.root, 'link', 'findings.json', 'claims.json', 'recalc.json', 'manifest.json', 'report.md'))


if __name__ == '__main__':
    unittest.main()
