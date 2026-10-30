from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,'src')
w=Path('workspace/runs/doublecheck-review-v01'); o=w/'outputs'; fixture=Path('teams/strict_review/fixtures/doublecheck-review-v01')
read=lambda p:json.loads(p.read_text())
ind=read(o/'pass1-normalized/independent_findings.json'); rows=read(o/'review_adjudication.json')['adjudications']; get=lambda role,id:next(x for x in rows if x['original_reviewer']==role and x['source_finding_id']==id)
report=(o/'doublecheck_report.md').read_text(); missed=(o/'missed_issues.md').read_text(); phase=read(o/'phase_manifest.json'); calc=read(o/'local_rmse_verification.json')['record']['calculations'][0]; orig=read(w/'pass1-freeze.json'); norm=read(w/'pass1-normalized-freeze.json'); frozen=read(w/'preoracle-hashes.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def freeze_ok(x):return all(sha(Path(i['path']))==i['sha256'] for i in x['artifacts'])
def same_files(src,dst):return all((dst/p.relative_to(src)).is_file() and sha(p)==sha(dst/p.relative_to(src)) for p in src.rglob('*') if p.is_file())
tests={
'T01_missed_workload':any(x['finding_id']=='DC1-02' and '60' in x['reasoning'] and '100' in x['reasoning'] for x in ind) and 'matched' in missed,
'T02_method_supported':get('review_method','M-01')['adjudication_status']=='supported' and get('review_method','M-01')['supporting_evidence'][0]['locator']=='L15-L15',
'T03_statistics_real_calculation':get('review_statistics','S-01')['adjudication_status']=='supported' and calc['calculation_id']=='RMSE' and abs(calc['recalculated_value']-1.5811388300841898)<1e-12 and calc['reported_value']==1.2,
'T04_different_conditions':get('review_consistency','C-01')['adjudication_status']=='unsupported' and {x['locator'] for x in get('review_consistency','C-01')['contradicting_evidence']}=={'L21-L21','L25-L25'},
'T05_severity_calibration':get('review_method','M-01')['original_severity']=='major' and get('review_consistency','C-02')['original_severity']=='minor' and get('review_consistency','C-02')['final_severity']=='major',
'T06_split_is_unknown':any(x['issue_type']=='split and reproducibility' and x['verification_status']=='insufficient_information' for x in ind) and 'whether a split occurred is unknown' in report,
'T07_supported_bounded_result':'20% total reduction' in report and not any(x['issue_type']=='total message reduction' for x in ind),
'T08_version_conflict':read(o/'version_conflict_result.json')['status']=='blocked',
'T09_context_limit':phase['execution_mode']=='inline_skill' and phase['independence_status']=='non_blind' and 'not technically enforced' in report,
'T10_input_immutable':all(sha(fixture/n)==sha(w/'inputs'/n) for n in ('manuscript.md','forecast.csv')) and same_files(fixture/'source_reports',w/'sources') and freeze_ok(orig) and freeze_ok(norm),
'T11_preoracle_hashes':all(sha(w/p)==h for p,h in frozen.items()),
}
(o/'postoracle_test_results.json').write_text(json.dumps(tests,indent=2)+'\n');print(json.dumps(tests,indent=2));assert all(tests.values())
