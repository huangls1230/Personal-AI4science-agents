"""Deterministic numeric and authorization regression tests, no network."""
import hashlib
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai4science.statistics_recalculation import (
    recalculate_forecast, recalculate_reduction, paired_sign_flip, summarize_paired,
)


class StatisticalCalculationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.csv'
        self.source.write_text('actual,predicted,base,proposed,id\n1,2,100,80,a\n2,0,200,120,b\n3,4,100,80,c\n', encoding='utf-8')
        self.auth = ['input.csv']

    def tearDown(self):
        self.tmp.cleanup()

    def forecast(self, **kw):
        defaults = dict(actual_column='actual', prediction_column='predicted', metrics=['MAE', 'RMSE'],
                        unit='seconds', aggregation='mean_over_rows', authorized_data_paths=self.auth)
        defaults.update(kw)
        return recalculate_forecast(self.root, 'input.csv', **defaults)

    def test_metrics_and_independent_expected_values(self):
        before = self.source.read_bytes()
        result = self.forecast(metrics=['MAE', 'MSE', 'RMSE', 'MAPE', 'sMAPE'],
                               reported_values={'MAE': 4/3, 'RMSE': 9}, tolerance=1e-9)
        values = {c['metric']: c for c in result['calculations']}
        # Errors 1, 2, 1; ratio sums are 1 + 1 + 1/3 and 1/3 + 1 + 1/7.
        self.assertAlmostEqual(values['MAE']['recalculated_value'], 4/3)
        self.assertAlmostEqual(values['MSE']['recalculated_value'], 2)
        self.assertAlmostEqual(values['RMSE']['recalculated_value'], math.sqrt(2))
        self.assertAlmostEqual(values['MAPE']['recalculated_value'], 700/9)
        self.assertAlmostEqual(values['sMAPE']['recalculated_value'], 200*(1/3 + 1 + 1/7)/3)
        self.assertEqual(values['MAE']['status'], 'within_tolerance')
        self.assertEqual(values['RMSE']['status'], 'difference_detected')
        self.assertEqual(result['source_hash'], hashlib.sha256(before).hexdigest())
        self.assertEqual(self.source.read_bytes(), before)

    def test_ratio_of_means_has_correct_denominator(self):
        result = recalculate_reduction(self.root, 'input.csv', baseline_column='base',
            proposed_column='proposed', unit='messages', aggregation='ratio_of_means',
            authorized_data_paths=self.auth, reported_value=30, tolerance=1e-9)
        item = result['calculations'][0]
        self.assertAlmostEqual(item['baseline_mean'], 400/3)
        self.assertAlmostEqual(item['proposed_mean'], 280/3)
        self.assertAlmostEqual(item['recalculated_value'], 30)
        self.assertEqual(item['status'], 'within_tolerance')

    def test_paired_sign_flip_exact_and_claim_limit(self):
        # Differences: -20, -80, -20; all negative: 2/8 sign assignments as extreme.
        result = paired_sign_flip(self.root, 'input.csv', pair_id_column='id', baseline_column='base',
            proposed_column='proposed', unit='messages', independent_units_confirmed=True,
            exchangeability_confirmed=True, authorized_data_paths=self.auth)
        self.assertEqual(result['calculation']['p_two_sided'], .25)
        self.assertAlmostEqual(result['calculation']['mean_proposed_minus_baseline'], -40)
        self.assertIn('caller declaration', result['calculation']['independence_evidence'])
        self.assertIn('caller declaration', result['calculation']['exchangeability_evidence'])
        self.assertIs(result['execution']['parameters']['exchangeability_confirmed'], True)
        with self.assertRaises(ValueError):
            paired_sign_flip(self.root, 'input.csv', pair_id_column='id', baseline_column='base',
                proposed_column='proposed', unit='messages', independent_units_confirmed=False,
                exchangeability_confirmed=True, authorized_data_paths=self.auth)
        with self.assertRaisesRegex(ValueError, 'sign-exchangeability'):
            paired_sign_flip(self.root, 'input.csv', pair_id_column='id', baseline_column='base',
                proposed_column='proposed', unit='messages', independent_units_confirmed=True,
                exchangeability_confirmed=False, authorized_data_paths=self.auth)

    def test_paired_summary_describes_directions_without_inference_or_writes(self):
        self.source.write_text('id,base,proposed\na,10,7\nb,10,12\nc,5,5\nd,8,4\n', encoding='utf-8')
        before = self.source.read_bytes()
        before_files = set(self.root.iterdir())
        args = dict(pair_id_column='id', baseline_column='base', proposed_column='proposed',
                    unit='seconds', authorized_data_paths=self.auth)
        with patch('socket.socket', side_effect=AssertionError('network access forbidden')):
            result = summarize_paired(self.root, 'input.csv', lower_is_better=True, **args)
            inverse = summarize_paired(self.root, 'input.csv', lower_is_better=False, **args)
        item = result['calculation']
        self.assertEqual(item['n_pairs'], 4)
        self.assertEqual(item['min_proposed_minus_baseline'], -4)
        self.assertEqual(item['max_proposed_minus_baseline'], 2)
        self.assertAlmostEqual(item['mean_proposed_minus_baseline'], -5/4)
        self.assertEqual((item['improved_count'], item['worsened_count'], item['unchanged_count']), (2, 1, 1))
        self.assertEqual((inverse['calculation']['improved_count'], inverse['calculation']['worsened_count']), (1, 2))
        self.assertNotIn('p_two_sided', item)
        self.assertIn('no inference', item['interpretation'])
        self.assertEqual(result['source_hash'], hashlib.sha256(before).hexdigest())
        self.assertEqual(result['execution']['parameters']['lower_is_better'], True)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(set(self.root.iterdir()), before_files)

    def test_paired_summary_rejects_missing_duplicate_invalid_and_unauthorized(self):
        args = dict(pair_id_column='id', baseline_column='base', proposed_column='proposed',
                    unit='seconds', authorized_data_paths=self.auth, lower_is_better=True)
        for data in ('id,base,proposed\na,1,2\na,3,4\n', 'id,base,proposed\n,1,2\n',
                     'id,base,proposed\na,1,\n', 'id,base,proposed\na,nan,2\n',
                     'id,base,proposed\na,1,inf\n'):
            with self.subTest(data=data):
                self.source.write_text(data, encoding='utf-8')
                with self.assertRaises(ValueError):
                    summarize_paired(self.root, 'input.csv', **args)
        self.source.write_text('id,base,proposed\na,1,2\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            summarize_paired(self.root, 'input.csv', **dict(args, lower_is_better=1))
        with self.assertRaises(ValueError):
            summarize_paired(self.root, 'input.csv', **dict(args, authorized_data_paths=['other.csv']))

    def test_missing_numeric_nonfinite_bad_schema_fail(self):
        for data in ['actual,predicted\n1,\n', 'actual,predicted\n1,nan\n',
                     'actual,predicted\n1,inf\n', 'actual,predicted\n1,hello\n',
                     'actual,actual\n1,2\n', 'actual,predicted\n1,2,3\n']:
            with self.subTest(data=data):
                self.source.write_text(data)
                with self.assertRaises(ValueError):
                    self.forecast()

    def test_zero_denominators_and_formula_choice(self):
        self.source.write_text('actual,predicted\n0,1\n')
        with self.assertRaises(ValueError):
            self.forecast(metrics=['MAPE'])
        self.source.write_text('actual,predicted\n0,0\n')
        with self.assertRaises(ValueError):
            self.forecast(metrics=['sMAPE'])
        self.source.write_text('base,proposed\n0,1\n')
        with self.assertRaises(ValueError):
            recalculate_reduction(self.root, 'input.csv', baseline_column='base', proposed_column='proposed',
                unit='ms', aggregation='ratio_of_means', authorized_data_paths=self.auth)
        with self.assertRaises(ValueError):
            self.forecast(aggregation='unknown')

    def test_reject_unapproved_outside_symlink_and_hardlink(self):
        with self.assertRaises(ValueError):
            self.forecast(authorized_data_paths=['other.csv'])
        with self.assertRaises(ValueError):
            recalculate_forecast(self.root, '../outside.csv', actual_column='a', prediction_column='b',
                metrics=['MAE'], unit='s', aggregation='mean_over_rows', authorized_data_paths=['../outside.csv'])
        link = self.root / 'link.csv'
        link.symlink_to(self.source)
        with self.assertRaises(ValueError):
            recalculate_forecast(self.root, 'link.csv', actual_column='actual', prediction_column='predicted',
                metrics=['MAE'], unit='s', aggregation='mean_over_rows', authorized_data_paths=['link.csv'])
        outside = self.root.parent / 'not-authorized-statistics.csv'
        external_link = self.root / 'outside.csv'
        external_link.symlink_to(outside)
        with self.assertRaises(ValueError):
            recalculate_forecast(self.root, 'outside.csv', actual_column='actual', prediction_column='predicted',
                metrics=['MAE'], unit='s', aggregation='mean_over_rows', authorized_data_paths=['outside.csv'])
        os.link(self.source, self.root / 'hard.csv')
        with self.assertRaises(ValueError):
            self.forecast()

    def test_duplicate_pairs_invalid_tolerance_and_no_implicit_code(self):
        self.source.write_text('id,base,proposed\na,1,2\na,2,3\n')
        with self.assertRaises(ValueError):
            paired_sign_flip(self.root, 'input.csv', pair_id_column='id', baseline_column='base',
                proposed_column='proposed', unit='s', independent_units_confirmed=True,
                exchangeability_confirmed=True, authorized_data_paths=self.auth)
        self.source.write_text('actual,predicted\n1,2\n')
        with self.assertRaises(ValueError):
            self.forecast(tolerance=-1)
        with self.assertRaises(ValueError):
            self.forecast(tolerance=float('nan'))
        with self.assertRaises(ValueError):
            self.forecast(metrics=['exec'])

    def test_rejects_pickle_and_code_like_numeric_data_without_execution(self):
        pickle_path = self.root / 'payload.pkl'
        pickle_path.write_bytes(b'\x80\x04untrusted-pickle-payload')
        marker = self.root / 'must-not-exist'
        self.source.write_text(
            "actual,predicted\n1,__import__('os').system('touch " + str(marker) + "')\n",
            encoding='utf-8',
        )
        pickle_before = pickle_path.read_bytes()
        csv_before = self.source.read_bytes()
        with patch('pickle.load', side_effect=AssertionError('pickle load forbidden')), \
             patch('pickle.loads', side_effect=AssertionError('pickle loads forbidden')), \
             patch('subprocess.Popen', side_effect=AssertionError('subprocess forbidden')), \
             patch('subprocess.run', side_effect=AssertionError('subprocess forbidden')), \
             patch('os.system', side_effect=AssertionError('shell execution forbidden')), \
             patch('socket.socket', side_effect=AssertionError('network forbidden')):
            with self.assertRaisesRegex(ValueError, 'only CSV'):
                recalculate_forecast(self.root, 'payload.pkl', actual_column='actual',
                    prediction_column='predicted', metrics=['MAE'], unit='s',
                    aggregation='mean_over_rows', authorized_data_paths=['payload.pkl'])
            with self.assertRaisesRegex(ValueError, 'numeric'):
                self.forecast()
        self.assertEqual(pickle_path.read_bytes(), pickle_before)
        self.assertEqual(self.source.read_bytes(), csv_before)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
