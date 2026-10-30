import json
import tempfile
import unittest
from pathlib import Path

from ai4science.consistency_review_validation import (
    compare_numeric_claims, index_markdown, validate_consistency_review_run, inspect_statistics_handoff,
)
from ai4science.contracts import create_artifact


class NumericTests(unittest.TestCase):
    def item(self, value):
        return {'value': value, 'metric': 'reduction', 'unit': '%', 'conditions': {'agents': '20', 'dataset': 'A'}}

    def test_same_condition_and_rounding_boundary(self):
        self.assertEqual(compare_numeric_claims(self.item(18.1), self.item(18), tolerance=.1)['status'], 'within_tolerance')
        self.assertEqual(compare_numeric_claims(self.item(25), self.item(18), tolerance=.1)['status'], 'contradicted')

    def test_incompatible_and_unknown_conditions(self):
        a, b = self.item(18), self.item(25)
        b['conditions']['agents'] = '40'
        self.assertEqual(compare_numeric_claims(a, b, tolerance=.1)['status'], 'insufficient_information')
        b['conditions'] = {'agents': 'unknown'}
        self.assertEqual(compare_numeric_claims(a, b, tolerance=.1)['status'], 'insufficient_information')
        b = self.item(18); b['unit'] = 'percentage points'
        self.assertEqual(compare_numeric_claims(a, b, tolerance=.1)['status'], 'insufficient_information')
        b['unit'] = '%'; b['metric'] = 'another metric'
        self.assertEqual(compare_numeric_claims(a, b, tolerance=.1)['status'], 'insufficient_information')

    def test_invalid_numbers(self):
        for value in (float('nan'), float('inf'), True, '3'):
            with self.assertRaises(ValueError):
                compare_numeric_claims(self.item(value), self.item(0), tolerance=.1)
        with self.assertRaises(ValueError):
            compare_numeric_claims(self.item(1), self.item(1), tolerance=-1)


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'paper.md').write_text('# Paper\nSee Figure 1.\n![plot](fig.png)\n```\nFigure 22\n```\n', encoding='utf-8')
        (self.root / 'fig.png').write_bytes(b'fixture bytes not an actual figure')
        self.art = create_artifact(self.root, 'paper.md').to_dict()
        self.img = create_artifact(self.root, 'fig.png').to_dict()
        self.findings = [{'schema_version':'1.0','finding_id':'F1','reviewer_role':'review_consistency','issue_type':'contrast','severity':'major','confidence':'high','verification_status':'verified','source_location':'L2-L2','claim_or_observation':'Claim', 'evidence_location':[{'artifact':self.art,'description':'test','locator':'L2-L2','schema_version':'1.0'}], 'reasoning':'reason','impact':'impact','recommended_action':'check','additional_material_required':[],'verification_method':'read','verification_limitations':'fixture'}]
        self.inventory = {'schema_version':'1.0','artifacts':[
            {'artifact_id':'P','source_path':'paper.md','source_hash':self.art['sha256'],'artifact_type':'manuscript','document_section':'all','page_or_location':'L1-L6','extraction_method':'text','verification_status':'available'},
            {'artifact_id':'I','source_path':'fig.png','source_hash':self.img['sha256'],'artifact_type':'image','document_section':'results','page_or_location':'L3-L3','extraction_method':'image','verification_status':'available'},
            {'artifact_id':'M','source_path':'missing.png','source_hash':None,'artifact_type':'image','document_section':'results','page_or_location':'L3-L3','extraction_method':'unavailable','verification_status':'missing'}]}
        self.claims = {'schema_version':'1.0','claims':[{'claim_id':'C','claim_text':'claim','source_location':'L2-L2','evidence_ids':['P'],'evidence_locations':['L2-L2'],'evidence_scope':'reported','reported_magnitude':'unknown','uncertainty_information':'unknown','alignment_status':'potential_issue','limitation':'test only','recommended_action':'review'}]}
        self.cross = {'schema_version':'1.0','references':[{'reference_id':'R','reference_type':'figure','source_location':'L2-L2','target':'Figure 1','status':'not_checked'}]}
        self.visual = {'schema_version':'1.0','figures':[{'artifact_id':'I','visual_review_status':'not_performed','inspection_method':'none','inspection_event':'','checked_content':'','limitations':'not inspected'},{'artifact_id':'M','visual_review_status':'not_performed','inspection_method':'none','inspection_event':'','checked_content':'','limitations':'missing'}]}
        (self.root/'report.md').write_text('# Report\nTest only.\n')
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        for name, obj in [('findings',self.findings),('claims',self.claims),('inventory',self.inventory),('cross',self.cross),('visual',self.visual)]:
            (self.root / (name+'.json')).write_text(json.dumps(obj))

    def validate(self, paths=('fig.png','missing.png')):
        return validate_consistency_review_run(self.root, 'paper.md', 'findings.json', 'claims.json', 'inventory.json', 'cross.json', 'visual.json', 'report.md', evidence_paths=paths)

    def test_index_is_literal_and_ignores_fences(self):
        idx = index_markdown(self.root, 'paper.md')
        self.assertEqual(idx['images'][0]['target'], 'fig.png')
        self.assertEqual([r['number'] for r in idx['references']], ['1'])

    def test_valid_manifests_and_immutable_inputs(self):
        before = (self.root/'paper.md').read_bytes()
        self.assertEqual(self.validate(), [])
        self.assertEqual(before, (self.root/'paper.md').read_bytes())

    def test_missing_figure_cannot_be_claimed_checked(self):
        self.visual['figures'][1].update(visual_review_status='checked',inspection_method='view',inspection_event='event',checked_content='trend')
        self.write()
        self.assertTrue(any('checked requires available' in x for x in self.validate()))

    def test_image_existence_is_not_visual_review(self):
        self.claims['claims'][0].update(evidence_ids=['I'], evidence_locations=['image'], alignment_status='contradicted')
        self.write()
        self.assertTrue(any('not been visually checked' in x for x in self.validate()))
        self.visual['figures'][0].update(visual_review_status='checked',inspection_method='view',inspection_event='event-id',checked_content='trend')
        self.write()
        self.assertEqual(self.validate(), [])  # structural assertion, not proof of viewing

    def test_unauthorized_and_hash_mismatch(self):
        self.assertTrue(any('not authorized' in x for x in self.validate(('missing.png',))))
        (self.root/'paper.md').write_text('# Changed\nline\n')
        self.assertTrue(any('hash' in x for x in self.validate()))

    def test_path_escape_and_hardlink_output_rejected(self):
        self.assertTrue(self.validate(('../outside',)))
        (self.root/'alias.md').hardlink_to(self.root/'paper.md')
        errors = validate_consistency_review_run(self.root,'paper.md','findings.json','claims.json','inventory.json','cross.json','visual.json','alias.md',evidence_paths=('fig.png','missing.png'))
        self.assertIn('independent', errors[0])

    def test_invalid_finding_and_bad_location(self):
        self.findings[0]['reviewer_role'] = 'review_statistics'
        self.findings[0]['source_location'] = 'L20-L20'
        self.write()
        errors = self.validate()
        self.assertTrue(any('reviewer role' in x for x in errors))
        self.assertTrue(any('source location' in x for x in errors))


