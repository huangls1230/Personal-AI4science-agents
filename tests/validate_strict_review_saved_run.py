"""Verify the saved synthetic integration run; does not rerun model reviews.

Run from repository root with PYTHONPATH=src. The controlled Doublecheck case
and report-only statistics run must exist in workspace; skips are explicit.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import json
from ai4science.strict_review_workflow import (route, prepare_session, verify_session,
    record_stage, reuse_session, prepare_rereview)
from ai4science.method_review_validation import validate_method_review_run
from ai4science.statistics_review_validation import validate_statistics_review_run
from ai4science.consistency_review_validation import validate_consistency_review_run
from ai4science.doublecheck_review_validation import validate_doublecheck_review_run
from ai4science.contracts import ResearchTask, ExecutionResult

w=Path('workspace'); s='projects/strict-review-synthetic/reviews/full-v01'; b=w/s
read=lambda p:json.loads(p.read_text())
state=verify_session(w,s);snap=s+'/manuscript_snapshot.md'; data='projects/strict-review-synthetic/inputs/forecast.csv';h=state['config']['snapshot']['sha256']
method=s+'/method/';stats=s+'/statistics/';cons=s+'/consistency/';dc=s+'/doublecheck/'
me=validate_method_review_run(w,snap,*[method+n for n in ('method_findings.json','assumptions_register.yaml','method_review.md')])
se=validate_statistics_review_run(w,snap,*[stats+n for n in ('statistics_findings.json','claim_evaluations.json','recalculation_report.json','reproduction_manifest.json','statistics_review.md')],evidence_paths=(data,),trusted_calculation_scripts=(Path('src/ai4science/statistics_recalculation.py').resolve(),))
ce=validate_consistency_review_run(w,snap,*[cons+n for n in ('consistency_findings.json','claim_evidence_matrix.json','evidence_inventory.json','cross_reference_audit.json','visual_review_manifest.json','consistency_review.md')],evidence_paths=(data,))
de=validate_doublecheck_review_run(w,snap,*[dc+n for n in ('independent_review.md','scientific_argument_map.md','independent_findings.json','review_adjudication.json','missed_issues.md','doublecheck_report.md','phase_manifest.json')],source_finding_paths=(method+'method_findings.json',stats+'statistics_findings.json',cons+'consistency_findings.json'),evidence_paths=(data,stats+'recalculation_report.json'))
review=read(b/'final_validation/aggregated_findings.json');report=(b/'final_validation/strict_review_report.md').read_text();vis=read(b/'consistency/visual_review_manifest.json'); rec=read(b/'statistics/recalculation_report.json'); decisions=read(b/'doublecheck/review_adjudication.json')['adjudications']
controlled=w/'runs/doublecheck-review-v01/outputs';oldfind=read(controlled/'pass1-normalized/independent_findings.json');olddec=read(controlled/'review_adjudication.json')['adjudications'];oldmiss=(controlled/'missed_issues.md').read_text()
ro=w/'runs/statistics-review-v01/report-only/recalculation_report.json'; oldstats=read(ro)
configs=read(w/'projects/strict-review-synthetic/inputs/configuration.json')['files']; config_match=all(sha256(Path(p).read_bytes()).hexdigest()==v for p,v in configs.items())
cache=reuse_session(w,s,project_id='strict-review-synthetic',manuscript_path='projects/strict-review-synthetic/inputs/manuscript.md',mode='full',review_scope='synthetic complete scientific review',permission_status='authorized',review_policy='synthetic engineering test',evidence_paths=(data,),configuration_paths=('projects/strict-review-synthetic/inputs/configuration.json',))
with TemporaryDirectory() as tmp:
 root=Path(tmp).resolve();(root/'manuscript.md').write_text('# Synthetic\n')
 p=prepare_session(root,project_id='partial',review_session_id='run',manuscript_path='manuscript.md',mode='full',review_scope='test',permission_status='authorized');r=p.relative_to(root).as_posix(); hh=verify_session(root,r)['config']['snapshot']['sha256']
 (p/'method'/'result.md').write_text('# Success\n');record_stage(root,r,'method',status='completed',execution_mode='inline_skill',output_paths=(r+'/method/result.md',),manuscript_hash=hh)
 partial=record_stage(root,r,'statistics',status='failed',execution_mode='inline_skill',errors=('synthetic failure',),manuscript_hash=hh)
 partial_ok=partial['status']=='partial' and (p/'method'/'result.md').exists()
changed=prepare_rereview(h,'a'*64,['M01']); sourcefind=read(b/'method/method_findings.json'); ind=read(b/'doublecheck/independent_findings.json')
tests={
'01_method_only_routing':route('method')==('method',),
'02_statistics_only_routing':route('statistics')==('statistics',),
'03_consistency_only_routing':route('consistency')==('consistency',),
'04_full_workflow':state['status']=='completed' and all(v['status']=='completed' for v in state['stages'].values()) and not(me+se+ce+de),
'05_real_calculation_record':any(x.get('execution',{}).get('status')=='completed' and x.get('calculations') for x in rec['records']),
'06_no_data_report_only':oldstats['mode']=='report_only' and not oldstats['records'] and bool(oldstats['reason']),
'07_visual_not_performed':vis.get('visual_review_status')=='not_performed' and not vis['figures'],
'08_controlled_missing_issue':any(x['finding_id']=='DC1-02' for x in oldfind) and 'DC1-02' in oldmiss,
'09_controlled_false_major_rejected':any(x['source_finding_id']=='C-01' and x['adjudication_status']=='unsupported' and x['original_severity']=='major' for x in olddec),
'10_independent_context_limit':state['blind_review'] is False and read(b/'doublecheck/pass1_freeze.json')['blind_review'] is False,
'11_verification_states':{'verified','potential','insufficient_information'} <= {x['verification_status'] for x in sourcefind},
'12_version_conflict':read(controlled/'version_conflict_result.json')['status']=='blocked',
'13_explicit_dedup_with_provenance':any(len(x['source_finding_ids'])>1 and len(x['source_findings'])==len(x['source_finding_ids']) for x in review['findings']),
'14_failed_stage_partial':partial_ok,
'15_original_unchanged':sha256((w/state['config']['manuscript']['path']).read_bytes()).hexdigest()==h,
'16_complete_report':all(x in report for x in ('Executive summary','Research strengths','Critical issue','Major issues','Review limitations')),
'17_reuse_revalidated':cache['status']=='completed' and config_match,
'18_rereview_not_auto_resolved':changed['findings'][0]['status']=='not_checked' and changed['findings'][0]['resolution']=='unknown',
'19_execution_mode_honesty':all(v['execution_mode']=='inline_skill' for k,v in state['stages'].items() if k!='final_validation') and state['stages']['final_validation']['execution_mode']=='deterministic' and state['blind_review'] is False,
'20_applicable_contracts':not(me+se+ce+de) and len({x['finding_id'] for x in review['findings']})==len(review['findings']) and ResearchTask.from_dict(read(b/'final_validation/research_task.json')).validate(w) is None and ExecutionResult.from_dict(read(b/'final_validation/execution_result.json')).validate(w) is None,
}
print(json.dumps(tests,indent=2)); assert all(tests.values())
