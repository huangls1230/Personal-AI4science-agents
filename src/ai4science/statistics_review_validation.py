"""Read-only structural/provenance checks for statistical-review artifacts.

This checks declared records against authorized file identities and hashes. It does
not execute code, prove an execution occurred, establish a causal relationship,
or establish that any numerical result is correct or a study was reproduced.
Workspace checks are not a sandbox against concurrent filesystem changes.
"""
import hashlib
import json
import math
import re
from pathlib import Path

from .contracts import ArtifactReference, create_artifact, validate_workspace_path
from .method_review_validation import _SCHEMA, _check_schema_keywords, _schema_valid, _line_range

_CLAIM_STATES = {'verified', 'contradicted', 'partially_supported', 'insufficient_information', 'not_checked'}
_REPO = Path(__file__).resolve().parents[2]


def _text(x):
    return isinstance(x, str) and bool(x.strip())


def _number(x):
    return type(x) in (int, float) and math.isfinite(x)


def validate_statistics_review_run(workspace_root, manuscript_path, findings_path, claims_path,
                                   recalculation_path, manifest_path, report_path, *,
                                   evidence_paths=(), allowed_line_ranges=None,
                                   trusted_calculation_scripts=()):
    """Return validation errors for existing files without writing or executing.

    Only manuscript_path and explicitly authorized evidence_paths may be used as
    evidence. Calculation scripts must be explicitly trusted absolute paths. A
    successful return is structural and does not establish scientific validity or
    independently attest claimed execution; full reproduction requires separate
    human examination and is not accepted automatically.
    """
    errors = []
    try:
        inputs = [manuscript_path, *evidence_paths]
        outputs = [findings_path, claims_path, recalculation_path, manifest_path, report_path]
        resolved = [validate_workspace_path(workspace_root, p, must_exist=True) for p in inputs + outputs]
        for i, out in enumerate(resolved[len(inputs):]):
            if any(out == p or out.samefile(p) for p in resolved[:len(inputs)+i]):
                return ['output paths must be independent of all inputs and other outputs']
        allowed = dict(zip(inputs, resolved[:len(inputs)]))
        source_lines = resolved[0].read_text(encoding='utf-8').splitlines()
        if allowed_line_ranges is not None and any(
            not isinstance(r, (tuple, list)) or len(r) != 2 or type(r[0]) is not int or
            type(r[1]) is not int or not 1 <= r[0] <= r[1] <= len(source_lines)
            for r in allowed_line_ranges
        ):
            return ['allowed_line_ranges must be valid manuscript ranges']
        schema = json.loads(_SCHEMA.read_text(encoding='utf-8'))
        _check_schema_keywords(schema)
        findings, claims, recalc, manifest = [json.loads(p.read_text(encoding='utf-8')) for p in resolved[-5:-1]]
        report = resolved[-1].read_text(encoding='utf-8')
        trusted = {Path(p).resolve(strict=True) for p in trusted_calculation_scripts if Path(p).is_absolute()}
        if any(out == script or out.samefile(script)
               for out in resolved[len(inputs):] for script in trusted):
            return ['output paths must be independent of trusted scripts']
    except (OSError, ValueError, UnicodeError, RecursionError, TypeError):
        return ['invalid, unreadable or unauthorized path, schema or JSON']
    if not report.strip() or not re.search(r'^#{1,6}\s+\S', report, re.MULTILINE):
        errors.append('report must contain a Markdown heading and text')

    def evidence_check(refs, label):
        if not isinstance(refs, list):
            errors.append(f'{label} evidence_location must be an array')
            return
        for ev in refs:
            try:
                if not isinstance(ev, dict) or set(ev) != {'schema_version', 'artifact', 'description', 'locator'} or ev['schema_version'] != '1.0' or not _text(ev['description']):
                    raise ValueError('invalid evidence')
                ref = ArtifactReference.from_dict(ev['artifact'])
                if ref.path not in allowed:
                    errors.append(f'{label} evidence artifact is not authorized')
                    continue
                if not ref.verify(workspace_root):
                    errors.append(f'{label} evidence sha256 does not match')
                lines = allowed[ref.path].read_text(encoding='utf-8').splitlines()
                source = allowed[ref.path].samefile(resolved[0])
                if not _line_range(ev['locator'], len(lines), allowed_line_ranges if source else None):
                    errors.append(f'{label} evidence locator is outside authorized source scope')
            except (ValueError, OSError, UnicodeError, TypeError, KeyError):
                errors.append(f'{label} evidence is invalid or unreadable')

    if not isinstance(findings, list):
        errors.append('findings must be an array')
        findings = []
    ids = set()
    for index, item in enumerate(findings):
        label = f'findings[{index}]'
        try:
            if not _schema_valid(item, schema, schema):
                errors.append(f'{label} fails Review Finding Schema')
                continue
        except (ValueError, KeyError, TypeError, RecursionError):
            return ['unsupported or invalid Review Finding Schema']
        if item['reviewer_role'] != 'review_statistics':
            errors.append(f'{label} must use review_statistics role')
        if item['finding_id'] in ids:
            errors.append(f'{label} finding_id must be unique')
        ids.add(item['finding_id'])
        if not _line_range(item['source_location'], len(source_lines), allowed_line_ranges):
            errors.append(f'{label} source_location is outside reviewed manuscript scope')
        evidence_check(item['evidence_location'], label)

    if not isinstance(claims, list):
        errors.append('claims must be an array')
        claims = []
    ids = set()
    for i, item in enumerate(claims):
        label = f'claims[{i}]'
        if not isinstance(item, dict) or not {'claim_id', 'source_location', 'claim', 'status', 'evidence_location'} <= item.keys():
            errors.append(f'{label} missing required claim fields')
            continue
        if not _text(item['claim_id']) or not _text(item['claim']) or not isinstance(item['status'], str) or item['status'] not in _CLAIM_STATES:
            errors.append(f'{label} invalid claim fields')
            continue
        if item['claim_id'] in ids:
            errors.append(f'{label} claim_id must be unique')
        ids.add(item['claim_id'])
        if not _line_range(item['source_location'], len(source_lines), allowed_line_ranges):
            errors.append(f'{label} source_location is outside reviewed manuscript scope')
        if item['status'] in {'verified', 'contradicted', 'partially_supported'} and not item['evidence_location']:
            errors.append(f'{label} requires evidence for claimed status')
        evidence_check(item['evidence_location'], label)

    if not isinstance(recalc, dict) or recalc.get('schema_version') != '1.0' or recalc.get('mode') not in ('report_only', 'metric_recalculation') or not isinstance(recalc.get('records'), list):
        errors.append('invalid recalculation report envelope')
        recalc = {'records': []}
    if recalc.get('mode') == 'report_only' and (recalc['records'] or not _text(recalc.get('reason'))):
        errors.append('report_only requires no records and a reason')
    if recalc.get('mode') == 'metric_recalculation' and not recalc['records']:
        errors.append('metric_recalculation requires records')
    if recalc.get('mode') == 'metric_recalculation' and not any(
        isinstance(r, dict) and isinstance(r.get('execution'), dict) and
        r['execution'].get('status') == 'completed' for r in recalc['records']
    ):
        errors.append('metric_recalculation requires a completed record')
    for i, record in enumerate(recalc['records']):
        label = f'records[{i}]'
        if not isinstance(record, dict):
            errors.append(f'{label} invalid record')
            continue
        if record.get('status') == 'not_executed':
            if (any(record.get(k) is not None for k in ('reported_value', 'recalculated_value', 'difference'))
                    or record.get('calculations') or record.get('calculation') or not _text(record.get('reason'))):
                errors.append(f'{label} not_executed must have null numeric values and a reason')
            continue
        try:
            source = record['source_data']
            if source not in evidence_paths:
                errors.append(f'{label} source data is not explicitly authorized')
            elif create_artifact(workspace_root, source).sha256 != record['source_hash']:
                errors.append(f'{label} source hash does not match')
            script_name = record['calculation_script']
            if not isinstance(script_name, str) or Path(script_name).is_absolute() or '..' in Path(script_name).parts:
                raise ValueError('invalid script')
            script = (_REPO / script_name).resolve(strict=True)
            if script not in trusted or not script.is_file():
                errors.append(f'{label} calculation script is not explicitly trusted')
            elif hashlib.sha256(script.read_bytes()).hexdigest() != record['script_sha256']:
                errors.append(f'{label} script hash does not match')
            execution = record['execution']
            if not isinstance(execution, dict) or execution.get('status') != 'completed' or not _text(execution.get('operation')) or not isinstance(execution.get('parameters'), dict):
                errors.append(f'{label} invalid execution metadata')
                continue
            if not isinstance(record['software_versions'], dict) or not _text(record['software_versions'].get('python')):
                errors.append(f'{label} missing software versions')
            if execution.get('operation') == 'summarize_paired':
                summary = record.get('calculation')
                fields = {'metric', 'n_pairs', 'unit', 'formula_or_method',
                          'min_proposed_minus_baseline', 'max_proposed_minus_baseline',
                          'mean_proposed_minus_baseline', 'improved_count', 'worsened_count',
                          'unchanged_count', 'lower_is_better', 'interpretation'}
                if not isinstance(summary, dict) or set(summary) != fields or 'calculations' in record:
                    errors.append(f'{label} invalid descriptive paired summary fields')
                    continue
                n = summary['n_pairs']
                counts = [summary[k] for k in ('improved_count', 'worsened_count', 'unchanged_count')]
                minimum, mean, maximum = (summary[k] for k in
                    ('min_proposed_minus_baseline', 'mean_proposed_minus_baseline', 'max_proposed_minus_baseline'))
                params = execution.get('parameters', {})
                checks = record.get('data_checks', {})
                if (summary['metric'] != 'paired_difference_summary' or type(n) is not int or n < 1
                        or any(type(x) is not int or x < 0 for x in counts)
                        or sum(counts) != n or not isinstance(checks, dict) or checks.get('rows') != n
                        or not _text(summary['unit']) or summary['unit'] != params.get('unit')
                        or type(summary['lower_is_better']) is not bool
                        or summary['lower_is_better'] is not params.get('lower_is_better')
                        or not all(_number(x) for x in (minimum, mean, maximum))
                        or not minimum <= mean <= maximum
                        or not _text(summary['formula_or_method']) or not _text(summary['interpretation'])):
                    errors.append(f'{label} invalid descriptive paired summary values')
                continue
            calculations = record.get('calculations')
            if not isinstance(calculations, list) or not calculations:
                errors.append(f'{label} must contain calculations')
                continue
            for calculation in calculations:
                if not isinstance(calculation, dict) or not all(_text(calculation.get(k)) for k in ('calculation_id', 'metric', 'formula_or_method', 'unit')):
                    errors.append(f'{label} invalid calculation')
                    continue
                rv, value, diff, tol = (calculation.get(k) for k in ('reported_value', 'recalculated_value', 'difference', 'tolerance'))
                if not _number(value) or not _number(tol) or tol < 0:
                    errors.append(f'{label} invalid result or tolerance')
                elif rv is None:
                    if diff is not None or calculation.get('status') != 'not_compared':
                        errors.append(f'{label} unreported value cannot be compared')
                elif not _number(rv) or not _number(diff) or not math.isclose(diff, value-rv, rel_tol=1e-12, abs_tol=1e-12) or calculation.get('status') != ('within_tolerance' if abs(diff) <= tol else 'difference_detected'):
                    errors.append(f'{label} inconsistent comparison')
        except (ValueError, OSError, TypeError, KeyError):
            errors.append(f'{label} invalid source, script or execution record')

    if not isinstance(manifest, dict) or manifest.get('schema_version') != '1.0' or manifest.get('review_level') not in ('A', 'B', 'C') or manifest.get('execution_mode') not in ('inline_skill', 'native_subagent'):
        errors.append('invalid reproduction manifest envelope')
        return errors
    if manifest.get('reproduction_status') != 'not_performed':
        errors.append('experiment reproduction cannot be automatically verified by this validator')
    if not isinstance(manifest.get('executed_commands'), list) or any(not _text(x) for x in manifest['executed_commands']):
        errors.append('manifest executed_commands must be an array of command strings')
    if not isinstance(manifest.get('limitations'), list) or not manifest['limitations'] or any(not _text(x) for x in manifest['limitations']):
        errors.append('manifest limitations must be nonempty')
    if not isinstance(manifest.get('software_versions'), dict) or not _text(manifest['software_versions'].get('python')):
        errors.append('manifest software_versions must include python')
    if not isinstance(manifest.get('input_artifacts'), list):
        errors.append('manifest input_artifacts must be an array')
    else:
        for item in manifest['input_artifacts']:
            try:
                ref = ArtifactReference.from_dict(item)
                if ref.path not in allowed or not ref.verify(workspace_root):
                    errors.append('manifest input artifact is unauthorized or hash differs')
            except (ValueError, OSError, TypeError):
                errors.append('manifest input artifact is invalid')
    return errors