class StatisticsHandoffTests(unittest.TestCase):
    def setUp(self):
        from ai4science.statistics_recalculation import recalculate_forecast
        import ai4science.statistics_recalculation as calculation
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'paper.md').write_text('# Paper\nClaim.\n')
        (self.root/'current.md').write_text('# Paper\nClaim.\n')
        (self.root/'data.csv').write_text('actual,predicted\n2,1\n3,4\n')
        self.record = recalculate_forecast(self.root, 'data.csv', actual_column='actual', prediction_column='predicted', metrics=['MAE'], unit='units', aggregation='mean_over_rows', authorized_data_paths=('data.csv',), reported_values={'MAE': 1.0}, tolerance=0.01)
        self.recalc = {'schema_version':'1.0','mode':'metric_recalculation','records':[self.record, {'status':'not_executed','reason':'data missing'}]}
        self.manifest = {'schema_version':'1.0','execution_mode':'inline_skill','review_level':'B','executed_commands':['fixture'], 'input_artifacts':[create_artifact(self.root, 'paper.md').to_dict(), create_artifact(self.root, 'data.csv').to_dict()], 'software_versions':{'python':'test'}, 'reproduction_status':'not_performed','limitations':['no reproduction']}
        self.trusted = (Path(calculation.__file__).resolve(),)
        (self.root/'findings.json').write_text('[]')
        (self.root/'claims.json').write_text('[]')
        (self.root/'report.md').write_text('# Report\nTest.')
        self.save()

    def save(self):
        (self.root/'recalc.json').write_text(json.dumps(self.recalc))
        (self.root/'manifest.json').write_text(json.dumps(self.manifest))

    def inspect(self):
        return inspect_statistics_handoff(self.root, 'current.md', 'paper.md', 'findings.json', 'claims.json', 'recalc.json', 'manifest.json', 'report.md', evidence_paths=('data.csv',), trusted_calculation_scripts=self.trusted)

    def test_same_hash_and_unexecuted_record(self):
        result = self.inspect()
        self.assertEqual(result['status'], 'available')
        self.assertEqual([x['status'] for x in result['records']], ['completed_record','not_executed'])
        self.assertIn('do not prove', result['limitation'])

    def test_changed_manuscript_blocks(self):
        (self.root/'current.md').write_text('# Different version\n')
        self.assertEqual(self.inspect()['status'], 'blocked')

    def test_absent_manifest_manuscript_blocks(self):
        self.manifest['input_artifacts'] = [create_artifact(self.root, 'data.csv').to_dict()]
        self.save()
        self.assertEqual(self.inspect()['status'], 'blocked')

    def test_report_only_cannot_be_verified(self):
        self.recalc = {'schema_version':'1.0','mode':'report_only','records':[],'reason':'no data'}
        self.save()
        self.assertEqual(self.inspect()['status'], 'no_completed_recalculation')

    def test_handoff_with_invalid_calculation_blocked(self):
        self.record['calculations'][0]['difference'] = 99
        self.save()
        self.assertEqual(self.inspect()['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
