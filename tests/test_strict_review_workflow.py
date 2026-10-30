import json
from pathlib import Path
import tempfile
import unittest

from ai4science.contracts import create_artifact
from ai4science.strict_review_workflow import (route, prepare_session, verify_session,
    reuse_session, record_stage, aggregate_findings, prepare_rereview, build_evidence_inventory)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'paper.md').write_text('# Paper\nClaim and evidence.\n')
        (self.root / 'data.csv').write_text('x,y\n1,2\n')
        (self.root / 'skill.md').write_text('skill version 1\n')
        self.args = dict(project_id='p', review_session_id='s', manuscript_path='paper.md', mode='full',
                         review_scope='all', permission_status='authorized', evidence_paths=('data.csv',),
                         configuration_paths=('skill.md',))
        self.rel = 'projects/p/reviews/s'

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self):
        return prepare_session(self.root, **self.args)

    def out(self, stage, name='result.md'):
        path = self.root / self.rel / stage / name
        path.write_text('# Output\n')
        return path.relative_to(self.root).as_posix()

    def done(self, stage, status='completed', **kw):
        h = create_artifact(self.root, 'paper.md').sha256
        outs = [self.out(stage)] if status == 'completed' else []
        return record_stage(self.root, self.rel, stage, status=status, execution_mode='inline_skill',
                            output_paths=outs, errors=[] if status == 'completed' else ['failure'], manuscript_hash=h, **kw)

    def test_modes_route_minimal(self):
        self.assertEqual(route('method'), ('method',))
        self.assertEqual(route('statistics'), ('statistics',))
        self.assertEqual(route('consistency'), ('consistency',))
        self.assertEqual(route('full'), ('method','statistics','consistency','doublecheck','final_validation'))
        self.assertEqual(route('targeted_rereview'), ('targeted_rereview','final_validation'))
        with self.assertRaises(ValueError): route('other')

    def test_permission_before_any_input_reads(self):
        self.args.update(permission_status='unknown', manuscript_path='missing')
        with self.assertRaises(PermissionError): self.prepare()
        self.assertFalse((self.root / 'projects').exists())

    def test_snapshot_and_exclusive_session(self):
        self.prepare()
        state = verify_session(self.root, self.rel)
        self.assertEqual(state['config']['snapshot']['sha256'], state['config']['manuscript']['sha256'])
        self.assertEqual((self.root / self.rel / 'manuscript_snapshot.md').read_text(), (self.root / 'paper.md').read_text())
        with self.assertRaises(FileExistsError): self.prepare()

    def test_paths_reject_traversal_and_escape_symlink(self):
        self.args['manuscript_path'] = '../outside'
        with self.assertRaises(ValueError): self.prepare()
        (self.root / 'escape').symlink_to(Path(self.tmp.name).parent)
        self.args['manuscript_path'] = 'escape/elsewhere'
        with self.assertRaises(ValueError): self.prepare()

    def test_reject_bad_ids(self):
        self.args['project_id'] = '../x'
        with self.assertRaises(ValueError): self.prepare()

    def test_reject_modified_source_snapshot_and_evidence(self):
        for path in ('paper.md', 'data.csv', 'skill.md', self.rel + '/manuscript_snapshot.md'):
            with self.subTest(path=path):
                self.prepare()
                target = self.root / path
                old = target.read_bytes()
                target.write_bytes(old + b'changed')
                with self.assertRaises(ValueError): verify_session(self.root, self.rel)
                target.write_bytes(old)
                import shutil
                shutil.rmtree(self.root / 'projects')

    def test_stage_binding_and_separate_output(self):
        self.prepare()
        h = create_artifact(self.root, 'paper.md').sha256
        with self.assertRaises(ValueError):
            record_stage(self.root, self.rel, 'method', status='completed', execution_mode='inline_skill', output_paths=['paper.md'], manuscript_hash=h)
        with self.assertRaises(ValueError):
            record_stage(self.root, self.rel, 'method', status='completed', execution_mode='inline_skill', output_paths=[self.out('method')], manuscript_hash='0'*64)
        self.assertEqual(self.done('method')['stages']['method']['status'], 'completed')
        with self.assertRaises(ValueError): self.done('method')

    def test_must_not_declare_blind_from_manifest(self):
        self.prepare()
        with self.assertRaises(ValueError): self.done('method', blind_review=True)

    def test_doublecheck_waits_for_specialists(self):
        self.prepare()
        with self.assertRaises(ValueError): self.done('doublecheck')

    def test_partial_failure_and_valid_work_preserved(self):
        self.prepare()
        self.done('method')
        state = self.done('statistics', status='failed')
        self.assertEqual(state['status'], 'partial')
        self.assertEqual(state['stages']['method']['status'], 'completed')
        self.done('consistency')
        self.done('doublecheck')
        self.assertEqual(self.done('final_validation')['status'], 'partial')

    def test_cache_requires_all_inputs_configuration_and_output_unchanged(self):
        self.args['mode'] = 'method'
        self.prepare(); self.done('method')
        reuse = dict(project_id='p', manuscript_path='paper.md', mode='method', review_scope='all',
                     permission_status='authorized', evidence_paths=('data.csv',), configuration_paths=('skill.md',))
        self.assertEqual(reuse_session(self.root, self.rel, **reuse)['status'], 'completed')
        with self.assertRaises(ValueError): reuse_session(self.root, self.rel, **{**reuse, 'review_scope':'different'})
        with self.assertRaises(PermissionError): reuse_session(self.root, self.rel, **{**reuse, 'permission_status':'unknown'})
        with self.assertRaises(ValueError): reuse_session(self.root, self.rel, **{**reuse, 'configuration_paths':()})
        (self.root / self.rel / 'method/result.md').write_text('changed')
        with self.assertRaises(ValueError): reuse_session(self.root, self.rel, **reuse)

    def record(self, role, ident, status='supported'):
        artifact = create_artifact(self.root, 'paper.md').to_dict()
        ev = {'schema_version':'1.0','artifact':artifact,'description':'source','locator':'L2-L2'}
        finding = {'schema_version':'1.0','finding_id':ident,'reviewer_role':role,'issue_type':'test',
            'severity':'major','confidence':'medium','verification_status':'potential','source_location':'L2-L2',
            'claim_or_observation':'Claim', 'evidence_location':[ev], 'reasoning':'reason', 'impact':'impact',
            'recommended_action':'check', 'additional_material_required':[], 'verification_method':'inspection',
            'verification_limitations':'not verified'}
        return {'finding':finding, 'manuscript_hash':artifact['sha256'], 'adjudication_status':status,
                'unresolved_questions':['question']}

    def test_explicit_dedup_preserves_sources_and_conflict(self):
        a=self.record('review_method','m'); b=self.record('review_consistency','c','unsupported')
        result=aggregate_findings(self.root,'paper.md',[a,b],duplicate_groups=[['review_method:m','review_consistency:c']])
        row=result['findings'][0]
        self.assertEqual(len(row['source_findings']),2)
        self.assertEqual(row['adjudication_status'],'unresolved')
        self.assertEqual(len(row['source_finding_ids']),2)
        self.assertEqual(len(aggregate_findings(self.root,'paper.md',[a,b])['findings']),2)

    def test_reject_invalid_finding_evidence_and_hash(self):
        rec=self.record('review_method','m')
        rec['manuscript_hash']='0'*64
        with self.assertRaises(ValueError): aggregate_findings(self.root,'paper.md',[rec])
        rec=self.record('review_method','m')
        rec['finding']['evidence_location'][0]['locator']='L99-L99'
        with self.assertRaises(ValueError): aggregate_findings(self.root,'paper.md',[rec])
        rec=self.record('review_method','m')
        rec['finding']['evidence_location'][0]['artifact']=create_artifact(self.root,'data.csv').to_dict()
        with self.assertRaises(ValueError): aggregate_findings(self.root,'paper.md',[rec])

    def test_inventory_does_not_read_restricted_or_missing(self):
        inv=build_evidence_inventory(self.root,[
            {'artifact_id':'p','artifact_type':'manuscript','status':'available','path':'paper.md'},
            {'artifact_id':'secret','artifact_type':'data','status':'restricted','path':'../do-not-read'},
            {'artifact_id':'f','artifact_type':'figure','status':'unavailable','path':'missing.png'},
            {'artifact_id':'u','artifact_type':'figure','status':'not_checked','path':'paper.md'}])
        self.assertEqual(inv['artifacts'][0]['sha256'], create_artifact(self.root,'paper.md').sha256)
        self.assertTrue(all(x['sha256'] is None and x['access_method']=='not_read' for x in inv['artifacts'][1:]))

    def test_output_from_other_stage_rejected(self):
        self.prepare()
        h=create_artifact(self.root,'paper.md').sha256
        out=self.out('statistics')
        with self.assertRaises(ValueError):
            record_stage(self.root,self.rel,'method',status='completed',execution_mode='inline_skill',output_paths=[out],manuscript_hash=h)

    def test_input_manifest_change_detected(self):
        self.prepare()
        p=self.root/self.rel/'input_manifest.json'
        obj=json.loads(p.read_text());obj['review_scope']='changed';p.write_text(json.dumps(obj))
        with self.assertRaises(ValueError): verify_session(self.root,self.rel)

    def test_output_hash_tampering_detected(self):
        self.prepare();self.done('method')
        (self.root/self.rel/'method/result.md').write_text('changed')
        with self.assertRaises(ValueError): verify_session(self.root,self.rel)

    def test_cached_skills_needing_hash_manifest(self):
        self.args['mode']='method';self.args['configuration_paths']=()
        self.prepare();self.done('method')
        with self.assertRaises(ValueError):
            reuse_session(self.root,self.rel,project_id='p',manuscript_path='paper.md',mode='method',review_scope='all',permission_status='authorized',evidence_paths=('data.csv',))

    def test_reject_unadjudicated_status_and_invalid_sources(self):
        rec=self.record('review_method','m','unknown')
        with self.assertRaises(ValueError): aggregate_findings(self.root,'paper.md',[rec])
        rec=self.record('review_method','m')
        with self.assertRaises(ValueError): aggregate_findings(self.root,'paper.md',[rec],duplicate_groups=[['review_method:m','missing']])
        with self.assertRaises(ValueError): aggregate_findings(self.root,'paper.md',[rec,rec])

    def test_targeted_review_never_auto_resolves(self):
        result=prepare_rereview('a'*64,'b'*64,['old-1'])
        self.assertEqual(result['findings'][0]['status'],'not_checked')
        self.assertEqual(result['findings'][0]['resolution'],'unknown')
        with self.assertRaises(ValueError): prepare_rereview('a'*64,'a'*64,['old-1'])


if __name__ == '__main__': unittest.main()
