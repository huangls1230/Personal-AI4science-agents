"""Deterministic integration gates; fake stages are not agent calls."""
import json
import tempfile
import unittest
from pathlib import Path

from ai4science.paper_editing_workflow import (route, prepare_run, begin_stage,
    complete_stage, fail_stage, retry_stage, verify_run, approved_changes_only)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); (self.root/'outputs').mkdir()
        (self.root/'input.md').write_text('# Study\nSynthetic text may suggest a trend [@fake].\n')
        (self.root/'glossary.yaml').write_text('{}\n')

    def prepare(self, kind='full', **kwargs):
        args = dict(project_id='p', manuscript_path='input.md', task_type=kind,
                    editing_scope='all', glossary_path='glossary.yaml', max_retries=0)
        args.update(kwargs)
        return prepare_run(self.root, 'outputs', **args)

    def artifact(self, run, stage, name='report.md'):
        directory=run/stage; directory.mkdir(exist_ok=True)
        path=directory/name; path.write_text('Synthetic artifact.\n')
        return path.relative_to(self.root).as_posix()

    def test_routing_only_necessary_roles(self):
        self.assertEqual(('structure',),route('structure'))
        self.assertEqual(('terminology',),route('terminology'))
        self.assertEqual(('language',),route('language'))
        self.assertEqual(('structure','terminology','language','final_validation'),route('full'))
        with self.assertRaises(ValueError):route('other')

    def test_sequential_handoff_version_records_and_approval_pending(self):
        run,_=self.prepare()
        with self.assertRaises(ValueError):begin_stage(self.root,run,'terminology')
        for stage in route('full'):
            begin_stage(self.root,run,stage)
            complete_stage(self.root,run,stage,[self.artifact(run,stage)],execution_mode='deterministic' if stage=='final_validation' else 'inline_skill')
        manifest=json.loads((run/'manifest.json').read_text())
        self.assertEqual('awaiting_author_approval',manifest['status'])
        self.assertEqual('pending',manifest['author_approval'])
        self.assertEqual('unknown',manifest['usage'])
        self.assertEqual(5,len(manifest['artifacts']))
        for item in manifest['artifacts']:
            self.assertTrue({'artifact_id','source_artifact_id','source_hash','output_hash','stage','agent_or_executor','approval_status','created_at'}<=set(item))
        verify_run(self.root,run)

    def test_single_agent_routes(self):
        for kind in ('structure','terminology','language'):
            with self.subTest(kind=kind):
                run,_=self.prepare(kind,project_id=kind);begin_stage(self.root,run,kind)
                complete_stage(self.root,run,kind,[self.artifact(run,kind)],execution_mode='inline_skill')
                self.assertEqual([kind],[s['stage'] for s in json.loads((run/'manifest.json').read_text())['stages']])

    def test_approval_gate_never_trusts_status(self):
        edit={'change_id':'L1','applied_to_draft':True,'status':'approved'}
        self.assertFalse(approved_changes_only([edit],set()))
        self.assertTrue(approved_changes_only([edit],{'L1'}))
        self.assertTrue(approved_changes_only([{'change_id':'L2','applied_to_draft':False}],set()))

    def test_failure_blocks_downstream_and_retry_is_bounded(self):
        run,_=self.prepare(max_retries=1);begin_stage(self.root,run,'structure')
        fail_stage(self.root,run,'structure','simulated failure')
        with self.assertRaises(ValueError):begin_stage(self.root,run,'terminology')
        retry_stage(self.root,run,'structure');begin_stage(self.root,run,'structure')
        fail_stage(self.root,run,'structure','simulated second failure')
        with self.assertRaises(ValueError):retry_stage(self.root,run,'structure')

    def test_input_and_output_conflict_stops_reuse_and_handoff(self):
        run,_=self.prepare();begin_stage(self.root,run,'structure')
        (self.root/'input.md').write_text('Changed source\n')
        with self.assertRaisesRegex(ValueError,'conflict'):complete_stage(self.root,run,'structure',[self.artifact(run,'structure')],execution_mode='inline_skill')
        with self.assertRaisesRegex(ValueError,'conflict'):verify_run(self.root,run)
        state = json.loads((run/'manifest.json').read_text())
        self.assertEqual('failed', state['status'])
        self.assertEqual('failed', state['stages'][0]['status'])

    def test_dedup_reuses_and_checks_tampering(self):
        run,reused=self.prepare('structure');self.assertFalse(reused)
        begin_stage(self.root,run,'structure');p=self.artifact(run,'structure')
        complete_stage(self.root,run,'structure',[p],execution_mode='inline_skill')
        same,reused=self.prepare('structure');self.assertTrue(reused);self.assertEqual(run,same)
        (self.root/p).write_text('tampered')
        with self.assertRaisesRegex(ValueError,'conflict'):self.prepare('structure')

    def test_missing_glossary_and_path_escape(self):
        with self.assertRaisesRegex(ValueError,'glossary'):self.prepare('language',glossary_path=None)
        with self.assertRaises(ValueError):self.prepare('full',manuscript_path='../secret.md')
        with self.assertRaises(ValueError):prepare_run(self.root,'../outside',project_id='p',manuscript_path='input.md',task_type='structure',editing_scope='all')

    def test_inline_and_native_are_distinct_records_not_proof(self):
        for mode in ('inline_skill','native_subagent'):
            run,_=self.prepare('structure',project_id=mode);begin_stage(self.root,run,'structure')
            complete_stage(self.root,run,'structure',[self.artifact(run,'structure')],execution_mode=mode)
            self.assertEqual(mode,json.loads((run/'manifest.json').read_text())['stages'][0]['execution_mode'])

    def test_unapproved_structure_never_changes_source(self):
        run,_=self.prepare();original=(self.root/'input.md').read_bytes()
        begin_stage(self.root,run,'structure');complete_stage(self.root,run,'structure',[self.artifact(run,'structure')],execution_mode='inline_skill')
        begin_stage(self.root,run,'terminology');self.assertEqual(original,(self.root/'input.md').read_bytes())
        manifest=json.loads((run/'manifest.json').read_text())
        self.assertEqual('original',manifest['artifacts'][1]['source_artifact_id'])

    def test_reject_output_outside_run(self):
        run,_=self.prepare('structure');begin_stage(self.root,run,'structure')
        (self.root/'other.md').write_text('other')
        with self.assertRaises(ValueError):complete_stage(self.root,run,'structure',['other.md'],execution_mode='inline_skill')
        other_stage = self.artifact(run,'language')
        with self.assertRaises(ValueError):complete_stage(self.root,run,'structure',[other_stage],execution_mode='inline_skill')

if __name__=='__main__':unittest.main()
