"""Acceptance checks for the saved synthetic review, not scientific or runtime proof."""
import hashlib
import json
import re
import subprocess
import unittest
from collections import Counter
from pathlib import Path

from ai4science.contracts import ExecutionRequest
from ai4science.paper_terminology_validation import validate_glossary_data, validate_terminology_run
from ai4science.terminology_inventory import count_terms

ROOT = Path(__file__).resolve().parents[1] / 'workspace'
FIXTURE = ROOT / 'paper-terminology-v0.1-fixture'
RUN = FIXTURE / 'run-01'
MANUSCRIPT = 'paper-terminology-v0.1-fixture/manuscript.md'
PRIOR = 'paper-terminology-v0.1-fixture/prior_glossary.yaml'
INPUT_HASH = 'c339f56ab7f085348c3bc2c057083129d858a1b68b8a5a7ff753f2f48b36dc1c'
PRIOR_HASH = 'd887a5bb46d15984f87436e87ba039cda9a044da353d50b20e5e6c74de2a94b2'


def safe_yaml(path):
    result = subprocess.run(['ruby', '-rjson', '-ryaml', '-e',
                             'print JSON.generate(YAML.safe_load(File.read(ARGV.fetch(0)), permitted_classes: [], permitted_symbols: [], aliases: false))',
                             str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TerminologyExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = ExecutionRequest.from_dict(json.loads((RUN / 'execution_request.json').read_text(encoding='utf-8')))
        cls.changes = json.loads((RUN / 'terminology_changes.json').read_text(encoding='utf-8'))
        cls.prior = safe_yaml(ROOT / PRIOR)
        cls.glossary = safe_yaml(RUN / 'terminology_glossary.yaml')
        cls.report = (RUN / 'terminology_report.md').read_text(encoding='utf-8')
        cls.handoff = (RUN / 'language_handoff.md').read_text(encoding='utf-8')

    def test_execution_request_inputs_and_required_outputs(self):
        before = {MANUSCRIPT: digest(ROOT / MANUSCRIPT), PRIOR: digest(ROOT / PRIOR)}
        self.assertEqual({MANUSCRIPT: INPUT_HASH, PRIOR: PRIOR_HASH}, before)
        self.request.validate(ROOT)
        self.assertEqual(before, {item.path: item.sha256 for item in self.request.task.input_artifacts})
        self.assertEqual(self.request.task.task_id, self.changes['task_id'])
        self.assertEqual({'terminology_report.md', 'terminology_glossary.yaml', 'terminology_changes.json', 'language_handoff.md'},
                         {Path(item).name for item in self.request.task.output_artifacts})
        for item in self.request.task.output_artifacts:
            self.assertTrue((ROOT / item).is_file())
            self.assertGreater((ROOT / item).stat().st_size, 0)
        self.assertEqual([], validate_terminology_run(ROOT, MANUSCRIPT, 'paper-terminology-v0.1-fixture/run-01/terminology_changes.json'))
        self.assertEqual([], validate_glossary_data(ROOT, MANUSCRIPT, self.glossary))
        self.assertEqual(before, {path: digest(ROOT / path) for path in before})

    def test_approved_prior_is_preserved_and_explicitly_simulated(self):
        self.assertEqual({'path': PRIOR, 'sha256': PRIOR_HASH}, self.glossary['prior_glossary'])
        self.assertIn('simulat', self.prior['fixture_notice'].lower())
        self.assertIn('no real person approved', self.prior['fixture_notice'].lower())
        prior_entries = {entry['canonical_term']: entry for entry in self.prior['terms']}
        actual_entries = {entry['canonical_term']: entry for entry in self.glossary['terms']}
        self.assertTrue(prior_entries)
        for canonical, entry in prior_entries.items():
            self.assertEqual('approved', entry['approval_status'])
            self.assertEqual(entry, actual_entries[canonical])
        for canonical in actual_entries.keys() - prior_entries.keys():
            self.assertEqual('proposed', actual_entries[canonical]['approval_status'])
        self.assertIn('模拟', self.report)
        self.assertIn('模拟', self.handoff)

    def test_every_variant_occurrence_matches_literal_inventory(self):
        for entry in self.glossary['terms']:
            with self.subTest(term=entry['canonical_term']):
                variants = entry['observed_variants']
                self.assertEqual(len(variants), len(set(variants)))
                inventory = count_terms(ROOT, MANUSCRIPT, variants)
                expected = Counter((item['term'], occurrence['line'])
                                   for item in inventory['terms'] for occurrence in item['occurrences'])
                recorded = Counter((location['term'], location['line']) for location in entry['occurrence_locations'])
                self.assertEqual(expected, recorded)
                self.assertEqual(sum(expected.values()), entry['occurrences'])

    def test_required_findings_symbol_gcf_and_language_handoff(self):
        changes = self.changes['changes']
        self.assertTrue(all(item['status'] == 'proposed' for item in changes))
        by_line = {}
        for item in changes:
            by_line.setdefault(item['location']['start_line'], []).append(item)
            self.assertRegex(self.report, rf'\b{re.escape(item["issue_id"])}\b')
        self.assertTrue({11, 13, 15, 21, 23, 27}.issubset(by_line))
        symbol = next(item for item in by_line[21] if item['original_term'] == r'\lambda')
        self.assertEqual('high', symbol['semantic_risk'])
        self.assertIs(symbol['approval_required'], True)
        self.assertIsNone(symbol['suggested_term'])
        self.assertIn('19', symbol['reason'])
        gcf = next(item for item in by_line[15] if item['original_term'] == 'GCF')
        self.assertIsNone(gcf['suggested_term'])
        entry = next(item for item in self.glossary['terms'] if item['canonical_term'] == 'GCF')
        self.assertIsNone(entry['definition'])
        self.assertIsNone(entry['abbreviation'])
        for text in ('Horizon Mapper', 'MAS', 'Agent Network', 'GCF', r'\lambda', 'MAE', 'AAE'):
            self.assertIn(text, self.handoff)
        self.assertIn('不得', self.handoff)
        self.assertIn('不授权修改稿件', self.handoff)
        self.assertIn(digest(RUN / 'terminology_glossary.yaml'), self.handoff)


if __name__ == '__main__':
    unittest.main()
