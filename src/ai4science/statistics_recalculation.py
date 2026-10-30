"""Bounded, local CSV calculations for authorized workspace data.

All paths are explicit workspace-relative inputs. These functions read one CSV
and return JSON-serializable evidence; they never write files, run code, or use
the network. Callers are responsible for authorization and recording the API
invocation. Path checks are not a substitute for an OS sandbox, particularly
when an attacker can concurrently replace directories.
"""

import csv
import hashlib
import io
import itertools
import math
import os
import platform
import stat
from pathlib import Path

from .contracts import validate_workspace_path

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 200_000
MAX_PAIRS = 16


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _finite(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be finite')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be numeric and non-missing') from exc
    if not math.isfinite(number):
        raise ValueError(f'{name} must be finite')
    return number


def _read_csv(root, path, columns, authorized_data_paths):
    _text(path, 'source_data')
    if not isinstance(authorized_data_paths, (list, tuple)) or not authorized_data_paths:
        raise ValueError('explicit authorized_data_paths are required')
    if path not in authorized_data_paths:
        raise ValueError('source_data is not explicitly authorized')
    if not path.lower().endswith('.csv'):
        raise ValueError('only CSV input is supported')
    if len(set(columns)) != len(columns):
        raise ValueError('required columns must be distinct')
    for column in columns:
        _text(column, 'column')
    resolved = validate_workspace_path(Path(root), path, must_exist=True)
    # Refuse every symlink component, even links resolving back inside the root.
    # A concurrent directory replacement remains a TOCTOU risk: use an OS sandbox.
    component = Path(root).resolve(strict=True)
    for part in path.split('/'):
        component = component / part
        if component.is_symlink():
            raise ValueError('symlink input paths are not permitted')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(resolved, flags)
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError('input must be a regular file')
        if file_stat.st_nlink != 1:
            raise ValueError('hard-linked input is not permitted')
        if file_stat.st_size > MAX_BYTES:
            raise ValueError(f'input exceeds {MAX_BYTES} byte limit')
        with os.fdopen(fd, 'rb') as stream:
            fd = -1
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('input exceeds byte limit')
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        text = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
        names = reader.fieldnames
        if not names or any(not n or not n.strip() for n in names) or len(names) != len(set(names)):
            raise ValueError('CSV needs unique non-empty headers')
        missing = set(columns) - set(names)
        if missing:
            raise ValueError(f'missing required columns: {sorted(missing)}')
        rows = []
        for row in reader:
            if None in row or any(row[k] is None or not row[k].strip() for k in columns):
                raise ValueError(f'missing or extra fields at CSV line {reader.line_num}')
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise ValueError('row limit exceeded')
        if not rows:
            raise ValueError('CSV has no observations')
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError('invalid UTF-8 CSV') from exc
    return rows, hashlib.sha256(raw).hexdigest()


def _metadata(source_data, digest, operation, parameters):
    script = Path(__file__).resolve()
    return {
        'source_data': source_data, 'source_hash': digest,
        'calculation_script': 'src/ai4science/statistics_recalculation.py',
        'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
        'software_versions': {'python': platform.python_version(), 'dependencies': {}},
        'execution': {'method': 'python_api', 'operation': operation, 'parameters': parameters,
                      'command': None, 'random_seed': None, 'status': 'completed'},
    }


def _comparison(value, reported, tolerance):
    tolerance = _finite(tolerance, 'tolerance')
    if tolerance < 0:
        raise ValueError('tolerance must be nonnegative')
    if reported is None:
        return {'reported_value': None, 'recalculated_value': value, 'difference': None,
                'tolerance': tolerance, 'status': 'not_compared'}
    reported = _finite(reported, 'reported_value')
    diff = value - reported
    if not math.isfinite(diff):
        raise ValueError('difference is non-finite')
    return {'reported_value': reported, 'recalculated_value': value, 'difference': diff,
            'tolerance': tolerance, 'status': 'within_tolerance' if abs(diff) <= tolerance else 'difference_detected'}


