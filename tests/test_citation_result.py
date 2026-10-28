import copy
import json
import tempfile
import unittest
from pathlib import Path

from ai4science.citation_result import validate_citation_result
from ai4science.citation_metadata import citation_record_from_search
from ai4science.contracts import ExecutionResult, UsageMetrics, create_artifact


class CitationResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'export.bib').write_text('@article{a, title={Example}}\n')
        self.ref = create_artifact(self.root, 'export.bib')
        usage = UsageMetrics()
        execution = ExecutionResult(task_id='citation-1', executor='citation_cli', status='completed',
                                    output_artifacts=(self.ref,), usage_metrics=usage)
        self.result = {
            'schema_version': '1.0', 'task_id': 'citation-1', 'operation': 'export',
            'execution_status': 'completed',
            'affected_records': [citation_record_from_search({'title': 'Example'})],
            'proposed_changes': [], 'applied_changes': [],
            'exported_artifacts': [self.ref.to_dict()], 'verification_results': [],
            'warnings': ['Metadata is not verified'], 'errors': [],
            'usage_metrics': usage.to_dict(), 'execution': execution.to_dict(),
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_envelope_keeps_unknown_usage(self):
        validate_citation_result(self.result, self.root)
        self.assertIsNone(self.result['usage_metrics']['input_tokens'])
        self.assertEqual('unknown', self.result['usage_metrics']['token_measurement'])

    def test_inconsistent_status_errors_and_usage_rejected(self):
        for mutate in (
            lambda r: r.update(execution_status='failed'),
            lambda r: r.update(errors=['request failed']),
            lambda r: r['usage_metrics'].update(model_calls=1),
            lambda r: r.update(task_id='other'),
        ):
            result = copy.deepcopy(self.result)
            mutate(result)
            with self.assertRaises(ValueError):
                validate_citation_result(result, self.root)

    def test_artifact_must_match_execution_and_bytes(self):
        result = copy.deepcopy(self.result)
        result['exported_artifacts'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'referenced'):
            validate_citation_result(result, self.root)
        (self.root / 'export.bib').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            validate_citation_result(self.result, self.root)

    def test_claimed_write_is_rejected(self):
        self.result['applied_changes'] = [{'operation': 'tag'}]
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            validate_citation_result(self.result, self.root)

    def test_schema_and_required_fields(self):
        schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/CitationResult.schema.json').read_text())
        self.assertEqual(set(schema['required']), set(self.result))
        self.result.pop('operation')
        with self.assertRaisesRegex(ValueError, 'exactly'):
            validate_citation_result(self.result, self.root)


if __name__ == '__main__':
    unittest.main()
