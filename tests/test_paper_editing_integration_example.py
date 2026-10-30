"""Regression tests for saved native-role integration artifacts; no runtime claim."""
from pathlib import Path
import json
import unittest

from ai4science.contracts import ExecutionRequest, ExecutionResult, create_artifact
from ai4science.paper_editing_workflow import approved_changes_only
from ai4science.paper_structure_validation import validate_structure_run
from ai4science.paper_terminology_validation import validate_terminology_run, validate_glossary_data
from ai4science.paper_language_validation import validate_language_run

ROOT=Path(__file__).resolve().parents[1]/'workspace'
RUN='paper-editing-integration-fixture/full-run/'
SOURCE='paper-language-v0.1-fixture/manuscript.md'
OLD='paper-language-v0.1-fixture/terminology_glossary.yaml'
SHA='fa05039c73ebacae4d9f1d76d901521e00d78603ddf703ce91974bf2d45a4501'


class IntegrationExampleTests(unittest.TestCase):
    def test_serial_handoffs_and_contracts(self):
        self.assertEqual(SHA,create_artifact(ROOT,SOURCE).sha256)
        requests={}
        for stage,role in (('structure','paper_structure'),('terminology','paper_terminology'),('language','paper_language')):
            request=ExecutionRequest.from_dict(json.loads((ROOT/RUN/stage/'execution_request.json').read_text()))
            result=ExecutionResult.from_dict(json.loads((ROOT/RUN/stage/'execution_result.json').read_text()))
            request.validate(ROOT);result.validate(ROOT)
            self.assertEqual(role,request.executor);self.assertEqual(role,result.executor)
            self.assertEqual('pending',result.approval_status)
            self.assertEqual(set(request.task.output_artifacts),{a.path for a in result.output_artifacts})
            self.assertIn(SOURCE,{a.path for a in request.task.input_artifacts})
            requests[stage]={a.path for a in request.task.input_artifacts}
        self.assertIn(RUN+'structure/structure_report.md',requests['terminology'])
        self.assertIn(RUN+'terminology/terminology_glossary.yaml',requests['language'])
        self.assertIn(RUN+'terminology/language_handoff.md',requests['language'])
        self.assertNotIn(RUN+'structure/restructuring_plan.json',requests['language'])
        self.assertEqual(SHA,create_artifact(ROOT,SOURCE).sha256)

    def test_all_three_outputs_reuse_existing_validators(self):
        self.assertEqual([],validate_structure_run(ROOT,SOURCE,RUN+'structure/restructuring_plan.json'))
        self.assertEqual([],validate_terminology_run(ROOT,SOURCE,RUN+'terminology/terminology_changes.json'))
        glossary=json.loads((ROOT/RUN/'terminology/terminology_glossary.yaml').read_text())
        self.assertEqual([],validate_glossary_data(ROOT,SOURCE,glossary))
        initial=json.loads((ROOT/OLD).read_text())
        self.assertIn('mock',initial['fixture_notice'].lower())
        self.assertTrue(all(t in glossary['terms'] for t in initial['terms'] if t['approval_status']=='approved'))
        params=json.loads((ROOT/RUN/'language/language_input.json').read_text())
        self.assertEqual([],validate_language_run(ROOT,SOURCE,RUN+'language/language_changes.json',RUN+'language/manuscript_edited.md',glossary,params['allowed_line_ranges']))
        candidate=(ROOT/RUN/'final_candidate.md').read_bytes()
        self.assertEqual(candidate,(ROOT/RUN/'language/manuscript_edited.md').read_bytes())
        for item in (b'0.25 units',b'[@synthetic2026]',b'$\\hat{y}_{t+1} = f(x_t)$',b'Horizon Mapper',b'may suggest'):
            self.assertIn(item,candidate)

    def test_approval_gate_and_version_manifest(self):
        changes=json.loads((ROOT/RUN/'language/language_changes.json').read_text())['changes']
        self.assertFalse(approved_changes_only(changes,set()))
        manifest=json.loads((ROOT/RUN/'version_manifest.json').read_text())
        self.assertEqual('awaiting_author_approval',manifest['final_status'])
        self.assertIsNone(manifest['approved_structure_revision'])
        self.assertIn('simulated',manifest['glossary_approval'])
        ids=set()
        for artifact in manifest['artifacts']:
            self.assertNotIn(artifact['artifact_id'],ids);ids.add(artifact['artifact_id'])
            self.assertEqual(artifact['output_hash'],create_artifact(ROOT,artifact['path']).sha256)
            self.assertTrue({'artifact_id','source_artifact_id','source_hash','output_hash','stage','agent_or_executor','approval_status','created_at'}<=set(artifact))
        self.assertIn('final_candidate.md',ids);self.assertIn('change_log.md',ids)
        self.assertIn('PENDING',(ROOT/RUN/'final_validation_report.md').read_text())
        self.assertEqual(SHA,create_artifact(ROOT,SOURCE).sha256)

if __name__=='__main__':unittest.main()