def recalculate_forecast(workspace_root, source_data, *, actual_column, prediction_column,
                         metrics, unit, aggregation, authorized_data_paths, reported_values=None, tolerance=0.0):
    """Compute row-weighted MAE/MSE/RMSE/MAPE/sMAPE for explicitly paired rows.

    MAPE = mean(100*abs(error)/abs(actual)); rejects zero actuals. sMAPE =
    mean(200*abs(error)/(abs(actual)+abs(prediction))); rejects both-zero rows.
    No row dropping, unit conversion, window grouping, or implicit averaging
    of per-series metrics is performed. These zero-denominator conventions
    differ from epsilon-based definitions: caller must check the author's
    actual metric definitions, corresponding rows, scales, units,
    normalization and scientific choice of aggregation before comparison.
    """
    _text(unit, 'unit')
    if aggregation != 'mean_over_rows':
        raise ValueError('aggregation must explicitly be mean_over_rows')
    supported = {'MAE', 'MSE', 'RMSE', 'MAPE', 'sMAPE'}
    if not isinstance(metrics, (list, tuple)) or not metrics or len(set(metrics)) != len(metrics) or any(m not in supported for m in metrics):
        raise ValueError('metrics must be unique supported names')
    reported_values = {} if reported_values is None else reported_values
    if not isinstance(reported_values, dict) or set(reported_values) - set(metrics):
        raise ValueError('reported_values keys must be requested metrics')
    rows, digest = _read_csv(workspace_root, source_data, [actual_column, prediction_column], authorized_data_paths)
    actual = [_finite(row[actual_column], f'{actual_column} row {i+2}') for i, row in enumerate(rows)]
    predicted = [_finite(row[prediction_column], f'{prediction_column} row {i+2}') for i, row in enumerate(rows)]
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    if any(not math.isfinite(x) for x in errors):
        raise ValueError('error overflow')
    if 'MAPE' in metrics and any(a == 0 for a in actual):
        raise ValueError('MAPE undefined when an actual value is zero')
    if 'sMAPE' in metrics and any(a == 0 and p == 0 for a, p in zip(actual, predicted)):
        raise ValueError('sMAPE undefined when actual and prediction are both zero')
    if 'sMAPE' in metrics and any(not math.isfinite(abs(a) + abs(p)) for a, p in zip(actual, predicted)):
        raise ValueError('sMAPE denominator overflow')
    try:
        calculated = {}
        if 'MAE' in metrics:
            calculated['MAE'] = math.fsum(errors) / len(rows)
        if 'MSE' in metrics or 'RMSE' in metrics:
            mse = math.fsum(e * e for e in errors) / len(rows)
            if 'MSE' in metrics:
                calculated['MSE'] = mse
            if 'RMSE' in metrics:
                calculated['RMSE'] = math.sqrt(mse)
        if 'MAPE' in metrics:
            calculated['MAPE'] = math.fsum(100 * (e / abs(a)) for e, a in zip(errors, actual)) / len(rows)
        if 'sMAPE' in metrics:
            calculated['sMAPE'] = math.fsum(200 * (e / (abs(a) + abs(p))) for e, a, p in zip(errors, actual, predicted)) / len(rows)
    except OverflowError as exc:
        raise ValueError('calculation overflow') from exc
    if any(not math.isfinite(v) for v in calculated.values()):
        raise ValueError('non-finite calculation')
    formulas = {'MAE': 'mean(abs(prediction-actual))', 'MSE': 'mean((prediction-actual)^2)',
                'RMSE': 'sqrt(mean((prediction-actual)^2))',
                'MAPE': '100*mean(abs(prediction-actual)/abs(actual))',
                'sMAPE': '200*mean(abs(prediction-actual)/(abs(actual)+abs(prediction)))'}
    params = {'actual_column': actual_column, 'prediction_column': prediction_column,
              'metrics': list(metrics), 'unit': unit, 'aggregation': aggregation,
              'reported_values': reported_values, 'tolerance': tolerance}
    result = _metadata(source_data, digest, 'recalculate_forecast', params)
    result['data_checks'] = {'rows': len(rows), 'missing_values': 0, 'non_finite_values': 0,
                             'actual_range': [min(actual), max(actual)],
                             'prediction_range': [min(predicted), max(predicted)],
                             'outliers': 'not automatically excluded; inspect range and context'}
    result['calculations'] = [dict(calculation_id=m, metric=m, formula_or_method=formulas[m],
                                   unit='percent' if m in ('MAPE', 'sMAPE') else (f'{unit}^2' if m == 'MSE' else unit),
                                   **_comparison(calculated[m], reported_values.get(m), tolerance)) for m in metrics]
    return result


