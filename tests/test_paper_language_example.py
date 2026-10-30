"""Regression checks on synthetic examples; not proof of science or runtime provenance."""
import hashlib
import json
import unittest
from pathlib import Path

from ai4science.contracts import ExecutionRequest, ExecutionResult
from ai4science.paper_language_validation import validate_language_run, render_language_diff

ROOT = Path(__file__).resolve().parents[1] / 'workspace'
FIXTURE = ROOT / 'paper-language-v0.1-fixture'
MANUSCRIPT = 'paper-language-v0.1-fixture/manuscript.md'
GLOSSARY = 'paper-language-v0.1-fixture/terminology_glossary.yaml'
SOURCE_HASH = 'fa05039c73ebacae4d9f1d76d901521e00d78603ddf703ce91974bf2d45a4501'
GLOSSARY_HASH = 'b9984d7799e7ceb01ab603447cc27ab1085fb40d19a8a17333c568b20baad2a0'
MODES = ('proofreading', 'conservative', 'academic_polishing')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LanguageExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / MANUSCRIPT).read_text(encoding='utf-8')
        # JSON is a YAML subset; this fixture intentionally uses JSON syntax.
        cls.glossary = json.loads((ROOT / GLOSSARY).read_text(encoding='utf-8'))
        cls.runs = {}
        for mode in MODES:
            directory = FIXTURE / f'run-{mode}'
            cls.runs[mode] = {
                'dir': directory,
                'input': json.loads((directory / 'language_input.json').read_text(encoding='utf-8')),
                'request': ExecutionRequest.from_dict(json.loads((directory / 'execution_request.json').read_text(encoding='utf-8'))),
                'result': ExecutionResult.from_dict(json.loads((directory / 'execution_result.json').read_text(encoding='utf-8'))),
                'changes': json.loads((directory / 'language_changes.json').read_text(encoding='utf-8')),
                'edited': (directory / 'manuscript_edited.md').read_text(encoding='utf-8'),
                'report': (directory / 'language_report.md').read_text(encoding='utf-8'),
            }

    def test_contracts_scope_hashes_and_outputs(self):
        expected_hashes = {MANUSCRIPT: SOURCE_HASH, GLOSSARY: GLOSSARY_HASH}
        self.assertEqual(expected_hashes, {path: digest(ROOT / path) for path in expected_hashes})
        self.assertIn('mock approval', self.glossary['fixture_notice'].lower())
        self.assertIn('no real person approved', self.glossary['fixture_notice'].lower())
        for mode, run in self.runs.items():
            with self.subTest(mode=mode):
                request, result, params, changes = (run[k] for k in ('request', 'result', 'input', 'changes'))
                request.validate(ROOT)
                result.validate(ROOT)
                self.assertEqual(expected_hashes, {item.path: item.sha256 for item in request.task.input_artifacts})
                self.assertEqual(request.task.task_id, result.task_id)
                self.assertEqual(request.task.task_id, changes['task_id'])
                self.assertEqual('paper_language', request.executor)
                self.assertEqual('paper_language', result.executor)
                self.assertEqual('completed', result.status)
                self.assertEqual('pending', result.approval_status)
                self.assertEqual('pending', params['author_approval'])
                self.assertIn('synthetic mock', params['glossary_approval_context'].lower())
                self.assertEqual(mode, params['editing_mode'])
                for field in ('project_id', 'editing_mode', 'language_variant', 'editing_scope'):
                    self.assertEqual(params[field], changes[field])
                self.assertEqual('preserve', params['language_variant'])
                self.assertEqual(MANUSCRIPT, params['manuscript_path'])
                self.assertEqual(GLOSSARY, params['terminology_glossary_path'])
                self.assertEqual(SOURCE_HASH, params['manuscript_sha256'])
                self.assertEqual(GLOSSARY_HASH, params['terminology_glossary_sha256'])
                expected_files = {'language_report.md', 'language_changes.json', 'manuscript_edited.md'}
                self.assertEqual(expected_files, {Path(path).name for path in request.task.output_artifacts})
                self.assertEqual(set(request.task.output_artifacts), {item.path for item in result.output_artifacts})
                for path in request.task.output_artifacts:
                    self.assertTrue((ROOT / path).is_file())
                    self.assertGreater((ROOT / path).stat().st_size, 0)
                rel = f'paper-language-v0.1-fixture/run-{mode}'
                self.assertEqual([], validate_language_run(ROOT, MANUSCRIPT, f'{rel}/language_changes.json',
                                                            f'{rel}/manuscript_edited.md', self.glossary,
                                                            params['allowed_line_ranges']))
                self.assertEqual((run['dir'] / 'language_diff.patch').read_text(encoding='utf-8'),
                                 render_language_diff(ROOT, MANUSCRIPT, f'{rel}/manuscript_edited.md'))
        self.assertEqual(expected_hashes, {path: digest(ROOT / path) for path in expected_hashes})

    def test_modes_and_traceable_ambiguous_sentence(self):
        lines = self.source.splitlines()
        for mode, run in self.runs.items():
            with self.subTest(mode=mode):
                changes, edited = run['changes']['changes'], run['edited']
                self.assertTrue(changes)
                self.assertTrue(all(c['status'] in ('proposed', 'deferred') and c['approval_required'] is True for c in changes))
                for change in changes:
                    self.assertIn(change['change_id'], run['report'])
                self.assertIn('A multi-agent system (MAS) uses time series forecasts to coordinate agents.', edited)
                self.assertIn('The Horizon Mapper produces a forecast from the available observations.', edited)
                ambiguity = [c for c in changes if c['source_location']['start_line'] == 13]
                self.assertTrue(ambiguity)
                self.assertTrue(any(c['semantic_risk'] == 'high' and c['approval_required'] is True
                                    and c['status'] == 'deferred' and c['applied_to_draft'] is False
                                    for c in ambiguity))
                self.assertIn(lines[12], edited)
                self.assertIn('In order to be able to make decisions', lines[10])
                limitation = 'The synthetic result is limited to the described example.'
                if mode == 'proofreading':
                    self.assertIn(lines[10], edited)
                    self.assertIn(lines[35], edited)
                    self.assertEqual(2, edited.count(limitation))
                else:
                    self.assertNotIn('In order to be able to make decisions', edited)
                    self.assertIn('produced before', edited)
                    self.assertIn('decisions', edited)
                    self.assertEqual(1, edited.count(limitation))
                    self.assertIn('This limitation should be retained', edited)

    def test_preserved_literal_scientific_and_markdown_content(self):
        lines = self.source.splitlines()
        protected = [lines[18], '\n'.join(lines[20:24]), '\n'.join(lines[29:32]), lines[27], lines[39]]
        approved = [term for entry in self.glossary['terms'] if entry['approval_status'] == 'approved'
                    for term in (entry['canonical_term'], entry['abbreviation'], *entry['allowed_variants']) if term]
        for mode, run in self.runs.items():
            with self.subTest(mode=mode):
                edited = run['edited']
                for item in protected:
                    self.assertIn(item, edited)
                for literal in set(approved):
                    self.assertGreaterEqual(edited.count(literal), self.source.count(literal))
                for token in ('4 time steps', '0.25 units', '[@synthetic2026]', 'suggest', 'may', 'indicate', 'do not', 'simulated setting'):
                    self.assertEqual(self.source.count(token), edited.count(token))
                self.assertEqual([line for line in lines if line.startswith('#')],
                                 [line for line in edited.splitlines() if line.startswith('#')])


if __name__ == '__main__':
    unittest.main()