def recalculate_reduction(workspace_root, source_data, *, baseline_column, proposed_column,
                          unit, aggregation, authorized_data_paths, reported_value=None, tolerance=0.0):
    """Percent reduction: 100*(mean(baseline)-mean(proposed))/mean(baseline).

    Values must be non-negative costs, a strictly positive baseline is required,
    and each CSV row must represent matching evaluation conditions. A percentage
    of mean values is not the same as the mean of per-row percentages.
    """
    _text(unit, 'unit')
    if aggregation != 'ratio_of_means':
        raise ValueError('aggregation must explicitly be ratio_of_means')
    rows, digest = _read_csv(workspace_root, source_data, [baseline_column, proposed_column], authorized_data_paths)
    baseline = [_finite(row[baseline_column], baseline_column) for row in rows]
    proposed = [_finite(row[proposed_column], proposed_column) for row in rows]
    if any(v < 0 for v in baseline + proposed):
        raise ValueError('costs must be non-negative')
    try:
        base = math.fsum(baseline) / len(rows)
        prop = math.fsum(proposed) / len(rows)
        if base <= 0:
            raise ValueError('mean baseline denominator must be positive')
        value = 100 * ((base - prop) / base)
    except OverflowError as exc:
        raise ValueError('calculation overflow') from exc
    if not math.isfinite(value):
        raise ValueError('non-finite calculation')
    params = {'baseline_column': baseline_column, 'proposed_column': proposed_column, 'unit': unit,
              'aggregation': aggregation, 'reported_value': reported_value, 'tolerance': tolerance}
    result = _metadata(source_data, digest, 'recalculate_reduction', params)
    result['data_checks'] = {'rows': len(rows), 'missing_values': 0, 'non_finite_values': 0,
                             'baseline_range': [min(baseline), max(baseline)],
                             'proposed_range': [min(proposed), max(proposed)],
                             'outliers': 'not automatically excluded; inspect range and context'}
    result['calculations'] = [dict(calculation_id='reduction', metric='percentage_reduction',
        formula_or_method='100*(mean(baseline)-mean(proposed))/mean(baseline)',
        baseline_mean=base, proposed_mean=prop, baseline_unit=unit, denominator=base, unit='percent',
        **_comparison(value, reported_value, tolerance))]
    return result


def summarize_paired(workspace_root, source_data, *, pair_id_column, baseline_column,
                     proposed_column, lower_is_better, unit, authorized_data_paths):
    """Describe matched observations without inference or independence assumptions.

    Each row is an explicitly paired observation with a unique ID. The caller
    must choose whether a smaller value is favorable. Counts report observed
    directions only; dependent observations are permitted and the result makes
    no claims about statistical significance or population generalization.
    """
    _text(unit, 'unit')
    if type(lower_is_better) is not bool:
        raise ValueError('lower_is_better must be explicitly True or False')
    rows, digest = _read_csv(workspace_root, source_data,
                             [pair_id_column, baseline_column, proposed_column], authorized_data_paths)
    ids = [row[pair_id_column].strip() for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate pair IDs are not allowed')
    baseline = [_finite(row[baseline_column], baseline_column) for row in rows]
    proposed = [_finite(row[proposed_column], proposed_column) for row in rows]
    differences = [p - b for b, p in zip(baseline, proposed)]
    if any(not math.isfinite(x) for x in differences):
        raise ValueError('difference overflow')
    try:
        mean = math.fsum(differences) / len(differences)
    except OverflowError as exc:
        raise ValueError('calculation overflow') from exc
    if not math.isfinite(mean):
        raise ValueError('non-finite calculation')
    improved = sum(d < 0 if lower_is_better else d > 0 for d in differences)
    worsened = sum(d > 0 if lower_is_better else d < 0 for d in differences)
    unchanged = sum(d == 0 for d in differences)
    params = {'pair_id_column': pair_id_column, 'baseline_column': baseline_column,
              'proposed_column': proposed_column, 'lower_is_better': lower_is_better,
              'unit': unit}
    result = _metadata(source_data, digest, 'summarize_paired', params)
    result['data_checks'] = {'rows': len(rows), 'missing_values': 0, 'non_finite_values': 0,
                             'duplicate_pair_ids': 0}
    result['calculation'] = {
        'metric': 'paired_difference_summary', 'n_pairs': len(rows), 'unit': unit,
        'formula_or_method': 'each difference = proposed - baseline; summarize all rows',
        'min_proposed_minus_baseline': min(differences),
        'max_proposed_minus_baseline': max(differences),
        'mean_proposed_minus_baseline': mean,
        'improved_count': improved, 'worsened_count': worsened, 'unchanged_count': unchanged,
        'lower_is_better': lower_is_better,
        'interpretation': 'descriptive observations only; no inference or independence assumption',
    }
    return result


def paired_sign_flip(workspace_root, source_data, *, pair_id_column, baseline_column, proposed_column,
                     independent_units_confirmed, exchangeability_confirmed, unit, authorized_data_paths):
    """Exact two-sided paired sign-flip test, enumerating at most 2**16 flips.

    Caller must verify that rows are independent experimental units (not windows,
    agents sharing a run, or repeated measurements) and that differences are
    sign-exchangeable under the null. The software cannot establish those facts.
    The p value is the fraction of permutations with |mean difference| at least
    as large as observed; no randomization or effect-size interpretation occurs.
    """
    _text(unit, 'unit')
    if independent_units_confirmed is not True:
        raise ValueError('independent experimental units must be explicitly confirmed')
    if exchangeability_confirmed is not True:
        raise ValueError('sign-exchangeability under the null must be explicitly confirmed')
    rows, digest = _read_csv(workspace_root, source_data, [pair_id_column, baseline_column, proposed_column], authorized_data_paths)
    if not 2 <= len(rows) <= MAX_PAIRS:
        raise ValueError(f'paired test requires 2 to {MAX_PAIRS} independent pairs')
    ids = [row[pair_id_column].strip() for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate pair IDs are not independent pairs')
    baseline = [_finite(row[baseline_column], baseline_column) for row in rows]
    proposed = [_finite(row[proposed_column], proposed_column) for row in rows]
    differences = [p - b for b, p in zip(baseline, proposed)]
    if any(not math.isfinite(x) for x in differences):
        raise ValueError('difference overflow')
    try:
        observed_sum = math.fsum(differences)
        if not math.isfinite(observed_sum):
            raise ValueError('sum overflow')
        threshold = abs(observed_sum)
        extreme = 0
        total = 2 ** len(rows)
        for signs in itertools.product((-1, 1), repeat=len(rows)):
            permuted = abs(math.fsum(sign * difference for sign, difference in zip(signs, differences)))
            if permuted >= threshold or math.isclose(permuted, threshold, rel_tol=1e-12, abs_tol=1e-15):
                extreme += 1
    except OverflowError as exc:
        raise ValueError('calculation overflow') from exc
    params = {'pair_id_column': pair_id_column, 'baseline_column': baseline_column,
              'proposed_column': proposed_column, 'independent_units_confirmed': True,
              'exchangeability_confirmed': True, 'unit': unit}
    result = _metadata(source_data, digest, 'paired_sign_flip', params)
    result['calculation'] = {'metric': 'paired_sign_flip', 'n_pairs': len(rows),
        'mean_proposed_minus_baseline': observed_sum / len(rows), 'unit': unit,
        'p_two_sided': extreme / total, 'extreme_permutations': extreme, 'total_permutations': total,
        'formula_or_method': 'enumerate all pairwise sign flips; P(abs(sum)>=abs(observed sum))',
        'numerical_tie_policy': 'isclose(rel_tol=1e-12, abs_tol=1e-15) counts near ties as extreme',
        'assumptions': ['independent experimental units', 'sign-exchangeability under null'],
        'independence_evidence': 'caller declaration only; not verified by software',
        'exchangeability_evidence': 'caller declaration only; not verified by software',
        'pair_differences': [{'pair_id': identifier, 'difference': diff} for identifier, diff in zip(ids, differences)]}
    return result
